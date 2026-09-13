"""RPD-DURABILITY-V1 (D-4) — the day counter survives a restart.

U2-PERSISTENCE-CANARY-V1 measured (2026-09-10) that `llm_controller_state` held NO row
for any pMAP lane even though those lanes had dispatched thousands of requests: the
only writer was `_emit_change()`, which fires when the AIMD controller CHANGES SHAPE.
A lane running steadily at concurrency 1 that never adapts — exactly the pMAP lanes —
never emitted a change, so `day_count` lived in memory and died with the worker.

Provider-free: an in-memory store stands in for Postgres (same `ControllerStore`
protocol the real `PostgresControllerStore` implements).
"""
from __future__ import annotations

from polymath_shared.llm_extraction import limiter as L


class MemStore:
    """The ControllerStore protocol, in memory. Mirrors PostgresControllerStore."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.writes = 0

    def load(self, key: str) -> dict | None:
        return dict(self.rows[key]) if key in self.rows else None

    def save(self, key: str, state: dict) -> None:
        self.rows[key] = dict(state)
        self.writes += 1


def _lane(name: str = "map_groq2", rpd: int = 250) -> L.AdaptiveLimiter:
    spec = L.ProviderLimit(kind="rate", rpm=600, tpm=1_000_000, rpd=rpd, conc_cap=2)
    return L.AdaptiveLimiter(name, spec)


def _wire(lim: L.AdaptiveLimiter, store: MemStore, key: str) -> None:
    lim.restore(store.load(key))
    lim._on_change = lambda state, _k=key: store.save(_k, state)


def _dispatch(lim: L.AdaptiveLimiter, n: int = 1) -> None:
    for _ in range(n):
        d = lim.admit(est_tokens=10, block=False)
        assert d.admitted, f"admission refused: {d.reason}"
        lim.release()


def test_a_steady_lane_persists_its_day_count_without_any_aimd_move() -> None:
    """THE REGRESSION: no 429, no adaptation — and the counter must still be durable."""
    store, key = MemStore(), "llm_cloud[map_groq2]"
    lim = _lane(); _wire(lim, store, key)
    lim.RPD_PERSIST_MIN_INTERVAL_S = 0.0

    _dispatch(lim, 3)
    lim.flush_rpd()

    assert key in store.rows, "a steady lane persisted nothing — D-4 has regressed"
    row = store.rows[key]
    assert row["day_count"] == 3
    assert row["decreases"] == 0 and row["increases"] == 0   # it never adapted
    assert row["last_dispatch_at"]                            # last update recorded


def test_restart_continues_from_durable_truth() -> None:
    """dispatch -> durable count changes -> restart -> restored -> next continues."""
    store, key = MemStore(), "llm_cloud[map_groq3]"

    lim1 = _lane("map_groq3"); _wire(lim1, store, key)
    lim1.RPD_PERSIST_MIN_INTERVAL_S = 0.0
    _dispatch(lim1, 4)
    lim1.flush_rpd()
    assert store.rows[key]["day_count"] == 4

    # ---- restart: a brand-new controller object, same durable row ----
    lim2 = _lane("map_groq3"); _wire(lim2, store, key)
    assert lim2.state()["day_count"] == 4, "restart did not restore the day count"

    _dispatch(lim2, 2)
    lim2.flush_rpd()
    assert store.rows[key]["day_count"] == 6, "the next dispatch did not continue from durable truth"


def test_the_durable_row_carries_the_reconciliation_fields() -> None:
    """day/window · dispatch count · rate-limit state · last update. Lane = the row key;
    account and function come from the LANE REGISTRY join, never duplicated here."""
    store, key = MemStore(), "llm_cloud[map_groq4]"
    lim = _lane("map_groq4"); _wire(lim, store, key)
    lim.RPD_PERSIST_MIN_INTERVAL_S = 0.0
    _dispatch(lim, 1); lim.flush_rpd()

    row = store.rows[key]
    for field in ("day", "day_count", "last_dispatch_at", "effective", "ceiling",
                  "increases", "decreases"):
        assert field in row, f"durable row is missing {field!r}"
    assert not any("key" in str(k).lower() and "api" in str(k).lower() for k in row), "no secret may be stored"


def test_a_refused_call_moves_no_counter() -> None:
    """A local refusal consumes no provider request, so it must not bump the RPD count."""
    store, key = MemStore(), "llm_cloud[map_groq5]"
    lim = _lane("map_groq5", rpd=1); _wire(lim, store, key)
    lim.RPD_PERSIST_MIN_INTERVAL_S = 0.0

    _dispatch(lim, 1); lim.flush_rpd()
    assert store.rows[key]["day_count"] == 1

    refused = lim.admit(est_tokens=10, block=False)     # rpd=1 is now spent
    assert not refused.admitted and refused.reason == L.REFUSE_RPD
    lim.flush_rpd()
    assert store.rows[key]["day_count"] == 1, "a refusal must not increment the RPD counter"


def test_yesterdays_row_does_not_carry_into_today() -> None:
    """A stale day bucket must not eat today's budget."""
    store, key = MemStore(), "llm_cloud[map_groq6]"
    store.rows[key] = {"effective": 1, "day": "2000-01-01", "day_count": 999,
                       "increases": 0, "decreases": 0, "last_dispatch_at": "2000-01-01T00:00:00Z"}
    lim = _lane("map_groq6"); _wire(lim, store, key)
    assert lim.state()["day_count"] == 0, "a previous day's count must not be restored"
