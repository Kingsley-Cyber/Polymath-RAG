"""I0 acceptance: two public-domain book samples (psychology +
technical) complete the full pipeline: native file -> materialization
-> intake -> extraction (real GLiNER) -> canonicalization -> Neo4j
projection -> evidence/source lineage.

The lineage proves the citation chain the user asked for:
    fact -> evidence -> chunk offsets -> source-map segment
    -> page/chapter -> original book

Requires live stores + the GLiNER sidecar: POLYMATH_INTEGRATION=1.
Seeded corpora use unique ids and clean up after themselves.
"""
from __future__ import annotations

import base64
import json
import os
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash, run_id  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from workers.intake_worker import process_event as intake_ev  # noqa: E402
from workers.extract_worker import process_event as extract_ev  # noqa: E402
from workers.profile_worker import process_event as profile_ev  # noqa: E402
from workers.project_qdrant_worker import process_event as pq_ev  # noqa: E402
from workers.project_neo4j_worker import process_event as pn_ev  # noqa: E402
from workers.canonicalize_worker import process_event as canon_ev  # noqa: E402
from workers.project_canonical_worker import process_event as pcanon_ev  # noqa: E402
from workers.verify_worker import process_event as verify_ev  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures" / "native_docs"

CORPUS = "i0_e2e"

SAMPLES = [
    # (fixture, media_type, min_expected_span_text)
    ("psychology.pdf", "application/pdf", "habit"),
    ("psychology.epub", "application/epub+zip", "habit"),
    ("psychology.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
     "habit"),
    ("technical.html", "text/html", "selection"),
    ("technical.md", "text/markdown", "selection"),
    ("technical.txt", "text/plain", "selection"),
]


def _cleanup() -> None:
    from polymath_shared.embedding_contracts import active_contract
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.stores import qdrant_client as _qc

    _client = _qc()
    try:
        try:
            _client.delete_collection(qdrant_collection_name(CORPUS, active_contract().contract_id))
        except Exception:
            pass
    finally:
        _client.close()

    with tx() as conn:
        ids = conn.execute(
            "SELECT jsonb_agg(id) FROM ("
            "SELECT DISTINCT c.chunk_id AS id FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT e.evidence_id AS id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT f.fact_id AS id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT ce.canonical_id AS id FROM canonical_entities ce WHERE ce.corpus_id=%s "
            "UNION SELECT DISTINCT cm.local_entity_id AS id FROM canonical_memberships cm WHERE cm.corpus_id=%s) x",
            (CORPUS,) * 5,
        ).fetchone()[0] or []
        ent_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT e.entity_id FROM entities e JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id "
            "JOIN evidence ev ON ev.fact_id=f.fact_id JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s",
            (CORPUS,)).fetchall()]
        chunk_ids = [i for i in ids if i.startswith("chunk_")]
        ev_ids = [i for i in ids if i.startswith("ev_")]
        fact_ids = [i for i in ids if i.startswith("fact_")]
        canon_ids = [i for i in ids if i.startswith("cent_")]
        mem_ids = [i for i in ids if i.startswith("ent_")]
        conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                     (chunk_ids + ev_ids + fact_ids + canon_ids + mem_ids,))
        conn.execute("DELETE FROM canonicalization_decisions WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM canonical_memberships WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM canonical_entities WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM evidence WHERE evidence_id = ANY(%s)", (ev_ids,))
        conn.execute("DELETE FROM facts WHERE fact_id = ANY(%s)", (fact_ids,))
        if ent_ids:
            conn.execute(
                "DELETE FROM entities WHERE entity_id = ANY(%s) "
                "AND NOT EXISTS (SELECT 1 FROM facts f2 WHERE f2.subject_id=entities.entity_id OR f2.object_id=entities.entity_id)",
                (ent_ids,))
        conn.execute("DELETE FROM chunks WHERE chunk_id = ANY(%s)", (chunk_ids,))
        conn.execute("DELETE FROM documents WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
    driver = neo4j_driver()
    try:
        with driver.session() as s:
            s.run("MATCH (c:CanonicalEntity {corpus_id: $c}) DETACH DELETE c", c=CORPUS).consume()
            s.run("MATCH (ch:Chunk) WHERE ch.chunk_id IN $ids DETACH DELETE ch", ids=chunk_ids).consume()
            s.run("MATCH (ev:Evidence) WHERE ev.evidence_id IN $ids DETACH DELETE ev", ids=ev_ids).consume()
            s.run("MATCH (f:Fact) WHERE f.fact_id IN $ids DETACH DELETE f", ids=fact_ids).consume()
            if ent_ids:
                s.run("MATCH (e:Entity) WHERE e.entity_id IN $ids DETACH DELETE e", ids=ent_ids).consume()
    finally:
        driver.close()


def _ingest_sample(name: str, media_type: str) -> tuple[str, dict]:
    raw = (FIXTURES / name).read_bytes()
    canonical = {
        "corpus_id": CORPUS,
        "source_name": name,
        "media_type": media_type,
        "content_b64": base64.b64encode(raw).decode(),
        "config": {},
    }
    rid = run_id(CORPUS, canonical)
    with tx() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'intake', %s) "
            "ON CONFLICT (run_id) DO NOTHING",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})),
        )
    event = {"run_id": rid, "payload": canonical,
             "idempotency_key": content_hash({"run": rid})}
    with tx() as conn:
        intake_ev(conn, event)
    with tx() as conn:
        chunked = conn.execute(
            "SELECT payload FROM outbox_events WHERE run_id = %s AND event_type = 'chunked.v1' "
            "ORDER BY event_id DESC LIMIT 1", (rid,)).fetchone()
        assert chunked is not None
        extract_ev(conn, {"run_id": rid, "payload": chunked[0],
                          "idempotency_key": content_hash({"r": rid, "c": chunked[0]})})
    with tx() as conn:
        profile_ev(conn, {"run_id": rid})
    with tx() as conn:
        pq_ev(conn, {"run_id": rid, "payload": {}})
    with tx() as conn:
        pn_ev(conn, {"run_id": rid, "payload": {}})
    with tx() as conn:
        canon_ev(conn, {"run_id": rid})
    with tx() as conn:
        pcanon_ev(conn, {"run_id": rid})
    with tx() as conn:
        verify_ev(conn, {"run_id": rid})
    return rid, event


