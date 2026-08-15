"""D2: graph expansion is corpus-authorized.

Seeds resolve from entities attached to in-scope evidence; the
directed bidirectional expansion never returns facts supported
exclusively by another corpus. GLOBAL identity is untouched; shared
entities only surface facts authorized by the active corpus.

Requires live stores: make db-up; POLYMATH_INTEGRATION=1.
"""
from __future__ import annotations

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
from orchestrator.orchestrator.api.retrieve import _neo4j_expand  # noqa: E402
from polymath_shared.identity import content_hash  # noqa: E402

CORPUS_A = "d2-scope-a"
CORPUS_B = "d2-scope-b"


def _seed_corpus(corpus: str, entities: list[tuple[str, str, str | None]],
                 facts: list[tuple[str, str, str, str]]) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,%s) "
            "ON CONFLICT (corpus_id) DO NOTHING",
            (corpus, corpus, "d2"),
        )
        doc = f"doc_{corpus}"
        conn.execute(
            "INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) "
            "VALUES (%s,%s,%s,'text/plain',10,%s) ON CONFLICT (doc_id) DO NOTHING",
            (doc, corpus, f"{corpus}.txt", corpus),
        )
        chunk = f"chunk_{corpus}"
        conn.execute(
            "INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier, text, summary, char_start, char_end) "
            "VALUES (%s,%s,NULL,0,'child',%s,'',0,10) ON CONFLICT (chunk_id) DO NOTHING",
            (chunk, doc, f"{corpus} evidence text"),
        )
        for eid, ctype, surface in entities:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface, admission_class) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (entity_id) DO NOTHING",
                (eid, ctype, surface, None),
            )
        for fact_id, pred, subj, obj in facts:
            conn.execute(
                "INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers, decision, rule_id, rule_version, provenance) "
                "VALUES (%s,%s,%s,%s,%s,'ACCEPT','r','1.0',%s) ON CONFLICT (fact_id) DO NOTHING",
                (fact_id, pred, subj, obj, json.dumps({}), json.dumps({})),
            )
            conn.execute(
                "INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets, rule_id, gliner_scores, extractor_version, rule_version) "
                "VALUES (%s,%s,%s,%s,%s,'r',%s,'t','1.0') ON CONFLICT (evidence_id) DO NOTHING",
                (f"ev_{fact_id}", fact_id, doc, chunk, json.dumps({"t": 0}), json.dumps({})),
            )


def _project(corpus: str) -> None:
    from workers.project_neo4j_worker import process_event as _n
    from polymath_shared.identity import run_id

    with tx() as conn:
        rid = conn.execute("SELECT run_id FROM runs WHERE corpus_id=%s LIMIT 1", (corpus,)).fetchone()
        if rid is None:
            canonical = {"corpus_id": corpus, "source_name": f"{corpus}.txt",
                         "media_type": "text/plain", "content_b64": "dGVzdA==", "config": {}}
            rid = run_id(corpus, canonical)
            conn.execute(
                "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s,%s,'query_ready',%s)",
                (rid, corpus, json.dumps({"intake_payload": canonical})),
            )
            conn.execute(
                "INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key) VALUES (%s,'intake.v1',%s,%s)",
                (rid, json.dumps(canonical), content_hash({"r": rid})),
            )
        _n(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "d2"})


def _wipe(corpus: str) -> None:
    from workers.project_neo4j_worker import _driver

    with tx() as conn:
        conn.execute("DELETE FROM projection_receipts WHERE entity_id LIKE %s", (f"{corpus}%",))
        conn.execute("DELETE FROM facts WHERE fact_id LIKE %s", (f"fact_{corpus}%",))
        conn.execute("DELETE FROM evidence WHERE evidence_id LIKE %s", (f"ev_fact_{corpus}%",))
        conn.execute("DELETE FROM entities WHERE entity_id LIKE %s", (f"ent_{corpus}%",))
        conn.execute("DELETE FROM chunks WHERE chunk_id LIKE %s", (f"chunk_{corpus}%",))
        conn.execute("DELETE FROM documents WHERE doc_id LIKE %s", (f"doc_{corpus}%",))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
    driver = _driver()
    try:
        with driver.session() as s:
            s.run("MATCH (e:Entity) WHERE e.entity_id STARTS WITH $p DETACH DELETE e", p=f"ent_{corpus}_")
            s.run("MATCH (f:Fact) WHERE f.fact_id STARTS WITH $p DETACH DELETE f", p=f"fact_{corpus}_")
            s.run("MATCH (c:Chunk) WHERE c.chunk_id STARTS WITH $p DETACH DELETE c", p=f"chunk_{corpus}_")
            s.run("MATCH (d:Document) WHERE d.doc_id STARTS WITH $p DETACH DELETE d", p=f"doc_{corpus}_")
    finally:
        driver.close()


def test_expansion_is_corpus_authorized():
    _wipe(CORPUS_A)
    _wipe(CORPUS_B)
    try:
        # Corpus A: legacy generic hubs (NULL admission = GLOBAL eligible).
        _seed_corpus(CORPUS_A,
                     [("ent_d2a_system", "Technology", "the system"),
                      ("ent_d2a_pool", "Technology", "the worker pool"),
                      ("ent_d2a_shared", "Organization", "SharedCorp")],
                     [("fact_d2a_use", "uses", "ent_d2a_pool", "ent_d2a_system"),
                      ("fact_d2a_shared", "depends_on", "ent_d2a_shared", "ent_d2a_pool")])
        _project(CORPUS_A)
        # Corpus B: the active query corpus.
        _seed_corpus(CORPUS_B,
                     [("ent_d2b_db", "Technology", "the database"),
                      ("ent_d2b_shared", "Organization", "SharedCorp")],
                     [("fact_d2b_use", "uses", "ent_d2b_shared", "ent_d2b_db")])
        _project(CORPUS_B)

        # 1) A surface that only matches corpus A's generic hub yields
        #    NOTHING when the active scope is corpus B.
        rows = _neo4j_expand(["system"], corpus_id=CORPUS_B)
        assert rows == [], f"foreign generic hub leaked: {rows}"

        # 2) Corpus B's own surfaces return only corpus B facts —
        #    never the shared entity's corpus A fact.
        rows = _neo4j_expand(["database", "sharedcorp"], corpus_id=CORPUS_B)
        fact_ids = {r["fact_id"] for r in rows}
        assert "fact_d2b_use" in fact_ids
        assert not (fact_ids & {"fact_d2a_use", "fact_d2a_shared"}), f"foreign facts leaked: {fact_ids}"

        # 3) Orientation is preserved (subject/object as stored).
        b_use = next(r for r in rows if r["fact_id"] == "fact_d2b_use")
        assert b_use["subject_id"] == "ent_d2b_shared"
        assert b_use["object_id"] == "ent_d2b_db"
        assert b_use["predicate"] == "uses"

        # 4) Cross-corpus route (corpus_id=None) still spans corpora.
        #    Use d2-only surfaces so legacy shared-graph hubs do not
        #    consume the 8-seed cap before the d2 entities.
        rows = _neo4j_expand(["sharedcorp"], corpus_id=None)
        fact_ids = {r["fact_id"] for r in rows}
        assert "fact_d2a_shared" in fact_ids, f"corpus A fact missing: {fact_ids}"
        assert "fact_d2b_use" in fact_ids, f"corpus B fact missing: {fact_ids}"
    finally:
        _wipe(CORPUS_A)
        _wipe(CORPUS_B)
