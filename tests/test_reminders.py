from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

from radar.pipeline import RadarService
from radar.reminders.schemas import CST


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    monkeypatch.setenv("RADAR_PUSH_DRY_RUN", "1")
    return RadarService(data_dir=tmp_path)


def _chat(svc: RadarService, user_id: str, message: str) -> dict:
    return asyncio.run(svc.chat(message, user_id=user_id))


def _notice_blob(svc: RadarService, user_id: str) -> str:
    rows = svc.for_user(user_id).notify.list()
    return "\n".join(f"{row.get('title') or ''} {row.get('content') or ''}" for row in rows)


def test_deadline_reminder_is_contextual_not_a_timer(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 10, 0, tzinfo=CST)
    task = svc.create_task(
        {
            "title": "完成 Personal Agent PPT",
            "status": "todo",
            "project": "Personal Work Secretary Agent",
            "deadline": (now + timedelta(hours=20)).isoformat(),
        },
        user_id="alice",
    )
    fired = svc.evaluate_reminders("alice", now=now)
    deadline_rows = [row for row in fired if row.get("reminder_type") == "deadline" and row.get("task_id") == task["id"]]
    assert deadline_rows
    content = deadline_rows[0]["generated_content"]
    assert "Personal Agent PPT" in content
    assert "待办" in content
    assert "Memory 模块" in content or "项目" in content
    assert not re.search(r"今天\s*\d{1,2}:\d{2}\s*提醒", content)
    assert "17:00 提醒" not in content


def test_progress_and_risk_use_children(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 10, 0, tzinfo=CST)
    parent = svc.create_task(
        {
            "title": "周五完成 Personal Agent 汇报",
            "status": "todo",
            "deadline": (now + timedelta(hours=20)).isoformat(),
        },
        user_id="alice",
    )
    svc.breakdown_task(parent["id"], user_id="alice")
    fired = svc.evaluate_reminders("alice", now=now)
    progress = [row for row in fired if row.get("reminder_type") == "progress" and row.get("task_id") == parent["id"]]
    risk = [row for row in fired if row.get("reminder_type") == "risk" and row.get("task_id") == parent["id"]]
    assert progress
    assert "仍是待办" in progress[0]["generated_content"]
    assert risk
    assert "不足一半" in risk[0]["generated_content"]
    assert "子任务完成 0/" in risk[0]["generated_content"]


def test_bob_does_not_receive_alice_reminders(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 10, 0, tzinfo=CST)
    svc.create_task(
        {
            "title": "Alice secret PPT",
            "user_id": "bob",
            "deadline": (now + timedelta(hours=20)).isoformat(),
        },
        user_id="alice",
    )
    svc.evaluate_reminders("alice", now=now)
    assert "Alice secret PPT" in _notice_blob(svc, "alice")
    assert "Alice secret PPT" not in _notice_blob(svc, "bob")
    bob_ids = {row.get("task_id") for row in svc.list_reminders("bob")}
    alice_ids = {row["id"] for row in svc.list_tasks("alice") if "Alice secret PPT" in row["title"]}
    assert alice_ids
    assert not (bob_ids & alice_ids)


def test_morning_brief_is_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 8, 30, tzinfo=CST)
    alice = svc.evaluate_reminders("alice", now=now, force_morning=True)
    bob = svc.evaluate_reminders("bob", now=now, force_morning=True)
    alice_text = "\n".join(row.get("generated_content") or "" for row in alice if row.get("reminder_type") == "morning")
    bob_text = "\n".join(row.get("generated_content") or "" for row in bob if row.get("reminder_type") == "morning")
    assert "完善 Memory Demo" in alice_text
    assert "整理 World Model 数据集" in bob_text
    assert "完善 Memory Demo" not in bob_text
    assert "整理 World Model 数据集" not in alice_text
    assert "完善 Memory Demo" not in _notice_blob(svc, "bob")
    assert "整理 World Model 数据集" not in _notice_blob(svc, "alice")


def test_chat_create_reminder_stays_on_alice(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = _chat(svc, "alice", "明天下午提醒我发方案给老板。")
    assert out["intent"] == "create_reminder"
    assert "提醒" in out["reply"]
    manuals = [row for row in svc.list_reminders("alice") if row.get("reminder_type") == "manual"]
    assert manuals
    assert all(row["user_id"] == "alice" for row in manuals)
    bob_manual = [row for row in svc.list_reminders("bob") if row.get("reminder_type") == "manual"]
    assert bob_manual == []
    titles = {row["title"] for row in svc.list_tasks("alice")}
    assert any("方案" in title or "老板" in title for title in titles)


def test_done_task_cancels_pending_reminders(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 10, 0, tzinfo=CST)
    task = svc.create_task(
        {
            "title": "Write overdue brief",
            "deadline": (now + timedelta(hours=30)).isoformat(),
        },
        user_id="alice",
    )
    pending = [row for row in svc.list_reminders("alice") if row.get("task_id") == task["id"] and row.get("status") == "pending"]
    assert pending
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    leftover = [row for row in svc.list_reminders("alice") if row.get("task_id") == task["id"] and row.get("status") == "pending"]
    assert leftover == []


def test_three_oclock_meeting_creates_timed_reminder(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    now = datetime(2026, 8, 27, 14, 50, tzinfo=CST)
    monkeypatch.setattr("radar.reminders.schemas.now_cst", lambda current=None: now if current is None else current)
    monkeypatch.setattr("radar.skills.reminder.service.now_cst", lambda current=None: now if current is None else current)
    out = _chat(svc, "bob", "我等下三点要开一个交流会，提醒我一下，主题是车载记忆系统的构建，顺便帮我准备一下相关材料，并发我")
    assert out["intent"] == "create_reminder"
    assert "三点" in out["reply"] or "15:00" in out["reply"] or "14:50" in out["reply"] or "2026-08-27 15" in out["reply"]
    manuals = [row for row in svc.list_reminders("bob") if row.get("reminder_type") == "manual"]
    assert manuals
    trigger = datetime.fromisoformat(manuals[0]["trigger_at"])
    assert trigger.hour == 15
    assert trigger.minute == 0
    titles = {row["title"] for row in svc.list_tasks("bob")}
    assert any("车载记忆" in title for title in titles)
    later = datetime(2026, 8, 27, 15, 0, tzinfo=CST)
    fired = svc.evaluate_reminders("bob", now=later)
    sent = [row for row in fired if row.get("reminder_type") == "manual"]
    assert sent
    blob = _notice_blob(svc, "bob")
    assert "车载记忆" in blob or "到点了" in blob
    assert "车载记忆" not in _notice_blob(svc, "alice")
