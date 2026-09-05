"""Durable adaptive controllers (2026-08-29 owner flag: "the concurrency
code is dead — I asked for one that auto-finds the highest concurrency").

Proves: state survives a process restart (via the store), the local batch
budget climbs and halves like the concurrency limiter, the batched client
sizes its calls from the budget, and receipts carry the values captured at
the call. Pure: fake store, no DB, no network.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.llm_extraction.client import LLMCallResult, LLMExtractionClient
from polymath_shared.llm_extraction.contract import SanitizeResult
from polymath_shared.llm_extraction.limiter import (
    BUDGET_STREAK_FOR_INCREASE,
    SUCCESS_STREAK_FOR_INCREASE,
    AdaptiveBudget,
    LimiterRegistry,
    ProviderLimit,
)


class _FakeStore:
    def __init__(self, seed: dict | None = None) -> None:
        self.rows: dict[str, dict] = dict(seed or {})
        self.saves: list[tuple[str, dict]] = []

    def load(self, key):
        return self.rows.get(key)

    def save(self, key, state):
        self.rows[key] = dict(state)
        self.saves.append((key, dict(state)))


def test_limiter_restores_found_ceiling_after_restart() -> None:
    spec = ProviderLimit(kind="rate", rpm=1000, conc_cap=16, min=2, max=16, init=3)
    store = _FakeStore()
    reg1 = LimiterRegistry()
    reg1.attach_store(store)
    lim = reg1.lane("llm_cloud", "default", spec)
    assert lim.effective == 3                       # no history: yaml seed
    for _ in range(SUCCESS_STREAK_FOR_INCREASE * 5):
        lim.record_success()
    assert lim.effective == 8
    assert store.rows["llm_cloud[default]"]["effective"] == 8
    # "process restart": a fresh registry with the same store
    reg2 = LimiterRegistry()
    reg2.attach_store(store)
    lim2 = reg2.lane("llm_cloud", "default", spec)
    assert lim2.effective == 8                      # NOT back to the seed
    lim2.record_failure()
    assert lim2.effective == 4 and store.rows["llm_cloud[default]"]["effective"] == 4


def test_restore_clamps_to_current_ceiling_and_floor() -> None:
    store = _FakeStore({"llm_cloud[default]": {"effective": 99}})
    reg = LimiterRegistry()
    reg.attach_store(store)
    lim = reg.lane("llm_cloud", "default",
                   ProviderLimit(kind="rate", rpm=10, conc_cap=6, min=2, max=6))
    assert lim.effective == 6
    store2 = _FakeStore({"x[default]": {"effective": 0}})
    reg2 = LimiterRegistry()
    reg2.attach_store(store2)
    assert reg2.lane("x", "default", ProviderLimit(kind="concurrency", min=1, max=4)).effective == 1


def test_attach_after_creation_restores_existing_lanes() -> None:
    reg = LimiterRegistry()
    lim = reg.lane("llm_cloud", "default", ProviderLimit(kind="rate", rpm=10, conc_cap=8, init=3))
    assert lim.effective == 3
    reg.attach_store(_FakeStore({"llm_cloud[default]": {"effective": 7}}))
    assert lim.effective == 7


def test_budget_aimd_and_persistence() -> None:
    store = _FakeStore()
    reg = LimiterRegistry()
    reg.attach_store(store)
    b = reg.budget("llm_local:batch_tokens", seed=28000, floor=4000, ceiling=40000, step=2000)
    for _ in range(BUDGET_STREAK_FOR_INCREASE):
        b.record_success()
    assert b.effective == 30000
    assert store.rows["llm_local:batch_tokens"]["effective"] == 30000
    b.record_oom()
    assert b.effective == 15000
    assert store.rows["llm_local:batch_tokens"]["ooms"] == 1
    for _ in range(BUDGET_STREAK_FOR_INCREASE * 100):
        b.record_success()
    assert b.effective == 40000                     # ceiling respected
    b2 = AdaptiveBudget("t", seed=10, floor=5, ceiling=100, step=1)
    b2.restore({"effective": 1_000_000})
    assert b2.effective == 100
    assert b2.restore({"effective": "junk"}) is False


def test_batched_client_sizes_calls_from_the_budget(monkeypatch) -> None:
    reg = LimiterRegistry()
    monkeypatch.setattr(client_mod, "REGISTRY", reg)
    monkeypatch.setenv(client_mod.LOCAL_BATCH_TOKENS_SEED_ENV, "5000")   # ≥ floor (4,000)
    monkeypatch.setenv(client_mod.LOCAL_BATCH_TOKENS_MAX_ENV, "40000")
    client = LLMExtractionClient("local", url="http://127.0.0.1:1", model="m")
    seen: list[tuple[int, int | None]] = []

    def _fake(prompt_items, limiter, decision, cap=None, use_lean=False, system_prompt=None):   # mirrors _infer_batch_call
        seen.append((len(prompt_items), cap))
        return [LLMCallResult(lane="local", model="m", raw_text="", packet=None,
                              sanitize=SanitizeResult(ok=False), wall_ms=0,
                              limiter_effective=limiter.effective, batch_tokens_cap=cap)
                for _ in prompt_items]

    monkeypatch.setattr(client, "_infer_batch_call", _fake)
    # each neighborhood ≈ 2,000 chars → ~500 input tokens + ≥400 output budget
    hoods = [(f"n{i}", [(f"c{i}", "word " * 400)]) for i in range(6)]
    results = client.extract_batched(hoods, source_bytes=10, threshold_bytes=300_000)
    assert len(results) == 6
    assert all(cap == 5000 for _, cap in seen)
    assert len(seen) >= 2                           # split under the 5,000 cap
    assert all(r.batch_tokens_cap == 5000 and r.limiter_effective >= 1 for r in results)
    # climb: 4 clean batches → +2,000 on the persisted budget
    budget = client_mod.local_batch_budget()
    for _ in range(BUDGET_STREAK_FOR_INCREASE):
        budget.record_success()
    assert client_mod.local_batch_budget().effective == 7000


def test_receipts_carry_values_captured_at_the_call() -> None:
    from workers.llm_provider import call_receipts
    r = LLMCallResult(lane="cloud", model="m", raw_text="", packet=None,
                      sanitize=SanitizeResult(ok=False, error_class="SANITIZE_UNPARSEABLE"),
                      wall_ms=5, limiter_effective=7, batch_tokens_cap=None)
    rec = call_receipts([r])[0]
    assert rec["limiter_effective"] == 7 and rec["batch_tokens_cap"] is None
    assert rec["error_class"] == "SANITIZE_UNPARSEABLE"
