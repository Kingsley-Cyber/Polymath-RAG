"""LLM-DIRECT-PRONOUN-GATE-V1: the llm-direct fact path (LLM-DIRECT-FACTS-V1)
wrote ACCEPT facts with unresolved closed-class pronoun endpoints — 13 live
on 2026-09-02 ("me IS_A british luxury designer"). An unresolved pronoun is
evidence, never durable knowledge: pronoun entities and any relation with a
pronoun endpoint are dropped and COUNTED in the stage artifact. Real DB,
rolled back."""
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

import psycopg
import pytest

from polymath_shared.llm_extraction.gate import NormalizedExtraction
from workers.llm_direct import materialize

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
TEXT = "Adam hired me in London. Adam is a British luxury designer who founded Seraph."


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        yield c
        c.rollback()


def _seed(conn):
    corpus = "probe-pron-" + uuid.uuid4().hex[:8]
    doc = "doc_probe_" + uuid.uuid4().hex[:16]
    cid = "chunk_probe_" + uuid.uuid4().hex[:16]
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash, purpose) VALUES (%s,%s,'p','probe')", (corpus, corpus))
    conn.execute("""INSERT INTO documents (doc_id, corpus_id, source_name, media_type, byte_length, content_hash)
                    VALUES (%s,%s,'p.md','text/markdown',%s,%s)""", (doc, corpus, len(TEXT), "h" + uuid.uuid4().hex[:8]))
    conn.execute("""INSERT INTO chunks (chunk_id, doc_id, chunk_index, tier, text, char_start, char_end)
                    VALUES (%s,%s,0,'child',%s,0,%s)""", (cid, doc, TEXT, len(TEXT)))
    return corpus, doc, cid


def _span(surface):
    i = TEXT.index(surface)
    return i, i + len(surface)


def test_pronoun_entities_and_endpoints_are_dropped_and_counted(conn):
    corpus, doc, cid = _seed(conn)
    ents = []
    for surface, label in (("Adam", "Person"), ("me", "Person"), ("Seraph", "Organization"),
                           ("British luxury designer", "Concept")):
        s, e = _span(surface)
        ents.append({"label": label, "text": surface, "start": s, "end": e, "score": 1.0})
    def rel(pred, subj, obj, quote):
        s, e = _span(quote)
        return {"predicate": pred, "subject": subj, "object": obj, "start": s, "end": e,
                "text": quote, "evidence_class": "llm_relation"}
    merged = NormalizedExtraction(
        entities_by_chunk={cid: ents},
        evidence_by_chunk={cid: [
            rel("ACTS_ON", "Adam", "me", "Adam hired me"),                       # pronoun endpoint -> dropped
            rel("IS_A", "Adam", "British luxury designer", "Adam is a British luxury designer"),
            rel("PRODUCES", "Adam", "Seraph", "founded Seraph"),
        ]})
    out = materialize(conn, corpus_id=corpus, doc_id=doc,
                      chunk_rows={cid: {"text": TEXT, "char_start": 0}},
                      merged=merged, lane="probe", model="probe")
    assert out["pronoun_entities_dropped"] == 1
    assert out["pronoun_endpoints_dropped"] == 1
    facts = conn.execute(
        """SELECT DISTINCT f.fact_id, f.predicate FROM facts f JOIN evidence ev ON ev.fact_id = f.fact_id
            WHERE ev.doc_id = %s""", (doc,)).fetchall()
    preds = sorted(p for _, p in facts)
    assert preds == ["IS_A", "PRODUCES"], preds
    pron = conn.execute(
        """SELECT count(*) FROM facts f JOIN evidence ev ON ev.fact_id = f.fact_id
            JOIN entities e ON e.entity_id IN (f.subject_id, f.object_id)
           WHERE ev.doc_id = %s AND lower(e.normalized_surface) = 'me'""", (doc,)).fetchone()[0]
    assert pron == 0
    assert conn.execute("SELECT count(*) FROM mentions WHERE doc_id = %s AND surface = 'me'", (doc,)).fetchone()[0] == 0
