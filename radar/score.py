"""相关度：工作词只打工作条，兴趣词只打兴趣条。"""

from __future__ import annotations

import hashlib

from .models import RawItem, ScoredItem


def score_items(raw: list[RawItem], work_keywords: list[str], interest_keywords: list[str]) -> list[ScoredItem]:
    scored: list[ScoredItem] = []
    for item in raw:
        keywords = work_keywords if item.channel == "work" else interest_keywords
        points, matched = _match(item, keywords)
        why = _why(item, matched)
        scored.append(
            ScoredItem(
                id=_item_id(item.source_url),
                source_id=item.source_id,
                source_name=item.source_name,
                channel=item.channel,
                title=item.title,
                summary=item.summary,
                source_url=item.source_url,
                published_at=item.published_at,
                score=points,
                matched=matched,
                why=why,
            )
        )
    scored.sort(key=lambda row: -row.score)
    return scored


def for_channel(items: list[ScoredItem], channel: str, limit: int = 8) -> list[ScoredItem]:
    return [item for item in items if item.channel == channel][:limit]


def _match(item: RawItem, keywords: list[str]) -> tuple[int, list[str]]:
    blob = f"{item.title} {item.summary}".lower()
    matched = [kw for kw in keywords if kw and kw.lower() in blob]
    # 订阅源本身已表达关注，保底分，避免「一个词都没命中就整页空白」
    points = 42
    points += min(48, 16 * len(matched))
    if item.published_at:
        points = min(99, points + 4)
    return points, matched


def _why(item: RawItem, matched: list[str]) -> str:
    if matched:
        return f"为何推：命中 { ' / '.join(matched[:4]) }；来源 {item.source_name}"
    return f"为何推：你订阅了 {item.source_name}"


def _item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
