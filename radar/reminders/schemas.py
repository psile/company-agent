"""Reminder timing helpers. Skills never write reminder files directly."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..work_models import REMINDER_TYPES, normalize_reminder_type

CST = timezone(timedelta(hours=8))
DEADLINE_OFFSETS = (("24h", timedelta(hours=24)), ("3h", timedelta(hours=3)))


def now_cst(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(CST)
    if now.tzinfo is None:
        return now.replace(tzinfo=CST)
    return now.astimezone(CST)


def parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=CST)
    return stamp.astimezone(CST)


def hours_until(deadline: datetime | None, now: datetime | None = None) -> float | None:
    if deadline is None:
        return None
    return (deadline - now_cst(now)).total_seconds() / 3600


def local_date_key(now: datetime | None = None) -> str:
    return now_cst(now).date().isoformat()


def parse_clock(value: str, default: tuple[int, int] = (8, 30)) -> tuple[int, int]:
    match = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        return default
    hour = max(0, min(23, int(match.group(1))))
    minute = max(0, min(59, int(match.group(2))))
    return hour, minute


def in_quiet_hours(now: datetime | None, settings: dict[str, Any] | None) -> bool:
    prefs = settings or {}
    if not prefs.get("quiet_hours", True):
        return False
    stamp = now_cst(now)
    start_h, start_m = parse_clock(str(prefs.get("dnd") or "22:00 - 08:00").split("-")[0], (22, 0))
    end_raw = str(prefs.get("dnd") or "22:00 - 08:00")
    end_part = end_raw.split("-")[-1] if "-" in end_raw else "08:00"
    end_h, end_m = parse_clock(end_part, (8, 0))
    current = stamp.hour * 60 + stamp.minute
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def in_morning_window(now: datetime | None, settings: dict[str, Any] | None, window_minutes: int = 30) -> bool:
    prefs = settings or {}
    if not prefs.get("morning_brief", True):
        return False
    stamp = now_cst(now)
    hour, minute = parse_clock(str(prefs.get("morning_time") or "08:30"))
    target = hour * 60 + minute
    current = stamp.hour * 60 + stamp.minute
    return abs(current - target) <= window_minutes


CN_HOUR = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}

CLOCK_RE = re.compile(
    r"(?:(?P<num>\d{1,2})|(?P<cn>十一|十二|十|[一二三四五六七八九两]))"
    r"\s*(?:点|:|：)(?P<min>半|\d{1,2})?"
)


def has_clock(text: str) -> bool:
    return bool(CLOCK_RE.search(text or "")) or bool(re.search(r"(等下|待会|一会儿|一会)", text or ""))


def parse_spoken_clock(text: str, now: datetime | None = None) -> tuple[int, int] | None:
    blob = text or ""
    match = CLOCK_RE.search(blob)
    if not match:
        return None
    if match.group("num"):
        hour = int(match.group("num"))
    else:
        hour = CN_HOUR.get(match.group("cn") or "", 0)
    minute_raw = match.group("min") or ""
    minute = 30 if minute_raw == "半" else int(minute_raw) if minute_raw else 0
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    if re.search(r"晚上|今晚|夜里", blob) and hour < 12:
        hour += 12
    elif re.search(r"下午|中午", blob) and hour < 12:
        hour += 12
    elif not re.search(r"上午|早上|凌晨", blob) and 1 <= hour <= 6:
        hour += 12
    return hour, minute


def infer_trigger_at(text: str, now: datetime | None = None) -> datetime:
    stamp = now_cst(now)
    day = stamp.date()
    if "明天" in text:
        day = stamp.date() + timedelta(days=1)
    elif "后天" in text:
        day = stamp.date() + timedelta(days=2)
    parsed = parse_spoken_clock(text, stamp)
    if parsed:
        hour, minute = parsed
    elif "上午" in text:
        hour, minute = 10, 0
    elif "晚上" in text or "今晚" in text:
        hour, minute = 20, 0
        day = stamp.date()
    elif "下午" in text:
        hour, minute = 15, 0
    elif re.search(r"等下|待会|一会儿|一会", text or ""):
        later = stamp + timedelta(minutes=30)
        return later.replace(second=0, microsecond=0)
    else:
        later = stamp + timedelta(hours=1)
        return later.replace(second=0, microsecond=0)
    trigger = datetime(day.year, day.month, day.day, hour, minute, tzinfo=CST)
    if trigger <= stamp and "明天" not in (text or "") and "后天" not in (text or ""):
        return stamp.replace(second=0, microsecond=0)
    return trigger


def reminder_title(reminder_type: str) -> str:
    kind = normalize_reminder_type(reminder_type)
    return {
        "deadline": "截止提醒",
        "progress": "进度提醒",
        "morning": "今日工作重点",
        "risk": "风险提醒",
        "manual": "工作提醒",
    }.get(kind, "工作提醒")


def valid_type(value: str) -> bool:
    return (value or "").strip().lower() in REMINDER_TYPES
