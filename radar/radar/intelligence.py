"""情报理解层：摘要 / 标签 / 价值判断。不做推荐。"""

from __future__ import annotations

from typing import Any

from . import llm
from .models import RawItem, item_id


UNDERSTAND_SYSTEM = (
    "你是技术情报理解层，只做结构化理解，不做推荐。"
    "summary 和 innovation 必须用中文。"
    "tags 用中文短词（2–6字），方便用户扫一眼判断感不感兴趣。"
    "只返回 JSON。"
)


def understand_all(raw: list[RawItem]) -> list[dict[str, Any]]:
    base = [understand_heuristic(item) for item in raw]
    overlay = _llm_understand(base[:5])
    by_id = {row["id"]: row for row in overlay}
    out = []
    for row in base:
        merged = dict(row)
        extra = by_id.get(row["id"]) or {}
        for key in ("summary", "domain", "keywords", "innovation", "importance", "novelty", "technical_depth", "content_type", "tags"):
            if extra.get(key) not in (None, "", []):
                merged[key] = extra[key]
        if extra.get("summary"):
            merged["summary_zh"] = extra["summary"]
        if extra.get("tags"):
            merged["tags"] = extra["tags"]
        out.append(merged)
    return out


def understand_heuristic(item: RawItem) -> dict[str, Any]:
    blob = f"{item.title} {item.summary}"
    tags = _guess_tags(blob, item.item_type)
    importance = 0.55
    if item.item_type == "paper":
        importance = 0.72
    elif item.item_type == "release":
        importance = 0.7
    elif any(word in blob.lower() for word in ("funding", "raises", "融资", "series")):
        importance = 0.28
        tags = list(dict.fromkeys(["融资"] + tags))[:5]
    novelty = 0.6 if item.published_at else 0.45
    depth = {"paper": 0.88, "release": 0.7, "blog": 0.62, "news": 0.4}.get(item.item_type, 0.5)
    summary_zh = _zh_fallback(item)
    return {
        "id": item_id(item.source_url),
        "source_id": item.source_id,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "title": item.title,
        "summary": item.summary,
        "summary_zh": summary_zh,
        "published_at": item.published_at,
        "item_type": item.item_type,
        "content_type": item.item_type,
        "channel": item.channel,
        "domain": tags[:3],
        "keywords": tags,
        "tags": tags,
        "innovation": [],
        "importance": importance,
        "novelty": novelty,
        "technical_depth": depth,
        "via": "heuristic",
    }


def _llm_understand(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    compact = [
        {
            "id": row["id"],
            "title": row["title"],
            "summary": (row.get("summary") or "")[:320],
            "type": row.get("item_type"),
            "source": row.get("source_name"),
        }
        for row in rows
    ]
    parsed = llm.chat_json(
        UNDERSTAND_SYSTEM,
        (
            '返回 {"items":[{"id":"...","summary":"中文不超过80字","tags":["中文tag"],'
            '"domain":[],"keywords":[],"innovation":["中文要点"],'
            '"importance":0-1,"novelty":0-1,"technical_depth":0-1,'
            '"content_type":"research|release|blog|news"}]}\n'
            f"条目：{compact}"
        ),
        timeout=28,
    )
    if not parsed:
        return []
    out = []
    for row in parsed.get("items") or []:
        if not row.get("id"):
            continue
        tags = [str(x).strip() for x in (row.get("tags") or row.get("keywords") or []) if str(x).strip()][:5]
        out.append(
            {
                "id": row["id"],
                "summary": str(row.get("summary") or "").strip(),
                "tags": tags,
                "domain": row.get("domain") or tags[:3],
                "keywords": row.get("keywords") or tags,
                "innovation": [str(x).strip() for x in (row.get("innovation") or []) if str(x).strip()][:4],
                "importance": _clip(row.get("importance"), 0.55),
                "novelty": _clip(row.get("novelty"), 0.5),
                "technical_depth": _clip(row.get("technical_depth"), 0.5),
                "content_type": row.get("content_type") or "",
                "via": "llm",
            }
        )
    return out


def _guess_tags(blob: str, item_type: str) -> list[str]:
    text = blob.lower()
    mapping = [
        ("memory", "长期记忆"),
        ("mem0", "长期记忆"),
        ("agent", "Agent"),
        ("skill", "Memory Skill"),
        ("rag", "RAG"),
        ("vllm", "推理引擎"),
        ("multimodal", "多模态"),
        ("proactive", "主动智能体"),
        ("launch", "产品发布"),
        ("gpu", "GPU"),
        ("openai", "大模型"),
        ("funding", "融资"),
        ("融资", "融资"),
    ]
    tags = [label for needle, label in mapping if needle in text]
    type_tag = {"paper": "论文", "release": "开源发布", "blog": "技术博客", "news": "行业新闻"}.get(item_type)
    if type_tag:
        tags.append(type_tag)
    return list(dict.fromkeys(tags))[:5] or ["技术动态"]


def _zh_fallback(item: RawItem) -> str:
    if item.item_type == "release":
        return f"{item.source_name} 有新版本：{item.title}。"
    if item.item_type == "paper":
        return f"论文关注 {item.title}。"
    text = (item.summary or item.title or "").strip()
    return text[:80]


def _clip(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
