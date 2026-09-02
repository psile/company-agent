"""Match tasks/knowledge to the current project. Skills never write files."""

from __future__ import annotations

import re
from typing import Any

STATUS_LABEL = {
    "todo": "待办",
    "in_progress": "进行中",
    "blocked": "阻塞",
    "done": "完成",
    "cancelled": "取消",
}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").lower())


def belongs_to_project(row: dict[str, Any], project: dict[str, Any]) -> bool:
    name = str(project.get("project") or "").strip()
    pid = str(project.get("project_id") or "").strip()
    row_name = str(row.get("project") or "").strip()
    row_id = str(row.get("project_id") or "").strip()
    if not row_name and not row_id:
        return True
    if name and row_name and (name in row_name or row_name in name):
        return True
    if pid and row_id and pid == row_id:
        return True
    n_name, n_row, n_id = norm(name), norm(row_name), norm(row_id)
    if n_name and n_row and (n_name in n_row or n_row in n_name):
        return True
    name_parts = {part for part in re.split(r"[\s/\-_]+", name.lower()) if len(part) >= 4}
    id_parts = {part for part in re.split(r"[\s/\-_]+", (row_id or pid).lower()) if len(part) >= 4}
    if name_parts and id_parts and (name_parts & id_parts):
        return True
    if n_id and n_name and (n_id in n_name or n_name[:8] in n_id):
        return True
    return False


def knowledge_matches(card: dict[str, Any], project: dict[str, Any]) -> bool:
    blob = " ".join(
        [
            str(card.get("title") or ""),
            str(card.get("category") or ""),
            str(card.get("summary") or card.get("summary_zh") or ""),
            " ".join(str(tag) for tag in (card.get("tags") or [])),
        ]
    ).lower()
    if not blob.strip():
        return False
    needles = [str(topic).lower() for topic in (project.get("topics") or []) if str(topic).strip()]
    name = str(project.get("project") or "").lower()
    needles.extend(part for part in re.split(r"[\s/]+", name) if len(part) >= 4)
    return any(token and token.lower() in blob for token in needles)
