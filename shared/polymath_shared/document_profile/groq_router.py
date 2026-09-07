"""Groq account/model routing — the deterministic decision core.

Policy of record: docs/wiki/plans/GROQ-ROUTING-POLICY-V1.md. Plan slice S7
(DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md §14 / §35).

Deterministic policy (shared/): no I/O, no model, no clock of its own — `now` and
all account state are INJECTED so the same inputs always yield the same decision.
This is the SELECTION layer (which account + model to try, or wait); the existing
`llm_extraction.limiter` remains the per-lane ENFORCEMENT layer. This module adds
no second scheduler authority — it decides, the limiter enforces.

The correction this encodes: an account's RPD / rolling-RPM / TPM budget is SHARED
by its two models (`groq/compound` and `groq/compound-mini`). State is therefore
keyed on the ACCOUNT; only latency is per (account, model). A request for either
model draws down the one account budget, and a 429 / Retry-After locks the whole
account — never just one model's lane (no key burning).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from polymath_shared.document_profile.map_batches import TPM_CEILING, token_feasible_rpm

#: Work class -> the model policy chooses (GROQ-ROUTING-POLICY-V1 §2).
WORK_CLASS_MODEL = {
    "GLOBAL_DOCUMENT_PROFILE": "groq/compound",
    "PARENT_ROUTING_MAP": "groq/compound-mini",
    "COMBINED_ONE_CALL": "groq/compound",
}

#: Default safe per-account RPM ceiling (a TARGET, not the provider's 30; §14.3).
DEFAULT_RPM_CEILING = 4
#: A small backoff when every account is capacity-limited but none is time-locked.
DEFAULT_BACKOFF_SECONDS = 5.0


@dataclass(frozen=True)
class AccountState:
    """A Groq account = one capacity domain. RPD / rolling-RPM / TPM are SHARED by
    both models; `latency_ewma` is per model."""

    account: str
    remaining_rpd: int
    rolling_rpm: int
    tpm_used: int
    in_flight: int = 0
    locked_until: float = 0.0          # epoch seconds; > now => Retry-After lock
    breaker_open: bool = False
    latency_ewma: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteDecision:
    account: str | None
    model: str | None
    reason: str                        # "selected" | "all_locked" | "no_capacity" | "empty_pool"
    wait_seconds: float = 0.0

    @property
    def routed(self) -> bool:
        return self.account is not None


def _feasible(
    acct: AccountState,
    *,
    now: float,
    est_total_tokens: float,
    rpm_ceiling: int,
    tpm_ceiling: int,
) -> bool:
    if acct.breaker_open:
        return False
    if acct.locked_until > now:
        return False
    if acct.remaining_rpd <= 0:
        return False
    # The 4-RPM target is honored only under the §14.4 token guard: a heavy request
    # lowers the feasible RPM for THIS account.
    effective_rpm = token_feasible_rpm(est_total_tokens, target_rpm=rpm_ceiling, tpm_ceiling=tpm_ceiling)
    if acct.rolling_rpm >= effective_rpm:
        return False
    # TPM headroom: would this request's estimated tokens fit the 60 s window?
    if acct.tpm_used + est_total_tokens > tpm_ceiling:
        return False
    return True


def choose(
    work_class: str,
    accounts: list[AccountState],
    *,
    now: float,
    est_total_tokens: float,
    rpm_ceiling: int = DEFAULT_RPM_CEILING,
    tpm_ceiling: int = TPM_CEILING,
) -> RouteDecision:
    """Pick (account, model) for a work class by remaining capacity — never a fixed
    round-robin — or return a wait. Deterministic given (accounts, now, tokens).

    Tie-break for "most capacity": maximize remaining RPD, then TPM headroom, then
    the fewest in-flight and lowest rolling RPM; ties broken by account name so the
    choice is stable and replay-safe.
    """
    if work_class not in WORK_CLASS_MODEL:
        raise ValueError(f"unknown Groq work class: {work_class!r}")
    model = WORK_CLASS_MODEL[work_class]
    if not accounts:
        return RouteDecision(None, None, "empty_pool")

    feasible = [
        a for a in accounts
        if _feasible(a, now=now, est_total_tokens=est_total_tokens,
                     rpm_ceiling=rpm_ceiling, tpm_ceiling=tpm_ceiling)
    ]
    if feasible:
        best = max(
            feasible,
            key=lambda a: (
                a.remaining_rpd,
                tpm_ceiling - (a.tpm_used + est_total_tokens),
                -a.in_flight,
                -a.rolling_rpm,
                # negate the name via reversed comparison: use min-name as the final
                # deterministic tie-break by selecting the lexicographically smallest.
            ),
        )
        # Deterministic final tie-break: among accounts tied on the capacity key,
        # pick the lexicographically smallest name.
        best_key = (best.remaining_rpd, tpm_ceiling - (best.tpm_used + est_total_tokens),
                    -best.in_flight, -best.rolling_rpm)
        tied = [
            a for a in feasible
            if (a.remaining_rpd, tpm_ceiling - (a.tpm_used + est_total_tokens),
                -a.in_flight, -a.rolling_rpm) == best_key
        ]
        chosen = min(tied, key=lambda a: a.account)
        return RouteDecision(chosen.account, model, "selected")

    # Nothing feasible now. If any account is time-locked, wait until the soonest
    # unlock; otherwise everything is capacity-limited (RPD/TPM/RPM) -> short backoff.
    locks = [a.locked_until - now for a in accounts if a.locked_until > now and not a.breaker_open]
    if locks:
        return RouteDecision(None, model, "all_locked", wait_seconds=max(0.0, min(locks)))
    # Distinguish "day exhausted" from transient capacity pressure for the caller.
    if all(a.remaining_rpd <= 0 for a in accounts):
        return RouteDecision(None, model, "rpd_exhausted", wait_seconds=DEFAULT_BACKOFF_SECONDS)
    return RouteDecision(None, model, "no_capacity", wait_seconds=DEFAULT_BACKOFF_SECONDS)
