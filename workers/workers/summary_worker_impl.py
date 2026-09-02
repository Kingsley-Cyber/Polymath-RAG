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


def _job_done(conn: Connection, stage: str, input_hash: str) -> bool:
    """SUMMARY-IDEMPOTENCY-V1: has this WORK been done, regardless of
    which run asked?

    This used to check by ticket_id, and the ticket id is derived from
    the run (_stage_ticket), so it never matched across runs — every
    run re-executed every parent. MEASURED: 21,315 tickets for 3,025
    distinct input_hash values. The logical identity of summary work is
    (stage, input_hash): same inputs, same contract, same answer.
    """
    row = conn.execute(
        "SELECT state FROM summary_jobs WHERE stage=%s AND input_hash=%s",
        (stage, input_hash)).fetchone()
    return bool(row and row[0] == "COMPLETE")


def _ensure_job(conn: Connection, ticket_id: str, stage: str,
                corpus_id: str, input_hash: str) -> None:
    # SUMMARY-JOB-IDEMPOTENCY-V1 (2026-09-02): summary_jobs' PRIMARY KEY is
    # ticket_id, but the only conflict arbiter here was (stage, input_hash).
    # A delete + re-ingest of identical bytes mints the SAME ticket ids
    # (content-addressed runs) with a NEW input_hash, so the insert hit
    # the pkey and parent_summary failed 3/3 attempts on Gambling. A
    # stale job for this ticket with a different input is superseded
    # first; the (stage, input_hash) upsert then behaves as before.
    conn.execute(
        "DELETE FROM summary_jobs WHERE ticket_id = %s "
        "AND input_hash IS DISTINCT FROM %s",
        (ticket_id, input_hash))
    conn.execute(
        """INSERT INTO summary_jobs (ticket_id, stage, corpus_id,
           input_hash, contract_version)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (stage, input_hash) DO UPDATE
              SET attempts = summary_jobs.attempts + 1""",
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


def _compiled_card(conn: Connection, parent_id: str) -> dict | None:
    """SUMMARY-COMPILER-V1: the parent's ACTIVE routing card, the single
    summary authority S2 consumes (no second summarizer here)."""
    row = conn.execute(
        """SELECT summary_id, variant, plain_summary, relations, keywords
             FROM retrieval_summaries
            WHERE parent_id = %s AND kind = 'section_retrieval_summary' AND active
            LIMIT 1""",
        (parent_id,)).fetchone()
    if not row:
        return None
    rel = row[3] if isinstance(row[3], list) else json.loads(row[3] or "[]")
    kw = row[4] if isinstance(row[4], list) else json.loads(row[4] or "[]")
    return {"summary_id": row[0], "variant": row[1], "plain_summary": row[2] or "",
            "relations": rel, "keywords": kw}


def _do_parents(conn: Connection, run_id: str) -> dict:
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    docs = _run_docs(conn, run_id)
    done = 0
    for pid, slot in _parents_of_docs(conn, docs).items():
        facts = _facts_for_chunks(conn, slot["chunk_ids"])
        entities = _mentions_for_chunks(conn, slot["chunk_ids"])
        compiled = _compiled_card(conn, pid)
        children_text = "\n".join(c["text"] for c in slot["children"])
        input_hash = "in_" + _content_hash({
            "parent": pid, "children": children_text,
            "facts": sorted(json.dumps(f, sort_keys=True) for f in facts),
            "entities": sorted(e["surface"] for e in entities),
            "card": compiled["summary_id"] if compiled else None,
        })
        ticket = _stage_ticket(conn, run_id, "parent_summary") + ":" + pid[-16:]
        if _job_done(conn, "PARENT_SUMMARY", input_hash):
            continue
        _ensure_job(conn, ticket, "PARENT_SUMMARY", corpus, input_hash)
        res = run_parent_summary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus, parent_id=pid,
            input_hash=input_hash, contract_version=CONTRACT_VERSION,
            worker_id="summary-worker", parent_text=children_text,
            children=slot["children"], facts=facts, entities=entities,
            source_ids=list(slot["chunk_ids"]), compiled=compiled)
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
              WHERE ps.corpus_id=%s AND ps.superseded_at IS NULL""",
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
        if _job_done(conn, "DOCUMENT_SUMMARY", input_hash):
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
    if not _job_done(conn, "CORPUS_MAPPING", input_hash):
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
                      FROM parent_summaries
                     WHERE corpus_id=%s AND superseded_at IS NULL""",
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
    if not _job_done(conn, "VOCABULARY_MAPPING", input_hash):
        _ensure_job(conn, ticket, "VOCABULARY_MAPPING", corpus, input_hash)
        run_vocabulary_ticket(
            conn, ticket_id=ticket, corpus_id=corpus, input_hash=input_hash,
            contract_version=CONTRACT_VERSION, worker_id="summary-worker",
            families=families)
    return {"status": "COMPLETE"}


