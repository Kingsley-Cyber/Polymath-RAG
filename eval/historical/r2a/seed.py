"""R2A fixture seeding: two disposable qualification corpora.

r2a-text-corpus: the 9-doc R1A coverage fixture (rich multi-section).
r2a-fact-corpus: 3 docs with facts seeded through the PRODUCTION
compiler (build_candidates + compile_relation), incl. one parked
MENTION_ONLY fact for the graph-faithfulness control.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402

TEXT_CORPUS = "r2a-text-corpus"
FACT_CORPUS = "r2a-fact-corpus"

FACT_DOCS = {
    "acme.md": ("# AcmeCorp Stack\n\nAcmeCorp runs on the vector index. "
                "The vector index accelerates our engine. "
                "Our engine depends on the system.\n"),
    "shared.md": ("# Shared Infrastructure\n\nThe vector index serves the nearest "
                  "neighbors for the system.\n"),
    "founding.md": ("# Company Note\n\nAcmeCorp was established by its founding team.\n"),
}


def _wipe(corpus: str) -> None:
    with tx() as conn:
        rids = [r[0] for r in conn.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (corpus,)).fetchall()]
        for rid in rids:
            for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
                conn.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
        docs = [r[0] for r in conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,)).fetchall()]
        chunks = [r[0] for r in conn.execute(
            """SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
               WHERE d.corpus_id=%s""", (corpus,)).fetchall()]
        if docs:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (docs,))
        if chunks:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (chunks,))
        conn.execute("DELETE FROM retrieval_summaries WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM documents WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        for contract in (HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT):
            name = qdrant_collection_name(corpus, contract.contract_id)
            if client.collection_exists(name):
                client.delete_collection(name)
    finally:
        client.close()


def _drive_text(corpus: str, name: str, text: str) -> str:
    from workers.intake_worker import process_event as intake_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event

    payload = canonical_intake_payload(corpus, name, "text/markdown",
                                       base64.b64encode(text.encode()).decode())
    with tx() as conn:
        res = submit_intake(conn, payload)
    rid = res["run_id"]
    with tx() as conn:
        intake_event(conn, {"run_id": rid, "payload": payload,
                            "idempotency_key": content_hash({"i": rid})[:16]})
        conn.execute(
            """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
               VALUES (%s,'extract',%s,now(),now(),'ok') ON CONFLICT DO NOTHING""",
            (rid, content_hash({"s": "extract", "r2a": corpus})),
        )
    with tx() as conn:
        profile_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-p"})
    with tx() as conn:
        qdrant_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-q"})
    with tx() as conn:
        conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))
    return rid


def _drive_fact(corpus: str, name: str, text: str) -> str:
    from workers.intake_worker import process_event as intake_event

    payload = canonical_intake_payload(corpus, name, "text/markdown",
                                       base64.b64encode(text.encode()).decode())
    with tx() as conn:
        res = submit_intake(conn, payload)
    rid = res["run_id"]
    with tx() as conn:
        intake_event(conn, {"run_id": rid, "payload": payload,
                            "idempotency_key": content_hash({"i": rid})[:16]})
    return rid


def _seed_facts() -> None:
    """Seed facts through the production compiler (AcmeCorp pattern)."""
    from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan
    from polymath_shared.entity_admission import allocate_entity_id
    from polymath_shared.rulepack import compile_relation, load_rule_pack
    from polymath_shared.identity import evidence_id
    from workers.candidates import SentenceSlice, build_candidates

    pack = load_rule_pack()
    with tx() as conn:
        doc_id = conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name='acme.md'",
            (FACT_CORPUS,)).fetchone()[0]
        chunk = conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id=%s AND tier='child' ORDER BY chunk_index LIMIT 1",
            (doc_id,)).fetchone()[0]
        text = conn.execute("SELECT text FROM chunks WHERE chunk_id=%s", (chunk,)).fetchone()[0]
        spans = [
            ("AcmeCorp", "Organization", 0, 8),
            ("the vector index", "Technology", text.find("the vector index"), text.find("the vector index") + 16),
            ("our engine", "Technology", text.find("our engine"), text.find("our engine") + 10),
            ("the system", "Technology", text.find("the system"), text.find("the system") + 10),
        ]
        entities = []
        for surface, ctype, start, end in spans:
            entities.append(EntitySpan(
                doc_id=doc_id, chunk_id=chunk, start=start, end=end, text=surface,
                core_type=CoreType(ctype), score=0.9, extractor_version="r2a"))
        evidence = [EvidenceSpan(
            chunk_id=chunk, start=text.find("runs on"), end=text.find("runs on") + 8,
            text="runs on", evidence_class="usage_application",
            trigger_lemma="run", score=0.9, extractor_version="r2a")]
        sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                           entities=entities, evidence=evidence, parse=None)
        cands = build_candidates([sl], doc_id=doc_id, corpus_id=FACT_CORPUS,
                                 ontology_profile="core", extractor_version="r2a",
                                 rule_pack=pack, enrich=False)
        n = 0
        for cand in cands:
            decision = compile_relation(cand, None, pack)
            if decision.fact is None:
                continue
            fact = decision.fact
            for eid, span in ((fact.subject_id, cand.subject.span),
                              (fact.object_id, cand.object.span)):
                decision_adm = allocate_entity_id(
                    span.text, span.core_type.value,
                    corpus_id=FACT_CORPUS, doc_id=doc_id, chunk_id=chunk,
                    span_start=span.start, span_end=span.end,
                    extraction_score=span.score).reference_class
                conn.execute(
                    "INSERT INTO entities (entity_id, core_type, normalized_surface, admission_class) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (entity_id) DO NOTHING",
                    (eid, span.core_type.value, span.text, decision_adm))
            conn.execute(
                """INSERT INTO facts (fact_id, predicate, subject_id, object_id, qualifiers,
                                      decision, rule_id, rule_version, provenance)
                   VALUES (%s,%s,%s,%s,%s,'ACCEPT',%s,%s,%s) ON CONFLICT DO NOTHING""",
                (fact.fact_id, fact.predicate, fact.subject_id, fact.object_id,
                 json.dumps(fact.qualifiers), fact.rule_id, fact.rule_version,
                 json.dumps(fact.provenance)))
            ev_id = evidence_id(fact.fact_id, doc_id, chunk, {"t": "r2a"}, fact.rule_id)
            conn.execute(
                """INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                                          rule_id, gliner_scores, extractor_version, rule_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (ev_id, fact.fact_id, doc_id, chunk, json.dumps({"t": "r2a"}),
                 fact.rule_id, json.dumps({}), "r2a", fact.rule_version))
            n += 1
        print(f"seeded {n} facts for acme.md")


