from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    monkeypatch.setenv("RADAR_DEMO_CONTENT", "1")
    return RadarService(data_dir=tmp_path)


def test_interest_isolation(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = {row["topic"] for row in svc.for_user("alice").user_memory.interests()}
    bob = {row["topic"] for row in svc.for_user("bob").user_memory.interests()}
    assert "Agent Memory" in alice
    assert "Mem0" in alice
    assert "World Model" in bob
    assert "Autonomous Driving" in bob
    assert "Mem0" not in bob
    assert "World Model" not in alice


def test_knowledge_isolation(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    out = svc.track("demo-mem0", "collect", user_id="alice")
    assert out["card"]["title"].startswith("Mem0")
    alice_cards = svc.for_user("alice").memory.cards()
    bob_cards = svc.for_user("bob").memory.cards()
    assert any("Mem0" in (row.get("title") or "") for row in alice_cards)
    assert not any("Mem0" in (row.get("title") or "") for row in bob_cards)


def test_dislike_only_affects_alice(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.track("demo-world", "dislike", user_id="alice")
    alice_disliked = svc.for_user("alice").user_memory.behavior()["disliked_topics"]
    bob_disliked = svc.for_user("bob").user_memory.behavior()["disliked_topics"]
    assert any("World Model" in str(x) or "Autonomous Driving" in str(x) for x in alice_disliked)
    assert not any("World Model" in str(x) for x in bob_disliked)
    bob_topics = {row["topic"]: row["weight"] for row in svc.for_user("bob").user_memory.interests()}
    assert bob_topics.get("World Model", 0) >= 0.9


def test_same_article_different_scores(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = {row["id"]: row for row in svc.recommend_for("alice", auto_push=False)["for_you"]}
    bob = {row["id"]: row for row in svc.recommend_for("bob", auto_push=False)["for_you"]}
    assert alice["demo-mem0"]["score"] > bob["demo-mem0"]["score"]
    assert bob["demo-world"]["score"] > alice["demo-world"]["score"]


def test_feishu_open_id_maps_to_two_users(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    assert svc.identity.resolve_user("feishu", "ou_alice")["id"] == "alice"
    assert svc.identity.resolve_user("feishu", "ou_bob")["id"] == "bob"
    user_a = svc.identity.resolve_user("feishu", "ou_A", "User A")
    user_b = svc.identity.resolve_user("feishu", "ou_B", "User B")
    assert user_a["id"] != user_b["id"]
    assert user_a["id"] not in {"alice", "bob"} or user_b["id"] != user_a["id"]
    assert svc.identity.resolve_user("feishu", "ou_A")["id"] == user_a["id"]