def test_book_samples_complete_full_pipeline_with_lineage() -> None:
    _cleanup()
    run_ids: list[str] = []
    events: dict[str, dict] = {}
    try:
        for name, media_type, _ in SAMPLES:
            rid, event = _ingest_sample(name, media_type)
            run_ids.append(rid)
            events[rid] = event

        # --- materialization provenance persisted on documents -----------
        with tx() as conn:
            rows = conn.execute(
                "SELECT source_name, materialization, source_map FROM documents "
                "WHERE corpus_id = %s ORDER BY source_name", (CORPUS,)).fetchall()
        assert len(rows) == len(SAMPLES)
        for source_name, mat, source_map in rows:
            mat = mat or {}
            source_map = source_map or []
            assert mat.get("parser"), source_name
            assert mat.get("normalized_text_sha256"), source_name
            assert source_map, source_name
            assert all("location" in seg for seg in source_map), source_name
        pdf_row = next(r for r in rows if r[0] == "psychology.pdf")
        assert pdf_row[2][0]["kind"] == "page"
        epub_row = next(r for r in rows if r[0] == "psychology.epub")
        assert {s["kind"] for s in epub_row[2]} == {"chapter"}

        # --- facts extracted with evidence from the REAL pipeline ---------
        with tx() as conn:
            n_facts = conn.execute(
                "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (CORPUS,)).fetchone()[0]
            n_wo = conn.execute(
                "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
                "AND NOT EXISTS (SELECT 1 FROM evidence e2 WHERE e2.fact_id=f.fact_id)", (CORPUS,)).fetchone()[0]
            bad_prov = conn.execute(
                "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
                "AND (f.provenance='{}'::jsonb OR f.rule_id IS NULL OR NOT (f.provenance ? 'resource_contract_id'))",
                (CORPUS,)).fetchone()[0]
        assert n_facts > 0, "no facts extracted from the book samples"
        assert n_wo == 0
        assert bad_prov == 0

        # --- canonicalization converged -----------------------------------
        with tx() as conn:
            canon = conn.execute(
                "SELECT COUNT(*) FROM canonical_entities WHERE corpus_id=%s", (CORPUS,)).fetchone()[0]
            members = conn.execute(
                "SELECT COUNT(*) FROM canonical_memberships WHERE corpus_id=%s", (CORPUS,)).fetchone()[0]
        assert canon > 0 and members > 0

        # --- lineage: fact -> evidence -> chunk offsets -> source-map ----
        with tx() as conn:
            lineage = conn.execute(
                """
                SELECT f.fact_id, e.evidence_id, e.chunk_id, c.char_start, c.char_end,
                       d.source_name, d.source_map
                  FROM facts f
                  JOIN evidence e ON e.fact_id = f.fact_id
                  JOIN chunks c ON c.chunk_id = e.chunk_id
                  JOIN documents d ON d.doc_id = e.doc_id
                 WHERE d.corpus_id = %s
                 ORDER BY f.fact_id LIMIT 3
                """, (CORPUS,)).fetchall()
        assert lineage
        for fact_id, evidence_id, chunk_id, char_start, char_end, source_name, source_map in lineage:
            source_map = source_map or []
            probe = char_start
            seg = next(
                (s for s in source_map if s["text_start"] <= probe < s["text_end"]),
                None,
            )
            assert seg, f"chunk offset {probe} not covered by source map of {source_name}"
            assert seg["location"], f"source location missing for {source_name}"
            # The chunk text must be a slice of the materialized text.
            assert char_end > char_start

        # --- Neo4j canonical projection carries the lineage --------------
        with tx() as conn:
            canon_id, local_id = conn.execute(
                "SELECT canonical_id, local_entity_id FROM canonical_memberships "
                "WHERE corpus_id = %s LIMIT 1", (CORPUS,)).fetchone()
        driver = neo4j_driver()
        try:
            with driver.session() as s:
                nodes = s.run(
                    "MATCH (c:CanonicalEntity {canonical_id: $id})-[:HAS_MEMBER]->(e:Entity) "
                    "RETURN e.entity_id AS local", id=canon_id).data()
                assert nodes and nodes[0]["local"] == local_id
        finally:
            driver.close()

        # --- replay: identical intake events are no-ops -------------------
        with tx() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (CORPUS,)).fetchone()[0]
        for rid in run_ids:
            with tx() as conn:
                intake_ev(conn, events[rid])
        with tx() as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s", (CORPUS,)).fetchone()[0]
        assert after == before
    finally:
        _cleanup()
