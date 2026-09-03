"""GENERATION-SWAP-V1 live lineage (Postgres required; stores are stubbed).

A serving run R1 (generation gen-A) gets a blue/green successor R2
(generation gen-B) minted BESIDE it: R1 stays query_ready, R2 is
`reconciling` and hidden; gen-B rows coexist with gen-A rows for the same
document (migration 0050); the reader guard hides gen-B; promotion swaps:
R1 superseded, gen-A purged, gen-B visible, derived artifacts without a
surviving chunk removed.
"""
from __future__ import annotations

import json
import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "control", ROOT / "workers"):
    sys.path.insert(0, str(p))

from polymath_shared.settings import get_settings  # noqa: E402


def _pg():
    try:
        return psycopg.connect(get_settings().postgres.dsn, connect_timeout=3)
    except Exception:
        return None


pytestmark = pytest.mark.skipif(_pg() is None, reason="postgres unavailable")


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _seed(conn, tag: str):
    corpus = f"bg-test-{tag}"
    doc = f"doc_bg_{tag}"
    r1 = f"run_bg_{tag}_r1"
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s,%s,'bg')", (corpus, corpus))
    conn.execute(
        "INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash) "
        "VALUES (%s,%s,'bg.md','text/markdown',100,%s)", (doc, corpus, f"h_{tag}"))
    old_pin = {"query_policy": "semantic-query-policy-v1", "chunker": "tier_v3",
               "semantic_bundle": "old-bundle", "ontology_file_sha": "old-onto",
               "extraction_gate": "attestation-levels-v0/tiered"}
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata, execution_contract) "
        "VALUES (%s,%s,'query_ready','{}',%s)", (r1, corpus, json.dumps(old_pin, sort_keys=True)))
    conn.execute(
        "INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key) VALUES (%s,'intake.v1',%s,%s)",
        (r1, json.dumps({"run_id": r1, "corpus_id": corpus, "source_name": "bg.md"}), f"bg-intake-{tag}"))
    for i in range(3):
        conn.execute(
            "INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier, text, summary, char_start, char_end, chunk_contract_version) "
            "VALUES (%s,%s,NULL,%s,'child',%s,'',0,10,'gen-A')", (f"ch_{tag}_a{i}", doc, i, f"alpha text {i}"))
    return corpus, doc, r1


def _cleanup(conn, corpus):
    conn.execute("DELETE FROM stage_tickets WHERE corpus_id=%s", (corpus,))
    conn.execute("DELETE FROM outbox_events WHERE run_id IN (SELECT run_id FROM runs WHERE corpus_id=%s)", (corpus,))
    conn.execute("UPDATE runs SET supersedes_run_id=NULL, superseded_by_run_id=NULL WHERE corpus_id=%s", (corpus,))
    conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))  # documents/chunks/runs cascade


