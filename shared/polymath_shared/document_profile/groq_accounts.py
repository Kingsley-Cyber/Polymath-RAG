"""Groq per-account shared-budget accounting — assembles `groq_router.AccountState`.

GROQ-ROUTING-POLICY-V1 §2 / slice S7. A Groq ACCOUNT (one `GROQ_API_KEY`) is the
capacity domain: its RPD / rolling-RPM / TPM budget is SHARED by both models
(`groq/compound` and `groq/compound-mini`), which run as SEPARATE limiter lanes. The
per-lane `AdaptiveLimiter` tracks each lane independently; this module AGGREGATES the
lanes of one account so the router sees the ONE shared budget (the correction the
policy encodes — a request for either model draws down the same account).

Pure aggregation over per-lane `capacity_snapshot()` dicts + a lane→account map; the
live wrapper reads snapshots from the limiter registry. This is the SELECTION layer's
input; the limiter stays the ENFORCEMENT authority (no second scheduler).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from polymath_shared.document_profile.groq_router import AccountState


def account_states(
    lane_snapshots: Mapping[str, dict],   # lane_name -> AdaptiveLimiter.capacity_snapshot()
    account_of: Mapping[str, str],        # lane_name -> account id (e.g. GROQ_API_KEY_1)
    account_rpd: Mapping[str, int],       # account id -> shared daily budget (one key's quota)
) -> list[AccountState]:
    """One AccountState per account, aggregating its lanes' usage against the shared
    daily budget. RPD is the account budget minus the SUM of its lanes' day usage;
    RPM/TPM/in-flight sum; the account is locked/broken if ANY of its lanes is."""
    by_account: dict[str, list[dict]] = defaultdict(list)
    for lane, snap in lane_snapshots.items():
        acct = account_of.get(lane)
        if acct is not None:
            by_account[acct].append(snap)
    out: list[AccountState] = []
    for acct, snaps in by_account.items():
        used_rpd = sum(int(s.get("day_count", 0)) for s in snaps)
        budget = account_rpd.get(acct)
        if budget:
            remaining_rpd = budget - used_rpd
        else:
            remaining_rpd = min((int(s.get("remaining_rpd", 0)) for s in snaps), default=0)
        out.append(AccountState(
            account=acct,
            remaining_rpd=max(0, remaining_rpd),
            rolling_rpm=sum(int(s.get("rolling_rpm", 0)) for s in snaps),
            tpm_used=sum(int(s.get("tpm_used", 0)) for s in snaps),
            in_flight=sum(int(s.get("in_flight", 0)) for s in snaps),
            locked_until=max((float(s.get("locked_until", 0.0)) for s in snaps), default=0.0),
            breaker_open=any(bool(s.get("breaker_open")) for s in snaps),
        ))
    out.sort(key=lambda a: a.account)
    return out


def snapshot_from_registry(
    registry,
    lanes: Iterable[str],
    account_of: Mapping[str, str],
    account_rpd: Mapping[str, int],
    *,
    now: float | None = None,
) -> list[AccountState]:
    """Live wrapper: read each lane's `capacity_snapshot()` from the limiter registry
    (a lane absent from the registry is skipped), then aggregate. The registry access
    is duck-typed (`get(name)` -> limiter-or-None, as `LimiterRegistry` provides)."""
    snaps: dict[str, dict] = {}
    for lane in lanes:
        lim = registry.get(lane) if hasattr(registry, "get") else None
        if lim is not None and hasattr(lim, "capacity_snapshot"):
            snaps[lane] = lim.capacity_snapshot(now=now)
    return account_states(snaps, account_of, account_rpd)
