"""W0 冻结的「不做」。打开其中任何一项必须先改计划书第 0 节和第 2.2 节。"""

from __future__ import annotations


class NonGoalError(RuntimeError):
    """Attempted an explicitly frozen capability."""


FROZEN_NON_GOALS: frozenset[str] = frozenset(
    {
        "write_ppt",
        "virtual_computer",
        "browser_agent",
        "project_management",
        "jira_sync",
        "calendar_auto_create",
        "group_listen",
        "client_hook",
        "auto_file_without_complete",
        "send_internal_docs_to_public_llm",
        "idle_chat_push",
        "skip_level_unlock",
    }
)

ALLOWED_W0_ACTIONS: frozenset[str] = frozenset(
    {
        "set_weekly_goal",
        "set_daily_goal",
        "complete_goal",
        "preview_archive",
        "confirm_archive",
        "revoke_card",
        "morning_goal_card",
        "evening_wrap",
        "upgrade_to_lv2",
        "pet_pose",
    }
)


def assert_allowed(action: str) -> None:
    if action in FROZEN_NON_GOALS:
        raise NonGoalError(
            f"{action} is frozen in W0. Aily owns delivery-style office work; "
            "this secretary keeps rhythm and files what you finished."
        )
    if action not in ALLOWED_W0_ACTIONS:
        raise NonGoalError(f"{action} is not a W0 action")
