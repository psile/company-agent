"""推送渠道：业务只认 user_id。账号里配了飞书密钥就用账号的，否则 mock。"""

from __future__ import annotations

from typing import Any, Protocol

from .config import get_bool, get_str
from .notify import NotificationLog


class PushChannel(Protocol):
    def send_message(self, user_id: str, content: dict[str, Any]) -> dict[str, Any]: ...


class MockFeishuChannel:
    def __init__(self, notify: NotificationLog) -> None:
        self.notify = notify

    def send_message(self, user_id: str, content: dict[str, Any]) -> dict[str, Any]:
        self.notify.add(
            {
                "user_id": user_id,
                "type": content.get("type") or "high_relevance",
                "title": content.get("title") or "",
                "content": content.get("text") or content.get("content") or "",
                "recommendation_id": content.get("id") or "",
            }
        )
        return {"ok": True, "channel": "mock", "user_id": user_id, "reason": "feishu not configured; wrote inbox"}


class WebChannel:
    def __init__(self, notify: NotificationLog) -> None:
        self.notify = notify

    def send_message(self, user_id: str, content: dict[str, Any]) -> dict[str, Any]:
        self.notify.add(
            {
                "user_id": user_id,
                "type": content.get("type") or "system",
                "title": content.get("title") or "",
                "content": content.get("text") or content.get("content") or "",
                "recommendation_id": content.get("id") or "",
            }
        )
        return {"ok": True, "channel": "web", "user_id": user_id}


def send_for_user(
    user_id: str,
    notify: NotificationLog,
    content: dict[str, Any],
    feishu_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .feishu import app_config_from, format_push, push_text

    mock = MockFeishuChannel(notify)
    if get_bool("RADAR_PUSH_DRY_RUN", False):
        result = mock.send_message(user_id, content)
        result["reason"] = "RADAR_PUSH_DRY_RUN enabled"
        return result
    user_keys = bool((feishu_cfg or {}).get("app_id") and (feishu_cfg or {}).get("app_secret"))
    if user_keys:
        cfg = app_config_from(feishu_cfg, use_env=False)
        if cfg.get("ready"):
            result = push_text(content.get("text") or format_push(content), app=cfg)
            result["user_id"] = user_id
            WebChannel(notify).send_message(user_id, content)
            return result
        mocked = mock.send_message(user_id, content)
        mocked["reason"] = cfg.get("reason") or "feishu account incomplete"
        return mocked
    if get_str("FEISHU_MODE", "mock").lower() in {"developer", "enterprise"}:
        cfg = app_config_from(feishu_cfg, use_env=True)
        if cfg.get("ready"):
            result = push_text(content.get("text") or format_push(content), app=cfg)
            result["user_id"] = user_id
            if result.get("ok"):
                WebChannel(notify).send_message(user_id, content)
            return result
    return mock.send_message(user_id, {**content, "type": "high_relevance"})
