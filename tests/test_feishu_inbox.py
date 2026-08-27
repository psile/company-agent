from __future__ import annotations

from pathlib import Path

from radar.feishu_inbox import (
    extract_message_text,
    handle_incoming,
    reset_seen_for_tests,
    resolve_inbox_user,
    webhook_ack,
)
from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    monkeypatch.delenv("FEISHU_INBOX_USER", raising=False)
    monkeypatch.delenv("FEISHU_RECEIVE_ID", raising=False)
    reset_seen_for_tests()
    return RadarService(data_dir=tmp_path)


def _p2p_event(text: str, open_id: str = "ou_bob", message_id: str = "om_1", sender_type: str = "user") -> dict:
    return {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": open_id}, "sender_type": sender_type},
            "message": {
                "message_id": message_id,
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": '{"text":"%s"}' % text,
            },
        },
    }


def test_extract_text_and_mentions():
    assert extract_message_text({"message_type": "text", "content": '{"text":"你好"}'}) == "你好"
    assert extract_message_text({"message_type": "text", "content": '{"text":"@_user_1 帮我看看"}'}) == "帮我看看"
    post = {
        "title": "标题",
        "content": [[{"tag": "text", "text": "正文"}]],
    }
    assert "正文" in extract_message_text({"message_type": "post", "content": post})


def test_webhook_url_verification():
    assert webhook_ack({"type": "url_verification", "challenge": "abc"}) == {"challenge": "abc"}
    assert webhook_ack({"event": {"message": {}}, "header": {}}) is None


def test_skips_bot_and_group_without_mention(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    bot = handle_incoming(svc, _p2p_event("你好", sender_type="app"), send_reply=lambda **_: {"ok": True})
    assert bot["skipped"] == "bot"
    group = {
        "event": {
            "sender": {"sender_id": {"open_id": "ou_bob"}, "sender_type": "user"},
            "message": {
                "message_id": "om_group",
                "chat_id": "oc_g",
                "chat_type": "group",
                "message_type": "text",
                "content": '{"text":"大家好"}',
                "mentions": [],
            },
        }
    }
    out = handle_incoming(svc, group, send_reply=lambda **_: {"ok": True})
    assert out["skipped"] == "group_no_mention"


def test_maps_seed_open_id_to_bob_and_replies(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    replies = []

    def send_reply(**kwargs):
        replies.append(kwargs)
        return {"ok": True}

    out = handle_incoming(
        svc,
        _p2p_event("你好", open_id="ou_bob", message_id="om_bob"),
        send_reply=send_reply,
        lookup_profile=lambda _oid: {},
        chat_fn=lambda _svc, uid, text: {"reply": f"收到：{text}", "intent": "general_chat", "session_id": "feishu", "user_id": uid},
    )
    assert out["user_id"] == "bob"
    assert out["ok"] is True
    assert replies[0]["text"] == "收到：你好"
    again = handle_incoming(
        svc,
        _p2p_event("你好", open_id="ou_bob", message_id="om_bob"),
        send_reply=send_reply,
        lookup_profile=lambda _oid: {},
        chat_fn=lambda *_: {"reply": "不应再回"},
    )
    assert again["skipped"] == "duplicate"


def test_maps_receive_email_then_binds_open_id(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    from radar.store import _write_json

    _write_json(
        tmp_path / "users" / "bob" / "feishu.json",
        {"receive_id_type": "email", "receive_id": "bob@example.com"},
    )
    uid = resolve_inbox_user(svc, "ou_real_bob", {"email": "bob@example.com", "name": "Bob"})
    assert uid == "bob"
    assert resolve_inbox_user(svc, "ou_real_bob", {}) == "bob"


def test_inbox_user_fallback(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    monkeypatch.setenv("FEISHU_INBOX_USER", "alice")
    uid = resolve_inbox_user(svc, "ou_unknown_person", {})
    assert uid == "alice"


def test_unique_configured_feishu_account(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    from radar.store import _write_json

    _write_json(
        tmp_path / "users" / "bob" / "feishu.json",
        {"app_id": "cli_demo", "app_secret": "secret", "receive_mobile": "13800138000"},
    )
    uid = resolve_inbox_user(svc, "ou_real_person", {})
    assert uid == "bob"
