"""Repository 抽象层：统一数据访问接口，支持 JSON/SQLite 存储切换"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Repository(ABC):
    """数据仓库抽象基类"""

    @abstractmethod
    def create(self, data: dict[str, Any], user_id: str) -> dict[str, Any]:
        """创建一条记录，必须带 user_id"""
        pass

    @abstractmethod
    def get(self, user_id: str, record_id: str) -> dict[str, Any] | None:
        """按用户+ID获取记录（禁止不带user_id的查询）"""
        pass

    @abstractmethod
    def list(self, user_id: str, **filters: Any) -> list[dict[str, Any]]:
        """列出当前用户的记录，支持过滤"""
        pass

    @abstractmethod
    def update(self, user_id: str, record_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        """更新记录"""
        pass

    @abstractmethod
    def delete(self, user_id: str, record_id: str) -> bool:
        """删除记录"""
        pass


class JsonRepository(Repository):
    """基于JSON文件的Repository实现（现有逻辑改造）"""

    def __init__(self, root: Path, filename: str):
        self.root = root
        self.filename = filename
        self.path = root / filename
        if not self.path.exists():
            self._init_file()

    def _init_file(self):
        from radar.store import _write_json
        _write_json(self.path, {"items": []})

    def _read_items(self) -> list[dict[str, Any]]:
        from radar.store import _read_json
        data = _read_json(self.path, {"items": []})
        return data.get("items", [])

    def _save_items(self, items: list[dict[str, Any]]):
        from radar.store import _write_json
        _write_json(self.path, {"items": items})

    def create(self, data: dict[str, Any], user_id: str) -> dict[str, Any]:
        items = self._read_items()
        # 验证 user_id
        if data.get("user_id") != user_id:
            raise ValueError(f"User ID mismatch: {data.get('user_id')} vs {user_id}")
        # 生成ID（如果未提供）
        if not data.get("id"):
            from uuid import uuid4
            data["id"] = str(uuid4())[:12]
        items.append(data)
        self._save_items(items)
        return data

    def get(self, user_id: str, record_id: str) -> dict[str, Any] | None:
        items = self._read_items()
        for item in items:
            if item.get("id") == record_id and item.get("user_id") == user_id:
                return item
        return None

    def list(self, user_id: str, **filters: Any) -> list[dict[str, Any]]:
        items = self._read_items()
        result = [item for item in items if item.get("user_id") == user_id]
        # 应用过滤条件
        for key, value in filters.items():
            result = [item for item in result if item.get(key) == value]
        return result

    def update(self, user_id: str, record_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        items = self._read_items()
        for i, item in enumerate(items):
            if item.get("id") == record_id and item.get("user_id") == user_id:
                merged = dict(item)
                merged.update(patch)
                items[i] = merged
                self._save_items(items)
                return merged
        return None

    def delete(self, user_id: str, record_id: str) -> bool:
        items = self._read_items()
        before = len(items)
        items = [item for item in items if not (item.get("id") == record_id and item.get("user_id") == user_id)]
        if len(items) < before:
            self._save_items(items)
            return True
        return False


# 预创建的Repository实例（供Service使用）
tasks_repo: JsonRepository | None = None
reminders_repo: JsonRepository | None = None
work_events_repo: JsonRepository | None = None
work_notes_repo: JsonRepository | None = None
