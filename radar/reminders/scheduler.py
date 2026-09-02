"""Background reminder scan. Isolated per user_id; Feishu stays in Channel."""

from __future__ import annotations

import threading
import time
from typing import Any

from ..config import get_bool, get_int
from .service import evaluate_all


def tick(service: Any, now=None) -> list[dict[str, Any]]:
    return evaluate_all(service, now=now)


def start_reminder_loop(service: Any) -> None:
    minutes = get_int("RADAR_REMIND_MINUTES", 1)
    on_start = get_bool("RADAR_REMIND_ON_START", True)
    if minutes <= 0 and not on_start:
        print("[remind] 定时提醒关闭（RADAR_REMIND_MINUTES=0）")
        return

    def loop() -> None:
        if on_start:
            time.sleep(6)
            try:
                fired = tick(service)
                print(f"[remind] 启动扫描 sent={len(fired)}")
            except Exception as exc:
                print("[remind]", exc)
        if minutes <= 0:
            return
        while True:
            time.sleep(max(30, minutes * 60))
            try:
                fired = tick(service)
                if fired:
                    print(f"[remind] 定时扫描 sent={len(fired)}")
            except Exception as exc:
                print("[remind]", exc)

    threading.Thread(target=loop, daemon=True, name="radar-remind").start()
    print(f"[remind] 后台提醒 interval={minutes}m on_start={int(on_start)}")
