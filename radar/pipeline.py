"""采集一次进全局池，再按每个用户的 Memory 排序、推送、写回反馈。"""

from __future__ import annotations

import os

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ingest, intelligence, recommender
from .channels import send_for_user
from .config import get_bool, get_int, get_str, load_env
from .conversation import ConversationService
from .feishu import format_push, validate_app_config
from .identity import IdentityService, hash_password
from .memory_bridge import remember_fact
from .memory_os import HierarchicalMemory
from .notify import NotificationLog
from .proactive import decide_proactive_notification
from .seeds import bootstrap_new_user, bootstrap_user_dir, spec_by_id
from .store import ContentPool, LocalMemory, _read_json, _write_json, is_publishable_item
from .user_memory import UserMemory
from .work_memory import WorkMemory
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
    work: WorkMemory


class RadarService:
    def __init__(self, data_dir: Path | None = None, sources_path: Path | None = None) -> None:
        load_env()
        self.root = data_dir or DATA_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        from . import llm

        llm.set_data_dir(self.root)
        self._seed_demo = os.environ.get("DEV_SEED", "1") != "0"
        self.identity = IdentityService(self.root)
        # 初始化核心服务层（数据存到 users/ 下）
        from .core.services import TaskService, WorkEventService, WorkNoteService, ReminderService

        self.tasks_service = TaskService(self.root / "users")
        self.work_events_service = WorkEventService(self.root / "users")
        self.work_notes_service = WorkNoteService(self.root / "users")
        self.reminders_service = ReminderService(self.root / "users")
        if self._seed_demo:
            self._ensure_demo()
        self._ensure_admin()  # 无 admin 时始终创建（演示账号无 admin 角色）
        self.pool = ContentPool(self.root / "pool")
        self._purge_placeholder_content(self.pool.rejected_ids)
        self.observe_path = self.root / "pool" / "observe.json"
        self.sources = ingest.load_source_config(sources_path or SOURCES_PATH)
        default = self._scope(self.identity.default_id())
        self.memory = default.memory
        self.user_memory = default.user_memory
        self.workspace = default.workspace
        self.hierarchy = default.hierarchy
        self.conversation = ConversationService(self, self.root)

    def _ensure_demo(self) -> None:
        from .seeds import DEMO_PASSWORDS, DEMO_USERS, bootstrap_core_data

        for spec in DEMO_USERS:
            self.identity.ensure_user(
                spec["id"],
                spec["display_name"],
                spec["identities"],
                username=spec["id"],
                password=DEMO_PASSWORDS.get(spec["id"]),
            )
            user_root = self.root / "users" / spec["id"]
            bootstrap_user_dir(user_root, spec)
            bootstrap_core_data(
                self.tasks_service,
                self.work_notes_service,
                self.work_events_service,
                user_root,
                spec["id"],
            )

    def _ensure_admin(self) -> None:
        """首次启动且无 admin 时创建初始 admin（INITIAL_ADMIN_USERNAME/PASSWORD）。"""
        if any(row.get("role") == "admin" for row in self.identity.users()):
            return
        username = os.environ.get("INITIAL_ADMIN_USERNAME", "admin")
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
        if not password:
            import secrets

            password = secrets.token_urlsafe(12)
            print(f"[radar] generated admin password: {password} (shown once, please change it)")
        self.identity.create_user(username, "管理员", password, role="admin")
        print(f"[radar] initial admin created: {username}")

    # ── Admin 用户管理 ──

    def admin_create_user(self, username: str, display_name: str, password: str, email: str = "") -> dict[str, Any]:
        from .identity import _public_user

        user = self.identity.create_user(username, display_name, password, role="user", email=email)
        self._scope(str(user["id"]))  # 初始化用户目录
        return _public_user(user)

    def admin_reset_password(self, user_id: str, new_password: str) -> dict[str, Any]:
        user = self.identity.get(user_id)
        if not user:
            raise KeyError(user_id)
        if len(new_password or "") < 6:
            raise ValueError("密码至少 6 位")
        self.identity._patch_user(
            user_id,
            {
                "password_hash": hash_password(new_password),
                "must_change_password": True,
            },
        )
        return {"ok": True}

    def admin_disable_user(self, user_id: str) -> dict[str, Any]:
        self.identity.disable_user(user_id)
        return {"ok": True}

    def admin_enable_user(self, user_id: str) -> dict[str, Any]:
        self.identity.enable_user(user_id)
        return {"ok": True}

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
            work=WorkMemory(
                root, uid,
                tasks_service=self.tasks_service,
                events_service=self.work_events_service,
                notes_service=self.work_notes_service,
                reminders_service=self.reminders_service,
            ),
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

    async def chat(self, message: str, session_id: str | None = None, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        return await self.conversation.chat(uid, message, session_id)

    def conversations(self, user_id: str | None = None) -> list[dict]:
        return self.conversation.sessions(self.identity.require(user_id))

    def conversation_detail(self, session_id: str, user_id: str | None = None) -> dict:
        return self.conversation.detail(self.identity.require(user_id), session_id)

    def conversation_profile(self, user_id: str | None = None):
        return self.conversation.profile(self.identity.require(user_id))

    def save_conversation_profile(self, payload: dict, user_id: str | None = None) -> dict:
        return self.conversation_profile(user_id).update(payload)

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
            "verification_status": raw.get("verification_status") or "unverified",
            "verification_message": raw.get("verification_message") or "尚未验证飞书凭证",
            "verified_at": raw.get("verified_at") or "",
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
        verification = validate_app_config(merged)
        merged["verification_status"] = "verified" if verification.get("ok") else "failed"
        merged["verification_message"] = str(verification.get("reason") or "验证失败")
        merged["verified_at"] = datetime.now(timezone.utc).isoformat()
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

    def llm_settings(self) -> dict:
        from . import llm

        llm.set_data_dir(self.root)
        return llm.public_llm_settings()

    def recall_memory(self, query: str, user_id: str | None = None, limit: int = 8) -> list[dict]:
        from .retrieve import public_hits, retrieve

        return public_hits(retrieve(self._scope(user_id), query, limit=limit))

    def save_llm_settings(self, payload: dict | None = None) -> dict:
        from . import llm

        llm.set_data_dir(self.root)
        return llm.save_llm_settings(payload or {})

    def test_llm_connection(self) -> dict:
        from . import llm

        llm.set_data_dir(self.root)
        return llm.test_llm_connection()

    def zhihu_settings(self, user_id: str | None = None) -> dict:
        from . import settings_zhihu as mod

        uid = self.identity.require(user_id)
        return mod.public_zhihu_settings(uid)

    def save_zhihu_settings(self, payload: dict | None = None, user_id: str | None = None) -> dict:
        from . import settings_zhihu as mod

        uid = self.identity.require(user_id)
        return mod.save_zhihu_settings(uid, payload)

    def test_zhihu_connection(self, user_id: str | None = None) -> dict:
        from . import settings_zhihu as mod

        uid = self.identity.require(user_id)
        return mod.test_zhihu_connection(uid)

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
                "threshold": get_int("RADAR_PUSH_THRESHOLD", 78),
                "limit": get_int("RADAR_PUSH_LIMIT", 3),
                "dry_run": get_bool("RADAR_PUSH_DRY_RUN", False),
            },
            "memory": self._memory_snapshot(scope.user_id),
            "observe": scope.workspace.observe(),
            "sources": len(self.sources),
        }

    def refresh(self, auto_push: bool = True, user_id: str | None = None) -> dict:
        # 采集全局源 + 各用户的自定义源
        all_specs = list(self.sources)
        for uid in self.identity.active_ids():
            all_specs.extend(self._scope(uid).workspace.user_sources())
        raw = ingest.fetch_all(all_specs)
        understood = intelligence.understand_all(raw)
        if understood:
            self.pool.merge(understood)
        items = self.pool.items()
        intel = recommender.rank_world(items)[:18]
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
        pool_items = [
            intelligence.ensure_rich_summary(row)
            for row in (items if items is not None else self.pool.items())
            if self.pool.allow_demo or is_publishable_item(row)
        ]
        ctx = scope.user_memory.context()
        feed_limit = get_int("RADAR_FEED_LIMIT", 30)
        intel_rows = intel if intel is not None else recommender.rank_world(pool_items)[:feed_limit]
        ranked = recommender.rank_for_you(pool_items, ctx)
        personal = recommender.rerank_with_llm(ranked[: max(24, feed_limit * 2)], ctx, scope.memory.pushed_ids())
        personal = recommender.diversify_feed(
            personal,
            limit=feed_limit,
            work_ratio=int(scope.workspace.push_settings().get("work_personal_ratio") or 55),
        )
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
        events = scope.memory.events()
        feedback_actions = {"like", "useful", "collect", "star", "dislike", "skip", "dismiss"}
        handled_ids = {row.get("id") for row in events if row.get("action") in feedback_actions}
        pending_feedback = [row for row in for_you if row.get("id") not in handled_ids]
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
            "llm_settings": self.llm_settings(),
            "zhihu_settings": self.zhihu_settings(scope.user_id),
            "profile": ctx.get("profile") or {},
            "interests": ctx.get("interests") or [],
            "project": ctx.get("project") or {},
            "behavior": behavior,
            "goals": scope.workspace.goals(),
            "work_memory": scope.work.snapshot(),
            "products": scope.workspace.products(),
            "sources": self.sources,
            "intel": intel,
            "for_you": for_you,
            "work": work,
            "personal": personal,
            "pending_feedback": pending_feedback,
            "cards": cards,
            "events": events[:30],
            "push_settings": push,
            "weekly_topics": _weekly_topics(for_you, ctx.get("interests") or []),
            "stats": {
                "work": len(work),
                "personal": len(personal),
                "knowledge": len(cards),
                "pending_feedback": len(pending_feedback),
                "likes": int(counts.get("like") or 0),
                "collects": int(counts.get("collect") or 0),
                "feedback": int(counts.get("like") or 0) + int(counts.get("dislike") or 0),
            },
            "brief": _brief_preview(for_you, work, personal, observe, push),
            "tracker": self.project_tracker(scope.user_id),
            "project_trackers": self.list_project_trackers(scope.user_id),
            "skills": self.list_office_skills(),
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

    def add_goal(self, payload: dict, user_id: str | None = None) -> dict:
        title = str(payload.get("title") or "").strip()[:120]
        kind = str(payload.get("kind") or "today").strip()
        priority = str(payload.get("priority") or "medium").strip().lower()
        if not title:
            raise ValueError("title required")
        return self._scope(user_id).workspace.add_goal(title, kind=kind, priority=priority)

    def update_goal(self, goal_id: str, patch: dict, user_id: str | None = None) -> dict:
        row = self._scope(user_id).workspace.update_goal(goal_id, patch or {})
        if not row:
            raise KeyError(goal_id)
        return row

    def delete_goal(self, goal_id: str, user_id: str | None = None) -> dict:
        ok = self._scope(user_id).workspace.delete_goal(goal_id)
        if not ok:
            raise KeyError(goal_id)
        return {"ok": True, "id": goal_id}

    def work_snapshot(self, user_id: str | None = None) -> dict:
        return self._scope(user_id).work.snapshot()

    def list_tasks(self, user_id: str | None = None, include_done: bool = True) -> list[dict]:
        return self._scope(user_id).work.tasks(include_done=include_done)

    def create_task(self, payload: dict, user_id: str | None = None) -> dict:
        from .reminders.service import schedule_task_reminders

        uid = self.identity.require(user_id)
        data = dict(payload or {})
        data.pop("user_id", None)
        row = self._scope(uid).work.create_task(data)
        # 自动关联匹配的 Goal
        row = self._auto_assign_goal(uid, row) or row
        schedule_task_reminders(self, uid, row)
        return row

    def update_task(self, task_id: str, payload: dict, user_id: str | None = None) -> dict:
        from .reminders.service import on_task_updated

        uid = self.identity.require(user_id)
        data = dict(payload or {})
        data.pop("user_id", None)
        row = self._scope(uid).work.update_task(task_id, data)
        # 更新完成状态时同步关联 Goal 的 linked/progress
        if "status" in data and str(data["status"]).lower() == "done":
            self._update_goal_linked(uid, row.get("goal_id") or "")
        on_task_updated(self, uid, row, data)
        return row

    @staticmethod
    def _match_keywords(title: str, goals: list[dict]) -> list[dict]:
        import re

        needle = (title or "").strip().lower()
        if not needle:
            return []

        def grams(text: str) -> set[str]:
            return {text[i:i + 2] for i in range(len(text) - 1)} if len(text) >= 2 else {text}

        def ascii_words(text: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]{2,}", text))

        needle_grams = grams(needle)
        needle_words = ascii_words(needle)
        scored = []
        for g in goals:
            goal_text = str(g.get("title") or "").strip().lower()
            if not goal_text:
                continue
            goal_grams = grams(goal_text)
            goal_words = ascii_words(goal_text)
            # 直接包含给最高分
            if needle in goal_text or goal_text in needle:
                scored.append((1.0, g))
                continue
            # ASCII 词级命中率（英文关键词如 VLM/Mem0）
            word_score = 0.0
            if needle_words:
                word_score = len(needle_words & goal_words) / len(needle_words)
            # CJK bigram 覆盖率（相对任务标题）
            gram_score = len(needle_grams & goal_grams) / max(len(needle_grams), 1)
            overlap = max(word_score, gram_score)
            if overlap >= 0.3:
                scored.append((overlap, g))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [g for _, g in scored[:1]]

    def _auto_assign_goal(self, user_id: str, task: dict) -> dict | None:
        """创建任务时自动匹配最相关的 Goal，更新 goal 关联计数并回写 task.goal_id，返回更新后的 task"""
        if task.get("goal_id"):
            return None  # 已指定则不覆盖
        scope = self._scope(user_id)
        goals = scope.workspace.goals()
        open_goals = [g for g in goals if not g.get("done")]
        if not open_goals:
            return None
        matches = self._match_keywords(task.get("title") or "", open_goals)
        if not matches:
            return None
        goal = matches[0]
        updated = dict(task)
        try:
            # goal → task 关联：更新 goal 的 linked 计数
            items = scope.workspace.goals()
            for index, item in enumerate(items):
                if item.get("id") != goal["id"]:
                    continue
                merged = dict(item)
                merged["linked"] = (merged.get("linked") or 0) + 1
                items[index] = merged
                scope.workspace.save_goals(items)
                break
            # task → goal 回写
            updated = scope.work.update_task(task["id"], {"goal_id": goal["id"]})
        except Exception:
            pass  # 静默失败
        return updated

    def _update_goal_linked(self, user_id: str, goal_id: str) -> None:
        """任务完成后，目标 linked +1，progress 按比例提升"""
        if not goal_id:
            return
        scope = self._scope(user_id)
        try:
            items = scope.workspace.goals()
            for index, item in enumerate(items):
                if item.get("id") != goal_id:
                    continue
                merged = dict(item)
                merged["linked"] = (merged.get("linked") or 0) + 1
                progress = merged.get("progress") or 0
                merged["progress"] = min(100, progress + 5)
                items[index] = merged
                scope.workspace.save_goals(items)
                break
        except Exception:
            pass  # 静默失败

    def list_reminders(self, user_id: str | None = None, include_sent: bool = True) -> list[dict]:
        return self._scope(user_id).work.reminders(include_sent=include_sent)

    def create_reminder(self, payload: dict, user_id: str | None = None) -> dict:
        from .reminders.service import create_manual_reminder

        uid = self.identity.require(user_id)
        return create_manual_reminder(self, uid, payload)

    def evaluate_reminders(
        self,
        user_id: str | None = None,
        now=None,
        *,
        deliver: bool = True,
        force_morning: bool = False,
    ) -> list[dict]:
        from .reminders.service import evaluate_all, evaluate_user

        if user_id:
            return evaluate_user(self, user_id, now=now, deliver=deliver, force_morning=force_morning)
        return evaluate_all(self, now=now, deliver=deliver, force_morning=force_morning)

    def list_work_events(self, user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).work.events()

    def list_work_notes(self, user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).work.notes()

    def add_work_note(self, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        data = dict(payload or {})
        data.pop("user_id", None)
        return self._scope(uid).work.add_note(data)

    def list_reports(self, user_id: str | None = None, report_type: str | None = None) -> list[dict]:
        return self._scope(user_id).work.reports(report_type)

    def save_report(self, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        data = dict(payload or {})
        data.pop("user_id", None)
        return self._scope(uid).work.save_report(data)

    def update_report(self, report_id: str, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        data = dict(payload or {})
        data.pop("user_id", None)
        return self._scope(uid).work.update_report(report_id, data)

    def generate_report(
        self,
        report_type: str = "daily",
        user_id: str | None = None,
        *,
        now=None,
        project_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict:
        from .skills.report.service import generate_report as build_report

        uid = self.identity.require(user_id)
        return build_report(
            self,
            uid,
            report_type,
            now=now,
            project_id=project_id,
            start_time=start_time,
            end_time=end_time,
        )

    def project_tracker(self, user_id: str | None = None, project_id: str | None = None) -> dict:
        from .skills.project_tracker.service import project_snapshot

        uid = self.identity.require(user_id)
        project = None
        if project_id:
            project = next(
                (row for row in self._scope(uid).user_memory.projects() if row.get("project_id") == project_id),
                None,
            )
        return project_snapshot(self, uid, project)

    def create_project(self, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        scope = self._scope(uid)
        row = scope.user_memory.create_project(payload or {})
        self._record_project_change(scope, row, "项目已创建")
        return {"project": row, "tracker": self.project_tracker(uid, row["project_id"])}

    def update_project(self, project_id: str, payload: dict, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        scope = self._scope(uid)
        row = scope.user_memory.update_project(project_id, payload or {})
        self._record_project_change(scope, row, "项目已更新")
        return {"project": row, "tracker": self.project_tracker(uid, project_id)}

    def activate_project(self, project_id: str, user_id: str | None = None) -> dict:
        uid = self.identity.require(user_id)
        scope = self._scope(uid)
        row = scope.user_memory.activate_project(project_id)
        self._record_project_change(scope, row, "已切换当前项目")
        return {"project": row, "tracker": self.project_tracker(uid, project_id)}

    @staticmethod
    def _record_project_change(scope: Any, project: dict, content: str) -> None:
        scope.work.add_event(
            {
                "event_type": "project_updated",
                "title": str(project.get("project") or "项目"),
                "content": content,
                "source_type": "manual",
                "source_ref": str(project.get("project_id") or ""),
                "project_id": str(project.get("project_id") or ""),
            }
        )

    def work_summary(self, user_id: str | None = None, range_days: int = 7, now=None) -> dict:
        from .skills.work_summary.service import build_work_summary

        uid = self.identity.require(user_id)
        return build_work_summary(self, uid, range_days=max(1, min(int(range_days or 7), 90)), now=now)

    def work_period_summary(self, kind: str, user_id: str | None = None, project_id: str | None = None) -> dict:
        from .skills.work_summary.service import build_period_overview

        uid = self.identity.require(user_id)
        return build_period_overview(self, uid, kind, project_id=project_id)

    def list_project_trackers(self, user_id: str | None = None) -> dict:
        from .skills.project_tracker.service import list_trackers

        uid = self.identity.require(user_id)
        return list_trackers(self, uid)

    def list_office_skills(self) -> list[dict]:
        from .skills.catalog import list_office_skills

        return list_office_skills()

    def breakdown_task(self, task_id: str | None = None, user_id: str | None = None) -> dict:
        from .skills.task_capture.extractor import breakdown_subtasks

        uid = self.identity.require(user_id)
        work = self._scope(uid).work
        parent = work.get_task(task_id) if task_id else None
        if not parent:
            open_tasks = [row for row in work.tasks(include_done=False) if not row.get("parent_task_id")]
            parent = open_tasks[0] if open_tasks else None
        if not parent:
            raise KeyError("task not found")
        created = []
        for row in breakdown_subtasks(parent.get("title") or ""):
            created.append(
                self.create_task(
                    {
                        **row,
                        "parent_task_id": parent["id"],
                        "project": parent.get("project") or "",
                        "project_id": parent.get("project_id") or "",
                        "source_type": "breakdown",
                        "source_ref": parent["id"],
                    },
                    user_id=uid,
                )
            )
        return {"ok": True, "parent": parent, "items": created}

    def save_products(self, items: list[dict], user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).workspace.save_products(items)

    def user_sources(self, user_id: str | None = None) -> list[dict]:
        return self._scope(user_id).workspace.user_sources()

    def add_user_source(self, payload: dict, user_id: str | None = None) -> dict:
        return self._scope(user_id).workspace.add_user_source(payload or {})

    def update_user_source(self, source_id: str, patch: dict, user_id: str | None = None) -> dict:
        row = self._scope(user_id).workspace.update_user_source(source_id, patch or {})
        if not row:
            raise KeyError(source_id)
        return row

    def delete_user_source(self, source_id: str, user_id: str | None = None) -> dict:
        ok = self._scope(user_id).workspace.delete_user_source(source_id)
        if not ok:
            raise KeyError(source_id)
        return {"ok": True, "id": source_id}

    def merged_sources(self, user_id: str | None = None) -> list[dict]:
        """全局源 + 当前用户自定义源（采集时使用）。"""
        scope = self._scope(user_id)
        rows = list(self.sources)
        for spec in scope.workspace.user_sources():
            merged = dict(spec)
            if merged.get("kind") == "github_releases" and merged.get("repo"):
                merged.setdefault("url", "")
            rows.append(merged)
        return rows

    def follows_overview(self, user_id: str | None = None) -> dict:
        """主题/产品/信息源 + 各自最近动态摘要（来自采集池真实数据）。"""
        from datetime import timedelta

        scope = self._scope(user_id)
        ctx = scope.user_memory.context()
        interests = ctx.get("interests") or []
        products = scope.workspace.products()
        pool = self.pool.items()
        now = datetime.now(timezone.utc)

        def _match(keyword: str) -> list[dict]:
            needle = (keyword or "").strip().lower()
            if not needle:
                return []
            hits = []
            for row in pool:
                blob = " ".join(
                    [
                        str(row.get("title") or ""),
                        str(row.get("summary") or row.get("summary_zh") or ""),
                        " ".join(row.get("tags") or []),
                        " ".join(row.get("keywords") or []),
                        str(row.get("source_name") or ""),
                    ]
                ).lower()
                if needle in blob:
                    hits.append(row)
            hits.sort(key=lambda row: str(row.get("published_at") or ""), reverse=True)
            return hits

        def _brief(keyword: str) -> dict:
            hits = _match(keyword)
            if not hits:
                return {"latest_title": "", "latest_at": "", "count": 0}
            top = hits[0]
            published = str(top.get("published_at") or "")
            days = ""
            if published:
                try:
                    delta = now - datetime.fromisoformat(published.replace("Z", "+00:00"))
                    days = max(0, delta.days)
                except ValueError:
                    days = ""
            return {
                "latest_title": str(top.get("title") or "")[:80],
                "latest_at": published[:10],
                "latest_days_ago": days,
                "count": len(hits),
            }

        interest_rows = [
            {**row, "brief": _brief(str(row.get("topic") or ""))}
            for row in interests
        ]
        product_rows = [
            {**row, "brief": _brief(str(row.get("name") or ""))}
            for row in products
        ]
        source_rows = []
        for spec in self.merged_sources(scope.user_id):
            name = str(spec.get("name") or "")
            hits = [row for row in pool if str(row.get("source_name") or "") == name]
            hits.sort(key=lambda row: str(row.get("published_at") or ""), reverse=True)
            source_rows.append(
                {
                    "id": spec.get("id") or "",
                    "name": name,
                    "kind": spec.get("kind") or "",
                    "type": spec.get("type") or "",
                    "search": spec.get("search") or "",
                    "repo": spec.get("repo") or "",
                    "url": spec.get("url") or "",
                    "credential_env": spec.get("credential_env") or "",
                    "ready": not spec.get("credential_env") or bool(get_str(str(spec.get("credential_env")), "")),
                    "custom": str(spec.get("id") or "").startswith("user-"),
                    "count": len(hits),
                    "latest_title": str(hits[0].get("title") or "")[:80] if hits else "",
                    "latest_at": str(hits[0].get("published_at") or "")[:10] if hits else "",
                }
            )
        focus = sorted(
            [row for row in interest_rows if row["brief"]["count"]],
            key=lambda row: -row["brief"]["count"],
        )
        return {
            "interests": interest_rows,
            "products": product_rows,
            "sources": source_rows,
            "focus": [
                {"topic": row["topic"], "weight": row.get("weight"), "brief": row["brief"]}
                for row in focus[:3]
            ],
        }

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
        settings = scope.workspace.push_settings()
        env_threshold = get_int("RADAR_PUSH_THRESHOLD", 78)
        threshold = (
            max(env_threshold, int(settings.get("high_threshold") or 75))
            if settings.get("high_only")
            else min(env_threshold, int(settings.get("instant_threshold") or 78))
        )
        push_limit = get_int("RADAR_PUSH_LIMIT", 3)
        picked = recommender.pick_push(
            candidates,
            scope.memory.pushed_ids(),
            limit=push_limit,
            threshold=threshold,
        )
        daily_discovery_id = ""
        if not settings.get("high_only") and not _pushed_today(scope.notify.list(), "daily_discovery"):
            already = set(scope.memory.pushed_ids()) | {str(row.get("id") or "") for row in picked}
            wider = next(
                (
                    row for row in candidates
                    if row.get("lane") in {"industry", "discovery"}
                    and row.get("id") not in already
                    and int(row.get("score") or 0) >= 60
                ),
                None,
            )
            if wider:
                picked = (picked[: max(0, push_limit - 1)] + [wider])[:push_limit]
                daily_discovery_id = str(wider.get("id") or "")
        results = []
        for item in picked:
            lane = str(item.get("lane") or "personal")
            scores = item.get("scores") or {}
            candidate = {
                **item,
                "current_goal_match": scores.get("project", 0.35 if lane != "work" else 0.75),
                "source_quality": scores.get("quality", 0.7),
                "user_preference": max(float(scores.get("interest") or 0), float(scores.get("feedback") or 0.65)),
                "interrupt_cost": 0.1 if lane in {"industry", "discovery"} else 0.16,
                "urgency": 0.8 if lane in {"industry", "discovery"} else 0.35,
            }
            decision_settings = dict(settings)
            decision_settings["instant_threshold"] = min(
                float(settings.get("instant_threshold") or 78),
                58 if lane in {"industry", "discovery"} else 72,
            )
            decision = decide_proactive_notification(
                candidate,
                self.conversation_profile(scope.user_id).get(),
                decision_settings,
            )
            if decision.decision != "push_now":
                results.append({"ok": True, "id": item.get("id"), "proactive": decision.to_dict()})
                continue
            push_type = "daily_discovery" if str(item.get("id") or "") == daily_discovery_id else "high_relevance"
            pushed = self._push_item(scope, item, push_type=push_type)
            pushed["proactive"] = decision.to_dict()
            results.append(pushed)
            if pushed.get("ok"):
                scope.memory.mark_pushed(item["id"])
                scope.hierarchy.add_memory(
                    user_input=f"系统准备把《{item.get('title')}》推到飞书",
                    agent_response=item.get("why_you") or item.get("summary_zh") or "",
                    meta={"action": "push", "id": item.get("id"), "lane": lane, "type": push_type},
                )
        return results

    def _push_item(self, scope: UserScope, item: dict, push_type: str = "high_relevance") -> dict:
        if not is_publishable_item(item):
            return {
                "ok": False,
                "id": item.get("id"),
                "title": item.get("title"),
                "reason": "来源链接无效或属于演示占位域名，已阻止推送",
            }
        text = format_push(item)
        result = send_for_user(
            scope.user_id,
            scope.notify,
            {
                **item,
                "text": text,
                "type": push_type,
                "content": item.get("summary_zh") or item.get("summary") or "",
            },
            feishu_cfg=self._feishu_raw(scope.user_id),
            service=self,
        )
        result["id"] = item.get("id")
        result["title"] = item.get("title")
        result["summary_zh"] = item.get("summary_zh")
        result["tags"] = item.get("tags") or []
        return result

    def _purge_placeholder_content(self, rejected_ids: set[str]) -> None:
        if not rejected_ids:
            return
        for uid in self.identity.active_ids():
            root = self.root / "users" / uid
            memory = LocalMemory(root)
            feeds = memory.feeds()
            clean = lambda rows: [row for row in (rows or []) if row.get("id") not in rejected_ids and is_publishable_item(row)]
            memory.save_feeds(clean(feeds.get("intel")), clean(feeds.get("for_you")), intel=clean(feeds.get("intel")), for_you=clean(feeds.get("for_you")))
            for path, container in (
                (root / "pushed.json", "ids"),
                (root / "notifications.json", "items"),
            ):
                payload = _read_json(path, {container: []})
                if container == "ids":
                    payload[container] = [key for key in payload.get(container, []) if key not in rejected_ids]
                else:
                    payload[container] = [
                        row for row in payload.get(container, [])
                        if row.get("recommendation_id") not in rejected_ids
                        and not any(host in str(row.get("content") or "") for host in ("example.com", "example.org", "example.net"))
                    ]
                _write_json(path, payload)
            for path in (root / "cards.json", root / "events.json"):
                rows = _read_json(path, [])
                if isinstance(rows, list):
                    _write_json(path, [row for row in rows if row.get("id") not in rejected_ids and "example.com" not in str(row.get("source_url") or "")])

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


def _pushed_today(notifications: list[dict], push_type: str) -> bool:
    today = datetime.now(timezone.utc).date()
    for row in notifications:
        if row.get("type") != push_type:
            continue
        try:
            if datetime.fromisoformat(str(row.get("created_at") or "")).date() == today:
                return True
        except ValueError:
            continue
    return False


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
