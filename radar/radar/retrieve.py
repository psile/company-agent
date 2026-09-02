"""Query-conditioned memory recall. Lexical + synonym expansion; no vector DB required."""

from __future__ import annotations

import re
from typing import Any

SELF_QUERY = re.compile(
    r"(我最近|我主要|我在做|研究什么|在做什么|记得什么|你还记得|我的记忆|我是谁|当前项目|我的项目)",
    re.I,
)
WORD_RE = re.compile(r"[a-z0-9]{2,}", re.I)
HAN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset(
        {
            "agent memory",
            "长期记忆",
            "记忆系统",
            "memory skill",
            "temporal memory",
            "long-term memory",
            "long term memory",
            "mem0",
            "memos",
            "memoryos",
            "用户记忆",
        }
    ),
    frozenset({"rag", "检索增强", "检索增强生成", "retrieval-augmented"}),
    frozenset({"vllm", "推理引擎", "推理服务"}),
    frozenset({"personal agent", "个人秘书", "个人 ai 秘书", "工作秘书", "personal work secretary"}),
    frozenset({"world model", "世界模型"}),
    frozenset({"proactive", "主动推送", "主动服务", "proactive agent"}),
    frozenset({"multimodal", "多模态", "vlm"}),
)


def normalize(text: str) -> str:
    return re.sub(r"[-_/]+", " ", (text or "").lower()).strip()


def tokens(text: str) -> set[str]:
    blob = normalize(text)
    out: set[str] = set(WORD_RE.findall(blob))
    for run in HAN_RE.findall(blob):
        out.add(run)
        if len(run) >= 2:
            out.update(run[i : i + 2] for i in range(len(run) - 1))
    return {item for item in out if item}


def expand_terms(text: str) -> set[str]:
    blob = normalize(text)
    found = set(tokens(text))
    if blob:
        found.add(blob)
    for group in SYNONYM_GROUPS:
        if any(term in blob or blob in term for term in group if len(term) >= 2):
            found.update(group)
            for term in group:
                found.update(tokens(term))
    return found


def text_similarity(left: str, right: str) -> float:
    a = normalize(left)
    b = normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92 if min(len(a), len(b)) >= 4 else 0.8
    ta, tb = tokens(a), tokens(b)
    jaccard = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    ea, eb = expand_terms(a), expand_terms(b)
    overlap = (len(ea & eb) / max(1, min(len(ea), len(eb)))) if ea and eb else 0.0
    alias = 0.72 if overlap >= 0.2 and (ea & eb) - (ta & tb) else overlap * 0.55
    return max(jaccard, alias, overlap * 0.5)


def related(left: str, right: str, threshold: float = 0.28) -> bool:
    return text_similarity(left, right) >= threshold


def _unit(kind: str, text: str, ref: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    clean = " ".join(str(text or "").split())
    if not clean:
        return None
    row = {"kind": kind, "text": clean[:400], "ref": ref}
    if extra:
        row.update(extra)
    return row


def collect_units(scope: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ctx = scope.user_memory.context()
    profile = ctx.get("profile") or {}
    rows.append(
        _unit(
            "profile",
            " ".join(
                str(profile.get(key) or "")
                for key in ("display_name", "role", "bio", "team")
            ),
            "profile",
        )
    )
    project = ctx.get("project") or {}
    rows.append(
        _unit(
            "project",
            " ".join(
                [str(project.get("project") or ""), str(project.get("stage") or "")]
                + [str(x) for x in (project.get("topics") or [])]
            ),
            "project",
            {"project": project},
        )
    )
    for item in ctx.get("interests") or []:
        topic = str(item.get("topic") or "")
        rows.append(_unit("interest", topic, topic, {"weight": item.get("weight")}))
    hierarchy = scope.hierarchy
    long_term = hierarchy.long_term()
    rows.append(_unit("long_term", str(long_term.get("profile_summary") or ""), "long_term"))
    for fact in long_term.get("knowledge") or []:
        rows.append(_unit("fact", str(fact), "fact"))
    for item in hierarchy.short_term()[-12:]:
        rows.append(
            _unit(
                "short_term",
                f"{item.get('user_input') or ''} {item.get('agent_response') or ''}",
                "short_term",
            )
        )
    for page in (hierarchy.mid_term().get("pages") or [])[-8:]:
        rows.append(_unit("mid_term", str(page.get("overview") or ""), "mid_term"))
    for goal in scope.workspace.goals()[:12]:
        rows.append(_unit("goal", str(goal.get("title") or ""), str(goal.get("id") or "")))
    work = getattr(scope, "work", None)
    if work is not None:
        for task in work.tasks(include_done=False)[:16]:
            rows.append(
                _unit(
                    "task",
                    f"{task.get('title') or ''} {task.get('description') or ''} {task.get('project') or ''}",
                    str(task.get("id") or ""),
                )
            )
        for note in work.notes()[:10]:
            rows.append(_unit("note", str(note.get("content") or note.get("title") or ""), str(note.get("id") or "")))
    for card in scope.memory.cards()[:30]:
        rows.append(
            _unit(
                "knowledge",
                f"{card.get('title') or ''} {card.get('summary') or ''} {' '.join(card.get('tags') or [])}",
                str(card.get("id") or card.get("source_url") or ""),
            )
        )
    return [row for row in rows if row]


def _salience(unit: dict[str, Any]) -> float:
    kind = unit.get("kind")
    if kind == "project":
        return 0.22
    if kind == "interest":
        return 0.08 + 0.12 * float(unit.get("weight") or 0)
    if kind in {"task", "goal"}:
        return 0.1
    if kind in {"long_term", "profile"}:
        return 0.12
    return 0.04


def is_self_query(query: str) -> bool:
    text = (query or "").strip()
    if not text:
        return True
    return bool(SELF_QUERY.search(text)) and len(tokens(text)) <= 12


def retrieve(scope: Any, query: str, limit: int = 8) -> list[dict[str, Any]]:
    units = collect_units(scope)
    needle = (query or "").strip()
    scored: list[dict[str, Any]] = []
    for unit in units:
        sim = text_similarity(needle, unit["text"]) if needle and not is_self_query(needle) else 0.0
        score = sim + _salience(unit)
        if needle and not is_self_query(needle):
            score = sim if sim >= 0.22 else (0.0 if sim < 0.16 else sim * 0.5)
            if score <= 0:
                continue
        scored.append({**unit, "score": round(score, 3)})
    scored.sort(key=lambda row: -float(row.get("score") or 0))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in scored:
        key = f"{row.get('kind')}:{row.get('text')[:80]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def public_hits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": row.get("kind") or "",
            "text": row.get("text") or "",
            "score": row.get("score") or 0,
            "ref": row.get("ref") or "",
        }
        for row in rows
    ]
