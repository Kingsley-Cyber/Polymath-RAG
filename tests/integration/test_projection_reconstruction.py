"""Phase F acceptance gate (PLAN): projections are disposable, Postgres
is truth. Requires live stores: run `make db-up` and
`POLYMATH_INTEGRATION=1 pytest tests/integration -q`.

The seven gates:

1. Delete the entire Qdrant collection -> census reconstructs it exactly.
2. Delete the entire Neo4j database -> census reconstructs it exactly.
3. Kill the projector halfway through -> rerun converges without
   duplicates.
4. Replay the same corpus -> zero new semantic facts, zero duplicate
   points.
5. Change the projection contract -> new projection version, source
   facts unchanged.
6. Inject one missing Qdrant point + one missing Neo4j edge -> census
   detects exactly two discrepancies.
7. Inject an extra/orphan projection -> verifier detects it, never
   silently accepts.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLYMATH_INTEGRATION") != "1",
        reason="set POLYMATH_INTEGRATION=1 with live stores (make db-up)",
    ),
]

import psycopg  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

sys_path = str(Path(__file__).resolve().parents[2])
import sys  # noqa: E402

if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash, run_id  # noqa: E402
from polymath_shared.embedding_contracts import active_contract  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402
from workers.project_neo4j_worker import _driver as _neo4j_driver  # noqa: E402
from workers.verify_worker import process_event as verify_event  # noqa: E402
from control.census import compute_census  # noqa: E402
from control.scheduler import schedule_gaps  # noqa: E402

TEXT = (
    "Sarah created the Polaris toolkit in 2020. "
    "Polaris was created by Sarah. "
    "The toolkit uses a transformer encoder. "
    "Polaris runs on the M3 chip. "
    "The chip is a component of the laptop. "
    "Sarah is the CTO of Polaris. "
    "The laptop depends on the chip."
)


def _event(run: str, payload: dict) -> dict:
    return {"run_id": run, "payload": payload, "idempotency_key": "test"}


def _make_run(corpus_id: str, text: str | None = None) -> str:
    """Insert run + intake outbox event exactly as the orchestrator does.

    Each corpus gets a content variant (the corpus id appended) so the
    content-hashed document identity is unique per test."""
    text = text or (TEXT + f" Corpus marker: {corpus_id}.")
    canonical = {
        "corpus_id": corpus_id,
        "source_name": f"{corpus_id}.txt",
        "media_type": "text/plain",
        "content_b64": base64.b64encode(text.encode()).decode(),
        "config": {},
    }
    rid = run_id(corpus_id, canonical)
    with tx() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s)",
            (rid, corpus_id, json.dumps({"intake_payload": canonical})),
        )
        conn.execute(
            """
            INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
            VALUES (%s, 'intake.v1', %s, %s)
            """,
            (rid, json.dumps(canonical), content_hash({"run": rid, "intake": corpus_id})),
        )
    return rid


def _run_intake(run: str) -> None:
    """Drive the intake stage with the run's own canonical intake payload
    (the same payload the control plane re-arms from)."""
    from workers.intake_worker import process_event as intake_event

    with tx() as conn:
        payload = conn.execute(
            "SELECT metadata->'intake_payload' FROM runs WHERE run_id = %s", (run,)
        ).fetchone()[0]
        intake_event(conn, _event(run, payload))


def _corpus_of(run: str) -> str:
    with tx() as conn:
        return conn.execute("SELECT corpus_id FROM runs WHERE run_id = %s", (run,)).fetchone()[0]


def _seed_facts(run: str) -> None:
    """Seed the run's facts through the REAL compiler path (gold inputs,
    no GLiNER needed): entities + facts + evidence rows, exactly as the
    extract stage writes them."""
    from polymath_shared.contracts import (
        CoreType,
        EntityCandidate,
        EntitySpan,
        EvidenceSpan,
        RelationCandidate,
        ScopeFlags,
    )
    from polymath_shared.rulepack import compile_relation, load_rule_pack
    from polymath_shared.rulepack.compiler import canonical_entity_id
    from polymath_shared.identity import evidence_id

    pack = load_rule_pack()
    triples = [
        ("Sarah", "Person", "Polaris", "Organization", "founded", "creation", "found"),
        ("Polaris", "Organization", "M3 chip", "Technology", "runs on", "usage_application", "run"),
        ("chip", "Technology", "laptop", "Technology", "component of", "composition", "component"),
        ("Sarah", "Person", "Polaris", "Organization", "CEO of", "leadership_governance", "serve"),
        ("laptop", "Technology", "chip", "Technology", "depends on", "dependency", "depend"),
    ]
    with tx() as conn:
        doc_id = conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id = %s LIMIT 1", (_corpus_of(run),)
        ).fetchone()[0]
        chunk = conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = %s AND tier = 'child' ORDER BY chunk_index LIMIT 1",
            (doc_id,),
        ).fetchone()[0]

        for subj, subj_type, obj, obj_type, ev_text, ev_class, lemma in triples:
            subject_span = EntitySpan(
                doc_id=doc_id, chunk_id=chunk, start=0, end=len(subj),
                text=subj, core_type=CoreType(subj_type), score=0.9, extractor_version="test",
            )
            object_span = EntitySpan(
                doc_id=doc_id, chunk_id=chunk, start=0, end=len(obj),
                text=obj, core_type=CoreType(obj_type), score=0.9, extractor_version="test",
            )
            evidence = EvidenceSpan(
                chunk_id=chunk, start=0, end=len(ev_text), text=ev_text,
                evidence_class=ev_class, trigger_lemma=lemma, score=1.0, extractor_version="test",
            )
            candidate = RelationCandidate(
                evidence=evidence,
                subject=EntityCandidate(span=subject_span, resolved_entity_id=canonical_entity_id(subject_span.core_type, subj)),
                object=EntityCandidate(span=object_span, resolved_entity_id=canonical_entity_id(object_span.core_type, obj)),
                scope=ScopeFlags(),
                ontology_profile="core",
            )
            decision = compile_relation(candidate, None, pack)
            assert decision.fact is not None, f"{subj} {ev_text} {obj}: {decision.reason}"
            fact = decision.fact
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (fact.subject_id, subj_type, subj),
            )
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (fact.object_id, obj_type, obj),
            )
            conn.execute(
                """
                INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                                   decision, rule_id, rule_version, provenance)
                VALUES (%s,%s,%s,%s,%s,'ACCEPT',%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                (fact.fact_id, fact.predicate, fact.subject_id, fact.object_id,
                 json.dumps(fact.qualifiers), fact.rule_id, fact.rule_version, json.dumps(fact.provenance)),
            )
            ev_id = evidence_id(fact.fact_id, doc_id, chunk, {"t": "test"}, fact.rule_id)
            conn.execute(
                """
                INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                                      rule_id, gliner_scores, extractor_version, rule_version)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                (ev_id, fact.fact_id, doc_id, chunk, json.dumps({"t": "test"}),
                 fact.rule_id, json.dumps({}), "test", fact.rule_version),
            )


def _mark_stage_ok(run: str, stage: str) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
            VALUES (%s, %s, %s, now(), now(), 'ok')
            ON CONFLICT (run_id, stage, contract_hash) DO NOTHING
            """,
            (run, stage, content_hash({"stage": stage, "test": "integration"})),
        )
        conn.execute(
            """
            INSERT INTO receipts (receipt_id, run_id, stage, contract_hash, status)
            VALUES (%s, %s, %s, %s, 'committed')
            ON CONFLICT (run_id, stage, contract_hash) DO NOTHING
            """,
            (content_hash({"r": run, "s": stage}), run, stage, content_hash({"stage": stage, "test": "integration"})),
        )


