"""Per-user preferences that control how the secretary communicates."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import _read_json, _write_json


DEFAULT_CONVERSATION_PROFILE = {
    "tone": "professional_friendly",
    "verbosity": "concise",
    "answer_style": "conclusion_first",
    "technical_detail": "high",
    "proactive_level": "medium",
    "confirmation_policy": "important_actions",
    "assistant_name": "",
    "updated_at": "",
}

ALLOWED = {
    "tone": {"professional_friendly", "professional", "friendly", "direct"},
    "verbosity": {"concise", "balanced", "detailed"},
    "answer_style": {"conclusion_first", "step_by_step"},
    "technical_detail": {"low", "medium", "high"},
    "proactive_level": {"low", "medium", "high"},
    "confirmation_policy": {"important_actions", "always", "never"},
}


class ConversationProfile:
    def __init__(self, user_root: Path) -> None:
        self.path = user_root / "conversation_profile.json"

    def get(self) -> dict[str, Any]:
        profile = dict(DEFAULT_CONVERSATION_PROFILE)
        profile.update(_read_json(self.path, {}))
        return profile

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self.get()
        for key, choices in ALLOWED.items():
            value = str(payload.get(key) or "").strip()
            if value in choices:
                profile[key] = value
        if "assistant_name" in payload:
            profile["assistant_name"] = str(payload.get("assistant_name") or "").strip()[:16]
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(self.path, profile)
        return profile

    def update_from_message(self, message: str) -> tuple[dict[str, Any], list[str]]:
        text = (message or "").lower()
        patch: dict[str, str] = {}
        changed: list[str] = []
        if any(word in text for word in ("简洁", "简短", "少一点", "短一点")):
            patch["verbosity"] = "concise"
            changed.append("普通回答保持简洁")
        if any(word in text for word in ("详细", "展开", "深入")):
            if any(word in text for word in ("技术", "代码", "工程")):
                patch["technical_detail"] = "high"
                changed.append("技术问题详细分析")
            else:
                patch["verbosity"] = "detailed"
                changed.append("回答更详细")
        if any(word in text for word in ("结论优先", "先说结论")):
            patch["answer_style"] = "conclusion_first"
            changed.append("结论优先")
        if any(word in text for word in ("发消息时先问", "推送前先问", "先确认")):
            patch["confirmation_policy"] = "always"
            changed.append("发送消息前先确认")
        if any(word in text for word in ("主动一点", "多提醒")):
            patch["proactive_level"] = "high"
            changed.append("提高主动服务级别")
        if any(word in text for word in ("少推送", "不要主动", "少打扰")):
            patch["proactive_level"] = "low"
            changed.append("降低主动打扰")
        return self.update(patch), changed
