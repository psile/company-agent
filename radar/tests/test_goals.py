from __future__ import annotations

from pathlib import Path

import pytest

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def test_goals_crud_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    # Add goal
    goal = svc.add_goal({"title": "Read World Model paper", "kind": "today", "priority": "high"}, user_id="alice")
    assert goal["title"] == "Read World Model paper"
    assert goal["kind"] == "today"
    assert goal["priority"] == "high"
    assert goal["linked"] == 0
    # Update goal
    updated = svc.update_goal(goal["id"], {"progress": 50}, user_id="alice")
    assert updated["progress"] == 50
    assert updated["linked"] == 0
    # Delete goal
    assert svc.delete_goal(goal["id"], user_id="alice")["ok"] is True
    with pytest.raises(KeyError):
        svc.update_goal(goal["id"], {}, user_id="alice")
    # Isolation
    bob_goal = svc.add_goal({"title": "Bob task", "kind": "week"}, user_id="bob")
    alice_goals = [g for g in (svc._scope("alice").workspace.goals())]
    assert not any(g["title"] == "Bob task" for g in alice_goals)


def test_goal_task_auto_assign(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    goal = svc.add_goal({"title": "构建记忆系统", "kind": "quarter"}, user_id="alice")
    # Create matching task
    task = svc.create_task(
        {"title": "设计车载云端记忆系统", "project": "Personal Work Secretary Agent"},
        user_id="alice",
    )
    # Goal should have linked task
    goals = svc._scope("alice").workspace.goals()
    matched = [g for g in goals if g["id"] == goal["id"]]
    assert matched and matched[0].get("linked") >= 1
    # Task should carry goal_id back-ref
    assert task.get("goal_id") == goal["id"]


def test_goal_progress_update_on_task_complete(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    goal = svc.add_goal({"title": "Complete X project", "kind": "today"}, user_id="alice")
    task = svc.create_task(
        {"title": "完成 X 项目核心功能", "goal_id": goal["id"]},
        user_id="alice",
    )
    # Complete task
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    # Goal should reflect
    goals = svc._scope("alice").workspace.goals()
    matched = [g for g in goals if g["id"] == goal["id"]]
    assert matched and matched[0].get("linked", 0) >= 1
    assert matched[0].get("progress", 0) >= 5


def test_goal_keyword_matching(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    goal = svc.add_goal({"title": "VLM Intelligent Cockpit Research", "kind": "week"}, user_id="alice")
    # Title match
    task = svc.create_task({"title": "研究 VLM 在智能座舱的应用"}, user_id="alice")
    goals = svc._scope("alice").workspace.goals()
    assert any(g.get("linked") > 0 for g in goals if g["id"] == goal["id"])
    # No match
    task2 = svc.create_task({"title": "吃晚饭"}, user_id="alice")
    goals = svc._scope("alice").workspace.goals()
    assert not any(g.get("linked") > 1 for g in goals if g["id"] == goal["id"])


def test_goal_edit_roundtrip(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    goal = svc.add_goal({"title": "Original title", "kind": "open"}, user_id="alice")
    updated = svc.update_goal(
        goal["id"],
        {"title": "Renamed title", "priority": "low", "kind": "quarter"},
        user_id="alice",
    )
    assert updated["title"] == "Renamed title"
    assert updated["priority"] == "low"
    assert updated["kind"] == "quarter"
