"""Hard interrupt budget. Extra pushes are product failure, not diligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .non_goals import assert_allowed


class PushKind(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
    INTEREST = "interest"
    BURST = "burst"


class QuotaWindow(str, Enum):
    MORNING_COMMUTE = "morning_commute"
    DEEP_WORK = "deep_work"
    LUNCH = "lunch"
    EVENING_WRAP = "evening_wrap"
    NIGHT = "night"


class QuotaError(RuntimeError):
    """Push would exceed the daily budget or violate the time window."""


@dataclass
class QuotaGuard:
    morning_limit: int = 1
    evening_limit: int = 1
    interest_limit: int = 1
    burst_limit: int = 1
    counts: dict[tuple[str, date, PushKind], int] = field(default_factory=dict)

    def allow(
        self,
        user_id: str,
        day: date,
        kind: PushKind,
        window: QuotaWindow,
        *,
        action: str = "morning_goal_card",
    ) -> None:
        assert_allowed(action)
        if window == QuotaWindow.DEEP_WORK:
            raise QuotaError("deep work is silent")
        if window == QuotaWindow.NIGHT and kind != PushKind.INTEREST:
            raise QuotaError("night window only allows interest")
        if kind == PushKind.MORNING and window not in {
            QuotaWindow.MORNING_COMMUTE,
            QuotaWindow.LUNCH,
        }:
            raise QuotaError("morning card is for the commute window")
        if kind == PushKind.EVENING and window != QuotaWindow.EVENING_WRAP:
            raise QuotaError("evening wrap only at wrap window")

        key = (user_id, day, kind)
        used = self.counts.get(key, 0)
        limit = {
            PushKind.MORNING: self.morning_limit,
            PushKind.EVENING: self.evening_limit,
            PushKind.INTEREST: self.interest_limit,
            PushKind.BURST: self.burst_limit,
        }[kind]
        if used >= limit:
            raise QuotaError(f"{kind.value} push budget exhausted")
        self.counts[key] = used + 1
