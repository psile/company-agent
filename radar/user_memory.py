"""结构化记忆：画像 / 带权兴趣 / 当前项目 / 行为。兴趣必须带权重和时间。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import LocalMemory, _read_json, _write_json


DEFAULT_PROFILE = {
    "user_id": "me",
    "role": "AI算法工程师",
    "domains": ["Agent", "Multimodal AI"],
    "preferred_content": ["论文", "技术博客", "开源项目"],
}

DEFAULT_INTERESTS = [
    {"topic": "Agent Memory", "weight": 0.92, "last_active": "", "source": ["seed"]},
    {"topic": "Memory Skill", "weight": 0.86, "last_active": "", "source": ["seed"]},
    {"topic": "Proactive Agent", "weight": 0.84, "last_active": "", "source": ["seed"]},
    {"topic": "Multimodal Agent", "weight": 0.73, "last_active": "", "source": ["seed"]},
    {"topic": "vLLM", "weight": 0.58, "last_active": "", "source": ["seed"]},
    {"topic": "World Model", "weight": 0.42, "last_active": "", "source": ["seed"]},
]

DEFAULT_PROJECT = {
    "project": "Personal Work Secretary Agent",
    "stage": "方案设计 / 技术调研",
    "topics": ["Memory", "Personalization", "Proactive Recommendation"],
    "priority": "high",
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
        return {
            "profile": self.profile(),
            "interests": self.interests(),
            "project": self.project(),
            "behavior": self.behavior(),
        }

    def profile(self) -> dict[str, Any]:
        return _read_json(self.profile_path, dict(DEFAULT_PROFILE))

    def interests(self) -> list[dict[str, Any]]:
        data = _read_json(self.interest_path, {"topics": list(DEFAULT_INTERESTS)})
        rows = data.get("topics") if isinstance(data, dict) else data
        return sorted(list(rows or []), key=lambda row: -float(row.get("weight") or 0))

    def project(self) -> dict[str, Any]:
        return _read_json(self.project_path, dict(DEFAULT_PROJECT))

    def behavior(self) -> dict[str, Any]:
        merged = dict(DEFAULT_BEHAVIOR)
        merged.update(_read_json(self.behavior_path, {}))
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
    for token in ("Memory", "Agent", "vLLM", "RAG", "LLM", "Skill"):
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