def test_blue_green_lineage_hides_then_swaps(conn, monkeypatch):
    from control import generation_swap
    from control.reconciliation import mint_shadow_successor
    from polymath_shared.generation import chunk_visible_sql, hidden_generations

    monkeypatch.setattr(generation_swap, "_sweep_stores",
                        lambda corpus_id, chunk_ids, evidence_ids: {"neo4j_deleted": None, "qdrant_deleted": None})
    tag = uuid.uuid4().hex[:8]
    corpus, doc, r1 = _seed(conn, tag)
    try:
        # 1. mint beside: predecessor untouched
        r2 = mint_shadow_successor(conn, r1, generation="gen-B")
        assert r2 and r2 != r1
        assert conn.execute("SELECT status FROM runs WHERE run_id=%s", (r1,)).fetchone()[0] == "query_ready"
        st, meta = conn.execute("SELECT status, metadata::text FROM runs WHERE run_id=%s", (r2,)).fetchone()
        bg = json.loads(meta)["blue_green"]
        assert st == "reconciling" and bg["supersedes"] == r1 and bg["generation"] == "gen-B"
        assert bg["predecessor_generation"] == "gen-A"
        assert "extract" in bg["regenerated_stages"]      # gate + bundle changed
        # idempotent: a second mint returns None, no second lineage
        assert mint_shadow_successor(conn, r1, generation="gen-B") is None

        # 2. the successor's intake writes gen-B rows BESIDE gen-A (same indices)
        for i in range(2):
            conn.execute(
                "INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier, text, summary, char_start, char_end, chunk_contract_version) "
                "VALUES (%s,%s,NULL,%s,'child',%s,'',0,10,'gen-B')", (f"ch_{tag}_b{i}", doc, i, f"beta text {i}"))
        assert hidden_generations(conn, corpus) == ["gen-B"]
        visible = conn.execute(
            "SELECT c.chunk_contract_version FROM chunks c JOIN documents d ON d.doc_id=c.doc_id "
            "WHERE d.corpus_id=%s AND " + chunk_visible_sql("c", "d"), (corpus,)).fetchall()
        assert {v[0] for v in visible} == {"gen-A"}, visible

        # a derived artifact grounded only in the old generation
        conn.execute(
            "INSERT INTO concept_artifacts (concept_id, document_id, corpus_id, name, description, domain, "
            "related_entities, source_sentence, confidence, supporting_chunks, provenance, generated_by_bundle_hash) "
            "VALUES (%s,%s,%s,'Alpha','','general','[]','alpha',0.5,%s,'{}','bundle_t')",
            (f"conc_{tag}", doc, corpus, [f"ch_{tag}_a0"]))

        # 3. promotion swaps
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (r2,))
        report = generation_swap.swap(conn, r2, corpus)
        assert report["predecessor"] == r1 and report["purged_chunks"] == 3
        assert report["purged_concepts"] == 1
        assert conn.execute("SELECT status, superseded_by_run_id FROM runs WHERE run_id=%s", (r1,)).fetchone() == ("superseded", r2)
        left = conn.execute("SELECT chunk_contract_version, count(*) FROM chunks WHERE doc_id=%s GROUP BY 1", (doc,)).fetchall()
        assert left == [("gen-B", 2)], left
        assert hidden_generations(conn, corpus) == []
        visible = conn.execute(
            "SELECT count(*) FROM chunks c JOIN documents d ON d.doc_id=c.doc_id "
            "WHERE d.corpus_id=%s AND " + chunk_visible_sql("c", "d"), (corpus,)).fetchone()[0]
        assert visible == 2
        # swap is idempotent
        assert generation_swap.swap(conn, r2, corpus) is None
    finally:
        _cleanup(conn, corpus)
        conn.commit()


def test_extraction_only_successor_hides_nothing(conn, monkeypatch):
    """Same chunker: the successor shares the chunk rows, so no generation
    is hidden and the swap purges no chunks."""
    from control import generation_swap
    from control.reconciliation import mint_shadow_successor
    from polymath_shared.generation import hidden_generations

    monkeypatch.setattr(generation_swap, "_sweep_stores",
                        lambda corpus_id, chunk_ids, evidence_ids: {"neo4j_deleted": None, "qdrant_deleted": None})
    tag = uuid.uuid4().hex[:8]
    corpus, doc, r1 = _seed(conn, tag)
    try:
        r2 = mint_shadow_successor(conn, r1, generation="gen-A")
        assert hidden_generations(conn, corpus) == []
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (r2,))
        report = generation_swap.swap(conn, r2, corpus)
        assert report["purged_chunks"] == 0
        assert conn.execute("SELECT count(*) FROM chunks WHERE doc_id=%s", (doc,)).fetchone()[0] == 3
        assert conn.execute("SELECT status FROM runs WHERE run_id=%s", (r1,)).fetchone()[0] == "superseded"
    finally:
        _cleanup(conn, corpus)
        conn.commit()
