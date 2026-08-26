"""当前用户的站内通知。飞书 mock 时也写这里。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .store import _read_json, _write_json


class NotificationLog:
    def __init__(self, user_root: Path) -> None:
        self.path = user_root / "notifications.json"

    def list(self) -> list[dict[str, Any]]:
        return list(_read_json(self.path, {"items": []}).get("items") or [])

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": payload.get("id") or uuid4().hex[:12],
            "user_id": payload.get("user_id"),
            "type": payload.get("type") or "high_relevance",
            "title": payload.get("title") or "",
            "content": payload.get("content") or "",
            "recommendation_id": payload.get("recommendation_id") or "",
            "read_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        rows = self.list()
        rows.insert(0, row)
        _write_json(self.path, {"items": rows[:80]})
        return row
