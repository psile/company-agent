"""Generate daily/weekly reports from Work Memory. Writes through RadarService only."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from ...work_models import normalize_report_type
from .context_builder import build_report_context
from .schemas import heading_for, infer_report_type
from .templates import render_report


class ReportSkill:
    name = "report"

    def __init__(self, service: Any) -> None:
        self.service = service

    async def can_handle(self, user_id: str, message: str, context: dict[str, Any] | None = None) -> bool:
        return bool(re.search(r"(日报|周报|月度总结|项目总结|工作总结|生成本周)", message or ""))

    async def execute(self, user_id: str, payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        message = str((payload or {}).get("message") or "")
        report_type = str((payload or {}).get("report_type") or infer_report_type(message))
        row = generate_report(
            self.service,
            user_id,
            report_type,
            project_id=str((payload or {}).get("project_id") or ""),
            start_time=(payload or {}).get("start_time"),
            end_time=(payload or {}).get("end_time"),
        )
        return {
            "ok": True,
            "report": row,
            "reply": row.get("content") or "已生成工作总结。",
        }

    async def generate(
        self,
        user_id: str,
        report_type: str,
        start_time=None,
        end_time=None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return generate_report(
            self.service,
            user_id,
            report_type,
            start_time=start_time,
            end_time=end_time,
            project_id=project_id,
        )


def generate_report(
    service: Any,
    user_id: str,
    report_type: str = "daily",
    *,
    now=None,
    project_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    uid = service.identity.require(user_id)
    kind = normalize_report_type(report_type)
    ctx = build_report_context(
        service,
        uid,
        kind,
        now=now,
        project_id=project_id,
        start_time=start_time,
        end_time=end_time,
    )
    content = render_report(ctx)
    title = _title(kind, ctx)
    return service.save_report(
        {
            "report_type": kind,
            "project_id": project_id or "",
            "start_time": ctx["start"].isoformat(),
            "end_time": ctx["end"].isoformat(),
            "title": title,
            "content": content,
            "sources": ctx.get("sources") or {},
        },
        user_id=uid,
    )


def _title(report_type: str, ctx: dict[str, Any]) -> str:
    start = ctx["start"].date().isoformat()
    end = (ctx["end"] - timedelta(seconds=1)).date().isoformat()
    if report_type == "daily":
        return f"{heading_for('daily')} · {start}"
    if report_type == "weekly":
        return f"{heading_for('weekly')} · {start} ~ {end}"
    if report_type == "monthly":
        return f"{heading_for('monthly')} · {start[:7]}"
    project = ctx.get("project") or "当前项目"
    return f"{heading_for(report_type)} · {project}"
