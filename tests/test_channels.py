from radar.channels import send_for_user
from radar.notify import NotificationLog


def test_app_failure_falls_back_to_running_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr("radar.feishu.app_config_from", lambda *_args, **_kwargs: {"ready": True})
    monkeypatch.setattr("radar.feishu.push_text", lambda *_args, **_kwargs: {"ok": False, "reason": "temporary failure"})
    monkeypatch.setattr("radar.channels._try_inbox_push", lambda *_args, **_kwargs: {"ok": True})

    notify = NotificationLog(tmp_path)
    result = send_for_user(
        "bob",
        notify,
        {"id": "item-1", "title": "Industry update", "text": "hello"},
        feishu_cfg={"app_id": "cli_test", "app_secret": "secret"},
        service=object(),
    )

    assert result["ok"] is True
    assert result["channel"] == "feishu_inbox"
    assert result["fallback_reason"] == "temporary failure"
    assert notify.list()[0]["recommendation_id"] == "item-1"
