"""Ingest TEST copy.md through the production path and produce the
full intelligence extraction report.

Runs inside ONE transaction using the v2 stack (kimi_v1 + frame lane +
syntax spacy), COMMITS (this corpus is real, persisted knowledge),
then reports from committed state.
"""
import base64
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

SRC = "/Users/king/Downloads/untitled folder/TEST copy.md"
CORPUS = "test-copy-v1"

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402


def main() -> dict:
    raw = Path(SRC).read_bytes()
    content_b64 = base64.b64encode(raw).decode()
    canonical = {
        "corpus_id": CORPUS,
        "source_name": Path(SRC).name,
        "media_type": "text/markdown",
        "content_b64": content_b64,
        "config": {},
    }

    from polymath_shared.intake_submission import submit_intake
    from polymath_shared.identity import content_hash
    from workers.intake_worker import process_event as intake_process
    from workers.extract_worker import process_event as extract_process

    # worker path uses positional cursors -> plain connection
    wconn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False)

    res = submit_intake(wconn, canonical)
    run_id, fresh = res["run_id"], not res["already_exists"]
    print(f"intake: run={run_id[:24]}… fresh={fresh}")

    # intake stage: materialize document + chunks (+ emit chunked.v1)
    intake_process(wconn, {"run_id": run_id, "event_type": "intake.v1",
                          "payload": canonical,
                          "idempotency_key": "replay-intake"})

    wcur = wconn.cursor()
    wcur.execute("""
        SELECT doc_id FROM documents WHERE corpus_id=%s AND source_name=%s""",
        (CORPUS, canonical["source_name"]))
    doc_id = wcur.fetchone()[0]
    wcur.execute("""
        SELECT payload::text FROM outbox_events
         WHERE run_id=%s AND event_type='chunked.v1'
         ORDER BY event_id LIMIT 1""", (run_id,))
    ev_payload = wcur.fetchone()[0]
    extract_process(wconn, {"run_id": run_id, "event_type": "chunked.v1",
                           "payload": json.loads(ev_payload),
                           "idempotency_key": "replay-extract"})
    wconn.commit()  # extraction durable
    wconn.close()
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"], autocommit=False,
                           row_factory=dict_row)
    cur = conn.cursor()

    # ---- measure committed intelligence ---------------------------------
    ents = cur.execute("""
        SELECT admission_class, count(*) FROM mentions WHERE doc_id=%s
        GROUP BY 1 ORDER BY 2 DESC""", (doc_id,)).fetchall()
    cands = cur.execute("""
        SELECT decision, reason, predicate, subject_surface, object_surface,
               trigger_surface, evidence_class
          FROM relation_candidates WHERE doc_id=%s ORDER BY decision""",
        (doc_id,)).fetchall()
    facts = cur.execute("""
        SELECT DISTINCT f.fact_id, f.predicate,
               sn.normalized_surface AS subject,
               no.normalized_surface AS object
          FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id
          JOIN entities sn ON sn.entity_id=f.subject_id
          JOIN entities no ON no.entity_id=f.object_id
         WHERE ev.doc_id=%s ORDER BY 2, 3""", (doc_id,)).fetchall()
    evidence_n = cur.execute(
        "SELECT count(*) FROM evidence WHERE doc_id=%s",
        (doc_id,)).fetchone()["count"]
    parents = cur.execute("""
        SELECT chunk_id, text FROM chunks WHERE doc_id=%s AND tier='parent'
         ORDER BY chunk_index""", (doc_id,)).fetchall()

    # ---- summaries + corpus map + vocabulary ----------------------------
    from polymath_shared.summary_runtime import run_parent_summary_ticket
    from polymath_shared.summary_workers import build_document_summary
    from polymath_shared.corpus_mapping import build_corpus_map
    from polymath_shared.vocabulary_mapping import build_concept_families

    facts_flat = [dict(f) | {"subject_surface": f["subject"],
                             "object_surface": f["object"]}
                  for f in facts]
    ent_surfaces = [r["surface"] for r in cur.execute("""
        SELECT DISTINCT surface FROM mentions WHERE doc_id=%s AND
        admission_class IN ('GLOBAL','CORPUS_SCOPED','DOCUMENT_SCOPED')""",
        (doc_id,)).fetchall()]

    parent_payloads = []
    for p in parents:
        pid, ptext = p["chunk_id"], p["text"]
        kids = cur.execute("""
            SELECT chunk_id, text FROM chunks WHERE parent_id=%s
             AND tier='child' ORDER BY chunk_index""", (pid,)).fetchall()
        ticket = "tc_ps_" + pid[-12:]
        cur.execute("""
            INSERT INTO summary_jobs (ticket_id, stage, corpus_id, parent_id,
              input_hash, contract_version)
            VALUES (%s,'PARENT_SUMMARY',%s,%s,%s,'v2-report')
            ON CONFLICT (ticket_id) DO NOTHING""",
            (ticket, CORPUS, pid, "rep_" + pid[-16:]))
        r = run_parent_summary_ticket(
            conn, ticket_id=ticket, corpus_id=CORPUS, parent_id=pid,
            input_hash="rep_" + pid[-16:], contract_version="v2-report",
            worker_id="ingest-report", parent_text=ptext,
            children=[{"id": k["chunk_id"], "text": k["text"]}
                      for k in kids],
            facts=facts_flat,
            entities=[{"surface": s} for s in ent_surfaces],
            source_ids=[k["chunk_id"] for k in kids] or [pid])
        if r.get("status") in ("COMPLETE", "EXISTING"):
            row = cur.execute("""
                SELECT entities, concepts, summary FROM parent_summaries
                 WHERE summary_id=%s""", (r["summary_id"],)).fetchone()
            parent_payloads.append({
                "payload": {"parent_id": pid, "entities": row["entities"],
                            "concepts": row["concepts"],
                            "summary": row["summary"]},
                "artifact_id": r["summary_id"]})
    conn.commit()

    doc_env = build_document_summary(document_id=doc_id, title=canonical["source_name"],
                                     parent_summaries=parent_payloads)
    ds = {"summary_id": "dsum_" + doc_id[-12:], "document_id": doc_id,
          **doc_env["payload"], "evidence_density": 0.9,
          "methods": sorted({f["predicate"] for f in facts})}
    cmap = build_corpus_map(corpus_id=CORPUS, document_summaries=[ds])
    vocab = build_concept_families(
        corpus_id=CORPUS, parent_summaries=parent_payloads,
        document_summaries=[ds],
        accepted_concepts=[c["item"] for c in cmap.get("concepts", [])])

    report = {
        "corpus": CORPUS, "document_id": doc_id,
        "source": SRC,
        "entities_by_admission_class": {m["admission_class"]: m["count"]
                                        for m in ents},
        "candidate_funnel": {c["decision"]: sum(
            1 for x in cands if x["decision"] == c["decision"])
            for c in cands},
        "admitted_facts": [
            {"subject": f["subject"].title() if f["subject"].islower()
             else f["subject"],
             "predicate": f["predicate"],
             "object": f["object"].title() if f["object"].islower()
             else f["object"]}
            for f in facts],
        "rejected_candidates": [
            {"subject": c["subject_surface"], "predicate": c["predicate"],
             "object": c["object_surface"], "reason": c["reason"][:90]}
            for c in cands if c["decision"] not in ("ACCEPT",)],
        "evidence_rows": evidence_n,
        "parent_summaries": [{"entities": pp["payload"]["entities"],
                              "summary": pp["payload"]["summary"][:160]}
                             for pp in parent_payloads],
        "document_summary": {"major_entities": ds["major_entities"],
                             "major_concepts": ds["major_concepts"],
                             "methods": ds["methods"],
                             "summary": ds["summary"][:300]},
        "corpus_map": {
            "entities": [e["item"] for e in cmap.get("entities", [])],
            "predicates": [p["item"] for p in cmap.get("predicates", [])]},
        "vocabulary_families": vocab.get("families", []),
    }
    conn.close()
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
