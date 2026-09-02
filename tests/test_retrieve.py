import json
import threading
from pathlib import Path

from radar.pipeline import RadarService
from radar.retrieve import related, retrieve, text_similarity
from radar.store import _write_json


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    return RadarService(data_dir=tmp_path)


def test_similarity_matches_synonyms_not_funding():
    assert related("Temporal Memory for Agents", "Agent Memory")
    assert related("检索增强生成在推荐里的用法", "RAG")
    assert text_similarity("Startup raises Series B funding", "Agent Memory") < 0.28


def test_retrieve_ranks_rag_over_unrelated(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    scope = svc.for_user("alice")
    scope.user_memory.add_interests([{"topic": "RAG", "weight": 0.9, "source": ["test"]}])
    scope.user_memory.add_interests([{"topic": "World Model", "weight": 0.4, "source": ["test"]}])
    hits = retrieve(scope, "检索增强生成最近有什么进展", limit=8)
    kinds = [row["kind"] for row in hits]
    texts = " ".join(row["text"] for row in hits)
    assert "interest" in kinds
    assert "RAG" in texts
    assert hits[0]["text"] == "RAG" or "RAG" in hits[0]["text"]


def test_recall_memory_is_per_user(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.for_user("alice").user_memory.add_interests([{"topic": "Mem0", "weight": 0.95, "source": ["test"]}])
    svc.for_user("bob").user_memory.add_interests([{"topic": "World Model", "weight": 0.95, "source": ["test"]}])
    alice = " ".join(row["text"] for row in svc.recall_memory("长期记忆", "alice"))
    bob = " ".join(row["text"] for row in svc.recall_memory("世界模型", "bob"))
    assert "Mem0" in alice
    assert "World Model" in bob


def test_write_json_is_atomic_and_valid(tmp_path):
    path = tmp_path / "state.json"
    _write_json(path, {"n": 1})
    errors: list[str] = []

    def writer(value: int) -> None:
        try:
            _write_json(path, {"n": value})
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "n" in data
    leftovers = list(tmp_path.glob(".state.json.*.tmp"))
    assert leftovers == []
