"""Context-aware reminders. Writes through WorkMemory; delivers via Channel."""

from __future__ import annotations

import re
from typing import Any

from ..channels import send_for_user
from .context_builder import (
    build_morning_context,
    build_task_context,
    compose_deadline,
    compose_manual,
    compose_morning,
    compose_progress,
    compose_risk,
)
from .schemas import (
    DEADLINE_OFFSETS,
    hours_until,
    in_morning_window,
    in_quiet_hours,
    infer_trigger_at,
    local_date_key,
    now_cst,
    parse_dt,
    reminder_title,
)


def schedule_task_reminders(service: Any, user_id: str, task: dict[str, Any], now=None) -> list[dict[str, Any]]:
    if not task or task.get("status") in {"done", "cancelled"}:
        return []
    deadline = parse_dt(task.get("deadline"))
    if not deadline:
        return []
    work = service.for_user(user_id).work
    stamp = now_cst(now)
    remaining = hours_until(deadline, stamp)
    if remaining is None or remaining <= 0:
        return []
    created: list[dict[str, Any]] = []
    for label, offset in DEADLINE_OFFSETS:
        key = f"{task['id']}:deadline:{label}"
        if _has_key(work, key):
            continue
        # Keep trigger on the deadline timeline (possibly already past) so
        # evaluate fires as soon as the 24h/3h window opens, even when the
        # caller did not pass a frozen `now`.
        if label == "24h" and remaining <= 3:
            continue
        trigger = deadline - offset
        created.append(
            work.add_reminder(
                {
                    "task_id": task["id"],
                    "trigger_at": trigger.isoformat(),
                    "reminder_type": "deadline",
                    "status": "pending",
                    "dedupe_key": key,
                }
            )
        )
    return created


def on_task_updated(service: Any, user_id: str, task: dict[str, Any], patch: dict[str, Any] | None = None) -> None:
    work = service.for_user(user_id).work
    if task.get("status") in {"done", "cancelled"}:
        _cancel_pending(work, task.get("id") or "")
        return
    if patch and "deadline" in patch:
        _cancel_pending(work, task.get("id") or "", types={"deadline"})
        schedule_task_reminders(service, user_id, task)


def ensure_open_task_schedules(service: Any, user_id: str, now=None) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for task in service.for_user(user_id).work.tasks(include_done=False):
        created.extend(schedule_task_reminders(service, user_id, task, now=now))
    return created


def create_manual_reminder(service: Any, user_id: str, payload: dict[str, Any] | None = None, now=None) -> dict[str, Any]:
    data = dict(payload or {})
    data.pop("user_id", None)
    trigger = parse_dt(data.get("trigger_at")) or infer_trigger_at(str(data.get("message") or ""), now)
    task_id = str(data.get("task_id") or "").strip()
    if task_id and not service.for_user(user_id).work.get_task(task_id):
        raise KeyError(task_id)
    return service.for_user(user_id).work.add_reminder(
        {
            "task_id": task_id,
            "trigger_at": trigger.isoformat(),
            "reminder_type": str(data.get("reminder_type") or "manual"),
            "status": "pending",
            "dedupe_key": str(data.get("dedupe_key") or ""),
            "generated_content": str(data.get("generated_content") or data.get("message") or ""),
        }
    )


def evaluate_all(service: Any, now=None, *, deliver: bool = True, force_morning: bool = False) -> list[dict[str, Any]]:
    fired: list[dict[str, Any]] = []
    for uid in service.identity.active_ids():
        fired.extend(evaluate_user(service, uid, now=now, deliver=deliver, force_morning=force_morning))
    return fired


def evaluate_user(
    service: Any,
    user_id: str,
    now=None,
    *,
    deliver: bool = True,
    force_morning: bool = False,
) -> list[dict[str, Any]]:
    uid = service.identity.require(user_id)
    scope = service.for_user(uid)
    stamp = now_cst(now)
    ensure_open_task_schedules(service, uid, now=stamp)
    _plan_progress_and_risk(scope, stamp)
    if force_morning or in_morning_window(stamp, scope.workspace.push_settings()):
        _plan_morning(scope, stamp)
    fired: list[dict[str, Any]] = []
    quiet = in_quiet_hours(stamp, scope.workspace.push_settings()) and not force_morning
    for row in scope.work.reminders(include_sent=False):
        if row.get("status") != "pending":
            continue
        trigger = parse_dt(row.get("trigger_at"))
        if trigger and trigger > stamp:
            continue
        if quiet:
            continue
        fired.append(_deliver(service, uid, row, stamp, deliver=deliver))
    return fired


