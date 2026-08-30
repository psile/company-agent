"""本地 / 云上 HTTP：Agent 工作台 + API。飞书入站长连接可选依赖 lark-oapi。"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import get_bool, get_int, load_env
from .feishu_inbox import handle_http_event, inbox_status, start_feishu_inbox, verify_webhook, webhook_ack
from .pipeline import RadarService
from .reminders.scheduler import start_reminder_loop
from .routes import Router
from .store import DEFAULT_PROFILE

load_env()
WEB = Path(os.environ.get("RADAR_WEB_DIR", Path(__file__).resolve().parents[1] / "web"))
HOST = os.environ.get("RADAR_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT") or os.environ.get("RADAR_PORT") or 8765)
SESSION_COOKIE = "radar_session"


def _q(query: str, name: str) -> str:
    return (parse_qs(query).get(name) or [""])[0]


def make_handler(service: RadarService):
    router = Router()

    def add(method: str, path: str, auth: str, fn) -> None:
        router.add(method, path, auth, fn)

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

        def _dispatch(self, method: str) -> bool:
            parsed = urlparse(self.path)
            found = router.match(method, parsed.path)
            if not found:
                return False
            try:
                user_id = self._user() if found.auth == "user" else None
                body = self._read_json() if method in {"POST", "PUT"} else {}
                found.fn(self, user_id, found.params, parsed.query, body)
            except PermissionError:
                self._json(401, {"error": "login required"})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except KeyError as exc:
                label = "conversation not found" if method == "GET" else f"item not found: {exc}"
                self._json(404, {"error": label})
            except Exception as exc:
                if method == "POST":
                    self._json(500, {"error": str(exc)})
                else:
                    raise
            return True

        def do_GET(self) -> None:
            if not self._dispatch("GET"):
                super().do_GET()

        def do_PUT(self) -> None:
            if not self._dispatch("PUT"):
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._dispatch("POST"):
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

    def health(h: Handler, *_args) -> None:
        st = service.status()
        h._json(
            200,
            {
                "ok": True,
                "demo": st["demo"],
                "llm": st["llm"].get("enabled"),
                "model": st["llm"].get("model"),
                "feishu_mode": st.get("feishu_mode"),
                "feishu_inbox": inbox_status(),
            },
        )

    def me(h: Handler, *_args) -> None:
        account = service.session_user(h._session_token())
        if not account:
            return h._json(401, {"error": "login required"})
        h._json(200, account)

    def feishu_event(h: Handler, _user, _params, _query, body: dict) -> None:
        ack = webhook_ack(body)
        if ack is not None:
            if not verify_webhook(body):
                return h._json(401, {"error": "invalid feishu token"})
            return h._json(200, ack)
        if not verify_webhook(body):
            return h._json(401, {"error": "invalid feishu token"})
        threading.Thread(
            target=handle_http_event,
            args=(service, body),
            daemon=True,
            name="radar-feishu-event",
        ).start()
        h._json(200, {"ok": True})

    add("GET", "/api/health", "none", health)
    add("GET", "/api/me", "none", me)
    add("GET", "/api/status", "user", lambda h, uid, *_: h._json(200, service.status(uid)))
    add("GET", "/api/dashboard", "user", lambda h, uid, *_: h._json(200, service.dashboard(uid)))
    add("GET", "/api/account/feishu", "user", lambda h, uid, *_: h._json(200, service.feishu_settings(uid)))
    add("GET", "/api/settings/llm", "user", lambda h, uid, *_: h._json(200, service.llm_settings()))
    add("GET", "/api/conversations", "user", lambda h, uid, *_: h._json(200, {"items": service.conversations(uid)}))
    add(
        "GET",
        "/api/conversations/{session_id}",
        "user",
        lambda h, uid, params, *_: h._json(200, service.conversation_detail(params["session_id"], uid)),
    )
    add("GET", "/api/conversation-profile", "user", lambda h, uid, *_: h._json(200, service.conversation_profile(uid).get()))
    add("GET", "/api/notifications", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).notify.list()}))
    add("GET", "/api/memory", "user", lambda h, uid, *_: h._json(200, service._memory_snapshot(uid)))
    add(
        "GET",
        "/api/memory/search",
        "user",
        lambda h, uid, _params, query, *_: h._json(200, {"items": service.recall_memory(_q(query, "q"), uid)}),
    )
    add("GET", "/api/profile", "user", lambda h, uid, *_: h._json(200, service.for_user(uid).memory.profile()))
    add("GET", "/api/memory/profile", "user", lambda h, uid, *_: h._json(200, service.for_user(uid).user_memory.profile()))
    add("GET", "/api/goals", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).workspace.goals()}))
    add(
        "GET",
        "/api/work/tasks",
        "user",
        lambda h, uid, _p, query, *_: h._json(
            200,
            {"items": service.list_tasks(uid, include_done=_q(query, "include_done") not in {"0", "false"})},
        ),
    )
    add("GET", "/api/work/events", "user", lambda h, uid, *_: h._json(200, {"items": service.list_work_events(uid)}))
    add("GET", "/api/work/notes", "user", lambda h, uid, *_: h._json(200, {"items": service.list_work_notes(uid)}))
    add("GET", "/api/work/reminders", "user", lambda h, uid, *_: h._json(200, {"items": service.list_reminders(uid)}))
    add(
        "GET",
        "/api/work/reports",
        "user",
        lambda h, uid, _p, query, *_: h._json(200, {"items": service.list_reports(uid, _q(query, "type") or None)}),
    )
    add(
        "GET",
        "/api/work/summary",
        "user",
        lambda h, uid, _p, query, *_: h._json(
            200,
            service.work_period_summary(
                _q(query, "kind") or "week",
                user_id=uid,
                project_id=_q(query, "project_id") or None,
            )
            if (_q(query, "kind") or "") not in {"", "timeline", "7", "30"}
            else service.work_summary(uid, range_days=int(_q(query, "days") or 7)),
        ),
    )
    add("GET", "/api/projects", "user", lambda h, uid, *_: h._json(200, service.list_project_trackers(uid)))
    add("POST", "/api/projects", "user", lambda h, uid, _p, _q, body: h._json(200, service.create_project(body or {}, uid)))
    add("PUT", "/api/projects/{project_id}", "user", lambda h, uid, params, _q, body: h._json(200, service.update_project(params["project_id"], body or {}, uid)))
    add("POST", "/api/projects/{project_id}/activate", "user", lambda h, uid, params, _q, _body: h._json(200, service.activate_project(params["project_id"], uid)))
    add("GET", "/api/project/tracker", "user", lambda h, uid, *_: h._json(200, service.project_tracker(uid)))
    add("GET", "/api/work/tracker", "user", lambda h, uid, *_: h._json(200, service.project_tracker(uid)))
    add("GET", "/api/skills", "user", lambda h, uid, *_: h._json(200, {"items": service.list_office_skills()}))
    add("GET", "/api/push-settings", "user", lambda h, uid, *_: h._json(200, service.for_user(uid).workspace.push_settings()))
    add("GET", "/api/feeds/work", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.feeds().get("intel", [])}))
    add("GET", "/api/feeds/intel", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.feeds().get("intel", [])}))
    add("GET", "/api/feeds/personal", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.feeds().get("for_you", [])}))
    add("GET", "/api/feeds/for-you", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.feeds().get("for_you", [])}))
    add("GET", "/api/feeds/for_you", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.feeds().get("for_you", [])}))
    add("GET", "/api/cards", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.cards()}))
    add("GET", "/api/events", "user", lambda h, uid, *_: h._json(200, {"items": service.for_user(uid).memory.events()[:40]}))

    add("PUT", "/api/profile", "user", lambda h, uid, _p, _q, body: h._json(200, service.for_user(uid).memory.save_profile(body or DEFAULT_PROFILE)))
    add("PUT", "/api/memory/profile", "user", lambda h, uid, _p, _q, body: h._json(200, service.for_user(uid).user_memory.save_profile(body or {})))
    add("PUT", "/api/project", "user", lambda h, uid, _p, _q, body: h._json(200, service.for_user(uid).user_memory.save_project(body or {})))
    add("PUT", "/api/interests", "user", lambda h, uid, _p, _q, body: h._json(200, {"items": service.for_user(uid).user_memory.save_interests(body.get("items") or [])}))
    add("PUT", "/api/goals", "user", lambda h, uid, _p, _q, body: h._json(200, {"items": service.save_goals(body.get("items") or [], user_id=uid)}))
    add("PUT", "/api/work/tasks/{task_id}", "user", lambda h, uid, params, _q, body: h._json(200, service.update_task(params["task_id"], body or {}, user_id=uid)))
    add("PUT", "/api/work/reports/{report_id}", "user", lambda h, uid, params, _q, body: h._json(200, service.update_report(params["report_id"], body or {}, user_id=uid)))
    add("PUT", "/api/products", "user", lambda h, uid, _p, _q, body: h._json(200, {"items": service.save_products(body.get("items") or [], user_id=uid)}))
    add("PUT", "/api/push-settings", "user", lambda h, uid, _p, _q, body: h._json(200, service.save_push_settings(body or {}, user_id=uid)))
    add("PUT", "/api/account/feishu", "user", lambda h, uid, _p, _q, body: h._json(200, service.save_feishu_settings(body or {}, user_id=uid)))
    add("PUT", "/api/settings/llm", "user", lambda h, uid, _p, _q, body: h._json(200, service.save_llm_settings(body or {})))
    add("PUT", "/api/conversation-profile", "user", lambda h, uid, _p, _q, body: h._json(200, service.save_conversation_profile(body or {}, user_id=uid)))
    add(
        "PUT",
        "/api/account/password",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.change_password(uid, body.get("old_password") or "", body.get("new_password") or ""),
        ),
    )

    add("POST", "/api/feishu/event", "none", feishu_event)
    add(
        "POST",
        "/api/auth/register",
        "none",
        lambda h, _u, _p, _q, body: h._json(
            200,
            (session := service.register_account(body.get("username") or "", body.get("password") or "", body.get("display_name") or "")),
            cookie=_session_cookie(session["token"]),
        ),
    )
    add(
        "POST",
        "/api/auth/login",
        "none",
        lambda h, _u, _p, _q, body: h._json(
            200,
            (session := service.login(body.get("username") or "", body.get("password") or "")),
            cookie=_session_cookie(session["token"]),
        ),
    )
    add(
        "POST",
        "/api/auth/logout",
        "none",
        lambda h, *_: (
            service.logout(h._session_token()),
            h._json(200, {"ok": True}, cookie=_clear_session_cookie()),
        )[1],
    )
    add("POST", "/api/refresh", "user", lambda h, uid, *_: h._json(200, service.refresh()))
    add("POST", "/api/feeds/work/refresh", "user", lambda h, uid, *_: h._json(200, service.refresh()))
    add("POST", "/api/feeds/personal/refresh", "user", lambda h, uid, *_: h._json(200, service.refresh()))
    add(
        "POST",
        "/api/events",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.track(body["id"], body.get("action", "open"), int(body.get("dwell_ms") or 0), user_id=uid),
        ),
    )
    add(
        "POST",
        "/api/items/feedback",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.feedback(body["id"], body.get("channel", "work"), body.get("action", "useful"), user_id=uid),
        ),
    )
    add(
        "POST",
        "/api/follows",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.add_follow(body.get("text") or "", body.get("topic") or "", float(body.get("weight") or 0.86), user_id=uid),
        ),
    )
    add(
        "POST",
        "/api/cards/move",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.move_card(body.get("id") or body.get("source_url") or "", body.get("category") or "待整理", user_id=uid),
        ),
    )
    add("POST", "/api/push/feishu", "user", lambda h, uid, *_: h._json(200, service.push_top_work(user_id=uid)))
    add("POST", "/api/settings/llm/test", "user", lambda h, *_: h._json(200, service.test_llm_connection()))
    add(
        "POST",
        "/api/chat",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            asyncio.run(service.chat(body.get("message") or "", session_id=body.get("session_id") or None, user_id=uid)),
        ),
    )
    add("POST", "/api/work/tasks", "user", lambda h, uid, _p, _q, body: h._json(200, service.create_task(body or {}, user_id=uid)))
    add(
        "POST",
        "/api/work/tasks/{task_id}/breakdown",
        "user",
        lambda h, uid, params, *_: h._json(200, service.breakdown_task(params["task_id"], user_id=uid)),
    )
    add("POST", "/api/work/notes", "user", lambda h, uid, _p, _q, body: h._json(200, service.add_work_note(body or {}, user_id=uid)))
    add("POST", "/api/work/reminders/tick", "user", lambda h, uid, *_: h._json(200, {"ok": True, "items": service.evaluate_reminders(uid)}))
    add("POST", "/api/work/reminders", "user", lambda h, uid, _p, _q, body: h._json(200, service.create_reminder(body or {}, user_id=uid)))
    add(
        "POST",
        "/api/work/reports/generate",
        "user",
        lambda h, uid, _p, _q, body: h._json(
            200,
            service.generate_report(
                body.get("report_type") or "daily",
                user_id=uid,
                project_id=body.get("project_id") or None,
                start_time=body.get("start_time"),
                end_time=body.get("end_time"),
            ),
        ),
    )

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
    start_reminder_loop(service)
    start_feishu_inbox(service)
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"个人工作秘书 Agent  http://{host}:{port}/")
    print("Remember · Observe · Act  |  登录后使用  |  飞书里可以直接对话")
    httpd.serve_forever()