def _mark_query_ready(run: str) -> None:
    with tx() as conn:
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (run,))


def _project_all(run: str) -> None:
    _run_intake(run)
    _seed_facts(run)
    _mark_stage_ok(run, "extract")
    _mark_stage_ok(run, "profile_document")
    from polymath_shared.db import tx as _tx

    with _tx() as conn:
        from workers.project_qdrant_worker import process_event as _q
        _q(conn, _event(run, {"run_id": run}))
    with _tx() as conn:
        from workers.project_neo4j_worker import process_event as _n
        _n(conn, _event(run, {"run_id": run}))
    _mark_query_ready(run)


def _qdrant_point_ids(run: str) -> set[str]:
    """Source chunk ids present in the run's collection (via payloads)."""
    settings = get_settings()
    corpus = _corpus_of(run)
    collection = qdrant_collection_name(corpus, active_contract().contract_id)
    client = QdrantClient(url=settings.stores.qdrant_url)
    try:
        points, _ = client.scroll(collection_name=collection, limit=100_000, with_vectors=False)
        return {str(p.payload.get("chunk_id")) for p in points if p.payload}
    finally:
        client.close()


def _neo4j_chunk_ids(run: str) -> set[str]:
    """The run's chunks that exist as nodes in Neo4j."""
    with tx() as conn:
        desired = {
            r[0] for r in conn.execute(
                """
                SELECT c.chunk_id FROM chunks c
                  JOIN documents d ON d.doc_id = c.doc_id
                  JOIN runs r2 ON r2.corpus_id = d.corpus_id
                 WHERE r2.run_id = %s
                """,
                (run,),
            ).fetchall()
        }
    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            present = {r["id"] for r in session.run("MATCH (c:Chunk) RETURN c.chunk_id AS id")}
    finally:
        driver.close()
    return desired & present


