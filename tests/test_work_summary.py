from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def _patch_task_date(svc: RadarService, task_id: str, user_id: str, completed_at: str) -> None:
    from radar.core.repositories import JsonRepository

    repo = JsonRepository(svc.root / "users", "tasks.json")
    repo.update(user_id, task_id, {"completed_at": completed_at, "updated_at": completed_at})


def test_daily_ordering_desc(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    today = datetime.now()
    for offset, title in ((3, "三天前任务"), (1, "昨天任务"), (0, "今天任务")):
        task = svc.create_task({"title": title}, user_id="alice")
        stamp = today - timedelta(days=offset)
        _patch_task_date(svc, task["id"], "alice", stamp.isoformat() + "+08:00")
        svc.update_task(task["id"], {"status": "done"}, user_id="alice")
        _patch_task_date(svc, task["id"], "alice", stamp.isoformat() + "+08:00")
    summary = svc.work_summary("alice", range_days=7)
    dates = [day["date"] for day in summary["days"]]
    assert dates == sorted(dates, reverse=True)
    assert today.strftime("%Y-%m-%d") in dates and (today - timedelta(days=3)).strftime("%Y-%m-%d") in dates


def test_user_isolation(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "Alice only task"}, user_id="alice")
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    alice = svc.work_summary("alice")
    bob = svc.work_summary("bob")
    alice_titles = [t for day in alice["days"] for t in day["top_completed"]]
    assert "Alice only task" in alice_titles
    for day in bob["days"]:
        assert "Alice only task" not in day["top_completed"]
    assert all("Alice only task" not in json_day for json_day in [str(bob)])
    assert bob["stats"]["completed"] == 0 or "Alice only task" not in str(bob)


def test_date_scope_daily(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "scoped task"}, user_id="alice")
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    _patch_task_date(svc, task["id"], "alice", "2026-08-01T10:00:00+08:00")
    now = datetime(2026, 8, 30, 12, 0)
    summary = svc.work_summary("alice", range_days=7, now=now)
    for day in summary["days"]:
        assert day["date"] != "2026-08-01"
    assert summary["stats"]["completed"] == 0


def test_empty_day_returns_clean(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "still working"}, user_id="alice")
    _patch_task_date(svc, task["id"], "alice", "2026-08-30T10:00:00+08:00")
    summary = svc.work_summary("alice", range_days=7)
    assert summary["stats"]["completed"] == 0
    assert summary["stats"]["in_progress"] >= 1
    today = summary["days"][0]
    assert today["summary"] != ""


def test_counts_match_real_data(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    for index in range(3):
        task = svc.create_task({"title": f"task-{index}"}, user_id="alice")
        svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    summary = svc.work_summary("alice", range_days=7)
    assert summary["stats"]["completed"] == 3
    total_in_cards = sum(day["stats"]["completed"] for day in summary["days"])
    assert total_in_cards == 3


def test_detail_report_link(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    report = svc.generate_report("daily", user_id="alice")
    summary = svc.work_summary("alice", range_days=7)
    day = summary["days"][0]
    date = day["date"]
    reports = [row for row in svc.list_reports("alice", "daily")]
    assert any((row.get("start_time") or "")[:10] == date for row in reports)
    assert svc.for_user("alice").work.get_report(report["id"]) is not None
    assert "完成事项" in report["content"]


def test_period_overview_week_isolation(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "alice week task"}, user_id="alice")
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    alice = svc.work_period_summary("week", "alice")
    bob = svc.work_period_summary("week", "bob")
    assert alice["stats"]["completed"] >= 1
    assert bob["stats"]["completed"] == 0
    assert alice["period"]["type"] == "week"
