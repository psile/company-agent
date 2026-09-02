"""核心领域 Schemas：合并 work_models.py 的 normalize 函数和常量定义"""
from __future__ import annotations

# Task 状态和优先级
TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")

# Reminder 类型和状态
REMINDER_TYPES = ("deadline", "progress", "morning", "risk", "manual")
REMINDER_STATUSES = ("pending", "sent", "cancelled", "skipped")

# Report 类型
REPORT_TYPES = ("daily", "weekly", "monthly", "project_summary", "work_summary")

# Work Event 类型
WORK_EVENT_TYPES = (
    "task_created",
    "task_completed",
    "task_updated",
    "goal_updated",
    "project_updated",
    "knowledge_saved",
    "decision_made",
    "report_generated",
    "meeting",
    "note",
    "note_created",
    "reminder_sent",
)

# Note 来源类型
NOTE_SOURCE_TYPES = ("conversation", "manual", "meeting", "system", "seed")


def normalize_status(value: str, default: str = "todo") -> str:
    text = (value or "").strip().lower()
    return text if text in TASK_STATUSES else default


def normalize_priority(value: str, default: str = "medium") -> str:
    text = (value or "").strip().lower()
    return text if text in TASK_PRIORITIES else default


def normalize_reminder_type(value: str, default: str = "manual") -> str:
    text = (value or "").strip().lower()
    return text if text in REMINDER_TYPES else default


def normalize_reminder_status(value: str, default: str = "pending") -> str:
    text = (value or "").strip().lower()
    return text if text in REMINDER_STATUSES else default


def normalize_report_type(value: str, default: str = "daily") -> str:
    text = (value or "").strip().lower().replace("-", "_")
    aliases = {"日报": "daily", "周报": "weekly", "月报": "monthly", "月度": "monthly"}
    text = aliases.get(text, text)
    return text if text in REPORT_TYPES else default


def public_task(row: dict[str, Any]) -> dict[str, Any]:
    from typing import Any
    return {
        "id": row.get("id") or "",
        "user_id": row.get("user_id") or "",
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "project_id": row.get("project_id") or "",
        "project": row.get("project") or "",
        "goal_id": row.get("goal_id") or "",
        "parent_task_id": row.get("parent_task_id") or "",
        "priority": normalize_priority(str(row.get("priority") or "")),
        "status": normalize_status(str(row.get("status") or "")),
        "scheduled_at": row.get("scheduled_at") or "",
        "deadline": row.get("deadline") or "",
        "estimated_duration": row.get("estimated_duration") or "",
        "source_type": row.get("source_type") or "manual",
        "source_ref": row.get("source_ref") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
        "completed_at": row.get("completed_at") or "",
    }


def public_reminder(row: dict[str, Any]) -> dict[str, Any]:
    from typing import Any
    return {
        "id": row.get("id") or "",
        "user_id": row.get("user_id") or "",
        "task_id": row.get("task_id") or "",
        "trigger_at": row.get("trigger_at") or "",
        "reminder_type": normalize_reminder_type(str(row.get("reminder_type") or "")),
        "status": normalize_reminder_status(str(row.get("status") or "")),
        "generated_content": row.get("generated_content") or "",
        "dedupe_key": row.get("dedupe_key") or "",
        "created_at": row.get("created_at") or "",
        "sent_at": row.get("sent_at") or "",
    }


def public_report(row: dict[str, Any]) -> dict[str, Any]:
    from typing import Any
    sources = row.get("sources") if isinstance(row.get("sources"), dict) else {}
    return {
        "id": row.get("id") or "",
        "user_id": row.get("user_id") or "",
        "report_type": normalize_report_type(str(row.get("report_type") or "")),
        "project_id": row.get("project_id") or "",
        "start_time": row.get("start_time") or "",
        "end_time": row.get("end_time") or "",
        "title": row.get("title") or "",
        "content": row.get("content") or "",
        "sources": {
            "tasks": int(sources.get("tasks") or 0),
            "events": int(sources.get("events") or 0),
            "notes": int(sources.get("notes") or 0),
            "goals": int(sources.get("goals") or 0),
            "knowledge": int(sources.get("knowledge") or 0),
            "decisions": int(sources.get("decisions") or 0),
            "recommendations": int(sources.get("recommendations") or 0),
        },
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }
