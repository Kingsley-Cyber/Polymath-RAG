"""SUMMARY-SWEEP-SERIALIZATION-V1 — regression for the 2026-09-05 cross-process
deadlock: two summary workers sweeping the SAME corpus wedged on
summary_jobs (stage, input_hash). Worker A's outer ticket transaction held an
uncommitted `_ensure_job` upsert for key K while worker B's short transaction
upserted K (and vice versa); Postgres could not detect the cycle because one
edge of it was a Python wait, so both workers sat "healthy" for 15 minutes.

Laws proven here:
  1. `_ensure_job` NEVER waits forever on a peer's transaction — it bounds the
     lock wait (POLYMATH_SUMMARY_LOCK_TIMEOUT_MS) and raises.
  2. A corpus sweep is exclusive per (stage, corpus): the second worker's
     try-lock is refused until the first commits.
  3. Every sweeping handler takes the sweep lock (structural contract).
Requires the dev Postgres (docker polymath-v4-postgres-1); skips otherwise.
"""
from __future__ import annotations

import inspect
import os
import pathlib
import sys
import threading
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers", "control"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from workers import summary_worker_impl as impl  # noqa: E402

DSN = os.environ.get("POLYMATH_TEST_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _connect():
    try:
        return psycopg.connect(DSN, autocommit=False, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")


@pytest.fixture
def two_conns():
    a, b = _connect(), _connect()
    yield a, b
    for c in (a, b):
        try:
            c.rollback(); c.close()
        except Exception:  # noqa: BLE001
            pass


def test_ensure_job_bounds_the_lock_wait(two_conns, monkeypatch):
    """Law 1: peer holds key K uncommitted → our upsert raises quickly, never hangs."""
    monkeypatch.setenv("POLYMATH_SUMMARY_LOCK_TIMEOUT_MS", "1500")
    a, b = two_conns
    key = "in_test_" + uuid.uuid4().hex
    corpus = "sweep-test-" + uuid.uuid4().hex[:8]
    impl._ensure_job(a, "tkt_a_" + uuid.uuid4().hex[:12], "PARENT_ENRICHMENT", corpus, key)   # uncommitted
    outcome: dict = {}

    def peer():
        try:
            impl._ensure_job(b, "tkt_b_" + uuid.uuid4().hex[:12], "PARENT_ENRICHMENT", corpus, key)
            outcome["result"] = "returned"
        except psycopg.errors.LockNotAvailable as exc:
            outcome["result"] = "lock_timeout"; outcome["exc"] = exc
        except Exception as exc:  # noqa: BLE001
            outcome["result"] = f"other:{type(exc).__name__}"

    t = threading.Thread(target=peer, daemon=True); t.start(); t.join(timeout=10)
    still_blocked = t.is_alive()
    a.rollback()                      # release the peer whatever happened
    t.join(timeout=10)
    assert not still_blocked, "the peer upsert hung on the uncommitted key — unbounded lock wait (the 2026-09-05 wedge)"
    assert outcome.get("result") == "lock_timeout", outcome


def test_sweep_lock_is_exclusive_per_stage_and_corpus(two_conns):
    """Law 2: one sweep per (stage, corpus) at a time; released with the transaction."""
    a, b = two_conns
    corpus = "sweep-test-" + uuid.uuid4().hex[:8]
    assert impl._try_sweep_lock(a, "parent_enrichment", corpus) is True
    assert impl._try_sweep_lock(b, "parent_enrichment", corpus) is False, "second worker must be refused while the first sweeps"
    assert impl._try_sweep_lock(b, "parent_summary", corpus) is True, "a different stage of the same corpus is independent"
    a.rollback()
    b.rollback()
    assert impl._try_sweep_lock(b, "parent_enrichment", corpus) is True, "the lock dies with the holder's transaction"


def test_enrichment_partitions_the_corpus_by_document(two_conns):
    """ENRICH-DOC-PARTITION-V1: two workers sweep DISJOINT documents of one
    corpus concurrently; the same document is never held twice."""
    a, b = two_conns
    corpus = "sweep-test-" + uuid.uuid4().hex[:8]
    assert impl._doc_sweep_lock(a, "parent_enrichment", corpus, "doc1") is True
    assert impl._doc_sweep_lock(b, "parent_enrichment", corpus, "doc1") is False, "peer must skip a held document"
    assert impl._doc_sweep_lock(b, "parent_enrichment", corpus, "doc2") is True, "peer sweeps the other document meanwhile"
    assert impl._try_sweep_lock(b, "parent_summary", corpus) is True, "other stages keep their corpus-level lock"
    a.rollback()
    assert impl._doc_sweep_lock(b, "parent_enrichment", corpus, "doc1") is True, "the document lock dies with the holder's transaction"


def test_ladder_fan_out_is_concurrent_and_ordered():
    """ENRICH-LADDER-FANOUT-V1: N calls on width N finish in ~one call's
    time and keep input order."""
    import time
    items = [("p%d" % i, "sys", "user", 100) for i in range(6)]

    def one(item):
        time.sleep(0.3)
        return (item[0], "raw", None)
    t0 = time.monotonic()
    out = impl._fan_out(items, one, width=6)
    wall = time.monotonic() - t0
    assert [o[0] for o in out] == [i[0] for i in items]
    assert wall < 1.0, f"6 x 0.3 s calls took {wall:.2f}s — not concurrent"
    assert impl._fan_out([], one, width=4) == []


def test_enrichment_ladders_fan_out_in_source():
    import inspect
    src = inspect.getsource(impl)
    body = src[src.index("def _complete_fb("):src.index("_persisted: set = set()")]
    assert body.count("_fan_out(") == 2, "semantic failover and hard-case escape must both fan out"


def test_enrichment_outcomes_persist_in_their_own_transactions():
    """ENRICH-OUTCOME-DURABILITY-V1: no compiled parent is persisted on the
    ticket's outer connection; INVALID/terminal rows land committed like READY."""
    import inspect
    src = inspect.getsource(impl._do_enrichment)
    assert "persist_compiled_parent(\n                conn," not in src and "persist_compiled_parent(conn," not in src, \
        "a compiled parent is still persisted on the outer (rarely committed) transaction"
    assert src.count("persist_compiled_parent(") == 2 and src.count("with _ptx() as _c:") == 2
    assert "ENRICH_CALL_LADDER" in src, "ladder calls must leave receipts"


def test_every_sweeping_handler_takes_the_sweep_lock():
    """Law 3: the structural contract — every handler that sweeps a corpus serializes on it."""
    for name in ("_do_parents", "_do_document", "_do_corpus", "_do_vocabulary", "_do_enrichment"):
        src = inspect.getsource(getattr(impl, name))
        if name == "_do_enrichment":
            import re
            assert "_doc_sweep_lock(" in src and not re.search(r'(?<!_doc)_sweep_lock\(conn, "parent_enrichment"', src), \
                "parent_enrichment partitions the corpus per document (ENRICH-DOC-PARTITION-V1)"
            continue
        assert "_sweep_lock(" in src, f"{name} sweeps the corpus without the per-(stage, corpus) sweep lock"
