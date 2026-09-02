"""情报理解层：摘要 / 标签 / 价值判断。不做推荐。"""

from __future__ import annotations

from typing import Any

from . import llm
from .models import RawItem, item_id


UNDERSTAND_SYSTEM = (
    "你是个人工作秘书的情报编辑，只做结构化理解，不做推荐。"
    "summary、key_points、impact、what_to_watch 和 innovation 必须用自然、具体的中文。"
    "不要只改写标题，要说清发生了什么、重要细节、可能产生的影响。"
    "tags 用中文短词（2–6字），方便用户扫一眼判断感不感兴趣。"
    "只返回 JSON。"
)


def understand_all(raw: list[RawItem]) -> list[dict[str, Any]]:
    base = [understand_heuristic(item) for item in raw]
    overlay = _llm_understand(base[:12])
    by_id = {row["id"]: row for row in overlay}
    out = []
    for row in base:
        merged = dict(row)
        extra = by_id.get(row["id"]) or {}
        for key in (
            "summary", "key_points", "impact", "what_to_watch", "interesting_point",
            "domain", "keywords", "innovation", "importance", "novelty",
            "technical_depth", "content_type", "tags",
        ):
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
    platform = item.metadata or {}
    if platform:
        votes = max(0, int(platform.get("vote_up_count") or 0))
        ranking = _clip(platform.get("ranking_score"), 0.0)
        authority = _clip(platform.get("authority_level"), 0.0)
        engagement = min(1.0, votes / 500)
        importance = max(importance, 0.45 + 0.2 * ranking + 0.12 * engagement + 0.08 * authority)
    depth = {"paper": 0.88, "release": 0.7, "blog": 0.62, "news": 0.4}.get(item.item_type, 0.5)
    summary_zh = _zh_fallback(item)
    key_points = _fallback_points(item)
    return {
        "id": item_id(item.source_url),
        "source_id": item.source_id,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "title": item.title,
        "summary": item.summary,
        "summary_zh": summary_zh,
        "key_points": key_points,
        "impact": _fallback_impact(item),
        "what_to_watch": _fallback_watch(item),
        "interesting_point": "",
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
        "author_name": platform.get("author_name") or "",
        "author_badge_text": platform.get("author_badge_text") or "",
        "vote_up_count": int(platform.get("vote_up_count") or 0),
        "comment_count": int(platform.get("comment_count") or 0),
        "authority_level": platform.get("authority_level") or "",
        "ranking_score": float(platform.get("ranking_score") or 0),
        "content_id": platform.get("content_id") or "",
        "via": "heuristic",
    }


def ensure_rich_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Backfill editorial fields for content collected before rich summaries existed."""
    row = dict(item)
    raw = RawItem(
        source_id=str(row.get("source_id") or "existing"),
        source_name=str(row.get("source_name") or "信息源"),
        channel=str(row.get("channel") or "interest"),
        title=str(row.get("title") or "未命名内容"),
        summary=str(row.get("summary") or row.get("summary_zh") or ""),
        source_url=str(row.get("source_url") or ""),
        published_at=str(row.get("published_at") or ""),
        item_type=str(row.get("item_type") or row.get("content_type") or "article"),
    )
    if len(str(row.get("summary_zh") or "").strip()) < 60:
        row["summary_zh"] = _zh_fallback(raw)
    row.setdefault("key_points", _fallback_points(raw))
    row.setdefault("impact", _fallback_impact(raw))
    row.setdefault("what_to_watch", _fallback_watch(raw))
    row.setdefault("interesting_point", "")
    return row


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
            '返回 {"items":[{"id":"...","summary":"中文120-180字，包含事实与背景","key_points":["要点1","要点2","要点3"],'
            '"impact":"对行业、产品或工作可能产生的影响，不超过80字",'
            '"what_to_watch":"接下来值得观察什么，不超过60字","interesting_point":"有趣或反直觉的一点，不超过50字",'
            '"tags":["中文tag"],'
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
                "key_points": [str(x).strip() for x in (row.get("key_points") or []) if str(x).strip()][:3],
                "impact": str(row.get("impact") or "").strip(),
                "what_to_watch": str(row.get("what_to_watch") or "").strip(),
                "interesting_point": str(row.get("interesting_point") or "").strip(),
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
        return f"{item.source_name} 刚发布了《{item.title}》。看新增能力、有没有 breaking change、升级成本多大，再决定要不要跟进。"
    if item.item_type == "paper":
        return f"论文《{item.title}》。核心在解决什么问题、用了什么方法、实验结论是否站得住——判断能不能用到你现在的项目里。"
    if item.item_type == "news":
        return f"{item.source_name} 报道了《{item.title}》。这条帮你快速了解行业最近发生了什么、谁在动、对你的产品或方向有没有影响。"
    text = (item.summary or item.title or "").strip()
    return f"{item.source_name} 更新了《{item.title}》。{text[:140]}"


def _fallback_points(item: RawItem) -> list[str]:
    if item.item_type == "paper":
        return ["论文解决的核心问题是什么", "方法有没有新意、实验对比是否充分", "结论能否迁移到你的场景"]
    if item.item_type == "release":
        return ["这次实际加了什么能力", "有没有不兼容或需要改的地方", "值不值得现在升级"]
    return ["这件事的关键在哪", "对你的工作或产品有什么影响", "接下来会怎么演变"]


def _fallback_impact(item: RawItem) -> str:
    if item.item_type == "news":
        return "可能影响行业判断、产品节奏或竞争格局，建议和近期同类动态放一起看。"
    if item.item_type == "paper":
        return "如果结论可靠，可以作为方案设计或技术选型的依据。"
    return "可能影响你的工具链、技术选型或近期工作安排。"


def _fallback_watch(item: RawItem) -> str:
    if item.item_type == "release":
        return "留意真实用户反馈、已知 bug 和下个补丁。"
    if item.item_type == "paper":
        return "看代码和数据有没有开源，以及后续有没有复现结果。"
    return "看后续官方回应、产品落地和同行的动作。"


def _clip(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
