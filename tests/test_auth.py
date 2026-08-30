from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    monkeypatch.setenv("RADAR_DEMO_CONTENT", "1")
    return RadarService(data_dir=tmp_path)


def test_login_and_wrong_password(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    session = svc.login("alice", "alice123")
    assert session["user"]["id"] == "alice"
    assert session["token"]
    assert svc.identity.user_id_for_session(session["token"]) == "alice"
    try:
        svc.login("alice", "wrong-password")
        assert False, "should reject"
    except ValueError:
        pass


def test_register_has_private_memory(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    session = svc.register_account("carol", "carol123", "Carol")
    assert session["user"]["id"] == "carol"
    svc.track("demo-mem0", "collect", user_id="carol")
    assert svc.for_user("carol").memory.cards()
    assert not svc.for_user("alice").memory.cards()
    assert svc.for_user("carol").user_memory.profile()["display_name"] == "Carol"


def test_session_logout(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    token = svc.login("bob", "bob123")["token"]
    assert svc.session_user(token)["user"]["id"] == "bob"
    svc.logout(token)
    assert svc.session_user(token) is None


def test_feishu_secret_stays_per_user_and_masked(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "radar.pipeline.validate_app_config",
        lambda config: {"ok": True, "reason": "verified"},
    )
    svc = _svc(tmp_path, monkeypatch)
    saved = svc.save_feishu_settings(
        {
            "app_id": "cli_alice",
            "app_secret": "alice-secret",
            "receive_id_type": "email",
            "receive_id": "alice@example.com",
        },
        user_id="alice",
    )
    assert saved["app_id"] == "cli_alice"
    assert saved["app_secret_set"] is True
    assert saved["ready"] is True
    assert saved["verification_status"] == "verified"
    assert "alice-secret" not in str(saved)
    bob = svc.feishu_settings("bob")
    assert not bob["app_secret_set"]
    assert bob["app_id"] == ""
    raw = svc._feishu_raw("alice")
    assert raw["app_secret"] == "alice-secret"
    blank = svc.save_feishu_settings({"app_secret": ""}, user_id="alice")
    assert svc._feishu_raw("alice")["app_secret"] == "alice-secret"
    assert blank["app_secret_set"] is True


def test_change_password(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.change_password("alice", "alice123", "alice456")
    svc.login("alice", "alice456")
    try:
        svc.login("alice", "alice123")
        assert False, "old password should fail"
    except ValueError:
        pass
