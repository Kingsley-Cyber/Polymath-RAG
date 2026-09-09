"""BACKFILL-SPREAD-V1 — the parent-map backfill distributes map inference evenly across
the six distinct-account endpoints (round-robin), instead of pinning to the lexically-first
account the way the capacity-blind `route()` did in a dedicated backfill process."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from collections import Counter

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
