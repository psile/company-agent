"""知乎 OpenAPI 密钥管理。密钥只保存在本机 data/{user}/zhihu.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import _read_json, _write_json


def load_zhihu_config(user_id: str) -> dict[str, str]:
    path = Path("data") / "users" / user_id / "zhihu.json"
    saved = _read_json(path, {})
    env_secret = (Path(".env").read_text(encoding="utf-8") if Path(".env").exists() else "").splitlines()
    env_key = ""
    for line in env_secret:
        if line.startswith("ZHIHU_ACCESS_SECRET="):
            env_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    secret = str(saved.get("secret") or env_key or "").strip()
    base_url = str(saved.get("base_url") or "https://developer.zhihu.com").strip().rstrip("/")
    source = "settings" if saved.get("secret") else ("env" if env_key else "none")
    return {"secret": secret, "base_url": base_url, "source": source}


def public_zhihu_settings(user_id: str) -> dict[str, Any]:
    cfg = load_zhihu_config(user_id)
    key = cfg.get("secret") or ""
    return {
        "enabled": bool(key),
        "active": bool(key),
        "secret_set": bool(key),
        "secret_preview": _mask_key(key),
        "base_url": cfg.get("base_url", ""),
        "source": cfg.get("source", "none"),
    }


def save_zhihu_settings(user_id: str, payload: dict | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    path = Path("data") / "users" / user_id / "zhihu.json"
    current = _read_json(path, {})
    incoming_secret = str(body.get("secret") or "").strip()
    secret = current.get("secret", "") if _keep_existing_key(incoming_secret) else incoming_secret
    base_url = str(body.get("base_url") or str(current.get("base_url") or "https://developer.zhihu.com")).strip().rstrip("/")
    data = {"secret": secret, "base_url": base_url}
    _write_json(path, data)
    return public_zhihu_settings(user_id)


def test_zhihu_connection(user_id: str) -> dict[str, Any]:
    from .config import get_str
    import urllib.request, urllib.parse

    cfg = load_zhihu_config(user_id)
    secret = cfg.get("secret", "")
    base_url = cfg.get("base_url", "https://developer.zhihu.com").rstrip("/")
    if not secret:
        return {"ok": False, "reason": "请先填写知乎 Secret"}
    try:
        import time as _time

        params = urllib.parse.urlencode({"Query": "测试", "Count": 1})
        url = f"{base_url}/api/v1/content/global_search?{params}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {secret}",
            "X-Request-Timestamp": str(int(_time.time())),
            "Accept": "application/json",
            "User-Agent": "RadarME-secretary-demo/0.1",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            code = data.get("Code", data.get("code", 0))
            if code in (0, "0"):
                return {"ok": True, "reply": "知乎搜索 API 连通正常"}
            return {"ok": False, "reason": f"API 返回错误码: {code}"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:120]}


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
