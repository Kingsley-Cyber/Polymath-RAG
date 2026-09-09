"""EFFECTIVE-CAPACITY-V1 (RAG-PIPELINE-FINISH Phase 3) precedence tests.

runtime headers > explicit config > vendored seed > unknown(None, never 0).
Provider-free: no network, no provider call.
"""
from __future__ import annotations

from polymath_shared.llm_extraction import effective_capacity as EC
from polymath_shared.llm_extraction import lane_registry as LR


def _lane(name, host, model, **cap):
    return LR.LaneInfo(
        name=name, function="TEST", api_key_env="K", account_id="K", model=model,
        provider_host=host, dedicated=True, role="pinned", reachability=LR.ACTIVE,
        credential_present=True, enabled=True, capacity=LR.LaneCapacity(**cap))


def test_config_beats_seed() -> None:
    # a google lane: seed says rpm 15, but explicit config says rpm 2 -> config wins.
    lane = _lane("g", "generativelanguage.googleapis.com", "gemini-3.1-flash-lite", rpm=2, tpm=60000)
    eff = EC.resolve(lane)
    assert eff.values["rpm"] == 2 and eff.sources["rpm"] == EC.SRC_CONFIG
    assert eff.values["tpm"] == 60000 and eff.sources["tpm"] == EC.SRC_CONFIG


def test_seed_fills_gap_when_config_absent() -> None:
    # config leaves rpm None; the google seed (rpm 15) fills it as the lowest layer.
    lane = _lane("g", "generativelanguage.googleapis.com", "gemini-3.1-flash-lite")
    eff = EC.resolve(lane)
    assert eff.values["rpm"] == 15 and eff.sources["rpm"] == EC.SRC_SEED


def test_null_seed_and_absent_config_stays_unknown_not_zero() -> None:
    # groq seed has rpd: null; config leaves rpd None -> effective None/unknown, NOT 0.
    lane = _lane("m", "api.groq.com", "groq/compound-mini")
    eff = EC.resolve(lane)
    assert eff.values["rpd"] is None and eff.sources["rpd"] == EC.SRC_UNKNOWN
    assert eff.values["rpd"] != 0


def test_observed_headers_beat_config() -> None:
    lane = _lane("m", "api.groq.com", "groq/compound-mini", rpd=230, rpm=2)
    eff = EC.resolve(lane, observed={"rpd": 100})
    assert eff.values["rpd"] == 100 and eff.sources["rpd"] == EC.SRC_OBSERVED
    # a field with no observed value falls back to config.
    assert eff.values["rpm"] == 2 and eff.sources["rpm"] == EC.SRC_CONFIG


def test_catalog_unavailable_still_resolves_from_config() -> None:
    lane = _lane("m", "api.groq.com", "groq/compound-mini", rpd=230)
    eff = EC.resolve(lane, seed={})           # empty seed = catalog unavailable
    assert eff.values["rpd"] == 230 and eff.sources["rpd"] == EC.SRC_CONFIG


def test_provider_slug_inference() -> None:
    assert EC._provider_slug("api.groq.com", "groq/compound") == "groq"
    assert EC._provider_slug("", "gemini-3.1-flash-lite") == "google"
    assert EC._provider_slug("openrouter.ai", "x") == "openrouter"
    assert EC._provider_slug("api.siliconflow.cn", "Qwen/Qwen3-8B") == "siliconflow"


def test_resolve_all_over_real_registry_is_isolated_per_lane() -> None:
    reg = LR.build_registry()
    effs = {e.lane: e for e in EC.resolve_all(reg)}
    # every real lane resolves; groq lanes keep their explicit config rpm (2), each
    # lane an independent object (no shared mutable state across accounts).
    assert "map_groq1" in effs and "map_groq2" in effs
    assert effs["map_groq1"].values["rpm"] == 2
    assert effs["map_groq1"] is not effs["map_groq2"]
    # seed_version is surfaced for provenance.
    assert effs["map_groq1"].seed_version == "rate-limit-seed-v1"
