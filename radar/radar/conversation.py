"""Unified conversation entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent import ConversationAgent
from .conversation_profile import ConversationProfile
from .conversation_store import ConversationStore


class ConversationService:
    def __init__(self, service: Any, data_root: Path) -> None:
        self.service = service
        self.data_root = data_root
        self.agent = ConversationAgent(service)

    def store(self, user_id: str) -> ConversationStore:
        uid = self.service.identity.require(user_id)
        return ConversationStore(self.data_root / "users" / uid, uid)

    def profile(self, user_id: str) -> ConversationProfile:
        uid = self.service.identity.require(user_id)
        return ConversationProfile(self.data_root / "users" / uid)

    async def chat(self, user_id: str, message: str, session_id: str | None = None) -> dict[str, Any]:
        uid = self.service.identity.require(user_id)
        clean = (message or "").strip()
        if not clean:
            raise ValueError("message required")
        store = self.store(uid)
        session = store.require_session(session_id, title=clean[:32])
        store.add_message(session["id"], "user", clean)
        result = await self.agent.respond(uid, clean, store.context(session["id"]), self.profile(uid).get())
        store.add_message(
            session["id"],
            "assistant",
            result["reply"],
            {
                "intent": result["intent"],
                "actions": result["actions"],
                "memory_updated": result["memory_updated"],
            },
        )
        return {"session_id": session["id"], **result}

    def sessions(self, user_id: str) -> list[dict[str, Any]]:
        return self.store(user_id).sessions()

    def detail(self, user_id: str, session_id: str) -> dict[str, Any]:
        return self.store(user_id).detail(session_id)


async def chat(user_id: str, message: str, session_id: str | None = None) -> dict[str, Any]:
    """Compatibility entry point; use a configured ConversationService in the app."""
    from .pipeline import RadarService

    return await RadarService().conversation.chat(user_id, message, session_id)
