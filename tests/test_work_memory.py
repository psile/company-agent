from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def test_demo_users_have_isolated_seed_tasks(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    alice = {row["title"] for row in svc.list_tasks("alice")}
    bob = {row["title"] for row in svc.list_tasks("bob")}
    assert "完善 Memory Demo" in alice
    assert "整理 World Model 数据集" in bob
    assert "完善 Memory Demo" not in bob
    assert "整理 World Model 数据集" not in alice


def test_alice_task_is_invisible_to_bob(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    created = svc.create_task(
        {"title": "Alice secret task", "priority": "urgent", "user_id": "bob"},
        user_id="alice",
    )
    assert created["user_id"] == "alice"
    assert created["title"] == "Alice secret task"
    bob_titles = {row["title"] for row in svc.list_tasks("bob")}
    assert "Alice secret task" not in bob_titles
    assert svc.for_user("bob").work.get_task(created["id"]) is None


def test_work_events_and_notes_are_isolated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    note = svc.add_work_note({"content": "only alice should see this"}, user_id="alice")
    assert note["user_id"] == "alice"
    alice_notes = [row["content"] for row in svc.list_work_notes("alice")]
    bob_notes = [row["content"] for row in svc.list_work_notes("bob")]
    assert "only alice should see this" in alice_notes
    assert "only alice should see this" not in bob_notes
    alice_events = {row["event_type"] for row in svc.list_work_events("alice")}
    assert "task_created" in alice_events
    assert "note_created" in alice_events
    bob_refs = {row.get("source_ref") for row in svc.list_work_events("bob")}
    assert note["id"] not in bob_refs


def test_complete_task_writes_event(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    task = svc.create_task({"title": "Write PPT", "priority": "high"}, user_id="alice")
    updated = svc.update_task(task["id"], {"status": "done"}, user_id="alice")
    assert updated["status"] == "done"
    assert updated["completed_at"]
    types = [row["event_type"] for row in svc.list_work_events("alice") if row.get("source_ref") == task["id"]]
    assert "task_created" in types
    assert "task_completed" in types
