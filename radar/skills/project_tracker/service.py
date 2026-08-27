"""Project tracker skill. Reads Work Memory / Goals / Knowledge through RadarService."""

from __future__ import annotations

import re
from typing import Any

from .context_builder import build_snapshot, format_reply
from .schemas import belongs_to_project, norm


class ProjectTrackerSkill:
    name = "project_tracker"

    def __init__(self, service: Any) -> None:
        self.service = service

    async def can_handle(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> bool:
        text = message or ""
        return bool(re.search(r"项目.{0,16}(到哪了|进展|进度|怎么样)|这个项目现在进展怎么样", text))

    async def execute(self, user_id: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        message = str((payload or {}).get("message") or "")
        pack = list_trackers(self.service, user_id)
        snap = pack.get("current") or {}
        for item in pack.get("items") or []:
            name = str(item.get("project") or "")
            if name and name in message:
                snap = item
                break
        return {"ok": True, "tracker": snap, "items": pack.get("items") or [], "reply": format_reply(snap)}


def project_snapshot(service: Any, user_id: str, project: dict[str, Any] | None = None) -> dict[str, Any]:
    uid = service.identity.require(user_id)
    return build_snapshot(service, uid, project)


def list_trackers(service: Any, user_id: str) -> dict[str, Any]:
    uid = service.identity.require(user_id)
    scope = service.for_user(uid)
    current_meta = dict(scope.user_memory.project() or {})
    current = build_snapshot(service, uid, current_meta)
    seen = {norm(str(current_meta.get("project") or ""))}
    items = [current]
    for task in scope.work.tasks():
        name = str(task.get("project") or "").strip()
        if not name or norm(name) in seen or belongs_to_project(task, current_meta):
            continue
        seen.add(norm(name))
        extra = {"project": name, "stage": "", "topics": [], "priority": task.get("priority") or "medium", "project_id": task.get("project_id") or ""}
        items.append(build_snapshot(service, uid, extra))
    return {"user_id": uid, "current": current, "items": items}
