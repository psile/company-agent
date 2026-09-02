"""统一信息条目。没有 source_url 不准进候选池。"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


def item_id(url: str) -> str:
    return hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]


@dataclass
class RawItem:
    source_id: str
    source_name: str
    channel: str  # 源侧提示，不再作为两套独立模块
    title: str
    summary: str
    source_url: str
    published_at: str = ""
    item_type: str = "article"  # paper | release | blog | news | page
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = item_id(self.source_url)
        return data


@dataclass
class ScoredItem:
    """兼容旧飞书格式。新推送走 dict（含 summary_zh / tags）。"""

    id: str
    source_id: str
    source_name: str
    channel: str
    title: str
    summary: str
    source_url: str
    published_at: str
    score: int
    matched: list[str] = field(default_factory=list)
    why: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
