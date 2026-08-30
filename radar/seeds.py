"""Demo 用户种子：Alice = Agent Memory，Bob = 自动驾驶。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import _write_json


ALICE = "alice"
BOB = "bob"

DEMO_PASSWORDS = {
    ALICE: "alice123",
    BOB: "bob123",
}

DEMO_USERS = [
    {
        "id": ALICE,
        "display_name": "Alice",
        "label": "Alice — Agent Memory",
        "identities": [("web", "alice"), ("feishu", "ou_alice")],
        "profile": {
            "user_id": ALICE,
            "display_name": "Alice",
            "role": "AI 算法工程师",
            "bio": "正在做 Personal Work Secretary 的长期记忆与个性化推荐。",
            "team": "Agent 平台",
            "timezone": "GMT +8",
            "languages": "中文 / English",
        },
        "interests": [
            {"topic": "Agent Memory", "weight": 0.94, "source": ["seed"]},
            {"topic": "Mem0", "weight": 0.9, "source": ["seed"]},
            {"topic": "Long-term Memory", "weight": 0.88, "source": ["seed"]},
            {"topic": "Personal Agent", "weight": 0.86, "source": ["seed"]},
            {"topic": "RAG", "weight": 0.72, "source": ["seed"]},
        ],
        "project": {
            "project": "Personal Work Secretary Agent",
            "stage": "Memory 模块设计",
            "topics": ["Memory", "Personalization", "Proactive Recommendation"],
            "priority": "high",
        },
        "goals": [
            {"id": "a-today", "kind": "today", "title": "完成 Memory 推荐 Demo", "priority": "high", "progress": 60, "linked": 5, "done": False},
            {"id": "a-week", "kind": "week", "title": "接入长期记忆与反馈闭环", "priority": "high", "progress": 40, "linked": 3, "done": False},
        ],
        "products": [{"id": "mem0", "name": "Mem0", "status": "深度关注", "running": True}],
        "tasks": [
            {
                "title": "完善 Memory Demo",
                "description": "补齐多用户 Memory 隔离与对话记忆演示。",
                "priority": "high",
                "status": "in_progress",
                "project": "Personal Work Secretary Agent",
                "project_id": "personal-agent",
                "deadline": "2026-08-29T18:00:00+08:00",
            }
        ],
        "work_notes": [
            {"content": "第一阶段优先聚焦主动感知 + 个性化推荐。", "tags": ["decision"], "project_id": "personal-agent"}
        ],
        "work_events": [
            {
                "event_type": "task_created",
                "title": "完善 Memory Demo",
                "content": "补齐多用户 Memory 隔离与对话记忆演示。",
                "project_id": "personal-agent",
                "source_type": "seed",
                "source_ref": "task-001",
            },
        ],
    },
    {
        "id": BOB,
        "display_name": "Bob",
        "label": "Bob — Autonomous Driving",
        "identities": [("web", "bob"), ("feishu", "ou_bob")],
        "profile": {
            "user_id": BOB,
            "display_name": "Bob",
            "role": "自动驾驶研究员",
            "bio": "关注 World Model、VLM 与智能座舱，正在做自动驾驶研究。",
            "team": "智驾感知",
            "timezone": "GMT +8",
            "languages": "中文 / English",
        },
        "interests": [
            {"topic": "World Model", "weight": 0.94, "source": ["seed"]},
            {"topic": "Autonomous Driving", "weight": 0.92, "source": ["seed"]},
            {"topic": "VLM", "weight": 0.88, "source": ["seed"]},
            {"topic": "Intelligent Cockpit", "weight": 0.8, "source": ["seed"]},
        ],
        "project": {
            "project": "Autonomous Driving Research",
            "stage": "World Model 调研",
            "topics": ["World Model", "VLM", "Autonomous Driving"],
            "priority": "high",
        },
        "goals": [
            {"id": "b-today", "kind": "today", "title": "阅读 World Model 相关论文", "priority": "high", "progress": 35, "linked": 4, "done": False},
            {"id": "b-week", "kind": "week", "title": "对比 VLM 在智驾场景的方案", "priority": "medium", "progress": 20, "linked": 2, "done": False},
        ],
        "products": [{"id": "tesla-fsd", "name": "Occupancy Network", "status": "持续跟踪", "running": True}],
        "tasks": [
            {
                "title": "整理 World Model 数据集",
                "description": "汇总占用预测与闭环规划相关数据集，供本周调研使用。",
                "priority": "high",
                "status": "todo",
                "project": "Autonomous Driving Research",
                "project_id": "autonomous-driving",
                "deadline": "2026-08-30T18:00:00+08:00",
            }
        ],
        "work_notes": [
            {"content": "智驾场景 VLM 方案对比仍缺闭环评测集。", "tags": ["research"], "project_id": "autonomous-driving"}
        ],
        "work_events": [
            {
                "event_type": "task_created",
                "title": "整理 World Model 数据集",
                "content": "汇总占用预测与闭环规划相关数据集，供本周调研使用。",
                "project_id": "autonomous-driving",
                "source_type": "seed",
                "source_ref": "task-002",
            },
        ],
    },
]

DEMO_ITEMS = [
    {
        "id": "demo-mem0",
        "title": "Mem0 发布 Temporal Memory：让 AI Agent 拥有时间感知的长期记忆",
        "summary": "Mem0 提出面向 Agent 的时间衰减长期记忆，适合 Personal Work Secretary 的 Memory 与 Personalization 模块。",
        "summary_zh": "Mem0 提出面向 Agent 的时间衰减长期记忆，适合 Personal Work Secretary 的 Memory 与 Personalization 模块。",
        "source_url": "https://example.com/mem0-temporal-memory",
        "source_name": "Mem0 Blog",
        "published_at": "2026-08-25T08:00:00Z",
        "item_type": "blog",
        "tags": ["Agent Memory", "Mem0", "Long-term Memory"],
        "keywords": ["memory", "mem0", "agent", "personalization"],
        "importance": 0.96,
        "novelty": 0.92,
        "technical_depth": 0.88,
    },
    {
        "id": "demo-skill",
        "title": "Memory Skill：把长期记忆做成 Agent 可调用的能力",
        "summary": "讨论 Personal Agent 如何用 Memory Skill 做个性化推荐。",
        "summary_zh": "讨论 Personal Agent 如何用 Memory Skill 做个性化推荐。",
        "source_url": "https://example.com/memory-skill",
        "source_name": "ArXiv",
        "published_at": "2026-08-25T07:00:00Z",
        "item_type": "paper",
        "tags": ["Personal Agent", "RAG", "Memory Skill"],
        "keywords": ["personal agent", "rag", "memory"],
        "importance": 0.82,
        "novelty": 0.7,
        "technical_depth": 0.84,
    },
    {
        "id": "demo-world",
        "title": "World Model for Autonomous Driving：用世界模型预测占用栅格",
        "summary": "面向自动驾驶的 World Model，强调多模态占用预测与闭环规划。",
        "summary_zh": "面向自动驾驶的 World Model，强调多模态占用预测与闭环规划。",
        "source_url": "https://example.com/world-model-ad",
        "source_name": "ArXiv",
        "published_at": "2026-08-25T09:00:00Z",
        "item_type": "paper",
        "tags": ["World Model", "Autonomous Driving", "Occupancy"],
        "keywords": ["world model", "autonomous driving", "vlm"],
        "importance": 0.88,
        "novelty": 0.8,
        "technical_depth": 0.86,
    },
    {
        "id": "demo-vlm",
        "title": "VLM Intelligent Cockpit：座舱多模态大模型与驾驶场景理解",
        "summary": "智能座舱 VLM 如何理解驾驶场景并辅助决策。",
        "summary_zh": "智能座舱 VLM 如何理解驾驶场景并辅助决策。",
        "source_url": "https://example.com/vlm-cockpit",
        "source_name": "NVIDIA Blog",
        "published_at": "2026-08-25T06:00:00Z",
        "item_type": "blog",
        "tags": ["VLM", "Intelligent Cockpit", "Autonomous Driving"],
        "keywords": ["vlm", "cockpit", "driving"],
        "importance": 0.8,
        "novelty": 0.74,
        "technical_depth": 0.7,
    },
]


def spec_by_id(user_id: str) -> dict[str, Any] | None:
    for row in DEMO_USERS:
        if row["id"] == user_id:
            return row
    return None


def bootstrap_user_dir(root: Path, spec: dict[str, Any]) -> None:
    memory = root / "memory"
    if (memory / "interests.json").exists():
        return
    _write_json(root / "profile.json", {"user_id": spec["id"], "work_keywords": [], "interest_keywords": []})
    _write_json(memory / "profile.json", dict(spec["profile"]))
    _write_json(memory / "interests.json", {"topics": list(spec.get("interests") or [])})
    _write_json(memory / "project.json", dict(spec.get("project") or {}))
    _write_json(root / "goals.json", {"items": list(spec.get("goals") or [])})
    _write_json(root / "products.json", {"items": list(spec.get("products") or [])})


def bootstrap_new_user(root: Path, user_id: str, display_name: str) -> None:
    bootstrap_user_dir(
        root,
        {
            "id": user_id,
            "profile": {
                "user_id": user_id,
                "display_name": display_name,
                "role": "",
                "bio": "",
                "team": "",
                "timezone": "GMT +8",
                "languages": "中文 / English",
            },
            "interests": [],
            "project": {
                "project": "我的工作",
                "stage": "开始使用",
                "topics": [],
                "priority": "medium",
            },
            "goals": [],
            "products": [],
        },
    )


def bootstrap_core_data(
    tasks_service,
    notes_service,
    events_service,
    user_root: Path,
    user_id: str,
) -> None:
    """把种子 tasks/work_notes/work_events 写入核心服务存储（幂等：已有种子任务则跳过）。"""
    spec = spec_by_id(user_id)
    if not spec:
        return
    existing = tasks_service.list_tasks(user_id, source_type="seed")
    if existing:
        return
    for draft in spec.get("tasks") or []:
        tasks_service.create_task(
            {
                **draft,
                "source_type": "seed",
            },
            user_id,
        )
    for draft in spec.get("work_notes") or []:
        notes_service.create_note(
            {
                **draft,
                "source_type": "seed",
            },
            user_id,
        )
    for draft in spec.get("work_events") or []:
        events_service.record(
            event_type=str(draft.get("event_type") or "note"),
            user_id=user_id,
            title=str(draft.get("title") or ""),
            content=str(draft.get("content") or ""),
            source_type="seed",
            source_ref=str(draft.get("source_ref") or ""),
            project_id=str(draft.get("project_id") or ""),
        )
