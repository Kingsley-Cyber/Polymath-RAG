"""Summary-worker implementation: DB-driven input assembly + delegation
to the run_*_ticket contracts. See summary_worker.py (entrypoint)."""
from __future__ import annotations

import hashlib
import json
import logging

from psycopg import Connection

from polymath_shared.corpus_mapping import run_corpus_mapping_ticket
from polymath_shared.identity import content_hash
from polymath_shared.summary_runtime import (
    run_document_summary_ticket,
    run_parent_summary_ticket,
)
from polymath_shared.vocabulary_mapping import (
    build_concept_families,
    run_vocabulary_ticket,
)
from workers.summarizer import split_sentences

log = logging.getLogger("worker-summaries")

CONTRACT_VERSION = "admission-harbor-v2"


def _content_hash(obj) -> str:
    return content_hash(obj)


def _corpus_of_run(conn: Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT corpus_id FROM runs WHERE run_id=%s",
                       (run_id,)).fetchone()
    return row[0] if row else None


def _run_docs(conn: Connection, run_id: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT doc_id FROM documents d WHERE d.corpus_id="
        "(SELECT corpus_id FROM runs WHERE run_id=%s)", (run_id,)).fetchall()]


def _job_done(conn: Connection, ticket_id: str) -> bool:
    row = conn.execute(
        "SELECT state FROM summary_jobs WHERE ticket_id=%s",
        (ticket_id,)).fetchone()
    return bool(row and row[0] == "COMPLETE")


def _ensure_job(conn: Connection, ticket_id: str, stage: str,
                corpus_id: str, input_hash: str) -> None:
    conn.execute(
        """INSERT INTO summary_jobs (ticket_id, stage, corpus_id,
           input_hash, contract_version)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (ticket_id) DO NOTHING""",
        (ticket_id, stage, corpus_id, input_hash, CONTRACT_VERSION))


def _stage_ticket(conn: Connection, run_id: str, stage: str) -> str:
    """Same derivation as control.tickets.ticket_id, inlined so the
    worker layer never imports control internals (ownership rule)."""
    return "tkt_" + _content_hash(
        {"run": run_id, "stage": stage, "gen": 1})[:32]


# ---------------------------------------------------------------- parents

def _parents_of_docs(conn: Connection, docs: list[str]) -> dict[str, dict]:
    """parent_id -> {doc_id, children:[{id,text}], chunk_ids}"""
    out: dict[str, dict] = {}
    for doc in docs:
        rows = conn.execute(
            """SELECT chunk_id, parent_id, text FROM chunks
               WHERE doc_id=%s AND tier='child' AND parent_id IS NOT NULL
               ORDER BY chunk_index""", (doc,)).fetchall()
        for cid, pid, text in rows:
            slot = out.setdefault(pid, {"document_id": doc,
                                        "children": [],
                                        "chunk_ids": []})
            slot["children"].append({"id": cid, "text": text})
            slot["chunk_ids"].append(cid)
    return out


