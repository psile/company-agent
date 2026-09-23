"""把 Web / 飞书外部身份解析成内部 user_id。业务层只认 user.id。"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .store import _read_json, _write_json


DEFAULT_USER = "alice"
SESSION_DAYS = 14
PBKDF2_ROUNDS = 120_000
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")


class IdentityService:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "identity"
        self.users_path = self.root / "users.json"
        self.identities_path = self.root / "identities.json"
        self.channels_path = self.root / "channels.json"
        self.sessions_path = self.root / "sessions.json"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.users_path.exists():
            _write_json(self.users_path, {"items": []})
        if not self.identities_path.exists():
            _write_json(self.identities_path, {"items": []})
        if not self.channels_path.exists():
            _write_json(self.channels_path, {"items": []})
        if not self.sessions_path.exists():
            _write_json(self.sessions_path, {"items": []})

    def users(self) -> list[dict[str, Any]]:
        return list(_read_json(self.users_path, {"items": []}).get("items") or [])

    def identities(self) -> list[dict[str, Any]]:
        return list(_read_json(self.identities_path, {"items": []}).get("items") or [])

    def channels(self) -> list[dict[str, Any]]:
        return list(_read_json(self.channels_path, {"items": []}).get("items") or [])

    def default_id(self) -> str:
        ids = self.active_ids()
        return DEFAULT_USER if DEFAULT_USER in ids else (ids[0] if ids else DEFAULT_USER)

    def active_ids(self) -> list[str]:
        return [str(row["id"]) for row in self.users() if row.get("status") != "disabled" and row.get("id")]

    def get(self, user_id: str) -> dict[str, Any] | None:
        for row in self.users():
            if row.get("id") == user_id:
                return row
        return None

    def find_by_username(self, username: str) -> dict[str, Any] | None:
        needle = _normalize_username(username)
        if not needle:
            return None
        for row in self.users():
            if _normalize_username(str(row.get("username") or row.get("id") or "")) == needle:
                return row
        return None

    def public_user(self, user_id: str | None) -> dict[str, Any] | None:
        row = self.get(user_id or "")
        if not row:
            return None
        return _public_user(row)

    def require(self, user_id: str | None) -> str:
        uid = (user_id or "").strip() or self.default_id()
        if self.get(uid):
            return uid
        raise KeyError(uid)

    def resolve_user(self, provider: str, external_id: str, display_name: str | None = None) -> dict[str, Any]:
        provider = (provider or "").strip().lower()
        external_id = (external_id or "").strip()
        if not provider or not external_id:
            raise ValueError("provider and external_id required")
        for row in self.identities():
            if row.get("provider") == provider and str(row.get("external_id")) == external_id:
                user = self.get(str(row.get("user_id")))
                if user:
                    return _public_user(user)
        # 未绑定的外部身份不自动创建用户（安全：需 admin 先建账号并绑定）
        return None

    def ensure_user(
        self,
        user_id: str,
        display_name: str,
        identities: list[tuple[str, str]],
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        user = self.get(user_id)
        if not user:
            user = {
                "id": user_id,
                "username": _normalize_username(username or user_id) or user_id,
                "display_name": display_name,
                "avatar_url": "",
                "status": "active",
                "created_at": _now(),
                "updated_at": _now(),
            }
            rows = self.users()
            rows.append(user)
            _write_json(self.users_path, {"items": rows})
        patch: dict[str, Any] = {}
        if username and not user.get("username"):
            patch["username"] = _normalize_username(username) or user_id
        if password and not user.get("password_hash"):
            patch["password_hash"] = hash_password(password)
        if patch:
            self._patch_user(user_id, patch)
        for provider, external_id in identities:
            if not any(
                row.get("provider") == provider and str(row.get("external_id")) == external_id
                for row in self.identities()
            ):
                self._add_identity(user_id, provider, external_id)
            if not any(
                row.get("user_id") == user_id and row.get("channel_type") == provider
                for row in self.channels()
            ):
                self._add_channel(user_id, provider, external_id)
        return _public_user(self.get(user_id) or user)

    def register(self, username: str, password: str, display_name: str = "") -> dict[str, Any]:
        username = _normalize_username(username)
        if not USERNAME_RE.match(username or ""):
            raise ValueError("用户名需 3–32 位，字母开头，只能含小写字母、数字、下划线")
        if len(password or "") < 6:
            raise ValueError("密码至少 6 位")
        if self.find_by_username(username) or self.get(username):
            raise ValueError("用户名已被占用")
        user = {
            "id": username,
            "username": username,
            "display_name": (display_name or username).strip() or username,
            "avatar_url": "",
            "status": "active",
            "password_hash": hash_password(password),
            "created_at": _now(),
            "updated_at": _now(),
        }
        rows = self.users()
        rows.append(user)
        _write_json(self.users_path, {"items": rows})
        self._add_identity(username, "web", username)
        self._add_channel(username, "web", username)
        return _public_user(user)

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self.find_by_username(username) or self.get((username or "").strip())
        if not user or not verify_password(password or "", str(user.get("password_hash") or "")):
            raise ValueError("用户名或密码不正确")
        if user.get("status") == "disabled":
            raise ValueError("账号已停用")
        self._patch_user(str(user["id"]), {"last_login_at": _now()})
        token = self._create_session(str(user["id"]))
        return {"ok": True, "token": token, "user": _public_user(user)}

    def logout(self, token: str) -> None:
        token = (token or "").strip()
        if not token:
            return
        items = [row for row in self._sessions() if row.get("token") != token]
        _write_json(self.sessions_path, {"items": items})

    def user_id_for_session(self, token: str) -> str | None:
        token = (token or "").strip()
        if not token:
            return None
        now = datetime.now(timezone.utc)
        kept: list[dict[str, Any]] = []
        found: str | None = None
        dirty = False
        for row in self._sessions():
            expires = _parse_time(str(row.get("expires_at") or ""))
            if not expires or expires <= now:
                dirty = True
                continue
            kept.append(row)
            if row.get("token") == token:
                found = str(row.get("user_id") or "")
        if dirty:
            _write_json(self.sessions_path, {"items": kept})
        if found and self.get(found):
            return found
        return None

    def create_user(
        self,
        username: str,
        display_name: str = "",
        password: str = "",
        role: str = "user",
        email: str = "",
    ) -> dict[str, Any]:
        username = _normalize_username(username)
        if not USERNAME_RE.match(username or ""):
            raise ValueError("用户名需 3–32 位，字母开头，只能含小写字母、数字、下划线")
        if len(password or "") < 6:
            raise ValueError("密码至少 6 位")
        if self.find_by_username(username) or self.get(username):
            raise ValueError("用户名已被占用")
        user = {
            "id": f"u_{uuid4().hex[:8]}",
            "username": username,
            "display_name": (display_name or "").strip() or username,
            "email": (email or "").strip(),
            "avatar_url": "",
            "status": "active",
            "role": role,
            "must_change_password": True,
            "password_hash": hash_password(password),
            "created_at": _now(),
            "updated_at": _now(),
            "last_login_at": "",
        }
        rows = self.users()
        rows.append(user)
        _write_json(self.users_path, {"items": rows})
        return user

    def disable_user(self, user_id: str) -> None:
        self._patch_user(user_id, {"status": "disabled"})
        # 撤销该用户全部 session
        items = [row for row in self._sessions() if row.get("user_id") != user_id]
        _write_json(self.sessions_path, {"items": items})

    def enable_user(self, user_id: str) -> None:
        self._patch_user(user_id, {"status": "active"})

    def is_admin(self, user_id: str) -> bool:
        user = self.get(user_id)
        return bool(user and user.get("role") == "admin")

    def change_password(self, user_id: str, old_password: str, new_password: str) -> dict[str, Any]:
        user = self.get(user_id)
        if not user:
            raise KeyError(user_id)
        if len(new_password or "") < 6:
            raise ValueError("新密码至少 6 位")
        # 首次登录强制改密时（must_change_password）跳过旧密码校验
        if not user.get("must_change_password") and not verify_password(
            old_password or "", str(user.get("password_hash") or "")
        ):
            raise ValueError("当前密码不正确")
        self._patch_user(
            user_id,
            {"password_hash": hash_password(new_password), "must_change_password": False},
        )
        return {"ok": True}

    def _patch_user(self, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self.users()
        updated = None
        for index, row in enumerate(rows):
            if row.get("id") == user_id:
                merged = dict(row)
                merged.update(patch)
                merged["updated_at"] = _now()
                rows[index] = merged
                updated = merged
                break
        if not updated:
            raise KeyError(user_id)
        _write_json(self.users_path, {"items": rows})
        return updated

    def _sessions(self) -> list[dict[str, Any]]:
        return list(_read_json(self.sessions_path, {"items": []}).get("items") or [])

    def _create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        items = self._sessions()
        items.append(
            {
                "token": token,
                "user_id": user_id,
                "created_at": _now(),
                "expires_at": expires.isoformat(),
            }
        )
        _write_json(self.sessions_path, {"items": items[-200:]})
        return token

    def bind_identity(self, user_id: str, provider: str, external_id: str) -> dict[str, Any]:
        return self._add_identity(user_id, provider, external_id)

    def _add_identity(self, user_id: str, provider: str, external_id: str) -> dict[str, Any]:
        for row in self.identities():
            if row.get("provider") == provider and str(row.get("external_id")) == external_id:
                if row.get("user_id") != user_id:
                    raise ValueError("external identity already bound")
                return row
        row = {
            "id": uuid4().hex[:12],
            "user_id": user_id,
            "provider": provider,
            "external_id": external_id,
            "metadata": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
        items = self.identities()
        items.append(row)
        _write_json(self.identities_path, {"items": items})
        return row

    def _add_channel(self, user_id: str, channel_type: str, external_user_id: str) -> dict[str, Any]:
        row = {
            "id": uuid4().hex[:12],
            "user_id": user_id,
            "channel_type": channel_type,
            "external_user_id": external_user_id,
            "status": "enabled",
            "is_enabled": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        items = self.channels()
        items.append(row)
        _write_json(self.channels_path, {"items": items})
        return row


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    parts = (stored or "").split("$")
    if len(parts) != 3 or parts[0] != "pbkdf2":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), parts[1].encode("utf-8"), PBKDF2_ROUNDS).hex()
    return hmac.compare_digest(digest, parts[2])


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "username": row.get("username") or row.get("id"),
        "display_name": row.get("display_name") or row.get("username") or row.get("id"),
        "email": row.get("email") or "",
        "avatar_url": row.get("avatar_url") or "",
        "status": row.get("status") or "active",
        "role": row.get("role") or "user",
        "must_change_password": bool(row.get("must_change_password")),
        "last_login_at": row.get("last_login_at") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
        "has_password": bool(row.get("password_hash")),
    }


def _normalize_username(value: str) -> str:
    return (value or "").strip().lower()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None
