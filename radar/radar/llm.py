"""OpenAI 兼容网关。密钥只走本机设置或环境变量，不写进仓库。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import load_env


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RADARME_CONFIG = Path(__file__).resolve().parents[2] / "RadarME" / "js" / "config.js"
_data_dir: Path | None = None

PRESETS: list[dict[str, str]] = [
    {
        "id": "siliconflow",
        "label": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V4-Flash",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    {
        "id": "local",
        "label": "本地网关",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "Qwen3.8-27B",
    },
]


def set_data_dir(path: Path | None) -> None:
    global _data_dir
    _data_dir = Path(path) if path else None


def _store_dir() -> Path:
    return _data_dir or DATA_DIR


def llm_status() -> dict[str, Any]:
    load_env()
    cfg = load_llm_config()
    return {
        "enabled": _llm_configured(cfg) and not _llm_off(),
        "settings_enabled": not _llm_off(),
        "model": cfg.get("model") or "",
        "base_url": cfg.get("base_url") or "",
        "source": cfg.get("source") or "none",
        "api_key_set": bool(cfg.get("api_key")),
    }


def public_llm_settings() -> dict[str, Any]:
    cfg = load_llm_config()
    key = str(cfg.get("api_key") or "")
    status = llm_status()
    return {
        "enabled": status["settings_enabled"],
        "active": status["enabled"],
        "base_url": status["base_url"],
        "model": status["model"],
        "api_key_set": status["api_key_set"],
        "api_key_preview": _mask_key(key),
        "source": status["source"],
        "presets": [dict(row) for row in PRESETS],
    }


def save_llm_settings(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    current = _read_saved()
    incoming_key = str(body.get("api_key") or "").strip()
    key = str(current.get("api_key") or "") if _keep_existing_key(incoming_key) else incoming_key
    if "enabled" in body:
        enabled = _as_bool(body.get("enabled"), True)
    elif "enabled" in current:
        enabled = bool(current["enabled"])
    else:
        enabled = True
    if "base_url" in body:
        base = str(body.get("base_url") or "").strip().rstrip("/")
    else:
        base = str(current.get("base_url") or "").strip().rstrip("/")
    if "model" in body:
        model = str(body.get("model") or "").strip()
    else:
        model = str(current.get("model") or "").strip()
    data = {
        "enabled": enabled,
        "base_url": base,
        "model": model,
        "api_key": key,
    }
    path = _store_dir() / "llm.json"
    from .store import _write_json

    _write_json(path, data)
    return public_llm_settings()


def test_llm_connection() -> dict[str, Any]:
    if _llm_off():
        return {"ok": False, "reason": "大模型已关闭，请先在设置里开启"}
    cfg = load_llm_config()
    if not _llm_configured(cfg):
        return {"ok": False, "reason": "请先填写网关地址；云端服务还需要 API Key"}
    reply = chat_text("You are a connectivity probe.", "只回复 ok", timeout=12, max_tokens=16)
    if not reply:
        return {"ok": False, "reason": "请求失败，请检查网关地址、模型名和 API Key"}
    return {"ok": True, "reply": reply[:120]}


def load_llm_config() -> dict[str, str]:
    load_env()
    saved = _read_saved()
    env_base = (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")
    env_key = (os.environ.get("LLM_API_KEY") or "").strip()
    env_model = (os.environ.get("LLM_MODEL") or "").strip()
    parsed = _parse_radarme_config()
    base = str(saved.get("base_url") or env_base or parsed.get("base_url") or "").strip().rstrip("/")
    key = str(saved.get("api_key") or env_key or parsed.get("api_key") or "").strip()
    model = str(saved.get("model") or env_model or parsed.get("model") or "").strip()
    if saved.get("base_url") or saved.get("api_key") or saved.get("model"):
        source = "settings"
    elif env_base or env_key or env_model:
        source = "env"
    elif parsed:
        source = "RadarME/js/config.js"
    else:
        source = "none"
    if not model:
        model = "Qwen3.8-27B"
    return {"base_url": base, "api_key": key, "model": model, "source": source}


def _is_local_gateway(base_url: str) -> bool:
    host = (base_url or "").lower()
    return any(token in host for token in ("127.0.0.1", "localhost", "0.0.0.0", "[::1]"))


def _llm_configured(cfg: dict[str, str] | None = None) -> bool:
    data = cfg or load_llm_config()
    if not data.get("base_url"):
        return False
    if data.get("api_key"):
        return True
    return _is_local_gateway(str(data.get("base_url") or ""))


def _llm_off() -> bool:
    saved = _read_saved()
    if "enabled" in saved:
        return not bool(saved["enabled"])
    return os.environ.get("RADAR_LLM", "1").strip().lower() in {"0", "false", "no", "off"}


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


def chat_text(system: str, user: str, timeout: int = 45, max_tokens: int | None = None) -> str:
    if _llm_off():
        return ""
    cfg = load_llm_config()
    if not _llm_configured(cfg):
        return ""
    url = cfg["base_url"] + "/chat/completions"
    payload: dict[str, Any] = {
        "model": cfg["model"],
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key'] or 'local'}",
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


def _read_saved() -> dict[str, Any]:
    path = _store_dir() / "llm.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {
        "base_url": str(data.get("base_url") or data.get("baseURL") or "").strip().rstrip("/"),
        "api_key": str(data.get("api_key") or data.get("apiKey") or "").strip(),
        "model": str(data.get("model") or "").strip(),
    }
    if "enabled" in data:
        out["enabled"] = _as_bool(data.get("enabled"), True)
    return out


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


def _mask_key(key: str) -> str:
    text = (key or "").strip()
    if not text:
        return ""
    if len(text) <= 6:
        return "••••" + text[-2:]
    return text[:3] + "••••" + text[-4:]


def _keep_existing_key(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    compact = text.replace(" ", "")
    if "•" in compact or compact.startswith("****") or compact in {"********", "unchanged"}:
        return True
    return False


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
