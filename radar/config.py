"""Small runtime configuration helpers.

Secrets stay outside git: environment variables win, then local .env files.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    for path in (ROOT / ".env", ROOT / "data" / ".env"):
        _load_env_file(path)
    _LOADED = True


def get_bool(name: str, default: bool = False) -> bool:
    load_env()
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name: str, default: int) -> int:
    load_env()
    try:
        return int(os.environ.get(name, "").strip())
    except ValueError:
        return default


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
