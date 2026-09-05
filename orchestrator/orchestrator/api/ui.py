"""UI support layer (POLYMATH-UI-V1): the thin endpoints the web chat
needs on top of the existing query product.

  GET  /corpora            corpus picker data (docs, readiness, purpose)
  GET  /documents          file-manager listing for one corpus
  POST /upload             multipart upload → SPOOL-CLAIM-CHECK-V1:
                           bytes stream to the spool volume, the
                           canonical intake payload carries a content
                           reference (same submit_intake writer path
                           as /intake; Postgres never holds the bytes)
  GET  /synthesizers       model-selector data (the answer synthesizer
                           registry; deterministic grounded synthesis is
                           the only production entry today — the shape
                           is a list so future synthesizers slot in)
  POST /chat/stream        SSE: the SAME retrieval/synthesis machinery
                           as /chat, with phase events emitted between
                           the real pipeline steps (scope → retrieve →
                           graph → assemble → synthesize → answer) so
                           the UI can show what the engine is actually
                           doing, plus the retrieved-chunk inventory in
                           the final event.

No new semantics anywhere: every phase event wraps an existing call;
the final answer is byte-identical to what /chat (or /ask) returns.
Scope stays fail-closed through the same shared resolver.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from polymath_shared.db import tx

router = APIRouter()

import os

OLLAMA_URL = os.environ.get("POLYMATH_OLLAMA_URL",
                            "http://127.0.0.1:11434")

#: STUDY-DEFAULT-2026-08-27. New chats inherit the FIRST list entry
#: (frontend App.tsx uses synths[0]). The default is the fastest
#: capable LLM present (measured TTFT over this corpus: deepseek-v4-
#: flash 3.6 s vs kimi-k2.7 7.8 s), overridable without a deploy.
#:
#: The deterministic stitcher (`deterministic-template-v3`) is no
#: longer OFFERED (owner request 2026-08-27): its verbatim quote
#: assembly is audit output, not an answer. The execution path is kept
#: for API callers that name it explicitly.
_PREFERRED_DEFAULT = os.environ.get(
    "POLYMATH_DEFAULT_SYNTHESIZER", "ollama:deepseek-v4-flash:cloud")


def _ollama_models() -> list[dict]:
    """Live model list from the local Ollama daemon (non-fatal)."""
    import httpx

    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return [
            {"id": f"ollama:{m['name']}",
             "label": f"Ollama · {m['name']}",
             "description": "LLM generation over the retrieved evidence "
                            "(answers are GENERATED, not claim-validated).",
             "kind": "ollama"}
            for m in (r.json().get("models") or [])
        ]
    except Exception:
        return []


@router.get("/corpora")
def corpora(all: bool = False) -> dict:
    with tx() as conn:
        # independent aggregates: joining documents AND runs onto
        # corpora cross-multiplies (measured: 60s+ on 12k runs)
        rows = conn.execute(
            """
            SELECT c.corpus_id, c.purpose, c.query_enabled,
                   COALESCE(d.docs, 0),
                   COALESCE(r.ready, 0) > 0,
                   c.name
              FROM corpora c
              LEFT JOIN (SELECT corpus_id, COUNT(*) AS docs
                           FROM documents GROUP BY corpus_id) d
                     ON d.corpus_id = c.corpus_id
              LEFT JOIN (SELECT corpus_id, COUNT(*) AS ready
                           FROM runs WHERE status = 'query_ready'
                          GROUP BY corpus_id) r
                     ON r.corpus_id = c.corpus_id
             ORDER BY c.corpus_id
            """
        ).fetchall()
    # Default listing hides empty non-production corpora — right for
    # the chat picker, but the corpus MANAGER must see every row or
    # empty husks become invisible and undeletable (found as 8
    # stragglers the 2026-08-26 purge could not see). all=true lifts
    # the filter.
    return {"corpora": [
        {"corpus_id": r[0], "purpose": r[1], "query_enabled": r[2],
         "documents": r[3], "query_ready": r[4],
         "name": r[5] or r[0]}
        for r in rows if all or r[3] > 0 or r[1] == "production"
    ]}


class RenameCorpusRequest(BaseModel):
    name: str


@router.patch("/corpora/{corpus_id}")
def rename_corpus(corpus_id: str, req: RenameCorpusRequest) -> dict:
    """Rename a corpus's DISPLAY NAME only. `corpus_id` is immutable
    identity: it keys the FK chains, run scoping, and the derived
    Qdrant collection names — renaming identity would orphan the
    stores. The display name is presentation, safe to change freely."""
    name = req.name.strip()
    if not name:
        raise HTTPException(422, {
            "error_code": "invalid_name",
            "message": "name must be non-empty"})
    if len(name) > 120:
        raise HTTPException(422, {
            "error_code": "invalid_name",
            "message": "name must be 120 characters or fewer"})
    with tx() as conn:
        row = conn.execute(
            """UPDATE corpora SET name = %s, updated_at = now()
                WHERE corpus_id = %s
            RETURNING corpus_id, name""",
            (name, corpus_id)).fetchone()
        if not row:
            raise HTTPException(404, {
                "error_code": "QUERY_SCOPE_UNKNOWN",
                "message": f"corpus {corpus_id!r} not found"})
    return {"corpus_id": row[0], "name": row[1]}


class QueryEnableRequest(BaseModel):
    query_enabled: bool


@router.patch("/corpora/{corpus_id}/query_enabled")
def set_query_enabled(corpus_id: str, req: QueryEnableRequest) -> dict:
    """UI-V3 F13: the retrieval-visibility toggle, surfaced. Upload
    defaults hide new corpora (purpose='probe', query_enabled=false —
    QUERY-SCOPE-V1 by design); the owner hit that as "retrieval
    constantly fails". This flips ONLY query_enabled; purpose remains a
    separate governance decision."""
    with tx() as conn:
        row = conn.execute(
            """UPDATE corpora SET query_enabled = %s, updated_at = now()
                WHERE corpus_id = %s
            RETURNING corpus_id, query_enabled""",
            (req.query_enabled, corpus_id)).fetchone()
        if not row:
            raise HTTPException(404, {
                "error_code": "QUERY_SCOPE_UNKNOWN",
                "message": f"corpus {corpus_id!r} not found"})
    return {"corpus_id": row[0], "query_enabled": row[1]}


def _mint_enrichment(conn, corpus_id: str, doc_id: str | None) -> dict:
    """ENRICHMENT-BUTTON-V1 (§0a): shared mint (latent/trigger.py) —
    same path AUTO-ENRICH uses at promotion."""
    from polymath_shared.latent.trigger import mint_parent_enrichment
    run = conn.execute(
        """SELECT run_id FROM runs WHERE corpus_id=%s
            ORDER BY (status='query_ready') DESC, created_at DESC LIMIT 1""",
        (corpus_id,)).fetchone()
    if not run:
        raise HTTPException(404, {
            "error_code": "no_run_for_corpus",
            "message": f"corpus {corpus_id!r} has no runs to enrich"})
    return mint_parent_enrichment(conn, corpus_id=corpus_id,
                                  run_id=run[0], doc_id=doc_id)


@router.post("/corpora/{corpus_id}/enrich")
def enrich_corpus(corpus_id: str) -> dict:
    """§0a corpus button: enrich every document of the corpus."""
    with tx() as conn:
        out = _mint_enrichment(conn, corpus_id, None)
    return {"status": "queued", **out}


@router.post("/documents/{doc_id}/enrich")
def enrich_document(doc_id: str) -> dict:
    """§0a document button: enrich one document."""
    with tx() as conn:
        row = conn.execute(
            "SELECT corpus_id FROM documents WHERE doc_id=%s",
            (doc_id,)).fetchone()
        if not row:
            raise HTTPException(404, {
                "error_code": "unknown_document",
                "message": f"document {doc_id!r} not found"})
        out = _mint_enrichment(conn, row[0], doc_id)
    return {"status": "queued", **out}


@router.get("/documents/{doc_id}/sections")
def document_sections(doc_id: str) -> dict:
    """UI-V3 §4.2: the document -> section tree, straight from the
    compiled parent cards (retrieval_summaries, ONE-SUMMARY-AUTHORITY).
    Heading comes from the parent chunk's heading_path; NULL (legacy
    ingests) falls back to the card's summary head — the tree always
    renders (PRD §2)."""
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT rs.parent_id, rs.plain_summary, rs.summary_text,
                   rs.keywords, rs.coverage,
                   c.heading_path, c.chunk_index
              FROM retrieval_summaries rs
              LEFT JOIN chunks c ON c.chunk_id = rs.parent_id
             WHERE rs.doc_id = %s
               AND rs.kind = 'section_retrieval_summary' AND rs.active
             ORDER BY COALESCE(c.chunk_index, 0), rs.parent_id
            """,
            (doc_id,),
        ).fetchall()
        kids = dict(conn.execute(
            """SELECT parent_id, COUNT(*) FROM chunks
                WHERE doc_id = %s AND tier = 'child' GROUP BY parent_id""",
            (doc_id,),
        ).fetchall())
    sections = []
    for pid, plain, full, kw, cov, path_raw, idx in rows:
        if isinstance(path_raw, (list, tuple)):
            path = " › ".join(str(x) for x in path_raw if x)
        else:
            path = str(path_raw) if path_raw else ""
        summary = (plain or full or "").strip()
        title = (path.rsplit("›", 1)[-1].strip() if path
                 else (summary.split(". ")[0][:80] if summary else pid[:16]))
        sections.append({
            "parent_id": pid,
            "title": title,
            "heading_path": path,
            "summary": summary[:400],
            "keywords": (kw or [])[:8] if isinstance(kw, list) else [],
            "coverage": cov,
            "children": int(kids.get(pid, 0)),
        })
    return {"doc_id": doc_id, "sections": sections}


