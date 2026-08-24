"""飞书自定义机器人 Webhook。未配置则只返回文案。推送用中文总结 + tag。"""

from __future__ import annotations

import json
import os
import urllib.request

from .models import ScoredItem


def format_card(item: ScoredItem) -> str:
    return format_push(item.to_dict() if hasattr(item, "to_dict") else item)  # type: ignore[arg-type]


def format_interest_card(item: ScoredItem) -> str:
    return format_push(item.to_dict())


def format_push(item: dict | ScoredItem) -> str:
    data = item.to_dict() if isinstance(item, ScoredItem) else item
    tags = " · ".join(str(x) for x in (data.get("tags") or data.get("matched") or [])[:5])
    summary = data.get("summary_zh") or data.get("summary") or ""
    why = data.get("why_you") or data.get("why") or ""
    project = data.get("project_value") or ""
    score = data.get("score") or 0
    lines = [
        f"【为你发现】{data.get('title')}",
        f"标签 {tags}" if tags else "",
        f"相关度 {score}%",
        f"总结：{summary}" if summary else "",
        f"为什么推给你：{why}" if why else "",
        f"和当前项目：{project}" if project else "",
        f"原文 {data.get('source_url')}",
    ]
    return "\n".join(line for line in lines if line)


def push_text(text: str) -> dict:
    url = (os.environ.get("FEISHU_WEBHOOK_URL") or "").strip()
    if not url:
        return {"ok": False, "reason": "FEISHU_WEBHOOK_URL not set", "text": text}
    body = json.dumps({"msg_type": "text", "content": {"text": text}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return {"ok": True, "response": raw, "text": text}