def _facts_for_chunks(conn: Connection, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT f.predicate, e1.normalized_surface,
                        e2.normalized_surface
          FROM evidence ev
          JOIN facts f ON f.fact_id::text = ev.fact_id
          JOIN entities e1 ON e1.entity_id = f.subject_id
          JOIN entities e2 ON e2.entity_id = f.object_id
         WHERE ev.chunk_id = ANY(%s)
        """,
        (chunk_ids,),
    ).fetchall()
    return [{"predicate": p, "subject_surface": s, "object_surface": o}
            for p, s, o in rows]


def _mentions_for_chunks(conn: Connection, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    rows = conn.execute(
        """SELECT DISTINCT surface, core_type FROM mentions
           WHERE chunk_id = ANY(%s) LIMIT 24""",
        (chunk_ids,),
    ).fetchall()
    return [{"surface": s, "core_type": c} for s, c in rows]


def _do_parents(conn: Connection, run_id: str) -> dict:
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    docs = _run_docs(conn, run_id)
    done = 0
    for pid, slot in _parents_of_docs(conn, docs).items():
        facts = _facts_for_chunks(conn, slot["chunk_ids"])
        entities = _mentions_for_chunks(conn, slot["chunk_ids"])
        children_text = "\n".join(c["text"] for c in slot["children"])
        input_hash = "in_" + _content_hash({
            "parent": pid, "children": children_text,
            "facts": sorted(json.dumps(f, sort_keys=True) for f in facts),
            "entities": sorted(e["surface"] for e in entities),
        })
        ticket = _stage_ticket(conn, run_id, "parent_summary") + ":" + pid[-16:]
        if _job_done(conn, ticket):
            continue
        _ensure_job(conn, ticket, "PARENT_SUMMARY", corpus, input_hash)
        res = run_parent_summary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus, parent_id=pid,
            input_hash=input_hash, contract_version=CONTRACT_VERSION,
            worker_id="summary-worker", parent_text=children_text,
            children=slot["children"], facts=facts, entities=entities,
            source_ids=list(slot["chunk_ids"]))
        if res.get("status") in ("COMPLETE", "EXISTING"):
            done += 1
    log.info("parent summaries settled", extra={
        "run_id": run_id[:20], "completed": done})
    return {"status": "COMPLETE", "parents_completed": done}


# --------------------------------------------------------------- document

def _do_document(conn: Connection, run_id: str) -> dict:
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    docs = _run_docs(conn, run_id)
    completed = 0
    for doc in docs:
        parents = conn.execute(
            """SELECT DISTINCT parent_id FROM chunks
               WHERE doc_id=%s AND tier='child' AND parent_id IS NOT NULL""",
            (doc,)).fetchall()
        if not parents:
            continue
        parent_ids = [p[0] for p in parents]
        ps_rows = conn.execute(
            """SELECT summary_id FROM parent_summaries ps
               JOIN unnest(%s::text[]) AS t(pid)
                 ON ps.parent_id = t.pid
              WHERE ps.corpus_id=%s""",
            (parent_ids, corpus)).fetchall()
        ps_ids = [r[0] for r in ps_rows]
        if len(ps_ids) < len(parent_ids):
            continue  # lineage incomplete; wait for parent stage
        title_row = conn.execute(
            "SELECT source_name FROM documents WHERE doc_id=%s",
            (doc,)).fetchone()
        preds = [r[0] for r in conn.execute(
            """SELECT DISTINCT f.predicate FROM facts f
               JOIN evidence ev ON ev.fact_id::text=f.fact_id
               WHERE ev.doc_id=%s AND f.decision='ACCEPT'""", (doc,)).fetchall()]
        n_events = conn.execute(
            "SELECT count(*) FROM evidence WHERE doc_id=%s",
            (doc,)).fetchone()[0]
        input_hash = "in_" + _content_hash({
            "doc": doc, "parents": sorted(ps_ids), "preds": sorted(preds),
            "events": n_events})
        ticket = _stage_ticket(conn, run_id, "document_summary") + \
            ":" + doc[-16:]
        if _job_done(conn, ticket):
            continue
        _ensure_job(conn, ticket, "DOCUMENT_SUMMARY", corpus, input_hash)
        res = run_document_summary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus, document_id=doc,
            input_hash=input_hash, contract_version=CONTRACT_VERSION,
            worker_id="summary-worker", parent_summary_ids=ps_ids,
            title=title_row[0] if title_row else "",
            accepted_predicates=preds, event_count=n_events,
            source_ids=ps_ids)
        if res.get("status") in ("COMPLETE", "EXISTING"):
            completed += 1
    return {"status": "COMPLETE", "documents_completed": completed}


# ------------------------------------------------------------------ corpus

def _do_corpus(conn: Connection, run_id: str) -> dict:
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    input_hash = "in_" + _content_hash({
        "corpus": corpus,
        "docs": sorted(r[0] for r in conn.execute(
            "SELECT document_id FROM document_summaries "
            "WHERE corpus_id=%s", (corpus,)).fetchall())})
    ticket = _stage_ticket(conn, run_id, "corpus_summary")
    if not _job_done(conn, ticket):
        _ensure_job(conn, ticket, "CORPUS_MAPPING", corpus, input_hash)
        run_corpus_mapping_ticket(
            conn, ticket_id=ticket, corpus_id=corpus,
            input_hash=input_hash, contract_version=CONTRACT_VERSION,
            worker_id="summary-worker")
    return {"status": "COMPLETE"}


# -------------------------------------------------------------- vocabulary

def _do_vocabulary(conn: Connection, run_id: str) -> dict:
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    # VOCABULARY-PRODUCTION-CONTRACT-V1: `support_id` is REQUIRED by
    # build_concept_families and must be the parent evidence
    # neighbourhood (parent_id), not the summary artifact. The
    # SUMMARY-WORKER-FLEET refactor moved this assembly from
    # payload-wrapped artifacts to a direct DB read and dropped
    # parent_id, so every row lost its support identity and the layer
    # silently produced zero families. Do not remove parent_id from
    # this SELECT.
    parents = [dict(zip(("summary_id", "support_id", "entities",
                         "concepts", "summary"), r))
               for r in conn.execute(
                   """SELECT summary_id, parent_id, entities, concepts, summary
                      FROM parent_summaries WHERE corpus_id=%s""",
                   (corpus,)).fetchall()]
    docs = [dict(zip(("summary_id", "major_entities", "major_concepts"), r))
            for r in conn.execute(
                """SELECT summary_id, major_entities, major_concepts
                   FROM document_summaries WHERE corpus_id=%s""",
                (corpus,)).fetchall()]
    accepted = sorted({c for p in parents for c in (p["concepts"] or [])})
    families = build_concept_families(
        corpus_id=corpus, parent_summaries=parents,
        document_summaries=docs, accepted_concepts=accepted)
    input_hash = "in_" + _content_hash({
        "corpus": corpus, "n_parents": len(parents),
        "families": json.dumps(families, sort_keys=True,
                               default=str)})
    ticket = _stage_ticket(conn, run_id, "vocabulary")
    if not _job_done(conn, ticket):
        _ensure_job(conn, ticket, "VOCABULARY_MAPPING", corpus, input_hash)
        run_vocabulary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus, input_hash=input_hash,
            contract_version=CONTRACT_VERSION, worker_id="summary-worker",
            families=families)
    return {"status": "COMPLETE"}


_DISPATCH = {
    "parent_summary.v1": _do_parents,
    "document_summary.v1": _do_document,
    "corpus_summary.v1": _do_corpus,
    "vocabulary.v1": _do_vocabulary,
}


def process_event(conn: Connection, event: dict) -> None:
    handler = _DISPATCH.get(event.get("event_type"))
    if handler is None:
        return
    result = handler(conn, event["run_id"])
    log.info("summary stage executed", extra={
        "event_type": event.get("event_type"),
        "result": json.dumps(result)[:160]})
