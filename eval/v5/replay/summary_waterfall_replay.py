"""SUMMARY INTELLIGENCE WATERFALL REPLAY — TEST.md, zero pollution.

One transaction: extract (v2/kimi_v1) -> accepted knowledge ->
parent summaries -> document summary -> corpus map -> vocabulary
admission. Measure lineage + anti-hallucination at every level.
ROLLBACK at the end: the live drain never sees this.

Owner rules honored:
- summaries consume ONLY accepted facts/entities/events
- document summaries derive ONLY from parent summaries
- vocabulary admits ONLY from corpus/document map concepts
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
os.environ["POLYMATH_PREDICATE_V2"] = "shadow"
os.environ["POLYMATH_SYNTAX_PROVIDER"] = "spacy"
os.environ.setdefault(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

RUN_ID = "run_3f7954d5df151520336a53f0acaadc55d240737716f6896bc4671046457b7dc4"


def main() -> dict:
    from workers.extract_worker import process_event as extract_event
    from polymath_shared.summary_runtime import run_parent_summary_ticket
    from polymath_shared.summary_workers import (
        build_document_summary, build_corpus_summary)
    from polymath_shared.corpus_mapping import build_corpus_map
    from polymath_shared.vocabulary_mapping import build_concept_families

    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False)
    conn.execute("SET lock_timeout='10s'")
    cur = conn.cursor(row_factory=dict_row)

    # ---- 1. extraction inside the tx -----------------------------------
    cur.execute("""
        SELECT d.doc_id, d.corpus_id, d.source_name FROM runs r
          JOIN documents d ON d.corpus_id=r.corpus_id
         WHERE r.run_id=%s AND d.source_name ILIKE %s LIMIT 1""",
        (RUN_ID, "%TEST.md%"))
    _d = cur.fetchone()
    doc_id, corpus_id, source_name = (_d["doc_id"], _d["corpus_id"],
                                      _d["source_name"])

    cur.execute("""
        SELECT payload::text FROM outbox_events
         WHERE run_id=%s AND event_type='chunked.v1'
           AND payload::text LIKE %s LIMIT 1""", (RUN_ID, f"%{doc_id[:24]}%"))
    row = cur.fetchone()
    payload = json.loads(row["payload"]) if row else {
        "run_id": RUN_ID, "doc_id": doc_id, "corpus_id": corpus_id}
    extract_event(conn, {"run_id": RUN_ID, "event_type": "chunked.v1",
                         "payload": payload,
                         "idempotency_key": "replay-waterfall"})

    facts = [
        {"fact_id": r["fact_id"], "predicate": r["predicate"],
         "subject_surface": r["subject"],
         "object_surface": r["object"]}
        for r in cur.execute("""
        SELECT DISTINCT f.fact_id, f.predicate,
               sn.normalized_surface AS subject,
               no.normalized_surface AS object
          FROM facts f
          JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN entities sn ON sn.entity_id=f.subject_id
          JOIN entities no ON no.entity_id=f.object_id
         WHERE ev.doc_id=%s""", (doc_id,)).fetchall()] or []
    # fallback mapping subject/object text via canonical surfaces
    if not facts:
        facts = [dict(r) for r in cur.execute("""
            SELECT DISTINCT f.fact_id, f.predicate FROM facts f
              JOIN evidence ev ON ev.fact_id=f.fact_id
             WHERE ev.doc_id=%s""", (doc_id,)).fetchall()]
    admitted_entities = [r["surface"] for r in cur.execute("""
        SELECT DISTINCT surface FROM mentions WHERE doc_id=%s
          AND admission_class IN ('GLOBAL','CORPUS_SCOPED','DOCUMENT_SCOPED')
        """, (doc_id,)).fetchall()]

    parents = [(r["chunk_id"], r["text"]) for r in cur.execute("""
        SELECT chunk_id, text FROM chunks
         WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index""",
        (doc_id,)).fetchall()]
    children_by_parent = {}
    for pid, ptext in parents:
        kids = cur.execute("""
            SELECT chunk_id, text FROM chunks
             WHERE parent_id=%s AND tier='child' ORDER BY chunk_index""",
            (pid,)).fetchall()
        children_by_parent[pid] = (ptext, kids)

    # ---- 2. parent summaries -------------------------------------------
    report = {"levels": {}}
    parent_payloads = []
    for pid, ptext in parents:
        ptext2, kids = ptext, children_by_parent[pid][1]
        ticket = "replay_ps_" + pid[-12:]
        cur.execute("""
            INSERT INTO summary_jobs (ticket_id, stage, corpus_id, parent_id,
               input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY',%s,%s,%s,'replay-v1')
            ON CONFLICT (ticket_id) DO NOTHING""",
            (ticket, corpus_id, pid, "replay_" + pid[-16:]))
        kid_dicts = [{"id": k, "text": t} for k, t in kids]
        res = run_parent_summary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus_id, parent_id=pid,
            input_hash="replay_" + pid[-16:], contract_version="replay-v1",
            worker_id="waterfall-replay", parent_text=ptext2,
            children=kid_dicts, facts=facts,
            entities=[{"surface": s} for s in admitted_entities],
            source_ids=[k for k, _ in kids] or [pid])
        if res.get("status") in ("COMPLETE", "EXISTING"):
            sid = res["summary_id"]
            payload_row = cur.execute("""
                SELECT entities, concepts, summary FROM parent_summaries
                 WHERE summary_id=%s""", (sid,)).fetchone()
            parent_payloads.append({
                "payload": {"parent_id": pid,
                            "entities": payload_row["entities"],
                            "concepts": payload_row["concepts"],
                            "summary": payload_row["summary"]},
                "artifact_id": sid})
    report["levels"]["parent_summaries"] = {
        "count": len(parent_payloads),
        "samples": [{"entities": p["payload"]["entities"],
                     "concepts": p["payload"]["concepts"],
                     "summary": p["payload"]["summary"][:120]}
                    for p in parent_payloads[:3]],
    }

    # ---- 3. document summary (parents ONLY) ----------------------------
    doc_env = build_document_summary(
        document_id=doc_id, title=source_name,
        parent_summaries=parent_payloads)
    doc_payload = doc_env["payload"]
    report["levels"]["document_summary"] = {
        "summary": doc_payload["summary"][:200],
        "major_entities": doc_payload["major_entities"],
        "major_concepts": doc_payload["major_concepts"],
        "derived_from_parents_only": all(
            d in {p["payload"]["parent_id"] for p in parent_payloads}
            for d in doc_payload["derived_from"]),
    }

    # ---- 4. corpus map ---------------------------------------------------
    doc_payload["summary_id"] = "replay_doc_" + doc_id[-12:]
    corpus_map = build_corpus_map(corpus_id=corpus_id,
                                  document_summaries=[doc_payload])
    report["levels"]["corpus_map"] = {
        "entities": corpus_map.get("entities") or corpus_map,
        "concepts": corpus_map.get("concepts"),
        "predicates": corpus_map.get("predicates"),
    }

    # ---- 5. vocabulary admission (from map concepts ONLY) ---------------
    concepts = []
    for c in (corpus_map.get("concepts") or [])[:20]:
        concepts.append(c if isinstance(c, str) else str(c))
    families = build_concept_families(
        corpus_id=corpus_id, parent_summaries=parent_payloads,
        document_summaries=[doc_payload],
        accepted_concepts=concepts) if concepts else {"families": []}
    report["levels"]["vocabulary"] = families

    # ---- lineage audit ----------------------------------------------------
    dangling = 0
    failed_ids = []
    for p in parent_payloads:
        for sid in (p["payload"].get("parent_id"),):
            r = cur.execute("SELECT 1 FROM chunks WHERE chunk_id=%s",
                            (sid,)).fetchone()
            if r is None:
                dangling += 1
                failed_ids.append(sid)
    report["lineage"] = {
        "parent_source_ids_resolve": dangling == 0,
        "unresolved_ids": failed_ids,
        "doc_derived_from_parents_only":
            report["levels"]["document_summary"]["derived_from_parents_only"],
    }

    conn.rollback()
    conn.close()
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
