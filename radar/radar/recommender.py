"""召回 + 规则打分 + LLM 重排。推荐模块只负责排序，不负责采集和记忆写入。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from . import llm


SOURCE_TRUST = {
    "arxiv": 0.9,
    "github": 0.85,
    "hugging face": 0.8,
    "openai": 0.82,
    "nvidia": 0.8,
    "mem0": 0.86,
    "vllm": 0.84,
    "the verge": 0.52,
}

RERANK_SYSTEM = (
    "你是个性化重排。结合用户当前项目、近期兴趣和负反馈，判断这条对此刻的这个人有没有价值。"
    "所有面向用户的字段必须用中文：summary、tags、reason、project_value。"
    "tags 用中文短词，方便用户判断感不感兴趣。宁缺毋滥。"
    "只返回 JSON。"
)


def rank_world(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in items:
        quality = _quality(item)
        fresh = freshness(item.get("published_at") or "")
        importance = float(item.get("importance") or 0.5)
        novelty = float(item.get("novelty") or 0.5)
        score = 0.35 * quality + 0.30 * fresh + 0.20 * importance + 0.15 * novelty
        row = dict(item)
        row["view"] = "intel"
        row["score"] = int(round(100 * score))
        row["scores"] = {
            "quality": round(quality, 3),
            "fresh": round(fresh, 3),
            "importance": round(importance, 3),
            "novelty": round(novelty, 3),
        }
        row["why_you"] = row.get("why_you") or f"行业里正在发生：来自 {item.get('source_name')}"
        ranked.append(row)
    ranked.sort(key=lambda row: -row["score"])
    return ranked


def rank_for_you(items: list[dict[str, Any]], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = []
    for item in items:
        parts = score_parts(item, ctx)
        total = (
            0.20 * parts["semantic"]
            + 0.25 * parts["interest"]
            + 0.25 * parts["project"]
            + 0.10 * parts["fresh"]
            + 0.12 * parts["quality"]
            + 0.08 * parts["feedback"]
        )
        row = dict(item)
        row["view"] = "for_you"
        row["score"] = int(round(100 * total))
        row["scores"] = {key: round(val, 3) for key, val in parts.items() if key != "matched"}
        row["matched"] = parts["matched"]
        row["why_you"] = _why(item, ctx, parts)
        row["project_value"] = _project_hint(item, ctx, parts)
        ranked.append(row)
    ranked.sort(key=lambda row: -row["score"])
    return ranked


def score_parts(item: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    interests = ctx.get("interests") or []
    project = ctx.get("project") or {}
    behavior = ctx.get("behavior") or {}
    blob = _blob(item)
    matched: list[str] = []
    interest_score = 0.0
    for row in interests:
        topic = str(row.get("topic") or "")
        if topic and _overlap(blob, topic):
            matched.append(topic)
            interest_score = max(interest_score, float(row.get("weight") or 0))
    project_topics = list(project.get("topics") or []) + [str(project.get("project") or "")]
    project_hit = any(_overlap(blob, topic) for topic in project_topics if topic)
    project_score = 0.85 if project_hit else 0.15
    semantic = _jaccard(blob, " ".join(matched + project_topics))
    fresh = freshness(item.get("published_at") or "")
    quality = _quality(item)
    feedback = _feedback(item, behavior)
    return {
        "semantic": semantic,
        "interest": interest_score,
        "project": project_score,
        "fresh": fresh,
        "quality": quality,
        "feedback": feedback,
        "matched": matched[:6],
    }


def rerank_with_llm(items: list[dict[str, Any]], ctx: dict[str, Any], already: list[str]) -> list[dict[str, Any]]:
    if not items:
        return []
    compact = [
        {
            "id": row.get("id"),
            "title": row.get("title"),
            "summary": (row.get("summary_zh") or row.get("summary") or "")[:180],
            "tags": row.get("tags") or [],
            "score": row.get("score"),
            "matched": row.get("matched") or [],
        }
        for row in items[:6]
    ]
    project = ctx.get("project") or {}
    interests = [f"{row.get('topic')}={row.get('weight')}" for row in (ctx.get("interests") or [])[:6]]
    disliked = (ctx.get("behavior") or {}).get("disliked_topics") or []
    parsed = llm.chat_json(
        RERANK_SYSTEM,
        (
            '返回 {"items":[{"id":"...","recommend":true,"score":0-1,"priority":"high|normal|skip",'
            '"summary":"中文总结不超过80字","tags":["中文tag"],'
            '"reason":"为什么推荐给你","project_value":"与当前项目的关系"}]}\n'
            f"当前项目：{project.get('project')} / 阶段 {project.get('stage')} / 主题 {project.get('topics')}\n"
            f"近期兴趣：{interests}\n"
            f"负反馈：{disliked}\n"
            f"已推送：{already[-20:]}\n"
            f"候选：{compact}"
        ),
        timeout=28,
    )
    by_id = {row.get("id"): row for row in items}
    if not parsed:
        return _heuristic_decide(items, already)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in parsed.get("items") or []:
        item_id = str(row.get("id") or "")
        base = by_id.get(item_id)
        if not base or item_id in seen:
            continue
        merged = dict(base)
        if row.get("summary"):
            merged["summary_zh"] = str(row["summary"]).strip()
        if row.get("tags"):
            merged["tags"] = [str(x).strip() for x in row["tags"] if str(x).strip()][:5]
        if row.get("reason"):
            merged["why_you"] = str(row["reason"]).strip()
        if row.get("project_value"):
            merged["project_value"] = str(row["project_value"]).strip()
        merged["recommend"] = bool(row.get("recommend")) and row.get("priority") != "skip"
        merged["priority"] = row.get("priority") or "normal"
        if row.get("score") is not None:
            try:
                merged["score"] = int(round(100 * float(row["score"])))
            except (TypeError, ValueError):
                pass
        merged["via"] = "llm"
        out.append(merged)
        seen.add(item_id)
    for row in items:
        if row.get("id") not in seen:
            extra = dict(row)
            extra.setdefault("recommend", extra.get("score", 0) >= 70)
            extra.setdefault("priority", "high" if extra.get("score", 0) >= 85 else "normal")
            out.append(extra)
    out.sort(key=lambda row: -int(row.get("score") or 0))
    return out


def pick_push(items: list[dict[str, Any]], already: list[str], limit: int = 2) -> list[dict[str, Any]]:
    picked = []
    for row in items:
        if row.get("id") in already:
            continue
        if not row.get("recommend") and int(row.get("score") or 0) < 78:
            continue
        if row.get("priority") == "skip":
            continue
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def freshness(published_at: str) -> float:
    when = _parse_time(published_at)
    if not when:
        return 0.45
    hours = max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 3600)
    if hours <= 24:
        return 1.0
    if hours <= 72:
        return 0.8
    if hours <= 168:
        return 0.6
    if hours <= 720:
        return 0.3
    return 0.15


def _heuristic_decide(items: list[dict[str, Any]], already: list[str]) -> list[dict[str, Any]]:
    out = []
    for row in items:
        extra = dict(row)
        extra["recommend"] = extra.get("id") not in already and int(extra.get("score") or 0) >= 70
        extra["priority"] = "high" if int(extra.get("score") or 0) >= 85 else "normal"
        extra.setdefault("via", "heuristic")
        out.append(extra)
    return out


def _quality(item: dict[str, Any]) -> float:
    name = str(item.get("source_name") or "").lower()
    trust = 0.5
    for key, value in SOURCE_TRUST.items():
        if key in name or key in str(item.get("source_id") or "").lower():
            trust = max(trust, value)
    depth = float(item.get("technical_depth") or 0.5)
    importance = float(item.get("importance") or 0.5)
    return 0.4 * trust + 0.35 * depth + 0.25 * importance


def _feedback(item: dict[str, Any], behavior: dict[str, Any]) -> float:
    score = 0.55
    disliked = [str(x).lower() for x in (behavior.get("disliked_topics") or [])]
    blob = _blob(item)
    if any(topic and topic in blob for topic in disliked):
        score -= 0.4
    type_weights = behavior.get("type_weights") or {}
    item_type = item.get("item_type") or item.get("content_type") or "article"
    if item_type in type_weights:
        score = 0.5 * score + 0.5 * float(type_weights[item_type])
    source_weights = behavior.get("source_weights") or {}
    source_name = item.get("source_name") or ""
    if source_name in source_weights:
        score = 0.7 * score + 0.3 * float(source_weights[source_name])
    return max(0.0, min(1.0, score))


def _why(item: dict[str, Any], ctx: dict[str, Any], parts: dict[str, Any]) -> str:
    matched = parts.get("matched") or []
    project = (ctx.get("project") or {}).get("project") or "当前项目"
    if parts.get("project", 0) >= 0.8 and matched:
        return f"你正在做 {project}，这条命中了 { ' / '.join(matched[:3]) }。"
    if matched:
        return f"近期兴趣里 {matched[0]} 权重较高，和这条对得上。"
    return f"来自你订阅的 {item.get('source_name')}。"


def _project_hint(item: dict[str, Any], ctx: dict[str, Any], parts: dict[str, Any]) -> str:
    if parts.get("project", 0) < 0.8:
        return ""
    stage = (ctx.get("project") or {}).get("stage") or "当前阶段"
    points = item.get("innovation") or []
    if points:
        return f"当前处在{stage}，可看：{'；'.join(str(x) for x in points[:2])}"
    return f"当前处在{stage}，值得对照方案里的 Memory / 主动推送设计。"


def _blob(item: dict[str, Any]) -> str:
    bits = [
        item.get("title"),
        item.get("summary"),
        item.get("summary_zh"),
        " ".join(item.get("tags") or []),
        " ".join(item.get("keywords") or []),
    ]
    return " ".join(str(x) for x in bits if x).lower()


def _overlap(blob: str, topic: str) -> bool:
    needle = topic.lower().strip()
    if not needle:
        return False
    if needle in blob:
        return True
    tokens = [t for t in re.split(r"[\s/_-]+", needle) if len(t) > 2]
    return bool(tokens) and all(token in blob for token in tokens)


def _jaccard(left: str, right: str) -> float:
    a = set(re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", left.lower()))
    b = set(re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", right.lower()))
    if not a or not b:
        return 0.15
    return len(a & b) / len(a | b)


def _parse_time(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
