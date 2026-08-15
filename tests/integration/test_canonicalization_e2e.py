"""C1 acceptance: the canonicalize worker stage builds the corpus
canonical registry over live stores, with full lineage back to
source-local knowledge, replay safety, and incremental delta behavior.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up + db-migrate).
Seeded corpora use unique ids and clean up after themselves.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import run_id  # noqa: E402
from workers.canonicalize_worker import process_event  # noqa: E402

CORPUS = "c1_e2e"


def _cleanup() -> None:
    """Corpus-scoped cleanup (join-based: content-hashed ids can start
    with 'c1'/'doc_c1' coincidentally, so prefix patterns may hit
    unrelated corpora's rows)."""
    with tx() as conn:
        ids = conn.execute(
            "SELECT jsonb_agg(id) FROM ("
            "SELECT DISTINCT c.chunk_id AS id FROM chunks c JOIN documents d ON d.doc_id=c.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT e.evidence_id AS id FROM evidence e JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT f.fact_id AS id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s "
            "UNION SELECT DISTINCT ce.canonical_id AS id FROM canonical_entities ce WHERE ce.corpus_id=%s "
            "UNION SELECT DISTINCT cm.local_entity_id AS id FROM canonical_memberships cm WHERE cm.corpus_id=%s "
            "UNION SELECT DISTINCT e2.entity_id AS id FROM entities e2 JOIN facts f2 ON f2.subject_id=e2.entity_id OR f2.object_id=e2.entity_id "
            "JOIN evidence ev2 ON ev2.fact_id=f2.fact_id JOIN documents d2 ON d2.doc_id=ev2.doc_id WHERE d2.corpus_id=%s) x",
            (CORPUS,)*6).fetchone()[0] or []
        chunk_ids=[i for i in ids if i.startswith('chunk_')]
        ev_ids=[i for i in ids if i.startswith('ev_')]
        fact_ids=[i for i in ids if i.startswith('fact_')]
        canon_ids=[i for i in ids if i.startswith('cent_')]
        ent_ids=[i for i in ids if i.startswith('ent_')]
        conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                     (chunk_ids+ev_ids+fact_ids+canon_ids+ent_ids,))
        conn.execute("DELETE FROM canonicalization_decisions WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_memberships WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_entities WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM evidence WHERE evidence_id = ANY(%s)", (ev_ids,))
        conn.execute("DELETE FROM facts WHERE fact_id = ANY(%s)", (fact_ids,))
        if ent_ids:
            conn.execute(
                "DELETE FROM entities WHERE entity_id = ANY(%s) "
                "AND NOT EXISTS (SELECT 1 FROM facts f2 WHERE f2.subject_id=entities.entity_id OR f2.object_id=entities.entity_id)",
                (ent_ids,))
        conn.execute("DELETE FROM chunks WHERE chunk_id = ANY(%s)", (chunk_ids,))
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,))


def _seed_doc(run: str, doc_id: str, source_name: str,
              chunk_id: str, text: str) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                   byte_length, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO NOTHING
            """,
            (doc_id, CORPUS, source_name, "text/plain", len(text), f"hash-{doc_id}"),
        )
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                text, summary, char_start, char_end)
            VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
            ON CONFLICT (chunk_id) DO NOTHING
            """,
            (chunk_id, doc_id, text, len(text)),
        )


def _seed_entity(entity_id: str, core_type: str, surface: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s) "
            "ON CONFLICT (entity_id) DO NOTHING",
            (entity_id, core_type, surface),
        )


def _seed_fact(fact_id: str, predicate: str, subject_id: str, object_id: str,
               doc_id: str, chunk_id: str) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                               qualifiers, decision, rule_id, rule_version, provenance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fact_id) DO NOTHING
            """,
            (fact_id, predicate, subject_id, object_id, "{}", "ACCEPT",
             "rule-1", "1.0.1", "{}"),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                  span_offsets, rule_id, gliner_scores,
                                  extractor_version, rule_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (evidence_id) DO NOTHING
            """,
            (f"ev_{fact_id}", fact_id, doc_id, chunk_id, "{}", "rule-1", "{}",
             "1.0", "1.0.1"),
        )


def _make_run() -> str:
    canonical = {
        "corpus_id": CORPUS,
        "source_name": f"{CORPUS}.txt",
        "media_type": "text/plain",
        "content_b64": "x",
        "config": {},
    }
    rid = run_id(CORPUS, canonical)
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s) "
            "ON CONFLICT (corpus_id) DO NOTHING",
            (CORPUS, "c1 e2e corpus", "c1-config"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'reconciling', %s) "
            "ON CONFLICT (run_id) DO NOTHING",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})),
        )
    return rid


def _registry_rows() -> tuple[list[tuple], list[tuple], list[tuple]]:
    with tx() as conn:
        canons = conn.execute(
            "SELECT canonical_id, canonical_type, normalized_name FROM canonical_entities "
            "WHERE corpus_id = %s ORDER BY canonical_id", (CORPUS,)
        ).fetchall()
        members = conn.execute(
            "SELECT local_entity_id, canonical_id, decision, confidence FROM canonical_memberships "
            "WHERE corpus_id = %s ORDER BY local_entity_id", (CORPUS,)
        ).fetchall()
        decisions = conn.execute(
            "SELECT local_entity_a, local_entity_b, decision, confidence FROM canonicalization_decisions "
            "WHERE corpus_id = %s ORDER BY decision_id", (CORPUS,)
        ).fetchall()
    return canons, members, decisions


