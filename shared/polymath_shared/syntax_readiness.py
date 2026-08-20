"""S3 — V2 SYNTAX READINESS CONTRACT.

`syntax-evidence-v1` is a HARD runtime prerequisite for every
`admission-harbor-v2` interpretation. IDENTITY-PRECISION-V2 separates
`Postgres/PROPN` from `Researchers/NOUN` using POS; without POS the only
remaining signal is capitalization, which is the exact production defect
this whole dependency exists to remove.

Three layers, because they protect against different failures:

    A RUN PREFLIGHT       static compatibility  — impossible configuration
    B CLAIM ELIGIBILITY   dynamic readiness     — don't claim then discover
    C EXECUTION ASSERTION race protection       — TOCTOU after claim

A health check cannot eliminate TOCTOU, so C is required even with B.

TWO DISTINCT FAILURES, never conflated:

    INCOMPATIBLE_RUN_CONFIGURATION   V2 requested, syntax disabled.
                                     No retry fixes it. Fail before scheduling.
    RETRYABLE_DEPENDENCY_UNAVAILABLE V2 correct, sidecar down.
                                     Pending until capability returns.

THE INVARIANT:

    A failed required dependency may INTERRUPT a run.
    It may NEVER alter its semantics.

So the same sentence must never yield `Researchers -> GENERIC` with a
healthy sidecar and `Researchers -> GLOBAL` without one. The degraded path
is unreachable under V2 rather than merely discouraged.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

SYNTAX_READINESS_CONTRACT = "syntax-readiness-v1"
CAPABILITY_STALE_AFTER_S = 60.0


class IncompatibleRunConfiguration(Exception):
    """Configuration error. Retrying cannot fix it; do not enqueue work."""

    code = "INCOMPATIBLE_RUN_CONFIGURATION"


class RetryableDependencyUnavailable(Exception):
    """Runtime dependency failure. Ticket stays pending until healthy."""

    code = "RETRYABLE_DEPENDENCY_UNAVAILABLE"


@dataclass(frozen=True)
class SyntaxCapability:
    available: bool
    contract: str | None = None
    model: str | None = None
    checked_at: float = 0.0
    detail: str = ""

    def fresh(self, now: float | None = None) -> bool:
        return (time.time() if now is None else now) - self.checked_at <= CAPABILITY_STALE_AFTER_S


def requires_syntax(execution_contract: dict) -> bool:
    """Only admission-harbor-v2 interpretations carry the hard dependency."""
    from polymath_shared.execution import SEMANTIC_CONTRACT_V2

    return execution_contract.get("semantic_contract") == SEMANTIC_CONTRACT_V2


# --- A. RUN PREFLIGHT ------------------------------------------------------

def check_run_configuration(execution_contract: dict) -> None:
    """Reject an impossible V2 configuration BEFORE any work is enqueued.

    Raises IncompatibleRunConfiguration. Never returns a degraded mode.
    """
    if not requires_syntax(execution_contract):
        return
    provider = execution_contract.get("syntax_provider")
    if provider != "spacy":
        raise IncompatibleRunConfiguration(
            f"admission-harbor-v2 requires syntax_provider='spacy'; run pins "
            f"{provider!r}. IDENTITY-PRECISION-V2 cannot decide without POS, "
            f"and falling back to capitalization is forbidden.")
    if execution_contract.get("syntax_contract") != "syntax-evidence-v1":
        raise IncompatibleRunConfiguration(
            f"admission-harbor-v2 requires syntax-evidence-v1; run pins "
            f"{execution_contract.get('syntax_contract')!r}")
    if not execution_contract.get("syntax_model"):
        raise IncompatibleRunConfiguration(
            "admission-harbor-v2 requires a pinned syntax_model; reprocessing "
            "parsed under an unpinned model is not reproducible")


def probe_syntax(timeout: float = 3.0) -> SyntaxCapability:
    """Current sidecar capability. Never raises."""
    try:
        import httpx

        from polymath_shared.settings import get_settings
        r = httpx.get(f"{get_settings().sidecars.spacy_url}/manifest", timeout=timeout)
        r.raise_for_status()
        j = r.json()
        m = j.get("identity", {}).get("model", {})
        return SyntaxCapability(
            True, j.get("identity", {}).get("release"),
            f"{m.get('id')}@{m.get('revision')}" if m else None,
            time.time(), "manifest ok")
    except Exception as exc:                       # noqa: BLE001 — health probe
        return SyntaxCapability(False, None, None, time.time(),
                                f"{type(exc).__name__}: {exc}"[:120])


# --- B. CLAIM ELIGIBILITY --------------------------------------------------

def claim_eligible(execution_contract: dict,
                   capability: SyntaxCapability | None,
                   now: float | None = None) -> tuple[bool, str]:
    """May this worker CLAIM this ticket right now?

    A V2 ticket is claimable only by a worker whose CURRENT, FRESH
    capability satisfies the dependency. Otherwise the ticket stays pending
    — better than claiming and repeatedly releasing.
    """
    if not requires_syntax(execution_contract):
        return True, "no syntax dependency"
    if capability is None:
        return False, "no syntax capability registered"
    if not capability.available:
        return False, f"syntax sidecar unavailable ({capability.detail})"
    if not capability.fresh(now):
        return False, "syntax capability registration is stale"
    want_model = execution_contract.get("syntax_model")
    if want_model and capability.model != want_model:
        return False, (f"syntax model mismatch: run pins {want_model!r}, "
                       f"worker has {capability.model!r}")
    want_contract = execution_contract.get("syntax_contract")
    if want_contract and capability.contract != want_contract:
        return False, (f"syntax contract mismatch: run pins {want_contract!r}, "
                       f"worker has {capability.contract!r}")
    return True, "syntax capability satisfies the run contract"


# --- C. EXECUTION ASSERTION ------------------------------------------------

def assert_syntax_available(execution_contract: dict, syntax: object | None,
                            *, where: str = "V2 semantic interpretation") -> None:
    """Immediately before any V2 semantic write.

    A sidecar can die between claim and use; B cannot prevent that. On
    failure NOTHING is written — no admission result, no entity, no fact,
    no semantic receipt — and the ticket becomes retryable.
    """
    if not requires_syntax(execution_contract):
        return
    if not syntax:
        raise RetryableDependencyUnavailable(
            f"{where} requires syntax-evidence-v1 and none is present. "
            f"No admission, entity or fact may be written; the ticket is "
            f"retryable. Degrading to syntaxless identity is forbidden — it "
            f"would make graph semantics depend on sidecar health.")
