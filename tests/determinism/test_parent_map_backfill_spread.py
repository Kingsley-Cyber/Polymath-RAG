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
    monkeypatch.setattr(map_prompt, "build_map_prompt", lambda skeletons, is_combined=False: ("sys", "user"))

    class _FakeClient:
        def __init__(self, *a, **k):
            self.endpoint_name = None

        def complete_one(self, user, system_prompt=None, max_tokens=0):
            return "{}", None  # (raw, err) — no real network

    monkeypatch.setattr(client_mod, "LLMExtractionClient", _FakeClient)

    lane_counter: Counter = Counter()
    infer = mod._routed_infer(lane_counter)
    for _ in range(60):
        infer([{"alias": "p", "text": "t"}])

    # Perfect 6-way spread — no single account carries the batch (the pin bug).
    assert set(lane_counter) == set(names), lane_counter
    assert all(lane_counter[n] == 10 for n in names), dict(lane_counter)
    assert max(lane_counter.values()) - min(lane_counter.values()) == 0


def test_backfill_infer_raises_when_no_endpoints(monkeypatch):
    mod = _load_backfill()
    import polymath_shared.llm_extraction.pool as pool
    monkeypatch.setattr(pool, "stage_pin", lambda stage: [])
    monkeypatch.setattr(pool, "cloud_endpoints", lambda: [])
    infer = mod._routed_infer(Counter())
    raised = False
    try:
        infer([{"alias": "p", "text": "t"}])
    except RuntimeError:
        raised = True
    assert raised, "empty endpoint pool must raise, not silently pin"
