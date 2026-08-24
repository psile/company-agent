"""File-on-complete: preview, confirm, then card. Never auto-file."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .goals import GoalStore
from .non_goals import assert_allowed


class FilingError(ValueError):
    """Archive rules were violated."""


@dataclass(slots=True)
class ArchivePreview:
    id: str
    user_id: str
    daily_goal_id: str
    title: str
    summary: str
    source_url: str
    why_filed: str
    channel: str = "work"
    confirmed: bool = False
    revoked: bool = False
    created_at: str = ""


@dataclass
class FilingService:
    goals: GoalStore
    previews: list[ArchivePreview] = field(default_factory=list)
    cards: list[ArchivePreview] = field(default_factory=list)

    def preview(
        self,
        user_id: str,
        daily_goal_id: str,
        *,
        title: str,
        summary: str,
        source_url: str,
        why_filed: str,
    ) -> ArchivePreview:
        assert_allowed("preview_archive")
        if not any(
            event.user_id == user_id and event.daily_goal_id == daily_goal_id
            for event in self.goals.completions
        ):
            raise FilingError("complete the daily goal before filing")
        url = source_url.strip()
        if not url:
            raise FilingError("source_url is required")
        if not title.strip() or not summary.strip():
            raise FilingError("title and summary are required")
        item = ArchivePreview(
            id=f"p_{uuid4().hex[:10]}",
            user_id=user_id,
            daily_goal_id=daily_goal_id,
            title=title.strip(),
            summary=summary.strip(),
            source_url=url,
            why_filed=why_filed.strip() or "completed daily goal",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.previews.append(item)
        return item

    def confirm(self, user_id: str, preview_id: str) -> ArchivePreview:
        assert_allowed("confirm_archive")
        preview = self._preview(user_id, preview_id)
        if preview.revoked:
            raise FilingError("preview was revoked")
        if preview.confirmed:
            raise FilingError("preview already confirmed")
        preview.confirmed = True
        self.cards.append(preview)
        return preview

    def revoke(self, user_id: str, preview_id: str) -> ArchivePreview:
        assert_allowed("revoke_card")
        preview = self._preview(user_id, preview_id)
        preview.revoked = True
        preview.confirmed = False
        self.cards = [card for card in self.cards if card.id != preview.id]
        return preview

    def confirmed_count(self, user_id: str) -> int:
        return sum(1 for card in self.cards if card.user_id == user_id and not card.revoked)

    def _preview(self, user_id: str, preview_id: str) -> ArchivePreview:
        for item in self.previews:
            if item.id == preview_id and item.user_id == user_id:
                return item
        raise FilingError("preview not found")
