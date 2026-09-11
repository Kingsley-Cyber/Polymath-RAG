"""TERMINAL-STATE-V1 (D-1) — six distinct outcomes, classified from REAL dispatch metadata.

The defect (measured 2026-09-10, register 11.196): three pMAP batches carried a
`raw_response_hash` — proof that a request reached the provider and was answered — yet
their terminal marker was `LIMITER_REFUSED`, which means "refused LOCALLY, zero HTTP,
zero quota". One of the three hashed to the SHA-256 of the empty string, i.e. an empty
200. The control plane's refused-vs-429 distinction (11.187) is built on those being
different things, so a backfill would have reported spent requests as free refusals.

Two properties are pinned here:
  1. classification comes from `dispatched` / error class / body / compiler result —
     never from error TEXT;
  2. a later LOCAL refusal cannot overwrite a terminal state that proves dispatch.
"""
from __future__ import annotations

import pytest

from workers.doc_parent_map_worker import (
    DISPATCHED_TERMINAL_STATES, TERMINAL_COMPILER_REJECTED, TERMINAL_HTTP_429,
    TERMINAL_LIMITER_REFUSED, TERMINAL_PROVIDER_EMPTY, TERMINAL_PROVIDER_ERROR,
    TERMINAL_SUCCESS, classify_terminal_state, record_batch_result,
)


# ── 1. classification from real dispatch metadata ────────────────────────────

@pytest.mark.parametrize("kw,expected", [
    # the ONLY free outcome: the limiter refused admission, nothing left the process
    (dict(dispatched=False), TERMINAL_LIMITER_REFUSED),
    (dict(dispatched=False, error_class="LIMITER_REFUSED"), TERMINAL_LIMITER_REFUSED),
    # everything below COST a provider request
    (dict(dispatched=True, error_class="HTTP_429"), TERMINAL_HTTP_429),
    (dict(dispatched=True, error_class="HTTP_500"), TERMINAL_PROVIDER_ERROR),
    (dict(dispatched=True, error_class="ReadTimeout"), TERMINAL_PROVIDER_ERROR),
    (dict(dispatched=True, raw=""), TERMINAL_PROVIDER_EMPTY),
    (dict(dispatched=True, raw="   \n "), TERMINAL_PROVIDER_EMPTY),
    (dict(dispatched=True, raw=None), TERMINAL_PROVIDER_EMPTY),
    (dict(dispatched=True, raw="P0001 -> alpha", mapped_all=True, compiled_any=True), TERMINAL_SUCCESS),
    (dict(dispatched=True, raw="garbage", compiler_rejected=True), TERMINAL_COMPILER_REJECTED),
    (dict(dispatched=True, raw="P1 -> a", compiled_any=True, mapped_all=False), TERMINAL_COMPILER_REJECTED),
])
def test_classification_comes_from_metadata_not_error_text(kw, expected) -> None:
    assert classify_terminal_state(**kw) == expected


def test_a_dispatched_empty_body_is_never_a_local_refusal() -> None:
    """THE D-1 REGRESSION, at the classifier level."""
    state = classify_terminal_state(dispatched=True, raw="")
    assert state == TERMINAL_PROVIDER_EMPTY
    assert state != TERMINAL_LIMITER_REFUSED
    assert state in DISPATCHED_TERMINAL_STATES


def test_only_the_local_refusal_is_outside_the_dispatched_set() -> None:
    assert TERMINAL_LIMITER_REFUSED not in DISPATCHED_TERMINAL_STATES
    for s in (TERMINAL_HTTP_429, TERMINAL_PROVIDER_ERROR, TERMINAL_PROVIDER_EMPTY,
              TERMINAL_COMPILER_REJECTED, TERMINAL_SUCCESS):
        assert s in DISPATCHED_TERMINAL_STATES


def test_the_six_states_are_distinct() -> None:
    states = {TERMINAL_LIMITER_REFUSED, TERMINAL_HTTP_429, TERMINAL_PROVIDER_EMPTY,
              TERMINAL_PROVIDER_ERROR, TERMINAL_COMPILER_REJECTED, TERMINAL_SUCCESS}
    assert len(states) == 6


# ── 2. a local refusal cannot erase proof of dispatch ────────────────────────

class _FakeConn:
    """Captures the UPDATE the recorder issues, with its bound parameters."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):  # noqa: ANN001
        self.calls.append((" ".join(str(sql).split()), tuple(params)))
        return self


def _params(conn: _FakeConn) -> tuple:
    assert conn.calls, "recorder issued no statement"
    return conn.calls[-1][1]


def test_recording_a_local_refusal_carries_the_downgrade_guard() -> None:
    """Writing LIMITER_REFUSED must be guarded so a dispatched row keeps its marker."""
    conn = _FakeConn()
    record_batch_result(conn, batch_id="b1", status="partial", valid_count=0,
                        last_error=TERMINAL_LIMITER_REFUSED)
    sql = conn.calls[-1][0]
    assert "CASE" in sql and "raw_response_hash IS NOT NULL" in sql, sql
    assert True in _params(conn), "the guard flag must be set for a local refusal"


def test_recording_a_dispatched_state_is_not_guarded() -> None:
    """PROVIDER_EMPTY / 429 / errors describe real spend and must always be written."""
    for state in (TERMINAL_PROVIDER_EMPTY, TERMINAL_HTTP_429, TERMINAL_PROVIDER_ERROR,
                  TERMINAL_COMPILER_REJECTED):
        conn = _FakeConn()
        record_batch_result(conn, batch_id="b1", status="partial", valid_count=0,
                            last_error=state)
        assert False in _params(conn), f"{state} must not be downgrade-guarded"


def test_success_clears_the_marker_and_is_not_guarded() -> None:
    conn = _FakeConn()
    record_batch_result(conn, batch_id="b1", status="done", valid_count=5, last_error=None)
    assert False in _params(conn)


def test_the_guard_also_catches_a_wrapped_refusal_message() -> None:
    """Legacy call sites passed a full message; the guard matches on substring too."""
    conn = _FakeConn()
    record_batch_result(conn, batch_id="b1", status="partial", valid_count=0,
                        last_error="groq/compound-mini error: LIMITER_REFUSED")
    assert True in _params(conn)
