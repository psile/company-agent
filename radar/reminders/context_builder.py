"""Build reminder copy from Task + Project + Progress + Work Events."""

from __future__ import annotations

from typing import Any

from .schemas import hours_until, parse_dt

STATUS_LABEL = {
    "todo": "待办",
    "in_progress": "进行中",
    "blocked": "阻塞",
    "done": "完成",
    "cancelled": "取消",
}


def build_task_context(scope: Any, task: dict[str, Any], now=None) -> dict[str, Any]:
    work = scope.work
    task_id = str(task.get("id") or "")
    children = [row for row in work.tasks() if row.get("parent_task_id") == task_id]
    done = [row for row in children if row.get("status") == "done"]
    incomplete = [row for row in children if row.get("status") not in {"done", "cancelled"}]
    events = [row for row in work.events() if row.get("source_ref") == task_id][:6]
    project = scope.user_memory.project()
    deadline = parse_dt(task.get("deadline"))
    remaining = hours_until(deadline, now)
    return {
        "task": task,
        "project": str(project.get("project") or task.get("project") or ""),
        "stage": str(project.get("stage") or ""),
        "status": str(task.get("status") or "todo"),
        "children": children,
        "children_done": len(done),
        "children_total": len(children),
        "incomplete": incomplete,
        "events": events,
        "deadline": deadline,
        "hours_left": remaining,
    }


def build_morning_context(scope: Any, now=None) -> dict[str, Any]:
    project = scope.user_memory.project()
    open_tasks = [row for row in scope.work.tasks(include_done=False) if not row.get("parent_task_id")]
    ranked = sorted(open_tasks, key=_focus_key)
    related = 0
    try:
        related = len((scope.memory.feeds().get("for_you") or [])[:4])
    except Exception:
        related = 0
    return {
        "project": str(project.get("project") or ""),
        "stage": str(project.get("stage") or ""),
        "focus_tasks": ranked[:3],
        "open_count": len(open_tasks),
        "related_count": related,
        "contexts": [build_task_context(scope, row, now) for row in ranked[:3]],
    }


def compose_deadline(ctx: dict[str, Any]) -> str:
    task = ctx.get("task") or {}
    title = str(task.get("title") or "这项工作")
    when = _when_label(ctx.get("hours_left"))
    parts = [f"{when}需要完成「{title}」。"]
    parts.append(_progress_clause(ctx))
    stage = ctx.get("stage") or ""
    if stage:
        parts.append(f"项目当前在「{stage}」。")
    suggestion = _next_action(ctx)
    if suggestion:
        parts.append(suggestion)
    return "".join(parts)


def compose_progress(ctx: dict[str, Any]) -> str:
    task = ctx.get("task") or {}
    title = str(task.get("title") or "这项工作")
    hours = ctx.get("hours_left")
    remain = "已临近" if hours is None else f"还剩约 {max(0, int(hours))} 小时"
    status = STATUS_LABEL.get(str(ctx.get("status") or ""), "待办")
    parts = [f"「{title}」截止{remain}，目前仍是{status}。"]
    parts.append(_progress_clause(ctx))
    stage = ctx.get("stage") or ""
    if stage:
        parts.append(f"项目处在「{stage}」。")
    parts.append("建议今天先推进，而不是等到截止当天。")
    return "".join(parts)


def compose_risk(ctx: dict[str, Any]) -> str:
    task = ctx.get("task") or {}
    title = str(task.get("title") or "这项工作")
    done = int(ctx.get("children_done") or 0)
    total = int(ctx.get("children_total") or 0)
    names = "、".join(str(row.get("title") or "") for row in (ctx.get("incomplete") or [])[:3] if row.get("title"))
    parts = [f"「{title}」还剩大约 1 天，子任务完成 {done}/{total}，不足一半。"]
    if names:
        parts.append(f"还没完成：{names}。")
    parts.append("建议今天优先补这些缺口，避免汇报前赶工。")
    return "".join(parts)


def compose_manual(ctx: dict[str, Any], message: str = "") -> str:
    task = ctx.get("task") or {}
    title = str(task.get("title") or message or "约定事项")
    parts = [f"到点了：该处理「{title}」。"]
    parts.append(_progress_clause(ctx))
    stage = ctx.get("stage") or ""
    if stage:
        parts.append(f"结合当前项目「{stage}」，先确认材料是否齐。")
    return "".join(parts)


def compose_morning(ctx: dict[str, Any]) -> str:
    tasks = ctx.get("focus_tasks") or []
    if not tasks:
        project = ctx.get("project") or "当前项目"
        return f"早上好。今天还没有待办，可以围绕「{project}」看一眼相关资料，或告诉我要推进的事项。"
    lines = [f"早上好，今天建议优先完成 {len(tasks)} 件事："]
    details = ctx.get("contexts") or []
    for index, task in enumerate(tasks, 1):
        nested = details[index - 1] if index - 1 < len(details) else {}
        due = _when_label(nested.get("hours_left")) if nested else "近期"
        progress = _progress_short(nested) if nested else STATUS_LABEL.get(str(task.get("status") or ""), "待办")
        lines.append(f"{index}. {task.get('title')}\n   截止：{due}\n   当前进度：{progress}")
    related = int(ctx.get("related_count") or 0)
    if related:
        lines.append(f"另外，我发现 {related} 篇与你当前项目高度相关的新资料。")
    return "\n".join(lines)


def _progress_clause(ctx: dict[str, Any]) -> str:
    total = int(ctx.get("children_total") or 0)
    done = int(ctx.get("children_done") or 0)
    if total:
        names = "、".join(str(row.get("title") or "") for row in (ctx.get("incomplete") or [])[:3] if row.get("title"))
        extra = f"还没完成：{names}。" if names else ""
        return f"子任务完成 {done}/{total}。{extra}"
    status = STATUS_LABEL.get(str(ctx.get("status") or ""), "待办")
    if status == "待办":
        return "目前还停留在待办，建议今天开工。"
    return f"目前状态是{status}。"


def _progress_short(ctx: dict[str, Any]) -> str:
    total = int(ctx.get("children_total") or 0)
    done = int(ctx.get("children_done") or 0)
    if total:
        return f"{int(round(100 * done / total))}%"
    return STATUS_LABEL.get(str(ctx.get("status") or ""), "待办")


def _next_action(ctx: dict[str, Any]) -> str:
    incomplete = ctx.get("incomplete") or []
    if incomplete:
        names = "、".join(str(row.get("title") or "") for row in incomplete[:2] if row.get("title"))
        return f"建议今天优先补{names}。" if names else ""
    if str(ctx.get("status") or "") == "todo":
        return "建议今天先把范围和材料清单定下来。"
    return ""


def _when_label(hours: float | None) -> str:
    if hours is None:
        return "近期"
    if hours <= 0:
        return "已经到期，仍需处理"
    if hours <= 5:
        return "几小时内"
    if hours <= 36:
        return "明天"
    if hours <= 72:
        return "这两天"
    return "近期"


def _focus_key(task: dict[str, Any]) -> tuple:
    deadline = parse_dt(task.get("deadline"))
    due = deadline.timestamp() if deadline else 9e18
    rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(str(task.get("priority") or ""), 2)
    return (due, rank, str(task.get("title") or ""))
