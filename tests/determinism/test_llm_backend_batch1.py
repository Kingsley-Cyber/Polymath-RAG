"""LLM-BACKEND-BATCH1 (register 11.464): the eight backend clean-up fixes.

Gaps (docs/wiki/plans/GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md): L-08 stale adopted ceilings, L-09 a local refusal
failing a profile for good, L-10 one OpenRouter limiter family for three accounts, L-12 dead / slow lanes, L-13 the
timing-out compiler lane, L-16 qwen's output-per-minute cap, L-17 attempt rows without a stage. (L-18 is a live
.env line.) Pure tests: no database, no network, no model call.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = json.loads((ROOT / "config/cloud_providers.json").read_text())
LIMITS = yaml.safe_load((ROOT / "config/extraction_models/limiter.yaml").read_text())["providers"]
BY_NAME = {e["name"]: e for e in PROVIDERS["providers"]}


# ---- L-09: a local limiter refusal holds the profile ticket instead of burning an attempt

def test_a_local_limiter_refusal_is_transient_for_profiles():
    from workers.doc_profile_worker import transient_pool_error

    assert transient_pool_error({"attempts": [{"error": "LIMITER_REFUSED"}]}, "LIMITER_REFUSED")
    assert transient_pool_error({"attempts": [{"error": "HTTP_429"}, {"error": "LIMITER_REFUSED"}]}, "LIMITER_REFUSED")
    # a real document fault still fails the attempt
    assert not transient_pool_error({"attempts": [{"error": "HTTP_401"}]}, "HTTP_401")


# ---- L-08: a header-adopted ceiling is reused only under the limits it was learned with

def _limiter(tpm: int = 8000, family: str = "groq_acct_2_gpt_oss_20b"):
    from polymath_shared.llm_extraction.limiter import AdaptiveLimiter, ProviderLimit

    return AdaptiveLimiter("map_groq2", ProviderLimit(kind="rate", rpm=2, tpm=tpm, family=family, min=1, max=2))


def test_restore_reuses_an_adopted_ceiling_under_the_same_limits():
    lim = _limiter()
    state = {**lim.state(), "adopted_tpm": 12000.0}
    fresh = _limiter()
    assert fresh.restore(state)
    assert fresh.state()["adopted_tpm"] == 12000.0


def test_restore_drops_a_ceiling_learned_under_other_limits():
    # the measured case: 70,000 TPM adopted from the retired compound model on a lane now configured at 8,000
    old = _limiter(tpm=70000, family="groq_acct_2")
    state = {**old.state(), "adopted_tpm": 70000.0}
    fresh = _limiter()
    assert fresh.restore(state)
    assert fresh.state()["adopted_tpm"] is None


def test_restore_drops_a_ceiling_from_a_row_written_before_fingerprints():
    state = {**_limiter().state(), "adopted_tpm": 70000.0}
    state.pop("spec_fingerprint")
    fresh = _limiter()
    assert fresh.restore(state)
    assert fresh.state()["adopted_tpm"] is None


def test_the_fingerprint_changes_with_the_configured_limits():
    assert _limiter().spec_fingerprint() == _limiter().spec_fingerprint()
    assert _limiter().spec_fingerprint() != _limiter(tpm=70000).spec_fingerprint()
    assert _limiter().spec_fingerprint() != _limiter(family="groq_acct_2").spec_fingerprint()


# ---- L-10: one limiter family per OpenRouter account

def test_openrouter_families_are_one_per_account():
    fams: dict[str, set[str]] = {}
    for lane, spec in LIMITS.items():
        fam = (spec or {}).get("family") or ""
        if fam.startswith("openrouter"):
            fams.setdefault(fam, set()).add(BY_NAME[lane]["api_key_env"])
    assert "openrouter" not in fams, "the shared family spanning three accounts is gone"
    assert fams, "OpenRouter lanes still carry families"
    for fam, keys in fams.items():
        assert len(keys) == 1, f"{fam} spans accounts {sorted(keys)}"
    assert len(fams) == len({k for keys in fams.values() for k in keys})


# ---- L-12 / L-13: dead and slow lanes parked; the compiler pin skips the timing-out lane

def test_slow_extraction_lanes_are_parked():
    for name in ("nvidia", "nvidia2", "siliconflow1", "siliconflow2", "siliconflow3"):
        assert BY_NAME[name]["enabled"] is False, name


def test_the_compiler_pin_skips_the_timing_out_qwen_lane_and_keeps_backups():
    pin = PROVIDERS["stage_pins"]["chat_compiler"]
    assert "compiler_alibaba_qwen" not in pin
    assert "compiler_alibaba_qwen" in BY_NAME, "the lane stays defined (rollback = re-pin)"
    assert pin[:1] and len(pin) >= 2


def test_the_primary_lane_can_be_parked_but_the_pool_never_goes_empty(monkeypatch):
    from types import SimpleNamespace

    from polymath_shared.llm_extraction import pool

    def settings(primary: bool):
        # a stub for pool's own settings lookup: the process-wide settings cache stays untouched
        side = SimpleNamespace(llm_cloud_url="http://127.0.0.1:11434", llm_cloud_model="m",
                               llm_cloud_primary=primary, llm_cloud_extra_endpoints="")
        return lambda: SimpleNamespace(sidecars=side)

    fake = [pool.CloudEndpoint("gemini1", "https://example.invalid", "m")]
    monkeypatch.setattr(pool, "_configured_providers", lambda: list(fake))
    monkeypatch.setattr(pool, "get_settings", settings(False))
    assert [e.name for e in pool.cloud_endpoints()] == ["gemini1"]
    monkeypatch.setattr(pool, "_configured_providers", list)
    assert [e.name for e in pool.cloud_endpoints()] == ["primary"]
    monkeypatch.setattr(pool, "_configured_providers", lambda: list(fake))
    monkeypatch.setattr(pool, "get_settings", settings(True))
    assert [e.name for e in pool.cloud_endpoints()] == ["gemini1", "primary"]


def test_the_primary_switch_reads_its_env_variable(monkeypatch):
    from polymath_shared.settings import Settings

    monkeypatch.setenv("POLYMATH_LLM_CLOUD_PRIMARY", "0")
    assert Settings().sidecars.llm_cloud_primary is False
    monkeypatch.setenv("POLYMATH_LLM_CLOUD_PRIMARY", "1")
    assert Settings().sidecars.llm_cloud_primary is True


# ---- L-16: a lane can ask for less output than the stage default

def test_lane_max_tokens_lowers_the_stage_budget_only_when_the_lane_says_so():
    from polymath_shared.llm_extraction.pool import CloudEndpoint, lane_max_tokens

    assert lane_max_tokens(CloudEndpoint("a", "u", "m", max_output_tokens=900), 2400) == 900
    assert lane_max_tokens(CloudEndpoint("a", "u", "m", max_output_tokens=3000), 2400) == 2400
    assert lane_max_tokens(CloudEndpoint("a", "u", "m"), 2400) == 2400


def test_the_qwen_pmap_lanes_cap_their_output_below_otpm_1000():
    for n in range(2, 7):
        assert BY_NAME[f"map_groq{n}q"]["max_output_tokens"] == 900
    # the gpt-oss lanes keep the stage default
    assert "max_output_tokens" not in BY_NAME["map_groq2"]


# ---- L-17: attempt rows carry a stage even from worker threads

def test_merged_tags_fall_back_to_the_client_tags_and_the_context_wins():
    from polymath_shared.conformance.attempts import merged_tags

    assert merged_tags({}, stage="extract", function="EXTRACT") == {"stage": "extract", "function": "EXTRACT"}
    ctx = {"stage": "doc_parent_map", "function": "PMAP", "run_id": "r1"}
    assert merged_tags(ctx, stage="extract", function="EXTRACT") == ctx
    assert merged_tags({"run_id": "r1"}) == {"run_id": "r1"}


def test_the_client_records_attempts_with_its_tags(monkeypatch):
    from polymath_shared.conformance import attempts
    from polymath_shared.llm_extraction.client import LLMExtractionClient

    seen: list[dict] = []
    monkeypatch.setattr(attempts, "record", lambda a: seen.append(dict(attempts._ctx.get())))
    client = LLMExtractionClient.__new__(LLMExtractionClient)       # no network, no limiter
    client.attempt_stage, client.attempt_function = "doc_profile", "PROFILE"
    client._record_attempt(object())
    assert seen[-1]["stage"] == "doc_profile" and seen[-1]["function"] == "PROFILE"
    # an explicit attempt_context still wins
    with attempts.attempt_context(function="PMAP", stage="doc_parent_map", run_id="r1"):
        client._record_attempt(object())
    assert seen[-1]["stage"] == "doc_parent_map" and seen[-1]["function"] == "PMAP"
    # tags never leak past the recording
    assert not attempts._ctx.get().get("stage")
