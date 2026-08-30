"""Timeline-first work summary aggregation. Read-only over core work data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..report.schemas import in_window, now_cst, parse_dt

DAY_MS = timedelta(days=1)


def build_work_summary(
    service: Any,
    user_id: str,
    *,
    range_days: int = 7,
    now: datetime | None = None,
    kind: str = "daily",
) -> dict[str, Any]:
    """Return timeline (days desc) + overview stats for the requested range."""
    uid = service.identity.require(user_id)
    stamp = now_cst(now)
    scope = service.for_user(uid)
    start = stamp.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=range_days - 1)
    end = start + timedelta(days=range_days)
    data = _collect(scope, uid, start, end)
    days = [_daily_card(date_key, data, stamp) for date_key in sorted(data["by_day"], reverse=True)]
    overview = _overview(data, start, end)
    project_breakdown = _project_breakdown(data["events"])
    return {
        "period": {"type": "range", "start": start.date().isoformat(), "end": (end - DAY_MS).date().isoformat()},
        "stats": overview,
        "summary": _period_summary(kind, overview, data, stamp),
        "days": days,
        "projects": project_breakdown,
        "generated_at": stamp.isoformat(),
    }


def build_period_overview(
    service: Any,
    user_id: str,
    kind: str,
    *,
    now: datetime | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Overview + timeline for today/week/month/project tabs."""
    uid = service.identity.require(user_id)
    stamp = now_cst(now)
    scope = service.for_user(uid)
    kind = (kind or "week").strip().lower()
    if kind == "today":
        start = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + DAY_MS
    elif kind == "week":
        monday = stamp.date() - timedelta(days=stamp.weekday())
        start = datetime(monday.year, monday.month, monday.day, tzinfo=stamp.tzinfo)
        end = start + timedelta(days=7)
    elif kind == "month":
        start = stamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:  # project: last 30 days of the project's events
        start = stamp.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
        end = start + timedelta(days=30)
    needle = (project_id or "").strip() if kind == "project" else ""
    data = _collect(scope, uid, start, end, project_id=needle)
    stats = _overview(data, start, end)
    result: dict[str, Any] = {
        "period": {"type": kind, "start": start.date().isoformat(), "end": (end - DAY_MS).date().isoformat()},
        "stats": stats,
        "summary": _period_summary(kind, stats, data, stamp),
        "generated_at": stamp.isoformat(),
    }
    if kind in {"today", "week"}:
        result["days"] = [_daily_card(key, data, stamp) for key in sorted(data["by_day"], reverse=True)]
    if kind == "month":
        result["weeks"] = _month_weeks(data, start, end, stamp)
    if kind == "project":
        result["events"] = _project_timeline(data["events"])
    return result


def _collect(scope: Any, uid: str, start: datetime, end: datetime, *, project_id: str = "") -> dict[str, Any]:
    needle = (project_id or "").strip()
    tasks_all = scope.work.tasks()
    tasks = [row for row in tasks_all if not needle or row.get("project_id") == needle or row.get("project") == needle]
    completed = [
        row
        for row in tasks
        if row.get("status") == "done" and in_window(row.get("completed_at") or row.get("updated_at"), start, end)
    ]
    open_tasks = [row for row in tasks if row.get("status") not in {"done", "cancelled"}]
    in_progress = [row for row in open_tasks if row.get("status") == "in_progress"]
    blocked = [row for row in open_tasks if row.get("status") == "blocked"]
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
    decisions = [row for row in notes if "decision" in (row.get("tags") or [])]
    cards = [
        row
        for row in (scope.memory.cards() or [])
        if in_window(row.get("saved_at"), start, end)
    ]
    by_day: dict[str, dict[str, list]] = {}
    for row in completed:
        _bucket(by_day, row.get("completed_at") or row.get("updated_at"), "completed", row)
    for row in in_progress:
        _bucket(by_day, row.get("updated_at") or row.get("created_at"), "in_progress", row)
    for row in events:
        _bucket(by_day, row.get("occurred_at") or row.get("created_at"), "events", row)
    for row in notes:
        _bucket(by_day, row.get("created_at"), "notes", row)
    for row in decisions:
        _bucket(by_day, row.get("created_at"), "decisions", row)
    for row in cards:
        _bucket(by_day, row.get("saved_at"), "knowledge", row)
    return {
        "tasks": tasks,
        "completed": completed,
        "open_tasks": open_tasks,
        "in_progress": in_progress,
        "blocked": blocked,
        "events": events,
        "notes": notes,
        "decisions": decisions,
        "knowledge": cards,
        "by_day": by_day,
    }


def _bucket(by_day: dict[str, dict[str, list]], value: Any, key: str, row: dict[str, Any]) -> None:
    stamp = parse_dt(value)
    if stamp is None:
        return
    date_key = stamp.date().isoformat()
    slot = by_day.setdefault(date_key, {"completed": [], "in_progress": [], "events": [], "notes": [], "decisions": [], "knowledge": []})
    slot[key].append(row)