@router.get("/documents")
def documents(corpus_id: str) -> dict:
    with tx() as conn:
        row = conn.execute("SELECT 1 FROM corpora WHERE corpus_id=%s",
                           (corpus_id,)).fetchone()
        if not row:
            raise HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN",
                                      "message": f"corpus {corpus_id!r} not found"})
        # DOCUMENTS-LIST-SUBQUERY-V1 (measured 2026-09-05 on corpus `cinema`,
        # 67 documents / 79,787 chunks / 1,968 enrichments): the previous form
        # LEFT JOINed chunks AND parent_enrichments on the same document and
        # then DISTINCT-counted the cross product — chunks × enrichments rows
        # per document, 80 s per request, and the Files view showed nothing.
        # Correlated per-document counts use the (doc_id) indexes directly:
        # 25 ms on the same data, identical numbers.
        rows = conn.execute(
            """
            SELECT d.doc_id, d.source_name, d.media_type, d.byte_length,
                   d.created_at,
                   (SELECT COUNT(*) FROM chunks c
                     WHERE c.doc_id = d.doc_id AND c.tier = 'child') AS children,
                   (SELECT COUNT(DISTINCT c.parent_id) FROM chunks c
                     WHERE c.doc_id = d.doc_id AND c.tier = 'child') AS parents,
                   (SELECT COUNT(DISTINCT pe.parent_id) FROM parent_enrichments pe
                     WHERE pe.doc_id = d.doc_id AND pe.status = 'READY') AS enriched,
                   (SELECT COUNT(DISTINCT pe.parent_id) FROM parent_enrichments pe
                     WHERE pe.doc_id = d.doc_id AND pe.status = 'INVALID'
                       AND NOT EXISTS (SELECT 1 FROM parent_enrichments pr
                                        WHERE pr.parent_id = pe.parent_id
                                          AND pr.status = 'READY')) AS enrich_failed
              FROM documents d
             WHERE d.corpus_id = %s
             ORDER BY d.created_at DESC
            """,
            (corpus_id,)).fetchall()
        runs = conn.execute(
            """SELECT r.run_id, r.status, r.created_at,
                      COALESCE(
                        (SELECT re.error FROM receipts re
                          WHERE re.run_id = r.run_id
                            AND re.status = 'failed'
                            AND re.error IS NOT NULL
                          ORDER BY re.wall_clock DESC LIMIT 1),
                        (SELECT t.last_error_note FROM stage_tickets t
                          WHERE t.run_id = r.run_id
                            AND t.last_error_note IS NOT NULL
                          ORDER BY t.updated_at DESC LIMIT 1)
                      ) AS error
                 FROM runs r
                WHERE r.corpus_id = %s
                ORDER BY r.created_at DESC LIMIT 25""",
            (corpus_id,)).fetchall()
    return {
        "corpus_id": corpus_id,
        "documents": [
            {"doc_id": r[0], "source_name": r[1], "media_type": r[2],
             "bytes": r[3], "created_at": str(r[4]), "chunks": r[5],
             # UI-V3 enrichment indicator: parents vs READY vs
             # unrecovered INVALID — the doc ✨ button renders only
             # while remaining > 0
             "parents": r[6], "enriched": r[7], "enrich_failed": r[8]}
            for r in rows
        ],
        "runs": [{"run_id": r[0], "status": r[1], "created_at": str(r[2]),
                  "error": r[3]}
                 for r in runs],
    }


_UPLOAD_EXTENSIONS = {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}


@router.post("/upload")
async def upload(corpus_id: str = Form(...),
                 file: UploadFile = File(...)) -> dict:
    """SPOOL-CLAIM-CHECK-V1: stream to the spool volume in 1 MiB
    chunks (sha256 computed in flight), then submit the canonical
    intake payload carrying a content REFERENCE — the request body is
    transport, never pipeline state, and Postgres never holds the
    bytes. Same submit_intake writer path as /intake; run identity
    stays content-addressed via the sha256 inside the payload."""
    from polymath_shared.blob_spool import spool_write
    from polymath_shared.intake_submission import (
        canonical_intake_payload,
        submit_intake,
    )

    source_name = os.path.basename(file.filename or "") or "upload.bin"
    ext = os.path.splitext(source_name)[1].lower()
    if ext not in _UPLOAD_EXTENSIONS:
        raise HTTPException(
            422, f"unsupported extension {ext!r}; "
                 f"accepted: {sorted(_UPLOAD_EXTENSIONS)}")
    max_bytes = int(os.environ.get("POLYMATH_UPLOAD_MAX_MB", "200")) * 1024 * 1024

    # Starlette's multipart parser has already streamed the body to a
    # disk-spooled temp file in bounded chunks; file.file is its sync
    # handle. spool_write re-streams it in 1 MiB chunks, hashing in
    # flight — the bytes never sit in process memory as one buffer.
    import anyio
    file.file.seek(0, os.SEEK_END)
    if file.file.tell() > max_bytes:
        raise HTTPException(413, f"file exceeds {max_bytes} bytes")
    file.file.seek(0)
    ref = await anyio.to_thread.run_sync(spool_write, file.file)
    if ref["bytes"] == 0:
        raise HTTPException(422, "empty file")
    # DUPLICATE-DOCUMENT-GUARD-V1 layer 1 (byte-identical): the
    # uploaded file's raw sha256 matches documents.source_hash (the
    # original-bytes hash intake records), so this exact file —
    # whatever it is named — is already in the corpus. Refuse loudly
    # instead of minting a run that silently no-ops into the existing
    # content-addressed document. Layer 2 (same text, different
    # container format) lives in the intake worker where the extracted
    # text exists.
    with tx() as conn:
        dup = conn.execute(
            """SELECT source_name FROM documents
                WHERE corpus_id = %s AND source_hash = %s LIMIT 1""",
            (corpus_id, ref["sha256"])).fetchone()
    if dup:
        raise HTTPException(409, {
            "error_code": "duplicate_document",
            "message": f"this exact file is already in the corpus as "
                       f"{dup[0]!r}; upload skipped"})
    payload = canonical_intake_payload(
        corpus_id=corpus_id,
        source_name=source_name,
        media_type=file.content_type or "application/octet-stream",
        content_ref=ref,
    )
    with tx() as conn:
        out = submit_intake(conn, payload)
    return {**out, "corpus_id": corpus_id, "source_name": source_name,
            "bytes": ref["bytes"], "sha256": ref["sha256"]}


