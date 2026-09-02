from pathlib import Path

from radar.feishu import _app_message_payload, _lookup_open_id_by_mobile, _sign, format_push
from radar.ingest import fetch_zhihu_open_search, parse_atom, parse_rss
from radar.intelligence import understand_heuristic
from radar.llm import parse_json_object
from radar.models import RawItem
from radar.pipeline import RadarService
from radar.recommender import diversify_feed, pick_push, rank_for_you
from radar.store import ContentPool, LocalMemory, is_publishable_url
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


def test_placeholder_sources_never_enter_production_pool(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DEMO_CONTENT", "0")
    pool = ContentPool(tmp_path / "pool")
    pool.merge(
        [
            {"id": "fake", "source_url": "https://example.com/made-up", "title": "fake"},
            {"id": "real", "source_url": "https://arxiv.org/abs/2608.26983", "title": "real"},
        ]
    )
    assert [row["id"] for row in pool.items()] == ["real"]
    assert not is_publishable_url("https://example.com/world-model-ad")


def test_authorized_platform_search_keeps_only_expected_domain(monkeypatch):
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", "test-secret")
    monkeypatch.setattr(
        "radar.ingest._get_json",
        lambda *_args, **_kwargs: {
            "Code": 0,
            "Data": {
                "items": [
                    {
                        "Title": "世界模型如何用于自动驾驶",
                        "ContentType": "Article",
                        "ContentID": "123",
                        "ContentText": "真实知乎内容",
                        "Url": "https://www.zhihu.com/question/123",
                        "CommentCount": 15,
                        "VoteUpCount": 128,
                        "AuthorName": "张三",
                        "AuthorBadgeText": "自动驾驶优秀答主",
                        "EditTime": 1710000000,
                        "AuthorityLevel": "2",
                        "RankingScore": 0.98,
                    },
                    {"Title": "不应混入", "Url": "https://untrusted.test/post", "ContentText": "其他站点"},
                ]
            },
        },
    )
    rows = fetch_zhihu_open_search(
        {
            "id": "zhihu-test",
            "name": "知乎测试",
            "kind": "zhihu_search",
            "search": "自动驾驶 世界模型",
            "allowed_hosts": ["zhihu.com"],
            "max": 5,
        }
    )
    assert len(rows) == 1
    assert rows[0].source_url == "https://www.zhihu.com/question/123"
    assert rows[0].summary == "真实知乎内容"
    assert rows[0].metadata["author_name"] == "张三"
    assert rows[0].metadata["vote_up_count"] == 128
    assert rows[0].published_at.startswith("2024-03")


def test_global_search_runs_multiple_queries_and_deduplicates(monkeypatch):
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", "test-secret")
    requested_urls = []

    def fake_get_json(url, _headers):
        requested_urls.append(url)
        query = "自动驾驶" if "%E8%87%AA%E5%8A%A8%E9%A9%BE%E9%A9%B6" in url else "世界模型"
        return {
            "Code": 0,
            "Data": {
                "Items": [
                    {
                        "Title": f"{query}公众号文章",
                        "ContentText": "真实内容摘要",
                        "Url": f"https://mp.weixin.qq.com/s/{'shared' if query == '世界模型' else 'driving'}",
                        "RankingScore": 0.8,
                    },
                    {
                        "Title": "重复文章",
                        "ContentText": "重复内容",
                        "Url": "https://mp.weixin.qq.com/s/shared",
                    },
                ]
            },
        }

    monkeypatch.setattr("radar.ingest._get_json", fake_get_json)
    rows = fetch_zhihu_open_search(
        {
            "id": "wechat-test",
            "name": "微信公众号测试",
            "kind": "global_search",
            "searches": ["自动驾驶", "世界模型"],
            "filter": 'host=="mp.weixin.qq.com"',
            "allowed_hosts": ["mp.weixin.qq.com"],
            "max": 10,
        }
    )
    assert len(requested_urls) == 2
    assert all("Filter=host%3D%3D%22mp.weixin.qq.com%22" in url for url in requested_urls)
    assert len(rows) == 2
    assert {row.source_url for row in rows} == {
        "https://mp.weixin.qq.com/s/driving",
        "https://mp.weixin.qq.com/s/shared",
    }
    assert rows[0].metadata["search_query"] == "自动驾驶"


def test_understanding_fallback_is_rich_enough_to_scan():
    item = understand_heuristic(
        RawItem("news", "Industry News", "industry", "A new AI product ships", "Launch details", "https://x/news", "2026-08-30T00:00:00Z", "news")
    )
    assert len(item["summary_zh"]) > 50
    assert len(item["key_points"]) == 3
    assert item["impact"]
    assert item["what_to_watch"]


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


def test_diversify_feed_reserves_industry_and_discovery():
    rows = []
    for index in range(12):
        rows.append({"id": f"w{index}", "lane": "work", "source_id": "work-source", "score": 99 - index})
    rows.extend(
        [
            {"id": "industry", "lane": "industry", "source_id": "news", "score": 70},
            {"id": "discovery", "lane": "discovery", "source_id": "hn", "score": 66},
            {"id": "personal", "lane": "personal", "source_id": "blog", "score": 65},
        ]
    )
    feed = diversify_feed(rows, limit=10, work_ratio=55)
    assert {row["lane"] for row in feed} >= {"work", "industry", "discovery", "personal"}


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
    assert "引入时间衰减" in text
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


def test_feishu_tenant_token_is_reused(monkeypatch):
    from radar.feishu import _tenant_access_token, reset_token_cache_for_tests

    reset_token_cache_for_tests()
    calls = []

    def fake_post(*_args, **_kwargs):
        calls.append(1)
        return {"ok": True, "data": {"tenant_access_token": "cached-token", "expire": 7200}}

    monkeypatch.setattr("radar.feishu._post_json", fake_post)
    first = _tenant_access_token("cli_cache_test", "secret")
    second = _tenant_access_token("cli_cache_test", "secret")
    assert first["tenant_access_token"] == "cached-token"
    assert second["tenant_access_token"] == "cached-token"
    assert second["cached"] is True
    assert len(calls) == 1


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
    pending = svc.dashboard()
    assert pending["stats"]["pending_feedback"] == 1
    assert [row["id"] for row in pending["pending_feedback"]] == ["dddddddddddd"]
    tracked = svc.track("dddddddddddd", "useful")
    assert "提高" in tracked["note"]
    handled = svc.dashboard()
    assert handled["stats"]["pending_feedback"] == 0
    assert handled["pending_feedback"] == []
    collected = svc.track("dddddddddddd", "collect")
    assert "Agent Memory" in collected["note"]
    assert collected["card"]["category"] == "Agent Memory"
