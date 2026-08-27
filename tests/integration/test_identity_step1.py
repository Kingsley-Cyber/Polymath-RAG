"""STEP 1b acceptance: identity model wired through persistence.

Fact growth on the live store: same semantic triple from two sources ->
ONE canonical fact row, TWO evidence links. Duplicate source documents
are rejected by UNIQUE(corpus_id, source_hash) (migration 0026).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.identity_model import fact_key  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "identity-step1-test"


def _cleanup():
    with psycopg.connect(DSN) as c:
        c.execute("DELETE FROM evidence WHERE doc_id LIKE %s", ("idt_%",))
        c.execute("DELETE FROM facts WHERE fact_id LIKE %s",
                  ("fact_idt%",))
        c.execute("DELETE FROM chunks WHERE chunk_id LIKE %s", ("idt_%",))
        c.execute("DELETE FROM entities WHERE entity_id IN "
                  "('idt_bert','idt_books')")
        c.execute("DELETE FROM documents WHERE corpus_id=%s OR "
                  "doc_id LIKE %s", (CORPUS, "idt_%"))
        c.execute("DELETE FROM corpora WHERE corpus_id=%s",
                  (CORPUS,))
        c.commit()


def test_fact_growth_and_duplicate_source_rejection():
    fid = "fact_idt" + fact_key(subject_id="idt_bert",
                                predicate="trained_on",
                                object_id="idt_books")[:24]
    _cleanup()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) "
                     "VALUES (%s,%s,%s) ON CONFLICT (corpus_id) DO NOTHING",
                     (CORPUS, CORPUS, "cfg-test"))
        conn.commit()
        # two distinct source documents (distinct source hashes)
        for n, dh in (("a", "hash_a"), ("b", "hash_b")):
            conn.execute(
                """INSERT INTO documents (doc_id, corpus_id, source_name,
                   media_type, byte_length, content_hash, source_hash)
                   VALUES (%s,%s,%s,'text/markdown',10,%s,%s)""",
                ("idt_" + n, CORPUS, f"{n}.md", dh, dh))
            conn.execute(
                """INSERT INTO chunks (chunk_id, doc_id, chunk_index,
                   tier, text, char_start, char_end)
                   VALUES (%s,'idt_'||%s,0,'child','x',0,1)""",
                ("idt_ch_" + n, n))
        for eid, core in (("idt_bert", "Model"),
                          ("idt_books", "Dataset")):
            conn.execute(
                """INSERT INTO entities (entity_id, core_type,
                   normalized_surface, admission_class)
                   VALUES (%s,%s,%s,'GLOBAL')
                   ON CONFLICT (entity_id) DO NOTHING""", (eid, core, eid))

        # SAME triple from two sources -> ONE fact, evidence GROWS
        for n, chunk in (("a", "idt_ch_a"), ("b", "idt_ch_b")):
            conn.execute(
                """INSERT INTO facts (fact_id, predicate, subject_id,
                   object_id, qualifiers, decision, rule_id, rule_version,
                   provenance)
                   VALUES (%s,'trained_on','idt_bert','idt_books','{}',
                   'ACCEPT','trained_on','1.4.0','{}')
                   ON CONFLICT (fact_id) DO NOTHING""", (fid,))
            conn.execute(
                """INSERT INTO evidence (evidence_id, fact_id, doc_id,
                   chunk_id, span_offsets, rule_id, gliner_scores,
                   extractor_version, rule_version, provenance_contract)
                   VALUES (%s,%s,'idt_'||%s,%s,'[]','trained_on','{}',
                   'test','1.4.0','exact-evidence-v1')""",
                ("ev_" + uuid.uuid4().hex, fid, n, chunk))

        n_facts = conn.execute("SELECT count(*) FROM facts WHERE "
                               "fact_id=%s", (fid,)).fetchone()[0]
        n_ev = conn.execute("SELECT count(*) FROM evidence WHERE "
                            "fact_id=%s", (fid,)).fetchone()[0]
        assert n_facts == 1 and n_ev == 2

    # duplicate SOURCE document rejected by the identity index
    with psycopg.connect(DSN) as conn:
        conn.execute(
            """INSERT INTO documents (doc_id, corpus_id, source_name,
               media_type, byte_length, content_hash, source_hash)
               VALUES ('idt_first',%s,'first.md','text/markdown',5,
               'duphash','duphash')""", (CORPUS,))
        rejected = False
        try:
            conn.execute(
                """INSERT INTO documents (doc_id, corpus_id, source_name,
                   media_type, byte_length, content_hash, source_hash)
                   VALUES ('idt_second',%s,'second.md','text/markdown',5,
                   'dupcontent','duphash')""", (CORPUS,))
        except psycopg.errors.UniqueViolation:
            rejected = True
            conn.rollback()
    assert rejected, "UNIQUE(corpus_id, source_hash) must reject duplicates"

    _cleanup()
