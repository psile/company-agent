from __future__ import annotations

from pathlib import Path

import pytest

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def test_user_source_crud_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    row = svc.add_user_source({"name": "My Blog", "url": "https://example.com/feed.xml", "kind": "rss", "type": "blog"}, user_id="alice")
    assert row["id"].startswith("user-")
    assert svc.user_sources("bob") == []
    updated = svc.update_user_source(row["id"], {"name": "Renamed"}, user_id="alice")
    assert updated["name"] == "Renamed"
    with pytest.raises(KeyError):
        svc.update_user_source(row["id"], {"name": "x"}, user_id="bob")
    assert svc.delete_user_source(row["id"], user_id="alice")["ok"]
    assert svc.user_sources("alice") == []


def test_add_user_source_validates(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        svc.add_user_source({"name": "", "url": "https://x"}, user_id="alice")
    with pytest.raises(ValueError):
        svc.add_user_source({"name": "no url"}, user_id="alice")
    svc.add_user_source({"name": "Feed", "url": "https://example.com/rss", "kind": "rss"}, user_id="alice")
    with pytest.raises(ValueError):
        svc.add_user_source({"name": "Dup", "url": "https://example.com/rss", "kind": "rss"}, user_id="alice")


def test_merged_sources_includes_user_specs(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    base = len(svc.merged_sources("alice"))
    svc.add_user_source({"name": "Extra Feed", "url": "https://example.com/rss", "kind": "rss"}, user_id="alice")
    assert len(svc.merged_sources("alice")) == base + 1
    assert len(svc.merged_sources("bob")) == base


def test_follows_overview_briefs(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    overview = svc.follows_overview("alice")
    assert "interests" in overview and "products" in overview and "sources" in overview
    assert isinstance(overview["sources"], list) and overview["sources"]
    custom = svc.add_user_source({"name": "Custom RSS", "url": "https://example.com/rss", "kind": "rss"}, user_id="alice")
    overview = svc.follows_overview("alice")
    row = next(r for r in overview["sources"] if r["id"] == custom["id"])
    assert row["custom"] is True
    assert row["count"] == 0 and row["latest_title"] == ""


def test_interests_edit_roundtrip(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    scope = svc.for_user("alice")
    items = scope.user_memory.interests()
    assert items
    items[0]["weight"] = 0.5
    saved = scope.user_memory.save_interests(items)
    assert any(abs(float(row["weight"]) - 0.5) < 0.01 for row in saved if row["topic"] == items[0]["topic"])
