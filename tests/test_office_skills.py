from pathlib import Path

from radar.pipeline import RadarService
from radar.skills.catalog import list_office_skills


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def test_enabled_office_skills_are_the_work_secretary_set():
    items = list_office_skills()
    enabled = {row["id"] for row in items if row["status"] == "enabled"}
    assert enabled == {
        "task_capture",
        "task_planner",
        "work_brief",
        "reminder",
        "daily_report",
        "weekly_report",
        "project_tracker",
    }
    coming = {row["id"] for row in items if row["status"] == "coming_soon"}
    assert {"research", "knowledge_organizer", "meeting", "decision", "deliverable"} <= coming
    blob = " ".join(f"{row.get('name')} {row.get('title')} {row.get('summary')}" for row in items)
    assert "日期计算" not in blob
    assert "习惯打卡" not in blob


def test_office_skills_catalog_is_not_user_memory(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.dashboard("alice")
    bob = svc.dashboard("bob")
    assert alice["skills"] == bob["skills"]
    assert alice["skills"] == svc.list_office_skills()
    assert "完善 Memory Demo" not in str(alice["skills"])
    assert "World Model 数据集" not in str(bob["skills"])
    enabled = [row for row in alice["skills"] if row["status"] == "enabled"]
    assert all(row.get("href") or row.get("example") for row in enabled)