def _project_fact_corpus() -> None:
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event
    from workers.project_neo4j_worker import process_event as neo4j_event
    from workers.canonicalize_worker import process_event as canon_event
    from workers.project_canonical_worker import process_event as pcanon_event

    with tx() as conn:
        rids = [r[0] for r in conn.execute(
            "SELECT run_id FROM runs WHERE corpus_id=%s ORDER BY created_at", (FACT_CORPUS,)).fetchall()]
    for rid in rids:
        with tx() as conn:
            conn.execute(
                """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                   VALUES (%s,'extract',%s,now(),now(),'ok') ON CONFLICT DO NOTHING""",
                (rid, content_hash({"s": "extract", "r2a": "facts"})),
            )
        with tx() as conn:
            profile_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-fp"})
        with tx() as conn:
            qdrant_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-fq"})
        with tx() as conn:
            neo4j_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-fn"})
        with tx() as conn:
            canon_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-fc"})
        with tx() as conn:
            pcanon_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r2a-fpc"})
        with tx() as conn:
            conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))


def main() -> int:
    fixture = ROOT / "eval" / "r1a" / "coverage" / "docs"
    _wipe(TEXT_CORPUS)
    for name in sorted(p.name for p in fixture.glob("*.md")):
        _drive_text(TEXT_CORPUS, name, (fixture / name).read_text())
    print(f"text corpus seeded: {len(list(fixture.glob('*.md')))} docs")

    _wipe(FACT_CORPUS)
    for name, text in FACT_DOCS.items():
        _drive_fact(FACT_CORPUS, name, text)
    _seed_facts()
    _project_fact_corpus()
    print("fact corpus seeded + projected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
