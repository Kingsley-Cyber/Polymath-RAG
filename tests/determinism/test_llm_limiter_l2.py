"""LLM-BACKEND L2 (register 11.466): limiter correctness.

Gaps (docs/wiki/plans/GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md): L-04 admission counted `len(user_prompt)/4` (no system
prompt, no output); L-05 no daily-token budget; L-16 no output-per-minute budget. Pure: no database, no network.
"""
from __future__ import annotations

import time

from polymath_shared.llm_extraction import accounts as A
from polymath_shared.llm_extraction import client as C
from polymath_shared.llm_extraction.limiter import (
    REFUSE_OTPM,
    REFUSE_TPD,
    AdaptiveLimiter,
    ProviderLimit,
    _RollingTokens,
)


def _lim(**kw) -> AdaptiveLimiter:
    spec = {"kind": "rate", "rpm": 100, "tpm": 10_000, "tpd": 5_000, "otpm": 1_000, "min": 4, "max": 4, "init": 4,
            "conc_cap": 4}
    spec.update(kw)
    return AdaptiveLimiter("groq_test", ProviderLimit(**spec))


# ---- admission reserves prompt + output; settle trues it up

def test_admission_reserves_prompt_plus_output_and_settle_refunds_the_unused_part():
    lim = _lim()
    d = lim.admit(est_tokens=3_000, block=False, reserved_output=900)
    assert d.admitted and d.reserved_tokens == 3_000 and d.reserved_output == 900
    assert lim._tpm.tokens <= 10_000 - 3_000 + 1          # refill during the test is at most ~1 token
    assert lim._otpm.tokens <= 1_000 - 900 + 1
    assert abs(lim._tpd.total() - 3_000) < 1e-6
    lim.settle(d, tokens_in=1_200, tokens_out=300)         # the provider's real usage
    lim.release()
    assert abs(lim._tpd.total() - 1_500) < 1e-6            # the daily window records the real total
    assert lim._tpm.tokens >= 10_000 - 1_500 - 1           # 1,500 of the 3,000 reserved came back
    assert lim._otpm.tokens >= 1_000 - 300 - 1


def test_settle_charges_a_call_that_used_more_than_it_reserved():
    lim = _lim()
    d = lim.admit(est_tokens=1_000, block=False, reserved_output=200)
    lim.settle(d, tokens_in=900, tokens_out=600)
    lim.release()
    assert abs(lim._tpd.total() - 1_500) < 1e-6
    assert lim._tpm.tokens <= 10_000 - 1_500 + 1


def test_a_failed_call_releases_its_daily_reservation():
    lim = _lim()
    d = lim.admit(est_tokens=2_000, block=False, reserved_output=500)
    lim.settle(d, failed=True)
    lim.release()
    assert lim._tpd.total() == 0


def test_settle_without_usage_keeps_the_estimate():
    lim = _lim()
    d = lim.admit(est_tokens=2_000, block=False)
    lim.settle(d, tokens_in=0, tokens_out=0)                # a provider that reports no usage
    lim.release()
    assert abs(lim._tpd.total() - 2_000) < 1e-6


# ---- the daily budget refuses, and the per-minute output budget refuses

def test_the_rolling_daily_budget_refuses_once_spent_and_refunds_the_rate_buckets():
    lim = _lim(tpd=5_000)
    first = lim.admit(est_tokens=4_000, block=False)
    lim.settle(first, tokens_in=4_000, tokens_out=0)
    lim.release()
    rpm_before, tpm_before = lim._rpm.tokens, lim._tpm.tokens
    second = lim.admit(est_tokens=2_000, block=False)
    assert not second.admitted and second.reason == REFUSE_TPD
    assert lim._rpm.tokens >= rpm_before - 1e-6 and lim._tpm.tokens >= tpm_before - 1e-6


