"""工作台附加账本：目标、关注产品、观察状态、推送偏好。不替代 Memory。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import _read_json, _write_json


DEFAULT_GOALS = [
    {
        "id": "today-1",
        "kind": "today",
        "title": "完成项目需求评审",
        "priority": "high",
        "progress": 67,
        "due": "",
        "linked": 8,
        "done": False,
    },
    {
        "id": "week-1",
        "kind": "week",
        "title": "输出个性化推荐 Demo / 技术方案",
        "priority": "high",
        "progress": 30,
        "due": "",
        "linked": 6,
        "done": False,
    },
    {
        "id": "quarter-1",
        "kind": "quarter",
        "title": "构建长期记忆型 Personal Agent",
        "priority": "medium",
        "progress": 45,
        "due": "",
        "linked": 4,
        "done": False,
    },
    {
        "id": "open-1",
        "kind": "open",
        "title": "持续关注 Agent 技术",
        "priority": "low",
        "progress": 0,
        "due": "",
        "linked": 0,
        "done": False,
    },
]

DEFAULT_PRODUCTS = [
    {"id": "mem0", "name": "Mem0", "status": "深度关注", "running": True},
    {"id": "memos", "name": "MemOS", "status": "持续跟踪", "running": True},
    {"id": "vllm", "name": "vLLM", "status": "持续跟踪", "running": True},
]

DEFAULT_PUSH = {
    "web": True,
    "feishu": True,
    "chat": False,
    "morning_brief": True,
    "morning_time": "08:30",
    "instant": True,
    "instant_threshold": 78,
    "weekly_brief": True,
    "weekly_time": "周一 09:00",
    "work_first": True,
    "quiet_hours": True,
    "high_only": False,
    "high_threshold": 75,
    "dnd": "22:00 - 08:00",
    "work_personal_ratio": 55,
    "content_types": ["技术文章", "行业资讯", "产品动态", "轻松发现"],
    "summary_length": "详细",
    "push_clock": "12:30",
}

KNOWN_TOPICS = [
    "Agent Memory",
    "Memory Skill",
    "Personal Agent",
    "Proactive Agent",
    "AI Coding",
    "RAG",
    "Mem0",
    "Long-term Memory",
    "World Model",
    "Autonomous Driving",
    "VLM",
    "Intelligent Cockpit",
    "Multimodal Agent",
    "vLLM",
]


class Workspace:
    def __init__(self, data_dir: Path, observe_path: Path | None = None) -> None:
        self.root = data_dir
        self.goals_path = data_dir / "goals.json"
        self.products_path = data_dir / "products.json"
        self.push_path = data_dir / "push_settings.json"
        self.observe_path = observe_path or (data_dir / "observe.json")
        if not self.goals_path.exists():
            _write_json(self.goals_path, {"items": list(DEFAULT_GOALS)})
        if not self.products_path.exists():
            _write_json(self.products_path, {"items": list(DEFAULT_PRODUCTS)})
        if not self.push_path.exists():
            _write_json(self.push_path, dict(DEFAULT_PUSH))
        if not self.observe_path.exists():
            self.record_observe(0, 0, 0)

    def goals(self) -> list[dict[str, Any]]:
        return list(_read_json(self.goals_path, {"items": []}).get("items") or [])

    def save_goals(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        _write_json(self.goals_path, {"items": items})
        return items

    def add_goal(self, title: str, kind: str = "today", priority: str = "medium") -> dict[str, Any]:
        name = str(title or "").strip()[:120]
        if not name:
            raise ValueError("title required")
        items = self.goals()
        item = {
            "id": f"g-{len(items) + 1}-{abs(hash(name)) % 100000}",
            "kind": kind,
            "title": name,
            "priority": priority,
            "progress": 0,
            "linked": 0,
            "done": False,
        }
        items.append(item)
        self.save_goals(items)
        return item

    def update_goal(self, goal_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        items = self.goals()
        for index, item in enumerate(items):
            if item.get("id") != goal_id:
                continue
            merged = dict(item)
            if "title" in patch and patch.get("title") is not None:
                merged["title"] = str(patch.get("title")).strip()[:120]
            if "kind" in patch and patch.get("kind") is not None:
                merged["kind"] = str(patch.get("kind")).strip()
            if "priority" in patch and patch.get("priority") is not None:
                merged["priority"] = str(patch.get("priority")).lower()
            if "done" in patch and patch.get("done") is not None:
                merged["done"] = bool(patch.get("done"))
            if "progress" in patch and patch.get("progress") is not None:
                merged["progress"] = max(0, min(100, int(patch.get("progress"))))
            if "deadline" in patch and patch.get("deadline") is not None:
                merged["deadline"] = str(patch.get("deadline")).strip()
            if "description" in patch and patch.get("description") is not None:
                merged["description"] = str(patch.get("description")).strip()[:500]
            if "parent_project_id" in patch and patch.get("parent_project_id") is not None:
                merged["parent_project_id"] = str(patch.get("parent_project_id")).strip()
            items[index] = merged
            self.save_goals(items)
            return merged
        return None

    def delete_goal(self, goal_id: str) -> bool:
        items = self.goals()
        kept = [item for item in items if item.get("id") != goal_id]
        if len(kept) == len(items):
            return False
        self.save_goals(kept)
        return True

    def products(self) -> list[dict[str, Any]]:
        return list(_read_json(self.products_path, {"items": []}).get("items") or [])

    def save_products(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        _write_json(self.products_path, {"items": items})
        return items

    def user_sources(self) -> list[dict[str, Any]]:
        return list(_read_json(self.root / "user_sources.json", {"items": []}).get("items") or [])

    def save_user_sources(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        _write_json(self.root / "user_sources.json", {"items": items})
        return items

    def add_user_source(self, spec: dict[str, Any]) -> dict[str, Any]:
        name = str(spec.get("name") or "").strip()
        url = str(spec.get("url") or spec.get("repo") or spec.get("search") or "").strip()
        if not name or not url:
            raise ValueError("name and url required")
        rows = self.user_sources()
        key = url.rstrip("/").lower()
        if any(str(row.get("url") or row.get("repo") or "").rstrip("/").lower() == key for row in rows):
            raise ValueError("source already exists")
        row = {
            "id": f"user-{len(rows) + 1}-{abs(hash(key)) % 100000}",
            "name": name[:80],
            "kind": str(spec.get("kind") or "rss"),
            "type": str(spec.get("type") or "blog"),
            "url": str(spec.get("url") or ""),
            "repo": str(spec.get("repo") or ""),
            "search": str(spec.get("search") or ""),
            "max": int(spec.get("max") or 5),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)
        self.save_user_sources(rows)
        return row

    def update_user_source(self, source_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        rows = self.user_sources()
        for index, row in enumerate(rows):
            if row.get("id") != source_id:
                continue
            for key in ("name", "kind", "type", "url", "repo", "search"):
                if key in patch and patch.get(key) is not None:
                    row[key] = str(patch.get(key)).strip()
            if "max" in patch:
                row["max"] = int(patch.get("max") or row.get("max") or 5)
            rows[index] = row
            self.save_user_sources(rows)
            return row
        return None

    def delete_user_source(self, source_id: str) -> bool:
        rows = self.user_sources()
        kept = [row for row in rows if row.get("id") != source_id]
        if len(kept) == len(rows):
            return False
        self.save_user_sources(kept)
        return True

    def push_settings(self) -> dict[str, Any]:
        merged = dict(DEFAULT_PUSH)
        merged.update(_read_json(self.push_path, {}))
        return merged

    def save_push_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = self.push_settings()
        merged.update(payload)
        _write_json(self.push_path, merged)
        return merged

    def observe(self) -> dict[str, Any]:
        return _read_json(
            self.observe_path,
            {"fetched": 0, "filtered": 0, "total": 0, "last_at": "", "running": True},
        )

    def record_observe(self, fetched: int, filtered: int, sources: int) -> dict[str, Any]:
        prev = self.observe()
        payload = {
            "fetched": fetched,
            "filtered": filtered,
            "sources": sources,
            "total": int(prev.get("total") or 0) + fetched,
            "last_at": datetime.now(timezone.utc).isoformat(),
            "running": True,
        }
        _write_json(self.observe_path, payload)
        return payload


def classify_knowledge(item: dict[str, Any]) -> str:
    blob = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("summary") or ""),
            " ".join(item.get("tags") or []),
        ]
    ).lower()
    if any(word in blob for word in ("world model", "autonomous driving", "occupancy", "自动驾驶")):
        return "Autonomous Driving"
    if any(word in blob for word in ("vlm", "cockpit", "座舱")):
        return "VLM"
    if any(word in blob for word in ("memory", "mem0", "记忆")):
        return "Agent Memory"
    if any(word in blob for word in ("personal agent", "secretary", "秘书")):
        return "Personal Agent"
    if any(word in blob for word in ("vllm", "github", "coding", "code")):
        return "AI Coding"
    if any(word in blob for word in ("launch", "release", "产品")):
        return "产品动态"
    if any(word in blob for word in ("tool", "工具")):
        return "工具实践"
    return "待整理"


def parse_follow_text(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return []
    found: list[dict[str, Any]] = []
    lower = raw.lower()
    for topic in KNOWN_TOPICS:
        if topic.lower() in lower:
            found.append({"topic": topic, "weight": 0.88, "source": ["follow"]})
    if found:
        return found
    parts = [p.strip() for p in re.split(r"[,，、和与以及]", raw) if p.strip()]
    out = []
    for part in parts[:6]:
        cleaned = re.sub(r"^(最近)?(帮我)?(重点)?(持续)?关注", "", part).strip(" 。.：:")
        if 1 < len(cleaned) <= 32:
            out.append({"topic": cleaned, "weight": 0.8, "source": ["follow"]})
    return out
