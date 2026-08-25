"""本地 / 云上 HTTP：Agent 工作台 + API。仅标准库。"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import get_bool, get_int, load_env
from .pipeline import RadarService
from .store import DEFAULT_PROFILE

load_env()
WEB = Path(os.environ.get("RADAR_WEB_DIR", Path(__file__).resolve().parents[1] / "web"))
HOST = os.environ.get("RADAR_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT") or os.environ.get("RADAR_PORT") or 8765)


def make_handler(service: RadarService):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            print("[radar]", fmt % args)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/health":
                st = service.status()
                return self._json(
                    200,
                    {
                        "ok": True,
                        "demo": st["demo"],
                        "llm": st["llm"].get("enabled"),
                        "model": st["llm"].get("model"),
                        "feishu": st["feishu"],
                        "feishu_channel": st.get("feishu_detail", {}).get("channel"),
                    },
                )
            if path == "/api/status":
                return self._json(200, service.status())
            if path == "/api/dashboard":
                return self._json(200, service.dashboard())
            if path == "/api/memory":
                return self._json(200, service._memory_snapshot())
            if path == "/api/profile":
                return self._json(200, service.memory.profile())
            if path == "/api/memory/profile":
                return self._json(200, service.user_memory.profile())
            if path == "/api/goals":
                return self._json(200, {"items": service.workspace.goals()})
            if path == "/api/push-settings":
                return self._json(200, service.workspace.push_settings())
            if path in {"/api/feeds/work", "/api/feeds/intel"}:
                return self._json(200, {"items": service.memory.feeds().get("intel", [])})
            if path in {"/api/feeds/personal", "/api/feeds/for-you", "/api/feeds/for_you"}:
                return self._json(200, {"items": service.memory.feeds().get("for_you", [])})
            if path == "/api/cards":
                return self._json(200, {"items": service.memory.cards()})
            if path == "/api/events":
                return self._json(200, {"items": service.memory.events()[:40]})
            return super().do_GET()

        def do_PUT(self) -> None:
            path = urlparse(self.path).path
            body = self._read_json()
            if path == "/api/profile":
                profile = service.memory.save_profile(body or DEFAULT_PROFILE)
                return self._json(200, profile)
            if path == "/api/memory/profile":
                return self._json(200, service.user_memory.save_profile(body or {}))
            if path == "/api/project":
                return self._json(200, service.user_memory.save_project(body or {}))
            if path == "/api/interests":
                return self._json(200, {"items": service.user_memory.save_interests(body.get("items") or [])})
            if path == "/api/goals":
                return self._json(200, {"items": service.save_goals(body.get("items") or [])})
            if path == "/api/products":
                return self._json(200, {"items": service.save_products(body.get("items") or [])})
            if path == "/api/push-settings":
                return self._json(200, service.save_push_settings(body or {}))
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path in {"/api/refresh", "/api/feeds/work/refresh", "/api/feeds/personal/refresh"}:
                    result = service.refresh()
                    return self._json(200, result)
                if path == "/api/events":
                    body = self._read_json()
                    out = service.track(
                        body["id"],
                        body.get("action", "open"),
                        int(body.get("dwell_ms") or 0),
                    )
                    return self._json(200, out)
                if path == "/api/items/feedback":
                    body = self._read_json()
                    out = service.feedback(body["id"], body.get("channel", "work"), body.get("action", "useful"))
                    return self._json(200, out)
                if path == "/api/follows":
                    body = self._read_json()
                    return self._json(200, service.add_follow(body.get("text") or "", body.get("topic") or "", float(body.get("weight") or 0.86)))
                if path == "/api/cards/move":
                    body = self._read_json()
                    return self._json(200, service.move_card(body.get("id") or body.get("source_url") or "", body.get("category") or "待整理"))
                if path == "/api/push/feishu":
                    return self._json(200, service.push_top_work())
            except KeyError as exc:
                return self._json(404, {"error": f"item not found: {exc}"})
            except Exception as exc:
                return self._json(500, {"error": str(exc)})
            self._json(404, {"error": "not found"})

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _json(self, code: int, payload: Any) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return Handler


def start_observer(service: RadarService) -> None:
    minutes = get_int("RADAR_OBSERVE_MINUTES", 180)
    on_start = get_bool("RADAR_OBSERVE_ON_START", False)
    if minutes <= 0 and not on_start:
        print("[observe] 定时感知关闭（RADAR_OBSERVE_MINUTES=0）")
        return

    def loop() -> None:
        if on_start:
            time.sleep(4)
            try:
                print("[observe] 启动后采集")
                service.refresh()
            except Exception as exc:
                print("[observe]", exc)
        if minutes <= 0:
            return
        while True:
            time.sleep(max(60, minutes * 60))
            try:
                print("[observe] 定时采集")
                service.refresh()
            except Exception as exc:
                print("[observe]", exc)

    threading.Thread(target=loop, daemon=True, name="radar-observe").start()
    print(f"[observe] 后台感知 interval={minutes}m on_start={int(on_start)}")


def serve(host: str = HOST, port: int = PORT) -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    service = RadarService()
    start_observer(service)
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"个人工作秘书 Agent  http://{host}:{port}/")
    print("Remember · Observe · Act  |  采集 → 理解 → 记忆 → 推荐 → 推送 → 反馈")
    httpd.serve_forever()
