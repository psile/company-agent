"""Per-user Work Memory: tasks, work events, notes. Decision/meeting stubs later."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .store import _read_json, _write_json
from .work_models import (
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


class WorkMemory:
    def __init__(self, user_root: Path, user_id: str) -> None:
        self.user_id = user_id
        self.root = user_root / "work"
        self.tasks_path = self.root / "tasks.json"
        self.events_path = self.root / "events.json"
        self.notes_path = self.root / "notes.json"
        self.decisions_path = self.root / "decisions.json"
        self.reminders_path = self.root / "reminders.json"
        self.reports_path = self.root / "reports.json"
        self.root.mkdir(parents=True, exist_ok=True)
        fresh = not self.tasks_path.exists()
        for path in (
            self.tasks_path,
            self.events_path,
            self.notes_path,
            self.decisions_path,
            self.reminders_path,
            self.reports_path,
        ):
            if not path.exists():
                _write_json(path, {"items": []})
        if fresh:
            self._seed_demo()

    def tasks(self, *, include_done: bool = True) -> list[dict[str, Any]]:
        rows = [public_task(row) for row in self._items(self.tasks_path) if row.get("user_id") == self.user_id]
        if not include_done:
            rows = [row for row in rows if row.get("status") not in {"done", "cancelled"}]
        return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        needle = (task_id or "").strip()
        for row in self.tasks():
            if row.get("id") == needle:
                return row
        return None

    def create_task(self, payload: dict[str, Any] | None = None, *, source_type: str = "manual") -> dict[str, Any]:
        data = dict(payload or {})
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("title required")
        now = _now()
        row = public_task(
            {
                "id": str(data.get("id") or uuid4().hex[:12]),
                "user_id": self.user_id,
                "title": title[:160],
                "description": str(data.get("description") or "").strip()[:800],
                "project_id": str(data.get("project_id") or "").strip(),
                "project": str(data.get("project") or "").strip(),
                "goal_id": str(data.get("goal_id") or "").strip(),
                "parent_task_id": str(data.get("parent_task_id") or "").strip(),
                "priority": normalize_priority(str(data.get("priority") or "medium")),
                "status": normalize_status(str(data.get("status") or "todo")),
                "deadline": str(data.get("deadline") or "").strip(),
                "estimated_duration": str(data.get("estimated_duration") or "").strip(),
                "source_type": str(data.get("source_type") or source_type).strip() or source_type,
                "source_ref": str(data.get("source_ref") or "").strip(),
                "created_at": now,
                "updated_at": now,
                "completed_at": "",
            }
        )
        rows = self.tasks()
        rows.insert(0, row)
        _write_json(self.tasks_path, {"items": rows[:400]})
        self.add_event(
            {
                "event_type": "task_created",
                "title": row["title"],
                "content": row.get("description") or "",
                "project_id": row.get("project_id") or "",
                "source_type": row.get("source_type") or source_type,
                "source_ref": row["id"],
            }
        )
        return row

    def update_task(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        needle = (task_id or "").strip()
        patch = dict(payload or {})
        rows = self.tasks()
        found = None
        for index, row in enumerate(rows):
            if row.get("id") != needle:
                continue
            updated = dict(row)
            for key in (
                "title",
                "description",
                "project_id",
                "project",
                "goal_id",
                "parent_task_id",
                "deadline",
                "estimated_duration",
                "source_ref",
            ):
                if key in patch and patch.get(key) is not None:
                    updated[key] = str(patch.get(key) or "").strip()
            if "priority" in patch:
                updated["priority"] = normalize_priority(str(patch.get("priority") or row.get("priority") or ""))
            if "status" in patch:
                updated["status"] = normalize_status(str(patch.get("status") or row.get("status") or ""))
            if updated.get("status") == "done":
                updated["completed_at"] = updated.get("completed_at") or _now()
            elif "status" in patch:
                updated["completed_at"] = ""
            updated["updated_at"] = _now()
            updated["user_id"] = self.user_id
            rows[index] = public_task(updated)
            found = rows[index]
            break
        if not found:
            raise KeyError(task_id)
        _write_json(self.tasks_path, {"items": rows[:400]})
        event_type = "task_completed" if found.get("status") == "done" else "task_updated"
        self.add_event(
            {
                "event_type": event_type,
                "title": found["title"],
                "content": found.get("status") or "",
                "project_id": found.get("project_id") or "",
                "source_type": "task",
                "source_ref": found["id"],
            }
        )
        return found

    def events(self) -> list[dict[str, Any]]:
        rows = [row for row in self._items(self.events_path) if row.get("user_id") == self.user_id]
        return sorted(rows, key=lambda row: str(row.get("occurred_at") or row.get("created_at") or ""), reverse=True)

    def add_event(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(payload or {})
        event_type = str(data.get("event_type") or "note").strip()
        if event_type not in WORK_EVENT_TYPES:
            event_type = "note"
        now = _now()
        row = {
            "id": str(data.get("id") or uuid4().hex[:12]),
            "user_id": self.user_id,
            "project_id": str(data.get("project_id") or "").strip(),
            "event_type": event_type,
            "title": str(data.get("title") or "").strip()[:160],
            "content": str(data.get("content") or "").strip()[:1200],
            "source_type": str(data.get("source_type") or "system").strip() or "system",
            "source_ref": str(data.get("source_ref") or "").strip(),
            "occurred_at": str(data.get("occurred_at") or now),
            "created_at": now,
        }
        rows = self.events()
        rows.insert(0, row)
        _write_json(self.events_path, {"items": rows[:800]})
        return row

    def notes(self) -> list[dict[str, Any]]:
        rows = [row for row in self._items(self.notes_path) if row.get("user_id") == self.user_id]
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    def add_note(self, payload: dict[str, Any] | None = None, *, source_type: str = "manual") -> dict[str, Any]:
        data = dict(payload or {})
        content = str(data.get("content") or "").strip()
        if not content:
            raise ValueError("content required")
        src = str(data.get("source_type") or source_type).strip() or source_type
        if src not in NOTE_SOURCE_TYPES:
            src = "manual"
        now = _now()
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        row = {
            "id": str(data.get("id") or uuid4().hex[:12]),
            "user_id": self.user_id,
            "project_id": str(data.get("project_id") or "").strip(),
            "content": content[:1200],
            "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:12],
            "source_type": src,
            "created_at": now,
        }
        rows = self.notes()
        rows.insert(0, row)
        _write_json(self.notes_path, {"items": rows[:400]})
        self.add_event(
            {
                "event_type": "note_created",
                "title": content[:40],
                "content": content,
                "project_id": row.get("project_id") or "",
                "source_type": src,
                "source_ref": row["id"],
            }
        )
        return row

    def decisions(self) -> list[dict[str, Any]]:
        """Reserved Decision Memory. Empty in this phase."""
        return [row for row in self._items(self.decisions_path) if row.get("user_id") == self.user_id]

    def reminders(self, *, include_sent: bool = True) -> list[dict[str, Any]]:
        rows = [
            public_reminder(row)
            for row in self._items(self.reminders_path)
            if row.get("user_id") == self.user_id
        ]
        if not include_sent:
            rows = [row for row in rows if row.get("status") == "pending"]
        return sorted(rows, key=lambda row: str(row.get("trigger_at") or row.get("created_at") or ""))

    def get_reminder(self, reminder_id: str) -> dict[str, Any] | None:
        needle = (reminder_id or "").strip()
        for row in self.reminders():
            if row.get("id") == needle:
                return row
        return None

    def add_reminder(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = dict(payload or {})
        data.pop("user_id", None)
        now = _now()
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

    def update_reminder(self, reminder_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        needle = (reminder_id or "").strip()
        patch = dict(payload or {})
        patch.pop("user_id", None)
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
