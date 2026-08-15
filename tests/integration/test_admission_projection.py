"""Entity admission projection gate (E2/C1.1): reference-class boundary
holds through the real projection path.

Seeds one corpus through the REAL production allocation path
(build_candidates -> compile_relation) with four admission classes:

  GLOBAL          AcmeCorp
  CORPUS_SCOPED   the vector index (same id across two sentences)
  DOCUMENT_SCOPED our engine
  MENTION_ONLY    the system

Gates:
1. GLOBAL / CORPUS_SCOPED / DOCUMENT_SCOPED entities project as Neo4j
   Entity nodes; MENTION_ONLY never does.
2. Facts whose endpoints are all admitted project as REL edges; facts
   touching a MENTION_ONLY endpoint stay parked (Postgres-only).
3. Re-projecting is deterministic (same node/edge multiset, no dupes).

Requires live stores: make db-up; POLYMATH_INTEGRATION=1.
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

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash, run_id, evidence_id  # noqa: E402
from polymath_shared.entity_admission import decide  # noqa: E402

TEXT = (
    "AcmeCorp runs on the vector index. "
    "The vector index depends on our engine. "
    "Our engine is a component of the system. "
    "Corpus marker: admission-projection."
)


def _event(run: str, payload: dict) -> dict:
    return {"run_id": run, "payload": payload, "idempotency_key": "test"}


def _make_run(corpus_id: str) -> str:
    text = TEXT + f" {corpus_id}."
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
    from workers.intake_worker import process_event as intake_event

    with tx() as conn:
        payload = conn.execute(
            "SELECT metadata->'intake_payload' FROM runs WHERE run_id = %s", (run,)
        ).fetchone()[0]
        intake_event(conn, _event(run, payload))


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


def _seed_through_admission(run: str) -> dict:
    """Seed facts through the REAL production identity boundary:
    build_candidates (admission allocation) -> compile_relation."""
    from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan
    from polymath_shared.rulepack import compile_relation, load_rule_pack
    from workers.candidates import SentenceSlice, build_candidates

    pack = load_rule_pack()
    corpus_id = None
    with tx() as conn:
        corpus_id = conn.execute("SELECT corpus_id FROM runs WHERE run_id=%s", (run,)).fetchone()[0]
        doc_id = conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id = %s LIMIT 1", (corpus_id,)
        ).fetchone()[0]
        chunk = conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = %s AND tier = 'child' ORDER BY chunk_index LIMIT 1",
            (doc_id,),
        ).fetchone()[0]

    def span(surface, ctype, start):
        return EntitySpan(doc_id=doc_id, chunk_id=chunk, start=start, end=start + len(surface),
                          text=surface, core_type=CoreType(ctype), score=0.9, extractor_version="test")

    sentences = [
        ("AcmeCorp runs on the vector index.", [
            span("AcmeCorp", "Organization", 0),
            span("the vector index", "Technology", 17),
        ], EvidenceSpan(chunk_id=chunk, start=9, end=13, text="runs on",
                        evidence_class="usage_application", trigger_lemma="run",
                        score=0.9, extractor_version="test")),
        ("The vector index depends on our engine.", [
            span("the vector index", "Technology", 0),
            span("our engine", "Technology", 25),
        ], EvidenceSpan(chunk_id=chunk, start=17, end=23, text="depends on",
                        evidence_class="dependency", trigger_lemma="depend",
                        score=0.9, extractor_version="test")),
        ("Our engine is a component of the system.", [
            span("our engine", "Technology", 0),
            span("the system", "Technology", 31),
        ], EvidenceSpan(chunk_id=chunk, start=15, end=27, text="component of",
                        evidence_class="composition", trigger_lemma="component",
                        score=0.9, extractor_version="test")),
    ]

    stored = {"facts": [], "entities": {}}
    with tx() as conn:
        for text, entities, evidence in sentences:
            sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                               entities=entities, evidence=[evidence], parse=None)
            cands = build_candidates([sl], doc_id=doc_id, corpus_id=corpus_id,
                                     ontology_profile="core", extractor_version="test",
                                     rule_pack=pack, enrich=False)
            assert cands, f"no candidates for {text!r}"
            for cand in cands:
                decision = compile_relation(cand, None, pack)
                if decision.fact is None:
                    continue
                fact = decision.fact
                for eid, span in ((fact.subject_id, cand.subject.span),
                                  (fact.object_id, cand.object.span)):
                    admission = decide(span.text, span.core_type.value, span.score)
                    conn.execute(
                        "INSERT INTO entities (entity_id, core_type, normalized_surface, admission_class) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT (entity_id) DO NOTHING",
                        (eid, span.core_type.value, span.text, admission.reference_class),
                    )
                    stored["entities"][span.text] = (eid, admission.reference_class)
                conn.execute(
                    """
                    INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                                       decision, rule_id, rule_version, provenance)
                    VALUES (%s,%s,%s,%s,%s,'ACCEPT',%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    """,
                    (fact.fact_id, fact.predicate, fact.subject_id, fact.object_id,
                     json.dumps(fact.qualifiers), fact.rule_id, fact.rule_version,
                     json.dumps(fact.provenance)),
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
                stored["facts"].append(fact)
    return stored


def _project_neo4j(run: str) -> None:
    from workers.project_neo4j_worker import process_event as _n

    with tx() as conn:
        _n(conn, _event(run, {"run_id": run}))


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
        conn.execute("DELETE FROM runs WHERE corpus_id = %s", (corpus,))
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (corpus,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (corpus,))


def _reset_stores_by_corpus(corpus: str) -> None:
    from workers.project_neo4j_worker import _driver as _neo4j_driver

    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    finally:
        driver.close()


def _new_corpus(name: str) -> str:
    _wipe_corpus(name)
    _reset_stores_by_corpus(name)
    return _make_run(name)


def _graph_state(run: str) -> dict:
    from workers.project_neo4j_worker import _driver as _neo4j_driver

    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            nodes = session.run(
                "MATCH (e:Entity) WHERE e.entity_id IS NOT NULL RETURN e.entity_id AS eid, e.surface AS s ORDER BY eid"
            ).data()
            edges = session.run(
                "MATCH (s:Entity)-[r:REL]->(o:Entity) RETURN r.fact_id AS fid, "
                "s.entity_id AS sid, o.entity_id AS oid, r.predicate AS p ORDER BY fid"
            ).data()
    finally:
        driver.close()
    return {"nodes": nodes, "edges": edges}


def test_admission_projection_gate():
    corpus = "admission-projection-gate"
    run = _new_corpus(corpus)
    _run_intake(run)
    stored = _seed_through_admission(run)
    _mark_stage_ok(run, "extract")
    _mark_stage_ok(run, "profile_document")
    _project_neo4j(run)

    assert stored["facts"], "seeded facts missing"
    mention_ids = {
        eid for _, (eid, cls) in stored["entities"].items()
        if cls == "MENTION_ONLY"
    }
    admitted_ids = {
        eid for _, (eid, cls) in stored["entities"].items()
        if cls != "MENTION_ONLY"
    }
    assert mention_ids, "expected at least one MENTION_ONLY entity"
    for eid in mention_ids:
        assert eid.startswith("mention_")

    state = _graph_state(run)
    node_ids = {n["eid"] for n in state["nodes"]}
    edge_ids = {e["fid"] for e in state["edges"]}

    # Gate 1: MENTION_ONLY never projects; admitted classes do.
    assert not (node_ids & mention_ids), f"mention entities leaked into the graph: {node_ids & mention_ids}"
    assert admitted_ids <= node_ids, f"admitted entities missing: {admitted_ids - node_ids}"

    # Gate 2: facts touching MENTION_ONLY are parked (Postgres-only).
    with tx() as conn:
        pg_fact_ids = {r[0] for r in conn.execute("SELECT fact_id FROM facts").fetchall()}
    parked = [f for f in stored["facts"] if f.subject_id in mention_ids or f.object_id in mention_ids]
    assert parked, "expected at least one parked fact"
    assert all(f.fact_id in pg_fact_ids for f in parked), "parked fact lost from authority"
    assert not ({f.fact_id for f in parked} & edge_ids), "parked fact projected as an edge"
    promoted = [f for f in stored["facts"] if f.subject_id not in mention_ids and f.object_id not in mention_ids]
    assert {f.fact_id for f in promoted} <= edge_ids, "admitted fact missing from graph"

    # Gate 3: re-projection is deterministic.
    _project_neo4j(run)
    state2 = _graph_state(run)
    assert state == state2, "re-projection changed the graph"


def test_admission_seed_classes_match_policy():
    """The corpus sentences must actually exercise all four classes."""
    stored_classes = {}
    run = _new_corpus("admission-class-check")
    _run_intake(run)
    stored = _seed_through_admission(run)
    for surface, (_eid, cls) in stored["entities"].items():
        stored_classes[surface] = cls
    assert stored_classes.get("AcmeCorp") == "GLOBAL"
    assert stored_classes.get("the vector index") == "CORPUS_SCOPED"
    assert stored_classes.get("our engine") == "DOCUMENT_SCOPED"
    assert stored_classes.get("the system") == "MENTION_ONLY"
