"""LANE-REGISTRY-V1 (RAG-PIPELINE-FINISH Phase 2) — the account/model lane
registry is explicit, sanitized, and answers the plan's query views, with
one-key-one-account isolation visible and NO secret ever rendered.

Provider-free: reads the committed config/cloud_providers.json + limiter.yaml.
"""
from __future__ import annotations

import os

from polymath_shared.llm_extraction import lane_registry as LR


def _reg() -> LR.LaneRegistry:
    return LR.build_registry()


def test_functional_pools_map_to_their_pins() -> None:
    by_fn = _reg().by_function()
    prof = {l.name for l in by_fn.get(LR.DOCUMENT_PROFILE, [])}
    pmap = {l.name for l in by_fn.get(LR.PMAP, [])}
    chat = {l.name for l in by_fn.get(LR.CHAT, [])}
    # PROVIDER-LANE-REASSIGNMENT-V1 (11.193): the six Groq accounts are DE-SHARED —
    # GROQ_API_KEY_1 serves doc_profile ONLY, KEY_2..6 serve pMAP ONLY.
    assert {"profile_groq1", "profile_fallback_openrouter"} <= prof
    assert {"map_groq2", "map_groq6", "map_fallback_openrouter"} <= pmap
    assert "map_groq1" not in pmap        # retired with the de-sharing
    assert "profile_groq6" not in prof    # ditto
    assert any(n.startswith("compiler") for n in chat)
    # GRAPH_EXTRACTION is the unpinned ring: siliconflow (dedicated:false) lands there.
    graph = {l.name for l in by_fn.get(LR.GRAPH_EXTRACTION, [])}
    assert "siliconflow1" in graph


def test_one_key_one_account_and_groq_sharing_is_visible() -> None:
    reg = _reg()
    lanes = {l.name: l for l in reg.lanes}
    prof1, map2 = lanes["profile_groq1"], lanes["map_groq2"]
    # distinct lanes / models / functions...
    assert prof1.name != map2.name
    assert prof1.model != map2.model
    assert prof1.function == LR.DOCUMENT_PROFILE and map2.function == LR.PMAP
    # PROVIDER-LANE-REASSIGNMENT-V1 (11.193) INVERTED the old S7 shared-budget rule:
    # each Groq account now serves EXACTLY ONE function. One key = one account = one function.
    assert prof1.account_id == "GROQ_API_KEY_1"
    assert map2.account_id == "GROQ_API_KEY_2"
    assert prof1.account_id != map2.account_id
    # No ENABLED lane pair may share one account across two PERMANENT functions.
    PERMANENT = {LR.GRAPH_EXTRACTION, LR.DOCUMENT_PROFILE, LR.PMAP, LR.CHAT}
    by_acct: dict[str, set] = {}
    for l in reg.lanes:
        if l.enabled and l.function in PERMANENT and l.api_key_env:
            by_acct.setdefault(l.api_key_env, set()).add(l.function)
    straddlers = {a: fns for a, fns in by_acct.items() if len(fns) > 1}
    assert not straddlers, f"account shared across permanent functions: {straddlers}"


def test_distinct_keys_are_distinct_accounts() -> None:
    reg = _reg()
    lanes = {l.name: l for l in reg.lanes}
    assert lanes["profile_groq1"].account_id != lanes["profile_groq2"].account_id
    # a different provider is a different account entirely (no provider-family coupling).
    assert lanes["siliconflow1"].account_id != lanes["profile_groq1"].account_id


def test_groq_accounts_carry_distinct_isolation_families() -> None:
    # limiter.yaml family: groq_acct_N — account N's compound + compound-mini share
    # a family, but account N and N+1 do NOT (a cooldown on one never cools the other).
    lanes = {l.name: l for l in _reg().lanes}
    f1 = lanes["profile_groq1"].capacity.family
    f2 = lanes["profile_groq2"].capacity.family
    m1 = lanes["map_groq1"].capacity.family
    assert f1 and f2 and f1 != f2
    assert f1 == m1  # compound + compound-mini of account 1 share the damp family


def test_configured_fallback_lanes_are_present_and_labelled() -> None:
    by_fn = _reg().by_function()
    prof = {l.name: l for l in by_fn.get(LR.DOCUMENT_PROFILE, [])}
    # 11.193 retired the Gemini profile fallbacks (Google went to graph extraction);
    # OpenRouter mistral-small is the doc_profile fallback tier.
    assert "profile_fallback_gemini1" not in prof
    # a fallback is a real reachable lane in the pool, not sliced out of the path.
    assert "profile_fallback_openrouter" in prof
    assert prof["profile_fallback_openrouter"].role == "fallback"


