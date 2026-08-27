"""Report windows and type inference. Skills never write report files directly."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from ...reminders.schemas import CST, now_cst, parse_dt
from ...work_models import REPORT_TYPES, normalize_report_type

HEADINGS = {
    "daily": "今日工作总结",
    "weekly": "本周工作总结",
    "monthly": "本月工作总结",
    "project_summary": "项目总结",
    "work_summary": "工作总结",
}


def infer_report_type(message: str) -> str:
    text = message or ""
    if re.search(r"周报|本周|这周|一周", text):
        return "weekly"
    if re.search(r"月度|本月|月报", text):
        return "monthly"
    if re.search(r"项目总结|项目进展|项目复盘", text):
        return "project_summary"
    if re.search(r"工作总结", text) and not re.search(r"今日|今天|日报", text):
        return "work_summary"
    return "daily"


def report_window(report_type: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    stamp = now_cst(now)
    kind = normalize_report_type(report_type)
    day = stamp.date()
    if kind == "daily":
        start = datetime(day.year, day.month, day.day, tzinfo=CST)
        return start, start + timedelta(days=1)
    if kind == "weekly":
        monday = day - timedelta(days=day.weekday())
        start = datetime(monday.year, monday.month, monday.day, tzinfo=CST)
        return start, start + timedelta(days=7)
    if kind == "monthly":
        start = datetime(day.year, day.month, 1, tzinfo=CST)
        if day.month == 12:
            end = datetime(day.year + 1, 1, 1, tzinfo=CST)
        else:
            end = datetime(day.year, day.month + 1, 1, tzinfo=CST)
        return start, end
    start = stamp - timedelta(days=14)
    return start, stamp + timedelta(seconds=1)


def in_window(value: Any, start: datetime, end: datetime) -> bool:
    stamp = parse_dt(value)
    if stamp is None:
        return False
    return start <= stamp < end


def heading_for(report_type: str) -> str:
    return HEADINGS.get(normalize_report_type(report_type), "工作总结")


__all__ = ["CST", "REPORT_TYPES", "heading_for", "infer_report_type", "in_window", "now_cst", "parse_dt", "report_window"]
