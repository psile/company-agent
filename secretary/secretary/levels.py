"""Upgrade is a capability gate, not a gacha number."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum

from .filing import FilingService
from .goals import GoalStore
from .non_goals import assert_allowed


class Level(IntEnum):
    LV1_INTERN = 1
    LV2_ASSISTANT = 2
    LV3_RESEARCH = 3
    LV4_KNOWLEDGE = 4
    LV5_CONFIDENTIAL = 5


CAPABILITIES: dict[Level, frozenset[str]] = {
    Level.LV1_INTERN: frozenset(
        {"goals", "morning_card", "evening_wrap", "pet_pose", "file_on_complete"}
    ),
    Level.LV2_ASSISTANT: frozenset(
        {"goals", "morning_card", "evening_wrap", "pet_pose", "file_on_complete", "friday_archive"}
    ),
    Level.LV3_RESEARCH: frozenset(
        {
            "goals",
            "morning_card",
            "evening_wrap",
            "pet_pose",
            "file_on_complete",
            "friday_archive",
            "watchlist",
            "interest_push",
        }
    ),
    Level.LV4_KNOWLEDGE: frozenset(
        {
            "goals",
            "morning_card",
            "evening_wrap",
            "pet_pose",
            "file_on_complete",
            "friday_archive",
            "watchlist",
            "interest_push",
            "papers",
            "url_watch",
        }
    ),
    Level.LV5_CONFIDENTIAL: frozenset(
        {
            "goals",
            "morning_card",
            "evening_wrap",
            "pet_pose",
            "file_on_complete",
            "friday_archive",
            "watchlist",
            "interest_push",
            "papers",
            "url_watch",
            "group_remind",
        }
    ),
}

LV2_MIN_CARDS = 3


class LevelError(RuntimeError):
    """Upgrade or capability was refused."""


@dataclass
class LevelService:
    goals: GoalStore
    filing: FilingService
    levels: dict[str, Level] = field(default_factory=dict)

    def level_of(self, user_id: str) -> Level:
        return self.levels.get(user_id, Level.LV1_INTERN)

    def can(self, user_id: str, capability: str) -> bool:
        return capability in CAPABILITIES[self.level_of(user_id)]

    def require(self, user_id: str, capability: str) -> None:
        if not self.can(user_id, capability):
            raise LevelError(f"{capability} is locked until a later level")

    def maybe_upgrade_lv2(self, user_id: str, week_start: date) -> Level:
        assert_allowed("upgrade_to_lv2")
        current = self.level_of(user_id)
        if current >= Level.LV2_ASSISTANT:
            return current
        if not self.goals.week_all_done(user_id, week_start):
            raise LevelError("week goals must all be done")
        if self.filing.confirmed_count(user_id) < LV2_MIN_CARDS:
            raise LevelError(f"need at least {LV2_MIN_CARDS} confirmed cards")
        self.levels[user_id] = Level.LV2_ASSISTANT
        return Level.LV2_ASSISTANT
