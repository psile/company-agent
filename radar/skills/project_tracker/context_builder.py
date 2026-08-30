"""Aggregate Goal + Task + Event + Knowledge into a project snapshot."""

from __future__ import annotations

from typing import Any

from ...reminders.schemas import hours_until, now_cst, parse_dt
from .schemas import belongs_to_project, knowledge_matches


def build_snapshot(service: Any, user_id: str, project: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = service.for_user(user_id)
    meta = dict(project or scope.user_memory.project() or {})
    tasks = [row for row in scope.work.tasks() if belongs_to_project(row, meta)]
    roots = [row for row in tasks if not row.get("parent_task_id")]
    done = [row for row in roots if row.get("status") == "done"]
    open_tasks = [row for row in roots if row.get("status") not in {"done", "cancelled"}]
    in_progress = [row for row in open_tasks if row.get("status") == "in_progress"] or open_tasks
    blocked = [row for row in open_tasks if row.get("status") == "blocked"]
    children = [row for row in tasks if row.get("parent_task_id")]
    task_ids = {str(row.get("id") or "") for row in tasks}
    pid = str(meta.get("project_id") or "")
    events = [
        row
        for row in scope.work.events()
        if row.get("source_ref") in task_ids or (pid and row.get("project_id") == pid) or belongs_to_project(row, meta)
    ][:12]
    notes = [row for row in scope.work.notes() if belongs_to_project(row, meta) or (pid and row.get("project_id") == pid)]
    goals = list(scope.workspace.goals() or [])
    knowledge = [row for row in (scope.memory.cards() or []) if knowledge_matches(row, meta)][:8]
    acceptance = _acceptance(meta.get("acceptance_criteria") or [])
    milestones = _milestones(meta.get("milestones") or [])
    risks = _risks(open_tasks, blocked, notes, scope.work.reminders(), children, milestones, str(meta.get("target_date") or ""))
    next_steps = _next_steps(open_tasks, children, milestones, acceptance)
    estimated = estimate_progress(roots, children, goals, events)
    if milestones:
        milestone_score = sum(1 for row in milestones if row.get("status") == "done") / len(milestones)
        estimated = int(round(estimated * 0.75 + milestone_score * 25))
    target = str(meta.get("objective") or "").strip() or _target(open_tasks, goals)
    status_code = str(meta.get("status") or "active")
    status_labels = {"planning": "准备中", "active": "进行中", "paused": "已暂停", "done": "已完成"}
    return {
        "user_id": scope.user_id,
        "project": str(meta.get("project") or "当前项目"),
        "project_id": pid,
        "summary": str(meta.get("summary") or ""),
        "objective": str(meta.get("objective") or ""),
        "stage": str(meta.get("stage") or ""),
        "status": status_labels.get(status_code, _status(roots, open_tasks)),
        "status_code": status_code,
        "priority": str(meta.get("priority") or "medium"),
        "start_date": str(meta.get("start_date") or ""),
        "target_date": str(meta.get("target_date") or ""),
        "topics": list(meta.get("topics") or []),
        "acceptance_criteria": acceptance,
        "acceptance_progress": int(round(100 * sum(1 for row in acceptance if row.get("done")) / max(1, len(acceptance)))) if acceptance else 0,
        "milestones": milestones,
        "milestone_progress": int(round(100 * sum(1 for row in milestones if row.get("status") == "done") / max(1, len(milestones)))) if milestones else 0,
        "estimated_progress": estimated,
        "progress_basis": "tasks+goals+events",
        "target": target,
        "completed": [{"id": row.get("id"), "title": row.get("title"), "status": row.get("status")} for row in done[:8]],
        "in_progress": [{"id": row.get("id"), "title": row.get("title"), "status": row.get("status")} for row in in_progress[:8]],
        "open_tasks": open_tasks[:8],
        "goals": goals[:8],
        "events": events[:8],
        "knowledge": [{"id": row.get("id"), "title": row.get("title"), "category": row.get("category")} for row in knowledge],
        "notes": notes[:6],
        "risks": risks[:6],
        "next_steps": next_steps[:5],
        "counts": {
            "tasks": len(roots),
            "open": len(open_tasks),
            "done": len(done),
            "events": len(events),
            "goals": len(goals),
            "knowledge": len(knowledge),
        },
    }


def estimate_progress(
    roots: list[dict[str, Any]],
    children: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> int:
    task_score = _task_score(roots, children)
    goal_vals = [max(0.0, min(100.0, float(row.get("progress") or 0))) / 100 for row in goals]
    goal_score = sum(goal_vals) / len(goal_vals) if goal_vals else 0.0
    completed_events = sum(1 for row in events if row.get("event_type") == "task_completed")
    event_score = min(1.0, completed_events / 4)
    value = 0.60 * task_score + 0.30 * goal_score + 0.10 * event_score
    return int(round(max(0.0, min(1.0, value)) * 100))


def _task_score(roots: list[dict[str, Any]], children: list[dict[str, Any]]) -> float:
    active = [row for row in roots if row.get("status") != "cancelled"]
    if not active:
        return 0.0
    scores = []
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for child in children:
        by_parent.setdefault(str(child.get("parent_task_id") or ""), []).append(child)
    for row in active:
        kids = by_parent.get(str(row.get("id") or ""), [])
        if row.get("status") == "done":
            scores.append(1.0)
        elif kids:
            done = sum(1 for child in kids if child.get("status") == "done")
            scores.append(min(0.95, done / max(1, len(kids))))
        elif row.get("status") == "in_progress":
            scores.append(0.5)
        elif row.get("status") == "blocked":
            scores.append(0.2)
        else:
            scores.append(0.08)
    return sum(scores) / len(scores)


def _status(roots: list[dict[str, Any]], open_tasks: list[dict[str, Any]]) -> str:
    active = [row for row in roots if row.get("status") != "cancelled"]
    if active and all(row.get("status") == "done" for row in active):
        return "已完成"
    if any(row.get("status") == "in_progress" for row in open_tasks):
        return "进行中"
    if open_tasks:
        return "进行中"
    return "未开始"


def _target(open_tasks: list[dict[str, Any]], goals: list[dict[str, Any]]) -> str:
    dated = [row for row in open_tasks if row.get("deadline")]
    dated.sort(key=lambda row: str(row.get("deadline") or ""))
    if dated:
        due = str(dated[0].get("deadline") or "")[:10]
        return f"{dated[0].get('title')}（截止 {due}）"
    week = next((row for row in goals if row.get("kind") == "week"), None)
    today = next((row for row in goals if row.get("kind") == "today"), None)
    goal = week or today
    return str(goal.get("title") or "") if goal else ""


def _next_steps(
    open_tasks: list[dict[str, Any]],
    children: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[str]:
    pending_milestones = [row for row in milestones if row.get("status") != "done"]
    pending_milestones.sort(key=lambda row: str(row.get("due_date") or "9999"))
    lines = [f"推进里程碑：{row['title']}" for row in pending_milestones[:2]]
    incomplete = [row for row in children if row.get("status") not in {"done", "cancelled"}]
    pool = incomplete or open_tasks
    pool = sorted(pool, key=lambda row: (str(row.get("deadline") or "9"), str(row.get("title") or "")))
    lines.extend(str(row.get("title") or "") for row in pool if row.get("title"))
    if not lines:
        lines.extend(f"确认验收项：{row['text']}" for row in acceptance if not row.get("done"))
    return lines[:5]


def _risks(
    open_tasks: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    notes: list[dict[str, Any]],
    reminders: list[dict[str, Any]],
    children: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    target_date: str,
) -> list[str]:
    lines = [f"{row.get('title')} 处于阻塞" for row in blocked if row.get("title")]
    for row in open_tasks:
        hours = hours_until(parse_dt(row.get("deadline")))
        if hours is not None and 0 < hours <= 24:
            lines.append(f"{row.get('title')} 即将截止")
    kids = [row for row in children if row.get("status") not in {"done", "cancelled"}]
    if children and len(kids) / max(1, len(children)) > 0.5:
        lines.append("子任务完成率偏低，汇报前可能来不及")
    for row in notes:
        content = str(row.get("content") or "")
        if any(token in content for token in ("风险", "未验证", "OAuth", "缺口", "阻塞")):
            lines.append(content[:80])
    for row in reminders or []:
        if row.get("reminder_type") == "risk" and row.get("generated_content"):
            lines.append(str(row.get("generated_content") or "").split("。")[0][:80])
    today = now_cst().date().isoformat()
    for row in milestones:
        due = str(row.get("due_date") or "")
        if due and due < today and row.get("status") != "done":
            lines.append(f"里程碑「{row.get('title')}」已逾期")
    if target_date and target_date < today:
        lines.append("项目计划完成日期已过，但项目尚未关闭")
    seen: set[str] = set()
    out = []
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def _acceptance(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for index, row in enumerate(rows):
        if isinstance(row, dict):
            text = str(row.get("text") or row.get("title") or "").strip()
            done = bool(row.get("done"))
            row_id = str(row.get("id") or f"accept-{index + 1}")
        else:
            text, done, row_id = str(row or "").strip(), False, f"accept-{index + 1}"
        if text:
            out.append({"id": row_id, "text": text, "done": done})
    return out


def _milestones(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            row = {"title": str(row or "")}
        title = str(row.get("title") or "").strip()
        if title:
            out.append(
                {
                    "id": str(row.get("id") or f"milestone-{index + 1}"),
                    "title": title,
                    "due_date": str(row.get("due_date") or "")[:10],
                    "status": str(row.get("status") or "pending"),
                }
            )
    return out


def format_reply(snap: dict[str, Any]) -> str:
    name = snap.get("project") or "当前项目"
    stage = snap.get("stage") or snap.get("status") or "进行中"
    progress = int(snap.get("estimated_progress") or 0)
    lines = [
        name,
        f"状态：{stage}",
        f"进度约 {progress}%（估算，来自任务完成情况、目标进度和工作事件）",
    ]
    if snap.get("target"):
        lines.append(f"目标：{snap['target']}")
    lines.append("")
    lines.append("已完成：")
    completed = snap.get("completed") or []
    lines.extend([f"✓ {row.get('title')}" for row in completed] or ["（本阶段还没有标记完成的任务）"])
    lines.append("")
    lines.append("进行中：")
    lines.extend([f"• {row.get('title')}" for row in (snap.get("in_progress") or [])] or ["（暂无进行中任务）"])
    lines.append("")
    lines.append("风险：")
    lines.extend([f"! {item}" for item in (snap.get("risks") or [])] or ["（暂无记录中的风险）"])
    lines.append("")
    lines.append("下一步建议：")
    steps = snap.get("next_steps") or []
    lines.extend([f"{index}. {item}" for index, item in enumerate(steps, 1)] or ["1. 先确认当前最紧急的待办"])
    return "\n".join(lines)
