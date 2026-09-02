"""MICROBATCH-CONCURRENCY-V1 knob: `enrichment_batch_concurrency` was read
with getattr(settings, ..., 5) but never declared on WorkerSettings, so the
env could not size it to the enrichment pin (measured 2026-09-02: 8 lanes
pinned, 5 batches in flight). Pin: declared, default 5, env-overridable,
bounded."""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import pytest

from polymath_shared.settings import WorkerSettings


def test_declared_with_the_historical_default(monkeypatch):
    monkeypatch.delenv("POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY", raising=False)
    s = WorkerSettings(_env_file=None)
    assert s.enrichment_batch_concurrency == 5


def test_env_sizes_it_to_the_pin(monkeypatch):
    monkeypatch.setenv("POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY", "9")
    assert WorkerSettings(_env_file=None).enrichment_batch_concurrency == 9


def test_bounds_reject_nonsense(monkeypatch):
    monkeypatch.setenv("POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY", "0")
    with pytest.raises(Exception):
        WorkerSettings(_env_file=None)


def test_summary_worker_reads_the_declared_field():
    src = (ROOT / "workers" / "workers" / "summary_worker_impl.py").read_text()
    assert '"enrichment_batch_concurrency"' in src
