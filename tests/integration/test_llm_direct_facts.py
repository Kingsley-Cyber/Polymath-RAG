"""LLM-DIRECT-FACTS-V1 — gated relations become facts, by identity, idempotently.

DB-backed (rolled back): temp document + chunk, a gated packet, then
materialize twice. Proves: rows land in entities/mentions/facts/evidence
with FKs satisfied; second call writes zero rows; the same relation from a
second document aggregates onto the SAME fact with a second evidence row;
symmetric predicates order their endpoints.
"""
from __future__ import annotations

import json
import pathlib
import sys

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.llm_extraction.gate import ChunkView, sanitize, validate_and_normalize  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402
from workers import llm_direct  # noqa: E402

TEXT = "FortiGate firewalls require IPsec tunnels. Splunk correlates with Elastic for detection."


def _packet(nid: str) -> str:
    return json.dumps({"contract": "polymath-extraction-v1", "profile": "volume", "items": [{
        "neighborhood_id": nid,
        "entities": [{"surface": "FortiGate", "type": "Product", "quote": TEXT},
                     {"surface": "IPsec tunnels", "type": "protocol", "quote": TEXT},
                     {"surface": "Splunk", "type": "Product", "quote": TEXT},
                     {"surface": "Elastic", "type": "Product", "quote": TEXT}],
        "relations": [{"subject": "FortiGate", "predicate": "REQUIRES", "object": "IPsec tunnels",
                       "quote": "FortiGate firewalls require IPsec tunnels."},
                      {"subject": "Elastic", "predicate": "CORRELATES_WITH", "object": "Splunk",
                       "quote": "Splunk correlates with Elastic for detection."}],
        "digest": {}}]})


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _seed(conn, doc_id: str, chunk_id: str, corpus="__llm_direct_test__"):
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose, query_enabled) "
                 "VALUES (%s,%s,'test','probe',false) ON CONFLICT (corpus_id) DO NOTHING", (corpus, corpus))
    conn.execute("""INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length,
                    content_hash, profile) VALUES (%s,%s,%s,'text/markdown',%s,%s,'{}')""",
                 (doc_id, corpus, f"{doc_id}.md", len(TEXT), doc_id))
    conn.execute("""INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier, text, summary,
                    char_start, char_end) VALUES (%s,%s,NULL,0,'child',%s,'',0,%s)""",
                 (chunk_id, doc_id, TEXT, len(TEXT)))
    return {chunk_id: {"chunk_id": chunk_id, "doc_id": doc_id, "text": TEXT,
                       "char_start": 0, "char_end": len(TEXT)}}


def test_direct_facts_land_and_aggregate_across_documents(conn) -> None:
    corpus = "__llm_direct_test__"
    rows_a = _seed(conn, "doc_llmdirect_a", "chunk_llmdirect_a")
    _, pkt = sanitize(_packet("n1"), {"n1"})
    merged = validate_and_normalize(pkt, {"n1": [ChunkView("chunk_llmdirect_a", TEXT)]})
    assert merged.stats["relations"] == 2
    stats = llm_direct.materialize(conn, corpus_id=corpus, doc_id="doc_llmdirect_a",
                                   chunk_rows=rows_a, merged=merged, lane="local", model="m")
    assert stats["written"]["facts"] == 2 and stats["written"]["evidence"] == 2
    assert stats["seen"]["entities"] >= 4 and stats["written"]["mentions"] >= 4   # entity rows are global by (type, surface): may pre-exist
    assert set(stats["predicates"]) == {"REQUIRES", "CORRELATES_WITH"}
    # idempotent
    again = llm_direct.materialize(conn, corpus_id=corpus, doc_id="doc_llmdirect_a",
                                   chunk_rows=rows_a, merged=merged, lane="local", model="m")
    assert again["written"] == {"entities": 0, "mentions": 0, "facts": 0, "evidence": 0}
    # symmetric predicate: endpoints ordered by entity id
    sym = conn.execute("SELECT DISTINCT f.subject_id, f.object_id FROM facts f "
                       "JOIN evidence e ON e.fact_id=f.fact_id WHERE f.predicate='CORRELATES_WITH' "
                       "AND f.provenance->>'contract'='llm-direct-facts-v1' AND e.doc_id='doc_llmdirect_a'").fetchall()
    assert sym and all(s < o for s, o in sym)
    # second document, same relation → same fact, new evidence row
    rows_b = _seed(conn, "doc_llmdirect_b", "chunk_llmdirect_b")
    merged_b = validate_and_normalize(pkt, {"n1": [ChunkView("chunk_llmdirect_b", TEXT)]})
    b = llm_direct.materialize(conn, corpus_id=corpus, doc_id="doc_llmdirect_b",
                               chunk_rows=rows_b, merged=merged_b, lane="cloud", model="m2")
    assert b["written"]["facts"] == 0 and b["written"]["evidence"] == 2
    fid = conn.execute("SELECT f.fact_id FROM facts f JOIN evidence e ON e.fact_id=f.fact_id "
                       "WHERE f.predicate='REQUIRES' "
                       "AND f.provenance->>'contract'='llm-direct-facts-v1' "
                       "AND e.doc_id='doc_llmdirect_a' LIMIT 1").fetchone()[0]
    docs = {r[0] for r in conn.execute("SELECT doc_id FROM evidence WHERE fact_id=%s", (fid,)).fetchall()}
    assert docs == {"doc_llmdirect_a", "doc_llmdirect_b"}
    # evidence offsets are exact source slices
    off = conn.execute("SELECT span_offsets FROM evidence WHERE fact_id=%s AND doc_id='doc_llmdirect_a'", (fid,)).fetchone()[0]
    assert TEXT[off["subject_start"]:off["subject_end"]] == "FortiGate"
    assert TEXT[off["object_start"]:off["object_end"]] == "IPsec tunnels"
    assert TEXT[off["evidence_start"]:off["evidence_end"]] == "FortiGate firewalls require IPsec tunnels."
    # mentions carry corpus + document provenance
    m = conn.execute("SELECT corpus_id, doc_id, entity_id FROM mentions WHERE doc_id='doc_llmdirect_a' AND surface='FortiGate'").fetchone()
    assert m[0] == corpus and m[2] is not None