def _llm_provider_rows() -> list[dict]:
    """Configured LiteLLM providers (LLM-PROVIDER-LAYER-V1)."""
    with tx() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS llm_providers (
                 provider_id text PRIMARY KEY,
                 provider text NOT NULL,
                 api_key text NOT NULL DEFAULT '',
                 api_base text NOT NULL DEFAULT '',
                 models jsonb NOT NULL DEFAULT '[]',
                 enabled boolean NOT NULL DEFAULT true,
                 created_at timestamptz NOT NULL DEFAULT now())""")
        rows = conn.execute(
            """SELECT provider_id, provider, api_key, api_base, models,
                      enabled FROM llm_providers ORDER BY provider_id"""
        ).fetchall()
    return [{"provider_id": r[0], "provider": r[1], "api_key": r[2],
             "api_base": r[3], "models": r[4] or [], "enabled": r[5]}
            for r in rows]


def _litellm_models() -> list[dict]:
    out = []
    for row in _llm_provider_rows():
        if not row["enabled"]:
            continue
        for m in row["models"]:
            out.append({
                "id": f"litellm:{m}",
                "label": f"{row['provider']} · {m.split('/', 1)[-1]}",
                "description": "LLM generation over the retrieved evidence "
                               "via LiteLLM (answers are GENERATED, not "
                               "claim-validated).",
                "kind": "litellm",
            })
    return out


def _litellm_credentials(model: str) -> dict:
    """api_key/api_base for the configured provider owning this model
    string; first enabled provider listing the model wins."""
    for row in _llm_provider_rows():
        if row["enabled"] and model in row["models"]:
            cred = {}
            if row["api_key"]:
                cred["api_key"] = row["api_key"]
            if row["api_base"]:
                cred["api_base"] = row["api_base"]
            return cred
    return {}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, confirm: str = "") -> dict:
    """DELETE-LOCK-TIMEOUT-V1 wrapper: a bounded wait on in-flight stage
    locks, 409 `runs_in_flight` instead of a silent hang."""
    try:
        return _delete_document_tx(doc_id, confirm)
    except Exception as exc:                      # noqa: BLE001
        _raise_if_lock_timeout(exc, f"delete document {doc_id[:24]}")
        raise


def _delete_document_tx(doc_id: str, confirm: str = "") -> dict:
    """DOCUMENT-DELETE-V1: remove ONE document and everything derived
    from it — PG rows, its Qdrant points, its Neo4j substrate, its runs
    (so the same bytes are re-ingestable), and its projection receipts
    (CRITICAL: receipts without points would make a re-ingest skip
    re-embedding into a hole). Facts are removed only when no evidence
    remains from other documents. Typed confirmation required."""
    # UI-CONTRACT-FIX 2026-08-30: the confirm token is the doc_id OR the
    # source_name — a 64-char content hash is not human-typable, which made
    # the delete button look dead (silent no-op on mismatch). Also 400-class
    # for a bad confirm (409 was semantically wrong).
    # DELETE-WINS: cancel this document's in-flight stages first
    with tx() as _q:
        _quiesce_doc(_q, doc_id)
    removed: dict = {}
    with tx() as conn:
        _lock_timeout_or_409(conn, "delete document")
        row = conn.execute(
            "SELECT corpus_id, source_name FROM documents WHERE doc_id=%s",
            (doc_id,)).fetchone()
        if not row:
            raise HTTPException(404, {"error_code": "unknown_document",
                                      "message": doc_id})
        corpus_id, source_name = row
        if confirm not in (doc_id, source_name):
            raise HTTPException(400, {
                "error_code": "confirmation_required",
                "message": f"pass confirm='{doc_id}' or the file name "
                           f"'{source_name}' to delete this document"})
        chunk_ids = [r[0] for r in conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id=%s", (doc_id,)).fetchall()]

        def _del(sql, params, key, optional=False):
            if optional:
                conn.execute("SAVEPOINT docdel")
            try:
                removed[key] = removed.get(key, 0) + conn.execute(
                    sql, params).rowcount
            except Exception:
                if optional:
                    conn.execute("ROLLBACK TO SAVEPOINT docdel")
                    removed[key] = "skipped"
                else:
                    raise

        # facts evidenced ONLY by this document
        orphan_facts = [r[0] for r in conn.execute(
            """SELECT DISTINCT e.fact_id FROM evidence e
                WHERE e.doc_id=%s AND NOT EXISTS
                  (SELECT 1 FROM evidence e2
                    WHERE e2.fact_id=e.fact_id AND e2.doc_id<>%s)""",
            (doc_id, doc_id)).fetchall()]
        _del("DELETE FROM evidence WHERE doc_id=%s", (doc_id,), "evidence")
        if orphan_facts:
            _del("DELETE FROM facts WHERE fact_id = ANY(%s)",
                 (orphan_facts,), "facts")
        for tbl in ("relation_candidates", "mentions", "sentence_slices",
                    "document_layout", "raw_entity_proposals",
                    "raw_predicate_evidence", "extraction_trace_events"):
            _del(f"DELETE FROM {tbl} WHERE doc_id=%s", (doc_id,), tbl,
                 optional=True)
        # DELETE-PURGES-EXTRACTION-RECEIPTS (2026-09-02): the LLM call
        # receipts are content-addressed per (contract, neighborhood), so
        # leaving them made a deleted+re-ingested document REPLAY its old
        # raw output — correct, but every speed measurement lied and the
        # delete was not the clean slate it claims to be.
        _del("DELETE FROM extraction_call_receipts WHERE doc_id=%s",
             (doc_id,), "extraction_call_receipts", optional=True)
        # DELETE-PURGES-ENRICHMENTS (2026-09-02): parent_enrichments are
        # keyed by content-addressed parent ids; rows from a deleted
        # document survived and were reused by the re-ingest (identical
        # inputs → identical answers, so correct — but not a clean slate).
        _del("DELETE FROM parent_enrichments WHERE doc_id=%s",
             (doc_id,), "parent_enrichments", optional=True)
        if chunk_ids:
            # projection receipts for this document's chunks — MUST go
            # with the points, or re-ingest skips embedding them.
            _del("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                 (chunk_ids,), "projection_receipts", optional=True)
            _del("DELETE FROM projection_attempts WHERE entity_id = ANY(%s)",
                 (chunk_ids,), "projection_attempts", optional=True)
            _del("DELETE FROM parent_summaries WHERE parent_id = ANY(%s)",
                 (chunk_ids,), "parent_summaries", optional=True)
        # routing-summary points are keyed by summary_id, not chunk_id:
        # capture them BEFORE the rows go, or the Qdrant purge below misses
        # every document/section routing card (MEASURED 2026-08-30: 2,550
        # ghost routing cards in the production collection).
        summary_ids = [r[0] for r in conn.execute(
            "SELECT summary_id FROM retrieval_summaries WHERE doc_id=%s",
            (doc_id,)).fetchall()]
        _del("DELETE FROM retrieval_summaries WHERE doc_id=%s", (doc_id,),
             "retrieval_summaries", optional=True)
        _del("DELETE FROM document_summaries WHERE doc_id=%s", (doc_id,),
             "document_summaries", optional=True)
        _del("DELETE FROM chunks WHERE doc_id=%s", (doc_id,), "chunks")
        # runs that ingested this source into this corpus (+ their
        # control rows) so identical bytes re-ingest cleanly
        run_ids = [r[0] for r in conn.execute(
            """SELECT run_id FROM runs WHERE corpus_id=%s
                AND metadata->>'source_name' = %s""",
            (corpus_id, source_name)).fetchall()]
        if run_ids:
            # DELETE-PURGES-SUMMARY-JOBS (2026-09-02): summary_jobs rows are
            # keyed by '<stage ticket>:<parent suffix>' and outlived the
            # delete; identical bytes re-ingest under the SAME ticket ids
            # and collided on the pkey (parent_summary failed 3/3).
            _del("""DELETE FROM summary_jobs
                     WHERE split_part(ticket_id, ':', 1) IN
                           (SELECT ticket_id FROM stage_tickets
                             WHERE run_id = ANY(%s))""",
                 (run_ids,), "summary_jobs", optional=True)
            for tbl in ("stage_tickets", "outbox_events", "artifacts",
                        "receipts"):
                _del(f"DELETE FROM {tbl} WHERE run_id = ANY(%s)",
                     (run_ids,), tbl, optional=True)
            _del("DELETE FROM runs WHERE run_id = ANY(%s)", (run_ids,),
                 "runs")
        _del("DELETE FROM documents WHERE doc_id=%s", (doc_id,), "documents")

    # derived stores (best effort, reported)
    try:
        from polymath_shared.projection_contracts import qdrant_point_uuid
        from polymath_shared.stores import qdrant_client
        import hashlib as _h

        prefix = f"polymath_{_h.sha256(corpus_id.encode()).hexdigest()[:12]}_"
        client = qdrant_client(timeout=60)
        try:
            n = 0
            ids = ([qdrant_point_uuid(cid) for cid in chunk_ids]
                   + [qdrant_point_uuid(sid) for sid in summary_ids])
            for col in client.get_collections().collections:
                if col.name.startswith(prefix) and ids:
                    for i in range(0, len(ids), 512):
                        client.delete(collection_name=col.name,
                                      points_selector=ids[i:i + 512])
                        n += min(512, len(ids) - i)
            removed["qdrant_points"] = len(ids)
        finally:
            client.close()
    except Exception as exc:
        removed["qdrant_error"] = str(exc)[:120]
    try:
        from polymath_shared.stores import neo4j_driver

        with neo4j_driver() as driver:
            with driver.session() as s:
                out = s.run(
                    "MATCH (c:Chunk {doc_id: $d}) DETACH DELETE c "
                    "RETURN count(*) AS n", d=doc_id).single()
                removed["neo4j_chunks"] = out["n"] if out else 0
    except Exception as exc:
        removed["neo4j_error"] = str(exc)[:120]
    return {"deleted": doc_id, "source_name": source_name,
            "corpus_id": corpus_id, "removed": removed}


class GeneratedPage(BaseModel):
    name: str = "generated"
    html: str


@router.post("/generated")
def save_generated(req: GeneratedPage) -> dict:
    """GENERATED-LAUNCH-V1: persist a generated HTML artifact as a real
    file and serve it at a stable URL — unlike a blob: URL it survives
    refresh, can be bookmarked, and lives on disk
    (~/PolymathRuntime/polymath-v4/generated/)."""
    import hashlib as _h
    import re as _re
    from pathlib import Path

    if not req.html.strip():
        raise HTTPException(422, "html is empty")
    gen_dir = Path(os.environ.get(
        "POLYMATH_GENERATED_DIR",
        str(Path.home() / "PolymathRuntime" / "polymath-v4" / "generated")))
    gen_dir.mkdir(parents=True, exist_ok=True)
    slug = _re.sub(r"[^a-z0-9]+", "-", req.name.lower()).strip("-")[:48]         or "generated"
    digest = _h.sha256(req.html.encode()).hexdigest()[:10]
    fname = f"{slug}-{digest}.html"
    (gen_dir / fname).write_text(req.html)
    return {"url": f"/generated/{fname}", "file": str(gen_dir / fname)}


@router.get("/reasoning_modes")
def reasoning_modes() -> dict:
    """The v3.3 reasoning layer's curated modes for the UI dropdown,
    plus every raw template id for power-user blends."""
    from orchestrator.api.reasoning import CURATED_MODES, REASONING_TEMPLATES

    def _label(mode: str) -> str:
        return mode.replace("_", " ")

    return {
        "modes": [
            {"id": m, "label": _label(m),
             "description": (REASONING_TEMPLATES.get(m) or
                             "no template — model answers directly")
             .strip()[:160]}
            for m in CURATED_MODES
        ],
        "blend_pool": sorted(REASONING_TEMPLATES.keys()),
        "default": os.environ.get("POLYMATH_REASONING_MODE", "none"),
    }


@router.get("/ui_pulse")
def ui_pulse() -> dict:
    """UI-PRESENCE-WARMTH (2026-08-27). The frontend pings this while
    the tab is open and visible; the autopilot keeps the embedder
    resident while the signal is fresh, so the FIRST query of a session
    never pays the ~20 s sidecar cold start. Closing the app lets the
    signal age out and the model park as before."""
    with tx() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS runtime_signals (
                 key text PRIMARY KEY, updated_at timestamptz NOT NULL)""")
        conn.execute(
            """INSERT INTO runtime_signals VALUES ('ui_active', now())
               ON CONFLICT (key) DO UPDATE SET updated_at = now()""")
    return {"ok": True}


@router.get("/synthesizers")
def synthesizers() -> dict:
    entries = [*_litellm_models(), *_ollama_models()]
    # Move the preferred study default to the front (new chats take
    # synths[0]).
    for i, e in enumerate(entries):
        if e["id"] == _PREFERRED_DEFAULT:
            entries.insert(0, entries.pop(i))
            break
    if not entries:
        # Model daemons unreachable: still offer the preferred id so
        # the UI has something to submit; generation fails typed if it
        # is truly down.
        entries = [{
            "id": _PREFERRED_DEFAULT,
            "label": _PREFERRED_DEFAULT.split(":", 1)[-1],
            "description": "model daemon currently unreachable",
            "kind": _PREFERRED_DEFAULT.split(":", 1)[0],
        }]
    for e in entries:
        e["default"] = e["id"] == entries[0]["id"]
    return {"synthesizers": entries}


class ProviderUpsert(BaseModel):
    provider: str
    api_key: str = ""
    api_base: str = ""
    models: list[str] = []
    enabled: bool = True


@router.get("/llm/providers")
def llm_providers() -> dict:
    rows = _llm_provider_rows()
    for r in rows:  # never return raw keys to the browser
        r["api_key_set"] = bool(r["api_key"])
        r["api_key"] = (r["api_key"][-4:] if r["api_key"] else "")
    return {"providers": rows}


@router.post("/llm/providers")
def llm_provider_upsert(req: ProviderUpsert) -> dict:
    pid = req.provider.strip().lower()
    if not pid:
        raise HTTPException(422, "provider is required")
    _llm_provider_rows()  # ensure table
    with tx() as conn:
        existing = conn.execute(
            "SELECT api_key FROM llm_providers WHERE provider_id=%s",
            (pid,)).fetchone()
        # empty key on update keeps the stored key (masked round-trip)
        key = req.api_key or (existing[0] if existing else "")
        conn.execute(
            """INSERT INTO llm_providers
                 (provider_id, provider, api_key, api_base, models, enabled)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (provider_id) DO UPDATE SET
                 provider=EXCLUDED.provider, api_key=EXCLUDED.api_key,
                 api_base=EXCLUDED.api_base, models=EXCLUDED.models,
                 enabled=EXCLUDED.enabled""",
            (pid, req.provider.strip(), key, req.api_base.strip(),
             json.dumps([m.strip() for m in req.models if m.strip()]),
             req.enabled))
    return {"saved": pid}


@router.delete("/llm/providers/{provider_id}")
def llm_provider_delete(provider_id: str) -> dict:
    with tx() as conn:
        n = conn.execute("DELETE FROM llm_providers WHERE provider_id=%s",
                         (provider_id,)).rowcount
    return {"deleted": provider_id, "existed": bool(n)}


