from __future__ import annotations

import asyncio
from pathlib import Path

from radar.pipeline import RadarService
from radar.skills.report.schemas import infer_report_type


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def _chat(svc: RadarService, user_id: str, message: str) -> dict:
    return asyncio.run(svc.chat(message, user_id=user_id))


def test_infer_report_type():
    assert infer_report_type("生成今天日报。") == "daily"
    assert infer_report_type("生成本周总结") == "weekly"
    assert infer_report_type("写一份月度总结") == "monthly"


def test_daily_report_is_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = svc.generate_report("daily", user_id="alice")
    bob = svc.generate_report("daily", user_id="bob")
    assert alice["user_id"] == "alice"
    assert bob["user_id"] == "bob"
    assert "完善 Memory Demo" in alice["content"]
    assert "整理 World Model 数据集" in bob["content"]
    assert "完善 Memory Demo" not in bob["content"]
    assert "整理 World Model 数据集" not in alice["content"]
    assert "今日工作总结" in alice["content"]
    assert "进行中" in alice["content"]
    assert alice["sources"]["tasks"] >= 1
    bob_titles = {row["title"] for row in svc.list_reports("bob")}
    assert alice["title"] not in bob_titles or alice["id"] not in {row["id"] for row in svc.list_reports("bob")}
    assert svc.for_user("bob").work.get_report(alice["id"]) is None


def test_completed_task_appears_in_daily_report(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "完成多用户 Memory 隔离测试", "priority": "high"}, user_id="alice")
    svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    report = svc.generate_report("daily", user_id="alice")
    assert "完成多用户 Memory 隔离测试" in report["content"]
    assert "完成事项" in report["content"]
    assert "完成多用户 Memory 隔离测试" not in svc.generate_report("daily", user_id="bob")["content"]


def test_weekly_summary_differs_for_alice_and_bob(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = _chat(svc, "alice", "生成本周总结")
    bob = _chat(svc, "bob", "生成本周总结")
    assert alice["intent"] == "generate_report"
    assert bob["intent"] == "generate_report"
    assert "本周工作总结" in alice["reply"]
    assert "Personal Work Secretary" in alice["reply"] or "Memory" in alice["reply"]
    assert "Autonomous Driving" in bob["reply"] or "World Model" in bob["reply"]
    assert "完善 Memory Demo" in alice["reply"]
    assert "整理 World Model 数据集" in bob["reply"]
    assert "完善 Memory Demo" not in bob["reply"]
    assert "整理 World Model 数据集" not in alice["reply"]


def test_save_report_ignores_body_user_id(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    row = svc.save_report(
        {"title": "Alice only", "content": "secret", "report_type": "daily", "user_id": "bob"},
        user_id="alice",
    )
    assert row["user_id"] == "alice"
    assert "secret" not in "\n".join(item.get("content") or "" for item in svc.list_reports("bob"))
