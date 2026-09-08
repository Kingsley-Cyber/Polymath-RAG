"""Live Groq lane routing — wires `groq_router.choose` over the live limiter registry.

Slice S7b / GROQ-ROUTING-POLICY-V1. Given a stage pin of Groq lanes (compound +
compound-mini across the six accounts), pick the (account, model) with the most shared
remaining budget and map it back to the lane to call. It reuses the three existing
layers and adds NO scheduler:

  * `groq_accounts.account_states` — the shared-budget accounting (S7a);
  * `groq_router.choose` — the pure decision (11.134);
  * the limiter registry — live capacity (`capacity_snapshot`) + the ENFORCEMENT.

Reversible: `POLYMATH_GROQ_ROUTER` off (default) → callers keep their existing rotation;
on → capacity-aware selection for these Groq lanes only. Scoped to the Groq
compound/compound-mini profile/MAP lanes; unrelated extraction providers are untouched.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from collections.abc import Iterable, Mapping

from polymath_shared.document_profile import groq_router as GR
from polymath_shared.document_profile.groq_accounts import account_states

_ROOT = Path(__file__).resolve().parents[3]
_PROVIDERS_FILE = _ROOT / "config" / "cloud_providers.json"
#: Fallback per-account daily budget when limiter config is not consulted (the six Groq
#: accounts' measured quota; the limiter row's rpd is authoritative when available).
DEFAULT_ACCOUNT_RPD = 230
#: The limiter registry keys a cloud lane as (f"llm_{client_lane}", limiter_key); the
#: doc_profile/parent-map clients use client lane "cloud", so their registry provider is
#: "llm_cloud" (NOT "cloud" — the 8-doc backfill's single-account pinning traced here).
DEFAULT_PROVIDER = "llm_cloud"


def router_enabled() -> bool:
    return os.environ.get("POLYMATH_GROQ_ROUTER", "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------------------------
# Concurrent-spread reservation (CONCURRENCY-SPREAD-V1, 2026-09-08).
# `choose` ranks accounts by capacity from a POINT-IN-TIME snapshot. Sequential callers spread
# fine — each sees the prior call's limiter draw — but N callers firing at once (a threaded
# backfill) read near-identical snapshots and all pick the SAME best account (measured: a
# 3-way parent-map backfill put 633/640 calls on map_groq1). The limiter's in_flight only
# reflects a call once it STARTS, i.e. just after route() returns, so it cannot separate a
# simultaneous burst. This short-TTL in-process reservation bridges exactly that gap: each pick
# is recorded per account for RESERVATION_TTL_S, and pending picks are injected as extra
# `in_flight` into the snapshot `choose` sees — so the existing `-in_flight` tie-break rotates
# the burst across accounts. The reservation is advisory (never blocks) and decays on its own,
# so sequential callers (map calls ~8 s apart, past the TTL) are unaffected; the limiter stays
# the enforcement authority. Process-local by design (it coordinates THIS process's threads).
RESERVATION_TTL_S = 6.0
_PENDING: dict[str, list[float]] = {}
_PENDING_LOCK = threading.Lock()


def reset_reservations() -> None:
    """Clear the in-process reservation state (tests + a fresh campaign)."""
    with _PENDING_LOCK:
        _PENDING.clear()


def _pending_counts_locked(now: float) -> dict[str, int]:
    """Decay expired reservations and return the live pending count per account. Caller holds the lock."""
    live: dict[str, int] = {}
    for acct, stamps in list(_PENDING.items()):
        fresh = [t for t in stamps if now - t < RESERVATION_TTL_S]
        if fresh:
            _PENDING[acct] = fresh
            live[acct] = len(fresh)
        else:
            _PENDING.pop(acct, None)
    return live


def _providers() -> list[dict]:
    try:
        return json.loads(_PROVIDERS_FILE.read_text()).get("providers", [])
    except Exception:  # noqa: BLE001
        return []


def account_maps(pin: Iterable[str], providers: list[dict] | None = None) -> tuple[dict, dict]:
    """(lane → account id, lane → model) for the pin lanes that carry an api_key_env."""
    provs = {e["name"]: e for e in (providers if providers is not None else _providers())}
    account_of, model_of = {}, {}
    for lane in pin:
        e = provs.get(lane)
        if e and e.get("api_key_env"):
            account_of[lane] = e["api_key_env"]
            model_of[lane] = e.get("model", "")
    return account_of, model_of


def select_lane(pin: Iterable[str], decision: GR.RouteDecision,
                account_of: Mapping[str, str], model_of: Mapping[str, str]) -> str | None:
    """Pure: map a RouteDecision (account, model) back to the pin lane serving it."""
    if not decision.routed:
        return None
    for lane in pin:
        if account_of.get(lane) == decision.account and model_of.get(lane) == decision.model:
            return lane
    return None


def route(pin: list[str], work_class: str, *, est_total_tokens: float,
          registry=None, providers: list[dict] | None = None,
          account_rpd: Mapping[str, int] | None = None, now: float | None = None,
          get_lane=None) -> tuple[str | None, GR.RouteDecision]:
    """Choose the pin lane to call for `work_class` by shared remaining capacity.

    `now` uses the MONOTONIC clock (matching the limiter's `_not_before`). Returns
    (lane_name, decision); lane is None when the router yields a wait/no-capacity.
    """
    now = time.monotonic() if now is None else now
    account_of, model_of = account_maps(pin, providers)
    if not account_of:
        return None, GR.RouteDecision(None, None, "empty_pool")
    if get_lane is None:
        from polymath_shared.llm_extraction.limiter import REGISTRY
        registry = registry or REGISTRY
        get_lane = lambda name: registry.get_lane(DEFAULT_PROVIDER, name)  # noqa: E731
    rpd = dict(account_rpd) if account_rpd else {a: DEFAULT_ACCOUNT_RPD for a in set(account_of.values())}
    # EVERY pin lane gets a snapshot — a live one when its limiter lane exists, else a
    # fresh full-budget placeholder. Considering only the registered lanes would leave
    # every unused account invisible and pin the router to the first-used lane (the bug
    # the 8-doc backfill exposed: 43/43 calls landed on map_groq1).
    snaps: dict[str, dict] = {}
    for lane, acct in account_of.items():
        lim = get_lane(lane)
        if lim is not None and hasattr(lim, "capacity_snapshot"):
            snaps[lane] = lim.capacity_snapshot(now=now)
        else:
            snaps[lane] = {"day_count": 0, "remaining_rpd": rpd.get(acct, DEFAULT_ACCOUNT_RPD),
                           "rolling_rpm": 0, "tpm_used": 0, "in_flight": 0,
                           "locked_until": 0.0, "breaker_open": False}
    # CONCURRENCY-SPREAD-V1: inject this process's recent (pending) picks as extra in_flight so a
    # simultaneous burst rotates across accounts via choose's `-in_flight` tie-break, then reserve
    # the chosen account. Held under one lock so concurrent callers see each other's picks.
    with _PENDING_LOCK:
        pending = _pending_counts_locked(now)
        for lane, acct in account_of.items():
            n = pending.get(acct, 0)
            if n:
                s = snaps[lane]
                s["in_flight"] = int(s.get("in_flight", 0)) + n
        states = account_states(snaps, account_of, rpd)
        decision = GR.choose(work_class, states, now=now, est_total_tokens=est_total_tokens)
        if decision.routed and decision.account:
            _PENDING.setdefault(decision.account, []).append(now)
    return select_lane(pin, decision, account_of, model_of), decision
