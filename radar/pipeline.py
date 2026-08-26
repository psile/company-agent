"""采集一次进全局池，再按每个用户的 Memory 排序、推送、写回反馈。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import ingest, intelligence, recommender
from .channels import send_for_user
from .config import get_bool, get_int, get_str, load_env
from .feishu import format_push
from .identity import IdentityService
from .memory_bridge import remember_fact
from .memory_os import HierarchicalMemory
from .notify import NotificationLog
from .seeds import bootstrap_new_user, bootstrap_user_dir, spec_by_id
from .store import ContentPool, LocalMemory, _read_json, _write_json
from .user_memory import UserMemory
from .workspace import Workspace, classify_knowledge, parse_follow_text


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "sources.json"
DATA_DIR = ROOT / "data"


@dataclass
class UserScope:
    user_id: str
    root: Path
    memory: LocalMemory
    user_memory: UserMemory
    workspace: Workspace
    hierarchy: HierarchicalMemory
    notify: NotificationLog


class RadarService:
    def __init__(self, data_dir: Path | None = None, sources_path: Path | None = None) -> None:
        load_env()
        self.root = data_dir or DATA_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = IdentityService(self.root)
        self._ensure_demo()
        self.pool = ContentPool(self.root / "pool")
        self.observe_path = self.root / "pool" / "observe.json"
        self.sources = ingest.load_source_config(sources_path or SOURCES_PATH)
        default = self._scope(self.identity.default_id())
        self.memory = default.memory
        self.user_memory = default.user_memory
        self.workspace = default.workspace
        self.hierarchy = default.hierarchy

    def _ensure_demo(self) -> None:
        from .seeds import DEMO_PASSWORDS, DEMO_USERS

        for spec in DEMO_USERS:
            self.identity.ensure_user(
                spec["id"],
                spec["display_name"],
                spec["identities"],
                username=spec["id"],
                password=DEMO_PASSWORDS.get(spec["id"]),
            )
            bootstrap_user_dir(self.root / "users" / spec["id"], spec)

    def for_user(self, user_id: str | None = None) -> UserScope:
        return self._scope(user_id)

    def _scope(self, user_id: str | None = None) -> UserScope:
        uid = self.identity.require(user_id)
        root = self.root / "users" / uid
        root.mkdir(parents=True, exist_ok=True)
        spec = spec_by_id(uid)
        if spec:
            bootstrap_user_dir(root, spec)
        local = LocalMemory(root)
        local_profile = local.profile()
        if local_profile.get("user_id") != uid:
            local_profile["user_id"] = uid
            local.save_profile(local_profile)
        user_memory = UserMemory(root, local)
        profile = user_memory.profile()
        if profile.get("user_id") != uid:
            identity_row = self.identity.get(uid) or {}
            patch = {"user_id": uid}
            if profile.get("display_name") in {"张伟", "", None}:
                patch["display_name"] = identity_row.get("display_name") or uid
            user_memory.save_profile(patch)
        return UserScope(
            user_id=uid,
            root=root,
            memory=local,
            user_memory=user_memory,
            workspace=Workspace(root, observe_path=self.observe_path),
            hierarchy=HierarchicalMemory(root, local),
            notify=NotificationLog(root),
        )

    def _find_item(self, scope: UserScope, item_id: str) -> dict | None:
        found = scope.memory.find_item(item_id)
        if found:
            return found
        return self.pool.find(item_id)

    def users(self) -> list[dict]:
        from .seeds import spec_by_id as seed_spec

        rows = []
        for row in self.identity.users():
            spec = seed_spec(str(row.get("id") or ""))
            item = self.identity.public_user(str(row.get("id") or "")) or {}
            item["label"] = (spec or {}).get("label") or item.get("display_name")
            rows.append(item)
        return rows

    def register_account(self, username: str, password: str, display_name: str = "") -> dict:
        user = self.identity.register(username, password, display_name)
        uid = str(user["id"])
        bootstrap_new_user(self.root / "users" / uid, uid, str(user.get("display_name") or uid))
        self._scope(uid)
        session = self.identity.login(username, password)
        return session

    def login(self, username: str, password: str) -> dict:
        return self.identity.login(username, password)

    def logout(self, token: str) -> None:
        self.identity.logout(token)

    def session_user(self, token: str) -> dict | None:
        uid = self.identity.user_id_for_session(token)
        if not uid:
            return None
        return self.account(uid)

    def account(self, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        user = self.identity.public_user(uid) or {"id": uid}
        return {
            "ok": True,
            "user": user,
            "feishu": self.feishu_settings(uid),
        }

    def feishu_settings(self, user_id: str | None = None) -> dict:
        raw = self._feishu_raw(user_id)
        secret = str(raw.get("app_secret") or "")
        webhook_secret = str(raw.get("webhook_secret") or "")
        return {
            "app_id": raw.get("app_id") or "",
            "app_secret_set": bool(secret),
            "receive_id_type": raw.get("receive_id_type") or "email",
            "receive_id": raw.get("receive_id") or "",
            "receive_mobile": raw.get("receive_mobile") or "",
            "webhook_url": raw.get("webhook_url") or "",
            "webhook_secret_set": bool(webhook_secret),
            "ready": bool(raw.get("app_id") and secret and (raw.get("receive_id") or raw.get("receive_mobile"))),
        }

    def save_feishu_settings(self, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        current = self._feishu_raw(uid)
        merged = dict(current)
        for key in ("app_id", "receive_id_type", "receive_id", "receive_mobile", "webhook_url"):
            if key in payload:
                merged[key] = str(payload.get(key) or "").strip()
        secret = str(payload.get("app_secret") or "").strip()
        if secret and secret not in {"********", "••••••••"}:
            merged["app_secret"] = secret
        webhook_secret = str(payload.get("webhook_secret") or "").strip()
        if webhook_secret and webhook_secret not in {"********", "••••••••"}:
            merged["webhook_secret"] = webhook_secret
        _write_json(self.root / "users" / uid / "feishu.json", merged)
        if merged.get("receive_id"):
            try:
                self.identity._add_identity(uid, "feishu", merged["receive_id"])
                if not any(
                    row.get("user_id") == uid and row.get("channel_type") == "feishu"
                    for row in self.identity.channels()
                ):
                    self.identity._add_channel(uid, "feishu", merged["receive_id"])
            except ValueError:
                pass
        return self.feishu_settings(uid)

    def change_password(self, user_id: str, old_password: str, new_password: str) -> dict:
        return self.identity.change_password(user_id, old_password, new_password)

    def _feishu_raw(self, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        path = self.root / "users" / uid / "feishu.json"
        data = _read_json(path, {})
        return data if isinstance(data, dict) else {}

    def status(self, user_id: str | None = None) -> dict:
        from . import llm

        scope = self._scope(user_id)
        feishu = self.feishu_settings(scope.user_id)
        return {
            "ok": True,
            "demo": "observe-understand-memory-recommend-feedback",
            "current_user": scope.user_id,
            "llm": llm.llm_status(),
            "feishu": bool(feishu.get("ready")),
            "feishu_detail": {"ok": feishu.get("ready"), "channel": "account" if feishu.get("ready") else "inbox"},
            "feishu_app": bool(feishu.get("app_id")),
            "feishu_mode": get_str("FEISHU_MODE", "mock"),
            "push": {
                "threshold": get_int("RADAR_PUSH_THRESHOLD", 85),
                "limit": get_int("RADAR_PUSH_LIMIT", 2),
                "dry_run": get_bool("RADAR_PUSH_DRY_RUN", False),
            },
            "memory": self._memory_snapshot(scope.user_id),
            "observe": scope.workspace.observe(),
            "sources": len(self.sources),
        }

    def refresh(self, auto_push: bool = True, user_id: str | None = None) -> dict:
        raw = ingest.fetch_all(self.sources)
        understood = intelligence.understand_all(raw)
        if understood:
            self.pool.merge(understood)
        items = self.pool.items()
        intel = recommender.rank_world(items)[:10]
        targets = [self.identity.require(user_id)] if user_id else self.identity.active_ids()
        recs: dict[str, dict] = {}
        pushed: list[dict] = []
        for uid in targets:
            rec = self.recommend_for(uid, auto_push=auto_push, items=items, intel=intel)
            recs[uid] = rec
            pushed.extend(rec.get("pushed") or [])
        default = recs.get(self.identity.default_id()) or (next(iter(recs.values())) if recs else {})
        observe = self._scope(self.identity.default_id()).workspace.record_observe(
            len(raw),
            len(default.get("for_you") or []),
            len(self.sources),
        )
        return {
            "fetched": len(raw),
            "intel": default.get("intel") or intel,
            "for_you": default.get("for_you") or [],
            "work": default.get("intel") or intel,
            "personal": default.get("for_you") or [],
            "pushed": pushed,
            "by_user": recs,
            "observe": observe,
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def recommend_for(
        self,
        user_id: str | None = None,
        auto_push: bool = True,
        items: list[dict] | None = None,
        intel: list[dict] | None = None,
    ) -> dict:
        scope = self._scope(user_id)
        pool_items = items if items is not None else self.pool.items()
        ctx = scope.user_memory.context()
        intel_rows = intel if intel is not None else recommender.rank_world(pool_items)[:10]
        personal = recommender.rank_for_you(pool_items, ctx)[:10]
        personal = recommender.rerank_with_llm(personal, ctx, scope.memory.pushed_ids())
        scope.memory.save_feeds(intel_rows, personal, intel=intel_rows, for_you=personal)
        pushed = self._auto_push(scope, personal) if auto_push else []
        return {
            "user_id": scope.user_id,
            "intel": intel_rows,
            "for_you": personal,
            "pushed": pushed,
        }

    def dashboard(self, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        feeds = scope.memory.feeds()
        if not (feeds.get("for_you") or []) and self.pool.items():
            self.recommend_for(scope.user_id, auto_push=True)
            feeds = scope.memory.feeds()
        for_you = feeds.get("for_you") or []
        intel = feeds.get("intel") or []
        work, personal = _split_channels(for_you)
        cards = [_enrich_card(row) for row in scope.memory.cards()]
        observe = dict(scope.workspace.observe())
        observe["sources"] = len(self.sources)
        ctx = scope.user_memory.context()
        push = scope.workspace.push_settings()
        behavior = ctx.get("behavior") or {}
        counts = behavior.get("counts") or {}
        st = self.status(scope.user_id)
        return {
            "ok": True,
            "current_user": scope.user_id,
            "account": self.account(scope.user_id),
            "notifications": scope.notify.list(),
            "observe": observe,
            "status": {
                "llm": st["llm"],
                "feishu": st["feishu"],
                "feishu_detail": st.get("feishu_detail"),
                "feishu_mode": st.get("feishu_mode"),
                "push": st["push"],
            },
            "profile": ctx.get("profile") or {},
            "interests": ctx.get("interests") or [],
            "project": ctx.get("project") or {},
            "behavior": behavior,
            "goals": scope.workspace.goals(),
            "products": scope.workspace.products(),
            "sources": self.sources,
            "intel": intel,
            "for_you": for_you,
            "work": work,
            "personal": personal,
            "cards": cards,
            "events": scope.memory.events()[:30],
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

    def add_follow(self, text: str = "", topic: str = "", weight: float = 0.86, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        rows = parse_follow_text(text) if (text or "").strip() else []
        if (topic or "").strip():
            rows.append({"topic": topic.strip(), "weight": weight, "source": ["follow"]})
        if not rows:
            return {"ok": False, "reason": "empty", "parsed": []}
        interests = scope.user_memory.add_interests(rows)
        note = "已为你创建关注：" + "、".join(row["topic"] for row in rows)
        scope.hierarchy.add_memory(user_input=text or topic, agent_response=note, meta={"action": "follow"})
        return {"ok": True, "parsed": rows, "interests": interests, "note": note, "user_id": scope.user_id}

    def move_card(self, key: str, category: str, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        card = scope.memory.update_card(key, {"category": category, "manual_category": True, "llm_classified": False})
        if not card:
            raise KeyError(key)
        note = f"已记录你的分类偏好，后续将优先按照「{category}」这种方式整理。"
        scope.hierarchy.add_memory(
            user_input=f"把《{card.get('title')}》移到 {category}",
            agent_response=note,
            meta={"action": "reclassify", "category": category},
        )
        return {"ok": True, "card": card, "note": note}

    def save_goals(self, items: list[dict], user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).workspace.save_goals(items)

    def save_products(self, items: list[dict], user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).workspace.save_products(items)

    def save_push_settings(self, payload: dict, user_id: str | None = None) -> dict:
        return self._scope(user_id).workspace.save_push_settings(payload)

    def track(self, item_id: str, action: str, dwell_ms: int = 0, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        item = self._find_item(scope, item_id)
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
        scope.memory.add_event(event)
        ctx = scope.user_memory.apply_feedback(action, item)
        if action == "dwell":
            return {"ok": True, "action": action, "memory": ctx, "user_id": scope.user_id}
        note = _feedback_note(action, item)
        mem = scope.hierarchy.add_memory(
            user_input=f"我{action}了《{item.get('title')}》 {item.get('source_url')}",
            agent_response=note,
            meta={"action": action, "id": item_id, "promote": action in {"like", "useful", "collect", "star"}},
        )
        remote = remember_fact(
            scope.user_memory.profile().get("user_id") or scope.user_id,
            f"用户{action}了 {item.get('title')} {item.get('source_url')}",
        )
        card = None
        if action in {"like", "useful", "collect", "star"}:
            card = self._file_card(scope, item)
        if action == "dislike":
            self._hide_from(scope, "for_you", item_id)
        if action in {"skip", "dismiss"}:
            self._hide_from(scope, "for_you", item_id)
        return {
            "ok": True,
            "action": action,
            "user_id": scope.user_id,
            "profile": scope.memory.profile(),
            "user_memory": ctx,
            "memory": mem,
            "vehiclemem": remote,
            "card": card,
            "note": note,
        }

    def feedback(self, item_id: str, channel: str, action: str, user_id: str | None = None) -> dict:
        mapped = {"useful": "like", "dismiss": "skip"}.get(action, action)
        return self.track(item_id, mapped, user_id=user_id)

    def push_top_work(self, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        feed = scope.memory.feeds().get("for_you") or scope.memory.feeds().get("intel") or []
        if not feed:
            return {"ok": False, "reason": "empty feed", "user_id": scope.user_id}
        return self._push_item(scope, feed[0])

    def _auto_push(self, scope: UserScope, candidates: list[dict]) -> list[dict]:
        picked = recommender.pick_push(
            candidates,
            scope.memory.pushed_ids(),
            limit=get_int("RADAR_PUSH_LIMIT", 2),
            threshold=get_int("RADAR_PUSH_THRESHOLD", 85),
        )
        results = []
        for item in picked:
            pushed = self._push_item(scope, item)
            results.append(pushed)
            if pushed.get("ok"):
                scope.memory.mark_pushed(item["id"])
                scope.hierarchy.add_memory(
                    user_input=f"系统准备把《{item.get('title')}》推到飞书",
                    agent_response=item.get("why_you") or item.get("summary_zh") or "",
                    meta={"action": "push", "id": item.get("id")},
                )
        return results

    def _push_item(self, scope: UserScope, item: dict) -> dict:
        text = format_push(item)
        result = send_for_user(
            scope.user_id,
            scope.notify,
            {
                **item,
                "text": text,
                "type": "high_relevance",
                "content": item.get("summary_zh") or item.get("summary") or "",
            },
            feishu_cfg=self._feishu_raw(scope.user_id),
        )
        result["id"] = item.get("id")
        result["title"] = item.get("title")
        result["summary_zh"] = item.get("summary_zh")
        result["tags"] = item.get("tags") or []
        return result

    def _file_card(self, scope: UserScope, item: dict) -> dict:
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
        scope.memory.add_card(card)
        return card

    def _hide_from(self, scope: UserScope, key: str, item_id: str) -> None:
        feeds = scope.memory.feeds()
        feeds[key] = [row for row in feeds.get(key, []) if row.get("id") != item_id]
        scope.memory.save_feeds(
            feeds.get("intel", []),
            feeds.get("for_you", []),
            intel=feeds.get("intel", []),
            for_you=feeds.get("for_you", []),
        )

    def _memory_snapshot(self, user_id: str | None = None) -> dict:
        scope = self._scope(user_id)
        snap = scope.hierarchy.snapshot()
        snap["user"] = scope.user_memory.snapshot()
        snap["user_id"] = scope.user_id
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
