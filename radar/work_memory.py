"""Per-user Work Memory: tasks, work events, notes. Decision/meeting stubs later."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .core.schemas import (
    NOTE_SOURCE_TYPES,
    WORK_EVENT_TYPES,
    normalize_priority,
    normalize_reminder_status,
    normalize_reminder_type,
    normalize_report_type,
    normalize_status,
    public_reminder,
    public_report,
    public_task,
)
from .core.services import TaskService, WorkEventService, WorkNoteService
from .store import _read_json, _write_json


class WorkMemory:
    def __init__(
        self,
        user_root: Path,
        user_id: str,
        *,
        tasks_service: Any = None,
        events_service: Any = None,
        notes_service: Any = None,
        reminders_service: Any = None,
    ) -> None:
        self.user_id = user_id
        self.root = user_root / "work"
        # 使用传入的核心服务（来自RadarService），避免重复初始化
        self._task_service = tasks_service
        self._event_service = events_service
        self._note_service = notes_service
        self._reminders_service = reminders_service
        if not self._task_service or not self._event_service or not self._note_service or not self._reminders_service:
            # fallback：如果未传入，则创建新的服务实例（兼容旧代码）
            from .core.services import TaskService, WorkEventService, WorkNoteService, ReminderService

            self._task_service = TaskService(user_root)
            self._event_service = WorkEventService(user_root)
            self._note_service = WorkNoteService(user_root)
            self._reminders_service = ReminderService(user_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports_path = self.root / "reports.json"
        self.decisions_path = self.root / "decisions.json"
        self.reminders_path = self.root / "reminders.json"

    def tasks(self, *, include_done: bool = True) -> list[dict[str, Any]]:
        """获取当前用户所有任务（兼容旧接口）"""
        return self._task_service.list_tasks(self.user_id, include_done=include_done)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """获取指定用户的任务（兼容旧接口）"""
        from .core.schemas import public_task
        raw = self._task_service.get_task(self.user_id, task_id)
        if raw:
            return public_task(raw)
        return None

    def create_task(
        self,
        payload: dict[str, Any] | None = None,
        *,
        source_type: str = "manual",
    ) -> dict[str, Any]:
        """创建任务并自动记录WorkEvent（兼容旧接口）"""
        data = dict(payload or {})
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("title required")

        # 通过核心服务创建
        task = self._task_service.create_task(
            {
                "title": title[:160],
                "description": str(data.get("description") or "").strip()[:800],
                "project_id": str(data.get("project_id") or "").strip(),
                "project": str(data.get("project") or "").strip(),
                "goal_id": str(data.get("goal_id") or "").strip(),
                "parent_task_id": str(data.get("parent_task_id") or "").strip(),
                "priority": data.get("priority"),
                "status": data.get("status"),
                "deadline": str(data.get("deadline") or "").strip(),
                "estimated_duration": str(data.get("estimated_duration") or "").strip(),
                "source_type": str(data.get("source_type") or source_type).strip() or source_type,
                "source_ref": str(data.get("source_ref") or "").strip(),
            },
            self.user_id,
        )
        # 自动记录 WorkEvent
        self._event_service.record(
            event_type="task_created",
            user_id=self.user_id,
            title=task["title"],
            content=task.get("description") or "",
            metadata={"project_id": task.get("project_id")},
            source_type=task.get("source_type"),
            source_ref=task["id"],
            task_id=task["id"],
            project_id=task.get("project_id"),
        )
        from .core.schemas import public_task
        return public_task(task)

    def update_task(
        self,
        task_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """更新任务并自动记录WorkEvent（兼容旧接口）"""
        from .core.schemas import public_task

        patch = dict(payload or {})
        # 通过核心服务更新
        updated = self._task_service.update_task(self.user_id, task_id, patch)
        if not updated:
            raise KeyError(task_id)

        event_type = "task_completed" if updated.get("status") == "done" else "task_updated"
        # 自动记录 WorkEvent
        self._event_service.record(
            event_type=event_type,
            user_id=self.user_id,
            title=updated["title"],
            content=updated.get("status") or "",
            metadata={"project_id": updated.get("project_id")},
            source_type="task",
            source_ref=updated["id"],
            task_id=updated["id"],
            project_id=updated.get("project_id"),
        )
        return public_task(updated)

    def events(self) -> list[dict[str, Any]]:
        """获取当前用户工作事件流（兼容旧接口）"""
        return self._event_service.list_events(self.user_id)

    def add_event(
        self,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """添加工作事件（兼容旧接口）"""
        data = dict(payload or {})
        event_type = str(data.get("event_type") or "note").strip()
        if event_type not in WORK_EVENT_TYPES:
            event_type = "note"
        # 通过核心服务记录
        event = self._event_service.record(
            event_type=event_type,
            user_id=self.user_id,
            title=str(data.get("title") or "").strip()[:160],
            content=str(data.get("content") or "").strip()[:1200],
            metadata={k: v for k, v in data.items() if k not in ("title", "content", "event_type")},
            source_type=str(data.get("source_type") or "system").strip() or "system",
            source_ref=str(data.get("source_ref") or "").strip(),
            task_id=str(data.get("task_id") or ""),
            project_id=str(data.get("project_id") or ""),
        )
        from .core.schemas import public_task
        return public_task(event)

    def notes(self) -> list[dict[str, Any]]:
        """获取当前用户工作笔记（兼容旧接口）"""
        from .core.schemas import public_task
        raw = self._note_service.list_notes(self.user_id)
        return [public_task(r) for r in raw]  # type: ignore

    def add_note(
        self,
        payload: dict[str, Any] | None = None,
        *,
        source_type: str = "manual",
    ) -> dict[str, Any]:
        """创建工作笔记并自动记录WorkEvent（兼容旧接口）"""
        data = dict(payload or {})
        content = str(data.get("content") or "").strip()
        if not content:
            raise ValueError("content required")
        src = str(data.get("source_type") or source_type).strip() or source_type
        if src not in NOTE_SOURCE_TYPES:
            src = "manual"
        # 通过核心服务创建
        note = self._note_service.create_note(
            {
                "content": content,
                "tags": data.get("tags") if isinstance(data.get("tags"), list) else [],
                "project_id": str(data.get("project_id") or "").strip(),
                "source_type": src,
                "source_ref": str(data.get("source_ref") or "").strip(),
            },
            self.user_id,
        )
        # 自动记录 WorkEvent
        self._event_service.record(
            event_type="note_created",
            user_id=self.user_id,
            title="工作笔记",
            content=note["content"],
            metadata={"tags": note.get("tags")},
            source_type=note.get("source_type"),
            source_ref=note["id"],
        )
        from .core.schemas import public_task
        return public_task(note)

    def decisions(self) -> list[dict[str, Any]]:
        """Reserved Decision Memory. Empty in this phase."""
        return [row for row in self._items(self.decisions_path) if row.get("user_id") == self.user_id]

    def reminders(self, *, include_sent: bool = True) -> list[dict[str, Any]]:
        """获取当前用户提醒列表（兼容旧接口）"""
        from .core.schemas import public_reminder
        
        if self._reminders_service:
            # 通过核心服务获取
            rows = self._reminders_service.repo.list(self.user_id)
            if not include_sent:
                rows = [r for r in rows if r.get("status") == "pending"]
            rows.sort(key=lambda row: str(row.get("trigger_at") or row.get("created_at") or ""))
            return [public_reminder(r) for r in rows]
        # fallback：旧方式
        rows = [
            public_reminder(row)
            for row in self._items(self.reminders_path)
            if row.get("user_id") == self.user_id
        ]
        if not include_sent:
            rows = [row for row in rows if row.get("status") == "pending"]
        return sorted(rows, key=lambda row: str(row.get("trigger_at") or row.get("created_at") or ""))

    def add_reminder(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """创建提醒（兼容旧接口）"""
        from .core.schemas import normalize_reminder_type, normalize_reminder_status, public_reminder
        from datetime import datetime, timezone
        
        data = dict(payload or {})
        data.pop("user_id", None)
        now = _now()
        
        if self._reminders_service:
            reminder = self._reminders_service.create_reminder(
                {
                    "task_id": str(data.get("task_id") or "").strip(),
                    "project_id": str(data.get("project_id") or "").strip(),
                    "trigger_at": str(data.get("trigger_at") or now).strip() or now,
                    "reminder_type": normalize_reminder_type(str(data.get("reminder_type") or "manual")),
                    "status": normalize_reminder_status(str(data.get("status") or "pending")),
                    "generated_content": str(data.get("generated_content") or "").strip()[:1600],
                    "dedupe_key": str(data.get("dedupe_key") or "").strip()[:120],
                },
                self.user_id,
            )
            return public_reminder(reminder)
        
        row = public_reminder(
            {
                "id": str(data.get("id") or uuid4().hex[:12]),
                "user_id": self.user_id,
                "task_id": str(data.get("task_id") or "").strip(),
                "trigger_at": str(data.get("trigger_at") or now).strip() or now,
                "reminder_type": normalize_reminder_type(str(data.get("reminder_type") or "manual")),
                "status": normalize_reminder_status(str(data.get("status") or "pending")),
                "generated_content": str(data.get("generated_content") or "").strip()[:1600],
                "dedupe_key": str(data.get("dedupe_key") or "").strip()[:120],
                "created_at": now,
                "sent_at": str(data.get("sent_at") or "").strip(),
            }
        )
        rows = self.reminders()
        rows.insert(0, row)
        _write_json(self.reminders_path, {"items": rows[:400]})
        return row

    def get_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        """获取单条提醒（兼容旧接口）"""
        from .core.schemas import public_reminder

        if self._reminders_service:
            raw = self._reminders_service.repo.get(self.user_id, (reminder_id or "").strip())
            return public_reminder(raw) if raw else None
        for row in self.reminders():
            if row.get("id") == (reminder_id or "").strip():
                return row
        return None

    def update_reminder(self, reminder_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """更新提醒（兼容旧接口）"""
        from .core.schemas import normalize_reminder_type, normalize_reminder_status, public_reminder
        
        needle = (reminder_id or "").strip()
        patch = dict(payload or {})
        patch.pop("user_id", None)
        
        if self._reminders_service:
            updated = self._reminders_service.repo.update(self.user_id, reminder_id, patch)
            if not updated:
                raise KeyError(reminder_id)
            return public_reminder(updated)
        
        rows = self.reminders()
        found = None
        for index, row in enumerate(rows):
            if row.get("id") != needle:
                continue
            updated = dict(row)
            if "task_id" in patch and patch.get("task_id") is not None:
                updated["task_id"] = str(patch.get("task_id") or "").strip()
            if "trigger_at" in patch and patch.get("trigger_at") is not None:
                updated["trigger_at"] = str(patch.get("trigger_at") or "").strip()
            if "generated_content" in patch and patch.get("generated_content") is not None:
                updated["generated_content"] = str(patch.get("generated_content") or "").strip()[:1600]
            if "dedupe_key" in patch and patch.get("dedupe_key") is not None:
                updated["dedupe_key"] = str(patch.get("dedupe_key") or "").strip()[:120]
            if "sent_at" in patch and patch.get("sent_at") is not None:
                updated["sent_at"] = str(patch.get("sent_at") or "").strip()
            if "reminder_type" in patch:
                updated["reminder_type"] = normalize_reminder_type(str(patch.get("reminder_type") or row.get("reminder_type") or ""))
            if "status" in patch:
                updated["status"] = normalize_reminder_status(str(patch.get("status") or row.get("status") or ""))
            updated["user_id"] = self.user_id
            rows[index] = public_reminder(updated)
            found = rows[index]
            break
        if not found:
            raise KeyError(reminder_id)
        _write_json(self.reminders_path, {"items": rows[:400]})
        return found

    def reports(self, report_type: str | None = None) -> list[dict[str, Any]]:
        rows = [
            public_report(row)
            for row in self._items(self.reports_path)
            if row.get("user_id") == self.user_id
        ]
        kind = (report_type or "").strip().lower()
        if kind:
            rows = [row for row in rows if row.get("report_type") == normalize_report_type(kind)]
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        needle = (report_id or "").strip()
        for row in self.reports():
            if row.get("id") == needle:
                return row
        return None

    def save_report(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(payload or {})
        data.pop("user_id", None)
        now = _now()
        sources = data.get("sources") if isinstance(data.get("sources"), dict) else {}
        row = public_report(
            {
                "id": str(data.get("id") or uuid4().hex[:12]),
                "user_id": self.user_id,
                "report_type": normalize_report_type(str(data.get("report_type") or "daily")),
                "project_id": str(data.get("project_id") or "").strip(),
                "start_time": str(data.get("start_time") or "").strip(),
                "end_time": str(data.get("end_time") or "").strip(),
                "title": str(data.get("title") or "").strip()[:160],
                "content": str(data.get("content") or "").strip()[:12000],
                "sources": sources,
                "created_at": now,
                "updated_at": now,
            }
        )
        rows = self.reports()
        rows.insert(0, row)
        _write_json(self.reports_path, {"items": rows[:80]})
        self.add_event(
            {
                "event_type": "report_generated",
                "title": row["title"] or row["report_type"],
                "content": row["content"][:400],
                "project_id": row.get("project_id") or "",
                "source_type": "report",
                "source_ref": row["id"],
            }
        )
        return row

    def update_report(self, report_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        needle = (report_id or "").strip()
        patch = dict(payload or {})
        patch.pop("user_id", None)
        rows = self.reports()
        found = None
        for index, row in enumerate(rows):
            if row.get("id") != needle:
                continue
            updated = dict(row)
            if "title" in patch and patch.get("title") is not None:
                updated["title"] = str(patch.get("title") or "").strip()[:160]
            if "content" in patch and patch.get("content") is not None:
                updated["content"] = str(patch.get("content") or "").strip()[:12000]
            if "project_id" in patch and patch.get("project_id") is not None:
                updated["project_id"] = str(patch.get("project_id") or "").strip()
            updated["user_id"] = self.user_id
            updated["updated_at"] = _now()
            rows[index] = public_report(updated)
            found = rows[index]
            break
        if not found:
            raise KeyError(report_id)
        _write_json(self.reports_path, {"items": rows[:80]})
        return found

    def snapshot(self) -> dict[str, Any]:
        tasks = self.tasks()
        open_tasks = [row for row in tasks if row.get("status") not in {"done", "cancelled"}]
        reminders = self.reminders()
        pending = [row for row in reminders if row.get("status") == "pending"]
        sent = [row for row in reminders if row.get("status") == "sent"]
        morning = next((row for row in reversed(sent) if row.get("reminder_type") == "morning"), None)
        return {
            "tasks": tasks,
            "open_tasks": open_tasks,
            "today": open_tasks[:5],
            "notes": self.notes()[:12],
            "events": self.events()[:20],
            "decisions": self.decisions()[:8],
            "reminders": (pending + list(reversed(sent)))[:16],
            "brief": (morning or {}).get("generated_content") or "",
            "reports": self.reports()[:8],
        }

    def _seed_demo(self) -> None:
        from .seeds import spec_by_id

        spec = spec_by_id(self.user_id) or {}
        for draft in spec.get("tasks") or []:
            self.create_task(draft, source_type="seed")
        for draft in spec.get("work_notes") or []:
            self.add_note(draft, source_type="seed")

    def _items(self, path: Path) -> list[dict[str, Any]]:
        return list(_read_json(path, {"items": []}).get("items") or [])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
