"""CHAT-MODEL-CATALOG-V1 (owner decision 2026-09-06): the chat model dropdown = OpenCode Zen's free models (LiteLLM provider row,
key read from .env by name) + Ollama's free cloud tier (fixed allowlist), nothing else; a provider whose env key is unset is hidden."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
from orchestrator.api import ui  # noqa: E402


class _Resp:
    def __init__(self, names):
        self._names = names

    def json(self):
        return {"models": [{"name": n} for n in self._names]}


def test_ollama_entries_are_the_free_cloud_allowlist_with_availability(monkeypatch):
    import httpx
    monkeypatch.delenv("POLYMATH_OLLAMA_MODELS", raising=False)
    monkeypatch.setattr(httpx, "get", lambda url, timeout=3: _Resp(["gemma4:31b-cloud", "deepseek-v4-pro:cloud", "llama3:8b", "nemotron-3-ultra:cloud"]))
    entries = ui._ollama_models()
    assert [e["id"] for e in entries] == [f"ollama:{n}" for n in ui.OLLAMA_FREE_CLOUD_MODELS]      # fixed order, six names
    assert all(e["kind"] == "ollama" and e["label"].startswith("Ollama cloud (free) · ") for e in entries)
    avail = {e["id"]: e["available"] for e in entries}
    assert avail["ollama:gemma4:31b-cloud"] is True and avail["ollama:nemotron-3-ultra:cloud"] is True
    assert avail["ollama:gpt-oss:120b-cloud"] is False and "ollama pull gpt-oss:120b-cloud" in [e for e in entries if e["id"] == "ollama:gpt-oss:120b-cloud"][0]["description"]
    assert not any("deepseek" in e["id"] or "llama3" in e["id"] for e in entries)                     # paid cloud + local never listed
    monkeypatch.setenv("POLYMATH_OLLAMA_MODELS", "gemma4:31b-cloud, gpt-oss:20b-cloud")
    assert [e["id"] for e in ui._ollama_models()] == ["ollama:gemma4:31b-cloud", "ollama:gpt-oss:20b-cloud"]
    monkeypatch.setattr(httpx, "get", lambda url, timeout=3: (_ for _ in ()).throw(ConnectionError("down")))
    assert all(e["available"] is False for e in ui._ollama_models())                                  # daemon down: listed, not available


def _rows(key="env:OPENCODE_API_KEY"):
    return [{"provider_id": "opencode-free", "provider": "openai", "api_key": key, "api_base": "https://opencode.ai/zen/v1",
             "models": ["openai/glm-5-free", "openai/big-pickle"], "enabled": True},
            {"provider_id": "literal", "provider": "groq", "api_key": "sk-literal", "api_base": "", "models": ["groq/llama"], "enabled": True},
            {"provider_id": "off", "provider": "openai", "api_key": "x", "api_base": "", "models": ["openai/never"], "enabled": False}]


def test_env_indirected_keys_resolve_at_call_time_and_hide_unset_providers(monkeypatch):
    monkeypatch.setattr(ui, "_llm_provider_rows", lambda: _rows())
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    ids = [e["id"] for e in ui._litellm_models()]
    assert ids == ["litellm:groq/llama"]                                   # OpenCode hidden until the key exists
    assert ui._litellm_credentials("openai/glm-5-free") == {"api_base": "https://opencode.ai/zen/v1"}
    monkeypatch.setenv("OPENCODE_API_KEY", "oc-secret")
    entries = ui._litellm_models()
    assert [e["id"] for e in entries] == ["litellm:openai/glm-5-free", "litellm:openai/big-pickle", "litellm:groq/llama"]
    assert entries[0]["label"] == "OpenCode (free) · glm-5-free" and entries[2]["label"] == "groq · llama"
    assert ui._litellm_credentials("openai/glm-5-free") == {"api_key": "oc-secret", "api_base": "https://opencode.ai/zen/v1"}
    assert ui._litellm_credentials("groq/llama") == {"api_key": "sk-literal"} and ui._litellm_credentials("openai/never") == {}
    masked = ui.llm_providers()["providers"]
    oc = [r for r in masked if r["provider_id"] == "opencode-free"][0]
    assert oc["api_key"] == "env:OPENCODE_API_KEY" and oc["api_key_set"] is True and oc["ready"] is True   # the NAME, never the value
    lit = [r for r in masked if r["provider_id"] == "literal"][0]
    assert lit["api_key"] == "eral" and lit["api_key_set"] is True


def test_synthesizers_default_is_the_preferred_free_model_when_offered_else_the_first_free_ollama(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "get", lambda url, timeout=3: _Resp(list(ui.OLLAMA_FREE_CLOUD_MODELS)))
    monkeypatch.setattr(ui, "_llm_provider_rows", lambda: _rows()[:1])                # only the OpenCode row configured
    monkeypatch.setattr(ui, "_PREFERRED_DEFAULT", "litellm:openai/glm-5-free")
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    out = ui.synthesizers()["synthesizers"]
    assert out[0]["id"] == "ollama:gemma4:31b-cloud" and out[0]["default"] is True     # no key yet → first free Ollama model
    assert not any(e["id"].startswith("litellm:") for e in out) and len(out) == len(ui.OLLAMA_FREE_CLOUD_MODELS)
    monkeypatch.setenv("OPENCODE_API_KEY", "oc-secret")
    out = ui.synthesizers()["synthesizers"]
    assert out[0]["id"] == "litellm:openai/glm-5-free" and out[0]["default"] is True and sum(e["default"] for e in out) == 1
    assert len(out) == 2 + len(ui.OLLAMA_FREE_CLOUD_MODELS)


def test_setup_script_filters_models_dev_to_zero_cost_and_the_config_snapshot_is_consistent():
    spec = importlib.util.spec_from_file_location("chat_models_setup", ROOT / "scripts" / "chat_models_setup.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    catalog = {"opencode": {"api": "https://opencode.ai/zen/v1", "env": ["OPENCODE_API_KEY"], "models": {
        "glm-5-free": {"name": "GLM-5 Free", "cost": {"input": 0, "output": 0}},
        "gpt-5": {"name": "GPT-5", "cost": {"input": 1.25, "output": 10}},
        "big-pickle": {"name": "Big Pickle", "cost": {"input": 0, "output": 0}},
        "odd": {"name": "no cost block"}}}}
    p, free = mod.free_models_from_models_dev(catalog)
    assert free == ["big-pickle", "glm-5-free", "odd"] and p["env"] == ["OPENCODE_API_KEY"]
    cfg = json.loads((ROOT / "config" / "chat_models" / "opencode_free.json").read_text())
    assert cfg["provider_id"] == "opencode-free" and cfg["litellm_provider"] == "openai" and cfg["api_key_env"] == "OPENCODE_API_KEY"
    assert cfg["api_base"] == "https://opencode.ai/zen/v1" and len(cfg["models"]) >= 20 and all(m.startswith("openai/") for m in cfg["models"])
    assert "openai/glm-5-free" in cfg["models"] and "openai/gpt-5" not in cfg["models"]


def test_alibaba_model_studio_snapshot_is_an_anthropic_messages_provider_with_the_nine_plan_models():
    cfg = json.loads((ROOT / "config" / "chat_models" / "alibaba_model_studio.json").read_text())
    assert cfg["provider_id"] == "alibaba-model-studio" and cfg["litellm_provider"] == "anthropic" and cfg["api_key_env"] == "ALIBABA_MODEL_STUDIO_API_KEY"
    assert cfg["api_base"].startswith("https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic") and cfg["api_base"].endswith("/v1/messages")
    assert len(cfg["models"]) == 9 and all(m.startswith("anthropic/") for m in cfg["models"]) and "anthropic/qwen3.8-max" in cfg["models"]
    assert ui._PROVIDER_LABELS["alibaba-model-studio"] == "Alibaba Model Studio"
    assert "sk-" not in json.dumps(cfg)                                   # never a key in the snapshot


def test_env_indirected_alibaba_row_labels_and_hides_like_opencode(monkeypatch):
    row = {"provider_id": "alibaba-model-studio", "provider": "anthropic", "api_key": "env:ALIBABA_MODEL_STUDIO_API_KEY",
           "api_base": "https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic/v1/messages", "models": ["anthropic/qwen3.8-max"], "enabled": True}
    monkeypatch.setattr(ui, "_llm_provider_rows", lambda: [row])
    monkeypatch.delenv("ALIBABA_MODEL_STUDIO_API_KEY", raising=False)
    assert ui._litellm_models() == []
    monkeypatch.setenv("ALIBABA_MODEL_STUDIO_API_KEY", "sk-test")
    entries = ui._litellm_models()
    assert entries[0]["id"] == "litellm:anthropic/qwen3.8-max" and entries[0]["label"] == "Alibaba Model Studio · qwen3.8-max"
    assert ui._litellm_credentials("anthropic/qwen3.8-max") == {"api_key": "sk-test", "api_base": row["api_base"]}

