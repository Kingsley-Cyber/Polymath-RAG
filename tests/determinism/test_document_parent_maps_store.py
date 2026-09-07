"""DOCUMENT-SEMANTIC-INDEX-V1 slice S4 — parent-map SQL durability.

Verifies migration 0054 against a real Postgres: idempotent batch insert
(restart/retry never duplicates completed API work), partial batch state, exactly
ONE active map per (doc_id, parent_id, map_contract) with supersede, and
restart-safe map insert. Skips when no database is reachable (as the other
document_profile stage tests do), so CI without a Postgres service is unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

MIGRATION = ROOT / "stores" / "postgres" / "migrations" / "0054_document_parent_maps.sql"
DOC = "s4-parent-map-test-doc"
CORPUS = "s4-parent-map-test-corpus"
CONTRACT = "map-compiler-v1"


def _tx():
    from polymath_shared.db import tx
    return tx


@pytest.fixture()
def db():
    tx = _tx()
    try:
        with tx() as conn:
            exists = conn.execute("SELECT to_regclass('public.document_parent_maps')").fetchone()[0]
    except Exception as exc:  # pragma: no cover - environment gate
        pytest.skip(f"postgres unavailable: {exc}")
    if exists is None:
        pytest.skip(f"migration 0054 not applied (apply {MIGRATION.name} first)")
    # A corpus + document to satisfy the FKs.
    with tx() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id=%s", (DOC,))
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,%s) ON CONFLICT (corpus_id) DO NOTHING",
            (CORPUS, "S4 Test Corpus", "cfg-s4"),
        )
        conn.execute(
            "INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (DOC, CORPUS, "S4 Test.md", "text/markdown", 10, "hash-s4"),
        )
    yield tx
    with tx() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id=%s", (DOC,))   # cascades to batches/maps/exclusions
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))


def _insert_batch(conn, batch_id, *, status="pending", expected=3):
    from psycopg.types.json import Json
    conn.execute(
        "INSERT INTO document_parent_map_batches "
        "(batch_id, run_id, doc_id, map_contract, ordinal, status, expected_count, alias_manifest, input_hash) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (batch_id) DO NOTHING",
        (batch_id, "run-1", DOC, CONTRACT, 0, status, expected, Json({"P0001": "chunk-1"}), "input-hash"),
    )


def _insert_map(conn, map_id, parent_id, *, active=True):
    from psycopg.types.json import Json
    conn.execute(
        "INSERT INTO document_parent_maps "
        "(map_id, doc_id, parent_id, map_contract, alias, routing_signature, semantic_hooks, exact_identifiers, map_hash, active) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (map_id) DO NOTHING",
        (map_id, DOC, parent_id, CONTRACT, "P0001", "routing sig", Json(["h1", "h2"]), Json(["CVE-2026-0217"]), map_id, active),
    )


def test_batch_insert_is_idempotent_restart_safe(db):
    tx = db
    with tx() as conn:
        _insert_batch(conn, "batch-hash-A")
    with tx() as conn:
        _insert_batch(conn, "batch-hash-A")   # replay: same source-bound batch_id
    with tx() as conn:
        n = conn.execute("SELECT count(*) FROM document_parent_map_batches WHERE batch_id=%s", ("batch-hash-A",)).fetchone()[0]
    assert n == 1   # completed API work is not duplicated on restart


def test_batch_partial_state_transitions_persist(db):
    tx = db
    with tx() as conn:
        _insert_batch(conn, "batch-hash-B", status="pending", expected=3)
    with tx() as conn:
        conn.execute("UPDATE document_parent_map_batches SET status='leased', lease_owner='w1', lease_expires_at=now()+interval '60 seconds' WHERE batch_id=%s", ("batch-hash-B",))
    with tx() as conn:
        conn.execute("UPDATE document_parent_map_batches SET status='partial', valid_count=2 WHERE batch_id=%s", ("batch-hash-B",))
    with tx() as conn:
        row = conn.execute("SELECT status, valid_count, expected_count FROM document_parent_map_batches WHERE batch_id=%s", ("batch-hash-B",)).fetchone()
    assert row == ("partial", 2, 3)   # 2 of 3 durable; 1 remains to repair


def test_exactly_one_active_map_per_parent_and_supersede(db):
    import psycopg
    tx = db
    with tx() as conn:
        _insert_map(conn, "map-v1", "chunk-1", active=True)
    # A second ACTIVE map for the same (doc, parent, contract) is rejected.
    with pytest.raises(psycopg.errors.UniqueViolation):
        with tx() as conn:
            _insert_map(conn, "map-v2", "chunk-1", active=True)
    # Supersede: deactivate v1, then v2 becomes the single active map.
    with tx() as conn:
        conn.execute("UPDATE document_parent_maps SET active=false WHERE map_id=%s", ("map-v1",))
    with tx() as conn:
        _insert_map(conn, "map-v2", "chunk-1", active=True)
    with tx() as conn:
        actives = conn.execute("SELECT map_id FROM document_parent_maps WHERE doc_id=%s AND parent_id=%s AND map_contract=%s AND active", (DOC, "chunk-1", CONTRACT)).fetchall()
    assert actives == [("map-v2",)]


def test_map_insert_is_idempotent(db):
    tx = db
    with tx() as conn:
        _insert_map(conn, "map-idem", "chunk-7", active=True)
    with tx() as conn:
        _insert_map(conn, "map-idem", "chunk-7", active=True)   # replay
    with tx() as conn:
        n = conn.execute("SELECT count(*) FROM document_parent_maps WHERE map_id=%s", ("map-idem",)).fetchone()[0]
    assert n == 1


def test_exclusion_is_accounted_and_idempotent(db):
    tx = db
    for _ in range(2):
        with tx() as conn:
            conn.execute(
                "INSERT INTO document_parent_exclusions (doc_id, parent_id, map_contract, reason) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (doc_id, parent_id, map_contract) DO NOTHING",
                (DOC, "chunk-toc", CONTRACT, "toc"),
            )
    with tx() as conn:
        row = conn.execute("SELECT reason, count(*) OVER () FROM document_parent_exclusions WHERE doc_id=%s AND parent_id=%s", (DOC, "chunk-toc")).fetchone()
    assert row == ("toc", 1)