def test_canonicalize_stage_builds_registry_with_lineage() -> None:
    _cleanup()
    rid = _make_run()
    # Doc A: AcmeCorp (also extracted from doc B as the same entity).
    _seed_doc(rid, "doc_c1_a", "a.txt", "chunk_c1_a", "AcmeCorp makes tools.")
    _seed_doc(rid, "doc_c1_b", "b.txt", "chunk_c1_b", "AcmeCorp ships tools.")
    for eid, ctype, surface in [
        ("ent_c1_tools", "Product", "tools"),
        ("ent_c1_acme_a", "Organization", "AcmeCorp"),
        ("ent_c1_acme_b", "Organization", "AcmeCorp"),
        ("ent_c1_js_a", "Person", "John Smith"),
        ("ent_c1_js_b", "Person", "John Smith"),
    ]:
        _seed_entity(eid, ctype, surface)
    _seed_fact("fact_c1_a", "produces", "ent_c1_acme_a", "ent_c1_tools",
               "doc_c1_a", "chunk_c1_a")
    _seed_fact("fact_c1_tools", "produced_by", "ent_c1_tools", "ent_c1_acme_a",
               "doc_c1_a", "chunk_c1_a")
    _seed_fact("fact_c1_b", "ships", "ent_c1_acme_b", "ent_c1_tools",
               "doc_c1_b", "chunk_c1_b")
    _seed_fact("fact_c1_js_a", "wrote", "ent_c1_js_a", "ent_c1_acme_a",
               "doc_c1_a", "chunk_c1_a")
    _seed_fact("fact_c1_js_b", "wrote", "ent_c1_js_b", "ent_c1_acme_b",
               "doc_c1_b", "chunk_c1_b")

    with tx() as conn:
        process_event(conn, {"run_id": rid})

    canons, members, decisions = _registry_rows()
    member_map = {m[0]: m for m in members}

    # Same obvious entity across two docs -> ONE canonical identity.
    assert member_map["ent_c1_acme_a"][1] == member_map["ent_c1_acme_b"][1]
    assert member_map["ent_c1_acme_a"][2] == "SAME_AS"
    assert member_map["ent_c1_acme_a"][3] == 1.0

    # Ambiguous John Smith pair abstains: separate canonicals.
    assert member_map["ent_c1_js_a"][1] != member_map["ent_c1_js_b"][1]
    assert member_map["ent_c1_js_a"][2] == "SELF"

    # Pair decision recorded with basis (basis JSONB checked non-empty).
    with tx() as conn:
        row = conn.execute(
            "SELECT basis FROM canonicalization_decisions WHERE corpus_id = %s LIMIT 1",
            (CORPUS,),
        ).fetchone()
        assert row and row[0]

    # Lineage: canonical -> local entity -> fact -> evidence -> source.
    with tx() as conn:
        lineage = conn.execute(
            """
            SELECT cm.canonical_id, e.entity_id, f.fact_id, ev.evidence_id,
                   ev.chunk_id, d.doc_id
              FROM canonical_memberships cm
              JOIN entities e ON e.entity_id = cm.local_entity_id
              JOIN facts f ON f.subject_id = e.entity_id
              JOIN evidence ev ON ev.fact_id = f.fact_id
              JOIN documents d ON d.doc_id = ev.doc_id
             WHERE cm.corpus_id = %s AND e.entity_id = %s
            """,
            (CORPUS, "ent_c1_acme_a"),
        ).fetchall()
        assert lineage
        assert lineage[0][1] == "ent_c1_acme_a"
        assert lineage[0][2] == "fact_c1_a"
        assert lineage[0][3] == "ev_fact_c1_a"
        assert lineage[0][4] == "chunk_c1_a"
        assert lineage[0][5] == "doc_c1_a"

    # Original entity/fact/evidence rows untouched.
    with tx() as conn:
        n_entities = conn.execute(
            "SELECT COUNT(DISTINCT e.entity_id) FROM entities e "
            "JOIN facts f ON f.subject_id=e.entity_id OR f.object_id=e.entity_id "
            "JOIN evidence ev ON ev.fact_id=f.fact_id "
            "JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s",
            (CORPUS,)).fetchone()[0]
        n_facts = conn.execute(
            "SELECT COUNT(*) FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
            "JOIN documents d ON d.doc_id=e.doc_id WHERE d.corpus_id=%s",
            (CORPUS,)).fetchone()[0]
        n_evidence = conn.execute(
            "SELECT COUNT(*) FROM evidence e JOIN documents d ON d.doc_id=e.doc_id "
            "WHERE d.corpus_id=%s",
            (CORPUS,)).fetchone()[0]
    assert n_entities == 5
    assert n_facts == 5
    assert n_evidence == 5

    # Replay: zero duplicates.
    with tx() as conn:
        process_event(conn, {"run_id": rid})
    canons2, members2, decisions2 = _registry_rows()
    assert canons2 == canons
    assert members2 == members
    assert decisions2 == decisions

    # Incremental addition: new document only adds the required delta.
    _seed_doc(rid, "doc_c1_c", "c.txt", "chunk_c1_c", "AcmeCorp expands.")
    _seed_entity("ent_c1_acme_c", "Organization", "AcmeCorp")
    _seed_fact("fact_c1_c", "expands", "ent_c1_acme_c", "ent_c1_tools",
               "doc_c1_c", "chunk_c1_c")
    with tx() as conn:
        process_event(conn, {"run_id": rid})
    canons3, members3, decisions3 = _registry_rows()
    # Previous rows identical...
    assert {(m[0], m[1], m[2], m[3]) for m in members} <= set(members3)
    # ...and the new entity joins the existing canonical identity.
    assert member_map["ent_c1_acme_a"][1] in {m[1] for m in members3}
    new_member = [m for m in members3 if m[0] == "ent_c1_acme_c"][0]
    assert new_member[1] == member_map["ent_c1_acme_a"][1]
    assert new_member[2] == "SAME_AS"
    _cleanup()
