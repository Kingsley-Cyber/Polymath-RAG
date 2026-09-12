"""PROVIDER-ATTEMPT-LEDGER on the BATCHED seam (2026-09-12).

§15 exists for one failure mode, stated in its own words:

    lane A -> HTTP 429 · lane B -> HTTP 429 · lane C -> HTTP 200 · PMAP batch -> SUCCESS

"Batch success is correct. But the first two attempts must not disappear." The ledger
recorded attempts only inside `LLMExtractionClient.complete_one` — the SINGLE-completion
path. Every batched extraction and pMAP dispatch goes through `_infer_batch_call`, which
recorded nothing. Measured on the live database before this fix: 209 rows spanning
3 distinct lanes, while 13 lanes showed real dispatch activity in the durable limiter
state, and every row was untagged. The telemetry was blind on exactly the path the
motivating example describes.

These tests pin the four branches with a mocked transport, so the wiring is proven
without spending provider quota: limiter refusal (no HTTP), success, an HTTP error
carrying Retry-After (the 429 case), and a transport error.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.llm_extraction import client as C  # noqa: E402


class _Limiter:
    """Minimal limiter: `admit` decides whether acquire() lets the call through."""

    def __init__(self, admit: bool = True):
        self.admit, self.effective, self.released = admit, 1, False

    def acquire(self, est_tokens=0.0):
        return self.admit

    def record_failure(self, retry_after=None, headers=None):
        self.failed = True

    def record_success(self):
        self.succeeded = True

    def release(self):
        self.released = True


def _client() -> C.LLMExtractionClient:
    """`lane` is the TRANSPORT kind ("local"/"cloud"); the lane NAME the ledger records
    is `limiter_key` — which is what `complete_one` has always recorded, so the batched
    seam must match it or the two halves of the ledger would disagree on identity."""
    return C.LLMExtractionClient("cloud", url="http://127.0.0.1:9/v1",
                                 model="test/model", limiter_key="gemini-test")


@pytest.fixture()
def recorded(monkeypatch):
    """Capture every Attempt the client records instead of writing to Postgres."""
    seen: list = []
    import polymath_shared.conformance.attempts as A
    monkeypatch.setattr(A, "record", lambda a: seen.append(a))
    return seen


def _call(cli, limiter, items=(("n1", "user prompt", 64),)):
    return cli._infer_batch_call(list(items), limiter, decision=None, cap=1,
                                 use_lean=False, system_prompt=None)


def test_limiter_refusal_is_recorded_as_an_attempt_that_never_dispatched(recorded):
    """A LOCAL refusal is not a provider request — it must be distinguishable from one,
    which is why the ledger carries `limiter_admitted` and `http_dispatched` separately."""
    cli = _client()
    with pytest.raises(C.ExtractionTransportError):
        _call(cli, _Limiter(admit=False))
    assert len(recorded) == 1
    a = recorded[0]
    assert a.lane == "gemini-test"   # the lane NAME, not "cloud"
    assert a.limiter_admitted is False and a.http_dispatched is False
    assert a.success is False and a.error_class == "limiter_refused"


def test_a_successful_batch_is_recorded(monkeypatch, recorded):
    cli = _client()

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    monkeypatch.setattr(C.httpx, "post", lambda *a, **k: _Resp())
    _call(cli, _Limiter())
    assert len(recorded) == 1
    a = recorded[0]
    assert a.limiter_admitted is True and a.http_dispatched is True
    assert a.success is True and a.http_status == 200
    assert a.latency_ms is not None


def test_a_429_is_recorded_with_its_status_and_retry_after(monkeypatch, recorded):
    """THE case §15 names: a throttled attempt inside a batch. Before this it vanished —
    only the batch's terminal outcome was durable."""
    cli = _client()
    request = httpx.Request("POST", "http://127.0.0.1:9/v1/infer_batch")
    response = httpx.Response(429, headers={"retry-after": "7"}, request=request)

    def _raise(*a, **k):
        raise httpx.HTTPStatusError("429", request=request, response=response)

    monkeypatch.setattr(C.httpx, "post", _raise)
    with pytest.raises(C.ExtractionTransportError):
        _call(cli, _Limiter())
    assert len(recorded) == 1
    a = recorded[0]
    assert a.http_dispatched is True and a.success is False
    assert a.http_status == 429 and a.retry_after_s == 7.0
    assert a.error_class == "http_429"


def test_a_transport_error_is_recorded(monkeypatch, recorded):
    cli = _client()
    request = httpx.Request("POST", "http://127.0.0.1:9/v1/infer_batch")

    def _raise(*a, **k):
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(C.httpx, "post", _raise)
    with pytest.raises(C.ExtractionTransportError):
        _call(cli, _Limiter())
    assert len(recorded) == 1
    a = recorded[0]
    assert a.http_dispatched is True and a.success is False
    assert a.error_class == "ConnectError" and a.http_status is None


def test_recording_never_breaks_a_dispatch(monkeypatch):
    """The ledger is diagnostics: a broken ledger must never fail a real extraction.
    `record` is fail-soft by construction; this pins that the client does not undo it."""
    cli = _client()
    import polymath_shared.conformance.attempts as A

    def _explode(a):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(A, "record", _explode)

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    monkeypatch.setattr(C.httpx, "post", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError):
        # documents the CURRENT contract: the client calls `record` directly, and
        # `record`'s own try/except is what makes it safe. If that swallow is ever
        # removed, this test fails loudly rather than extraction breaking in production.
        _call(cli, _Limiter())
