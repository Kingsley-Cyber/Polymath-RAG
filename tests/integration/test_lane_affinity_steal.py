"""LANE-AFFINITY-STEAL-V1 — DB-backed claim semantics, rolled back.

A cloud-affinity worker must (1) skip a local-lane run while claiming a
cloud-lane run first, and (2) STEAL the local-lane run once no cloud
work remains. A local-affinity worker mirrors this. Affinity never
strands work.
"""
from __future__ import annotations

import json
import pathlib
import sys

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.execution import worker_identity  # noqa: E402
from polymath_shared.worker_runtime import claim_ticket_events  # noqa: E402
from polymath_shared.llm_extraction.policy import effective_threshold  # noqa: E402

# the EFFECTIVE boundary (config may raise the owner floor) — the same
# number the claim predicate uses in production
THRESHOLD = effective_threshold(get_settings().worker.cloud_min_bytes)


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _mk_lane_run(conn, tag: str, byte_length: int) -> str:
    corpus, run = f"steal-test-{tag}", f"run_steal_test_{tag}"
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) "
        "VALUES (%s, %s, 'steal-test') ON CONFLICT DO NOTHING",
        (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata) "
        "VALUES (%s, %s, 'intake', '{}')", (run, corpus))
    conn.execute(
        "INSERT INTO documents (doc_id, corpus_id, source_name, media_type, "
        "byte_length, content_hash) VALUES (%s, %s, %s, 'text/plain', %s, %s)",
        (f"doc_steal_{tag}", corpus, f"{tag}.md", byte_length,
         f"hash_steal_{tag}"))
    conn.execute(
        "INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key) "
        "VALUES (%s, 'chunked.v1', %s, %s)",
        (run, json.dumps({"run_id": run, "doc_id": f"doc_steal_{tag}"}),
         f"steal-test-key-{tag}"))
    conn.execute(
        "INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, "
        "event_type, status) VALUES (%s, %s, %s, 'extract', 'chunked.v1', 'ready')",
        (f"tkt_steal_{tag}", run, corpus))
    return run


def test_affinity_prefers_home_lane_then_steals(conn) -> None:
    local_run = _mk_lane_run(conn, "loc", THRESHOLD)           # local lane
    cloud_run = _mk_lane_run(conn, "cld", THRESHOLD + 1)       # cloud lane
    identity = worker_identity("extract")

    # cloud affinity: claims the cloud run FIRST even though the local
    # event has a lower event_id (insertion order above).
    got = claim_ticket_events(conn, identity, ["chunked.v1"], 1,
                              lane_affinity="cloud")
    assert [e["run_id"] for e in got] == [cloud_run]

    # cloud lane now dry -> the SAME affinity steals the local run.
    got = claim_ticket_events(conn, identity, ["chunked.v1"], 1,
                              lane_affinity="cloud")
    assert [e["run_id"] for e in got] == [local_run]


def test_local_affinity_mirrors(conn) -> None:
    local_run = _mk_lane_run(conn, "loc2", 1_000)
    cloud_run = _mk_lane_run(conn, "cld2", THRESHOLD * 2)
    identity = worker_identity("extract")

    got = claim_ticket_events(conn, identity, ["chunked.v1"], 1,
                              lane_affinity="local")
    assert [e["run_id"] for e in got] == [local_run]
    got = claim_ticket_events(conn, identity, ["chunked.v1"], 1,
                              lane_affinity="local")
    assert [e["run_id"] for e in got] == [cloud_run]


def test_no_affinity_is_byte_identical_ordering(conn) -> None:
    first = _mk_lane_run(conn, "any1", 1_000)
    _mk_lane_run(conn, "any2", THRESHOLD * 2)
    identity = worker_identity("extract")
    got = claim_ticket_events(conn, identity, ["chunked.v1"], 1)
    assert [e["run_id"] for e in got] == [first]   # plain event_id order
