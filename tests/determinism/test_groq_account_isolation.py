"""GROQ-MAP-CONTROL-PLANE-REPAIR-V1 — per-account Groq circuit isolation.

Routing policy of record (GROQ-ROUTING-POLICY-V1): six Groq accounts are six
capacity domains; each account's two models (compound + compound-mini) share ONE
account circuit. The shipped config had all 12 lanes on a single `family: groq`,
so one account's 429 storm opened a family cooldown that refused ALL six map
lanes — the dominant source of the disputed cinema refusal cascade. Families are
now per-account (`groq_acct_N`); this pins that.
"""
from __future__ import annotations

import polymath_shared.llm_extraction.limiter as lim
from polymath_shared.llm_extraction.limiter import (
    FAMILY_FAILURE_THRESHOLD,
    AdaptiveLimiter,
    ProviderLimit,
    _FamilyGate,
)
from polymath_shared.llm_extraction.client import _lane_limit


def _lane(**over):
    spec = dict(kind="rate", init=2, min=1, max=6, rpm=30, tpm=10000,
                conc_cap=4, adaptive=True, use_headers=True)
    spec.update(over)
    return AdaptiveLimiter("acct", ProviderLimit(**spec))


def test_config_assigns_per_account_families():
    for n in (1, 2, 3, 4, 5, 6):
        prof = _lane_limit("cloud", f"profile_groq{n}")
        mp = _lane_limit("cloud", f"map_groq{n}")
        assert prof.family == f"groq_acct_{n}"      # compound
        assert mp.family == f"groq_acct_{n}"        # compound-mini, same account
    # no groq lane remains on the shared single circuit
    assert _lane_limit("cloud", "map_groq1").family != "groq"
    assert _lane_limit("cloud", "map_groq1").family != _lane_limit("cloud", "map_groq2").family


def test_account_circuit_isolates_across_accounts():
    gate = _FamilyGate()
    lim.FAMILY_GATE = gate
    try:
        acct1_map = _lane(family="groq_acct_1")
        acct1_profile = _lane(family="groq_acct_1")
        acct2_map = _lane(family="groq_acct_2")
        for _ in range(FAMILY_FAILURE_THRESHOLD):
            acct1_map.record_failure()              # account 1's 429 storm
        # sibling model on the SAME account is damped (intended account-level circuit)
        assert not acct1_profile.acquire(block=False)
        # a DIFFERENT account is untouched — the six accounts are isolated
        assert acct2_map.acquire(block=False)
        acct2_map.release()
    finally:
        lim.FAMILY_GATE = _FamilyGate()
