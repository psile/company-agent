"""Office skill protocol. Skills call RadarService / WorkMemory, never raw files."""

from __future__ import annotations

from typing import Any, Protocol


class AgentSkill(Protocol):
    name: str

    async def can_handle(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> bool: ...

    async def execute(self, user_id: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]: ...