def _reset_stores(run: str) -> None:
    settings = get_settings()
    corpus = _corpus_of(run)
    collection = qdrant_collection_name(corpus, active_contract().contract_id)
    client = QdrantClient(url=settings.stores.qdrant_url)
    try:
        try:
            client.delete_collection(collection)
        except Exception:
            pass
    finally:
        client.close()
    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    finally:
        driver.close()
    with tx() as conn:
        conn.execute(
            "DELETE FROM projection_receipts WHERE entity_id IN (SELECT chunk_id FROM chunks c JOIN documents d ON d.doc_id=c.doc_id JOIN runs r ON r.corpus_id=d.corpus_id WHERE r.run_id=%s)",
            (run,),
        )


def _new_corpus(name: str) -> str:
    _wipe_corpus(name)
    _reset_stores_by_corpus(name)
    return _make_run(name)


def _wipe_corpus(corpus: str) -> None:
    """Remove all state for one corpus so the suite is re-runnable."""
    with tx() as conn:
        doc_ids = [
            r[0] for r in conn.execute(
                "SELECT doc_id FROM documents WHERE corpus_id = %s", (corpus,)
            ).fetchall()
        ]
        fact_ids = [
            r[0] for r in conn.execute(
                """
                SELECT e.fact_id FROM evidence e
                  JOIN documents d ON d.doc_id = e.doc_id
                 WHERE d.corpus_id = %s
                """,
                (corpus,),
            ).fetchall()
        ]
        if doc_ids:
            conn.execute(
                "DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (doc_ids,)
            )
        if fact_ids:
            conn.execute(
                "DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (fact_ids,)
            )
        conn.execute(
            "DELETE FROM runs WHERE corpus_id = %s", (corpus,)
        )
        conn.execute(
            "DELETE FROM documents WHERE corpus_id = %s", (corpus,)
        )
        conn.execute(
            "DELETE FROM corpora WHERE corpus_id = %s", (corpus,)
        )


def _reset_stores_by_corpus(corpus: str) -> None:
    settings = get_settings()
    collection = qdrant_collection_name(corpus, active_contract().contract_id)
    client = QdrantClient(url=settings.stores.qdrant_url)
    try:
        try:
            client.delete_collection(collection)
        except Exception:
            pass
    finally:
        client.close()


