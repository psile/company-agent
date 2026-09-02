import json
from pathlib import Path

from radar.pipeline import RadarService


def _svc(tmp_path: Path, monkeypatch) -> RadarService:
    monkeypatch.setenv("RADAR_LLM", "0")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("MEMORYOS_ENABLED", "0")
    monkeypatch.setenv("FEISHU_MODE", "mock")
    monkeypatch.setattr("radar.llm._parse_radarme_config", lambda: {})
    return RadarService(data_dir=tmp_path)


def test_save_llm_settings_masks_key_and_is_system_wide(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    saved = svc.save_llm_settings(
        {
            "enabled": True,
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-V4-Flash",
            "api_key": "sk-alice-secret-key",
        }
    )
    assert saved["enabled"] is True
    assert saved["active"] is True
    assert saved["base_url"] == "https://api.siliconflow.cn/v1"
    assert saved["model"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert saved["api_key_set"] is True
    assert saved["source"] == "settings"
    assert "sk-alice-secret-key" not in json.dumps(saved)
    assert saved["api_key_preview"].startswith("sk-")
    assert "secret" not in saved["api_key_preview"]
    bob = svc.llm_settings()
    assert bob["api_key_set"] is True
    raw = json.loads((tmp_path / "llm.json").read_text(encoding="utf-8"))
    assert raw["api_key"] == "sk-alice-secret-key"
    dash = svc.dashboard("alice")
    assert "sk-alice-secret-key" not in json.dumps(dash)
    assert dash["llm_settings"]["api_key_set"] is True
    assert dash["status"]["llm"]["enabled"] is True


def test_blank_api_key_keeps_existing_secret(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.save_llm_settings(
        {
            "enabled": True,
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "api_key": "sk-keep-me",
        }
    )
    again = svc.save_llm_settings(
        {
            "enabled": True,
            "base_url": "https://api.example.com/v1",
            "model": "demo-model-2",
            "api_key": "",
        }
    )
    assert again["model"] == "demo-model-2"
    assert again["api_key_set"] is True
    raw = json.loads((tmp_path / "llm.json").read_text(encoding="utf-8"))
    assert raw["api_key"] == "sk-keep-me"


def test_disable_llm_from_settings_even_if_configured(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.save_llm_settings(
        {
            "enabled": False,
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "api_key": "sk-demo",
        }
    )
    status = svc.status("alice")["llm"]
    assert status["settings_enabled"] is False
    assert status["enabled"] is False
    assert status["api_key_set"] is True


def test_radar_llm_env_still_disables_without_saved_file(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-from-env")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("RADAR_LLM", "0")
    status = svc.status("alice")["llm"]
    assert status["enabled"] is False
    public = svc.llm_settings()
    assert public["model"] == "env-model"
    assert public["source"] == "env"
    assert "sk-from-env" not in json.dumps(public)


def test_local_gateway_does_not_need_api_key(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    saved = svc.save_llm_settings(
        {
            "enabled": True,
            "base_url": "http://127.0.0.1:8000/v1",
            "model": "Qwen3.8-27B",
            "api_key": "",
        }
    )
    assert saved["active"] is True
    assert saved["api_key_set"] is False


def test_llm_connection_probe(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    svc.save_llm_settings(
        {
            "enabled": True,
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "api_key": "sk-demo",
        }
    )
    monkeypatch.setattr("radar.llm.chat_text", lambda *args, **kwargs: "ok")
    out = svc.test_llm_connection()
    assert out["ok"] is True
    assert out["reply"] == "ok"
