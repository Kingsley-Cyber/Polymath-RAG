"""BACKFILL-SPREAD-V1 — the parent-map backfill distributes map inference evenly across
the six distinct-account endpoints (round-robin), instead of pinning to the lexically-first
account the way the capacity-blind `route()` did in a dedicated backfill process."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from collections import Counter

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load_backfill():
    spec = importlib.util.spec_from_file_location(
        "parent_map_backfill", str(ROOT / "scripts" / "parent_map_backfill.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_endpoint(name: str):
    return types.SimpleNamespace(
        name=name, url="http://x", model="groq/compound-mini", limiter_key=name,
        api_key=f"key-{name}", cloud_opts={})


def test_backfill_infer_round_robins_evenly_across_six_accounts(monkeypatch):
    mod = _load_backfill()
    names = [f"map_groq{i}" for i in range(1, 7)]

    # Patch the endpoint discovery + the LLM client where _routed_infer looks them up
    # (deferred imports inside the closure resolve to the live module attributes).
    import polymath_shared.llm_extraction.pool as pool
    import polymath_shared.llm_extraction.client as client_mod

    monkeypatch.setattr(pool, "stage_pin", lambda stage: list(names))
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: [_fake_endpoint(n) for n in names])

    # The round-robin is upstream of prompt building; stub it so the test needs no real skeletons.
    import polymath_shared.document_profile.map_prompt as map_prompt
    monkeypatch.setattr(map_prompt, "build_map_prompt",
                        lambda skeletons, is_combined=False, grounding=None: ("sys", "user"))

    class _FakeClient:
        def __init__(self, *a, **k):
            self.endpoint_name = None
            self._last_http_dispatched = True   # models a real 2xx dispatch
            self._last_refusal_reason = None

        def complete_one(self, user, system_prompt=None, max_tokens=0):
            return "{}", None  # (raw, err) — no real network

    monkeypatch.setattr(client_mod, "LLMExtractionClient", _FakeClient)

    lane_selected: Counter = Counter()
    dispatch: Counter = Counter()
    infer = mod._routed_infer(lane_selected, dispatch)
    for _ in range(60):
        infer([{"alias": "p", "text": "t"}])

    # Perfect 6-way spread — no single account carries the batch (the pin bug) —
    # AND selection now tracks dispatch separately (both even here).
    assert set(lane_selected) == set(names), lane_selected
    assert all(lane_selected[n] == 10 for n in names), dict(lane_selected)
    assert max(lane_selected.values()) - min(lane_selected.values()) == 0
    assert all(dispatch[n] == 10 for n in names), dict(dispatch)


def test_backfill_infer_raises_when_no_endpoints(monkeypatch):
    mod = _load_backfill()
    import polymath_shared.llm_extraction.pool as pool
    monkeypatch.setattr(pool, "stage_pin", lambda stage: [])
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: [])
    infer = mod._routed_infer(Counter(), Counter())
    raised = False
    try:
        infer([{"alias": "p", "text": "t"}])
    except RuntimeError:
        raised = True
    assert raised, "empty endpoint pool must raise, not silently pin"


def test_summary_surfaces_internal_failures_when_errored_docs_is_zero():
    """GROQ-MAP-CONTROL-PLANE-REPAIR-V1 Phase 9: a doc that returned normally
    (no escaped exception) but whose every batch was a LOCAL limiter refusal maps
    0 parents. errored_docs stays 0, yet the failures MUST be visible and PASS
    False — `+0 / 0-errors` can never again read as a clean provider run."""
    mod = _load_backfill()
    rows = [{
        "doc": "D", "eligible": 15, "already_mapped": 0, "newly_mapped": 0,
        "mapped": 0, "complete": False, "unresolved": 15,
        "batches_done": 0, "batches_partial": 1, "attempts_used": 3,
        "errors_n": 3, "limiter_refusals": 3, "http_dispatches": 0,
        "http_429": 0, "http_failures": 0, "empty_completions": 0,
        "compiler_complete": 0, "compiler_partial": 0, "compiler_invalid": 0,
        "refusal_reasons": ["FAMILY_GATE"], "projected": None,
    }]
    s = mod.summarize("cinema", rows, Counter({"map_groq1": 3}), Counter(),
                      concurrency=6, wall_s=1.0)
    assert s["errored_docs"] == 0                     # nothing RAISED
    assert s["documents_with_internal_errors"] == 1   # ...but failures are VISIBLE
    assert s["limiter_refusals"] == 3
    assert s["http_dispatches"] == 0                  # 0 HTTP => 0 provider spend
    assert s["lane_selection"] == {"map_groq1": 3}    # selections, NOT dispatches
    assert s["provider_http_dispatch"] == {}
    assert s["PASS"] is False


def test_summary_pass_only_when_complete_and_clean():
    mod = _load_backfill()
    rows = [{"doc": "D", "eligible": 15, "already_mapped": 0, "newly_mapped": 15,
             "mapped": 15, "complete": True, "unresolved": 0, "batches_done": 1,
             "batches_partial": 0, "attempts_used": 1, "errors_n": 0,
             "limiter_refusals": 0, "http_dispatches": 1, "http_429": 0,
             "http_failures": 0, "empty_completions": 0, "compiler_complete": 1,
             "compiler_partial": 0, "compiler_invalid": 0, "refusal_reasons": [],
             "projected": 15}]
    s = mod.summarize("cinema", rows, Counter({"map_groq1": 1}),
                      Counter({"map_groq1": 1}), concurrency=6, wall_s=1.0)
    assert s["PASS"] is True and s["maps_persisted"] == 15
    assert s["distinct_accounts_dispatched"] == 1


# ── CLOUDFLARE-PMAP-V1: local-refusal failover + per-batch provenance ──────────────────
def _multi_provider_pool(monkeypatch, behaviour):
    """behaviour: lane name -> ("refuse", reason) | ("fault", err) | ("ok", raw)."""
    import polymath_shared.llm_extraction.pool as pool
    import polymath_shared.llm_extraction.client as client_mod
    import polymath_shared.document_profile.map_prompt as map_prompt
    urls = {"map_groq2": "https://api.groq.com/openai",
            "cloudflare_map2": "https://api.cloudflare.com/client/v4/accounts/ACC/ai",
            "map_fallback_openrouter": "https://openrouter.ai/api"}
    models = {"map_groq2": "groq/compound-mini", "cloudflare_map2": "@cf/qwen/qwen3-30b-a3b-fp8",
              "map_fallback_openrouter": "mistralai/mistral-small-2603"}
    names = list(behaviour)
    eps = [types.SimpleNamespace(name=n, url=urls[n], model=models[n], limiter_key=n, api_key="k", cloud_opts={})
           for n in names]
    monkeypatch.setattr(pool, "stage_pin", lambda stage: list(names))
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: list(eps))
    monkeypatch.setattr(map_prompt, "build_map_prompt",
                        lambda skeletons, is_combined=False, grounding=None: ("sys", "user"))
    by_url = {urls[n]: behaviour[n] for n in names}

    class _FakeClient:
        def __init__(self, *a, **k):
            self.kind, self.payload = by_url[k["url"]]
            self.endpoint_name = None
            self._last_refusal_reason = None
            self._last_http_dispatched = False

        def complete_one(self, user, system_prompt=None, max_tokens=0):
            if self.kind == "refuse":                      # limiter said no: 0 HTTP
                self._last_http_dispatched = False
                self._last_refusal_reason = self.payload
                return "", "LIMITER_REFUSED"
            self._last_http_dispatched = True
            if self.kind == "fault":                       # dispatched provider fault
                return "", self.payload
            return self.payload, None
    monkeypatch.setattr(client_mod, "LLMExtractionClient", _FakeClient)


def test_backfill_infer_fails_over_a_local_refusal_to_the_next_lane_and_labels_it(monkeypatch):
    """A Groq account parked on its daily budget refuses admission (0 HTTP). The batch must
    NOT be deferred to the next pass: the ring hands it to the next lane (Cloudflare), the
    refusal is counted per lane, dispatch is counted on the lane that served, and the
    provenance labels name the provider FAMILY that actually answered."""
    mod = _load_backfill()
    _multi_provider_pool(monkeypatch, {"map_groq2": ("refuse", "REFUSE_PROVIDER_RPD"),
                                       "cloudflare_map2": ("ok", "MAP|P0001|sig|a;b;c"),
                                       "map_fallback_openrouter": ("ok", "MAP|P0001|sig|a;b;c")})
    sel, disp, ref = Counter(), Counter(), Counter()
    infer = mod._routed_infer(sel, disp, ref)
    raw = infer([{"alias": "P0001"}])                        # round-robin starts on map_groq2
    assert raw == "MAP|P0001|sig|a;b;c"
    assert ref == {"map_groq2": 1}                            # the refusal is VISIBLE, per lane
    assert disp == {"cloudflare_map2": 1}                     # exactly one HTTP request left the box
    assert sel == {"map_groq2": 1, "cloudflare_map2": 1}      # selections != dispatches
    assert infer.last_provider == "cloudflare"                # family, never the lane name
    assert infer.last_model == "@cf/qwen/qwen3-30b-a3b-fp8"


def test_backfill_infer_all_lanes_refused_raises_undispatched(monkeypatch):
    mod = _load_backfill()
    from workers.doc_parent_map_worker import MapInferError
    _multi_provider_pool(monkeypatch, {"map_groq2": ("refuse", "REFUSE_PROVIDER_RPD"),
                                       "cloudflare_map2": ("refuse", "FAMILY_GATE"),
                                       "map_fallback_openrouter": ("refuse", "REFUSE_PROVIDER_RPD")})
    sel, disp, ref = Counter(), Counter(), Counter()
    infer = mod._routed_infer(sel, disp, ref)
    with pytest.raises(MapInferError) as ei:
        infer([{"alias": "P0001"}])
    assert ei.value.dispatched is False                       # 0 HTTP, 0 spend -> LIMITER_REFUSED terminal
    assert sum(ref.values()) == 3 and disp == {}              # every lane tried once, none dispatched


def test_backfill_infer_dispatched_fault_is_not_retried_on_another_lane(monkeypatch):
    """A 429/5xx that COST a request defers (as before) — failover is for FREE refusals only,
    so a provider outage never doubles spend."""
    mod = _load_backfill()
    from workers.doc_parent_map_worker import MapInferError
    _multi_provider_pool(monkeypatch, {"map_groq2": ("fault", "HTTP_429"),
                                       "cloudflare_map2": ("ok", "MAP|P0001|sig|a;b;c")})
    sel, disp, ref = Counter(), Counter(), Counter()
    infer = mod._routed_infer(sel, disp, ref)
    with pytest.raises(MapInferError) as ei:
        infer([{"alias": "P0001"}])
    assert ei.value.dispatched is True and ei.value.error_class == "HTTP_429"
    assert disp == {"map_groq2": 1} and ref == {}             # one paid request, no second lane
    assert infer.last_provider == "groq"                      # the batch is labelled with the lane that FAILED


def test_summary_surfaces_local_refusals_per_lane():
    mod = _load_backfill()
    s = mod.summarize("cinema", [], Counter(), Counter(), concurrency=6, wall_s=0.1,
                      refused=Counter({"map_groq2": 4}))
    assert s["lane_local_refusals"] == {"map_groq2": 4}


def test_provider_family_is_derived_from_the_endpoint_host():
    from workers.doc_parent_map_worker import provider_family
    assert provider_family("https://api.groq.com/openai", "map_groq2") == "groq"
    assert provider_family("https://api.cloudflare.com/client/v4/accounts/ACC/ai", "cloudflare_map2") == "cloudflare"
    assert provider_family("https://openrouter.ai/api", "map_fallback_openrouter") == "openrouter"
    assert provider_family("", "lane_x") == "lane_x"          # unknown -> lane name, never None-crash


def test_backfill_lanes_allow_list_restricts_the_ring_without_widening_it(monkeypatch):
    """`--lanes` (operator override) keeps only the named ACTIVE lanes for this run — an exhausted
    account is skipped instead of eating 429s — and an unknown name is ignored, never invented."""
    mod = _load_backfill()
    _multi_provider_pool(monkeypatch, {"map_groq2": ("ok", "MAP|P0001|sig|a;b;c"),
                                       "cloudflare_map2": ("ok", "MAP|P0001|sig|a;b;c"),
                                       "map_fallback_openrouter": ("ok", "MAP|P0001|sig|a;b;c")})
    sel, disp, ref = Counter(), Counter(), Counter()
    infer = mod._routed_infer(sel, disp, ref, lanes={"cloudflare_map2", "map_fallback_openrouter", "ghost_lane"})
    for _ in range(6):
        infer([{"alias": "P0001"}])
    assert set(disp) == {"cloudflare_map2", "map_fallback_openrouter"}     # groq2 never picked
    assert disp["cloudflare_map2"] == 3 and disp["map_fallback_openrouter"] == 3
    assert "ghost_lane" not in sel                                          # not invented
