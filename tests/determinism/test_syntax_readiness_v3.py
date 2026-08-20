"""S3 — V2 syntax readiness contract.

Three layers, because they protect against different failures:
  A run preflight (impossible configuration)
  B claim eligibility (don't claim then discover)
  C execution assertion (TOCTOU — a health check cannot eliminate the race)

THE INVARIANT: a failed required dependency may INTERRUPT a run; it may
NEVER alter its semantics.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.execution import SEMANTIC_CONTRACT_V1_1, SEMANTIC_CONTRACT_V2, compatible
from polymath_shared.identity_evidence import identity_evidence
from polymath_shared.syntax_readiness import (
    IncompatibleRunConfiguration, RetryableDependencyUnavailable, SyntaxCapability,
    assert_syntax_available, check_run_configuration, claim_eligible, requires_syntax,
)

V2 = {"semantic_contract": SEMANTIC_CONTRACT_V2, "syntax_provider": "spacy",
      "syntax_contract": "syntax-evidence-v1", "syntax_model": "en_core_web_sm@3.8.0"}
HEALTHY = SyntaxCapability(True, "syntax-evidence-v1", "en_core_web_sm@3.8.0", time.time())


def _tok(text, pos):
    return [{"i": 0, "text": text, "pos": pos, "lemma": text.lower(),
             "char_start": 0, "char_end": len(text)}]


# --- A. preflight ----------------------------------------------------------

def test_v2_with_syntax_disabled_is_rejected_before_scheduling():
    with pytest.raises(IncompatibleRunConfiguration):
        check_run_configuration({**V2, "syntax_provider": "disabled"})


def test_v2_with_wrong_syntax_contract_is_rejected():
    with pytest.raises(IncompatibleRunConfiguration):
        check_run_configuration({**V2, "syntax_contract": "syntax-evidence-v0"})


def test_v2_without_a_pinned_model_is_rejected():
    """Reprocessing parsed under an unpinned model is not reproducible."""
    with pytest.raises(IncompatibleRunConfiguration):
        check_run_configuration({**V2, "syntax_model": None})


def test_valid_v2_configuration_is_admissible():
    check_run_configuration(V2)          # must not raise


def test_historical_v1_1_runs_carry_no_syntax_dependency():
    assert not requires_syntax({"semantic_contract": SEMANTIC_CONTRACT_V1_1})
    check_run_configuration({"semantic_contract": SEMANTIC_CONTRACT_V1_1,
                             "syntax_provider": "disabled"})


# --- B. claim eligibility --------------------------------------------------

def test_healthy_capability_makes_a_v2_ticket_claimable():
    ok, _ = claim_eligible(V2, HEALTHY)
    assert ok


def test_unhealthy_capability_leaves_the_ticket_pending():
    ok, why = claim_eligible(V2, SyntaxCapability(False, None, None, time.time(), "down"))
    assert not ok and "unavailable" in why


def test_stale_capability_leaves_the_ticket_pending():
    old = SyntaxCapability(True, "syntax-evidence-v1", "en_core_web_sm@3.8.0", 0.0)
    ok, why = claim_eligible(V2, old)
    assert not ok and "stale" in why


def test_model_mismatch_leaves_the_ticket_pending():
    other = SyntaxCapability(True, "syntax-evidence-v1", "en_core_web_lg@9.9.9", time.time())
    ok, why = claim_eligible(V2, other)
    assert not ok and "model mismatch" in why


def test_missing_capability_registration_is_not_claimable():
    ok, _ = claim_eligible(V2, None)
    assert not ok


def test_claim_gate_is_wired_into_compatible():
    wc = {"query_policy": None, "rule_pack": None, "chunker": None,
          "syntax_provider": "spacy", "rescue_stages": []}
    import polymath_shared.execution as ex
    real = ex.syntax_capability
    try:
        ex.syntax_capability = lambda *a, **k: SyntaxCapability(
            False, None, None, time.time(), "sidecar down")
        assert compatible(wc, {**V2, "rescue_stages": []}) is False
        ex.syntax_capability = lambda *a, **k: HEALTHY
        assert compatible(wc, {**V2, "rescue_stages": []}) is True
        # a contract with no semantic_contract is unaffected either way
        ex.syntax_capability = lambda *a, **k: SyntaxCapability(
            False, None, None, time.time(), "down")
        assert compatible(wc, {"rescue_stages": []}) is True
    finally:
        ex.syntax_capability = real


# --- C. execution assertion (TOCTOU) ---------------------------------------

def test_syntax_dying_after_claim_is_retryable_not_semantic():
    with pytest.raises(RetryableDependencyUnavailable):
        assert_syntax_available(V2, None)


def test_execution_assertion_is_a_noop_without_the_dependency():
    assert_syntax_available({"semantic_contract": SEMANTIC_CONTRACT_V1_1}, None)


def test_the_two_failure_classes_are_distinct():
    """Configuration errors never retry; runtime failures always do."""
    assert IncompatibleRunConfiguration.code == "INCOMPATIBLE_RUN_CONFIGURATION"
    assert RetryableDependencyUnavailable.code == "RETRYABLE_DEPENDENCY_UNAVAILABLE"
    assert not issubclass(IncompatibleRunConfiguration, RetryableDependencyUnavailable)
    assert not issubclass(RetryableDependencyUnavailable, IncompatibleRunConfiguration)


# --- D. the degraded path is unreachable under V2 --------------------------

def test_the_pinned_production_defect_cannot_recur():
    """`Researchers` must be GENERIC with syntax and NO DECISION without it.
    It must NEVER be GLOBAL — that outcome is what made this dependency
    load-bearing in the first place."""
    healthy = identity_evidence("Researchers", tokens=_tok("Researchers", "NOUN"),
                                require_syntax=True)
    assert not healthy.is_identity

    with pytest.raises(RetryableDependencyUnavailable):
        identity_evidence("Researchers", tokens=None, require_syntax=True)


def test_v2_never_reaches_the_capitalization_fallback():
    for surface in ("Researchers", "That", "Workers", "Two documents"):
        with pytest.raises(RetryableDependencyUnavailable):
            identity_evidence(surface, tokens=None, require_syntax=True)


def test_degraded_path_survives_only_for_surface_only_history():
    """The frozen 55-item gold has no syntax; it must still evaluate."""
    d = identity_evidence("Postgres", tokens=None)     # no require_syntax
    assert d.is_identity and "degraded" in d.reasons[0]
