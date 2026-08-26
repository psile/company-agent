from pathlib import Path

from radar.feishu import _app_message_payload, _lookup_open_id_by_mobile, _sign, format_push
from radar.ingest import parse_atom, parse_rss
from radar.intelligence import understand_heuristic
from radar.llm import parse_json_object
from radar.models import RawItem
from radar.pipeline import RadarService
from radar.recommender import pick_push, rank_for_you
from radar.store import LocalMemory
from radar.user_memory import UserMemory


ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Agent Memory for RAG</title>
    <summary>We study long-term memory in agents.</summary>
    <published>2026-08-01T00:00:00Z</published>
    <id>http://arxiv.org/abs/2601.00001</id>
    <link rel="alternate" href="https://arxiv.org/abs/2601.00001"/>
  </entry>
</feed>
"""

RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>OpenAI launch event</title>
      <link>https://example.com/launch</link>
      <description>Keynote and GPU news.</description>
    </item>
  </channel>
</rss>
"""


def test_parse_atom_keeps_url():
    spec = {"id": "arxiv", "name": "ArXiv", "kind": "arxiv", "type": "paper"}
    items = parse_atom(ATOM, spec)
    assert items[0].source_url.startswith("https://arxiv.org")
    assert "Memory" in items[0].title or "memory" in items[0].summary.lower()
    assert items[0].item_type == "paper"


def test_parse_rss():
    spec = {"id": "news", "name": "News", "kind": "rss", "type": "news"}
    items = parse_rss(RSS, spec)
    assert items[0].source_url == "https://example.com/launch"
    assert items[0].item_type == "news"


def test_for_you_ranks_memory_above_funding(tmp_path: Path):
    mem = UserMemory(tmp_path, LocalMemory(tmp_path))
    paper = understand_heuristic(
        RawItem("a", "ArXiv", "work", "Temporal Memory for Agents", "long-term memory ranking", "https://x/1", "2026-08-24T00:00:00Z", "paper")
    )
    news = understand_heuristic(
        RawItem("b", "The Verge AI", "interest", "Startup raises Series B funding", "financing news", "https://x/2", "2026-08-24T00:00:00Z", "news")
    )
    ranked = rank_for_you([paper, news], mem.context())
    assert ranked[0]["id"] == paper["id"]
    assert "融资" in (news.get("tags") or [])


def test_card_requires_url(tmp_path: Path):
    mem = LocalMemory(tmp_path)
    try:
        mem.add_card({"title": "x", "summary": "y", "source_url": ""})
        assert False, "should reject"
    except ValueError:
        pass
    mem.add_card({"title": "x", "summary": "y", "source_url": "https://example.com/a"})
    assert mem.cards()[0]["source_url"].startswith("http")


def test_parse_llm_json_fenced():
    parsed = parse_json_object('note\n```json\n{"channel":"work","keywords":["RAG"]}\n```')
    assert parsed["channel"] == "work"
    assert parsed["keywords"] == ["RAG"]


