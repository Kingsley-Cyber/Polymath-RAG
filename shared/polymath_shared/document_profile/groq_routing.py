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
DEFAULT_PROVIDER = "cloud"


def router_enabled() -> bool:
    return os.environ.get("POLYMATH_GROQ_ROUTER", "").strip().lower() in ("1", "true", "yes", "on")


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
    states = account_states(snaps, account_of, rpd)
    decision = GR.choose(work_class, states, now=now, est_total_tokens=est_total_tokens)
    return select_lane(pin, decision, account_of, model_of), decision
