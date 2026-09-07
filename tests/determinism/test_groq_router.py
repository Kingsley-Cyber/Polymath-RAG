"""GROQ-ROUTING-POLICY-V1 (plan slice S7) — the deterministic account/model
routing decision core. Pure pins: account-level budget coordination, capacity-
aware selection (never round-robin), retry-after locks, breaker skips, the §14.4
token guard, and stable tie-breaks. No I/O, no clock — `now` is injected.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import groq_router as GR  # noqa: E402

NOW = 1_000_000.0
PROFILE_TOKENS = 13362.0  # ~60-parent request at the measured baseline


def _acct(name, *, rpd=200, rpm=0, tpm=0, in_flight=0, locked=0.0, breaker=False):
    return GR.AccountState(
        account=name, remaining_rpd=rpd, rolling_rpm=rpm, tpm_used=tpm,
        in_flight=in_flight, locked_until=locked, breaker_open=breaker,
    )


def test_work_class_selects_the_policy_model():
    accts = [_acct("groq_acct_1")]
    assert GR.choose("GLOBAL_DOCUMENT_PROFILE", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).model == "groq/compound"
    assert GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).model == "groq/compound-mini"
    assert GR.choose("COMBINED_ONE_CALL", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).model == "groq/compound"


def test_unknown_work_class_raises():
    import pytest
    with pytest.raises(ValueError):
        GR.choose("NONSENSE", [_acct("a")], now=NOW, est_total_tokens=1)


def test_picks_account_with_most_capacity_not_round_robin():
    accts = [_acct("groq_acct_1", rpd=100), _acct("groq_acct_2", rpd=250), _acct("groq_acct_3", rpd=180)]
    d = GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert d.routed and d.account == "groq_acct_2"   # most remaining RPD, not a hash ring


def test_deterministic_tie_break_by_account_name():
    accts = [_acct("groq_acct_3"), _acct("groq_acct_1"), _acct("groq_acct_2")]  # all identical capacity
    d = GR.choose("GLOBAL_DOCUMENT_PROFILE", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert d.account == "groq_acct_1"                # lexicographically smallest, stable
    # Same inputs => same decision.
    assert GR.choose("GLOBAL_DOCUMENT_PROFILE", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).account == "groq_acct_1"


def test_account_budget_is_shared_by_both_models():
    # An account whose day is exhausted cannot serve EITHER model — state is keyed
    # on the account, so compound-mini gets no independent quota.
    accts = [_acct("groq_acct_1", rpd=0)]
    d = GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert not d.routed and d.reason == "rpd_exhausted"


def test_retry_after_lock_skips_account_and_reports_wait():
    accts = [_acct("groq_acct_1", locked=NOW + 12.0)]
    d = GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert not d.routed and d.reason == "all_locked"
    assert abs(d.wait_seconds - 12.0) < 1e-6
    # A second, unlocked account is chosen instead (no key burning on the locked one).
    accts.append(_acct("groq_acct_2"))
    assert GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).account == "groq_acct_2"


def test_all_locked_waits_for_soonest_unlock():
    accts = [_acct("a", locked=NOW + 30.0), _acct("b", locked=NOW + 8.0), _acct("c", locked=NOW + 15.0)]
    d = GR.choose("GLOBAL_DOCUMENT_PROFILE", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert d.reason == "all_locked" and abs(d.wait_seconds - 8.0) < 1e-6


def test_breaker_open_account_is_skipped():
    accts = [_acct("groq_acct_1", breaker=True), _acct("groq_acct_2")]
    assert GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS).account == "groq_acct_2"


def test_tpm_headroom_respected():
    # tpm_used leaves no room for this request's estimated tokens.
    tight = _acct("groq_acct_1", tpm=int(GR.TPM_CEILING - 1000))
    roomy = _acct("groq_acct_2", tpm=0)
    d = GR.choose("GLOBAL_DOCUMENT_PROFILE", [tight, roomy], now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert d.account == "groq_acct_2"


def test_rpm_ceiling_and_token_guard():
    # A light request keeps the 4-RPM ceiling: rolling 3 is still feasible.
    light_ok = _acct("groq_acct_1", rpm=3)
    assert GR.choose("PARENT_ROUTING_MAP", [light_ok], now=NOW, est_total_tokens=PROFILE_TOKENS).routed
    # rolling 4 is at the ceiling -> not feasible.
    at_ceiling = _acct("groq_acct_1", rpm=4)
    assert not GR.choose("PARENT_ROUTING_MAP", [at_ceiling], now=NOW, est_total_tokens=PROFILE_TOKENS).routed
    # A heavy request (>15k tokens) drops the guard to 3, so rolling 3 is now blocked.
    heavy_blocked = _acct("groq_acct_1", rpm=3)
    d = GR.choose("GLOBAL_DOCUMENT_PROFILE", [heavy_blocked], now=NOW, est_total_tokens=20000.0)
    assert not d.routed and d.reason == "no_capacity"


def test_empty_pool():
    d = GR.choose("PARENT_ROUTING_MAP", [], now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert not d.routed and d.reason == "empty_pool"


def test_no_capacity_vs_rpd_exhausted():
    # Capacity pressure but day not exhausted -> no_capacity (short backoff).
    accts = [_acct("groq_acct_1", rpm=4), _acct("groq_acct_2", rpm=4)]
    d = GR.choose("PARENT_ROUTING_MAP", accts, now=NOW, est_total_tokens=PROFILE_TOKENS)
    assert d.reason == "no_capacity" and d.wait_seconds == GR.DEFAULT_BACKOFF_SECONDS


def test_module_is_pure():
    source = (ROOT / "shared" / "polymath_shared" / "document_profile" / "groq_router.py").read_text()
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {"__future__", "dataclasses", "polymath_shared"}
    assert roots <= allowed, f"unexpected imports in a pure decision core: {roots - allowed}"
