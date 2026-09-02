"""MemoryOS 结构：短期对话、中期页、长期画像。真 Memoryos 可选，失败不挡推荐。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import llm
from .store import LocalMemory, _uniq, _write_json


SHORT_CAP = 10


class HierarchicalMemory:
    """本地实现 MemoryOS 的三层账本；关键词仍写回 LocalMemory 供打分。"""

    def __init__(self, data_dir: Path, local: LocalMemory) -> None:
        self.local = local
        self.user_id = data_dir.name
        self.root = data_dir / "memoryos"
        self.user_dir = self.root
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.short_path = self.user_dir / "short_term.json"
        self.mid_path = self.user_dir / "mid_term.json"
        self.long_path = self.user_dir / "long_term_user.json"
        if not self.short_path.exists():
            self._write(self.short_path, [])
        if not self.mid_path.exists():
            self._write(self.mid_path, {"pages": []})
        if not self.long_path.exists():
            self._write(
                self.long_path,
                {"profile_summary": "", "knowledge": [], "updated_at": ""},
            )

    def snapshot(self) -> dict[str, Any]:
        short = self.short_term()
        mid = self.mid_term()
        long_term = self.long_term()
        remote = try_memoryos_status(self.user_id)
        return {
            "backend": "memoryos-local" + ("+pypi" if remote.get("ok") else ""),
            "memoryos": remote,
            "short_term": short[-8:],
            "mid_term": (mid.get("pages") or [])[-6:],
            "long_term": long_term,
            "profile": self.local.profile(),
        }

    def short_term(self) -> list[dict[str, Any]]:
        return list(self._read(self.short_path, []))

    def mid_term(self) -> dict[str, Any]:
        return self._read(self.mid_path, {"pages": []})

    def long_term(self) -> dict[str, Any]:
        return self._read(self.long_path, {"profile_summary": "", "knowledge": []})

    def add_memory(self, user_input: str, agent_response: str, meta: dict | None = None) -> dict[str, Any]:
        qa = {
            "user_input": user_input,
            "agent_response": agent_response,
            "timestamp": _now(),
            "meta": meta or {},
        }
        short = self.short_term()
        short.append(qa)
        overflow: list[dict] = []
        if len(short) > SHORT_CAP:
            overflow = short[:-SHORT_CAP]
            short = short[-SHORT_CAP:]
        self._write(self.short_path, short)
        if overflow:
            self._archive_to_mid(overflow)
        if len(short) >= SHORT_CAP or (meta or {}).get("promote"):
            self._maybe_update_long_term(short)
        remote = remember_via_memoryos(user_input, agent_response, self.user_id)
        return {"ok": True, "short_size": len(short), "memoryos": remote}

    def merge_keywords(self, channel: str, keywords: list[str], intent: str = "") -> dict[str, Any]:
        profile = self.local.profile()
        key = "work_keywords" if channel == "work" else "interest_keywords"
        merged = _uniq(list(keywords) + list(profile.get(key, [])))
        profile[key] = merged[:24]
        if intent:
            facts = list(profile.get("intents") or [])
            facts.insert(0, {"channel": channel, "intent": intent, "at": _now()})
            profile["intents"] = facts[:20]
        saved = self.local.save_profile(profile)
        long_term = self.long_term()
        knowledge = list(long_term.get("knowledge") or [])
        for word in keywords[:5]:
            fact = f"{channel}:{word}"
            if fact not in knowledge:
                knowledge.insert(0, fact)
        long_term["knowledge"] = knowledge[:80]
        if intent:
            long_term["profile_summary"] = _join_summary(long_term.get("profile_summary", ""), intent)
        self._write(self.long_path, long_term)
        return saved

    def _archive_to_mid(self, overflow: list[dict]) -> None:
        mid = self.mid_term()
        pages = list(mid.get("pages") or [])
        titles = [row.get("user_input", "")[:80] for row in overflow]
        pages.append(
            {
                "timestamp": _now(),
                "overview": "；".join(t for t in titles if t)[:400],
                "heat": len(overflow),
                "pairs": overflow,
            }
        )
        mid["pages"] = pages[-40:]
        self._write(self.mid_path, mid)

    def _maybe_update_long_term(self, short: list[dict]) -> None:
        history = "\n".join(
            f"用户：{row.get('user_input','')}\n秘书：{row.get('agent_response','')}"
            for row in short[-8:]
        )
        profile = self.local.profile()
        parsed = llm.chat_json(
            "你是记忆系统的长期画像模块，结构对齐 MemoryOS 的 user profile。"
            "根据近期交互，用中文写一份不超过 120 字的画像，工作兴趣必须分开。"
            '只返回 JSON：{"summary":"...","work_keywords":[],"interest_keywords":[]}',
            f"当前工作词：{profile.get('work_keywords')}\n"
            f"当前兴趣词：{profile.get('interest_keywords')}\n"
            f"近期交互：\n{history}",
            timeout=40,
        )
        if not parsed:
            return
        summary = str(parsed.get("summary") or "").strip()
        long_term = self.long_term()
        if summary:
            long_term["profile_summary"] = summary
            long_term["updated_at"] = _now()
            self._write(self.long_path, long_term)
        work = [str(x).strip() for x in (parsed.get("work_keywords") or []) if str(x).strip()]
        interest = [str(x).strip() for x in (parsed.get("interest_keywords") or []) if str(x).strip()]
        if work:
            self.merge_keywords("work", work)
        if interest:
            self.merge_keywords("interest", interest)

    def _read(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _write(self, path: Path, payload: Any) -> None:
        _write_json(path, payload)


def try_memoryos_status(user_id: str = "me") -> dict[str, Any]:
    if os.environ.get("MEMORYOS_ENABLED", "").strip() not in {"1", "true", "yes"}:
        return {"ok": False, "reason": "MEMORYOS_ENABLED not set; using local hierarchy"}
    loaded = _load_memoryos_instance(user_id)
    return {"ok": bool(loaded.get("ok")), "reason": loaded.get("reason", "")}


def remember_via_memoryos(user_input: str, agent_response: str, user_id: str = "me") -> dict[str, Any]:
    if os.environ.get("MEMORYOS_ENABLED", "").strip() not in {"1", "true", "yes"}:
        return {"ok": False, "reason": "disabled"}
    if user_input == "__status__":
        return _load_memoryos_instance(user_id)
    loaded = _load_memoryos_instance(user_id)
    if not loaded.get("ok"):
        return loaded
    try:
        loaded["instance"].add_memory(user_input, agent_response)
        summary = ""
        inst = loaded["instance"]
        if hasattr(inst, "get_user_profile_summary"):
            summary = inst.get_user_profile_summary()
        return {"ok": True, "profile_summary": summary}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


_MEMORYOS_BY_USER: dict[str, dict[str, Any]] = {}


def _load_memoryos_instance(user_id: str = "me") -> dict[str, Any]:
    uid = (user_id or "me").strip() or "me"
    if uid in _MEMORYOS_BY_USER:
        return _MEMORYOS_BY_USER[uid]
    root = os.environ.get("MEMORYOS_ROOT", r"D:\agent memory\code\MemoryOS\memoryos-pypi")
    if not os.path.isdir(root):
        _MEMORYOS_BY_USER[uid] = {"ok": False, "reason": "MEMORYOS_ROOT missing"}
        return _MEMORYOS_BY_USER[uid]
    if root not in sys.path:
        sys.path.insert(0, root)
    cfg = llm.load_llm_config()
    if not cfg.get("api_key"):
        _MEMORYOS_BY_USER[uid] = {"ok": False, "reason": "LLM key missing for MemoryOS"}
        return _MEMORYOS_BY_USER[uid]
    try:
        from memoryos import Memoryos

        data_dir = os.environ.get(
            "MEMORYOS_DATA",
            str(Path(__file__).resolve().parents[1] / "data" / "memoryos_pypi"),
        )
        inst = Memoryos(
            user_id=uid,
            openai_api_key=cfg["api_key"],
            data_storage_path=data_dir,
            openai_base_url=cfg.get("base_url") or None,
            llm_model=cfg.get("model") or "gpt-4o-mini",
        )
        _MEMORYOS_BY_USER[uid] = {"ok": True, "instance": inst}
        return _MEMORYOS_BY_USER[uid]
    except Exception as exc:
        _MEMORYOS_BY_USER[uid] = {"ok": False, "reason": str(exc)}
        return _MEMORYOS_BY_USER[uid]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _join_summary(old: str, intent: str) -> str:
    parts = [p for p in [intent.strip(), (old or "").strip()] if p]
    return "；".join(parts)[:400]
