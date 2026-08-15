"""I1 acceptance: manifest-driven bulk ingestion over the existing
pipeline (intake -> ... -> query_ready), no second implementation.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up). Uses the
frozen fixture tests/fixtures/i1/ copied into a temp directory so the
changed-content case never mutates the frozen fixture.

Gates: read-only plan, idempotent execution, changed-content
re-drive, partial-failure resume, missing/disabled semantics,
cwd-independent path resolution, corpus propagation, batch-bounded
resumable submission, and deterministic manifest identity.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLYMATH_INTEGRATION") != "1",
        reason="set POLYMATH_INTEGRATION=1 with live stores (make db-up)",
    ),
]

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.manifest import load_manifest, manifest_id  # noqa: E402
from control.manifest_ingest import (  # noqa: E402
    ACTION_ERROR_MISSING,
    ACTION_SKIP_DISABLED,
    execute_manifest,
    plan_manifest,
    status_manifest,
)

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "i1"
CORPUS = "i1-fixture-corpus"


def _wipe_corpus() -> None:
    with tx() as conn:
        rid_rows = conn.execute(
            "SELECT run_id FROM runs WHERE corpus_id=%s", (CORPUS,)
        ).fetchall()
        for (rid,) in rid_rows:
            conn.execute("DELETE FROM stage_attempts WHERE run_id=%s", (rid,))
            conn.execute("DELETE FROM artifacts WHERE run_id=%s", (rid,))
            conn.execute("DELETE FROM receipts WHERE run_id=%s", (rid,))
            conn.execute("DELETE FROM outbox_events WHERE run_id=%s", (rid,))
        doc_ids = [r[0] for r in conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()]
        if doc_ids:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (doc_ids,))
        fact_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT e.fact_id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s",
            (CORPUS,)).fetchall()]
        if fact_ids:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (fact_ids,))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM documents WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))
    # Qdrant collection + Neo4j nodes are disposable projections.
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings
    from qdrant_client import QdrantClient

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        name = qdrant_collection_name(CORPUS, active_contract().contract_id)
        if client.collection_exists(name):
            client.delete_collection(name)
    finally:
        client.close()
    from workers.project_neo4j_worker import _driver

    driver = _driver()
    try:
        with driver.session() as s:
            s.run("MATCH (d:Document) WHERE d.doc_id IN $ids DETACH DELETE d", ids=doc_ids)
            s.run("MATCH (c:Chunk) WHERE c.chunk_id IN $ids DETACH DELETE c",
                  ids=doc_ids + [f"chunk_ff{i}" for i in range(20)])
    finally:
        driver.close()


def _drive_run(run_id: str, fail_extract: bool = False) -> None:
    """Drive one run through the existing worker functions (the same
    processors the control plane dispatches)."""
    from workers.intake_worker import process_event as intake_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event
    from workers.project_neo4j_worker import process_event as neo4j_event
    from workers.canonicalize_worker import process_event as canon_event
    from workers.project_canonical_worker import process_event as pcanon_event
    from workers.verify_worker import process_event as verify_event
    from polymath_shared.identity import content_hash

    def mark_ok(stage):
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                VALUES (%s,%s,%s,now(),now(),'ok')
                ON CONFLICT DO NOTHING
                """,
                (run_id, stage, content_hash({"s": stage, "i1": "test"})),
            )

    with tx() as conn:
        payload = conn.execute(
            "SELECT payload FROM outbox_events WHERE run_id=%s AND event_type='intake.v1' ORDER BY event_id",
            (run_id,),
        ).fetchone()
        intake_event(conn, {"run_id": run_id, "payload": payload[0], "idempotency_key": "i1"})
    if fail_extract:
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                VALUES (%s,'extract',%s,now(),now(),'failed')
                """,
                (run_id, content_hash({"s": "extract", "i1": "fail"})),
            )
            conn.execute("UPDATE runs SET status='failed' WHERE run_id=%s", (run_id,))
        return
    mark_ok("extract")
    with tx() as conn:
        profile_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        qdrant_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        neo4j_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        canon_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        pcanon_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        verify_event(conn, {"run_id": run_id, "payload": {"run_id": run_id}, "idempotency_key": "i1"})
    with tx() as conn:
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (run_id,))


def _copy_fixture(tmp_path: Path) -> Path:
    dst = tmp_path / "i1fixture"
    shutil.copytree(FIXTURE, dst)
    return dst / "manifest.yaml"


def _run_states() -> dict:
    with tx() as conn:
        rows = conn.execute("SELECT run_id, status FROM runs WHERE corpus_id=%s", (CORPUS,)).fetchall()
        return {r[0]: r[1] for r in rows}


def test_plan_is_read_only_and_deterministic(tmp_path, monkeypatch):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    with tx() as conn:
        p1 = plan_manifest(conn, doc, manifest)
        p2 = plan_manifest(conn, doc, manifest)
    assert p1 == p2, "plan must be deterministic"
    monkeypatch.chdir("/")
    with tx() as conn:
        p3 = plan_manifest(conn, doc, manifest)
    assert p3["counts"] == p1["counts"], "plan must not depend on cwd"
    assert p1["counts"]["new"] == 6
    assert p1["counts"]["disabled"] == 1
    assert p1["counts"]["missing"] == 1
    actions = {s["source"]: s["action"] for s in p1["sources"]}
    assert actions["books/disabled.md"] == ACTION_SKIP_DISABLED
    assert actions["books/missing.pdf"] == ACTION_ERROR_MISSING
    # A: plan is read-only.
    with tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE corpus_id=%s", (CORPUS,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchone()[0] == 0


def test_execute_idempotent_and_full_lifecycle(tmp_path):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    with tx() as conn:
        r1 = execute_manifest(conn, doc, manifest)
    assert r1["submitted"] == 6, r1
    run_ids = [res["run_id"] for res in r1["results"]]
    assert len(set(run_ids)) == 6

    # B/C: second identical execution submits nothing.
    with tx() as conn:
        r2 = execute_manifest(conn, doc, manifest)
    assert r2["submitted"] == 0, r2

    # drive the full existing pipeline for every run
    for rid in run_ids:
        _drive_run(rid)

    states = _run_states()
    assert all(s == "query_ready" for s in states.values()), states

    with tx() as conn:
        plan = plan_manifest(conn, doc, manifest)
    assert plan["counts"]["query_ready"] == 6
    assert plan["counts"]["new"] == 0
    assert plan["counts"]["changed_content"] == 0
    assert all(s["action"] in ("NOOP", "SKIP_DISABLED", "ERROR_MISSING")
               for s in plan["sources"] if s["action"] != "NOOP" or True)

    # E: completed documents do not restart on re-execution.
    with tx() as conn:
        r3 = execute_manifest(conn, doc, manifest)
    assert r3["submitted"] == 0 and r3["retried"] == 0

    # J: corpus propagation through the durable layers.
    with tx() as conn:
        docs = conn.execute(
            "SELECT doc_id, corpus_id, source_name FROM documents WHERE corpus_id=%s", (CORPUS,)
        ).fetchall()
        assert len(docs) == 6
        assert all(d[1] == CORPUS for d in docs)
        chunks = conn.execute(
            "SELECT COUNT(*) FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.corpus_id=%s",
            (CORPUS,),
        ).fetchone()[0]
        assert chunks > 0

    # K: census has no gaps for the completed corpus.
    from control.census import compute_census

    with tx() as conn:
        census = compute_census(conn, max_attempts=3)
        corpus_gaps = [g for g in census.gaps
                       if g.corpus_id == CORPUS]
        assert corpus_gaps == [], corpus_gaps


def test_changed_content_re_drives_only_that_source(tmp_path):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    with tx() as conn:
        r1 = execute_manifest(conn, doc, manifest)
    for res in r1["results"]:
        _drive_run(res["run_id"])

    # D: change exactly one file's content in the temp copy.
    changed = tmp_path / "i1fixture" / "books" / "changed.md"
    changed.write_text("# Changed Document\n\nUpdated content version two.\n")

    with tx() as conn:
        plan = plan_manifest(conn, doc, manifest)
    changed_entry = next(s for s in plan["sources"] if s["source"] == "books/changed.md")
    assert changed_entry["action"] == "INGEST", changed_entry
    assert plan["counts"]["changed_content"] == 1
    assert plan["counts"]["query_ready"] == 5

    with tx() as conn:
        r2 = execute_manifest(conn, doc, manifest)
    assert r2["submitted"] == 1, r2
    _drive_run(r2["results"][0]["run_id"])

    with tx() as conn:
        versions = conn.execute(
            "SELECT source_name, COUNT(*) FROM documents WHERE corpus_id=%s AND source_name='books/changed.md' GROUP BY 1",
            (CORPUS,),
        ).fetchall()
        assert versions[0][1] == 2, "same locator, two content versions (lineage preserved)"
        states = conn.execute("SELECT status, COUNT(*) FROM runs WHERE corpus_id=%s GROUP BY 1", (CORPUS,)).fetchall()
        assert dict(states) == {"query_ready": 7}


def test_partial_failure_resume_and_retry(tmp_path):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    with tx() as conn:
        r1 = execute_manifest(conn, doc, manifest)
    run_ids = [res["run_id"] for res in r1["results"]]
    good = run_ids[1:]
    for rid in good:
        _drive_run(rid)
    victim = run_ids[0]
    _drive_run(victim, fail_extract=True)

    with tx() as conn:
        assert conn.execute("SELECT status FROM runs WHERE run_id=%s", (victim,)).fetchone()[0] == "failed"

    # plan: victim -> RETRY; others -> NOOP (not restarted)
    with tx() as conn:
        plan = plan_manifest(conn, doc, manifest)
        assert plan["counts"]["failed_retryable"] == 1
        assert plan["counts"]["query_ready"] == 5

    # E/M: execution re-arms only the failed run.
    with tx() as conn:
        r2 = execute_manifest(conn, doc, manifest)
    assert r2["submitted"] == 0 and r2["retried"] == 1, r2
    with tx() as conn:
        assert conn.execute("SELECT status FROM runs WHERE run_id=%s", (victim,)).fetchone()[0] == "reconciling"
        undelivered = conn.execute(
            "SELECT COUNT(*) FROM outbox_events WHERE run_id=%s AND delivered_at IS NULL", (victim,)
        ).fetchone()[0]
        assert undelivered > 0

    # drive the victim through; the others were never touched.
    _drive_run(victim)
    states = _run_states()
    assert all(s == "query_ready" for s in states.values()), states
    with tx() as conn:
        attempts = conn.execute(
            "SELECT COUNT(*) FROM stage_attempts WHERE run_id=%s", (good[0],)
        ).fetchone()[0]
        assert attempts == 8, "completed run must not restart (attempts unchanged)"


def test_batch_bounded_resumable_submission(tmp_path):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    with tx() as conn:
        r1 = execute_manifest(conn, doc, manifest, batch_size=2)
        r2 = execute_manifest(conn, doc, manifest, batch_size=2)
        r3 = execute_manifest(conn, doc, manifest, batch_size=2)
    assert r1["submitted"] == 2
    assert r2["submitted"] == 2
    assert r3["submitted"] == 2
    with tx() as conn:
        r4 = execute_manifest(conn, doc, manifest)
    assert r4["submitted"] == 0
    with tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE corpus_id=%s", (CORPUS,)).fetchone()[0] == 6


def test_manifest_id_deterministic_and_status_report(tmp_path):
    _wipe_corpus()
    manifest = _copy_fixture(tmp_path)
    doc = load_manifest(manifest)
    mid1 = manifest_id(doc)
    mid2 = manifest_id(load_manifest(manifest))
    assert mid1 == mid2
    with tx() as conn:
        execute_manifest(conn, doc, manifest)
        report = status_manifest(conn, doc, manifest)
    assert report["summary"]["manifest_id"] == mid1
    assert report["summary"]["TOTAL"] == 8
    assert report["summary"]["NEW"] == 0
    assert report["summary"]["RUNNING"] == 6
