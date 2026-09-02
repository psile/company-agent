"""从点击/交互抽兴趣意图，并让 LLM 决定要不要主动推飞书。"""

from __future__ import annotations

from typing import Any

from . import llm


EXTRACT_SYSTEM = (
    "你是个人工作秘书的画像模块，结构对齐 MemoryOS：短期交互沉淀成意图，再写入长期关键词。"
    "工作（论文、推理、Agent、vLLM、RAG）和兴趣（发布会、产品、消费级科技）必须分账。"
    "只返回 JSON。"
)

PUSH_SYSTEM = (
    "你是秘书的主动推送判断。宁缺毋滥。已经推过的不要再推。"
    "工作条只能作为工作提醒推；兴趣条只能作为兴趣发现推，不要写成待办。"
    "最多选 2 条。只返回 JSON。"
)


def extract_from_event(action: str, item: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    fallback = _heuristic_extract(action, item)
    parsed = llm.chat_json(
        EXTRACT_SYSTEM,
        (
            '返回 {"channel":"work"|"interest","keywords":["最多5个短词"],'
            '"intent":"一句话","weight":1-5}\n'
            f"动作：{action}\n"
            f"通道：{item.get('channel')}\n"
            f"标题：{item.get('title')}\n"
            f"摘要：{(item.get('summary') or '')[:400]}\n"
            f"来源：{item.get('source_name')}\n"
            f"当前工作词：{profile.get('work_keywords')}\n"
            f"当前兴趣词：{profile.get('interest_keywords')}\n"
        ),
        timeout=35,
    )
    if not parsed:
        return fallback
    channel = parsed.get("channel") if parsed.get("channel") in {"work", "interest"} else fallback["channel"]
    keywords = [str(x).strip() for x in (parsed.get("keywords") or []) if str(x).strip()][:5]
    if not keywords:
        keywords = fallback["keywords"]
    try:
        weight = int(parsed.get("weight") or fallback["weight"])
    except (TypeError, ValueError):
        weight = fallback["weight"]
    return {
        "channel": channel,
        "keywords": keywords,
        "intent": str(parsed.get("intent") or fallback["intent"]).strip()[:120],
        "weight": max(1, min(5, weight)),
        "via": "llm",
    }


def select_push(candidates: list[dict[str, Any]], profile: dict[str, Any], already: list[str], memory_summary: str) -> list[dict[str, Any]]:
    if not candidates:
        return []
    compact = [
        {
            "id": row.get("id"),
            "channel": row.get("channel"),
            "title": row.get("title"),
            "score": row.get("score"),
            "why": row.get("why"),
            "summary": (row.get("summary") or "")[:180],
        }
        for row in candidates
    ]
    parsed = llm.chat_json(
        PUSH_SYSTEM,
        (
            '返回 {"items":[{"id":"...","channel":"work"|"interest","reason":"...","urgency":"high"|"normal"}]}\n'
            f"画像工作词：{profile.get('work_keywords')}\n"
            f"画像兴趣词：{profile.get('interest_keywords')}\n"
            f"长期画像：{memory_summary or '暂无'}\n"
            f"已推送 id：{already[-30:]}\n"
            f"候选：{compact}\n"
        ),
        timeout=40,
    )
    if not parsed:
        return _heuristic_push(candidates, already)
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_id = {row.get("id"): row for row in candidates}
    for row in parsed.get("items") or []:
        item_id = str(row.get("id") or "")
        if not item_id or item_id in already or item_id in seen:
            continue
        item = by_id.get(item_id)
        if not item:
            continue
        channel = row.get("channel") if row.get("channel") in {"work", "interest"} else item.get("channel")
        if channel != item.get("channel"):
            continue
        picked.append(
            {
                "id": item_id,
                "channel": channel,
                "reason": str(row.get("reason") or item.get("why") or "").strip(),
                "urgency": "high" if row.get("urgency") == "high" else "normal",
                "item": item,
                "via": "llm",
            }
        )
        seen.add(item_id)
        if len(picked) >= 2:
            break
    return picked


def _heuristic_extract(action: str, item: dict[str, Any]) -> dict[str, Any]:
    channel = item.get("channel") if item.get("channel") in {"work", "interest"} else "interest"
    matched = [str(x) for x in (item.get("matched") or []) if str(x).strip()]
    title_bits = [w for w in str(item.get("title") or "").replace("/", " ").split() if 1 < len(w) <= 16][:3]
    keywords = _uniq_keep(matched + title_bits)[:5]
    weight = {"like": 5, "useful": 5, "open": 3, "dwell": 2, "skip": 1, "dismiss": 1}.get(action, 2)
    intent = f"{action}《{item.get('title','')}》"
    return {"channel": channel, "keywords": keywords, "intent": intent, "weight": weight, "via": "heuristic"}


def _heuristic_push(candidates: list[dict[str, Any]], already: list[str]) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for row in candidates:
        if row.get("id") in already:
            continue
        score = int(row.get("score") or 0)
        matched = list(row.get("matched") or [])
        if score < 70 and not matched:
            continue
        picked.append(
            {
                "id": row["id"],
                "channel": row.get("channel"),
                "reason": row.get("why") or "高相关订阅更新",
                "urgency": "high" if score >= 85 else "normal",
                "item": row,
                "via": "heuristic",
            }
        )
        if len(picked) >= 1:
            break
    return picked


def _uniq_keep(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = value.strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out