class LlmTest(BaseModel):
    model: str


@router.post("/llm/test")
def llm_test(req: LlmTest) -> dict:
    """One-shot connectivity/credential test for a configured model."""
    import litellm

    try:
        out = litellm.completion(
            model=req.model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=20, timeout=30, **_litellm_credentials(req.model))
        text = (out.choices[0].message.content or "").strip()
        return {"ok": True, "model": req.model, "reply": text[:80]}
    except Exception as exc:
        return {"ok": False, "model": req.model,
                "error": f"{type(exc).__name__}: {str(exc)[:220]}"}


def _lock_timeout_or_409(conn, what: str) -> None:
    """DELETE-LOCK-TIMEOUT-V1 (measured 2026-08-30): a stage transaction
    (extract holds one for the whole document, 12+ minutes) locks the
    run/ticket rows; a delete waited on them silently while the UI showed
    nothing. Bound the wait and say why."""
    conn.execute("SET LOCAL lock_timeout = '5s'")


def _raise_if_lock_timeout(exc: Exception, what: str) -> None:
    import psycopg

    if isinstance(exc, psycopg.errors.LockNotAvailable):
        raise HTTPException(409, {
            "error_code": "runs_in_flight",
            "message": f"{what}: a stage transaction holds locks on this "
                       "corpus (extraction in progress). Stop the workers "
                       "or wait for the stage to finish, then retry."})


def _quiesce_doc(conn, doc_id: str) -> None:
    """DELETE-WINS for a single document: supersede its in-flight tickets
    so workers stop claiming while the delete proceeds."""
    conn.execute(
        """UPDATE stage_tickets t
              SET status = 'superseded', lease_owner = NULL,
                  lease_expires_at = NULL
            WHERE t.status IN ('pending','ready','leased')
              AND t.run_id IN (SELECT run_id FROM outbox_events
                                WHERE event_type = 'chunked.v1'
                                  AND payload->>'doc_id' = %s)""",
        (doc_id,))


def _quiesce_corpus(conn, corpus_id: str) -> dict:
    """DELETE-WINS (owner directive 2026-08-30): a corpus delete must
    succeed even with stages in flight. Cancel every non-terminal ticket
    (superseded = unclaimable; the machinery already tolerates the
    status), drop leases, and SIGTERM the extract workers IF they hold
    this corpus's leases — their stage transactions roll back cleanly
    (idempotent stage design) and the supervisor respawns them into an
    empty claim queue. Returns a summary for the delete receipt."""
    import subprocess
    rows = conn.execute(
        """SELECT stage, status FROM stage_tickets
            WHERE corpus_id = %s AND status IN ('pending','ready','leased')""",
        (corpus_id,)).fetchall()
    leased_stages = sorted({r[0] for r in rows if r[1] == "leased"})
    conn.execute(
        """UPDATE stage_tickets
              SET status = 'superseded', lease_owner = NULL,
                  lease_expires_at = NULL
            WHERE corpus_id = %s AND status IN ('pending','ready','leased')""",
        (corpus_id,))
    kicked = 0
    if "extract" in leased_stages:
        # best-effort, single-box: respawned workers find no claimable tickets
        r = subprocess.run(["pkill", "-f", "workers.extract_worker"],
                           capture_output=True)
        kicked = 1  # pkill returns count-unstable across platforms; report act
    return {"tickets_cancelled": len(rows), "stages_leased": leased_stages,
            "workers_kicked": kicked}



@router.delete("/corpora/{corpus_id}")
def delete_corpus(corpus_id: str, confirm: str = "") -> dict:
    """OWNER-DESTRUCTIVE: remove a corpus and everything derived from
    it — PG rows, the Qdrant collection, and its Neo4j substrate.

    Guard: `confirm` must equal the corpus_id (the UI makes the user
    type it). Facts are content-addressed and can be evidenced from
    multiple corpora: fact rows are deleted ONLY when no evidence
    remains anywhere after this corpus's evidence is removed; shared
    entities are never touched."""
    if confirm != corpus_id:
        raise HTTPException(422, {
            "error_code": "confirmation_required",
            "message": "pass confirm=<corpus_id> to delete"})
    # DELETE-WINS: quiesce in-flight stages before touching rows so the
    # owner never waits out (or 409s on) running work.
    with tx() as _q:
        quiesce = _quiesce_corpus(_q, corpus_id)
    removed: dict[str, int] = {}
    try:
        return _delete_corpus_tx(corpus_id, removed)
    except Exception as exc:                      # noqa: BLE001
        _raise_if_lock_timeout(exc, f"delete corpus {corpus_id!r}")
        raise


