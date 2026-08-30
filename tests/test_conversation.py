from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from radar.pipeline import RadarService
from radar.proactive import evaluate_proactive_notification


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def _chat(svc: RadarService, user_id: str, message: str, session_id: str | None = None) -> dict:
    return asyncio.run(svc.chat(message, session_id=session_id, user_id=user_id))


def test_demo_create_watch_updates_memory_and_history(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = _chat(
        svc,
        "alice",
        "最近帮我关注多模态长期记忆、Mem0 和 MemOS，有比较重要的新论文再告诉我。",
    )
    assert out["intent"] == "create_watch"
    assert out["memory_updated"] is True
    assert any(action["tool"] == "create_watch" and action["status"] == "success" for action in out["actions"])
    topics = {row["topic"] for row in svc.for_user("alice").user_memory.interests()}
    assert {"多模态长期记忆", "Mem0", "MemOS"} <= topics
    detail = svc.conversation_detail(out["session_id"], "alice")
    assert [row["role"] for row in detail["messages"]] == ["user", "assistant"]


def test_demo_search_uses_radar_recommendations(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = _chat(svc, "alice", "最近 Agent Memory 有什么值得看的？")
    assert out["intent"] == "search_info"
    assert any(action["tool"] == "search_latest_content" for action in out["actions"])
    assert "值得看" in out["reply"] or "Radar" in out["reply"]


def test_demo_conversation_profile_is_persisted(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = _chat(svc, "alice", "以后普通问题回答简洁一点，但技术问题可以详细分析。")
    assert out["intent"] == "change_conversation_setting"
    profile = svc.conversation_profile("alice").get()
    assert profile["verbosity"] == "concise"
    assert profile["technical_detail"] == "high"


def test_demo_long_term_memory_survives_new_session(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    first = _chat(svc, "alice", "我最近主要在做个人 AI 秘书和 Agent Memory。")
    assert first["intent"] == "save_memory"
    second = _chat(svc, "alice", "我最近主要研究什么？")
    assert second["session_id"] != first["session_id"]
    assert second["intent"] in {"search_memory", "query_memory"}
    assert "个人 AI 秘书" in second["reply"]
    assert "Agent Memory" in second["reply"]


def test_conversations_and_profiles_are_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = _chat(svc, "alice", "我最近主要在做 Agent Memory。")
    bob = _chat(svc, "bob", "我最近主要在做 World Model。")
    assert {row["id"] for row in svc.conversations("alice")} == {alice["session_id"]}
    assert {row["id"] for row in svc.conversations("bob")} == {bob["session_id"]}
    with pytest.raises(KeyError):
        svc.conversation_detail(alice["session_id"], "bob")
    svc.save_conversation_profile({"verbosity": "detailed"}, "alice")
    assert svc.conversation_profile("alice").get()["verbosity"] == "detailed"
    assert svc.conversation_profile("bob").get()["verbosity"] == "concise"


def test_proactive_policy_uses_profile_and_penalties():
    high = asyncio.run(
        evaluate_proactive_notification(
            "alice",
            {"score": 96, "novelty": 0.9, "goal_match": 0.9, "source_quality": 0.9},
            {"proactive_level": "high"},
            {"instant": True, "instant_threshold": 80},
        )
    )
    duplicate = asyncio.run(
        evaluate_proactive_notification(
            "alice",
            {"score": 96, "novelty": 0.9, "goal_match": 0.9, "source_quality": 0.9, "duplicate_score": 1, "interrupt_cost": 1},
            {"proactive_level": "low"},
            {"instant": True, "instant_threshold": 80},
        )
    )
    assert high.decision == "push_now"
    assert duplicate.decision != "push_now"
    assert high.score > duplicate.score


def test_general_chat_fallback_varies_without_llm(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    hello = _chat(svc, "bob", "你好")
    who = _chat(svc, "bob", "你是谁")
    can = _chat(svc, "bob", "可以帮我做什么")
    remember = _chat(svc, "bob", "可以记录其他事情吗")
    assert hello["intent"] == "general_chat"
    assert who["reply"] != hello["reply"]
    assert can["reply"] != hello["reply"]
    assert remember["reply"] != hello["reply"]
    assert "个人工作秘书" in who["reply"]
    assert "关注主题" in can["reply"]
    assert "记住" in remember["reply"]


def test_smalltalk_skips_intent_llm(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    routed = []

    def fake_json(*_args, **_kwargs):
        routed.append("json")
        return {"intent": "unknown", "confidence": 0.1, "entities": {}}

    monkeypatch.setattr("radar.agent.llm.chat_json", fake_json)
    out = _chat(svc, "bob", "我可以叫你小鲸吗")
    assert out["intent"] == "general_chat"
    assert routed == []