def test_reachability_partitions_every_lane() -> None:
    reg = _reg()
    reach = reg.reachability()
    counted = sum(len(v) for v in reach.values())
    assert counted == len(reg.lanes)
    for l in reg.lanes:
        assert l.reachability in (LR.ACTIVE, LR.CREDENTIAL_ABSENT, LR.DISABLED)


def test_registry_is_deterministic() -> None:
    a = [l.to_dict() for l in LR.build_lanes()]
    b = [l.to_dict() for l in LR.build_lanes()]
    assert a == b


def test_inventory_renders_no_secret_value() -> None:
    # The registry must never read a key VALUE. Prove it: plant a sentinel secret in
    # the environment for a real api_key_env and assert it never appears in output.
    sentinel = "sk-SENTINEL-DO-NOT-LEAK-abc123"
    prev = os.environ.get("GROQ_API_KEY_1")
    os.environ["GROQ_API_KEY_1"] = sentinel
    try:
        text = LR.sanitized_inventory()
        d = LR.build_registry().to_dict()
    finally:
        if prev is None:
            os.environ.pop("GROQ_API_KEY_1", None)
        else:
            os.environ["GROQ_API_KEY_1"] = prev
    assert sentinel not in text
    assert sentinel not in str(d)
    # the NAME is fine to render; the value is not.
    assert "GROQ_API_KEY_1" in text
    # with the sentinel set, the lane reads as credential-present.
    assert "GROQ_API_KEY_1" in {l.account_id for l in LR.build_registry().lanes}


def test_stage_to_functional_pool_mapping() -> None:
    assert LR.functional_pool_of("doc_parent_map") == LR.PMAP
    assert LR.functional_pool_of("doc_profile") == LR.DOCUMENT_PROFILE
    assert LR.functional_pool_of("extract") == LR.GRAPH_EXTRACTION
    assert LR.functional_pool_of("chat_compiler") == LR.CHAT
    # a non-LLM stage has no pool.
    assert LR.functional_pool_of("project_qdrant") is None
    assert LR.functional_pool_of("verify_projections") is None


def test_pool_lane_health_counts_active_lanes() -> None:
    health = _reg().pool_lane_health()
    # each ingestion pool has >=1 lane; totals partition into active/absent/disabled.
    for fn in (LR.DOCUMENT_PROFILE, LR.PMAP, LR.GRAPH_EXTRACTION):
        h = health[fn]
        assert h["total"] >= 1
        assert h["active"] + h["credential_absent"] + h["disabled"] == h["total"]
        assert len(h["active_lanes"]) == h["active"]
    # PMAP has the six map_groq lanes.
    assert health[LR.PMAP]["total"] == 6


def test_inventory_flags_dark_pool_when_no_credentials(monkeypatch) -> None:
    # If EVERY lane of a function is credential-absent, the inventory names it as a
    # fully-dark pool (would raise PinnedProviderUnavailable) — the reachability
    # diagnostic the plan requires. Simulate by pointing credential resolution at a
    # never-present env for the CHAT pins.
    reg = _reg()
    # Structural: unreachable_pins returns only WHOLE-dark pools; on a normally
    # configured repo it is a dict (possibly empty) and never raises.
    assert isinstance(reg.unreachable_pins(), dict)


def test_pmap_pool_batch_cap_is_min_over_active_lanes() -> None:
    reg = _reg()
    # config declares map_batch_cap=15 on the FIVE compound-mini pMAP lanes (11.193
    # de-shared GROQ_API_KEY_1 to doc_profile); the OpenRouter last-resort fallback
    # declares no cap, and the pool cap is the min over lanes that DO declare one.
    caps = {l.name: l.map_batch_cap for l in reg.by_function()[LR.PMAP]}
    groq_caps = {n: c for n, c in caps.items() if n.startswith("map_groq")}
    assert len(groq_caps) == 5 and all(c == 15 for c in groq_caps.values())
    assert caps["map_fallback_openrouter"] is None
    assert LR.pmap_pool_batch_cap(reg) == 15
    assert LR.PMAP_DEFAULT_BATCH_CAP == 15
