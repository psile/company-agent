"""可选写入 VehicleMem。失败不影响本地成卡。"""

from __future__ import annotations

import os
import sys
from typing import Any


def remember_fact(user_id: str, fact: str) -> dict[str, Any]:
    root = os.environ.get("VEHICLEMEM_ROOT", r"D:\agent memory\code\VehicleMem")
    if not os.path.isdir(root):
        return {"ok": False, "reason": "VehicleMem path missing"}
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from factory import create_memory

        memory = create_memory(
            {
                "mode": "edge",
                "user_id": user_id,
                "data_dir": os.environ.get("VEHICLEMEM_DATA", os.path.join(root, "..", "data", "radar_mem")),
            }
        )
        result = memory.remember_user_fact(fact, user_id)
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
