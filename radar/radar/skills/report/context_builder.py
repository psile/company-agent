"""Assemble report facts from Work Memory, goals, knowledge, and feeds."""

from __future__ import annotations

from typing import Any

from .schemas import in_window, now_cst, parse_dt, report_window


def build_report_context(
    service: Any,
    user_id: str,
    report_type: str,
    *,
    now=None,
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    scope = service.for_user(user_id)
    stamp = now_cst(now)
    start, end = report_window(report_type, stamp)
    if start_time:
        start = parse_dt(start_time) or start
    if end_time:
        end = parse_dt(end_time) or end
    needle = (project_id or "").strip()
    tasks = [
        row
        for row in scope.work.tasks()
        if not needle or row.get("project_id") == needle or row.get("project") == needle
    ]
    roots = [row for row in tasks if not row.get("parent_task_id")]
    open_tasks = [row for row in roots if row.get("status") not in {"done", "cancelled"}]
    completed = [
        row
        for row in tasks
        if row.get("status") == "done" and in_window(row.get("completed_at") or row.get("updated_at"), start, end)
    ]
    created = [row for row in tasks if in_window(row.get("created_at"), start, end)]
    events = [
        row
        for row in scope.work.events()
        if (not needle or row.get("project_id") == needle)
        and in_window(row.get("occurred_at") or row.get("created_at"), start, end)
    ]
    notes = [
        row
        for row in scope.work.notes()
        if (not needle or row.get("project_id") == needle) and in_window(row.get("created_at"), start, end)
    ]
    if not notes:
        notes = [
            row
            for row in scope.work.notes()
            if not needle or row.get("project_id") == needle
        ][:6]
    decisions = [row for row in notes if "decision" in (row.get("tags") or [])]
    goals = list(scope.workspace.goals() or [])
    project = scope.user_memory.project()
    cards = list(scope.memory.cards() or [])[:8]
    recs = list((scope.memory.feeds() or {}).get("for_you") or [])[:5]
    blocked = [row for row in open_tasks if row.get("status") == "blocked"]
    risks = [
        row
        for row in scope.work.reminders()
        if row.get("reminder_type") == "risk" and row.get("status") == "sent"
    ]
    planned = sorted(open_tasks, key=_plan_key)
    hierarchy = scope.hierarchy.snapshot()
    long_term = hierarchy.get("long_term") or {}
    return {
        "user_id": scope.user_id,
        "report_type": report_type,
        "now": stamp,
        "start": start,
        "end": end,
        "project": str(project.get("project") or ""),
        "stage": str(project.get("stage") or ""),
        "open_tasks": open_tasks,
        "completed": completed,
        "created": created,
        "in_progress": [row for row in open_tasks if row.get("status") == "in_progress"] or open_tasks,
        "events": events,
        "notes": notes,
        "decisions": decisions,
        "goals": goals,
        "knowledge": cards,
        "recommendations": recs,
        "blocked": blocked,
        "risks": risks,
        "planned": planned,
        "memory_summary": str(long_term.get("profile_summary") or ""),
        "sources": {
            "tasks": len(tasks),
            "events": len(events),
            "notes": len(notes),
            "goals": len(goals),
            "knowledge": len(cards),
            "decisions": len(decisions),
            "recommendations": len(recs),
        },
    }


def _plan_key(task: dict[str, Any]) -> tuple:
    deadline = parse_dt(task.get("deadline"))
    due = deadline.timestamp() if deadline else 9e18
    rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(str(task.get("priority") or ""), 2)
    return (due, rank, str(task.get("title") or ""))
