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
    monkeypatch.setattr(ui, "_PREFERRED_DEFAULTS", ["litellm:openai/glm-5-free", "litellm:anthropic/deepseek-v4-flash-0731", "ollama:gpt-oss:20b-cloud"])
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    out = ui.synthesizers()["synthesizers"]
    assert out[0]["id"] == "ollama:gpt-oss:20b-cloud" and out[0]["default"] is True     # no key → the first OFFERED preference (a free Ollama model)
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
    assert cfg["api_base"] == "https://opencode.ai/zen/v1" and all(m.startswith("openai/") for m in cfg["models"])
    snapshot = cfg.get("models_snapshot") or cfg["models"]
    assert len(snapshot) >= 20 and 1 <= len(cfg["models"]) <= len(snapshot)      # OPENCODE-RECONCILE-V1: offered = served ⊆ snapshot
    assert "openai/glm-5-free" in snapshot and "openai/gpt-5" not in snapshot        # models.dev's zero-cost list
    assert all(m in snapshot for m in cfg["models"])                                   # offered ⊆ snapshot (reconcile only removes)


def test_reconcile_keeps_only_the_free_ids_the_endpoint_serves():
    """OPENCODE-RECONCILE-V1 (2026-09-06): models.dev listed 31 zero-cost ids; the endpoint served 8 of them and answered
    'Model glm-5-free is not supported' for the rest — a default pointing at an unserved id broke every new chat."""
    spec = importlib.util.spec_from_file_location("chat_models_setup", ROOT / "scripts" / "chat_models_setup.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    cfg = {"litellm_provider": "openai", "models": ["openai/glm-5-free", "openai/big-pickle", "openai/deepseek-v4-flash-free"],
           "names": {"openai/glm-5-free": "GLM-5 Free", "openai/big-pickle": "Big Pickle", "openai/deepseek-v4-flash-free": "DeepSeek V4 Flash Free"}}
    served = {"big-pickle", "deepseek-v4-flash-free", "gpt-5", "claude-opus-5"}          # paid ids served too — never added
    out = mod.reconcile_with_endpoint(cfg, served)
    assert out["models"] == ["openai/big-pickle", "openai/deepseek-v4-flash-free"] and out["unserved"] == ["openai/glm-5-free"]
    assert out["names"] == {"openai/big-pickle": "Big Pickle", "openai/deepseek-v4-flash-free": "DeepSeek V4 Flash Free"}
    assert out["served_total"] == 4 and cfg["models"][0] == "openai/glm-5-free"          # pure: input untouched


def test_alibaba_model_studio_snapshot_is_an_anthropic_messages_provider_with_the_nine_plan_models():
    cfg = json.loads((ROOT / "config" / "chat_models" / "alibaba_model_studio.json").read_text())
    assert cfg["provider_id"] == "alibaba-model-studio" and cfg["litellm_provider"] == "anthropic" and cfg["api_key_env"] == "ALIBABA_MODEL_STUDIO_API_KEY"
    assert cfg["api_base"].startswith("https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic") and cfg["api_base"].endswith("/v1/messages")
    assert cfg["models"][0] == "anthropic/deepseek-v4-flash-0731" and cfg["models"][-1] == "anthropic/qwen3.8-max"   # measured order: fast + citing first
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


def test_the_chat_model_catalog_never_reaches_extraction_enrichment_or_the_compiler():
    """Owner rule (2026-09-06): the chat-model catalog (llm_providers rows, the Ollama allowlist, OpenCode / Alibaba keys) feeds
    the chat SYNTHESIZER only. Extraction, enrichment and the query compiler keep their own stage pins and env knobs; nothing
    under control/, workers/ or shared/ may import or read the catalog."""
    import re
    catalog_symbols = re.compile(r"llm_providers|_litellm_credentials|_litellm_models|_ollama_models|OLLAMA_FREE_CLOUD_MODELS|"
                                 r"OPENCODE_API_KEY|ALIBABA_MODEL_STUDIO_API_KEY|POLYMATH_DEFAULT_SYNTHESIZER|orchestrator\.api\.ui")
    offenders = []
    for top in ("control", "workers", "shared"):
        for path in (ROOT / top).rglob("*.py"):
            if ".venv" in path.parts or "tests" in path.parts:
                continue
            if catalog_symbols.search(path.read_text(errors="ignore")):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], offenders
    # and the compiler lanes are pinned by the control plane, not by the catalog
    ui_src = (ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py").read_text()
    assert "chat_compiler" not in ui_src.split("def _litellm_models")[1].split("def _litellm_credentials")[0]


def test_a_request_without_a_synthesizer_gets_the_first_offered_model_never_a_hidden_provider(monkeypatch):
    """2026-09-06 UI finding: an empty synthesizer fell to the raw first preference (glm-5-free) while its key was unset
    → LiteLLM 'Missing credentials'. The fallback must follow the dropdown's rule: first OFFERED preference."""
    import httpx
    monkeypatch.setattr(httpx, "get", lambda url, timeout=3: _Resp(list(ui.OLLAMA_FREE_CLOUD_MODELS)))
    alibaba = {"provider_id": "alibaba-model-studio", "provider": "anthropic", "api_key": "env:ALIBABA_MODEL_STUDIO_API_KEY",
               "api_base": "https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic/v1/messages",
               "models": ["anthropic/deepseek-v4-flash-0731", "anthropic/qwen3.8-max"], "enabled": True}
    monkeypatch.setattr(ui, "_llm_provider_rows", lambda: [_rows()[0], alibaba])
    monkeypatch.setattr(ui, "_PREFERRED_DEFAULTS", ["litellm:openai/glm-5-free", "litellm:anthropic/deepseek-v4-flash-0731", "ollama:gemma4:31b-cloud"])
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("ALIBABA_MODEL_STUDIO_API_KEY", raising=False)
    assert ui._default_synthesizer() == "ollama:gemma4:31b-cloud"                        # both keyed providers hidden
    monkeypatch.setenv("ALIBABA_MODEL_STUDIO_API_KEY", "sk-test")
    assert ui._default_synthesizer() == "litellm:anthropic/deepseek-v4-flash-0731"       # second preference, first offered
    monkeypatch.setenv("OPENCODE_API_KEY", "oc")
    assert ui._default_synthesizer() == "litellm:openai/glm-5-free"
    src = (ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py").read_text()
    assert "synth = req.synthesizer or _default_synthesizer()" in src and "synth = req.synthesizer or _PREFERRED_DEFAULT" not in src


def test_catalog_rows_carry_the_provider_grouping_fields(monkeypatch):
    """MODEL-PICKER-V1: the dropdown groups models into collapsible provider sections from DATA
    (provider id + display label + bare model name), never by parsing ids."""
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-test")
    monkeypatch.setattr(ui, "_llm_provider_rows", lambda: _rows())
    monkeypatch.setattr(ui, "_ollama_registered", lambda: {"gemma4:31b-cloud"})
    entries = ui.synthesizers()["synthesizers"]
    by_id = {e["id"]: e for e in entries}
    oc = by_id["litellm:openai/glm-5-free"]
    assert oc["provider"] == "opencode-free" and oc["provider_label"] == "OpenCode (free)" and oc["model"] == "glm-5-free"
    ol = by_id["ollama:gemma4:31b-cloud"]
    assert ol["provider"] == "ollama-free" and ol["provider_label"] == "Ollama cloud (free)" and ol["model"] == "gemma4:31b-cloud"
    assert all({"provider", "provider_label", "model", "kind", "available"} <= set(e) for e in entries)
