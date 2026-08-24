"""OpenAI 兼容网关。密钥只走环境变量或本机已有配置，不写进仓库。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RADARME_CONFIG = Path(__file__).resolve().parents[2] / "RadarME" / "js" / "config.js"


def llm_status() -> dict[str, Any]:
    cfg = load_llm_config()
    off = os.environ.get("RADAR_LLM", "1").strip().lower() in {"0", "false", "no", "off"}
    return {
        "enabled": bool(cfg.get("api_key") and cfg.get("base_url")) and not off,
        "model": cfg.get("model") or "",
        "base_url": cfg.get("base_url") or "",
        "source": cfg.get("source") or "none",
    }


def load_llm_config() -> dict[str, str]:
    base = (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("LLM_API_KEY") or "").strip()
    model = (os.environ.get("LLM_MODEL") or "").strip()
    source = "env"
    if not (base and key):
        local = _read_local_json()
        if local:
            base = base or local.get("base_url", "")
            key = key or local.get("api_key", "")
            model = model or local.get("model", "")
            source = "data/llm.json"
    if not (base and key):
        parsed = _parse_radarme_config()
        if parsed:
            base = base or parsed.get("base_url", "")
            key = key or parsed.get("api_key", "")
            model = model or parsed.get("model", "")
            source = "RadarME/js/config.js"
    if not model:
        model = "Qwen3.8-27B"
    return {"base_url": base, "api_key": key, "model": model, "source": source}


def chat_json(system: str, user: str, timeout: int = 45) -> dict[str, Any] | None:
    raw = chat_text(system, user, timeout=timeout)
    if not raw:
        return None
    return parse_json_payload(raw)


def parse_json_payload(text: str) -> dict[str, Any] | None:
    parsed = _loads_json(text)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"items": parsed}
    return None


def parse_json_object(text: str) -> dict[str, Any] | None:
    parsed = parse_json_payload(text)
    return parsed if isinstance(parsed, dict) else None


def _loads_json(text: str) -> Any:
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    else:
        obj = cleaned.find("{")
        arr = cleaned.find("[")
        starts = [i for i in (obj, arr) if i >= 0]
        if starts:
            start = min(starts)
            end_ch = "]" if cleaned[start] == "[" else "}"
            end = cleaned.rfind(end_ch)
            if end > start:
                cleaned = cleaned[start : end + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def chat_text(system: str, user: str, timeout: int = 45) -> str:
    if os.environ.get("RADAR_LLM", "1").strip().lower() in {"0", "false", "no", "off"}:
        return ""
    cfg = load_llm_config()
    if not cfg["api_key"] or not cfg["base_url"]:
        return ""
    url = cfg["base_url"] + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[llm] request failed: {exc}")
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content") or "").strip()


def _read_local_json() -> dict[str, str]:
    path = DATA_DIR / "llm.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        "base_url": str(data.get("base_url") or data.get("baseURL") or "").strip().rstrip("/"),
        "api_key": str(data.get("api_key") or data.get("apiKey") or "").strip(),
        "model": str(data.get("model") or "").strip(),
    }


def _parse_radarme_config() -> dict[str, str]:
    if not RADARME_CONFIG.exists():
        return {}
    try:
        text = RADARME_CONFIG.read_text(encoding="utf-8")
    except OSError:
        return {}
    base = _js_string(text, "baseURL")
    key = _js_string(text, "apiKey")
    model = _js_string(text, "model")
    if not (base and key):
        return {}
    return {"base_url": base.rstrip("/"), "api_key": key, "model": model}


def _js_string(text: str, field: str) -> str:
    match = re.search(rf'{field}\s*:\s*"([^"]+)"', text)
    return match.group(1).strip() if match else ""
