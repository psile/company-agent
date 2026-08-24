"""工位萌宠秘书 — W0 内核。

品类：专属办公秘书。不拼飞书 aily，不拼 EchoBot 陪聊。
W0 只做：周/日目标 → 勾完成 → 确认归档 → 升到 Lv2。
"""

from .claims import NON_GOALS, POSITIONING
from .filing import FilingError, KnowledgeCard, file_on_complete, revoke_card
from .goals import (
    MAX_DAILY_GOALS,
    MAX_WEEKLY_GOALS,
    CompletionEvent,
    DailyGoal,
    GoalStore,
    WeeklyGoal,
)
from .levels import Level, UpgradeError, evaluate_upgrade
from .quota import PushKind, QuotaExceeded, QuotaGuard

__all__ = [
    "NON_GOALS",
    "POSITIONING",
    "FilingError",
    "KnowledgeCard",
    "file_on_complete",
    "revoke_card",
    "MAX_DAILY_GOALS",
    "MAX_WEEKLY_GOALS",
    "CompletionEvent",
    "DailyGoal",
    "GoalStore",
    "WeeklyGoal",
    "Level",
    "UpgradeError",
    "evaluate_upgrade",
    "PushKind",
    "QuotaExceeded",
    "QuotaGuard",
]