def _delete_corpus_tx(corpus_id: str, removed: dict) -> dict:
    with tx() as conn:
        _lock_timeout_or_409(conn, "delete corpus")
        row = conn.execute("SELECT 1 FROM corpora WHERE corpus_id=%s",
                           (corpus_id,)).fetchone()
        if not row:
            raise HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN",
                                      "message": f"{corpus_id!r} not found"})
        doc_ids = [r[0] for r in conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s",
            (corpus_id,)).fetchall()]
        # PROJECTION-RECEIPT-PURGE-V2 (measured 2026-08-30): receipts are
        # keyed by the PROJECTED id — chunk ids, but also routing-card
        # summary ids, procedure/concept ids, fact/evidence ids. The
        # corpus delete purged chunk/doc ids only, so 904 receipts
        # survived the collection drop; ids are content-addressed, so a
        # re-ingest would have seen them as current and skipped
        # re-embedding into a hole. Every projected id goes.
        projected_ids: list[str] = []
        for sql in (
            "SELECT summary_id FROM retrieval_summaries WHERE corpus_id=%s",
            "SELECT procedure_id FROM procedure_artifacts WHERE corpus_id=%s",
            "SELECT concept_id FROM concept_artifacts WHERE corpus_id=%s",
            "SELECT canonical_id::text FROM canonical_entities WHERE corpus_id=%s",
        ):
            try:
                conn.execute("SAVEPOINT ids_sp")
                projected_ids.extend(r[0] for r in conn.execute(sql, (corpus_id,)).fetchall())
                conn.execute("RELEASE SAVEPOINT ids_sp")
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT ids_sp")
                conn.execute("RELEASE SAVEPOINT ids_sp")
        run_ids = [r[0] for r in conn.execute(
            "SELECT run_id FROM runs WHERE corpus_id=%s",
            (corpus_id,)).fetchall()]
        chunk_ids = [r[0] for r in conn.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = ANY(%s)",
            (doc_ids,)).fetchall()] if doc_ids else []

        # facts to fully remove = facts whose ONLY evidence is here
        orphan_facts = [r[0] for r in conn.execute(
            """SELECT DISTINCT ev.fact_id FROM evidence ev
                WHERE ev.doc_id = ANY(%s)
                  AND NOT EXISTS (
                      SELECT 1 FROM evidence e2
                       WHERE e2.fact_id = ev.fact_id
                         AND NOT (e2.doc_id = ANY(%s)))""",
            (doc_ids, doc_ids)).fetchall()] if doc_ids else []

        def _del(sql: str, args: tuple, key: str,
                 optional: bool = False) -> None:
            # optional tables (schema drift) roll back to a savepoint so
            # one missing table cannot abort the whole transaction
            if optional:
                conn.execute("SAVEPOINT del_sp")
                try:
                    removed[key] = removed.get(key, 0) + \
                        conn.execute(sql, args).rowcount
                    conn.execute("RELEASE SAVEPOINT del_sp")
                except Exception:
                    conn.execute("ROLLBACK TO SAVEPOINT del_sp")
                    conn.execute("RELEASE SAVEPOINT del_sp")
            else:
                removed[key] = removed.get(key, 0) + \
                    conn.execute(sql, args).rowcount

        if doc_ids:
            _del("DELETE FROM evidence WHERE doc_id = ANY(%s)",
                 (doc_ids,), "evidence")
            if orphan_facts:
                _del("DELETE FROM facts WHERE fact_id = ANY(%s)",
                     (orphan_facts,), "facts")
            _del("DELETE FROM relation_candidates WHERE doc_id = ANY(%s)",
                 (doc_ids,), "relation_candidates")
            _del("DELETE FROM mentions WHERE doc_id = ANY(%s)",
                 (doc_ids,), "mentions")
            for t in ("span_hypotheses", "sentence_slices",
                      "document_layout", "raw_entity_proposals",
                      "raw_predicate_evidence", "extraction_trace_events"):
                _del(f"DELETE FROM {t} WHERE doc_id = ANY(%s)",
                     (doc_ids,), t, optional=True)
        if chunk_ids:
            _del("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                 (chunk_ids,), "projection_receipts")
        if doc_ids:
            _del("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                 (doc_ids,), "projection_receipts")
            _del("""DELETE FROM projection_receipts WHERE entity_id IN (
                        SELECT ev.evidence_id FROM evidence ev WHERE ev.doc_id = ANY(%s))""",
                 (doc_ids,), "projection_receipts", optional=True)
        if projected_ids:
            _del("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                 (projected_ids,), "projection_receipts")
        if orphan_facts:
            _del("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)",
                 (orphan_facts,), "projection_receipts", optional=True)
        for t, col in (("retrieval_summaries", "corpus_id"),
                       ("parent_summaries", "corpus_id"),
                       ("document_summaries", "corpus_id"),
                       ("corpus_summaries", "corpus_id"),
                       ("summary_artifacts", "corpus_id"),
                       ("summary_jobs", "corpus_id"),
                       ("concept_families", "corpus_id"),
                       ("procedure_artifacts", "corpus_id"),
                       ("concept_artifacts", "corpus_id"),
                       ("canonical_entities", "corpus_id"),
                       ("canonical_memberships", "corpus_id"),
                       ("canonicalization_decisions", "corpus_id")):
            _del(f"DELETE FROM {t} WHERE {col} = %s", (corpus_id,), t,
                 optional=True)
        if run_ids:
            for t in ("stage_tickets", "outbox_events", "artifacts",
                      "receipts", "stage_attempts", "projection_attempts",
                      "dead_letter_archive"):
                _del(f"DELETE FROM {t} WHERE run_id = ANY(%s)",
                     (run_ids,), t, optional=True)
        if chunk_ids:
            _del("DELETE FROM chunks WHERE chunk_id = ANY(%s)",
                 (chunk_ids,), "chunks")
        if doc_ids:
            _del("DELETE FROM documents WHERE doc_id = ANY(%s)",
                 (doc_ids,), "documents")
        _del("DELETE FROM runs WHERE corpus_id = %s", (corpus_id,), "runs")
        _del("DELETE FROM archived_corpora WHERE corpus_id = %s",
             (corpus_id,), "archived_corpora", optional=True)
        _del("DELETE FROM corpora WHERE corpus_id = %s", (corpus_id,),
             "corpora")

    # derived stores (best effort, reported)
    try:
        import hashlib as _hashlib

        from polymath_shared.stores import qdrant_client

        # Sweep by corpus-hash PREFIX, not by computed contract names:
        # computing names from the current contract registry left every
        # older-contract collection orphaned (77 found on 2026-08-26).
        # Collection names are polymath_<sha256(corpus_id)[:12]>_<...>,
        # so the prefix enumerates every projection this corpus ever
        # had, under any embedding contract.
        prefix = f"polymath_{_hashlib.sha256(corpus_id.encode()).hexdigest()[:12]}_"
        client = qdrant_client(timeout=30)
        try:
            for col in client.get_collections().collections:
                if col.name.startswith(prefix):
                    client.delete_collection(col.name)
                    removed["qdrant_collections"] = \
                        removed.get("qdrant_collections", 0) + 1
        finally:
            client.close()
    except Exception as exc:
        removed["qdrant_error"] = str(exc)[:120]  # type: ignore[assignment]
    try:
        from polymath_shared.stores import neo4j_driver

        d = neo4j_driver()
        try:
            with d.session() as s:
                out = s.run(
                    """MATCH (c:Chunk) WHERE c.doc_id IN $docs
                       DETACH DELETE c""", docs=doc_ids).consume()
                removed["neo4j_chunks"] = out.counters.nodes_deleted
                if orphan_facts:
                    out2 = s.run(
                        """MATCH ()-[r:REL]->() WHERE r.fact_id IN $fids
                           DELETE r""", fids=orphan_facts).consume()
                    removed["neo4j_rels"] = \
                        out2.counters.relationships_deleted
        finally:
            d.close()
    except Exception as exc:
        removed["neo4j_error"] = str(exc)[:120]  # type: ignore[assignment]

    return {"deleted": corpus_id, "removed": removed}


# ---------------------------------------------------------------- SSE

class HistoryTurn(BaseModel):
    role: str                              # "user" | "assistant"
    content: str


class CarriedChunk(BaseModel):
    locator: str
    preview: str = ""


class StreamChatRequest(BaseModel):
    message: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    workspace: Optional[str] = None
    all_authorized: bool = False
    mode: Optional[str] = "HYBRID"        # VECTOR|HYBRID|GRAPH|ASK
    latent: Optional[bool] = None         # LATENT-TRANSFER D10 flag
    synthesizer: Optional[str] = None  # None -> _PREFERRED_DEFAULT
    # v3.3 reasoning layer (orchestrator.api.reasoning): a mode key
    # from REASONING_TEMPLATES, plus an optional power-user blend.
    # None -> POLYMATH_REASONING_MODE env, default "none".
    reasoning: Optional[str] = None
    reasoning_blend: list[str] = []
    # LLM generation context: prior conversation turns and evidence
    # chunks carried from earlier answers in this chat, so a request
    # like "build a PBQ test from what we just studied" can use the
    # WHOLE session's retrieved material, not only this turn's.
    history: list[HistoryTurn] = []
    carry_context: list[CarriedChunk] = []


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


#: Grounding core: the non-negotiable evidence contract. The STYLE
#: layer appended below (POLYMATH_STYLE_PROMPT, ported verbatim from
#: polymath v3.3) governs the answer's visual grammar; where the two
#: conflict — notably citations — the grounding core wins.
_LLM_GROUNDING = """You are Polymath's generation layer over an \
evidence-first retrieval system. You receive EVIDENCE blocks retrieved \
from the user's own corpus (current turn + material carried from \
earlier turns of this session). Teach it, never inventory it.

Grounding rules (non-negotiable; they override anything below):
- Everything you assert must come from the provided evidence. Cite by \
appending the evidence tag — e.g. [S2] — at the END of the sentence or \
paragraph a claim comes from; use ONLY the [S#] tags given, never raw \
chunk ids or page guesses. Never interrupt a sentence with a citation, \
never open with boilerplate like "Based on the evidence in your corpus".
- If the user asks you to BUILD something (a quiz, a PBQ-style HTML \
test, flashcards, a study plan, code), build it fully, drawing the \
substance from the evidence. Emit complete artifacts (e.g., a full \
self-contained HTML document in an ```html code block).
- If the evidence does not contain what the user needs, say exactly \
what is missing instead of inventing facts.
- COMPLETENESS OVERRIDES BREVITY. When the user asks for ALL of \
something — every domain, the full list, each step — enumerate every \
item the evidence contains, verbatim and in order. Do not sample, \
summarise, or stop at the representative few; the length rules above \
are suspended for this case. Scan the WHOLE of each evidence block \
before you answer, including its final lines: structured lists are \
routinely split across blocks and continue in the next one. State \
explicitly which items the evidence does not cover, and never imply a \
list is complete when it is not.
- These answers are GENERATED and are labeled as such downstream; do \
not claim to be a validated source of truth."""


#: CORPUS-STYLE-V1 (plan P0.a, measured 2026-09-05): every cinema answer
#: ended with a "for the exam" note because the study framing lived in the
#: core prompt. The study layer is now a per-corpus style: `corpora.profile
#: ->> 'style'` when set, else the POLYMATH_STUDY_STYLE_CORPORA list (default
#: cysa-study-v1), else neutral.
_STUDY_LAYER = """Study framing for this corpus:
- The user is STUDYING this material; teach toward mastery.
- When the material has an exam angle (objectives, question formats, \
common traps), end with a brief "for the exam" note drawn from the \
evidence."""
_STYLES = ("neutral", "study")
_STYLE_CACHE: dict[str, tuple[float, str | None]] = {}


def _corpus_style_from_db(corpus_id: str) -> str | None:
    now = time.time()
    hit = _STYLE_CACHE.get(corpus_id)
    if hit and now - hit[0] < 60:
        return hit[1]
    style = None
    try:
        with tx() as conn:
            row = conn.execute("SELECT profile->>'style' FROM corpora WHERE corpus_id=%s",
                               (corpus_id,)).fetchone()
        style = (row[0] or None) if row else None
    except Exception:  # noqa: BLE001 — style is a preference, never an error
        style = None
    _STYLE_CACHE[corpus_id] = (now, style)
    return style


def _style_for(corpus_ids, lookup=None) -> str:
    """Answer style for a scope: explicit corpus profile > study list > neutral."""
    lookup = lookup or _corpus_style_from_db
    ids = [c for c in (corpus_ids or []) if c]
    for cid in ids:
        st = lookup(cid)
        if st in _STYLES:
            return st
    study = {c.strip() for c in os.environ.get("POLYMATH_STUDY_STYLE_CORPORA", "cysa-study-v1").split(",") if c.strip()}
    return "study" if any(c in study for c in ids) else "neutral"


def _llm_system_prompt(style: str = "neutral") -> str:
    """Grounding core + optional study layer + the v3.3 style layer + date
    context (the v3.3 freshness block minus its live-web lines — v4 has no
    web lane)."""
    from datetime import datetime

    from orchestrator.api.polymath_style import POLYMATH_STYLE_PROMPT

    current = datetime.now().astimezone()
    layer = f"\n\n{_STUDY_LAYER}" if style == "study" else ""
    return (
        f"{_LLM_GROUNDING}{layer}\n\n{POLYMATH_STYLE_PROMPT}\n\n"
        "Date and source freshness:\n"
        f"- Today's date is {current.strftime('%Y-%m-%d')} "
        f"({current.tzname() or 'local time'}). Interpret relative dates "
        "like today, latest, recent, current, yesterday, and last year "
        "against this date.\n"
        "- Do not reject older sources when they are primary, historical, "
        "or the user is asking about stable theory."
    )


#: EVIDENCE-TRUNCATION-V1 (2026-08-27). Each evidence item was cut to
#: 900 characters, but the production chunker targets 1,200 (measured
#: corpus average 1,197) — so roughly the last quarter of EVERY chunk
#: was silently withheld from the model. That decapitates exactly the
#: chunks whose value sits at the end: MEASURED, the CySA objectives
#: map chunk is 1,230 chars with subdomain 1.4 starting at character
#: 1,061 and 1.5 at 1,144 — retrieval delivered them, the prompt
#: builder deleted them, and the answer listed only 1.1-1.3.
#: 1,600 covers the chunk-size distribution with headroom.
# EVIDENCE-BUDGET-V2 (audit F10): 2,000 covers the measured chunk-size
# distribution (avg 1,197, target 1,200) with real headroom — 1,600 still
# clipped long-tail chunks whose value sits at the end. Item COUNT is the
# depth lever (plan v2 final caps); chars per item just stops truncation.
_EVIDENCE_TEXT_CHARS = int(
    os.environ.get("POLYMATH_EVIDENCE_TEXT_CHARS", "2000"))


_LEGEND_ITEMS = 48
_S_TAG_RE = __import__("re").compile(r"\[S(\d+)\]")
_LOC_CHUNK_RE = __import__("re").compile(r"^chunk:([A-Za-z0-9_]+)")


def _evidence_legend(bundle: dict) -> list[dict]:
    """The [S#] legend exactly as the prompt builder emits it: one entry per
    evidence item that carries a locator and text, in bundle order, capped
    at _LEGEND_ITEMS. Shared by _grounded_messages (prompt), the answer
    event (UI) and the query receipt (RETRIEVAL-FUNNEL-V1 `selected`)."""
    out: list[dict] = []
    for item in (bundle.get("evidence_bundle") or [])[:_LEGEND_ITEMS]:
        span = item.get("source_span") or {}
        loc = span.get("locator") or ""
        text = (span.get("text") or "")[:_EVIDENCE_TEXT_CHARS]
        if loc and text:
            m = _LOC_CHUNK_RE.match(str(loc))
            out.append({"tag": f"S{len(out) + 1}", "locator": loc,
                        "chunk_id": (m.group(1) if m else (item.get("source_chunk_id") or None)),
                        "doc_id": item.get("source_document_id"), "text": text})
    return out


def _cited_chunk_ids(answer_text: str, legend: list[dict]) -> list[str]:
    """Chunk ids behind the [S#] tags the model actually emitted (order of
    first citation, deduped). Tags outside the legend are ignored."""
    by_tag = {e["tag"]: e.get("chunk_id") for e in legend}
    out: list[str] = []
    for n in _S_TAG_RE.findall(answer_text or ""):
        cid = by_tag.get(f"S{n}")
        if cid and cid not in out:
            out.append(cid)
    return out


_COMPILER_FLAG_ENV = "POLYMATH_CHAT_COMPILER"          # off | shadow | on
#: a compiler call that has not answered in 6 s is a failed lane, not a wait
#: (measured 2026-09-05: a Gemini 503 arrived after a 24 s hang)
_COMPILER_HTTP_TIMEOUT_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_HTTP_TIMEOUT_S", "6.0"))


def _compiler_flag() -> str:
    v = (os.environ.get(_COMPILER_FLAG_ENV, "shadow") or "shadow").strip().lower()
    return v if v in ("off", "shadow", "on") else "shadow"


_COMPILER_LANE_COOLDOWN_S = float(os.environ.get("POLYMATH_CHAT_COMPILER_LANE_COOLDOWN_S", "120"))
_COMPILER_LANE_FAILED_AT: dict[str, float] = {}       # lane name -> last transport failure (process-local breaker)


def _lane_family(ep) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(getattr(ep, "url", "") or "").netloc or "?"
    except Exception:  # noqa: BLE001
        return "?"


def _compiler_attempt_order(endpoints: list, key: str, *, failed_at: dict | None = None,
                            now: float | None = None, cooldown_s: float = _COMPILER_LANE_COOLDOWN_S,
                            max_attempts: int = 3) -> list:
    """COMPILER-LANE-ORDER-V1: deterministic attempt list for one turn —
    the ring's home lane for `key`, then the first lane of a DIFFERENT
    provider family (a Gemini-wide 503 storm must not eat both attempts),
    then the ring neighbour. Lanes whose last transport failure is inside
    the cooldown are moved to the back (never dropped: if every lane is
    cold we still try). Pure over its inputs."""
    import hashlib
    if not endpoints:
        return []
    roster = sorted(endpoints, key=lambda e: e.name)
    digest = hashlib.blake2b((key or "").encode(), digest_size=8).digest()
    home_idx = int.from_bytes(digest, "big") % len(roster)
    home = roster[home_idx]
    order = [home]
    alt = next((e for e in roster if _lane_family(e) != _lane_family(home)), None)
    if alt is not None:
        order.append(alt)
    for step in range(1, len(roster)):
        e = roster[(home_idx + step) % len(roster)]
        if e not in order:
            order.append(e)
    failed_at = failed_at if failed_at is not None else _COMPILER_LANE_FAILED_AT
    now = time.time() if now is None else now
    cold = lambda e: (now - failed_at.get(e.name, -1e12)) < cooldown_s
    order = [e for e in order if not cold(e)] + [e for e in order if cold(e)]
    return order[:max_attempts]


def _compile_chat_plan(message: str, history, corpus_ids, *, session_key: str | None = None):
    """CHAT-INTENT-PLAN-V1 through the `chat_compiler` stage pin (plan §3.2):
    one cheap lane, one call, strict local validation, deterministic fallback.
    The lane is chosen per session key (ring), each lane self-gates through
    its own limiter. Never raises."""
    from polymath_shared.chat_plan import COMPILER_STAGE, compile_plan, fallback_plan
    try:
        from polymath_shared.llm_extraction.client import LLMExtractionClient
        from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin
        key = session_key or message[:64]
        pin = stage_pin(COMPILER_STAGE) or []
        endpoints = [e for e in cloud_endpoints() if e.name in pin]
        if not endpoints:
            return fallback_plan(message, reason="compiler_unavailable:no_active_lane")
        last = None
        # COMPILER-LANE-FAILOVER-V1 + COMPILER-LANE-ORDER-V1: a transport
        # failure (429/503/timeout) walks to the next attempt — home lane,
        # then a different provider family, then the ring neighbour — and
        # cools the failed lane for later turns; validation failures do not
        # retry (the same prompt would produce the same plan).
        for attempt_no, ep in enumerate(_compiler_attempt_order(endpoints, key), start=1):
            offset = attempt_no - 1
            client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key,
                                         api_key=ep.api_key, cloud_opts=ep.cloud_opts,
                                         timeout_s=_COMPILER_HTTP_TIMEOUT_S, max_attempts=1)
            client.endpoint_name = ep.name

            def _complete(system_prompt: str, user_prompt: str, max_tokens: int, _c=client):
                return _c.complete_one(user_prompt, system_prompt=system_prompt, max_tokens=max_tokens)
            plan = compile_plan(message, history, corpus_ids, _complete, model=f"{ep.name}:{ep.model}")
            plan.compiler["lane"] = ep.name
            plan.compiler["attempt"] = attempt_no
            if last is not None:
                plan.compiler["first_failure"] = last
            if not plan.fallback or not str(plan.compiler.get("reason", "")).startswith("transport:"):
                return plan
            _COMPILER_LANE_FAILED_AT[ep.name] = time.time()
            last = f"{ep.name}:{plan.compiler.get('reason')}"
        return plan
    except Exception as exc:  # noqa: BLE001 — a missing pin / dark lane is a receipted fallback
        return fallback_plan(message, reason=f"compiler_unavailable:{type(exc).__name__}")


def _record_stream_receipt(req, *, question: str, scope, wall_ms: float, ui_mode: str,
                           answer: str | None, meta: dict, error: str | None = None) -> None:
    """QUERY-RECEIPTS on the streaming path (plan §3.6). Best effort, never
    on the critical path; the UI's turns were previously invisible."""
    try:
        from polymath_shared.query_receipts import record_query_receipt
        corpora = list(getattr(scope, "corpus_ids", None) or [])
        kind_scope = getattr(scope, "mode", None)
        out = None if error else {"answer": answer or "", "meta": dict(meta or {}, mode=ui_mode)}
        record_query_receipt(tx, kind="chat_stream", question=question, req=req,
                             scope_corpora=corpora, scope_kind=(str(kind_scope).lower() if kind_scope else None),
                             wall_ms=wall_ms, out=out, error=error, client="ui-stream")
    except Exception:  # noqa: BLE001 — receipts never break a stream
        pass


def _grounded_messages(query: str, bundle: dict, graph_facts: list,
                       history, carry_context,
                       reasoning: str | None = None,
                       reasoning_blend: list[str] | None = None,
                       style: str = "neutral") -> list[dict]:
    """Shared grounded-prompt assembly for every LLM backend.

    `reasoning`/`reasoning_blend` apply the v3.3 reasoning layer
    (orchestrator.api.reasoning, ported verbatim): templates prepend to
    the user prompt after the RAG context is assembled — the exact
    v3.3 composition point."""
    # CITATION-TAGS-V1 (measured 2026-08-30): raw locators instructed as
    # citation labels leaked into answers as "[chunk 67313]" — the model
    # now cites stable [S1]..[Sn] tags; the legend maps tags back to the
    # real locators for the trace/UI.
    ev_lines: list[str] = []
    legend: list[str] = []
    for e in _evidence_legend(bundle):
        ev_lines.append(f"[{e['tag']}]\n{e['text']}")
        legend.append(f"[{e['tag']}] = {e['locator']}")
    for f in graph_facts[:20]:
        ev_lines.append(
            f"[fact:{f.get('fact_id', '')[:24]}] "
            f"{f.get('subject')} —{f.get('predicate')}→ {f.get('object')}")
    carried = [
        f"[{c.locator}]\n{c.preview}" for c in (carry_context or [])[:30]
        if c.preview
    ]
    context_block = ""
    if ev_lines:
        context_block += ("EVIDENCE (this turn):\n" + "\n---\n".join(ev_lines))
        context_block += ("\n\nSOURCE TAGS:\n" + "\n".join(legend))
    if carried:
        context_block += ("\n\nEVIDENCE (carried from earlier turns):\n"
                          + "\n---\n".join(carried))
    if not context_block:
        context_block = "EVIDENCE: none retrieved for this turn."
    messages = [{"role": "system", "content": _llm_system_prompt(style)}]
    for turn in (history or [])[-12:]:
        if turn.role in ("user", "assistant") and turn.content:
            messages.append({"role": turn.role,
                             "content": turn.content[:4000]})
    from orchestrator.api.reasoning import apply_reasoning

    user_content = apply_reasoning(
        f"{context_block}\n\nREQUEST:\n{query}",
        mode=reasoning or os.environ.get("POLYMATH_REASONING_MODE", "none"),
        blend=reasoning_blend)
    messages.append({"role": "user", "content": user_content})
    return messages


def _litellm_generate(model: str, query: str, bundle: dict,
                      graph_facts: list, history, carry_context,
                      reasoning: str | None = None,
                      reasoning_blend: list[str] | None = None,
                      style: str = "neutral"):
    """LLM-PROVIDER-LAYER-V1: stream tokens from ANY provider through
    LiteLLM (OpenAI-format model strings: openai/gpt-4o,
    anthropic/claude-..., gemini/..., groq/..., ollama/...). Credentials
    come from the configured provider row; grounding prompt identical to
    the Ollama path. Yields {'token': str} or one {'error': ...}."""
    import litellm

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend, style=style)
    try:
        stream = litellm.completion(
            model=model, messages=messages, stream=True, timeout=300,
            **_litellm_credentials(model))
        for chunk in stream:
            piece = ""
            rpiece = ""
            try:
                delta = chunk.choices[0].delta
                piece = delta.content or ""
                # REASONING-STREAM-V1: providers that expose model
                # thinking surface it as reasoning_content.
                rpiece = getattr(delta, "reasoning_content", None) or ""
            except Exception:
                piece = ""
            if rpiece:
                yield {"reasoning": rpiece}
            if piece:
                yield {"token": piece}
    except Exception as exc:
        yield {"error": True, "error_code": "litellm_error",
               "message": f"{type(exc).__name__}: {str(exc)[:280]}"}
        return


def _ollama_generate(model: str, query: str, bundle: dict,
                     graph_facts: list, history, carry_context,
                     reasoning: str | None = None,
                     reasoning_blend: list[str] | None = None,
                     style: str = "neutral"):
    """Stream tokens from the local Ollama daemon over a grounded
    prompt. Yields {'token': str} pieces or one {'error': ...}.

    Prompt assembly is the SHARED builder — this function previously
    duplicated it inline, which let the two backends drift."""
    import httpx

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend, style=style)

    try:
        with httpx.stream(
                "POST", f"{OLLAMA_URL}/api/chat",
                # NO-THINK-CHAT-V1 (measured 2026-08-30): deepseek-v4-flash
                # via the daemon streams its reasoning INLINE as content
                # (the daemon cannot separate it for this model), so answers
                # opened with "The user is asking... Let me synthesize...".
                # Default off; POLYMATH_CHAT_THINK=on restores the
                # reasoning-card behavior for models that separate cleanly.
                json={"model": model, "messages": messages, "stream": True,
                      "think": os.environ.get("POLYMATH_CHAT_THINK", "off")
                               .lower() in ("1", "on", "true")},
                timeout=httpx.Timeout(300, connect=10)) as r:
            if r.status_code != 200:
                r.read()
                # REASONING-STREAM-V1: `think` is rejected by models
                # without a thinking mode — retry once without it
                # rather than failing the chat.
                if "think" in r.text.lower():
                    yield from _ollama_stream_plain(model, messages)
                    return
                yield {"error": True, "error_code": "ollama_error",
                       "message": r.text[:300]}
                return
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                if chunk.get("error"):
                    yield {"error": True, "error_code": "ollama_error",
                           "message": str(chunk["error"])[:300]}
                    return
                msg = chunk.get("message") or {}
                # REASONING-STREAM-V1: thinking tokens stream to the UI
                # reasoning card; they are never part of the answer.
                rpiece = msg.get("thinking", "")
                if rpiece:
                    yield {"reasoning": rpiece}
                piece = msg.get("content", "")
                if piece:
                    yield {"token": piece}
                if chunk.get("done"):
                    return
    except Exception as exc:
        yield {"error": True, "error_code": "ollama_unavailable",
               "message": f"{type(exc).__name__}: {exc}"[:300]}


