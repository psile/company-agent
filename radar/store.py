"""本地画像与成卡。工作 / 兴趣分账。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE = {
    "user_id": "me",
    "work_keywords": ["记忆", "Agent", "vLLM", "RAG", "推理", "LLM"],
    "interest_keywords": ["发布会", "开源", "GPU", "launch", "AI"],
}


class LocalMemory:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path = data_dir / "profile.json"
        self.cards_path = data_dir / "cards.json"
        self.feeds_path = data_dir / "feeds.json"
        self.events_path = data_dir / "events.json"
        self.pushed_path = data_dir / "pushed.json"
        if not self.profile_path.exists():
            self.save_profile(dict(DEFAULT_PROFILE))

    def profile(self) -> dict[str, Any]:
        return json.loads(self.profile_path.read_text(encoding="utf-8"))

    def save_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        merged = dict(DEFAULT_PROFILE)
        merged.update(profile)
        merged["work_keywords"] = _uniq(merged.get("work_keywords", []))
        merged["interest_keywords"] = _uniq(merged.get("interest_keywords", []))
        self.profile_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def cards(self) -> list[dict[str, Any]]:
        if not self.cards_path.exists():
            return []
        return json.loads(self.cards_path.read_text(encoding="utf-8"))

    def add_card(self, card: dict[str, Any]) -> dict[str, Any]:
        if not card.get("source_url"):
            raise ValueError("source_url required")
        rows = self.cards()
        if any(row.get("source_url") == card["source_url"] for row in rows):
            return card
        if not card.get("id"):
            card["id"] = _item_id(card["source_url"])
        rows.insert(0, card)
        self.cards_path.write_text(json.dumps(rows[:200], ensure_ascii=False, indent=2), encoding="utf-8")
        return card

    def update_card(self, key: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        rows = self.cards()
        for index, row in enumerate(rows):
            if row.get("id") == key or row.get("source_url") == key:
                merged = dict(row)
                merged.update(patch)
                rows[index] = merged
                self.cards_path.write_text(json.dumps(rows[:200], ensure_ascii=False, indent=2), encoding="utf-8")
                return merged
        return None

    def save_feeds(self, work: list[dict], personal: list[dict] | None = None, **extra: list[dict]) -> None:
        intel = extra.get("intel", work)
        for_you = extra.get("for_you", personal if personal is not None else work)
        payload = {
            "intel": intel,
            "for_you": for_you,
            "work": intel,
            "personal": for_you,
        }
        self.feeds_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def feeds(self) -> dict[str, list]:
        if not self.feeds_path.exists():
            return {"work": [], "personal": [], "intel": [], "for_you": []}
        data = json.loads(self.feeds_path.read_text(encoding="utf-8"))
        intel = data.get("intel") or data.get("work") or []
        for_you = data.get("for_you") or data.get("personal") or []
        return {"intel": intel, "for_you": for_you, "work": intel, "personal": for_you}

    def find_item(self, item_id: str) -> dict[str, Any] | None:
        feeds = self.feeds()
        for key in ("intel", "for_you", "work", "personal"):
            for row in feeds.get(key, []):
                if row.get("id") == item_id:
                    return row
        for row in self.cards():
            if row.get("id") == item_id or row.get("source_url") and _item_id(row["source_url"]) == item_id:
                return row
        return None

    def add_event(self, event: dict[str, Any]) -> dict[str, Any]:
        rows = self.events()
        rows.insert(0, event)
        self.events_path.write_text(json.dumps(rows[:300], ensure_ascii=False, indent=2), encoding="utf-8")
        return event

    def events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return json.loads(self.events_path.read_text(encoding="utf-8"))

    def pushed_ids(self) -> list[str]:
        if not self.pushed_path.exists():
            return []
        data = json.loads(self.pushed_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
        return [str(x) for x in data.get("ids", [])]

    def mark_pushed(self, item_id: str) -> None:
        ids = self.pushed_ids()
        if item_id not in ids:
            ids.append(item_id)
        self.pushed_path.write_text(
            json.dumps({"ids": ids[-200:]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _uniq(values: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


class ContentPool:
    """全局候选池：采集一次，所有用户从这里取内容再各自排序。"""

    def __init__(self, pool_dir: Path) -> None:
        from .seeds import DEMO_ITEMS

        self.root = pool_dir
        self.items_path = pool_dir / "items.json"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.items_path.exists():
            _write_json(self.items_path, {"items": list(DEMO_ITEMS)})

    def items(self) -> list[dict[str, Any]]:
        return list(_read_json(self.items_path, {"items": []}).get("items") or [])

    def merge(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in self.items():
            if row.get("id"):
                by_id[str(row["id"])] = dict(row)
        for row in rows:
            item_id = str(row.get("id") or "")
            if not item_id:
                continue
            by_id[item_id] = {**by_id.get(item_id, {}), **row}
        items = list(by_id.values())
        _write_json(self.items_path, {"items": items})
        return items

    def find(self, item_id: str) -> dict[str, Any] | None:
        for row in self.items():
            if row.get("id") == item_id or row.get("source_url") == item_id:
                return row
        return None