def _do_enrichment(conn: Connection, run_id: str) -> dict:
    """LATENT-TRANSFER-LAYER-V1 Phase B — parent_enrichment.v1.

    OWNER-TRIGGERED (§0a): tickets for this stage are minted by the
    enrichment buttons, never by chain advancement. Transport is the
    PINNED cross-provider group (STAGE-PIN-V1) — never the extraction
    sharding. Idempotent on (stage, input_hash): a re-click enriches
    only parents whose children or contract changed. Event payload may
    carry doc_id to scope one document (§0a document button)."""
    from polymath_shared.latent.compiler import (
        ParentInput,
        compile_microbatched_with_hard_case,
    )
    from polymath_shared.latent.contract import (
        PRODUCTION_BOUNDS,
        QUALIFICATION_BOUNDS,
    )
    from polymath_shared.latent.runtime import (
        input_hash_for,
        persist_compiled_parent,
    )
    from polymath_shared.settings import get_settings

    settings = get_settings().worker
    if getattr(settings, "enrichment_provider", "disabled") == "disabled":
        return {"status": "DISABLED"}
    corpus = _corpus_of_run(conn, run_id)
    if not corpus:
        return {"status": "NO_CORPUS"}
    scope_doc = None
    row = conn.execute(
        "SELECT payload FROM outbox_events WHERE run_id=%s AND "
        "event_type='parent_enrichment.v1' ORDER BY event_id DESC LIMIT 1",
        (run_id,)).fetchone()
    if row and isinstance(row[0], dict):
        scope_doc = row[0].get("doc_id") or None
    docs = [scope_doc] if scope_doc else _run_docs(conn, run_id)
    bounds = (PRODUCTION_BOUNDS
              if getattr(settings, "enrichment_profile", "qualification")
              == "production" else QUALIFICATION_BOUNDS)
    ceiling = int(getattr(settings, "enrichment_input_token_ceiling", 6000))

    ready = invalid = existing = 0
    for doc in docs:
        parents: list[ParentInput] = []
        for pid, slot in _parents_of_docs(conn, [doc]).items():
            parents.append(ParentInput(
                parent_id=pid,
                children=[(c["id"], i, c["text"]) for i, c in
                          enumerate(slot["children"])]))
        if not parents:
            continue
        # ENRICH-ELIGIBILITY (fleet review, owner-blessed): never pay
        # cloud inference to abstract TOC/bibliography/front-matter —
        # the same deterministic region roles extraction already skips.
        from polymath_shared.region_role import is_noise as _is_noise
        _roles = dict(conn.execute(
            "SELECT chunk_id, region_role FROM chunks "
            "WHERE chunk_id = ANY(%s)",
            ([p.parent_id for p in parents],)).fetchall())
        _before = len(parents)
        parents = [p for p in parents
                   if not _is_noise(_roles.get(p.parent_id))]
        if _before - len(parents):
            log.info("enrichment eligibility: skipped %d noise "
                     "parent(s) of %d", _before - len(parents), _before)
        if not parents:
            continue

        # ENRICH-PARENT-SHARD-V1 (owner 2026-09-01 "it should be
        # smart"): the lane is chosen per PARENT, not per document —
        # every pin-group lane churns even on a single-document job.
        # Shard key = parent_id (deterministic: the same parent always
        # lands on the same lane, so its enrichment identity stays
        # stable across retries); 429 ladder = backoff -> same lane ->
        # the parent's ring-adjacent OTHER lane.
        from polymath_shared.llm_extraction.client import (
            LLMExtractionClient,
            _lane_limit,
        )
        from polymath_shared.llm_extraction.pool import (
            select_endpoint_for_stage as _sel,
        )

        _lane_clients: dict[str, LLMExtractionClient] = {}

        def _client_for(pid: str, offset: int = 0):
            ep = _sel("parent_enrichment", pid, ring_offset=offset)
            c = _lane_clients.get(ep.name)
            if c is None:
                c = LLMExtractionClient(
                    "cloud", url=ep.url, model=ep.model,
                    limiter_key=ep.limiter_key, api_key=ep.api_key,
                    cloud_opts=ep.cloud_opts)
                c.endpoint_name = ep.name
                _lane_clients[ep.name] = c
            return c

        def _complete(items, _doc=doc):
            import time as _time
            from concurrent.futures import ThreadPoolExecutor

            def _retryable(err):
                # 429 IS retryable/failover-able (measured 2026-08-31:
                # a conc-4 burst 429'd 30/40 AWS parents into durable
                # INVALID because 429 was missing from this set).
                return err in ("LIMITER_REFUSED", "HTTP_429") or \
                    (err or "").startswith(
                        ("HTTP_5", "Connect", "ReadTimeout"))

            def _one(item):
                item_id, system, user, max_tokens = item
                primary = _client_for(item_id)
                raw, err = primary.complete_one(
                    user, system_prompt=system, max_tokens=max_tokens)
                if err == "HTTP_429":           # backoff, retry same lane
                    _time.sleep(10.0)
                    raw, err = primary.complete_one(
                        user, system_prompt=system, max_tokens=max_tokens)
                if _retryable(err):
                    fb = _client_for(item_id, 1)
                    if fb.endpoint_name != primary.endpoint_name:
                        log.warning("enrichment lane failover: %s -> %s (%s)",
                                    primary.endpoint_name, fb.endpoint_name,
                                    err, extra={"error_code":
                                                "ENRICHMENT_LANE_FAILOVER"})
                        raw, err = fb.complete_one(
                            user, system_prompt=system,
                            max_tokens=max_tokens)
                        if err == "HTTP_429":
                            _time.sleep(10.0)
                            raw, err = fb.complete_one(
                                user, system_prompt=system,
                                max_tokens=max_tokens)
                return (item_id, raw, err)

            # width = SUM of the involved lanes' concurrency caps (each
            # lane still self-gates through its own AIMD limiter — this
            # is a pool sizing, never a schedule).
            involved: dict[str, LLMExtractionClient] = {}
            for item in items:
                c = _client_for(item[0])
                involved[c.endpoint_name] = c
            width = 0
            for c in involved.values():
                spec = _lane_limit("cloud", None if c.limiter_key ==
                                   "default" else c.limiter_key)
                width += max(1, spec.conc_cap or 2)
            width = max(1, min(width, len(items), 12))
            with ThreadPoolExecutor(max_workers=width) as pool:
                results = list(pool.map(_one, items))
            return results

        def _enrichment_done(ih: str) -> bool:
            # ROW-TRUTH-DONE (A3 follow-through): job-state alone lied —
            # a pre-fix run marked COMPLETE against an INVALID row and
            # the sweep skipped it forever. Done means: a READY row
            # exists, or the failure is a SOURCE condition no model can
            # repair. Everything else stays retryable on every sweep.
            from polymath_shared.latent.gate import (
                SEMANTIC_FAILOVER_INELIGIBLE,
            )
            row = conn.execute(
                "SELECT status, error_class FROM parent_enrichments "
                "WHERE input_hash=%s AND status IN ('READY','INVALID') "
                "ORDER BY (status='READY') DESC LIMIT 1", (ih,)).fetchone()
            if row is None:
                return _job_done(conn, "PARENT_ENRICHMENT", ih)
            if row[0] == "READY":
                return True
            return row[1] in SEMANTIC_FAILOVER_INELIGIBLE


        todo: list[ParentInput] = []
        hashes: dict[str, str] = {}
        for p in parents:
            from polymath_shared.latent.gate import source_hash as _sh
            ep_p = _sel("parent_enrichment", p.parent_id)
            ih = input_hash_for(_sh(p.children),
                                f"{ep_p.name}:{ep_p.model}")
            hashes[p.parent_id] = ih
            if _enrichment_done(ih):
                existing += 1
                continue
            todo.append(p)
        if not todo:
            continue

        def _complete_fb(items, _doc=doc):
            # SEMANTIC-FAILOVER-V1: the parent's OTHER lane, gate-
            # rejects only; one retry, re-gated identically.
            out = []
            for item_id, system, user, max_tokens in items:
                fb = _client_for(item_id, 1)
                if fb.endpoint_name == _client_for(item_id).endpoint_name:
                    out.append((item_id, "", "ENRICH_NO_RESPONSE"))
                    continue
                raw, err = fb.complete_one(
                    user, system_prompt=system, max_tokens=max_tokens)
                out.append((item_id, raw, err))
            return out

        def _complete_escape(items, _doc=doc):
            # ENRICH-HARD-CASE-V1: the bounded MINIMAL escape on the
            # parent's ring+2 lane — guaranteed cross-FAMILY in the
            # 4-lane pin group (the 7/67 lesson: ring-adjacent lanes
            # can be the same model family, so "both lanes rejected"
            # really meant "one family rejected twice").
            out = []
            for item_id, system, user, max_tokens in items:
                esc = _client_for(item_id, 2)
                if esc.endpoint_name in (
                        _client_for(item_id).endpoint_name,
                        _client_for(item_id, 1).endpoint_name):
                    out.append((item_id, "", "ENRICH_NO_RESPONSE"))
                    continue
                raw, err = esc.complete_one(
                    user, system_prompt=system, max_tokens=max_tokens)
                out.append((item_id, raw, err))
            return out

        _persisted: set = set()

        def _persist_ready_now(cp):
            # PER-BATCH PERSIST (owner 2026-09-01): READY parents land
            # in their OWN COMMITTED transaction the moment their batch
            # gates — a bounce or crash mid-document keeps every batch
            # already landed (four bounces today each threw away a
            # whole document's compiled work). INVALIDs wait for the
            # hard-case pass; EXISTING/dup upserts are idempotent.
            if cp.status != "READY" or cp.parent_id in _persisted:
                return
            ih = hashes.get(cp.parent_id)
            if ih is None:
                return
            from polymath_shared.db import tx as _ptx
            ticket = (_stage_ticket(conn, run_id, "parent_enrichment")
                      + ":" + cp.parent_id[-16:])
            ep_cp = _sel("parent_enrichment", cp.parent_id)
            with _ptx() as _c:
                _ensure_job(_c, ticket, "PARENT_ENRICHMENT", corpus, ih)
                persist_compiled_parent(
                    _c, corpus_id=corpus, doc_id=doc, compiled=cp,
                    input_hash=ih, provider=f"llm:{ep_cp.name}",
                    model=ep_cp.model)
                _c.execute(
                    "UPDATE summary_jobs SET state='COMPLETE', "
                    "completed_at=now() WHERE stage='PARENT_ENRICHMENT' "
                    "AND input_hash=%s", (ih,))
            _persisted.add(cp.parent_id)

        compiled, semantic_failovers, hard_recovered, hard_terminal = \
            compile_microbatched_with_hard_case(
                _complete, _complete_fb, _complete_escape, todo, bounds,
                ceiling, on_compiled=_persist_ready_now,
                # MICROBATCH-CONCURRENCY-V1: run batches concurrently
                # across the pinned lane group (parent-shard puts
                # different batches on different lanes; each lane still
                # self-gates through its own AIMD limiter). Live E2E
                # measured the sequential loop at ~5.3 parents/min —
                # a 2h49m tail for 884 parents with 5 lanes idle.
                max_concurrency=int(getattr(
                    settings, "enrichment_batch_concurrency", 5)))
        if semantic_failovers:
            log.warning(
                "enrichment semantic failover recovered %d parent(s) on "
                "the other lane", semantic_failovers,
                extra={"error_code": "ENRICHMENT_SEMANTIC_FAILOVER"})
        if hard_recovered:
            log.warning(
                "hard-case escape recovered %d parent(s) on the minimal "
                "contract (cross-family lane)", hard_recovered,
                extra={"error_code": "ENRICHMENT_HARD_CASE_RECOVERED"})
        if hard_terminal:
            log.warning(
                "%d parent(s) terminal ENRICH_HARD_CASE (three lanes "
                "rejected; sweeps will stop retrying)", hard_terminal,
                extra={"error_code": "ENRICHMENT_HARD_CASE_TERMINAL"})
        for cp in compiled:
            if cp.parent_id in _persisted:
                ready += 1                  # landed per-batch already
                continue
            ih = hashes[cp.parent_id]
            ticket = (_stage_ticket(conn, run_id, "parent_enrichment")
                      + ":" + cp.parent_id[-16:])
            _ensure_job(conn, ticket, "PARENT_ENRICHMENT", corpus, ih)
            ep_cp = _sel("parent_enrichment", cp.parent_id)
            res = persist_compiled_parent(
                conn, corpus_id=corpus, doc_id=doc, compiled=cp,
                input_hash=ih, provider=f"llm:{ep_cp.name}",
                model=ep_cp.model)
            state = "COMPLETE" if res["status"] in ("READY", "EXISTING")                 else "FAILED"
            conn.execute(
                "UPDATE summary_jobs SET state=%s, completed_at=now() "
                "WHERE stage='PARENT_ENRICHMENT' AND input_hash=%s",
                (state, ih))
            if res["status"] == "READY":
                ready += 1
            elif res["status"] == "EXISTING":
                existing += 1
            else:
                invalid += 1
    if ready:
        # Phase C hand-off: new READY enrichments need their two points
        # projected. Re-arm the run's project_qdrant ticket + event —
        # projection is receipt-incremental, so this re-embeds ONLY the
        # new latent rows, nothing else.
        conn.execute(
            """UPDATE stage_tickets SET status='ready', lease_owner=NULL,
                      lease_expires_at=NULL, updated_at=now()
                WHERE run_id=%s AND stage='project_qdrant'
                  AND status IN ('done','failed')""", (run_id,))
        conn.execute(
            """INSERT INTO outbox_events (run_id, event_type, payload,
                   idempotency_key)
               VALUES (%s,'project_qdrant.v1',%s,%s)
               ON CONFLICT (idempotency_key)
               DO UPDATE SET delivered_at=NULL""",
            (run_id, json.dumps({"run_id": run_id,
                                 "reason": "latent_projection"}),
             f"enrich-project:{run_id}"))
    log.info("parent enrichment settled", extra={
        "run_id": run_id[:20], "ready": ready, "invalid": invalid,
        "existing": existing})
    return {"status": "COMPLETE", "ready": ready, "invalid": invalid,
            "existing": existing}


_DISPATCH = {
    "parent_summary.v1": _do_parents,
    "document_summary.v1": _do_document,
    "corpus_summary.v1": _do_corpus,
    "vocabulary.v1": _do_vocabulary,
    "parent_enrichment.v1": _do_enrichment,
}


def process_event(conn: Connection, event: dict) -> None:
    handler = _DISPATCH.get(event.get("event_type"))
    if handler is None:
        return
    result = handler(conn, event["run_id"])
    log.info("summary stage executed", extra={
        "event_type": event.get("event_type"),
        "result": json.dumps(result)[:160]})
