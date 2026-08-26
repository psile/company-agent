"""本地 / 云上 HTTP：Agent 工作台 + API。仅标准库。"""

from __future__ import annotations

import asyncio
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
SESSION_COOKIE = "radar_session"


def make_handler(service: RadarService):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            print("[radar]", fmt % args)

        def _session_token(self) -> str:
            auth = self.headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                return auth.split(" ", 1)[1].strip()
            for part in (self.headers.get("Cookie") or "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == SESSION_COOKIE:
                    return value.strip()
            return ""

        def _user(self) -> str:
            uid = service.identity.user_id_for_session(self._session_token())
            if uid:
                return uid
            raise PermissionError("login required")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    st = service.status()
                    return self._json(
                        200,
                        {
                            "ok": True,
                            "demo": st["demo"],
                            "llm": st["llm"].get("enabled"),
                            "model": st["llm"].get("model"),
                            "feishu_mode": st.get("feishu_mode"),
                        },
                    )
                if path == "/api/me":
                    account = service.session_user(self._session_token())
                    if not account:
                        return self._json(401, {"error": "login required"})
                    return self._json(200, account)
                if path == "/api/status":
                    return self._json(200, service.status(self._user()))
                if path == "/api/dashboard":
                    return self._json(200, service.dashboard(self._user()))
                if path == "/api/account/feishu":
                    return self._json(200, service.feishu_settings(self._user()))
                if path == "/api/conversations":
                    return self._json(200, {"items": service.conversations(self._user())})
                if path.startswith("/api/conversations/"):
                    session_id = path.rsplit("/", 1)[-1]
                    return self._json(200, service.conversation_detail(session_id, self._user()))
                if path == "/api/conversation-profile":
                    return self._json(200, service.conversation_profile(self._user()).get())
                if path == "/api/notifications":
                    return self._json(200, {"items": service.for_user(self._user()).notify.list()})
                if path == "/api/memory":
                    return self._json(200, service._memory_snapshot(self._user()))
                if path == "/api/profile":
                    return self._json(200, service.for_user(self._user()).memory.profile())
                if path == "/api/memory/profile":
                    return self._json(200, service.for_user(self._user()).user_memory.profile())
                if path == "/api/goals":
                    return self._json(200, {"items": service.for_user(self._user()).workspace.goals()})
                if path == "/api/push-settings":
                    return self._json(200, service.for_user(self._user()).workspace.push_settings())
                if path in {"/api/feeds/work", "/api/feeds/intel"}:
                    return self._json(200, {"items": service.for_user(self._user()).memory.feeds().get("intel", [])})
                if path in {"/api/feeds/personal", "/api/feeds/for-you", "/api/feeds/for_you"}:
                    return self._json(200, {"items": service.for_user(self._user()).memory.feeds().get("for_you", [])})
                if path == "/api/cards":
                    return self._json(200, {"items": service.for_user(self._user()).memory.cards()})
                if path == "/api/events":
                    return self._json(200, {"items": service.for_user(self._user()).memory.events()[:40]})
            except PermissionError:
                return self._json(401, {"error": "login required"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except KeyError:
                return self._json(404, {"error": "conversation not found"})
            return super().do_GET()

        def do_PUT(self) -> None:
            path = urlparse(self.path).path
            body = self._read_json()
            try:
                user_id = self._user()
                if path == "/api/profile":
                    profile = service.for_user(user_id).memory.save_profile(body or DEFAULT_PROFILE)
                    return self._json(200, profile)
                if path == "/api/memory/profile":
                    return self._json(200, service.for_user(user_id).user_memory.save_profile(body or {}))
                if path == "/api/project":
                    return self._json(200, service.for_user(user_id).user_memory.save_project(body or {}))
                if path == "/api/interests":
                    return self._json(200, {"items": service.for_user(user_id).user_memory.save_interests(body.get("items") or [])})
                if path == "/api/goals":
                    return self._json(200, {"items": service.save_goals(body.get("items") or [], user_id=user_id)})
                if path == "/api/products":
                    return self._json(200, {"items": service.save_products(body.get("items") or [], user_id=user_id)})
                if path == "/api/push-settings":
                    return self._json(200, service.save_push_settings(body or {}, user_id=user_id))
                if path == "/api/account/feishu":
                    return self._json(200, service.save_feishu_settings(body or {}, user_id=user_id))
                if path == "/api/conversation-profile":
                    return self._json(200, service.save_conversation_profile(body or {}, user_id=user_id))
                if path == "/api/account/password":
                    return self._json(
                        200,
                        service.change_password(user_id, body.get("old_password") or "", body.get("new_password") or ""),
                    )
            except PermissionError:
                return self._json(401, {"error": "login required"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/auth/register":
                    body = self._read_json()
                    session = service.register_account(
                        body.get("username") or "",
                        body.get("password") or "",
                        body.get("display_name") or "",
                    )
                    return self._json(200, session, cookie=_session_cookie(session["token"]))
                if path == "/api/auth/login":
                    body = self._read_json()
                    session = service.login(body.get("username") or "", body.get("password") or "")
                    return self._json(200, session, cookie=_session_cookie(session["token"]))
                if path == "/api/auth/logout":
                    service.logout(self._session_token())
                    return self._json(200, {"ok": True}, cookie=_clear_session_cookie())
                user_id = self._user()
                if path in {"/api/refresh", "/api/feeds/work/refresh", "/api/feeds/personal/refresh"}:
                    result = service.refresh()
                    return self._json(200, result)
                if path == "/api/events":
                    body = self._read_json()
                    out = service.track(
                        body["id"],
                        body.get("action", "open"),
                        int(body.get("dwell_ms") or 0),
                        user_id=user_id,
                    )
                    return self._json(200, out)
                if path == "/api/items/feedback":
                    body = self._read_json()
                    out = service.feedback(body["id"], body.get("channel", "work"), body.get("action", "useful"), user_id=user_id)
                    return self._json(200, out)
                if path == "/api/follows":
                    body = self._read_json()
                    return self._json(200, service.add_follow(body.get("text") or "", body.get("topic") or "", float(body.get("weight") or 0.86), user_id=user_id))
                if path == "/api/cards/move":
                    body = self._read_json()
                    return self._json(200, service.move_card(body.get("id") or body.get("source_url") or "", body.get("category") or "待整理", user_id=user_id))
                if path == "/api/push/feishu":
                    return self._json(200, service.push_top_work(user_id=user_id))
                if path == "/api/chat":
                    body = self._read_json()
                    out = asyncio.run(
                        service.chat(
                            body.get("message") or "",
                            session_id=body.get("session_id") or None,
                            user_id=user_id,
                        )
                    )
                    return self._json(200, out)
            except PermissionError:
                return self._json(401, {"error": "login required"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
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

        def _json(self, code: int, payload: Any, cookie: str | None = None) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

    return Handler


def _session_cookie(token: str) -> str:
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={14 * 24 * 3600}"


def _clear_session_cookie() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


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
    print("Remember · Observe · Act  |  登录后使用  |  飞书 App ID / Secret 写在「账号与安全」")
    httpd.serve_forever()
