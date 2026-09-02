"""Deterministic report copy from aggregated Work Memory. Not a free-form prompt."""

from __future__ import annotations

from typing import Any

from .schemas import heading_for

STATUS = {
    "todo": "待办",
    "in_progress": "进行中",
    "blocked": "阻塞",
    "done": "完成",
    "cancelled": "取消",
}


def render_report(ctx: dict[str, Any]) -> str:
    kind = str(ctx.get("report_type") or "daily")
    if kind == "weekly":
        return _weekly(ctx)
    if kind == "monthly":
        return _monthly(ctx)
    if kind in {"project_summary", "work_summary"}:
        return _project(ctx)
    return _daily(ctx)


def _daily(ctx: dict[str, Any]) -> str:
    parts = [heading_for("daily"), ""]
    parts += _section("一、完成事项", _task_lines(ctx.get("completed") or []), "今日暂无已完成事项，当前工作仍在推进。")
    parts += _section("二、进行中", _progress_lines(ctx.get("in_progress") or []), "当前没有进行中的任务。")
    parts += _section("三、问题与风险", _risk_lines(ctx), "暂无记录中的阻塞或风险。")
    parts += _section("四、明日计划", _plan_lines(ctx.get("planned") or []), "还没有排进明天的事项。")
    parts.append(_sources_footer(ctx))
    return "\n".join(parts).strip() + "\n"


def _weekly(ctx: dict[str, Any]) -> str:
    parts = [heading_for("weekly"), ""]
    project = ctx.get("project") or "当前项目"
    stage = ctx.get("stage") or ""
    focus = [f"{project}" + (f"（{stage}）" if stage else "")]
    focus.extend(str(row.get("title") or "") for row in (ctx.get("open_tasks") or [])[:4] if row.get("title"))
    parts += _section("一、本周重点", _numbered(focus), "本周尚未形成明确重点。")
    outcomes = [str(row.get("title") or "") for row in (ctx.get("completed") or []) if row.get("title")]
    outcomes.extend(_event_highlights(ctx.get("events") or []))
    parts += _section("二、关键成果", _numbered(outcomes), "本周还没有标记完成的事项，见进行中任务。")
    decisions = [str(row.get("content") or row.get("title") or "") for row in (ctx.get("decisions") or []) if row.get("content") or row.get("title")]
    parts += _section("三、关键决策", _numbered(decisions), "本周没有沉淀新的决策记录。")
    parts += _section("四、下周计划", _plan_lines(ctx.get("planned") or []), "下周计划待补充。")
    parts.append(_sources_footer(ctx))
    return "\n".join(parts).strip() + "\n"


def _monthly(ctx: dict[str, Any]) -> str:
    parts = [heading_for("monthly"), ""]
    parts += _section("一、本月完成", _task_lines(ctx.get("completed") or []), "本月暂无已完成事项。")
    parts += _section("二、仍在推进", _progress_lines(ctx.get("in_progress") or []), "没有进行中的任务。")
    parts += _section("三、风险", _risk_lines(ctx), "暂无风险记录。")
    parts += _section("四、下月建议", _plan_lines(ctx.get("planned") or []), "下月计划待补充。")
    parts.append(_sources_footer(ctx))
    return "\n".join(parts).strip() + "\n"


def _project(ctx: dict[str, Any]) -> str:
    project = ctx.get("project") or "当前项目"
    stage = ctx.get("stage") or "进行中"
    parts = [heading_for("project_summary"), "", f"项目：{project}", f"状态：{stage}", ""]
    parts += _section("已完成", _task_lines(ctx.get("completed") or []), "尚无已完成任务。")
    parts += _section("进行中", _progress_lines(ctx.get("in_progress") or []), "没有进行中的任务。")
    parts += _section("风险", _risk_lines(ctx), "暂无风险。")
    parts += _section("下一步建议", _plan_lines(ctx.get("planned") or []), "下一步待确认。")
    parts.append(_sources_footer(ctx))
    return "\n".join(parts).strip() + "\n"


def _progress_lines(tasks: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in tasks[:8]:
        status = STATUS.get(str(row.get("status") or ""), row.get("status") or "")
        project = row.get("project") or ""
        extra = f"（{project} · {status}）" if project else f"（{status}）"
        lines.append(f"{row.get('title') or '未命名'}{extra}")
    return lines


def _task_lines(tasks: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("title") or "未命名") for row in tasks[:8]]


def _plan_lines(tasks: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in tasks[:5]:
        due = str(row.get("deadline") or "")[:10]
        suffix = f"（截止 {due}）" if due else ""
        lines.append(f"{row.get('title') or '未命名'}{suffix}")
    return lines


def _risk_lines(ctx: dict[str, Any]) -> list[str]:
    lines = [f"{row.get('title')} 处于阻塞" for row in (ctx.get("blocked") or []) if row.get("title")]
    for row in ctx.get("risks") or []:
        text = str(row.get("generated_content") or "").strip()
        if text:
            lines.append(text.split("。")[0])
    for row in ctx.get("notes") or []:
        content = str(row.get("content") or "")
        if any(token in content for token in ("风险", "未验证", "阻塞", "缺口")):
            lines.append(content[:80])
    return lines[:6]


def _event_highlights(events: list[dict[str, Any]]) -> list[str]:
    labels = {
        "task_completed": "完成任务",
        "task_created": "新增任务",
        "knowledge_saved": "沉淀知识",
        "report_generated": "生成报告",
        "reminder_sent": "发出提醒",
    }
    out = []
    for row in events[:8]:
        label = labels.get(str(row.get("event_type") or ""), "")
        title = row.get("title") or ""
        if label and title:
            out.append(f"{label}：{title}")
    return out


def _section(title: str, lines: list[str], empty: str) -> list[str]:
    body = _numbered(lines) if lines else empty
    return [title, body, ""]


def _numbered(lines: list[str]) -> str:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    if not cleaned:
        return ""
    return "\n".join(f"{index}. {line}" for index, line in enumerate(cleaned, 1))


def _sources_footer(ctx: dict[str, Any]) -> str:
    src = ctx.get("sources") or {}
    return (
        "本次使用数据：\n"
        f"{src.get('tasks') or 0} 个 Task\n"
        f"{src.get('events') or 0} 个工作事件\n"
        f"{src.get('notes') or 0} 条工作记录\n"
        f"{src.get('goals') or 0} 个目标\n"
        f"{src.get('knowledge') or 0} 篇知识条目\n"
        f"{src.get('decisions') or 0} 个 Decision\n"
        f"{src.get('recommendations') or 0} 条相关推荐"
    )
