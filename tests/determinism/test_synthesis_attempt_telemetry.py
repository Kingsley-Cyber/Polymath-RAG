"""§15 on the CHAT seams: answer synthesis is an external model attempt too (2026-09-12).

The attempt ledger covered extraction and the query compiler. Answer synthesis —
`litellm.completion` against paid models, and the Ollama path, whose entire catalog on
this host is `*-cloud` and therefore not local inference at all — recorded nothing. Two
things made that hard rather than merely undone:

  * these seams have NO lane limiter, and the ledger's documented invariant was
    `limiter_admitted=false => zero HTTP, zero quota`. Recording a synthesis attempt
    either way would have written a false statement, so migration 0059 added
    `limiter_bypassed` to say "not applicable" instead of guessing;
  * a streaming generator ends at `done`, at an error chunk, at a non-200 or at an
    exception, and recording at each exit duplicates the row or drops it. `_AttemptOutcome`
    owns exactly one row per dispatch and writes it on the way out.

The bound-retry loop in `_litellm_generate` is §15's example again, in chat: attempt 1
refused for max_tokens, attempt 2 succeeds, the user gets an answer, and attempt 1 used
to survive only as a `degraded` event inside a stream the browser then closes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / p))

from orchestrator.api import ui as UI  # noqa: E402
from polymath_shared.llm_extraction import client as C  # noqa: E402


@pytest.fixture()
def recorded(monkeypatch):
    seen: list = []
    import polymath_shared.conformance.attempts as A
    monkeypatch.setattr(A, "record", lambda a: seen.append(a))
    return seen


# ── _AttemptOutcome: one row per dispatch, whichever exit is taken ───────────

def test_a_completed_stream_records_one_success(recorded):
    with UI._AttemptOutcome("http://127.0.0.1:11434", "gemma4:31b-cloud") as out:
        out.status(200)
        out.ok()
    assert len(recorded) == 1
    a = recorded[0]
    assert a.success is True and a.http_status == 200 and a.error_class is None
    assert a.limiter_bypassed is True and a.limiter_admitted is False
    assert a.lane == "chat_synth:ollama" and a.provider == "127.0.0.1:11434"


def test_a_stream_that_never_finished_is_not_a_success(recorded):
    """The failure mode a success-only record would hide: the generator is abandoned
    (client disconnects, provider stalls) and no `done` ever arrives."""
    with UI._AttemptOutcome("http://127.0.0.1:11434", "m") as out:
        out.status(200)                       # headers fine, body never completed
    assert len(recorded) == 1
    assert recorded[0].success is False
    assert recorded[0].error_class == "INCOMPLETE_STREAM"


def test_a_non_200_records_its_status(recorded):
    with UI._AttemptOutcome("http://127.0.0.1:11434", "m") as out:
        out.status(429)
    assert recorded[0].http_status == 429 and recorded[0].error_class == "HTTP_429"
    assert recorded[0].success is False


def test_an_exception_class_survives_as_the_error_class(recorded):
    with UI._AttemptOutcome("http://127.0.0.1:11434", "m") as out:
        out.failed("ConnectError")
    assert recorded[0].error_class == "ConnectError" and recorded[0].success is False


def test_exactly_one_row_per_dispatch_even_with_several_markers(recorded):
    """Marking is idempotent by construction — the row is written once, on exit."""
    with UI._AttemptOutcome("http://127.0.0.1:11434", "m") as out:
        out.status(200); out.ok(); out.status(200)
    assert len(recorded) == 1


# ── the bound-retry loop: §15's example, in chat ─────────────────────────────

def test_the_bound_retry_records_BOTH_attempts(monkeypatch, recorded):
    calls = {"n": 0}

    class _Chunk:
        class _C:
            class delta:
                content = "hi"
                reasoning_content = None
            finish_reason = "stop"
        choices = [_C]

    def _completion(**kwargs):
        calls["n"] += 1
        if "max_tokens" in kwargs:
            raise ValueError("max_tokens is not supported by this provider")
        return [_Chunk()]

    monkeypatch.setattr(UI, "_chat_max_tokens", lambda: 6000)
    monkeypatch.setattr(UI, "_bound_rejected", lambda exc: True)
    monkeypatch.setattr(UI, "_grounded_messages",
                        lambda *a, **k: [{"role": "user", "content": "q"}])
    monkeypatch.setattr(UI, "_prompt_stats", lambda *a, **k: {})
    import litellm
    monkeypatch.setattr(litellm, "completion", _completion)

    events = list(UI._litellm_generate("anthropic/deepseek-v4-flash-0731", "q", {}, [],
                                       None, None))
    assert any(e.get("token") for e in events), "the caller still gets an answer"
    assert calls["n"] == 2, "one refused attempt, one that worked"
    assert len(recorded) == 2, "both attempts durable, not just the outcome"
    assert recorded[0].success is False and recorded[0].error_class == "ValueError"
    assert recorded[1].success is True
    assert all(a.limiter_bypassed is True for a in recorded)
    assert all(a.provider == "anthropic" for a in recorded)


# ── the extraction client's probe, the other limiter-bypassing seam ──────────

def test_probe_records_as_bypassed_not_as_refused(monkeypatch, recorded):
    """A probe that takes a 401 or a 429 is exactly the evidence a lane-qualification
    argument turns on, and it was recorded nowhere."""
    cli = C.LLMExtractionClient("cloud", url="http://127.0.0.1:9/v1", model="m",
                                limiter_key="probe-lane")

    class _Resp:
        status_code = 429
        headers = {"retry-after": "12"}
        text = ""

        def raise_for_status(self):
            raise RuntimeError("429")

        def json(self):
            return {}

    monkeypatch.setattr(C.httpx, "post", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError):
        cli.probe()
    assert len(recorded) == 1
    a = recorded[0]
    assert a.limiter_bypassed is True and a.limiter_admitted is False
    assert a.http_dispatched is True, "a bypassing attempt still reached the provider"
    assert a.http_status == 429 and a.retry_after_s == 12.0


def test_a_refusal_and_a_bypass_are_not_the_same_row_shape(recorded):
    """The distinction migration 0059 exists for: `limiter_admitted=false` alone can no
    longer be read as 'zero HTTP, zero quota', so every reader of 'refused' must also
    require `NOT limiter_bypassed`."""
    from polymath_shared.conformance.attempts import Attempt
    refused = Attempt(lane="l", limiter_admitted=False, http_dispatched=False,
                      success=False)
    bypassed = Attempt(lane="l", limiter_admitted=False, http_dispatched=True,
                       success=True, limiter_bypassed=True)
    assert refused.limiter_bypassed is False
    assert (refused.limiter_admitted, refused.http_dispatched) == (False, False)
    assert (bypassed.limiter_admitted, bypassed.http_dispatched) == (False, True)


# ── the two counting bugs the live probe exposed ─────────────────────────────

def test_nested_contexts_share_one_correlation_id():
    """`correlation_id` "groups the attempts of one logical call". Minting a fresh id in
    every context split the Ollama `think` retry — a second attempt context opened inside
    the first — across two ids, so the retry looked like two separate calls and
    `failover_attempts` read as zero while a retry had plainly happened."""
    from polymath_shared.conformance.attempts import attempt_context
    with attempt_context(function="CHAT", stage="outer") as outer:
        with attempt_context(function="CHAT", stage="inner") as inner:
            assert inner["correlation_id"] == outer["correlation_id"]
            assert inner["stage"] == "inner", "inner fields still override"
        with attempt_context(function="CHAT", stage="sibling") as sib:
            assert sib["correlation_id"] == outer["correlation_id"]


class _StubConn:
    """Returns the summary row, then the per-lane rows, in call order."""

    def __init__(self, head, per_lane):
        self._rows = [head, per_lane]

    def execute(self, *a, **k):
        row = self._rows.pop(0)
        class _R:
            def fetchone(_self): return row
            def fetchall(_self): return row
        return _R()


def test_failover_is_not_inflated_by_attempts_that_have_no_logical_call():
    """attempts=22 with 14 uncorrelated rows and 6 logical calls read as failover=16
    live — i.e. a seam that simply forgot its attempt_context looked exactly like heavy
    provider failover. Failover is (attempts - logical calls) over CORRELATED rows."""
    from polymath_shared.conformance.attempts import attempt_summary
    #    attempts, refused, bypassed, dispatched, 429, ok, calls, uncorrelated
    head = (22, 0, 6, 22, 0, 6, 6, 14)
    s = attempt_summary(_StubConn(head, []), "10 minutes")
    assert s["failover_attempts"] == 2, "22 - 14 uncorrelated - 6 logical calls"
    assert s["uncorrelated_attempts"] == 14, "reported, not hidden inside failover"


def test_a_clean_window_with_no_uncorrelated_rows_is_unchanged():
    """The correction must not quietly change the number when every row IS correlated."""
    from polymath_shared.conformance.attempts import attempt_summary
    head = (9, 1, 0, 8, 3, 3, 3, 0)
    s = attempt_summary(_StubConn(head, []), "10 minutes")
    assert s["failover_attempts"] == 6 and s["uncorrelated_attempts"] == 0
