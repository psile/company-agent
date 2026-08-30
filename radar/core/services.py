"""核心Service层：TaskService/WorkEventService/WorkNoteService/ReminderService"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .repositories import JsonRepository


class TaskService:
    """任务服务：所有Task CRUD通过此层完成"""

    def __init__(self, root: Path):
        self.repo = JsonRepository(root, "tasks.json")

    def create_task(self, data: dict[str, Any], user_id: str) -> dict[str, Any]:
        """创建任务（自动写入user_id）"""
        task = {
            "user_id": user_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "project_id": data.get("project_id", ""),
            "project": data.get("project", ""),
            "goal_id": data.get("goal_id", ""),
            "parent_task_id": data.get("parent_task_id", ""),
            "priority": data.get("priority", "medium"),
            "status": data.get("status", "todo"),
            "deadline": data.get("deadline", ""),
            "estimated_duration": data.get("estimated_duration", ""),
            "source_type": data.get("source_type", "manual"),
            "source_ref": data.get("source_ref", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.repo.create(task, user_id)

    def get_task(self, user_id: str, task_id: str) -> dict[str, Any] | None:
        """获取指定用户的任务（禁止不带user_id查询）"""
        return self.repo.get(user_id, task_id)

    def list_tasks(
        self,
        user_id: str,
        include_done: bool = True,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """列出用户任务，支持按status/project_id/deadline等过滤"""
        results = self.repo.list(user_id, **filters)
        if not include_done:
            results = [r for r in results if r.get("status") not in ("done", "cancelled")]
        # 按updated_at倒序
        results.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return results

    def get_today_tasks(self, user_id: str) -> list[dict[str, Any]]:
        """今日待办 + 即将截止的任务"""
        from datetime import date, timedelta

        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return self.list_tasks(
            user_id,
            status="todo",
            deadline__gte=today,
            deadline__lt=tomorrow,
        )

    def get_overdue_tasks(self, user_id: str) -> list[dict[str, Any]]:
        """已过期未完成的任务"""
        from datetime import date

        today = date.today().isoformat()
        return self.list_tasks(
            user_id,
            status="todo",
            deadline__lt=today,
        )

    def complete_task(self, user_id: str, task_id: str) -> dict[str, Any] | None:
        """完成任务"""
        return self.repo.update(user_id, task_id, {
            "status": "done",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def update_task(self, user_id: str, task_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        """更新任务"""
        # 如果设置为 done，自动设置 completed_at
        if patch.get("status") == "done" or (isinstance(patch.get("status"), str) and patch["status"].lower() == "done"):
            patch["completed_at"] = datetime.now(timezone.utc).isoformat()
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.repo.update(user_id, task_id, patch)


class WorkEventService:
    """工作事件服务：记录所有工作相关操作"""

    def __init__(self, root: Path):
        self.repo = JsonRepository(root, "work_events.json")

    def record(
        self,
        event_type: str,
        user_id: str,
        title: str,
        content: str = "",
        metadata: dict[str, Any] | None = None,
        source_type: str = "system",
        source_ref: str = "",
        task_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """记录一条工作事件"""
        event = {
            "id": f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[-6:]}",
            "user_id": user_id,
            "event_type": event_type,
            "title": title,
            "content": content,
            "metadata": metadata or {},
            "source_type": source_type,
            "source_ref": source_ref,
            "task_id": task_id or "",
            "project_id": project_id or "",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self.repo.create(event, user_id)
        return result  # 返回完整记录

    def list_events(
        self,
        user_id: str,
        limit: int = 50,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """列出工作事件流"""
        results = self.repo.list(user_id, **filters)
        return sorted(results, key=lambda r: r.get("occurred_at") or "", reverse=True)[:limit]

    def by_event_type(self, user_id: str, event_type: str) -> list[dict[str, Any]]:
        """按事件类型筛选"""
        return self.list_events(user_id, event_type=event_type)


class WorkNoteService:
    """工作笔记服务：轻量级笔记存储"""

    def __init__(self, root: Path):
        self.repo = JsonRepository(root, "work_notes.json")

    def create_note(self, data: dict[str, Any], user_id: str) -> dict[str, Any]:
        """创建工作笔记"""
        note = {
            "user_id": user_id,
            "content": data.get("content", ""),
            "tags": data.get("tags", []),
            "project_id": data.get("project_id", ""),
            "source_type": data.get("source_type", "manual"),
            "source_ref": data.get("source_ref", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.repo.create(note, user_id)

    def list_notes(self, user_id: str, **filters: Any) -> list[dict[str, Any]]:
        """列出工作笔记"""
        return self.repo.list(user_id, **filters)


class ReminderService:
    """提醒服务：提醒CRUD"""

    def __init__(self, root: Path):
        self.repo = JsonRepository(root, "reminders.json")

    def create_reminder(self, data: dict[str, Any], user_id: str) -> dict[str, Any]:
        """创建提醒"""
        reminder = {
            "user_id": user_id,
            "task_id": data.get("task_id", ""),
            "project_id": data.get("project_id", ""),
            "trigger_at": data.get("trigger_at", ""),
            "reminder_type": data.get("reminder_type", "manual"),
            "status": data.get("status", "pending"),
            "generated_content": data.get("generated_content", ""),
            "dedupe_key": data.get("dedupe_key", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sent_at": "",
        }
        return self.repo.create(reminder, user_id)

    def get_due_reminders(self, user_id: str, now: datetime) -> list[dict[str, Any]]:
        """获取待发送的提醒"""
        from datetime import timezone as tz

        due = []
        for item in self.repo.list(user_id, status="pending"):
            trigger_at = item.get("trigger_at")
            if trigger_at and trigger_at <= now.isoformat():
                due.append(item)
        return due

    def mark_sent(self, user_id: str, reminder_id: str) -> dict[str, Any] | None:
        """标记已发送"""
        return self.repo.update(user_id, reminder_id, {
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
