from datetime import date, timedelta

import pytest

from secretary.filing import FilingError, FilingService
from secretary.goals import GoalError, GoalStore
from secretary.levels import Level, LevelError, LevelService
from secretary.non_goals import FROZEN_NON_GOALS, NonGoalError, assert_allowed
from secretary.quota import PushKind, QuotaError, QuotaGuard, QuotaWindow


USER = "u_self"
WEEK = date(2026, 8, 24)


def _store_with_done_day(day: date, title: str, weekly_id: str | None = None) -> tuple[GoalStore, str]:
    store = GoalStore()
    daily = store.add_daily(USER, day, title, weekly_id)
    store.complete_daily(USER, daily.id, day)
    return store, daily.id


def test_weekly_and_daily_caps():
    store = GoalStore()
    for index in range(3):
        store.add_weekly(USER, WEEK, f"week-{index}")
        store.add_daily(USER, WEEK, f"day-{index}")
    with pytest.raises(GoalError, match="weekly"):
        store.add_weekly(USER, WEEK, "too-many")
    with pytest.raises(GoalError, match="daily"):
        store.add_daily(USER, WEEK, "too-many")


def test_complete_writes_work_channel():
    store = GoalStore()
    daily = store.add_daily(USER, WEEK, "ship feishu card")
    event = store.complete_daily(USER, daily.id, WEEK)
    assert event.channel == "work"
    assert store.completed_count(USER) == 1


def test_cannot_file_before_complete():
    store = GoalStore()
    daily = store.add_daily(USER, WEEK, "not done")
    filing = FilingService(store)
    with pytest.raises(FilingError, match="complete"):
        filing.preview(
            USER,
            daily.id,
            title="notes",
            summary="draft",
            source_url="https://example.com/doc",
            why_filed="test",
        )


def test_cannot_file_without_source_url():
    store, daily_id = _store_with_done_day(WEEK, "done")
    filing = FilingService(store)
    with pytest.raises(FilingError, match="source_url"):
        filing.preview(
            USER,
            daily_id,
            title="notes",
            summary="draft",
            source_url="  ",
            why_filed="test",
        )


def test_preview_confirm_revoke():
    store, daily_id = _store_with_done_day(WEEK, "done")
    filing = FilingService(store)
    preview = filing.preview(
        USER,
        daily_id,
        title="W0 skeleton",
        summary="Feishu test card reached self.",
        source_url="https://feishu.cn/docx/w0",
        why_filed="completed daily goal",
    )
    card = filing.confirm(USER, preview.id)
    assert card.confirmed
    assert filing.confirmed_count(USER) == 1
    filing.revoke(USER, preview.id)
    assert filing.confirmed_count(USER) == 0


def test_quota_silent_in_deep_work_and_caps_morning():
    guard = QuotaGuard()
    guard.allow(USER, WEEK, PushKind.MORNING, QuotaWindow.MORNING_COMMUTE)
    with pytest.raises(QuotaError, match="exhausted"):
        guard.allow(USER, WEEK, PushKind.MORNING, QuotaWindow.MORNING_COMMUTE)
    with pytest.raises(QuotaError, match="silent"):
        guard.allow(USER, WEEK, PushKind.BURST, QuotaWindow.DEEP_WORK, action="morning_goal_card")


def test_frozen_non_goals_block_aily_style_work():
    for action in ("write_ppt", "virtual_computer", "group_listen", "project_management"):
        assert action in FROZEN_NON_GOALS
        with pytest.raises(NonGoalError):
            assert_allowed(action)


def test_lv2_requires_week_done_and_three_cards():
    store = GoalStore()
    filing = FilingService(store)
    levels = LevelService(store, filing)
    weekly = store.add_weekly(USER, WEEK, "close W0 loop")

    for offset in range(3):
        day = WEEK + timedelta(days=offset)
        daily = store.add_daily(USER, day, f"task-{offset}", weekly.id)
        store.complete_daily(USER, daily.id, day)
        preview = filing.preview(
            USER,
            daily.id,
            title=f"card-{offset}",
            summary="filed after complete",
            source_url=f"https://feishu.cn/docx/{offset}",
            why_filed="completed",
        )
        filing.confirm(USER, preview.id)

    assert levels.level_of(USER) is Level.LV1_INTERN
    with pytest.raises(LevelError, match="watchlist"):
        levels.require(USER, "watchlist")
    with pytest.raises(LevelError, match="group_remind"):
        levels.require(USER, "group_remind")

    assert levels.maybe_upgrade_lv2(USER, WEEK) is Level.LV2_ASSISTANT
    assert levels.can(USER, "friday_archive")
    assert not levels.can(USER, "watchlist")