def _ollama_stream_plain(model: str, messages: list[dict]):
    """Fallback stream without `think` for models that reject it."""
    import httpx

    try:
        with httpx.stream(
                "POST", f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
                timeout=httpx.Timeout(300, connect=10)) as r:
            if r.status_code != 200:
                r.read()
                yield {"error": True, "error_code": "ollama_error",
                       "message": r.text[:300]}
                return
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                if chunk.get("error"):
                    yield {"error": True, "error_code": "ollama_error",
                           "message": str(chunk["error"])[:300]}
                    return
                piece = (chunk.get("message") or {}).get("content", "")
                if piece:
                    yield {"token": piece}
                if chunk.get("done"):
                    return
    except Exception as exc:
        yield {"error": True, "error_code": "ollama_unavailable",
               "message": f"{type(exc).__name__}: {exc}"[:300]}


def _phase(stage: str, label: str, **detail) -> str:
    return _sse("phase", {"stage": stage, "label": label,
                          "t": round(time.time(), 3), **detail})


@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest) -> StreamingResponse:
    query = (req.message or "").strip()
    if not query:
        raise HTTPException(422, "message is required")
    ui_mode = (req.mode or "HYBRID").upper()
    if ui_mode == "VECTOR":
        ui_mode = "FAST"
    if ui_mode not in ("FAST", "HYBRID", "GRAPH", "ASK", "WILDCARD"):
        raise HTTPException(422, {"error_code": "unknown_mode",
                                  "message": f"mode {req.mode!r}"})
    synth = req.synthesizer or _PREFERRED_DEFAULT
    llm_model = None
    llm_backend = None
    if synth.startswith("ollama:"):
        llm_model, llm_backend = synth[len("ollama:"):], "ollama"
    elif synth.startswith("litellm:"):
        llm_model, llm_backend = synth[len("litellm:"):], "litellm"
    if synth != "deterministic-template-v3" and llm_model is None:
        raise HTTPException(422, {"error_code": "unknown_synthesizer",
                                  "message": f"{req.synthesizer!r}"})

    def generate():
        from polymath_shared.answer_synthesis import grounded_answer
        from polymath_shared.evidence_assembly import (
            AssemblyError,
            assemble_evidence_bundle,
        )

        from orchestrator.api.evidence import (
            _resolve_chunk,
            _resolve_document,
            _resolve_entity,
            _resolve_evidence_rows,
            _resolve_fact,
        )
        from orchestrator.api.retrieve import resolve_http_scope

        t0 = time.perf_counter()
        scope = None
        _trace: dict = {}
        _phase_ms: dict = {}
        _legend: list[dict] = []

        def _mark(name: str) -> None:
            _phase_ms[name] = round((time.perf_counter() - t0) * 1000, 1)
        try:
            yield _phase("scope", "Resolving query scope…")
            with tx() as conn:
                scope = resolve_http_scope(conn, req)
            yield _phase("scope_ok", "Scope resolved",
                         mode=scope.mode, corpora=list(scope.corpus_ids))
            # CHAT-INTENT-PLAN-V1 (plan P0.b): compile the turn. In `shadow`
            # the plan is receipted and shown but changes nothing downstream.
            _plan = None
            _plan_receipt: dict = {}
            _plan_future = None
            _flag = _compiler_flag()
            if _flag != "off":
                from concurrent.futures import ThreadPoolExecutor
                _session_key = (req.workspace or req.corpus_id or query[:64])
                _corpora = list(scope.corpus_ids)
                # SHADOW runs beside retrieval (no added latency, receipt
                # only); ON (P0.c) is the serial stage 0 the plan describes.
                _plan_future = ThreadPoolExecutor(max_workers=1).submit(
                    _compile_chat_plan, query, req.history, _corpora, session_key=_session_key)
                if _flag == "on":
                    _plan = _plan_future.result()
                    _plan_future = None
                    _mark("compile")
                    from polymath_shared.chat_plan import plan_receipt
                    _plan_receipt = plan_receipt(_plan)
                    yield _phase("compile", "Query compiled" if not _plan.fallback else "Query compiler fell back",
                                 task_type=_plan.task_type, retrieval_required=_plan.retrieval_required,
                                 queries=len(_plan.queries), fallback=_plan.fallback,
                                 mode=_flag, wall_ms=_plan.compiler.get("wall_ms"))

            def _join_plan():
                nonlocal _plan, _plan_receipt, _plan_future
                if _plan_future is not None:
                    from polymath_shared.chat_plan import plan_receipt
                    try:
                        _plan = _plan_future.result(timeout=8.0)
                    except Exception as exc:  # noqa: BLE001
                        from polymath_shared.chat_plan import fallback_plan
                        _plan = fallback_plan(query, reason=f"join_failed:{type(exc).__name__}")
                    _plan_future = None
                    _plan_receipt = plan_receipt(_plan)
                    _mark("compile_joined")

            if ui_mode == "ASK":
                yield _phase("ask", "Routing question over stored "
                                    "knowledge objects…")
                from orchestrator.api.ask import AskRequest, ask
                result = ask(AskRequest(
                    question=query, corpus_id=req.corpus_id,
                    corpus_ids=req.corpus_ids, workspace=req.workspace,
                    all_authorized=req.all_authorized))
                objs = result["objects"]
                counts = {k: len(v) for k, v in objs.items()}
                yield _phase("ask_done", "Stored objects retrieved",
                             counts=counts, route=result["route"])
                yield _sse("answer", {
                    "kind": "ask",
                    "result": result,
                    "retrieval": {
                        "mode": "ASK",
                        "evidence_count": sum(counts.values()),
                        "chunks": [],
                        "counts": counts,
                    },
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                })
                yield _sse("done", {})
                return

            corpus_id = scope.corpus_ids[0]
            if len(scope.corpus_ids) != 1:
                yield _sse("error", {
                    "error_code": "mode_requires_single_corpus",
                    "message": f"{ui_mode} retrieves over exactly one "
                               f"corpus; scope has {len(scope.corpus_ids)}"})
                return

            yield _phase("retrieve", f"{ui_mode} retrieval over "
                                     f"{corpus_id}…", mode=ui_mode)
            graph_facts: list = []
            latent_meta = None
            wildcard_lane = None
            if ui_mode == "GRAPH":
                from orchestrator.api.graph import graph_retrieve
                g = graph_retrieve(query, corpus_id, latent=req.latent)
                _trace = g.get("trace") or {}
                latent_meta = (g.get("meta") or {}).get("latent")
                evidence_rows = [
                    {"chunk_id": c["chunk_id"], "doc_id": d["doc_id"],
                     "parent_id": s["parent_id"]}
                    for d in g["documents"]
                    for s in d["sections"]
                    for c in s["evidence"]
                ]
                yield _phase("retrieve_done", "Dense + lexical evidence "
                             "selected",
                             evidence_count=len(evidence_rows),
                             lane_sizes=g["trace"].get("lane_sizes"))
                yield _phase("graph", "Expanding the canonical fact "
                                      "graph (hop-1)…")
                graph_facts = [
                    {"fact_id": f["fact_id"], "predicate": f["predicate"],
                     "subject": f["subject"], "object": f["object"]}
                    for f in g["graph_relationships"]
                ]
                yield _phase("graph_done",
                             f"{len(graph_facts)} canonical relationship(s)",
                             graph_fact_count=len(graph_facts),
                             relationships=graph_facts[:8])
                document_summaries = [
                    {"doc_id": d["doc_id"],
                     "summary": d["document_summary"] or ""}
                    for d in g["documents"] if d["document_summary"]
                ]
                section_summaries = [
                    {"chunk_id": s["parent_id"], "doc_id": d["doc_id"],
                     "summary": s["summary"] or ""}
                    for d in g["documents"] for s in d["sections"]
                ]
            else:
                wildcard_lane = None
                if ui_mode == "FAST":
                    from orchestrator.api.fast import fast_retrieve
                    fast = fast_retrieve(query, corpus_id)
                elif ui_mode == "WILDCARD":
                    # DIVERGENT-RETRIEVAL-V1: the answer evidence IS
                    # FAST (wildcard never displaces it); the bridges
                    # ride the separate `wildcard` lane.
                    from orchestrator.api.wildcard import wildcard_retrieve
                    fast = wildcard_retrieve(query, corpus_id)
                    wildcard_lane = fast.get("wildcard") or []
                else:
                    from orchestrator.api.hybrid import hybrid_fast_retrieve
                    fast = hybrid_fast_retrieve(query, corpus_id,
                                                latent=req.latent)
                latent_meta = (fast.get("meta") or {}).get("latent")
                _trace = fast.get("trace") or {}
                evidence_rows = [
                    {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                     "parent_id": c["parent_id"]}
                    for c in fast["evidence"]
                ]
                _mark("retrieve")
                yield _phase("retrieve_done", "Evidence selected",
                             evidence_count=len(evidence_rows),
                             lane_sizes=fast["trace"].get("lane_sizes"))
                if wildcard_lane is not None:
                    yield _phase(
                        "wildcard",
                        f"{len(wildcard_lane)} frontier bridge(s) beyond "
                        f"the obvious neighborhood",
                        bridges=len(wildcard_lane))
                document_summaries = [
                    {"doc_id": d["doc_id"],
                     "summary": (d.get("document_summary") or {}).get("text", "")}
                    for d in fast["selected_documents"]
                    if d.get("document_summary")
                ]
                parent_ids = [s["parent_id"]
                              for s in fast["selected_sections"]]
                with tx() as conn:
                    rows = conn.execute(
                        "SELECT chunk_id, doc_id, summary FROM chunks "
                        "WHERE chunk_id = ANY(%s)", (parent_ids,),
                    ).fetchall()
                section_summaries = [
                    {"chunk_id": r[0], "doc_id": r[1], "summary": r[2] or ""}
                    for r in rows
                ]

            yield _phase("assemble", "Assembling the evidence bundle…")
            stale: list[dict] = []
            try:
                bundle = assemble_evidence_bundle(
                    query, graph_facts, evidence_rows,
                    evidence_order=[c["chunk_id"] for c in evidence_rows],
                    resolve_fact=_resolve_fact,
                    resolve_evidence=_resolve_evidence_rows,
                    resolve_entity=_resolve_entity,
                    resolve_document=_resolve_document,
                    resolve_chunk=_resolve_chunk,
                    document_summaries=document_summaries,
                    section_summaries=section_summaries,
                    unresolved=stale,
                )
            except AssemblyError as exc:
                yield _sse("error", {"error_code": type(exc).__name__,
                                     "message": str(exc)[:300]})
                return
            _mark("assemble")
            _legend = _evidence_legend(bundle)
            yield _phase("assemble_done", "Bundle assembled",
                         items=len(bundle.get("evidence_bundle", [])))

            chunk_inventory = []
            seen = set()
            for item in bundle.get("evidence_bundle", []):
                span = item.get("source_span") or {}
                loc = span.get("locator") or ""
                cid = item.get("source_chunk_id") or loc
                if not loc or cid in seen:
                    continue
                seen.add(cid)
                pres = item.get("presentation") or {}
                chunk_inventory.append({
                    "locator": loc,
                    "doc_id": item.get("source_document_id"),
                    "kind": item.get("text_kind") or item.get("kind"),
                    "preview": (span.get("text") or "")[:220],
                    # UI-V3 §4.1: human identity for the Sources panel;
                    # raw locator/ids demote to the provenance expander.
                    "source_name": (item.get("applicability") or {}).get(
                        "source_name") or "",
                    "title": pres.get("title") or "",
                    "heading_path": pres.get("heading_path") or "",
                    "human_locator": pres.get("human_locator") or "",
                })
            from orchestrator.api.fast import degradations
            from polymath_shared.evidence_assembly import stale_projection_degradation

            retrieval = {
                "mode": "VECTOR" if ui_mode == "FAST" else ui_mode,
                "evidence_count": len(evidence_rows),
                "graph_fact_count": len(graph_facts),
                # LATENT-DIAGNOSTICS-V1 (roadmap B5): the survival
                # attribution frame the UI chip + P6 read.
                "latent": latent_meta,
                # DIVERGENT-RETRIEVAL-V1: labelled DERIVED insights with
                # their real source children attached (owner-blessed
                # §0b carve-out) — never part of `chunks` evidence.
                "wildcard": (wildcard_lane
                             if ui_mode == "WILDCARD" else None),
                "chunks": chunk_inventory,
                # NEVER-ERROR-ON-A-COLD-MODEL: a lane that degraded
                # (e.g. reranker parked behind extraction) still answers
                # — the UI says so instead of the query failing.
                "degraded": degradations() + stale_projection_degradation(stale),
            }

            if llm_model is not None:
                yield _phase("generate",
                             f"Generating with {llm_model}…",
                             model=llm_model,
                             carried=len(req.carry_context))
                full: list[str] = []
                _gen = (_litellm_generate if llm_backend == "litellm"
                        else _ollama_generate)
                _style = _style_for(list(getattr(scope, "corpus_ids", None) or []))
                retrieval["style"] = _style
                for tok in _gen(
                        llm_model, query, bundle, graph_facts,
                        req.history, req.carry_context,
                        req.reasoning, req.reasoning_blend, style=_style):
                    if tok.get("error"):
                        yield _sse("error", tok)
                        return
                    rpiece = tok.get("reasoning", "")
                    if rpiece:
                        # streams into the UI's reasoning card; never
                        # part of the recorded answer
                        yield _sse("reasoning", {"text": rpiece})
                    piece = tok.get("token", "")
                    if piece:
                        full.append(piece)
                        yield _sse("token", {"token": piece})
                _mark("generate")
                _join_plan()
                answer_text = "".join(full)
                from polymath_shared.funnel import funnel_from_trace
                used = _cited_chunk_ids(answer_text, _legend)
                funnel = funnel_from_trace(
                    _trace, selected=[e["chunk_id"] for e in _legend if e.get("chunk_id")],
                    cited=used, plan_version=(_trace or {}).get("plan"))
                retrieval["used_evidence"] = used
                retrieval["legend"] = [{"tag": e["tag"], "locator": e["locator"],
                                        "chunk_id": e.get("chunk_id"), "doc_id": e.get("doc_id")}
                                       for e in _legend]
                retrieval["funnel"] = {"version": funnel["version"], "counts": funnel["counts"],
                                       "lane_counts": funnel["lane_counts"], "multi_lane": funnel["multi_lane"]}
                if _plan_receipt:
                    retrieval["chat_plan"] = _plan_receipt
                    if _flag == "shadow" and _plan is not None:
                        yield _phase("compile", "Query compiled (shadow)" if not _plan.fallback else "Query compiler fell back (shadow)",
                                     task_type=_plan.task_type, retrieval_required=_plan.retrieval_required,
                                     queries=len(_plan.queries), fallback=_plan.fallback, mode=_flag,
                                     wall_ms=_plan.compiler.get("wall_ms"))
                _phase_ms["total"] = round((time.perf_counter() - t0) * 1000, 1)
                yield _sse("answer", {
                    "kind": "llm",
                    "result": {
                        "answer": answer_text,
                        "model": llm_model,
                        "meta": {
                            "verdict": "generated",
                            "abstained": False,
                            "synthesis_version": f"{llm_backend}:{llm_model}",
                            "phase_ms": dict(_phase_ms),
                        },
                    },
                    "retrieval": retrieval,
                    "latency_ms": round(
                        (time.perf_counter() - t0) * 1000, 1),
                })
                yield _sse("done", {})
                _record_stream_receipt(
                    req, question=query, scope=scope, wall_ms=_phase_ms["total"], ui_mode=retrieval.get("mode") or ui_mode,
                    answer=answer_text,
                    meta={"verdict": "generated", "synthesis_version": f"{llm_backend}:{llm_model}",
                          "model": llm_model, "latent": req.latent, "phase_ms": dict(_phase_ms),
                          "funnel": funnel, "used_evidence": used, "legend": retrieval["legend"],
                          "degraded": retrieval.get("degraded"), "plan": (_trace or {}).get("plan"),
                          "chat_plan": _plan_receipt or None})
                return

            yield _phase("synthesize", "Validating claims against "
                                       "evidence…")
            answer = grounded_answer(bundle, query)
            _mark("generate")
            _join_plan()
            from polymath_shared.funnel import funnel_from_trace
            used = []
            for c in (answer.get("citations") or []):
                for loc in (c.get("locators") or []):
                    m = _LOC_CHUNK_RE.match(str(loc))
                    if m and m.group(1) not in used:
                        used.append(m.group(1))
            funnel = funnel_from_trace(
                _trace, selected=[e["chunk_id"] for e in _legend if e.get("chunk_id")],
                cited=used, plan_version=(_trace or {}).get("plan"))
            retrieval["used_evidence"] = used
            retrieval["funnel"] = {"version": funnel["version"], "counts": funnel["counts"],
                                   "lane_counts": funnel["lane_counts"], "multi_lane": funnel["multi_lane"]}
            if _plan_receipt:
                retrieval["chat_plan"] = _plan_receipt
                if _flag == "shadow" and _plan is not None:
                    yield _phase("compile", "Query compiled (shadow)" if not _plan.fallback else "Query compiler fell back (shadow)",
                                 task_type=_plan.task_type, retrieval_required=_plan.retrieval_required,
                                 queries=len(_plan.queries), fallback=_plan.fallback, mode=_flag,
                                 wall_ms=_plan.compiler.get("wall_ms"))
            _phase_ms["total"] = round((time.perf_counter() - t0) * 1000, 1)
            yield _sse("answer", {
                "kind": "chat",
                "result": answer,
                "retrieval": retrieval,
                "latency_ms": _phase_ms["total"],
            })
            yield _sse("done", {})
            _record_stream_receipt(
                req, question=query, scope=scope, wall_ms=_phase_ms["total"], ui_mode=retrieval.get("mode") or ui_mode,
                answer=answer.get("answer"),
                meta={"verdict": (answer.get("meta") or {}).get("verdict"),
                      "synthesis_version": (answer.get("meta") or {}).get("synthesis_version"),
                      "latent": req.latent, "phase_ms": dict(_phase_ms), "funnel": funnel,
                      "used_evidence": used, "degraded": retrieval.get("degraded"),
                      "plan": (_trace or {}).get("plan"), "chat_plan": _plan_receipt or None})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {
                "message": str(exc.detail)}
            yield _sse("error", {"status": exc.status_code, **detail})
            _record_stream_receipt(req, question=query, scope=scope,
                                   wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode,
                                   answer=None, meta={}, error=f"HTTP {exc.status_code}: {str(detail)[:200]}")
        except Exception as exc:  # loud, typed-ish, never silent
            yield _sse("error", {"error_code": type(exc).__name__,
                                 "message": str(exc)[:300]})
            _record_stream_receipt(req, question=query, scope=scope,
                                   wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode,
                                   answer=None, meta={}, error=f"{type(exc).__name__}: {str(exc)[:200]}")

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
