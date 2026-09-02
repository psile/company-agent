"""结构化记忆：画像 / 带权兴趣 / 当前项目 / 行为。兴趣必须带权重和时间。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .store import LocalMemory, _read_json, _write_json


DEFAULT_PROFILE = {
    "user_id": "me",
    "display_name": "张伟",
    "role": "AI算法工程师",
    "bio": "关注大模型应用与推荐系统，持续把前沿能力落到个人工作秘书里。",
    "team": "算法平台",
    "timezone": "GMT +8",
    "languages": "中文 / English",
    "joined": "2024-03-18",
    "domains": ["Agent", "Multimodal AI"],
    "preferred_content": ["论文", "技术博客", "开源项目"],
}

DEFAULT_INTERESTS = [
    {"topic": "Agent Memory", "weight": 0.92, "last_active": "", "source": ["seed"]},
    {"topic": "Memory Skill", "weight": 0.86, "last_active": "", "source": ["seed"]},
    {"topic": "Proactive Agent", "weight": 0.84, "last_active": "", "source": ["seed"]},
    {"topic": "Multimodal Agent", "weight": 0.73, "last_active": "", "source": ["seed"]},
    {"topic": "AI Coding", "weight": 0.78, "last_active": "", "source": ["seed"]},
    {"topic": "RAG", "weight": 0.70, "last_active": "", "source": ["seed"]},
    {"topic": "vLLM", "weight": 0.58, "last_active": "", "source": ["seed"]},
    {"topic": "World Model", "weight": 0.42, "last_active": "", "source": ["seed"]},
]

DEFAULT_PROJECT = {
    "project": "Personal Work Secretary Agent",
    "project_id": "personal-work-secretary-agent",
    "summary": "",
    "objective": "",
    "stage": "方案设计 / 技术调研",
    "status": "active",
    "topics": ["Memory", "Personalization", "Proactive Recommendation"],
    "priority": "high",
    "start_date": "",
    "target_date": "",
    "acceptance_criteria": [],
    "milestones": [],
}

DEFAULT_BEHAVIOR = {
    "paper_like_rate": 0.81,
    "github_like_rate": 0.74,
    "financing_news_like_rate": 0.05,
    "preferred_summary_length": "short",
    "disliked_topics": ["融资", "funding", "基础教程", "tutorial for beginners"],
    "source_weights": {},
    "type_weights": {"paper": 0.81, "release": 0.74, "blog": 0.7, "news": 0.35},
    "counts": {"like": 0, "collect": 0, "open": 0, "dislike": 0, "skip": 0},
}


class UserMemory:
    def __init__(self, data_dir: Path, local: LocalMemory) -> None:
        self.local = local
        self.root = data_dir / "memory"
        self.root.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.root / "profile.json"
        self.interest_path = self.root / "interests.json"
        self.project_path = self.root / "project.json"
        self.projects_path = self.root / "projects.json"
        self.behavior_path = self.root / "behavior.json"
        if not self.profile_path.exists():
            _write_json(self.profile_path, dict(DEFAULT_PROFILE))
        if not self.interest_path.exists():
            _write_json(self.interest_path, {"topics": list(DEFAULT_INTERESTS)})
        if not self.project_path.exists():
            _write_json(self.project_path, dict(DEFAULT_PROJECT))
        if not self.behavior_path.exists():
            _write_json(self.behavior_path, dict(DEFAULT_BEHAVIOR))

    def context(self) -> dict[str, Any]:
        profile = self.profile()
        return {
            "user_id": profile.get("user_id") or self.local.profile().get("user_id") or "",
            "profile": profile,
            "interests": self.interests(),
            "project": self.project(),
            "behavior": self.behavior(),
        }

    def profile(self) -> dict[str, Any]:
        merged = dict(DEFAULT_PROFILE)
        raw = _read_json(self.profile_path, {})
        merged.update({key: value for key, value in raw.items() if value not in (None, "")})
        return merged

    def interests(self) -> list[dict[str, Any]]:
        data = _read_json(self.interest_path, {"topics": list(DEFAULT_INTERESTS)})
        rows = data.get("topics") if isinstance(data, dict) else data
        return sorted(list(rows or []), key=lambda row: -float(row.get("weight") or 0))

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(DEFAULT_PROFILE)
        merged.update(self.profile())
        merged.update(payload or {})
        _write_json(self.profile_path, merged)
        return merged

    def add_interests(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _now()
        existing = {str(row.get("topic") or "").lower(): dict(row) for row in self.interests() if row.get("topic")}
        for row in rows:
            topic = str(row.get("topic") or "").strip()
            if not topic:
                continue
            key = topic.lower()
            current = existing.get(key) or {"topic": topic, "weight": 0.4, "source": []}
            weight = max(float(current.get("weight") or 0.4), float(row.get("weight") or 0.8))
            sources = list(current.get("source") or [])
            for src in row.get("source") or ["follow"]:
                if src not in sources:
                    sources.append(src)
            current.update(
                {
                    "topic": topic,
                    "weight": round(min(0.99, weight), 3),
                    "last_active": now,
                    "source": sources[-8:],
                }
            )
            existing[key] = current
        return self.save_interests(list(existing.values()))

    def save_interests(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = sorted(topics, key=lambda row: -float(row.get("weight") or 0))[:40]
        _write_json(self.interest_path, {"topics": ranked})
        self._sync_keyword_ledger()
        return ranked

    def project(self) -> dict[str, Any]:
        data = self._project_collection()
        active_id = str(data.get("active_id") or "")
        rows = list(data.get("items") or [])
        active = next((row for row in rows if row.get("project_id") == active_id), None)
        return dict(active or (rows[0] if rows else DEFAULT_PROJECT))

    def projects(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._project_collection().get("items") or []]

    def save_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.project()
        return self.update_project(str(current.get("project_id") or ""), payload)

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = _normalize_project(payload)
        if not row.get("project"):
            raise ValueError("project required")
        data = self._project_collection()
        items = list(data.get("items") or [])
        existing = {str(item.get("project_id") or "") for item in items}
        base_id = str(row.get("project_id") or _project_slug(row["project"]) or f"project-{uuid4().hex[:8]}")
        project_id = base_id
        suffix = 2
        while project_id in existing:
            project_id = f"{base_id}-{suffix}"
            suffix += 1
        row["project_id"] = project_id
        row["created_at"] = _now()
        row["updated_at"] = row["created_at"]
        items.append(row)
        self._save_projects(items, project_id)
        return row

    def update_project(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._project_collection()
        items = list(data.get("items") or [])
        target_id = project_id or str(data.get("active_id") or "")
        index = next((i for i, row in enumerate(items) if str(row.get("project_id") or "") == target_id), -1)
        if index < 0:
            raise KeyError(target_id)
        merged = dict(items[index])
        merged.update(payload or {})
        merged["project_id"] = target_id
        merged = _normalize_project(merged)
        merged["updated_at"] = _now()
        items[index] = merged
        self._save_projects(items, str(data.get("active_id") or target_id))
        return merged

    def activate_project(self, project_id: str) -> dict[str, Any]:
        data = self._project_collection()
        items = list(data.get("items") or [])
        selected = next((row for row in items if str(row.get("project_id") or "") == project_id), None)
        if not selected:
            raise KeyError(project_id)
        self._save_projects(items, project_id)
        return dict(selected)

    def _project_collection(self) -> dict[str, Any]:
        raw = _read_json(self.projects_path, {})
        if isinstance(raw, dict) and raw.get("items"):
            return raw
        legacy = _read_json(self.project_path, dict(DEFAULT_PROJECT))
        row = _normalize_project(legacy)
        if not row.get("project_id"):
            row["project_id"] = _project_slug(str(row.get("project") or "")) or f"project-{uuid4().hex[:8]}"
        data = {"active_id": row["project_id"], "items": [row]}
        _write_json(self.projects_path, data)
        _write_json(self.project_path, row)
        return data

    def _save_projects(self, items: list[dict[str, Any]], active_id: str) -> None:
        active = next((row for row in items if str(row.get("project_id") or "") == active_id), items[0] if items else {})
        _write_json(self.projects_path, {"active_id": active_id, "items": items})
        if active:
            _write_json(self.project_path, active)

    def behavior(self) -> dict[str, Any]:
        merged = dict(DEFAULT_BEHAVIOR)
        merged.update(_read_json(self.behavior_path, {}))
        return merged

    def save_behavior(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = self.behavior()
        merged.update(payload or {})
        _write_json(self.behavior_path, merged)
        return merged

    def snapshot(self) -> dict[str, Any]:
        return self.context()

    def apply_feedback(self, action: str, item: dict[str, Any]) -> dict[str, Any]:
        delta = {
            "like": 0.06,
            "useful": 0.06,
            "collect": 0.1,
            "star": 0.1,
            "open": 0.05,
            "dwell": 0.02,
            "skip": 0.0,
            "dismiss": 0.0,
            "dislike": -0.12,
        }.get(action, 0.0)
        topics = _topics_from_item(item)
        if delta:
            self._bump_topics(topics, delta, action)
        self._bump_behavior(action, item, delta)
        self._sync_keyword_ledger()
        return self.context()

    def _bump_topics(self, topics: list[str], delta: float, source: str) -> None:
        now = _now()
        rows = {row["topic"].lower(): dict(row) for row in self.interests() if row.get("topic")}
        for topic in topics:
            key = topic.lower()
            row = rows.get(key) or {"topic": topic, "weight": 0.4, "source": []}
            weight = max(0.05, min(0.99, float(row.get("weight") or 0.4) + delta))
            sources = list(row.get("source") or [])
            if source not in sources:
                sources.append(source)
            row.update({"topic": topic, "weight": round(weight, 3), "last_active": now, "source": sources[-8:]})
            rows[key] = row
        ranked = sorted(rows.values(), key=lambda row: -float(row.get("weight") or 0))
        _write_json(self.interest_path, {"topics": ranked[:40]})

    def _bump_behavior(self, action: str, item: dict[str, Any], delta: float) -> None:
        behavior = self.behavior()
        counts = dict(behavior.get("counts") or {})
        mapped = {"useful": "like", "star": "collect", "dismiss": "skip"}.get(action, action)
        counts[mapped] = int(counts.get(mapped) or 0) + 1
        behavior["counts"] = counts
        item_type = item.get("item_type") or item.get("content_type") or "article"
        type_weights = dict(behavior.get("type_weights") or {})
        type_weights[item_type] = round(max(0.05, min(0.99, float(type_weights.get(item_type) or 0.5) + delta)), 3)
        behavior["type_weights"] = type_weights
        source_name = item.get("source_name") or item.get("source") or ""
        if source_name:
            source_weights = dict(behavior.get("source_weights") or {})
            source_weights[source_name] = round(
                max(0.05, min(0.99, float(source_weights.get(source_name) or 0.5) + delta)),
                3,
            )
            behavior["source_weights"] = source_weights
        if action == "dislike":
            disliked = list(behavior.get("disliked_topics") or [])
            for topic in _topics_from_item(item)[:3]:
                if topic not in disliked:
                    disliked.append(topic)
            behavior["disliked_topics"] = disliked[-20:]
        _write_json(self.behavior_path, behavior)

    def _sync_keyword_ledger(self) -> None:
        """旧关键词账本仍给兼容层用：高权兴趣当工作词，其余当发现词。"""
        interests = self.interests()
        work = [row["topic"] for row in interests if float(row.get("weight") or 0) >= 0.7][:12]
        rest = [row["topic"] for row in interests if row["topic"] not in work][:12]
        profile = self.local.profile()
        profile["work_keywords"] = work or profile.get("work_keywords", [])
        profile["interest_keywords"] = rest or profile.get("interest_keywords", [])
        self.local.save_profile(profile)


def _topics_from_item(item: dict[str, Any]) -> list[str]:
    bag: list[str] = []
    for key in ("tags", "keywords", "matched", "domain"):
        for value in item.get(key) or []:
            text = str(value).strip()
            if text:
                bag.append(text)
    title = str(item.get("title") or "")
    for token in (
        "Memory",
        "Agent",
        "vLLM",
        "RAG",
        "LLM",
        "Skill",
        "Mem0",
        "World Model",
        "VLM",
        "Driving",
        "Cockpit",
        "Occupancy",
    ):
        if token.lower() in title.lower():
            bag.append(token)
    seen: set[str] = set()
    out: list[str] = []
    for topic in bag:
        low = topic.lower()
        if low not in seen:
            seen.add(low)
            out.append(topic)
    return out[:8]


def _project_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:64]


def _normalize_project(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(payload or {})
    topics = raw.get("topics") or []
    if isinstance(topics, str):
        topics = [part.strip() for part in re.split(r"[,，、\n]+", topics) if part.strip()]
    criteria = []
    for index, item in enumerate(raw.get("acceptance_criteria") or []):
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("title") or "").strip()
            done = bool(item.get("done"))
            item_id = str(item.get("id") or f"accept-{index + 1}")
        else:
            text = str(item or "").strip()
            done = False
            item_id = f"accept-{index + 1}"
        if text:
            criteria.append({"id": item_id, "text": text[:240], "done": done})
    milestones = []
    for index, item in enumerate(raw.get("milestones") or []):
        if not isinstance(item, dict):
            item = {"title": str(item or "")}
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        status = str(item.get("status") or "pending").strip().lower()
        if status not in {"pending", "in_progress", "done"}:
            status = "pending"
        milestones.append(
            {
                "id": str(item.get("id") or f"milestone-{index + 1}"),
                "title": title[:160],
                "due_date": str(item.get("due_date") or "").strip()[:10],
                "status": status,
            }
        )
    status = str(raw.get("status") or "active").strip().lower()
    if status not in {"planning", "active", "paused", "done"}:
        status = "active"
    priority = str(raw.get("priority") or "medium").strip().lower()
    if priority not in {"low", "medium", "high", "urgent"}:
        priority = "medium"
    return {
        **raw,
        "project": str(raw.get("project") or "").strip()[:160],
        "project_id": str(raw.get("project_id") or "").strip()[:80],
        "summary": str(raw.get("summary") or "").strip()[:1200],
        "objective": str(raw.get("objective") or "").strip()[:600],
        "stage": str(raw.get("stage") or "").strip()[:120],
        "status": status,
        "priority": priority,
        "start_date": str(raw.get("start_date") or "").strip()[:10],
        "target_date": str(raw.get("target_date") or "").strip()[:10],
        "topics": [str(item).strip()[:80] for item in topics if str(item).strip()][:20],
        "acceptance_criteria": criteria[:30],
        "milestones": milestones[:30],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