def test_the_output_per_minute_budget_refuses_a_second_large_request():
    lim = _lim(otpm=1_000)
    a = lim.admit(est_tokens=1_000, block=False, reserved_output=900)
    assert a.admitted
    b = lim.admit(est_tokens=1_000, block=False, reserved_output=900)
    assert not b.admitted and b.reason == REFUSE_OTPM
    assert abs(lim._tpd.total() - 1_000) < 1e-6              # the refused call reserved nothing
    lim.release()


def test_the_window_forgets_usage_older_than_24_hours():
    w = _RollingTokens()
    now = time.time()
    w.add(700, now - 86_400 - 5)
    w.add(300, now - 60)
    assert w.total(now) == 300


# ---- the daily usage survives a restart under the same limits

def test_daily_usage_is_restored_under_the_same_limits_and_dropped_under_other_limits():
    lim = _lim()
    d = lim.admit(est_tokens=1_500, block=False)
    lim.settle(d, tokens_in=1_000, tokens_out=500)
    lim.release()
    state = lim.state()
    assert sum(state["tpd_hours"].values()) == 1_500
    same = _lim()
    same.restore(state)
    assert abs(same._tpd.total() - 1_500) < 1e-6
    other = _lim(tpd=9_000)                                  # a different configuration: the count does not carry
    other.restore(state)
    assert other._tpd.total() == 0


def test_a_lane_without_daily_or_output_budgets_behaves_as_before():
    lim = _lim(tpd=None, otpm=None)
    d = lim.admit(est_tokens=2_000, block=False, reserved_output=900)
    lim.settle(d, tokens_in=100, tokens_out=100)
    lim.release()
    assert d.admitted and d.tpd_slot is None and lim._tpd is None and lim._otpm is None
    assert lim.state()["tpd_hours"] is None


# ---- the client reserves what the provider counts

def test_admission_tokens_count_every_message_conservatively():
    assert C.admission_tokens("a" * 300, "b" * 3_000) == 1_100
    assert C.admission_tokens(None, "") == 0


def test_complete_one_reserves_system_user_and_output_and_settles_with_usage(monkeypatch):
    seen: dict = {}

    class _Recorder:
        def admit(self, est_tokens=0.0, block=True, *, reserved_output=0.0):
            seen["admit"] = (est_tokens, reserved_output)
            from polymath_shared.llm_extraction.limiter import LimiterDecision
            return LimiterDecision(True, reserved_tokens=est_tokens, reserved_output=reserved_output)

        def settle(self, decision, tokens_in=None, tokens_out=None, *, failed=False):
            seen["settle"] = (tokens_in, tokens_out, failed)

        def record_success(self, headers=None):
            pass

        def record_failure(self, retry_after=None, headers=None):
            pass

        def release(self):
            seen["released"] = True

    cli = C.LLMExtractionClient.__new__(C.LLMExtractionClient)
    cli.limiter_key, cli.model, cli.base_url, cli.endpoint_name = "groq_test", "m", "https://x.invalid", "groq_test"
    cli.attempt_stage = cli.attempt_function = None
    monkeypatch.setattr(cli, "_lane_limiter", lambda: _Recorder())
    monkeypatch.setattr(cli, "_chat", lambda u, m, system_prompt=None: ("ok", 120, 40, {}))
    monkeypatch.setattr(cli, "_record_attempt", lambda a: None)
    text, err = cli.complete_one("u" * 3_000, system_prompt="s" * 300, max_tokens=900)
    assert (text, err) == ("ok", None)
    assert seen["admit"] == (1_100 + 900, 900)
    assert seen["settle"] == (120, 40, False) and seen["released"]


# ---- the registry: daily budgets fit the quotas; per-minute budgets wait for L3's single owners

def test_daily_and_per_minute_budgets_fit_every_groq_quota():
    reg = A.load_registry()
    assert A.runtime_drift(reg) == []
    over = [f.message for f in A.validate(reg, env={}) if f.code == "BUDGET_EXCEEDS_QUOTA"]
    assert not [m for m in over if ": tpd " in m or ": rpd " in m]
    # L2 (11.466) reported per-minute overshoot on the SHARED pairs; L3 (11.467) gives every Groq pair one owner
    assert not [m for m in over if m.startswith("groq_")]
