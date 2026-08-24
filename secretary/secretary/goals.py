"""Weekly / daily goals. This is not a second Jira: caps are the product."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from uuid import uuid4

from .non_goals import assert_allowed

MAX_WEEKLY_GOALS = 3
MAX_DAILY_GOALS = 3

GoalStatus = Literal["pending", "done", "deferred"]


class GoalError(ValueError):
    """Goal quota or state violation."""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


@dataclass(slots=True)
class WeeklyGoal:
    id: str
    user_id: str
    week_start: date
    title: str
    status: GoalStatus = "pending"


@dataclass(slots=True)
class DailyGoal:
    id: str
    user_id: str
    day: date
    title: str
    weekly_goal_id: str | None = None
    status: GoalStatus = "pending"


@dataclass(slots=True)
class CompletionEvent:
    id: str
    user_id: str
    daily_goal_id: str
    completed_on: date
    channel: str = "work"


@dataclass
class GoalStore:
    """In-memory store for W0. Persistence can wrap the same methods later."""

    weekly: list[WeeklyGoal] = field(default_factory=list)
    daily: list[DailyGoal] = field(default_factory=list)
    completions: list[CompletionEvent] = field(default_factory=list)

    def add_weekly(self, user_id: str, week_start: date, title: str) -> WeeklyGoal:
        assert_allowed("set_weekly_goal")
        title = title.strip()
        if not title:
            raise GoalError("weekly goal title is required")
        open_count = sum(
            1
            for goal in self.weekly
            if goal.user_id == user_id
            and goal.week_start == week_start
            and goal.status != "deferred"
        )
        if open_count >= MAX_WEEKLY_GOALS:
            raise GoalError(f"weekly goals cap is {MAX_WEEKLY_GOALS}")
        goal = WeeklyGoal(
            id=_new_id("w"),
            user_id=user_id,
            week_start=week_start,
            title=title,
        )
        self.weekly.append(goal)
        return goal

    def add_daily(
        self,
        user_id: str,
        day: date,
        title: str,
        weekly_goal_id: str | None = None,
    ) -> DailyGoal:
        assert_allowed("set_daily_goal")
        title = title.strip()
        if not title:
            raise GoalError("daily goal title is required")
        open_count = sum(
            1
            for goal in self.daily
            if goal.user_id == user_id and goal.day == day and goal.status != "deferred"
        )
        if open_count >= MAX_DAILY_GOALS:
            raise GoalError(f"daily goals cap is {MAX_DAILY_GOALS}")
        if weekly_goal_id and not any(item.id == weekly_goal_id for item in self.weekly):
            raise GoalError("weekly_goal_id does not exist")
        goal = DailyGoal(
            id=_new_id("d"),
            user_id=user_id,
            day=day,
            title=title,
            weekly_goal_id=weekly_goal_id,
        )
        self.daily.append(goal)
        return goal

    def complete_daily(self, user_id: str, daily_goal_id: str, on: date) -> CompletionEvent:
        assert_allowed("complete_goal")
        goal = self._daily(user_id, daily_goal_id)
        if goal.status == "done":
            raise GoalError("daily goal already completed")
        goal.status = "done"
        event = CompletionEvent(
            id=_new_id("c"),
            user_id=user_id,
            daily_goal_id=goal.id,
            completed_on=on,
            channel="work",
        )
        self.completions.append(event)
        self._maybe_complete_weekly(goal)
        return event

    def defer_daily(self, user_id: str, daily_goal_id: str) -> DailyGoal:
        goal = self._daily(user_id, daily_goal_id)
        if goal.status == "done":
            raise GoalError("cannot defer a completed goal")
        goal.status = "deferred"
        return goal

    def completed_count(self, user_id: str, *, since: date | None = None) -> int:
        return sum(
            1
            for event in self.completions
            if event.user_id == user_id and (since is None or event.completed_on >= since)
        )

    def week_all_done(self, user_id: str, week_start: date) -> bool:
        goals = [
            goal
            for goal in self.weekly
            if goal.user_id == user_id and goal.week_start == week_start
        ]
        return bool(goals) and all(goal.status == "done" for goal in goals)

    def _daily(self, user_id: str, daily_goal_id: str) -> DailyGoal:
        for goal in self.daily:
            if goal.id == daily_goal_id and goal.user_id == user_id:
                return goal
        raise GoalError("daily goal not found")

    def _maybe_complete_weekly(self, daily: DailyGoal) -> None:
        if not daily.weekly_goal_id:
            return
        siblings = [
            goal
            for goal in self.daily
            if goal.weekly_goal_id == daily.weekly_goal_id and goal.status != "deferred"
        ]
        if siblings and all(goal.status == "done" for goal in siblings):
            for weekly in self.weekly:
                if weekly.id == daily.weekly_goal_id:
                    weekly.status = "done"
                    return
