"""Feishu inbound chat: long connection + HTTP event webhook.

Turns im.message.receive_v1 into ConversationService.chat, then replies
in the same Feishu thread. Optional dependency: lark-oapi (WebSocket only).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import threading
import time
from typing import Any, Callable

from .config import get_bool, get_str, load_env
from .feishu import bot_credentials, lookup_user_profile, reply_message, send_chat_text


SESSION_ID = "feishu"
_SEEN_MAX = 2000
_seen: dict[str, float] = {}
_seen_lock = threading.Lock()
_ws_started = False
_ChatFn = Callable[[Any, str, str], dict[str, Any]]
_ReplyFn = Callable[..., dict[str, Any]]
_ProfileFn = Callable[[str], dict[str, Any]]


def inbox_wanted() -> bool:
    load_env()
    has_creds = bool(get_str("FEISHU_APP_ID") and get_str("FEISHU_APP_SECRET"))
    if os.environ.get("FEISHU_INBOX") is None:
        return has_creds
    return get_bool("FEISHU_INBOX", False)


def inbox_status() -> dict[str, Any]:
    load_env()
    creds = bot_credentials()
    return {
        "enabled": inbox_wanted(),
        "credentials": bool(creds.get("ready")),
        "running": _ws_started,
        "user_hint": get_str("FEISHU_INBOX_USER"),
    }


def webhook_ack(body: dict[str, Any] | None) -> dict[str, str] | None:
    payload = body or {}
    if payload.get("type") == "url_verification":
        return {"challenge": str(payload.get("challenge") or "")}
    if "challenge" in payload and not payload.get("event") and not payload.get("header"):
        return {"challenge": str(payload.get("challenge") or "")}
    return None


def verify_webhook(body: dict[str, Any] | None) -> bool:
    expected = get_str("FEISHU_VERIFICATION_TOKEN")
    if not expected:
        return True
    payload = body or {}
    token = str(payload.get("token") or (payload.get("header") or {}).get("token") or "")
    return token == expected


def extract_message_text(message: dict[str, Any] | None) -> str:
    msg = message or {}
    raw = msg.get("content")
    parsed: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _strip_mentions(text)
    if not isinstance(parsed, dict):
        return _strip_mentions(str(parsed or "").strip())
    msg_type = str(msg.get("message_type") or msg.get("msg_type") or "text")
    if msg_type == "post":
        return _strip_mentions(_flatten_post(parsed))
    return _strip_mentions(str(parsed.get("text") or "").strip())


def normalize_event(envelope: dict[str, Any] | None) -> dict[str, Any]:
    payload = envelope or {}
    event = payload.get("event")
    if isinstance(event, dict) and (event.get("message") or event.get("sender")):
        return event
    if payload.get("message") and payload.get("sender"):
        return payload
    return {}


def handle_incoming(
    service: Any,
    envelope: dict[str, Any],
    *,
    send_reply: _ReplyFn | None = None,
    lookup_profile: _ProfileFn | None = None,
    chat_fn: _ChatFn | None = None,
) -> dict[str, Any]:
    event = normalize_event(envelope)
    if not event:
        return {"ok": False, "skipped": "not_message"}
    sender = event.get("sender") or {}
    message = event.get("message") or {}
    sender_type = str(sender.get("sender_type") or "").strip().lower()
    if sender_type in {"app", "bot"}:
        return {"ok": True, "skipped": "bot"}
    message_id = str(message.get("message_id") or "").strip()
    if _already_seen(message_id):
        return {"ok": True, "skipped": "duplicate", "message_id": message_id}
    chat_type = str(message.get("chat_type") or "").strip().lower()
    mentions = message.get("mentions") or []
    if chat_type == "group" and not mentions:
        return {"ok": True, "skipped": "group_no_mention", "message_id": message_id}
    text = extract_message_text(message)
    if not text:
        return {"ok": True, "skipped": "empty", "message_id": message_id}

    sender_id = sender.get("sender_id") or {}
    open_id = str(sender_id.get("open_id") or sender_id.get("user_id") or "").strip()
    profile = {}
    try:
        profile = (lookup_profile or _default_lookup_profile)(open_id) or {}
    except Exception as exc:
        print("[feishu-inbox] profile lookup failed", exc)
    user_id = resolve_inbox_user(service, open_id, profile)
    if not user_id:
        return {"ok": False, "skipped": "unmapped", "open_id": open_id, "message_id": message_id}

    try:
        result = (chat_fn or _default_chat)(service, user_id, text)
    except Exception as exc:
        print("[feishu-inbox] chat failed", exc)
        return {"ok": False, "error": str(exc), "user_id": user_id, "message_id": message_id}

    reply = str(result.get("reply") or "").strip()
    sent = {"ok": False, "reason": "empty reply"}
    if reply:
        try:
            sent = (send_reply or _default_send_reply)(
                message_id=message_id,
                chat_id=str(message.get("chat_id") or ""),
                text=reply,
            )
        except Exception as exc:
            sent = {"ok": False, "reason": str(exc)}
    return {
        "ok": bool(sent.get("ok")),
        "user_id": user_id,
        "message_id": message_id,
        "intent": result.get("intent"),
        "session_id": result.get("session_id") or SESSION_ID,
        "reply": reply,
        "send": sent,
    }


def resolve_inbox_user(service: Any, open_id: str, profile: dict[str, Any] | None = None) -> str | None:
    oid = (open_id or "").strip()
    if not oid:
        return None
    emails = _profile_emails(profile)
    name = str((profile or {}).get("name") or "").strip()

    matched = _identity_user(service, oid)
    if matched:
        return matched
    for email in emails:
        matched = _identity_user(service, email)
        if matched:
            _bind_open_id(service, matched, oid)
            return matched

    for uid in service.identity.active_ids():
        raw = service._feishu_raw(uid)
        rid = str(raw.get("receive_id") or "").strip()
        if not rid:
            continue
        if rid == oid or rid.lower() in emails:
            _bind_open_id(service, uid, oid)
            return uid

    env_rid = get_str("FEISHU_RECEIVE_ID")
    env_hit = bool(env_rid) and (env_rid == oid or env_rid.lower() in emails)
    fallback = get_str("FEISHU_INBOX_USER")
    if env_hit and fallback:
        try:
            uid = service.identity.require(fallback)
            _bind_open_id(service, uid, oid)
            return uid
        except KeyError:
            pass
    if fallback:
        try:
            uid = service.identity.require(fallback)
            _bind_open_id(service, uid, oid)
            return uid
        except KeyError:
            pass

    unique = _unique_feishu_account(service)
    if unique:
        _bind_open_id(service, unique, oid)
        return unique

    user = service.identity.resolve_user("feishu", oid, display_name=name or oid)
    return str(user.get("id") or "") or None


def push_inbox_text(service: Any, user_id: str, text: str) -> dict[str, Any]:
    """Send a proactive line through the same inbox bot that receives Feishu chats."""
    from .config import get_bool
    from .feishu import send_open_id_text

    if get_bool("RADAR_PUSH_DRY_RUN", False):
        return {"ok": False, "reason": "RADAR_PUSH_DRY_RUN enabled"}
    oid = _open_id_for_user(service, user_id)
    if not oid:
        return {"ok": False, "reason": "no feishu open_id"}
    return send_open_id_text(oid, text)


def _open_id_for_user(service: Any, user_id: str) -> str:
    uid = (user_id or "").strip()
    for row in service.identity.identities():
        if str(row.get("user_id") or "") != uid or row.get("provider") != "feishu":
            continue
        ext = str(row.get("external_id") or "").strip()
        if ext.startswith("ou_"):
            return ext
    for row in service.identity.channels():
        if str(row.get("user_id") or "") != uid or row.get("channel_type") != "feishu":
            continue
        ext = str(row.get("external_user_id") or "").strip()
        if ext.startswith("ou_"):
            return ext
    return ""


def start_feishu_inbox(service: Any) -> None:
    global _ws_started
    if not inbox_wanted():
        if get_str("FEISHU_APP_ID") or get_str("FEISHU_APP_SECRET"):
            print("[feishu-inbox] 已关闭（FEISHU_INBOX=0）")
        else:
            print("[feishu-inbox] 未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，跳过长连接")
        return
    creds = bot_credentials()
    if not creds.get("ready"):
        print("[feishu-inbox] 凭证不完整，跳过长连接")
        return
    try:
        bind_known_recipients(service)
    except Exception as exc:
        print("[feishu-inbox] 预绑定接收人失败", exc)

    def loop() -> None:
        try:
            import lark_oapi as lark  # noqa: F401
        except ImportError:
            print("[feishu-inbox] 未安装 lark-oapi，长连接不可用。运行: pip install lark-oapi")
            print("[feishu-inbox] HTTP 回调仍可用：POST /api/feishu/event")
            return
        try:
            run_ws_client(service)
        except Exception as exc:
            print("[feishu-inbox] 长连接退出", exc)

    threading.Thread(target=loop, daemon=True, name="radar-feishu-inbox").start()
    _ws_started = True
    hint = get_str("FEISHU_INBOX_USER") or _unique_feishu_account(service) or ""
    extra = f" default_user={hint}" if hint else ""
    print(f"[feishu-inbox] 长连接已启动{extra}。飞书里发「你好」应收到秘书回复。")


def run_ws_client(service: Any) -> None:
    import lark_oapi as lark

    creds = bot_credentials()

    def on_message(data) -> None:
        envelope = _event_dict_from_lark(data)
        threading.Thread(
            target=process_event,
            args=(service, envelope, "ws"),
            daemon=True,
            name="radar-feishu-chat",
        ).start()

    handler = (
        lark.EventDispatcherHandler.builder(get_str("FEISHU_ENCRYPT_KEY"), get_str("FEISHU_VERIFICATION_TOKEN"))
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    client = lark.ws.Client(
        creds["app_id"],
        creds["app_secret"],
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    client.start()


def bind_known_recipients(service: Any) -> None:
    """If a user saved a Feishu mobile, resolve it to open_id so inbound chat maps to them."""
    creds = bot_credentials()
    if not creds.get("ready"):
        return
    from .feishu import _tenant_access_token, lookup_open_id_by_mobile

    token = _tenant_access_token(creds["app_id"], creds["app_secret"])
    if not token.get("ok"):
        return
    for uid in service.identity.active_ids():
        raw = service._feishu_raw(uid)
        mobile = str(raw.get("receive_mobile") or "").strip()
        if not mobile:
            continue
        resolved = lookup_open_id_by_mobile(token["tenant_access_token"], mobile)
        if resolved.get("ok") and resolved.get("open_id"):
            _bind_open_id(service, uid, str(resolved["open_id"]))
            print(f"[feishu-inbox] 已按手机号绑定账号 {uid}")


def process_event(service: Any, body: dict[str, Any], source: str = "http") -> None:
    try:
        result = handle_incoming(service, body)
        print(
            "[feishu-inbox]",
            f"{source} ok={result.get('ok')} skipped={result.get('skipped')} "
            f"user={result.get('user_id')} intent={result.get('intent')}",
        )
    except Exception as exc:
        print(f"[feishu-inbox] {source} handler error", exc)


def handle_http_event(service: Any, body: dict[str, Any]) -> None:
    process_event(service, body, "http")


def _default_chat(service: Any, user_id: str, text: str) -> dict[str, Any]:
    store = service.conversation.store(user_id)
    store.ensure_session(SESSION_ID, "飞书对话")

    def invoke() -> dict[str, Any]:
        return asyncio.run(service.chat(text, session_id=SESSION_ID, user_id=user_id))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return invoke()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(invoke).result(timeout=120)


def _default_send_reply(*, message_id: str, chat_id: str, text: str) -> dict[str, Any]:
    result = reply_message(message_id, text)
    if result.get("ok"):
        return result
    if chat_id:
        fallback = send_chat_text(chat_id, text)
        fallback["fallback"] = "chat_id"
        fallback["reply_error"] = result.get("reason")
        return fallback
    return result


def _default_lookup_profile(open_id: str) -> dict[str, Any]:
    creds = bot_credentials()
    if not creds.get("ready") or not open_id:
        return {}
    from .feishu import _tenant_access_token

    token = _tenant_access_token(creds["app_id"], creds["app_secret"])
    if not token.get("ok"):
        return {}
    return lookup_user_profile(token["tenant_access_token"], open_id)


def _unique_feishu_account(service: Any) -> str | None:
    found: list[str] = []
    for uid in service.identity.active_ids():
        raw = service._feishu_raw(uid)
        if raw.get("app_id") and raw.get("app_secret"):
            found.append(uid)
    if len(found) == 1:
        return found[0]
    return None


def _identity_user(service: Any, external_id: str) -> str | None:
    needle = (external_id or "").strip()
    if not needle:
        return None
    lower = needle.lower()
    for row in service.identity.identities():
        if row.get("provider") != "feishu":
            continue
        ext = str(row.get("external_id") or "").strip()
        if ext == needle or ext.lower() == lower:
            uid = str(row.get("user_id") or "")
            if uid:
                return uid
    return None


def _bind_open_id(service: Any, user_id: str, open_id: str) -> None:
    try:
        service.identity.bind_identity(user_id, "feishu", open_id)
    except ValueError:
        pass


def _profile_emails(profile: dict[str, Any] | None) -> list[str]:
    emails: list[str] = []
    for key in ("email", "enterprise_email"):
        value = str((profile or {}).get(key) or "").strip().lower()
        if value and value not in emails:
            emails.append(value)
    return emails


def _already_seen(message_id: str) -> bool:
    mid = (message_id or "").strip()
    if not mid:
        return False
    now = time.time()
    with _seen_lock:
        if mid in _seen:
            return True
        _seen[mid] = now
        if len(_seen) > _SEEN_MAX:
            oldest = sorted(_seen.items(), key=lambda item: item[1])[: _SEEN_MAX // 2]
            for key, _ in oldest:
                _seen.pop(key, None)
        return False


def _strip_mentions(text: str) -> str:
    return re.sub(r"@_user_\d+\s*", "", text or "").strip()


def _flatten_post(content: dict[str, Any]) -> str:
    title = str(content.get("title") or "").strip()
    parts: list[str] = []
    for paragraph in content.get("content") or []:
        for span in paragraph or []:
            if isinstance(span, dict):
                parts.append(str(span.get("text") or ""))
            elif span:
                parts.append(str(span))
    body = "".join(parts).strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body


def _event_dict_from_lark(data: Any) -> dict[str, Any]:
    try:
        import lark_oapi as lark

        raw = json.loads(lark.JSON.marshal(data))
        if isinstance(raw, dict):
            if raw.get("event") or (raw.get("message") and raw.get("sender")):
                return raw
            return {"event": raw}
    except Exception:
        pass
    event = getattr(data, "event", None)
    sender = getattr(event, "sender", None)
    sender_id = getattr(sender, "sender_id", None)
    message = getattr(event, "message", None)
    return {
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": getattr(sender_id, "open_id", None),
                    "user_id": getattr(sender_id, "user_id", None),
                },
                "sender_type": getattr(sender, "sender_type", None),
            },
            "message": {
                "message_id": getattr(message, "message_id", None),
                "chat_id": getattr(message, "chat_id", None),
                "chat_type": getattr(message, "chat_type", None),
                "message_type": getattr(message, "message_type", None),
                "content": getattr(message, "content", None),
                "mentions": list(getattr(message, "mentions", None) or []),
            },
        }
    }


def reset_seen_for_tests() -> None:
    with _seen_lock:
        _seen.clear()
