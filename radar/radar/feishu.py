"""Feishu push channels.

Preferred: app bot one-to-one messages. Fallback: custom webhook bot.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import get_bool, load_env
from .models import ScoredItem


_TOKEN_CACHE: dict[tuple[str, str], tuple[float, str]] = {}
_TOKEN_LOCK = threading.Lock()


def format_card(item: ScoredItem) -> str:
    return format_push(item.to_dict() if hasattr(item, "to_dict") else item)  # type: ignore[arg-type]


def format_interest_card(item: ScoredItem) -> str:
    return format_push(item.to_dict())


def format_push(item: dict | ScoredItem) -> str:
    """把推荐内容组织成一眼能看懂的简报，不是结构化数据 dump。"""
    data = item.to_dict() if isinstance(item, ScoredItem) else item
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary_zh") or data.get("summary") or "").strip()
    why = str(data.get("why_you") or data.get("why") or "").strip()
    project = str(data.get("project_value") or "").strip()
    points = [str(x).strip() for x in (data.get("key_points") or data.get("innovation") or []) if str(x).strip()][:3]
    impact = str(data.get("impact") or "").strip()
    watch = str(data.get("what_to_watch") or "").strip()
    interesting = str(data.get("interesting_point") or "").strip()
    tags = [str(x) for x in (data.get("tags") or data.get("matched") or [])[:5] if str(x).strip()]
    source_name = str(data.get("source_name") or "").strip()
    source_url = str(data.get("source_url") or "").strip()
    lane_name = {
        "work": "工作情报",
        "industry": "行业动态",
        "discovery": "轻松发现",
        "personal": "个人兴趣",
    }.get(str(data.get("lane") or ""), "为你发现")

    # ── 标题行：类型 + 标题 + 来源 ──
    head = f"【{lane_name}】{title}"
    if source_name:
        head += f"（{source_name}）"

    # ── 核心内容：这段在做什么、贡献点是什么 ──
    core_parts = []
    if summary:
        core_parts.append(summary)
    if interesting:
        core_parts.append(f"值得注意：{interesting}")

    # ── 关键贡献 / 方法 ──
    contribution_lines = []
    if points:
        contribution_lines.append("核心要点：")
        for p in points:
            contribution_lines.append(f"  · {p}")
    if impact:
        contribution_lines.append(f"影响：{impact}")

    # ── 方向 ──
    direction_lines = []
    if watch:
        direction_lines.append(f"后续关注：{watch}")
    if project:
        direction_lines.append(f"与你的项目：{project}")
    if why:
        direction_lines.append(f"推荐理由：{why}")

    # ── 关键词 + 源链接 ──
    kw_line = ""
    if tags:
        kw_line = "关键词：" + "、".join(tags)
    link_line = ""
    if source_url:
        link_line = f"原文链接：{source_url}"

    # 拼装：用空行分段，让阅读节奏自然
    blocks = [head]
    if core_parts:
        blocks.append("\n".join(core_parts))
    if contribution_lines:
        blocks.append("\n".join(contribution_lines))
    if direction_lines:
        blocks.append("\n".join(direction_lines))
    footer_parts = [x for x in [kw_line, link_line] if x]
    if footer_parts:
        blocks.append("\n".join(footer_parts))

    return "\n\n".join(blocks)


def push_text(text: str, app: dict | None = None) -> dict:
    load_env()
    if get_bool("RADAR_PUSH_DRY_RUN", False):
        return {"ok": False, "reason": "RADAR_PUSH_DRY_RUN enabled", "text": text}
    cfg = app or _app_config()
    if cfg.get("ready"):
        return push_app_text(text, cfg)
    url = (cfg.get("webhook_url") or os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        return {"ok": False, "reason": "Feishu app bot/webhook not configured", "text": text}
    return push_webhook_text(text, url, secret=cfg.get("webhook_secret") or None)


def feishu_status() -> dict[str, Any]:
    load_env()
    app = _app_config()
    webhook = bool((os.environ.get("FEISHU_WEBHOOK_URL") or "").strip())
    channel = "app_bot" if app["ready"] else "webhook" if webhook else "none"
    return {
        "ok": app["ready"] or webhook,
        "channel": channel,
        "app_bot": app["ready"],
        "webhook": webhook,
        "reason": app["reason"] if not app["ready"] and not webhook else "ok",
        "receive_id_type": app.get("receive_id_type", ""),
        "receive_mobile": bool(app.get("receive_mobile")),
    }


def validate_app_config(app: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials and, when possible, resolve the configured recipient."""
    cfg = app_config_from(app, use_env=False)
    if not cfg.get("ready"):
        return {
            "ok": False,
            "credentials_ok": False,
            "recipient_ok": False,
            "reason": cfg.get("reason") or "飞书配置不完整",
        }

    token = _tenant_access_token(cfg["app_id"], cfg["app_secret"])
    if not token.get("ok"):
        return {
            "ok": False,
            "credentials_ok": False,
            "recipient_ok": False,
            "reason": token.get("reason") or "App ID 或 App Secret 验证失败",
        }

    receive_id = str(cfg.get("receive_id") or "").strip()
    receive_type = str(cfg.get("receive_id_type") or "email").strip()
    mobile = str(cfg.get("receive_mobile") or "").strip()
    if not receive_id and mobile:
        resolved = _lookup_open_id_by_mobile(token["tenant_access_token"], mobile)
        if not resolved.get("ok"):
            return {
                "ok": False,
                "credentials_ok": True,
                "recipient_ok": False,
                "reason": resolved.get("reason") or "凭证有效，但无法通过手机号找到接收人",
            }
        return {
            "ok": True,
            "credentials_ok": True,
            "recipient_ok": True,
            "reason": "App ID、App Secret 和接收人均验证成功",
        }

    if receive_type == "open_id" and not receive_id.startswith("ou_"):
        return {
            "ok": False,
            "credentials_ok": True,
            "recipient_ok": False,
            "reason": "App ID 和 App Secret 有效，但 open_id 格式不正确，应以 ou_ 开头",
        }
    if receive_type == "email" and "@" not in receive_id:
        return {
            "ok": False,
            "credentials_ok": True,
            "recipient_ok": False,
            "reason": "App ID 和 App Secret 有效，但接收邮箱格式不正确",
        }
    return {
        "ok": True,
        "credentials_ok": True,
        "recipient_ok": True,
        "reason": "App ID 和 App Secret 验证成功，接收人格式正确",
    }