def _plan_progress_and_risk(scope: Any, now) -> None:
    work = scope.work
    for task in work.tasks(include_done=False):
        if task.get("parent_task_id"):
            continue
        ctx = build_task_context(scope, task, now)
        hours = ctx.get("hours_left")
        if hours is None or hours <= 0 or hours > 24:
            continue
        day = local_date_key(now)
        if str(task.get("status") or "") == "todo":
            key = f"{task['id']}:progress:{day}"
            if not _has_key(work, key):
                work.add_reminder(
                    {
                        "task_id": task["id"],
                        "trigger_at": now.isoformat(),
                        "reminder_type": "progress",
                        "status": "pending",
                        "dedupe_key": key,
                    }
                )
        total = int(ctx.get("children_total") or 0)
        done = int(ctx.get("children_done") or 0)
        if total and (done / total) < 0.5 and hours <= 24:
            key = f"{task['id']}:risk"
            if not _has_key(work, key):
                work.add_reminder(
                    {
                        "task_id": task["id"],
                        "trigger_at": now.isoformat(),
                        "reminder_type": "risk",
                        "status": "pending",
                        "dedupe_key": key,
                    }
                )


def _plan_morning(scope: Any, now) -> None:
    key = f"morning:{local_date_key(now)}"
    if _has_key(scope.work, key):
        return
    scope.work.add_reminder(
        {
            "task_id": "",
            "trigger_at": now.isoformat(),
            "reminder_type": "morning",
            "status": "pending",
            "dedupe_key": key,
        }
    )


def _deliver(service: Any, user_id: str, reminder: dict[str, Any], now, *, deliver: bool) -> dict[str, Any]:
    scope = service.for_user(user_id)
    content = _generate(scope, reminder, now)
    updated = scope.work.update_reminder(
        reminder["id"],
        {
            "generated_content": content,
            "status": "sent" if deliver else "pending",
            "sent_at": now.isoformat() if deliver else "",
        },
    )
    if not deliver:
        return updated
    send_for_user(
        user_id,
        scope.notify,
        {
            "id": reminder["id"],
            "type": "work_reminder",
            "title": reminder_title(str(reminder.get("reminder_type") or "")),
            "text": content,
            "content": content,
        },
        service._feishu_raw(user_id),
        service=service,
    )
    scope.work.add_event(
        {
            "event_type": "reminder_sent",
            "title": reminder_title(str(reminder.get("reminder_type") or "")),
            "content": content[:400],
            "source_type": "reminder",
            "source_ref": reminder.get("task_id") or reminder["id"],
        }
    )
    return scope.work.get_reminder(reminder["id"]) or updated


def _generate(scope: Any, reminder: dict[str, Any], now) -> str:
    kind = str(reminder.get("reminder_type") or "manual")
    if kind == "morning":
        return compose_morning(build_morning_context(scope, now))
    task = scope.work.get_task(str(reminder.get("task_id") or "")) or {}
    ctx = build_task_context(scope, task, now) if task else {"task": {"title": "约定事项"}, "status": "todo"}
    if kind == "deadline":
        return compose_deadline(ctx)
    if kind == "progress":
        return compose_progress(ctx)
    if kind == "risk":
        return compose_risk(ctx)
    seed = str(reminder.get("generated_content") or "")
    if not task and seed:
        ctx = {"task": {"title": _short_title(seed), "status": "todo"}, "status": "todo"}
    return compose_manual(ctx, seed)


def _short_title(text: str) -> str:
    theme = re.search(r"主题是([^，。；\n]+)", text or "")
    if theme:
        return theme.group(1).strip()[:80]
    return (text or "约定事项").split("。")[0][:80]


def _has_key(work: Any, key: str) -> bool:
    needle = (key or "").strip()
    if not needle:
        return False
    return any(row.get("dedupe_key") == needle for row in work.reminders())


def _cancel_pending(work: Any, task_id: str, types: set[str] | None = None) -> None:
    needle = (task_id or "").strip()
    if not needle:
        return
    for row in work.reminders(include_sent=False):
        if row.get("task_id") != needle or row.get("status") != "pending":
            continue
        if types and row.get("reminder_type") not in types:
            continue
        work.update_reminder(row["id"], {"status": "cancelled"})


def due_soon(task: dict[str, Any], now=None, hours: float = 24) -> bool:
    remaining = hours_until(parse_dt(task.get("deadline")), now)
    return remaining is not None and 0 < remaining <= hours
