from __future__ import annotations

import asyncio
from pathlib import Path

from radar.pipeline import RadarService
from radar.skills.task_capture.extractor import extract_tasks, infer_deadline


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def _chat(svc: RadarService, user_id: str, message: str) -> dict:
    return asyncio.run(svc.chat(message, user_id=user_id))


def test_extracts_deadline_and_title_without_llm(monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    out = extract_tasks("周五前完成 Memory Demo。")
    assert out["should_create_task"] is True
    assert out["confidence"] >= 0.75
    assert "Memory Demo" in out["tasks"][0]["title"]
    assert out["tasks"][0]["deadline"]
    assert infer_deadline("周五前完成 Memory Demo。")


def test_opinion_question_is_not_a_task(monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    out = extract_tasks("你觉得 MemoryOS 怎么样？")
    assert out["should_create_task"] is False
    assert out["tasks"] == []


def test_chat_creates_isolated_task(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = _chat(svc, "alice", "周五前把 Personal Agent PPT 做完，提醒我。")
    assert out["intent"] == "create_task"
    assert "已记下" in out["reply"]
    titles = {row["title"] for row in svc.list_tasks("alice")}
    assert any("PPT" in title or "Personal Agent" in title for title in titles)
    bob_titles = {row["title"] for row in svc.list_tasks("bob")}
    assert not any("PPT" in title for title in bob_titles)


def test_chat_does_not_turn_question_into_task(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    before = {row["id"] for row in svc.list_tasks("alice")}
    out = _chat(svc, "alice", "你觉得 MemoryOS 怎么样？")
    assert out["intent"] != "create_task"
    after = {row["id"] for row in svc.list_tasks("alice")}
    assert after == before


def test_breakdown_creates_child_tasks(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    parent = svc.create_task({"title": "周五完成 Personal Agent 汇报", "priority": "high"}, user_id="alice")
    out = svc.breakdown_task(parent["id"], user_id="alice")
    assert len(out["items"]) >= 3
    children = [row for row in svc.list_tasks("alice") if row.get("parent_task_id") == parent["id"]]
    assert len(children) == len(out["items"])
    assert all(row["user_id"] == "alice" for row in children)
    bob_children = [row for row in svc.list_tasks("bob") if row.get("parent_task_id") == parent["id"]]
    assert bob_children == []