class TestReconstruction:
    def test_delete_qdrant_collection_reconstructs_exactly(self) -> None:
        run = _new_corpus("gate1")
        _project_all(run)
        before = _qdrant_point_ids(run)
        assert before

        settings = get_settings()
        collection = qdrant_collection_name(_corpus_of(run), active_contract().contract_id)
        client = QdrantClient(url=settings.stores.qdrant_url)
        client.delete_collection(collection)
        client.close()

        # Verify detects store loss -> clears receipts; census re-arms the
        # projector; re-running reconstructs the exact same point set.
        with tx() as conn:
            verify_event(conn, _event(run, {"run_id": run}))
        census = compute_census(_get_conn(), max_attempts=3)
        assert any(g.stage == "project_qdrant" for g in census.gaps)
        with tx() as conn:
            schedule_gaps(conn, census)
        with tx() as conn:
            from workers.project_qdrant_worker import process_event as _q
            _q(conn, _event(run, {"run_id": run}))
        with tx() as conn:
            verify_event(conn, _event(run, {"run_id": run}))

        after = _qdrant_point_ids(run)
        assert after == before

    def test_delete_neo4j_reconstructs_exactly(self) -> None:
        run = _new_corpus("gate2")
        _project_all(run)
        before = _neo4j_chunk_ids(run)
        assert before

        driver = _neo4j_driver()
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()

        with tx() as conn:
            verify_event(conn, _event(run, {"run_id": run}))
        census = compute_census(_get_conn(), max_attempts=3)
        assert any(g.stage == "project_neo4j" for g in census.gaps)
        with tx() as conn:
            schedule_gaps(conn, census)
        with tx() as conn:
            from workers.project_neo4j_worker import process_event as _n
            _n(conn, _event(run, {"run_id": run}))
        with tx() as conn:
            verify_event(conn, _event(run, {"run_id": run}))

        after = _neo4j_chunk_ids(run)
        assert after == before

    def test_crash_midway_converges_without_duplicates(self, monkeypatch) -> None:
        run = _new_corpus("gate3")
        _run_intake(run)
        _seed_facts(run)
        _mark_stage_ok(run, "extract")

        monkeypatch.setenv("POLYMATH_TEST_CRASH_AFTER_POINTS", "1")
        from polymath_shared.receipts import StageFailed

        with tx() as conn:
            with pytest.raises(StageFailed):
                from workers.project_qdrant_worker import process_event as _q
                _q(conn, _event(run, {"run_id": run}))
        monkeypatch.delenv("POLYMATH_TEST_CRASH_AFTER_POINTS")

        census = compute_census(_get_conn(), max_attempts=3)
        assert any(g.stage == "project_qdrant" for g in census.gaps)
        with tx() as conn:
            schedule_gaps(conn, census)
        with tx() as conn:
            from workers.project_qdrant_worker import process_event as _q
            _q(conn, _event(run, {"run_id": run}))

        chunk_count = _chunk_count(run)
        assert len(_qdrant_point_ids(run)) == chunk_count

    def test_replay_same_corpus_adds_nothing(self) -> None:
        run = _new_corpus("gate4")
        _project_all(run)
        points_before = _qdrant_point_ids(run)
        facts_before = _fact_count()

        with tx() as conn:
            from workers.project_qdrant_worker import process_event as _q
            _q(conn, _event(run, {"run_id": run}))
            from workers.project_neo4j_worker import process_event as _n
            _n(conn, _event(run, {"run_id": run}))

        assert _qdrant_point_ids(run) == points_before
        assert _fact_count() == facts_before

    def test_contract_bump_creates_new_version_keeps_facts(self, monkeypatch) -> None:
        run = _new_corpus("gate5")
        _project_all(run)
        from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, SHORT_NAMES
        from dataclasses import replace

        old_collection = qdrant_collection_name(_corpus_of(run), active_contract().contract_id)
        facts_before = _fact_count()

        bumped = replace(HASH_EMBED_CONTRACT, contract_version="2")
        monkeypatch.setitem(SHORT_NAMES, "hash-embed-v1", bumped)
        monkeypatch.setattr(
            "polymath_shared.embedding_contracts.CONTRACTS",
            {**__import__("polymath_shared.embedding_contracts", fromlist=["CONTRACTS"]).CONTRACTS,
             bumped.contract_id: bumped},
        )
        with tx() as conn:
            from workers.project_qdrant_worker import process_event as _q
            _q(conn, _event(run, {"run_id": run}))

        new_collection = qdrant_collection_name(_corpus_of(run), bumped.contract_id)
        settings = get_settings()
        client = QdrantClient(url=settings.stores.qdrant_url)
        try:
            assert client.collection_exists(old_collection)
            assert client.collection_exists(new_collection)
        finally:
            client.close()
        assert _fact_count() == facts_before

    def test_injected_missing_detects_exactly_two(self) -> None:
        run = _new_corpus("gate6")
        _project_all(run)

        settings = get_settings()
        collection = qdrant_collection_name(_corpus_of(run), active_contract().contract_id)
        from polymath_shared import projection_contracts as pc

        client = QdrantClient(url=settings.stores.qdrant_url)
        victim_point = sorted(_qdrant_point_ids(run))[0]
        victim_uuid = pc.qdrant_point_uuid(victim_point)
        client.delete(collection_name=collection, points_selector=[victim_uuid])
        client.close()

        driver = _neo4j_driver()
        with driver.session() as session:
            victim_edge = session.run(
                "MATCH ()-[r:REL]->() RETURN r.fact_id AS id LIMIT 1"
            ).single()
            if victim_edge:
                session.run(
                    "MATCH ()-[r:REL {fact_id: $id}]->() DELETE r", id=victim_edge["id"]
                )
        driver.close()

        with tx() as conn:
            verify_event(conn, _event(run, {"run_id": run}))

        census = compute_census(_get_conn(), max_attempts=3)
        detected = {
            (g.stage, g.event_type)
            for g in census.gaps
            if g.run_id == run and g.stage in ("project_qdrant", "project_neo4j")
        }
        assert detected == {
            ("project_qdrant", "project_qdrant.v1"),
            ("project_neo4j", "project_neo4j.v1"),
        }

    def test_orphan_projection_detected_and_removed(self) -> None:
        run = _new_corpus("gate7")
        _project_all(run)

        settings = get_settings()
        collection = qdrant_collection_name(_corpus_of(run), active_contract().contract_id)
        from polymath_shared import projection_contracts as pc

        client = QdrantClient(url=settings.stores.qdrant_url)
        client.upsert(
            collection_name=collection,
            points=[{"id": pc.qdrant_point_uuid("orphan_chunk_id"),
                     "vector": [0.0] * 512,
                     "payload": {"chunk_id": "orphan_chunk_id"}}],
        )
        client.close()

        with tx() as conn:
            conn.execute(
                """
                INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active)
                VALUES ('qdrant', 'chunk', 'orphan_chunk_id', 'deadbeef', TRUE)
                ON CONFLICT (projection, entity_kind, entity_id)
                DO UPDATE SET active = TRUE
                """
            )
            verify_event(conn, _event(run, {"run_id": run}))

        assert "orphan_chunk_id" not in _qdrant_point_ids(run)
        with tx() as conn:
            claim = conn.execute(
                "SELECT active FROM projection_receipts WHERE entity_id = 'orphan_chunk_id'"
            ).fetchone()
            # The claim is superseded (active=false); the immutable attempt
            # history remains — verification never erases the trail.
            assert claim is not None and claim[0] is False
        census = compute_census(_get_conn(), max_attempts=3)
        assert [g for g in census.gaps if g.run_id == run] == []


def _chunk_count(run: str) -> int:
    with tx() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM chunks c
              JOIN documents d ON d.doc_id = c.doc_id
              JOIN runs r ON r.corpus_id = d.corpus_id
             WHERE r.run_id = %s
            """,
            (run,),
        ).fetchone()[0]


def _fact_count() -> int:
    with tx() as conn:
        return conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]


def _get_conn():
    import contextlib

    conn = psycopg.connect(get_settings().postgres.dsn, autocommit=True)
    return _AutocommitWrapper(conn)


class _AutocommitWrapper:
    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)