def test_click_updates_interest_weight(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    svc = RadarService(data_dir=tmp_path)
    item = {
        "id": "aaaaaaaaaaaa",
        "title": "vLLM memory kernel",
        "summary": "release notes",
        "summary_zh": "vLLM 记忆内核有更新。",
        "source_url": "https://example.com/vllm",
        "source_name": "GitHub",
        "tags": ["推理引擎", "长期记忆"],
        "item_type": "release",
        "score": 88,
    }
    svc.memory.save_feeds([], [item], intel=[], for_you=[item])
    before = {row["topic"]: row["weight"] for row in svc.user_memory.interests()}
    out = svc.track("aaaaaaaaaaaa", "open")
    assert out["ok"]
    assert svc.memory.events()[0]["action"] == "open"
    assert svc.hierarchy.short_term()[0]["user_input"].startswith("我open了")
    after = {row["topic"]: row["weight"] for row in svc.user_memory.interests()}
    assert after.get("vLLM", 0) >= before.get("vLLM", 0)
    assert after.get("长期记忆", 0) > 0.4


def test_like_files_card_with_url(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    svc = RadarService(data_dir=tmp_path)
    item = {
        "id": "bbbbbbbbbbbb",
        "title": "GPU launch party",
        "summary": "keynote",
        "source_url": "https://example.com/launch",
        "source_name": "News",
        "tags": ["产品发布"],
        "item_type": "news",
        "score": 70,
    }
    svc.memory.save_feeds([], [item], intel=[], for_you=[item])
    out = svc.track("bbbbbbbbbbbb", "like")
    assert out["card"]["source_url"].startswith("http")


def test_already_pushed_not_selected_again():
    item = {
        "id": "keep-me",
        "title": "vLLM Agent memory",
        "score": 90,
        "recommend": True,
        "priority": "high",
        "source_url": "https://example.com/x",
    }
    assert pick_push([item], ["keep-me"]) == []


def test_push_threshold_keeps_low_relevance_quiet():
    item = {
        "id": "maybe-later",
        "title": "Some adjacent AI news",
        "score": 79,
        "recommend": True,
        "priority": "normal",
        "source_url": "https://example.com/y",
    }
    assert pick_push([item], [], threshold=85) == []
    assert pick_push([item], [], threshold=75)[0]["id"] == "maybe-later"


def test_push_copy_has_chinese_summary_and_tags():
    text = format_push(
        {
            "title": "Mem0 Temporal Memory",
            "summary_zh": "引入时间衰减，改进记忆排序。",
            "tags": ["长期记忆", "开源发布"],
            "why_you": "和当前 Memory 项目相关",
            "project_value": "可参考时间衰减",
            "score": 94,
            "source_url": "https://example.com/m",
        }
    )
    assert "总结" in text
    assert "长期记忆" in text
    assert "中文" not in text or "引入时间衰减" in text
    assert "https://example.com/m" in text


def test_feishu_sign_matches_official_shape():
    sign = _sign("1599360473", "demo")
    assert sign
    assert "\n" not in sign


def test_feishu_app_message_payload_content_is_json_string():
    payload = _app_message_payload("me@example.com", "你好")
    assert payload["receive_id"] == "me@example.com"
    assert payload["msg_type"] == "text"
    assert payload["content"] == '{"text": "你好"}' or '"你好"' in payload["content"]


def test_mobile_lookup_handles_empty_user_list(monkeypatch):
    def fake_post_json(*args, **kwargs):
        return {"ok": True, "data": {"data": {"user_list": []}}}

    monkeypatch.setattr("radar.feishu._post_json", fake_post_json)
    out = _lookup_open_id_by_mobile("token", "13800138000")
    assert not out["ok"]
    assert "mobile" in out["reason"]


def test_validate_app_config_checks_credentials_and_mobile(monkeypatch):
    monkeypatch.setattr(
        "radar.feishu._tenant_access_token",
        lambda app_id, app_secret: {"ok": True, "tenant_access_token": "token"},
    )
    monkeypatch.setattr(
        "radar.feishu._lookup_open_id_by_mobile",
        lambda token, mobile: {"ok": True, "open_id": "ou_test"},
    )
    from radar.feishu import validate_app_config

    out = validate_app_config(
        {"app_id": "cli_test", "app_secret": "secret", "receive_mobile": "13800138000"}
    )
    assert out["ok"] is True
    assert out["credentials_ok"] is True
    assert out["recipient_ok"] is True


def test_dislike_lowers_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    svc = RadarService(data_dir=tmp_path)
    item = {
        "id": "cccccccccccc",
        "title": "Startup funding round",
        "summary": "raises series B",
        "source_url": "https://example.com/fund",
        "tags": ["融资"],
        "item_type": "news",
    }
    svc.memory.save_feeds([], [item], intel=[], for_you=[item])
    svc.track("cccccccccccc", "dislike")
    topics = {row["topic"]: row["weight"] for row in svc.user_memory.interests()}
    assert topics.get("融资", 1) < 0.5
    assert "融资" in svc.user_memory.behavior()["disliked_topics"]


def test_parse_follow_and_classify():
    from radar.workspace import classify_knowledge, parse_follow_text

    rows = parse_follow_text("最近帮我重点关注 Agent Memory 和 Memory Skill")
    topics = {row["topic"] for row in rows}
    assert "Agent Memory" in topics
    assert "Memory Skill" in topics
    assert classify_knowledge({"title": "Mem0 Temporal Memory"}) == "Agent Memory"


def test_dashboard_follow_and_feedback_note(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_LLM", "0")
    svc = RadarService(data_dir=tmp_path)
    dash = svc.dashboard()
    assert dash["ok"]
    assert "observe" in dash
    assert dash["goals"]
    out = svc.add_follow("最近帮我重点关注 Agent Memory 和 RAG")
    assert out["ok"]
    topics = {row["topic"] for row in svc.user_memory.interests()}
    assert "RAG" in topics
    item = {
        "id": "dddddddddddd",
        "title": "Mem0 Temporal Memory",
        "summary": "long-term memory",
        "source_url": "https://example.com/mem0",
        "tags": ["Agent Memory"],
        "item_type": "blog",
    }
    svc.memory.save_feeds([], [item], intel=[], for_you=[item])
    tracked = svc.track("dddddddddddd", "useful")
    assert "提高" in tracked["note"]
    collected = svc.track("dddddddddddd", "collect")
    assert "Agent Memory" in collected["note"]
    assert collected["card"]["category"] == "Agent Memory"
