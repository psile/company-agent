"""Per-user conversation persistence with bounded context windows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import _read_json, _write_json


CONTEXT_WINDOW = 16


class ConversationStore:
    def __init__(self, user_root: Path, user_id: str) -> None:
        self.user_id = user_id
        self.root = user_root / "conversations"
        self.sessions_path = self.root / "sessions.json"
        self.messages_path = self.root / "messages.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def sessions(self) -> list[dict[str, Any]]:
        rows = list(_read_json(self.sessions_path, {"items": []}).get("items") or [])
        rows = [row for row in rows if row.get("user_id") == self.user_id]
        return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)

    def create_session(self, title: str = "新对话") -> dict[str, Any]:
        now = _now()
        session = {
            "id": uuid.uuid4().hex[:16],
            "user_id": self.user_id,
            "title": (title or "新对话").strip()[:60],
            "created_at": now,
            "updated_at": now,
        }
        rows = self.sessions()
        rows.insert(0, session)
        _write_json(self.sessions_path, {"items": rows[:100]})
        return session

    def require_session(self, session_id: str | None, title: str = "新对话") -> dict[str, Any]:
        if session_id:
            for row in self.sessions():
                if row.get("id") == session_id and row.get("user_id") == self.user_id:
                    return row
            raise KeyError("conversation not found")
        return self.create_session(title)

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        if not any(row.get("id") == session_id for row in self.sessions()):
            raise KeyError("conversation not found")
        rows = list(_read_json(self.messages_path, {"items": []}).get("items") or [])
        return [
            row
            for row in rows
            if row.get("user_id") == self.user_id and row.get("session_id") == session_id
        ]

    def context(self, session_id: str, limit: int = CONTEXT_WINDOW) -> list[dict[str, Any]]:
        return self.messages(session_id)[-max(2, min(limit, CONTEXT_WINDOW)) :]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require_session(session_id)
        message = {
            "id": uuid.uuid4().hex[:16],
            "session_id": session_id,
            "user_id": self.user_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": _now(),
        }
        data = _read_json(self.messages_path, {"items": []})
        rows = list(data.get("items") or [])
        rows.append(message)
        _write_json(self.messages_path, {"items": rows[-4000:]})
        self._touch(session_id, content if role == "user" else "")
        return message

    def detail(self, session_id: str) -> dict[str, Any]:
        session = self.require_session(session_id)
        return {"session": session, "messages": self.messages(session_id)}

    def _touch(self, session_id: str, first_user_message: str = "") -> None:
        rows = self.sessions()
        for row in rows:
            if row.get("id") != session_id:
                continue
            row["updated_at"] = _now()
            if first_user_message and row.get("title") == "新对话":
                row["title"] = first_user_message.strip().replace("\n", " ")[:32]
            break
        _write_json(self.sessions_path, {"items": rows[:100]})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