def _daily_card(date_key: str, data: dict[str, Any], stamp: datetime) -> dict[str, Any]:
    slot = data["by_day"].get(date_key) or {}
    completed = slot.get("completed") or []
    in_progress = slot.get("in_progress") or []
    events = slot.get("events") or []
    decisions = slot.get("decisions") or []
    knowledge = slot.get("knowledge") or []
    day = datetime.fromisoformat(date_key).date()
    today = stamp.date()
    if day == today:
        label = "今天"
    elif day == today - timedelta(days=1):
        label = "昨天"
    else:
        weekday = "周" + "一二三四五六日"[day.weekday()]
        label = weekday
    risky = [row for row in slot.get("notes") or [] if any(token in str(row.get("content") or "") for token in ("风险", "阻塞", "缺口", "未验证"))]
    top_completed = [str(row.get("title") or "") for row in completed[:3] if row.get("title")]
    top_in_progress = [str(row.get("title") or "") for row in in_progress[:2] if row.get("title")]
    return {
        "date": date_key,
        "day_label": label,
        "summary": _daily_summary(completed, in_progress, events, day == today),
        "stats": {
            "completed": len(completed),
            "in_progress": len(in_progress),
            "knowledge": len(knowledge),
            "decisions": len(decisions),
            "events": len(events),
        },
        "top_completed": top_completed,
        "top_in_progress": top_in_progress,
        "decisions": [str(row.get("content") or "")[:80] for row in decisions[:1]],
        "risks": [str(row.get("content") or "")[:80] for row in risky[:1]],
        "more_completed": max(0, len(completed) - 3),
        "more_in_progress": max(0, len(in_progress) - 2),
    }


def _daily_summary(completed: list, in_progress: list, events: list, is_today: bool) -> str:
    parts: list[str] = []
    if completed:
        titles = "、".join(str(row.get("title") or "") for row in completed[:2] if row.get("title"))
        parts.append(f"完成{len(completed)}项：{titles}" if len(completed) > 2 else f"完成{titles}")
    if in_progress:
        titles = "、".join(str(row.get("title") or "") for row in in_progress[:2] if row.get("title"))
        parts.append(f"推进{titles}")
    if not parts and events:
        labels = {"task_created": "新增任务", "note_created": "记录笔记", "report_generated": "生成报告", "knowledge_saved": "沉淀知识"}
        texts = [f"{labels.get(str(row.get('event_type') or ''), '更新')}「{row.get('title')}」" for row in events[:2] if row.get("title")]
        if texts:
            parts.append("、".join(texts))
    if not parts:
        return "" if is_today else "当天没有工作记录"
    text = "，".join(parts)
    if len(text) > 120:
        text = text[:117] + "…"
    return text


def _overview(data: dict[str, Any], start: datetime, end: datetime) -> dict[str, int]:
    return {
        "completed": len(data["completed"]),
        "in_progress": len(data["in_progress"]),
        "blocked": len(data["blocked"]),
        "knowledge": len(data["knowledge"]),
        "decisions": len(data["decisions"]),
        "events": len(data["events"]),
    }


def _period_summary(kind: str, stats: dict[str, int], data: dict[str, Any], stamp: datetime) -> str:
    """Deterministic 80-150 char narrative; LLM can replace later without touching counts."""
    project_counts = _project_breakdown(data["events"]) or _project_breakdown(data["tasks"])
    focus = "、".join(f"{row['project']}" for row in project_counts[:2] if row.get("project"))
    span = f"近{stamp.strftime('%-m')}月" if kind == "month" else ""
    head = focus or "工作"
    pieces = [f"{span}主要围绕{head}展开"] if focus else ["本段时间暂无明确项目主题"]
    if stats["completed"]:
        top = [str(row.get("title") or "") for row in data["completed"][:2] if row.get("title")]
        pieces.append(f"完成{stats['completed']}项工作" + (f"（{'、'.join(top)}）" if top else ""))
    if stats["in_progress"]:
        top = [str(row.get("title") or "") for row in data["in_progress"][:2] if row.get("title")]
        pieces.append(f"正在推进{stats['in_progress']}项" + (f"（{'、'.join(top)}）" if top else ""))
    if stats["decisions"]:
        pieces.append(f"沉淀{stats['decisions']}条关键决策")
    if stats["knowledge"]:
        pieces.append(f"新增{stats['knowledge']}篇知识沉淀")
    if stats["blocked"]:
        pieces.append(f"有{stats['blocked']}项被阻塞需要关注")
    text = "，".join(pieces) + "。"
    return text[:200]


def _project_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get("project") or "").strip()
        if not name:
            name = str(row.get("project_id") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [{"project": name, "events": count} for name, count in ranked[:5]]


def _project_timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(events, key=lambda row: str(row.get("occurred_at") or ""), reverse=True)
    return [
        {
            "date": str(row.get("occurred_at") or "")[:10],
            "event_type": row.get("event_type") or "",
            "title": row.get("title") or "",
            "content": str(row.get("content") or "")[:100],
        }
        for row in rows[:20]
    ]


def _month_weeks(data: dict[str, Any], start: datetime, end: datetime, stamp: datetime) -> list[dict[str, Any]]:
    weeks: list[dict[str, Any]] = []
    cursor = start
    index = 1
    while cursor < end:
        week_end = min(cursor + timedelta(days=7), end)
        slot_rows = {
            "completed": [row for row in data["completed"] if _in(row, cursor, week_end)],
            "in_progress": [row for row in data["in_progress"] if _in(row, cursor, week_end)],
            "events": [row for row in data["events"] if _in(row, cursor, week_end)],
        }
        weeks.append(
            {
                "label": f"第{index}周",
                "start": cursor.date().isoformat(),
                "end": (week_end - DAY_MS).date().isoformat(),
                "stats": {
                    "completed": len(slot_rows["completed"]),
                    "in_progress": len(slot_rows["in_progress"]),
                    "events": len(slot_rows["events"]),
                },
                "top_completed": [str(row.get("title") or "") for row in slot_rows["completed"][:2] if row.get("title")],
            }
        )
        cursor = week_end
        index += 1
    return weeks


def _in(row: dict[str, Any], start: datetime, end: datetime) -> bool:
    stamp = parse_dt(row.get("completed_at") or row.get("occurred_at") or row.get("updated_at") or row.get("created_at"))
    return stamp is not None and start <= stamp < end