def push_app_text(text: str, app: dict[str, str] | None = None) -> dict:
    load_env()
    cfg = app or _app_config()
    if not cfg["ready"]:
        return {"ok": False, "reason": cfg["reason"], "text": text}
    token = _tenant_access_token(cfg["app_id"], cfg["app_secret"])
    if not token.get("ok"):
        token["text"] = text
        return token
    if not cfg["receive_id"] and cfg.get("receive_mobile"):
        resolved = _lookup_open_id_by_mobile(token["tenant_access_token"], cfg["receive_mobile"])
        if not resolved.get("ok"):
            resolved["text"] = text
            return resolved
        cfg = dict(cfg)
        cfg["receive_id_type"] = "open_id"
        cfg["receive_id"] = resolved["open_id"]
    receive_id_type = cfg["receive_id_type"]
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    payload = _app_message_payload(cfg["receive_id"], text)
    result = _post_json(url, payload, headers={"Authorization": f"Bearer {token['tenant_access_token']}"})
    result["channel"] = "app_bot"
    result["receive_id_type"] = receive_id_type
    result["receive_id"] = cfg["receive_id"]
    result["text"] = text
    return result


def push_webhook_text(text: str, url: str | None = None, secret: str | None = None) -> dict:
    load_env()
    webhook = (url or os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()
    if not webhook:
        return {"ok": False, "reason": "FEISHU_WEBHOOK_URL not set", "text": text}
    payload = {"msg_type": "text", "content": {"text": text}}
    sign_secret = (secret if secret is not None else os.environ.get("FEISHU_SECRET") or "").strip()
    if sign_secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _sign(timestamp, sign_secret)
    result = _post_json(webhook, payload)
    result["channel"] = "webhook"
    result["text"] = text
    return result


def _sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _app_config() -> dict[str, Any]:
    return app_config_from(None, use_env=True)


def app_config_from(overrides: dict[str, Any] | None = None, use_env: bool = True) -> dict[str, Any]:
    load_env()
    cfg = {
        "app_id": "",
        "app_secret": "",
        "receive_id_type": "email",
        "receive_id": "",
        "receive_mobile": "",
        "webhook_url": "",
        "webhook_secret": "",
    }
    if use_env:
        cfg.update(
            {
                "app_id": (os.environ.get("FEISHU_APP_ID") or "").strip(),
                "app_secret": (os.environ.get("FEISHU_APP_SECRET") or "").strip(),
                "receive_id_type": (os.environ.get("FEISHU_RECEIVE_ID_TYPE") or "email").strip() or "email",
                "receive_id": (os.environ.get("FEISHU_RECEIVE_ID") or "").strip(),
                "receive_mobile": (os.environ.get("FEISHU_RECEIVE_MOBILE") or "").strip(),
                "webhook_url": (os.environ.get("FEISHU_WEBHOOK_URL") or "").strip(),
                "webhook_secret": (os.environ.get("FEISHU_SECRET") or "").strip(),
            }
        )
    for key in ("app_id", "app_secret", "receive_id_type", "receive_id", "receive_mobile", "webhook_url", "webhook_secret"):
        value = str((overrides or {}).get(key) or "").strip()
        if value:
            cfg[key] = value
    missing = [key for key in ("app_id", "app_secret") if not cfg[key]]
    cfg["has_credentials"] = not missing
    if not cfg["receive_id"] and not cfg["receive_mobile"]:
        missing.append("receive_id or receive_mobile")
    cfg["ready"] = not missing
    cfg["reason"] = "ok" if cfg["ready"] else f"missing {', '.join(missing)}"
    return cfg


def bot_credentials(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """App ID / Secret only. Inbound chat does not need a preconfigured receive_id."""
    load_env()
    cfg = {
        "app_id": (os.environ.get("FEISHU_APP_ID") or "").strip(),
        "app_secret": (os.environ.get("FEISHU_APP_SECRET") or "").strip(),
    }
    for key in ("app_id", "app_secret"):
        value = str((overrides or {}).get(key) or "").strip()
        if value:
            cfg[key] = value
    cfg["ready"] = bool(cfg["app_id"] and cfg["app_secret"])
    cfg["reason"] = "ok" if cfg["ready"] else "missing app_id or app_secret"
    return cfg


def reply_message(message_id: str, text: str, app: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = bot_credentials(app)
    if not cfg["ready"]:
        return {"ok": False, "reason": cfg["reason"], "text": text}
    mid = (message_id or "").strip()
    if not mid:
        return {"ok": False, "reason": "message_id required", "text": text}
    token = _tenant_access_token(cfg["app_id"], cfg["app_secret"])
    if not token.get("ok"):
        token["text"] = text
        return token
    quoted = urllib.parse.quote(mid, safe="")
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{quoted}/reply"
    payload = {"content": json.dumps({"text": text}, ensure_ascii=False), "msg_type": "text"}
    result = _post_json(url, payload, headers={"Authorization": f"Bearer {token['tenant_access_token']}"})
    result["channel"] = "app_bot_reply"
    result["message_id"] = mid
    result["text"] = text
    return result


def send_chat_text(chat_id: str, text: str, app: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = bot_credentials(app)
    if not cfg["ready"]:
        return {"ok": False, "reason": cfg["reason"], "text": text}
    cid = (chat_id or "").strip()
    if not cid:
        return {"ok": False, "reason": "chat_id required", "text": text}
    token = _tenant_access_token(cfg["app_id"], cfg["app_secret"])
    if not token.get("ok"):
        token["text"] = text
        return token
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    result = _post_json(
        url,
        _app_message_payload(cid, text),
        headers={"Authorization": f"Bearer {token['tenant_access_token']}"},
    )
    result["channel"] = "app_bot_chat"
    result["chat_id"] = cid
    result["text"] = text
    return result


def send_open_id_text(open_id: str, text: str, app: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = bot_credentials(app)
    if not cfg["ready"]:
        return {"ok": False, "reason": cfg["reason"], "text": text}
    oid = (open_id or "").strip()
    if not oid:
        return {"ok": False, "reason": "open_id required", "text": text}
    token = _tenant_access_token(cfg["app_id"], cfg["app_secret"])
    if not token.get("ok"):
        token["text"] = text
        return token
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    result = _post_json(
        url,
        _app_message_payload(oid, text),
        headers={"Authorization": f"Bearer {token['tenant_access_token']}"},
    )
    result["channel"] = "app_bot_open_id"
    result["open_id"] = oid
    result["text"] = text
    return result


def lookup_user_profile(tenant_access_token: str, open_id: str) -> dict[str, Any]:
    oid = (open_id or "").strip()
    if not oid:
        return {}
    quoted = urllib.parse.quote(oid, safe="")
    url = f"https://open.feishu.cn/open-apis/contact/v3/users/{quoted}?user_id_type=open_id"
    result = _get_json(url, headers={"Authorization": f"Bearer {tenant_access_token}"})
    if not result.get("ok"):
        return {}
    user = result.get("data", {}).get("data", {}).get("user") or result.get("data", {}).get("user") or {}
    return {
        "email": str(user.get("email") or "").strip(),
        "enterprise_email": str(user.get("enterprise_email") or "").strip(),
        "name": str(user.get("name") or "").strip(),
        "open_id": str(user.get("open_id") or oid).strip(),
    }


def _tenant_access_token(app_id: str, app_secret: str) -> dict[str, Any]:
    cache_key = (app_id, hashlib.sha256(app_secret.encode("utf-8")).hexdigest())
    now = time.time()
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return {"ok": True, "tenant_access_token": cached[1], "cached": True}
    result = _post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = result.get("data", {}).get("tenant_access_token") or result.get("tenant_access_token")
    if result.get("ok") and token:
        raw_ttl = result.get("data", {}).get("expire") or result.get("expire") or 7200
        try:
            ttl = max(60, int(raw_ttl) - 300)
        except (TypeError, ValueError):
            ttl = 6900
        with _TOKEN_LOCK:
            _TOKEN_CACHE[cache_key] = (now + ttl, str(token))
        return {"ok": True, "tenant_access_token": token}
    return {"ok": False, "reason": result.get("reason") or "tenant access token missing", "response": result}


def reset_token_cache_for_tests() -> None:
    with _TOKEN_LOCK:
        _TOKEN_CACHE.clear()


def lookup_open_id_by_mobile(tenant_access_token: str, mobile: str) -> dict[str, Any]:
    return _lookup_open_id_by_mobile(tenant_access_token, mobile)


def _lookup_open_id_by_mobile(tenant_access_token: str, mobile: str) -> dict[str, Any]:
    result = _post_json(
        "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id?user_id_type=open_id",
        {"mobiles": [mobile]},
        headers={"Authorization": f"Bearer {tenant_access_token}"},
    )
    if not result.get("ok"):
        return result
    users = result.get("data", {}).get("data", {}).get("user_list") or result.get("data", {}).get("user_list") or []
    if not users:
        return {"ok": False, "reason": "mobile not found or no contact permission"}
    open_id = users[0].get("user_id")
    if not open_id:
        return {"ok": False, "reason": "open_id missing in lookup response", "data": users[0]}
    return {"ok": True, "open_id": open_id}


def _app_message_payload(receive_id: str, text: str) -> dict[str, str]:
    return {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "reason": str(exc)}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "response": raw}
    code = parsed.get("code", 0)
    if code not in (0, None):
        return {"ok": False, "reason": parsed.get("msg") or parsed.get("message") or str(code), "data": parsed}
    return {"ok": True, "data": parsed}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json; charset=utf-8"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "reason": str(exc)}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "response": raw}
    code = parsed.get("code", 0)
    if code not in (0, None):
        return {"ok": False, "reason": parsed.get("msg") or parsed.get("message") or str(code), "data": parsed}
    return {"ok": True, "data": parsed}
