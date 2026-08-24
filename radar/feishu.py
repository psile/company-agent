"""Feishu push channels.

Preferred: app bot one-to-one messages. Fallback: custom webhook bot.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .config import get_bool, load_env
from .models import ScoredItem


def format_card(item: ScoredItem) -> str:
    return format_push(item.to_dict() if hasattr(item, "to_dict") else item)  # type: ignore[arg-type]


def format_interest_card(item: ScoredItem) -> str:
    return format_push(item.to_dict())


def format_push(item: dict | ScoredItem) -> str:
    data = item.to_dict() if isinstance(item, ScoredItem) else item
    tags = " · ".join(str(x) for x in (data.get("tags") or data.get("matched") or [])[:5])
    summary = data.get("summary_zh") or data.get("summary") or ""
    why = data.get("why_you") or data.get("why") or ""
    project = data.get("project_value") or ""
    score = data.get("score") or 0
    lines = [
        f"【为你发现】{data.get('title')}",
        f"标签 {tags}" if tags else "",
        f"相关度 {score}%",
        f"总结：{summary}" if summary else "",
        f"为什么推给你：{why}" if why else "",
        f"和当前项目：{project}" if project else "",
        f"原文 {data.get('source_url')}",
    ]
    return "\n".join(line for line in lines if line)


def push_text(text: str) -> dict:
    load_env()
    if get_bool("RADAR_PUSH_DRY_RUN", False):
        return {"ok": False, "reason": "RADAR_PUSH_DRY_RUN enabled", "text": text}
    app = _app_config()
    if app["ready"]:
        return push_app_text(text, app)
    url = (os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        return {"ok": False, "reason": "Feishu app bot/webhook not configured", "text": text}
    return push_webhook_text(text, url)


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


def push_webhook_text(text: str, url: str | None = None) -> dict:
    load_env()
    webhook = (url or os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()
    if not webhook:
        return {"ok": False, "reason": "FEISHU_WEBHOOK_URL not set", "text": text}
    payload = {"msg_type": "text", "content": {"text": text}}
    secret = (os.environ.get("FEISHU_SECRET") or "").strip()
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _sign(timestamp, secret)
    result = _post_json(webhook, payload)
    result["channel"] = "webhook"
    result["text"] = text
    return result


def _sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _app_config() -> dict[str, Any]:
    load_env()
    cfg = {
        "app_id": (os.environ.get("FEISHU_APP_ID") or "").strip(),
        "app_secret": (os.environ.get("FEISHU_APP_SECRET") or "").strip(),
        "receive_id_type": (os.environ.get("FEISHU_RECEIVE_ID_TYPE") or "email").strip(),
        "receive_id": (os.environ.get("FEISHU_RECEIVE_ID") or "").strip(),
        "receive_mobile": (os.environ.get("FEISHU_RECEIVE_MOBILE") or "").strip(),
    }
    missing = [key for key in ("app_id", "app_secret") if not cfg[key]]
    if not cfg["receive_id"] and not cfg["receive_mobile"]:
        missing.append("receive_id or receive_mobile")
    cfg["ready"] = not missing
    cfg["reason"] = "ok" if cfg["ready"] else f"missing {', '.join(missing)}"
    return cfg


def _tenant_access_token(app_id: str, app_secret: str) -> dict[str, Any]:
    result = _post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = result.get("data", {}).get("tenant_access_token") or result.get("tenant_access_token")
    if result.get("ok") and token:
        return {"ok": True, "tenant_access_token": token}
    return {"ok": False, "reason": result.get("reason") or "tenant access token missing", "response": result}


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
