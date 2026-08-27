"""Capture work tasks from conversation. Writes through RadarService only."""

from __future__ import annotations

from typing import Any

from .extractor import AUTO_CREATE, breakdown_subtasks, extract_tasks
from ...reminders.schemas import has_clock


class TaskCaptureSkill:
    name = "task_capture"

    def __init__(self, service: Any) -> None:
        self.service = service

    async def can_handle(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> bool:
        extracted = extract_tasks(message, context)
        return bool(extracted.get("should_create_task") or extracted.get("should_create_note"))

    async def extract_tasks(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = self._context(user_id, context)
        return extract_tasks(message, ctx)

    async def execute(self, user_id: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        message = str((payload or {}).get("message") or "")
        ctx = self._context(user_id, context)
        extracted = extract_tasks(message, ctx)
        if extracted.get("should_create_note") and extracted.get("note"):
            note = self.service.add_work_note(
                {"content": extracted["note"], "project_id": ctx.get("project_id") or "", "tags": ["conversation"]},
                user_id=user_id,
            )
            return {
                "ok": True,
                "created": [],
                "note": note,
                "reply": "已记成工作备忘，没有建成待办。之后写日报或跟项目时会用到。",
            }
        if not extracted.get("should_create_task") or not extracted.get("tasks"):
            return {"ok": True, "created": [], "reply": ""}
        if float(extracted.get("confidence") or 0) < AUTO_CREATE:
            titles = "、".join(row["title"] for row in extracted["tasks"][:3])
            return {
                "ok": True,
                "created": [],
                "pending": True,
                "reply": f"我理解这是一个待办（{titles}），需要帮你记下来吗？",
            }
        created = [self.service.create_task(row, user_id=user_id) for row in extracted["tasks"]]
        if has_clock(message):
            from ...reminders.schemas import infer_trigger_at

            self.service.create_reminder(
                {
                    "task_id": created[0]["id"] if created else "",
                    "trigger_at": infer_trigger_at(message).isoformat(),
                    "reminder_type": "manual",
                    "message": message,
                },
                user_id=user_id,
            )
        lines = []
        for row in created:
            due = f"，截止 {row['deadline'][:10]}" if row.get("deadline") else ""
            lines.append(f"{row['title']}{due}")
        extra = " 到点会提醒你。" if has_clock(message) else (" 截止前会提醒你。" if "提醒" in message else "")
        return {
            "ok": True,
            "created": created,
            "reply": "已记下：" + "；".join(lines) + "。" + extra,
        }

    async def breakdown(self, user_id: str, task_id: str | None, message: str = "") -> dict[str, Any]:
        parent = self._parent_task(user_id, task_id)
        if not parent:
            return {"ok": False, "created": [], "reply": "还没有可拆解的任务。先说一件要做的事，我记下后再拆。"}
        drafts = breakdown_subtasks(parent.get("title") or "", message)
        created = []
        for row in drafts:
            created.append(
                self.service.create_task(
                    {
                        **row,
                        "parent_task_id": parent["id"],
                        "project": parent.get("project") or "",
                        "project_id": parent.get("project_id") or "",
                        "source_type": "breakdown",
                        "source_ref": parent["id"],
                    },
                    user_id=user_id,
                )
            )
        listing = "\n".join(f"{i}. {row['title']}" for i, row in enumerate(created, 1))
        return {
            "ok": True,
            "parent": parent,
            "created": created,
            "reply": f"已把「{parent.get('title')}」拆成 {len(created)} 步：\n{listing}",
        }

    def _parent_task(self, user_id: str, task_id: str | None) -> dict[str, Any] | None:
        work = self.service.for_user(user_id).work
        if task_id:
            return work.get_task(task_id)
        open_tasks = [row for row in work.tasks(include_done=False) if not row.get("parent_task_id")]
        return open_tasks[0] if open_tasks else None

    def _context(self, user_id: str, extra: dict[str, Any] | None) -> dict[str, Any]:
        project = self.service.for_user(user_id).user_memory.project()
        ctx = {
            "project": str(project.get("project") or ""),
            "project_id": "",
        }
        ctx.update(extra or {})
        return ctx
