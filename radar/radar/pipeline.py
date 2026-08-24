"""采集 → 理解 → 记忆上下文 → 排序 → 推送 → 反馈写回记忆。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from . import ingest, intelligence, recommender
from .feishu import format_push, push_text
from .memory_bridge import remember_fact
from .memory_os import HierarchicalMemory
from .store import LocalMemory
from .user_memory import UserMemory


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "sources.json"
DATA_DIR = ROOT / "data"


class RadarService:
    def __init__(self, data_dir: Path | None = None, sources_path: Path | None = None) -> None:
        root = data_dir or DATA_DIR
        self.memory = LocalMemory(root)
        self.hierarchy = HierarchicalMemory(root, self.memory)
        self.user_memory = UserMemory(root, self.memory)
        self.sources = ingest.load_source_config(sources_path or SOURCES_PATH)

    def status(self) -> dict:
        from . import llm

        return {
            "ok": True,
            "demo": "observe-understand-memory-recommend-feedback",
            "llm": llm.llm_status(),
            "feishu": bool((os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()),
            "memory": self._memory_snapshot(),
        }

    def refresh(self, auto_push: bool = True) -> dict:
        raw = ingest.fetch_all(self.sources)
        understood = intelligence.understand_all(raw)
        ctx = self.user_memory.context()
        intel = recommender.rank_world(understood)[:10]
        personal = recommender.rank_for_you(understood, ctx)[:10]
        personal = recommender.rerank_with_llm(personal, ctx, self.memory.pushed_ids())
        self.memory.save_feeds(intel, personal, intel=intel, for_you=personal)
        pushed = self._auto_push(personal) if auto_push else []
        return {
            "fetched": len(raw),
            "intel": intel,
            "for_you": personal,
            "work": intel,
            "personal": personal,
            "pushed": pushed,
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def track(self, item_id: str, action: str, dwell_ms: int = 0) -> dict:
        item = self.memory.find_item(item_id)
        if not item:
            raise KeyError(item_id)
        event = {
            "id": item_id,
            "action": action,
            "dwell_ms": dwell_ms,
            "title": item.get("title"),
            "source_url": item.get("source_url"),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory.add_event(event)
        ctx = self.user_memory.apply_feedback(action, item)
        if action == "dwell":
            return {"ok": True, "action": action, "memory": ctx}
        note = _feedback_note(action, item)
        mem = self.hierarchy.add_memory(
            user_input=f"我{action}了《{item.get('title')}》 {item.get('source_url')}",
            agent_response=note,
            meta={"action": action, "id": item_id, "promote": action in {"like", "useful", "collect", "star"}},
        )
        remote = remember_fact(
            self.memory.profile().get("user_id", "me"),
            f"用户{action}了 {item.get('title')} {item.get('source_url')}",
        )
        card = None
        if action in {"like", "useful", "collect", "star"}:
            card = self._file_card(item)
        if action == "dislike":
            self._hide_from("for_you", item_id)
        if action in {"skip", "dismiss"}:
            self._hide_from("for_you", item_id)
        return {
            "ok": True,
            "action": action,
            "profile": self.memory.profile(),
            "user_memory": ctx,
            "memory": mem,
            "vehiclemem": remote,
            "card": card,
        }

    def feedback(self, item_id: str, channel: str, action: str) -> dict:
        mapped = {"useful": "like", "dismiss": "skip"}.get(action, action)
        return self.track(item_id, mapped)

    def push_top_work(self) -> dict:
        feed = self.memory.feeds().get("for_you") or self.memory.feeds().get("intel") or []
        if not feed:
            return {"ok": False, "reason": "empty feed"}
        return self._push_item(feed[0])

    def _auto_push(self, candidates: list[dict]) -> list[dict]:
        picked = recommender.pick_push(candidates, self.memory.pushed_ids(), limit=2)
        results = []
        for item in picked:
            pushed = self._push_item(item)
            results.append(pushed)
            if pushed.get("ok") or pushed.get("reason") == "FEISHU_WEBHOOK_URL not set":
                self.memory.mark_pushed(item["id"])
                self.hierarchy.add_memory(
                    user_input=f"系统准备把《{item.get('title')}》推到飞书",
                    agent_response=item.get("why_you") or item.get("summary_zh") or "",
                    meta={"action": "push", "id": item.get("id")},
                )
        return results

    def _push_item(self, item: dict) -> dict:
        text = format_push(item)
        result = push_text(text)
        result["id"] = item.get("id")
        result["title"] = item.get("title")
        result["summary_zh"] = item.get("summary_zh")
        result["tags"] = item.get("tags") or []
        return result

    def _file_card(self, item: dict) -> dict:
        card = {
            "title": item["title"],
            "summary": item.get("summary_zh") or item.get("summary", ""),
            "source_url": item["source_url"],
            "tags": item.get("tags") or [],
            "why_you": item.get("why_you", ""),
            "useful": True,
        }
        self.memory.add_card(card)
        return card

    def _hide_from(self, key: str, item_id: str) -> None:
        feeds = self.memory.feeds()
        feeds[key] = [row for row in feeds.get(key, []) if row.get("id") != item_id]
        self.memory.save_feeds(feeds.get("intel", []), feeds.get("for_you", []), intel=feeds.get("intel", []), for_you=feeds.get("for_you", []))

    def _memory_snapshot(self) -> dict:
        snap = self.hierarchy.snapshot()
        snap["user"] = self.user_memory.snapshot()
        return snap


def _feedback_note(action: str, item: dict) -> str:
    tags = " / ".join((item.get("tags") or item.get("matched") or [])[:4])
    if action in {"like", "useful", "collect", "star"}:
        return f"记下有用：{tags or item.get('title')}"
    if action == "dislike":
        return f"记下不感兴趣：{tags or item.get('title')}"
    if action == "open":
        return f"记下点开原文：{tags or item.get('title')}"
    return f"记下交互 {action}"
