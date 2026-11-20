"""PROVIDER-CAPACITY-IS-TRANSIENT-V1 + TRANSIENT-HOLD-V1 (2026-09-05).
Measured on the 63-document cinema ingest: seven extraction tickets FAILED after
three HTTP 429s in ten minutes each (attempts burned by provider pacing, not by
extraction), and a summaries worker blocked on the corpus sweep lock while a
parent_summary ticket sat READY_UNCLAIMED for 4.2 hours.
Laws: a 429 / lane-refused transport error and a TransientStageHold are
TRANSIENT (ticket handed back, no attempt); a genuine transport garbage error
is still a failure; the sweep lock yields with TransientStageHold instead of
blocking past its wait cap."""
from __future__ import annotations

import os
import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers", "control"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import worker_runtime as rt  # noqa: E402
from polymath_shared.llm_extraction.client import ExtractionTransportError  # noqa: E402

from sealed_env import sealed_dsn  # SEALED-TEST-ISOLATION-V1: POLYMATH_TEST_DSN only


def test_provider_capacity_errors_are_transient():
    e429 = ExtractionTransportError("cloud transport failed: HTTP 429 <- httpx.HTTPStatusError: Client error '429 Too Many Requests'")
    assert rt._is_sidecar_unavailable(e429) is True
    assert rt.transient_backoff_s(e429) == rt._CAPACITY_BACKOFF_S
    refused = ExtractionTransportError("cloud lane refused 10/11 calls (LIMITER_REFUSED)")
    assert rt._is_sidecar_unavailable(refused) is True
    wrapped = RuntimeError("stage failed"); wrapped.__cause__ = e429
    assert rt._is_sidecar_unavailable(wrapped) is True, "capacity events are recognised anywhere in the cause chain"


def test_a_provider_503_is_a_capacity_event():
    """PROVIDER-503-IS-CAPACITY-V1 (measured 2026-09-21 and 2026-10-02): a Gemini "503 Service Unavailable" failed
    "The Innovator's Dilemma" twice while the pool's other lanes answered 200 — provider capacity, not the document."""
    e503 = ExtractionTransportError("cloud transport failed: HTTP 503 <- httpx.HTTPStatusError: Server error "
                                    "'503 Service Unavailable' for url 'https://generativelanguage.googleapis.com/v1beta/'")
    assert rt._is_sidecar_unavailable(e503) is True
    assert rt.transient_backoff_s(e503) == rt._CAPACITY_BACKOFF_S
    wrapped = RuntimeError("stage extract failed"); wrapped.__cause__ = e503
    assert rt._is_sidecar_unavailable(wrapped) is True
    assert rt._is_sidecar_unavailable(ExtractionTransportError("cloud transport failed: HTTP 500")) is False   # still a failure


def test_real_transport_failures_still_fail():
    garbage = ExtractionTransportError("endpoint repeatedly returned garbage")
    assert rt._is_sidecar_unavailable(garbage) is False
    assert rt._is_sidecar_unavailable(ValueError("bad json")) is False
    assert rt.transient_backoff_s(garbage) == rt._TRANSIENT_BACKOFF_S


def test_transient_hold_is_transient():
    assert rt._is_sidecar_unavailable(rt.TransientStageHold("SUMMARY_SWEEP_BUSY")) is True


def test_sweep_lock_yields_instead_of_blocking(monkeypatch):
    from workers import summary_worker_impl as impl
    try:
        a = psycopg.connect(sealed_dsn(), autocommit=False, connect_timeout=3)
        b = psycopg.connect(sealed_dsn(), autocommit=False, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")
    monkeypatch.setenv("POLYMATH_SUMMARY_SWEEP_WAIT_S", "1")
    corpus = "sweep-yield-" + uuid.uuid4().hex[:8]
    try:
        assert impl._try_sweep_lock(a, "parent_enrichment", corpus) is True
        with pytest.raises(rt.TransientStageHold):
            impl._sweep_lock(b, "parent_enrichment", corpus)
    finally:
        for c in (a, b):
            c.rollback(); c.close()
