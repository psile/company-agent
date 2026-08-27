"""Structured task drafts from a user message. LLM JSON first, heuristic fallback."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ... import llm
from .prompts import BREAKDOWN_SYSTEM, EXTRACT_SYSTEM


CST = timezone(timedelta(hours=8))
AUTO_CREATE = 0.75
NOT_TASK = re.compile(r"(你觉得|帮我解释|怎么样|什么是|为何|为什么这样|值得看的|有什么进展)")
STRONG_TASK = re.compile(
    r"(周五|星期[一二三四五六日天]|周[一二三四五六日]|明天|后天|这周|本周|下周).{0,24}(完成|做完|整理|准备|发|写|验证|做)"
    r"|提醒我"
    r"|(记一下|帮我记|记下).{0,30}(要|完成|做|验证|发|准备|整理)"
    r"|(待办|任务).{0,8}(：|:)"
)


def extract_tasks(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    text = (message or "").strip()
    heuristic = _heuristic_extract(text, context)
    if heuristic.get("should_create_task") or heuristic.get("should_create_note"):
        return heuristic
    if text and llm.llm_status().get("enabled"):
        parsed = llm.chat_json(EXTRACT_SYSTEM, text, timeout=20)
        if isinstance(parsed, dict) and "should_create_task" in parsed:
            return _normalize_extract(parsed, context)
    return heuristic


def breakdown_subtasks(title: str, message: str = "") -> list[dict[str, str]]:
    parsed = None
    if llm.llm_status().get("enabled"):
        parsed = llm.chat_json(BREAKDOWN_SYSTEM, f"任务：{title}\n用户：{message}", timeout=20)
    rows = (parsed or {}).get("subtasks") if isinstance(parsed, dict) else None
    if isinstance(rows, list) and rows:
        out = []
        for row in rows[:6]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("title") or "").strip()
            if name:
                out.append({"title": name[:120], "priority": str(row.get("priority") or "medium")})
        if out:
            return out
    return default_subtasks(title)


def default_subtasks(title: str) -> list[dict[str, str]]:
    label = (title or "这项工作").strip()[:40]
    return [
        {"title": f"确认「{label}」的范围与验收标准", "priority": "high"},
        {"title": "补齐 Demo / 关键材料", "priority": "high"},
        {"title": "整理产品价值与结论", "priority": "medium"},
        {"title": "准备演示或汇报脚本", "priority": "medium"},
    ]


def _heuristic_extract(text: str, context: dict[str, Any] | None) -> dict[str, Any]:
    if not text or NOT_TASK.search(text):
        return _empty()
    if not STRONG_TASK.search(text):
        if re.search(r"^(记一下|记下)[，,]", text) and not re.search(r"(要|完成|做|验证|发|截止)", text):
            return {
                "should_create_task": False,
                "should_create_note": True,
                "confidence": 0.8,
                "tasks": [],
                "note": re.sub(r"^(记一下|记下)[，,：:\s]*", "", text).strip(),
            }
        return _empty()
    title = _infer_title(text)
    deadline = infer_deadline(text)
    project = str((context or {}).get("project") or "")
    priority = "urgent" if re.search(r"(老板|紧急|马上|立刻)", text) else "high"
    return {
        "should_create_task": True,
        "should_create_note": False,
        "confidence": 0.92,
        "tasks": [
            {
                "title": title,
                "description": text[:200],
                "deadline": deadline,
                "priority": priority,
                "project": project,
                "status": "todo",
                "source_type": "conversation",
            }
        ],
        "note": "",
    }


def infer_deadline(text: str, now: datetime | None = None) -> str:
    from ...reminders.schemas import infer_trigger_at, parse_spoken_clock

    stamp = now or datetime.now(CST)
    if parse_spoken_clock(text, stamp):
        return infer_trigger_at(text, stamp).isoformat()
    day = None
    if "明天" in text:
        day = stamp.date() + timedelta(days=1)
    elif "后天" in text:
        day = stamp.date() + timedelta(days=2)
    elif re.search(r"周五|星期五", text) or re.search(r"这周|本周", text):
        day = _next_friday(stamp)
    elif "下周" in text:
        day = _next_friday(stamp + timedelta(days=7))
    if not day:
        return ""
    return datetime(day.year, day.month, day.day, 18, 0, tzinfo=CST).isoformat()


def _infer_title(text: str) -> str:
    theme = re.search(r"主题是([^，。；\n]+)", text or "")
    if theme:
        return theme.group(1).strip()[:120]
    cleaned = re.sub(r"^(记一下|记下|帮我记|提醒我一下|提醒我|请)[，,：:\s]*", "", text)
    cleaned = re.sub(r"(周五前|星期五前|明天|后天|这周|本周|下周|等下|待会)", "", cleaned)
    cleaned = re.sub(r"(提醒我一下|提醒我|老板要看)", "", cleaned)
    cleaned = re.sub(r"(顺便帮我准备一下相关材料，并发我|并发我)", "", cleaned)
    grabbed = re.search(r"把(.+?)(做完|完成|整理出来)", cleaned)
    if grabbed:
        return ("完成" + grabbed.group(1).strip())[:120]
    cleaned = cleaned.strip(" ，。,.;；")
    return (cleaned.split("。")[0] or "未命名待办")[:120]


def _next_friday(stamp: datetime):
    days = (4 - stamp.weekday()) % 7
    return (stamp + timedelta(days=days)).date()


def _normalize_extract(parsed: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    tasks = []
    for row in parsed.get("tasks") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        tasks.append(
            {
                "title": title[:160],
                "description": str(row.get("description") or "").strip()[:800],
                "deadline": str(row.get("deadline") or "").strip(),
                "priority": str(row.get("priority") or "medium"),
                "project": str(row.get("project") or (context or {}).get("project") or ""),
                "status": "todo",
                "source_type": "conversation",
            }
        )
    confidence = float(parsed.get("confidence") or 0)
    should = bool(parsed.get("should_create_task")) and bool(tasks)
    return {
        "should_create_task": should,
        "should_create_note": bool(parsed.get("should_create_note")) and not should,
        "confidence": confidence,
        "tasks": tasks if should else [],
        "note": str(parsed.get("note") or "").strip(),
    }


def _empty() -> dict[str, Any]:
    return {
        "should_create_task": False,
        "should_create_note": False,
        "confidence": 0.2,
        "tasks": [],
        "note": "",
    }
