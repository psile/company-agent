"""采集 → 理解 → 记忆上下文 → 排序 → 推送 → 反馈写回记忆。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import get_bool, get_int, load_env
from . import ingest, intelligence, recommender
from .feishu import feishu_status, format_push, push_text
from .memory_bridge import remember_fact
from .memory_os import HierarchicalMemory
from .store import LocalMemory
from .user_memory import UserMemory
from .workspace import Workspace, classify_knowledge, parse_follow_text


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "sources.json"
DATA_DIR = ROOT / "data"


class RadarService:
    def __init__(self, data_dir: Path | None = None, sources_path: Path | None = None) -> None:
        load_env()
        root = data_dir or DATA_DIR
        self.memory = LocalMemory(root)
        self.hierarchy = HierarchicalMemory(root, self.memory)
        self.user_memory = UserMemory(root, self.memory)
        self.workspace = Workspace(root)
        self.sources = ingest.load_source_config(sources_path or SOURCES_PATH)

    def status(self) -> dict:
        from . import llm
        feishu = feishu_status()

        return {
            "ok": True,
            "demo": "observe-understand-memory-recommend-feedback",
            "llm": llm.llm_status(),
            "feishu": feishu["ok"],
            "feishu_detail": feishu,
            "feishu_app": feishu["app_bot"],
            "push": {
                "threshold": get_int("RADAR_PUSH_THRESHOLD", 85),
                "limit": get_int("RADAR_PUSH_LIMIT", 2),
                "dry_run": get_bool("RADAR_PUSH_DRY_RUN", False),
            },
            "memory": self._memory_snapshot(),
            "observe": self.workspace.observe(),
            "sources": len(self.sources),
        }

    def refresh(self, auto_push: bool = True) -> dict:
        raw = ingest.fetch_all(self.sources)
        understood = intelligence.understand_all(raw)
        ctx = self.user_memory.context()
        intel = recommender.rank_world(understood)[:10]
        personal = recommender.rank_for_you(understood, ctx)[:10]
        personal = recommender.rerank_with_llm(personal, ctx, self.memory.pushed_ids())
        self.memory.save_feeds(intel, personal, intel=intel, for_you=personal)
        observe = self.workspace.record_observe(len(raw), len(personal), len(self.sources))
        pushed = self._auto_push(personal) if auto_push else []
        return {
            "fetched": len(raw),
            "intel": intel,
            "for_you": personal,
            "work": intel,
            "personal": personal,
            "pushed": pushed,
            "observe": observe,
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def dashboard(self) -> dict:
        feeds = self.memory.feeds()
        for_you = feeds.get("for_you") or []
        intel = feeds.get("intel") or []
        work, personal = _split_channels(for_you)
        cards = [_enrich_card(row) for row in self.memory.cards()]
        observe = dict(self.workspace.observe())
        observe["sources"] = len(self.sources)
        ctx = self.user_memory.context()
        push = self.workspace.push_settings()
        behavior = ctx.get("behavior") or {}
        counts = behavior.get("counts") or {}
        st = self.status()
        return {
            "ok": True,
            "observe": observe,
            "status": {
                "llm": st["llm"],
                "feishu": st["feishu"],
                "feishu_detail": st.get("feishu_detail"),
                "push": st["push"],
            },
            "profile": ctx.get("profile") or {},
            "interests": ctx.get("interests") or [],
            "project": ctx.get("project") or {},
            "behavior": behavior,
            "goals": self.workspace.goals(),
            "products": self.workspace.products(),
            "sources": self.sources,
            "intel": intel,
            "for_you": for_you,
            "work": work,
            "personal": personal,
            "cards": cards,
            "events": self.memory.events()[:30],
            "push_settings": push,
            "weekly_topics": _weekly_topics(for_you, ctx.get("interests") or []),
            "stats": {
                "work": len(work),
                "personal": len(personal),
                "knowledge": len(cards),
                "pending_feedback": max(0, len(for_you) and 2 or 0),
                "likes": int(counts.get("like") or 0),
                "collects": int(counts.get("collect") or 0),
                "feedback": int(counts.get("like") or 0) + int(counts.get("dislike") or 0),
            },
            "brief": _brief_preview(for_you, work, personal, observe, push),
        }

    def add_follow(self, text: str = "", topic: str = "", weight: float = 0.86) -> dict:
        rows = parse_follow_text(text) if (text or "").strip() else []
        if (topic or "").strip():
            rows.append({"topic": topic.strip(), "weight": weight, "source": ["follow"]})
        if not rows:
            return {"ok": False, "reason": "empty", "parsed": []}
        interests = self.user_memory.add_interests(rows)
        note = "已为你创建关注：" + "、".join(row["topic"] for row in rows)
        self.hierarchy.add_memory(user_input=text or topic, agent_response=note, meta={"action": "follow"})
        return {"ok": True, "parsed": rows, "interests": interests, "note": note}

    def move_card(self, key: str, category: str) -> dict:
        card = self.memory.update_card(key, {"category": category, "manual_category": True, "llm_classified": False})
        if not card:
            raise KeyError(key)
        note = f"已记录你的分类偏好，后续将优先按照「{category}」这种方式整理。"
        self.hierarchy.add_memory(
            user_input=f"把《{card.get('title')}》移到 {category}",
            agent_response=note,
            meta={"action": "reclassify", "category": category},
        )
        return {"ok": True, "card": card, "note": note}

    def save_goals(self, items: list[dict]) -> list[dict]:
        return self.workspace.save_goals(items)

    def save_products(self, items: list[dict]) -> list[dict]:
        return self.workspace.save_products(items)

    def save_push_settings(self, payload: dict) -> dict:
        return self.workspace.save_push_settings(payload)

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
            "note": note,
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
        picked = recommender.pick_push(
            candidates,
            self.memory.pushed_ids(),
            limit=get_int("RADAR_PUSH_LIMIT", 2),
            threshold=get_int("RADAR_PUSH_THRESHOLD", 85),
        )
        results = []
        for item in picked:
            pushed = self._push_item(item)
            results.append(pushed)
            if pushed.get("ok"):
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
        category = classify_knowledge(item)
        card = {
            "id": item.get("id"),
            "title": item["title"],
            "summary": item.get("summary_zh") or item.get("summary", ""),
            "source_url": item["source_url"],
            "source_name": item.get("source_name") or "",
            "published_at": item.get("published_at") or "",
            "tags": item.get("tags") or [],
            "why_you": item.get("why_you", ""),
            "useful": True,
            "favorite": True,
            "category": category,
            "llm_classified": True,
            "saved_at": datetime.now(timezone.utc).isoformat(),
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
    tags = " / ".join((item.get("tags") or item.get("matched") or [])[:3]) or "相关主题"
    category = classify_knowledge(item)
    if action in {"like", "useful"}:
        return f"已记录你的偏好，将提高 {tags} 相关内容的推荐权重。"
    if action in {"collect", "star"}:
        return f"已收藏，并由 LLM 归类到「{category}」。"
    if action == "dislike":
        return "后续将减少类似内容。"
    if action in {"skip", "dismiss"}:
        return "已记下，这条不会再出现在为你推荐里。"
    if action == "open":
        return f"已记下你点开了原文，会加强 {tags} 的观察。"
    return f"已记下这次交互（{action}）。"


def _split_channels(items: list[dict]) -> tuple[list[dict], list[dict]]:
    work: list[dict] = []
    personal: list[dict] = []
    for item in items:
        channel = item.get("channel")
        if not channel:
            scores = item.get("scores") or {}
            channel = "work" if float(scores.get("project") or 0) >= 0.5 else "personal"
        (work if channel == "work" else personal).append(item)
    if not work and items:
        return items[: max(1, (len(items) + 1) // 2)], items[max(1, (len(items) + 1) // 2) :]
    return work, personal


def _enrich_card(card: dict) -> dict:
    row = dict(card)
    if not row.get("category"):
        row["category"] = classify_knowledge(row)
        row.setdefault("llm_classified", True)
    return row


def _weekly_topics(items: list[dict], interests: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for item in items:
        for tag in (item.get("tags") or item.get("matched") or [])[:4]:
            counts[str(tag)] = counts.get(str(tag), 0) + 1
    if not counts:
        return [{"topic": row.get("topic"), "count": 0, "weight": row.get("weight")} for row in interests[:6]]
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    return [{"topic": topic, "count": count} for topic, count in ranked]


def _brief_preview(for_you: list[dict], work: list[dict], personal: list[dict], observe: dict, push: dict) -> dict:
    top = (for_you or work or personal)[:3]
    return {
        "when": f"明天 {push.get('morning_time') or '08:30'}",
        "observed": int(observe.get("fetched") or 0),
        "filtered": int(observe.get("filtered") or len(for_you)),
        "work": len(work),
        "personal": len(personal),
        "items": [
            {
                "title": row.get("title"),
                "score": row.get("score"),
                "source_name": row.get("source_name"),
            }
            for row in top
        ],
    }
