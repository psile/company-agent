"""Create or fire reminders from conversation. Writes through RadarService only."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from ...reminders.schemas import infer_trigger_at, now_cst
from ..task_capture.extractor import extract_tasks


class ReminderSkill:
    name = "reminder"

    def __init__(self, service: Any) -> None:
        self.service = service

    async def can_handle(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> bool:
        text = message or ""
        return bool(re.search(r"提醒我|(今日|今天).{0,8}(工作重点|提醒)", text))

    async def execute(self, user_id: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        message = str((payload or {}).get("message") or "")
        if re.search(r"(生成|给我|看看)?(今日|今天).{0,8}(工作重点|提醒)|早上好", message):
            fired = self.service.evaluate_reminders(user_id, force_morning=True)
            morning = next((row for row in fired if row.get("reminder_type") == "morning"), None)
            content = (morning or {}).get("generated_content") or "今天还没有生成工作重点。"
            return {"ok": True, "created": [], "fired": fired, "reply": content}

        extracted = extract_tasks(message, self._context(user_id, context))
        created_tasks = []
        if extracted.get("should_create_task") and extracted.get("tasks"):
            created_tasks = [self.service.create_task(row, user_id=user_id) for row in extracted["tasks"]]
        task = created_tasks[0] if created_tasks else None
        trigger = infer_trigger_at(message)
        reminder = self.service.create_reminder(
            {
                "task_id": (task or {}).get("id") or "",
                "trigger_at": trigger.isoformat(),
                "reminder_type": "manual",
                "message": message,
            },
            user_id=user_id,
        )
        title = (task or {}).get("title") or "这件事"
        when = str(reminder.get("trigger_at") or "")[:16].replace("T", " ")
        extra = f"已记下待办「{title}」。" if task else ""
        materials = " 到点时把相关材料一并附上。" if re.search(r"材料|准备|发我", message) else ""
        if trigger <= now_cst() + timedelta(minutes=2):
            self.service.evaluate_reminders(user_id)
        return {
            "ok": True,
            "created": created_tasks,
            "reminder": reminder,
            "reply": f"{extra}会在 {when} 提醒你（飞书和站内通知都会发）。{materials}",
        }

    def _context(self, user_id: str, extra: dict[str, Any] | None) -> dict[str, Any]:
        project = self.service.for_user(user_id).user_memory.project()
        ctx = {"project": str(project.get("project") or ""), "project_id": ""}
        ctx.update(extra or {})
        return ctx
