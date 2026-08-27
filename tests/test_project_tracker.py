from __future__ import annotations

import asyncio
from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def _chat(svc: RadarService, user_id: str, message: str) -> dict:
    return asyncio.run(svc.chat(message, user_id=user_id))


def test_tracker_is_isolated_and_estimated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.project_tracker("alice")
    bob = svc.project_tracker("bob")
    assert alice["user_id"] == "alice"
    assert bob["user_id"] == "bob"
    assert "Personal Work Secretary" in alice["project"]
    assert "Autonomous Driving" in bob["project"]
    assert any("Memory Demo" in (row.get("title") or "") for row in alice["in_progress"] + alice["completed"] + alice["open_tasks"])
    assert any("World Model" in (row.get("title") or "") for row in bob["in_progress"] + bob["completed"] + bob["open_tasks"])
    assert not any("World Model" in (row.get("title") or "") for row in alice["in_progress"] + alice["open_tasks"] + alice["completed"])
    assert not any("Memory Demo" in (row.get("title") or "") for row in bob["in_progress"] + bob["open_tasks"] + bob["completed"])
    assert alice["progress_basis"] == "tasks+goals+events"
    assert 0 <= alice["estimated_progress"] <= 100
    assert alice["estimated_progress"] != bob["estimated_progress"] or alice["project"] != bob["project"]


def test_completing_task_raises_estimated_progress(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    before = svc.project_tracker("alice")["estimated_progress"]
    open_tasks = svc.list_tasks("alice", include_done=False)
    assert open_tasks
    svc.update_task(open_tasks[0]["id"], {"status": "done"}, user_id="alice")
    after = svc.project_tracker("alice")["estimated_progress"]
    assert after >= before


def test_bob_cannot_see_alice_tracker_via_list(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice_pack = svc.list_project_trackers("alice")
    bob_pack = svc.list_project_trackers("bob")
    assert alice_pack["user_id"] == "alice"
    assert bob_pack["user_id"] == "bob"
    alice_names = {row["project"] for row in alice_pack["items"]}
    bob_names = {row["project"] for row in bob_pack["items"]}
    assert any("Personal" in name for name in alice_names)
    assert any("Autonomous" in name or "Driving" in name for name in bob_names)
    assert not any("World Model 数据集" in (row.get("title") or "") for item in alice_pack["items"] for row in item.get("open_tasks") or [])


def test_chat_query_project_is_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = _chat(svc, "alice", "这个项目现在进展怎么样？")
    bob = _chat(svc, "bob", "我的 Personal Agent 项目到哪了")
    named = _chat(svc, "alice", "我的 Personal Agent 项目到哪了")
    assert alice["intent"] == "query_project"
    assert named["intent"] == "query_project"
    assert bob["intent"] == "query_project"
    assert "进度约" in alice["reply"] and "估算" in alice["reply"]
    assert "完善 Memory Demo" in named["reply"]
    assert "整理 World Model 数据集" in _chat(svc, "bob", "这个项目现在进展怎么样？")["reply"]
    assert "完善 Memory Demo" not in bob["reply"]
    assert "整理 World Model 数据集" not in alice["reply"]
    assert "17:00 提醒" not in alice["reply"]
