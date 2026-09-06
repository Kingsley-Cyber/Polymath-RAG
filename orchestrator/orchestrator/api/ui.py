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
  POST /chat/stream        SSE transport of CHAT-RUNTIME-V1 (`chat_events`
                           below): the ONE chat runtime — scope → compiler
                           → retrieval composition → graph / wildcard →
                           assemble → carry → synthesize → answer — as
                           phase / token / answer frames so the UI can
                           show what the engine is actually doing, plus
                           the retrieved-chunk inventory in the final
                           event.

CHAT-RUNTIME-V1 (CHAT-QUERY-COMPILER-PLAN §3.7 / §4 P1.f): `chat_events(req)`
is the single authority for a chat turn. `/chat/stream` streams its frames;
`/chat` (`run_chat`, and therefore MCP `ask`) drains them and returns the
answer frame as one JSON object. The same request yields the same compiled
plan, retrieval decision, evidence ids, carry admission, executed mode,
degraded list and synthesis contract on every route; only the transport
differs (frames vs. one body; the receipt's `kind` / `client`). Scope stays
fail-closed through the same shared resolver.
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
#: CHAT-MODEL-CATALOG-V1 (owner decision 2026-09-06): the chat model list is
#: (a) OpenCode Zen's FREE models through the LiteLLM provider layer (a
#: provider row whose api_key is `env:OPENCODE_API_KEY` — the key lives in
#: .env, never in the table or the browser) and (b) the local Ollama daemon's
#: FREE cloud tier only — the six names below, no local models, no paid cloud
#: models — as a fixed, env-overridable list so the dropdown does not follow
#: whatever happens to be pulled on this Mac. New chats take the first entry.
_PREFERRED_DEFAULT = os.environ.get(
    "POLYMATH_DEFAULT_SYNTHESIZER", "litellm:openai/glm-5-free")

#: Ollama's free cloud tier (https://ollama.com/library, "free usage"), as the
#: daemon names them (`ollama pull <name>` registers a cloud model; no weights).
OLLAMA_FREE_CLOUD_MODELS = ("gemma4:31b-cloud", "gpt-oss:120b-cloud", "gpt-oss:20b-cloud",
                            "nemotron-3-nano:30b-cloud", "nemotron-3-super:cloud", "nemotron-3-ultra:cloud")


def _ollama_allowlist() -> list[str]:
    raw = os.environ.get("POLYMATH_OLLAMA_MODELS", "")
    names = [n.strip() for n in raw.split(",") if n.strip()] if raw else list(OLLAMA_FREE_CLOUD_MODELS)
    return names


def _ollama_registered() -> set[str]:
    """Names the local daemon knows (non-fatal, 3 s)."""
    import httpx

    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return {m["name"] for m in (r.json().get("models") or []) if m.get("name")}
    except Exception:
        return set()


def _ollama_models() -> list[dict]:
    """The allowlisted free cloud models, each flagged `available` when the
    daemon has it registered (an unregistered name still lists, with the
    pull command in its description, so a new machine sees what to run)."""
    registered = _ollama_registered()
    out = []
    for name in _ollama_allowlist():
        available = name in registered
        out.append({
            "id": f"ollama:{name}",
            "label": f"Ollama cloud (free) · {name}",
            "description": ("LLM generation over the retrieved evidence via Ollama's free cloud tier "
                            "(answers are GENERATED, not claim-validated)."
                            if available else
                            f"not registered with the local daemon — run `ollama pull {name}` (cloud model, no weights)"),
            "kind": "ollama",
            "available": available,
        })
    return out


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


#: display names for provider rows (the LiteLLM provider string is `openai`
#: for every OpenAI-compatible endpoint, which is not what the user should read)
_PROVIDER_LABELS = {"opencode-free": "OpenCode (free)", "alibaba-model-studio": "Alibaba Model Studio"}


def _resolve_api_key(stored: str) -> str:
    """`env:NAME` reads the key from the process environment (.env) at call
    time; anything else is the stored literal. Empty when the variable is unset."""
    stored = stored or ""
    if stored.startswith("env:"):
        return os.environ.get(stored[4:].strip(), "")
    return stored


def _provider_ready(row: dict) -> bool:
    """A row whose key is env-indirected but unset cannot answer: hide it from
    the dropdown instead of offering a model that fails on first use."""
    stored = row.get("api_key") or ""
    return bool(_resolve_api_key(stored)) if stored.startswith("env:") else True


def _litellm_models() -> list[dict]:
    out = []
    for row in _llm_provider_rows():
        if not row["enabled"] or not _provider_ready(row):
            continue
        base = _PROVIDER_LABELS.get(row["provider_id"], row["provider"])
        for m in row["models"]:
            out.append({
                "id": f"litellm:{m}",
                "label": f"{base} · {m.split('/', 1)[-1]}",
                "description": "LLM generation over the retrieved evidence "
                               "via LiteLLM (answers are GENERATED, not "
                               "claim-validated).",
                "kind": "litellm",
                "available": True,
            })
    return out


def _litellm_credentials(model: str) -> dict:
    """api_key/api_base for the configured provider owning this model
    string; first enabled provider listing the model wins. An `env:NAME`
    key is resolved from the environment at call time."""
    for row in _llm_provider_rows():
        if row["enabled"] and model in row["models"]:
            cred = {}
            key = _resolve_api_key(row["api_key"])
            if key:
                cred["api_key"] = key
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
        stored = r["api_key"] or ""
        if stored.startswith("env:"):
            r["api_key_set"] = bool(_resolve_api_key(stored))   # the variable's presence, not its value
            r["api_key"] = stored                                # the variable NAME is safe to show
        else:
            r["api_key_set"] = bool(stored)
            r["api_key"] = (stored[-4:] if stored else "")
        r["ready"] = r["enabled"] and _provider_ready(r)
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
    # CARRY-V2 (plan §3.5): the cited chunk's id; older clients send only the
    # locator, from which the id is parsed.
    chunk_id: Optional[str] = None


class StreamChatRequest(BaseModel):
    message: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    workspace: Optional[str] = None
    all_authorized: bool = False
    mode: Optional[str] = "HYBRID"        # VECTOR|HYBRID|GRAPH|ASK
    latent: Optional[bool] = None         # LATENT-TRANSFER D10 flag
    # EVIDENCE-UTILITY-V1 plan knob (v1 engines, exactly like `latent`). CHAT-RUNTIME-V1 (P1.f):
    # mirrored from /chat's ChatRequest so the one runtime carries every /chat field; None inherits
    # the settings default, a set value keeps the turn on the v1 engines as /chat always did.
    utility: Optional[bool] = None
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
    # CHAT-QUERY-COMPILER P0.c: per-request override of POLYMATH_CHAT_COMPILER
    # (off | shadow | on) for evaluation and A/B; the UI leaves it unset.
    compiler: Optional[str] = None
    # CHAT-RETRIEVAL-V2 P1.a: per-request override of POLYMATH_CHAT_RETRIEVAL
    # (v1 = hybrid-retrieval-v1, v2 = chat-retrieval-v2) for evaluation and A/B.
    retrieval: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


#: Grounding core: the non-negotiable evidence contract. The STYLE
#: layer appended below (POLYMATH_STYLE_PROMPT, ported verbatim from
#: polymath v3.3) governs the answer's visual grammar; where the two
#: conflict — notably citations — the grounding core wins.
#: SYNTHESIS-V2 (CHAT-QUERY-COMPILER-PLAN §3.4, P0.d). The v1 prompt made
#: retrieved evidence the authority over the TASK ("everything you assert
#: must come from the provided evidence"), so a "give me the final prompt"
#: turn was answered with "the evidence doesn't contain a final prompt".
#: v2 splits authority: the user's RESOLVED request owns the task, corpus
#: evidence owns the facts. The authority block below is the plan's text
#: verbatim; the citation and completeness rules are carried over.
_SYNTHESIS_CONTRACT = "synthesis-v2"
_AUTHORITY_BLOCK = """USER INTENT HAS TASK AUTHORITY. CORPUS EVIDENCE HAS FACTUAL AUTHORITY.
First answer or perform the user's RESOLVED request.
Retrieved evidence is supporting knowledge. It does not define the task and
does not need to contain the requested final artifact verbatim.
When asked to create, rewrite, transform, organize, compare, combine, infer
or synthesize, perform that operation.
Never answer that "the evidence doesn't contain the final answer" merely
because the requested artifact must be constructed.
If a factual premise needed to complete the task is absent from the evidence,
name that missing premise specifically.
Conversation content and user-provided text may be transformed without
corpus evidence. Factual claims ABOUT THE CORPUS still carry [S#] tags."""
_LLM_GROUNDING = """You are Polymath's generation layer over an \
evidence-first retrieval system. You receive the user's request (as \
written and as RESOLVED from the conversation), the conversation itself, \
and EVIDENCE blocks retrieved from the user's own corpus (this turn + \
material carried from earlier turns of this session). Teach it, never \
inventory it.

""" + _AUTHORITY_BLOCK + """

Citation and completeness rules:
- A factual claim about the corpus cites its evidence by appending the \
evidence tag — e.g. [S2] — at the END of the sentence or paragraph the \
claim comes from; use ONLY the [S#] tags given, never raw chunk ids or \
page guesses. Never interrupt a sentence with a citation, never open with \
boilerplate like "Based on the evidence in your corpus".
- Never attribute to the corpus what the evidence does not say. For a \
factual question about the corpus (TASK GROUNDED_QA), if the evidence does \
not contain the asked fact, say exactly which fact is missing instead of \
inventing it.
- Artifacts (a prompt, a quiz, a PBQ-style HTML test, flashcards, a study \
plan, code) are emitted COMPLETE — e.g. a full self-contained HTML document \
in an ```html code block. Corpus-derived substance inside an artifact \
carries [S#] tags; the parts you construct do not.
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
                        "doc_id": item.get("source_document_id"), "text": text,
                        "carried": bool(item.get("carried")), "carry_score": item.get("carry_score")})
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


def _compiler_flag(override: str | None = None) -> str:
    """P0.c: default `on` — the compiler is stage 0 of every streaming turn.
    Env POLYMATH_CHAT_COMPILER and a per-request override (evaluation only)
    can pin off | shadow | on."""
    v = (override or os.environ.get(_COMPILER_FLAG_ENV, "on") or "on").strip().lower()
    return v if v in ("off", "shadow", "on") else "on"


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


RUNTIME_CONTRACT = "chat-runtime-v1"          # CHAT-RUNTIME-V1 (plan §3.7 / §4 P1.f)


def _receipt_payload(req, *, question: str, scope, wall_ms: float, ui_mode: str, route: str,
                     answer: str | None, meta: dict, error: str | None = None,
                     result: dict | None = None) -> dict:
    """QUERY-RECEIPTS on the chat runtime (plan §3.6): ONE payload per turn,
    built by the runtime for every transport — `record_query_receipt`'s
    keyword arguments minus the transport's own tags (`kind`, `client`).
    `meta.route` ("chat" | "chat/stream") is the transport tag the plan asks
    for (§4 P1.f); citations / claims ride along when the synthesizer
    produced them (deterministic answers), so /chat's receipt keeps its
    citation count. Pure."""
    corpora = list(getattr(scope, "corpus_ids", None) or [])
    kind_scope = getattr(scope, "mode", None)
    out = None
    if not error:
        out = {"answer": answer or "", "meta": dict(meta or {}, mode=ui_mode, route=route)}
        for key in ("citations", "claims"):
            if isinstance(result, dict) and isinstance(result.get(key), list):
                out[key] = result[key]
    return {"question": question, "req": req, "scope_corpora": corpora,
            "scope_kind": (str(kind_scope).lower() if kind_scope else None),
            "wall_ms": wall_ms, "out": out, "error": error}


def _default_receipt_sink(route: str):
    """The receipt writer used when the transport passes none: the stream's
    tags for the stream (kind `chat_stream`, client `ui-stream` — the UI's
    turns were previously invisible), the JSON transport's kind (`chat`, no
    client) for a bare `run_chat`. Best effort, never on the critical path."""
    from polymath_shared.query_receipts import record_query_receipt
    kind, client = ("chat_stream", "ui-stream") if route == "chat/stream" else ("chat", None)

    def _sink(payload: dict) -> None:
        record_query_receipt(tx, kind=kind, client=client, **payload)
    return _sink


#: §9.3 default: the last artifact VERBATIM (the history window truncates
#: assistant turns at 4,000 chars, which decapitates a long prompt or a
#: full HTML artifact) + the compiler's summary of earlier ones.
_PRIOR_ARTIFACT_CHARS = int(os.environ.get("POLYMATH_PRIOR_ARTIFACT_CHARS", "16000"))


def _turn_role(t) -> str | None:
    return getattr(t, "role", None) or (t.get("role") if isinstance(t, dict) else None)


def _turn_content(t) -> str:
    return str(getattr(t, "content", None) or (t.get("content") if isinstance(t, dict) else "") or "")


def _prior_artifact(plan, history) -> str | None:
    """SYNTHESIS-V2: the antecedent assistant turn, verbatim, when the task
    continues or refines it (CONTINUE_PRIOR_ARTIFACT, or the compiler's
    antecedent is an assistant artifact). The compiler's `antecedent.turn`
    offset is honoured when it points at an assistant turn; else the last
    non-empty assistant turn."""
    if plan is None:
        return None
    ante = plan.antecedent if isinstance(plan.antecedent, dict) else {}
    if plan.task_type != "CONTINUE_PRIOR_ARTIFACT" and ante.get("kind") != "assistant_artifact":
        return None
    turns = [t for t in (history or []) if _turn_role(t) in ("user", "assistant")]
    cand = None
    off = ante.get("turn")
    if isinstance(off, int) and off < 0 and -off <= len(turns) and _turn_role(turns[off]) == "assistant" and _turn_content(turns[off]).strip():
        cand = turns[off]
    if cand is None:
        for t in reversed(turns):
            if _turn_role(t) == "assistant" and _turn_content(t).strip():
                cand = t
                break
    return _turn_content(cand)[:_PRIOR_ARTIFACT_CHARS] if cand is not None else None


def _coverage_lines(coverage: dict | None) -> list[str]:
    """P1.b: tell the synthesizer which compiled aspects found evidence and
    which found none, so a weak dimension is named instead of papered over."""
    if not coverage:
        return []
    parts = []
    for qid, a in coverage.items():
        n = a.get("final", 0)
        weak = a.get("weak")
        if weak == "below_floor":
            why = f"NO RELEVANT EVIDENCE (best judge score {a.get('best')}): say so explicitly for this aspect"
        elif weak == "unjudged" and n:
            why = (f"{n} evidence item(s), relevance UNVERIFIED — the relevance judge did not score this turn (deadline or outage); "
                   "treat this aspect's coverage as unconfirmed and say so if the evidence does not plainly answer it")
        elif weak == "no_candidates" or not n:
            why = "NO EVIDENCE RETRIEVED: say so explicitly for this aspect"
        else:
            why = f"{n} evidence item(s)"
        parts.append(f'{qid} {a.get("type")} "{str(a.get("query") or "")[:60]}" — {why}')
    return ["EVIDENCE COVERAGE BY ASPECT:\n" + "\n".join(parts)]


def _request_block(query: str, plan, history, coverage: dict | None = None) -> str:
    """SYNTHESIS-V2 request framing: the request as written, the RESOLVED
    request, the compiled task/evidence policy/response type, coverage,
    constraints, the compiler's antecedent summary and the prior artifact
    verbatim. Without a plan (compiler off) the v1 block is unchanged."""
    if plan is None:
        return f"REQUEST:\n{query}"
    lines = [f"REQUEST (as written):\n{query}"]
    resolved = (plan.resolved_request or "").strip()
    if resolved and resolved != (query or "").strip():
        lines.append("RESOLVED REQUEST (pronouns and references resolved from the conversation — perform THIS):\n" + resolved)
    lines.append(f"TASK: {plan.task_type} · EVIDENCE POLICY: {plan.evidence_policy} · RESPONSE TYPE: {plan.response_type}")
    if plan.must_answer:
        lines.append("MUST COVER: " + "; ".join(str(x) for x in plan.must_answer[:6]))
    if plan.user_constraints:
        lines.append("CONSTRAINTS: " + "; ".join(str(x) for x in plan.user_constraints[:8]))
    lines.extend(_coverage_lines(coverage))
    ante = plan.antecedent if isinstance(plan.antecedent, dict) else None
    if ante and ante.get("summary"):
        lines.append(f"ANTECEDENT ({ante.get('kind') or 'topic'}, turn {ante.get('turn')}): {ante['summary']}")
    art = _prior_artifact(plan, history)
    if art:
        lines.append("PRIOR ARTIFACT (the assistant's earlier deliverable, verbatim — continue or refine THIS, do not ask the evidence for it):\n" + art)
    return "\n\n".join(lines)


def _plan_meta(plan) -> dict:
    """§3.4: the answer event names the task the synthesizer was given."""
    if plan is None:
        return {"prompt_contract": _SYNTHESIS_CONTRACT}
    return {"prompt_contract": _SYNTHESIS_CONTRACT, "task_type": plan.task_type, "evidence_policy": plan.evidence_policy,
            "response_type": plan.response_type, "retrieval_required": plan.retrieval_required,
            "compiler_fallback": bool(plan.fallback)}


def _grounded_messages(query: str, bundle: dict, graph_facts: list,
                       history, carry_context,
                       reasoning: str | None = None,
                       reasoning_blend: list[str] | None = None,
                       style: str = "neutral", plan=None, coverage: dict | None = None) -> list[dict]:
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
        context_block = "EVIDENCE: none retrieved for this turn" + (
            " (by design: this request is answered from the conversation and the user's own text)."
            if plan is not None and not plan.retrieval_required else ".")
    messages = [{"role": "system", "content": _llm_system_prompt(style)}]
    for turn in (history or [])[-12:]:
        if turn.role in ("user", "assistant") and turn.content:
            messages.append({"role": turn.role,
                             "content": turn.content[:4000]})
    from orchestrator.api.reasoning import apply_reasoning

    user_content = apply_reasoning(
        f"{context_block}\n\n{_request_block(query, plan, history, coverage)}",
        mode=reasoning or os.environ.get("POLYMATH_REASONING_MODE", "none"),
        blend=reasoning_blend)
    messages.append({"role": "user", "content": user_content})
    return messages



# ---------------- CARRY-V2 (CHAT-QUERY-COMPILER-PLAN §3.5, P0.e) ----------------
#: Measured 2026-09-05 (chat-carry-p0e-v1-baseline): the frontend carried
#: every RETRIEVED chunk of every earlier answer (cap 30), so an off-topic
#: turn 1 put 6 of its chunks into turn 3's prompt and the prompt grew
#: 32k → 47k chars over three turns. v2: the client carries only USED
#: evidence (cited [S#]) with its chunk id, cap 8; the backend hydrates the
#: chunks, reranks them against the RESOLVED request, drops those below the
#: admission floor, caps again, and puts the survivors into the evidence
#: bundle — so they get [S#] tags, appear in the legend as `carried`, and
#: count in used_evidence like any other evidence. Old clients that still
#: send 30 raw locators get the same admission (the backend owns the law).
_CARRY_CAP = int(os.environ.get("POLYMATH_CARRY_CAP", "8"))
#: The floor is on the reranker sidecar's RAW cross-encoder score (logit-
#: like, not a probability: measured on-topic carried chunks 1.1–6.9,
#: off-topic ones negative). 0.25 ≈ "more likely relevant than not" with a
#: margin above 0; every dropped score is recorded in the accounting.
_CARRY_ADMISSION_FLOOR = float(os.environ.get("POLYMATH_CARRY_ADMISSION_FLOOR", "0.25"))
_CARRY_MAX_IN = 64


def _carry_candidates(carry_context, exclude_ids: set[str] | None = None) -> tuple[list[dict], dict]:
    """Normalise the client's carried items to chunk ids (explicit chunk_id
    or parsed from the locator), newest-first order kept, deduped, minus
    the ids retrieved fresh this turn."""
    exclude_ids = exclude_ids or set()
    seen: set[str] = set()
    out: list[dict] = []
    acct = {"in": len(list(carry_context or [])), "dropped_duplicate": 0, "dropped_already_retrieved": 0, "dropped_unparsed": 0}
    for c in list(carry_context or [])[:_CARRY_MAX_IN]:
        cid = getattr(c, "chunk_id", None) or (c.get("chunk_id") if isinstance(c, dict) else None)
        loc = getattr(c, "locator", None) or (c.get("locator") if isinstance(c, dict) else None) or ""
        if not cid:
            m = _LOC_CHUNK_RE.match(str(loc))
            cid = m.group(1) if m else None
        if not cid:
            acct["dropped_unparsed"] += 1
            continue
        if cid in seen:
            acct["dropped_duplicate"] += 1
            continue
        seen.add(cid)
        if cid in exclude_ids:
            acct["dropped_already_retrieved"] += 1
            continue
        out.append({"chunk_id": str(cid), "locator": str(loc),
                    "preview": getattr(c, "preview", None) or (c.get("preview") if isinstance(c, dict) else None) or ""})
    return out, acct


def _carried_bundle_item(row: dict, score: float | None, resolve_document=None) -> dict:
    """An evidence-bundle item in the assembler's shape, flagged `carried`."""
    from polymath_shared.evidence_assembly import _presentation, _source_span
    if resolve_document is None:
        from orchestrator.api.evidence import _resolve_document as resolve_document  # noqa: N813 — the assembler's resolver
    doc = None
    try:
        doc = resolve_document(row.get("doc_id") or "")
    except Exception:  # noqa: BLE001 — presentation is best-effort
        doc = None
    return {"lane": "carry", "kind": "carried", "text_kind": None, "carried": True, "carry_score": score,
            "source_chunk_id": row["chunk_id"], "source_document_id": row.get("doc_id"),
            "source_span": _source_span(row, {}),
            "applicability": {"corpus_id": (doc or {}).get("corpus_id"), "source_name": (doc or {}).get("source_name"), "conditions": []},
            "presentation": _presentation(doc, row, None), "retrieval": {"lanes": ["carry"], "score": score}}


def _admit_carry(candidates: list[dict], resolved_request: str, *, resolve=None, scorer=None,
                 resolve_document=None, floor: float | None = None, cap: int | None = None) -> tuple[list[dict], dict]:
    """Hydrate → rerank against the resolved request → floor → cap.
    Returns (bundle items, accounting). A reranker outage degrades to
    newest-first + cap and is COUNTED (`degraded`), never silent."""
    if resolve is None:
        from orchestrator.api.evidence import _resolve_chunk as resolve  # noqa: N813 — the assembler's resolver
    floor = _CARRY_ADMISSION_FLOOR if floor is None else float(floor)
    cap = _CARRY_CAP if cap is None else int(cap)
    acct = {"candidates": len(candidates), "hydrated": 0, "dropped_missing": 0, "dropped_floor": 0, "dropped_cap": 0,
            "admitted": 0, "floor": floor, "cap": cap, "degraded": None, "scores": [], "admitted_ids": []}
    hydrated: list[tuple[dict, dict]] = []
    for c in candidates:
        try:
            row = resolve(c["chunk_id"])
        except Exception:  # noqa: BLE001 — a missing/hidden chunk is dropped, not fatal
            row = None
        if not row or not str(row.get("text") or "").strip():
            acct["dropped_missing"] += 1
            continue
        hydrated.append((c, row))
    acct["hydrated"] = len(hydrated)
    if not hydrated:
        return [], acct
    texts = [r["text"] for _, r in hydrated]
    scores = None
    try:
        if scorer is not None:
            scores = [float(x) for x in scorer(resolved_request, texts)]
        else:
            from polymath_shared.clients import RerankerClient
            from polymath_shared.rerank import _batched_scores
            scores = [float(x) for x in _batched_scores(RerankerClient(timeout=30.0), resolved_request, texts)["scores"]]
        if len(scores) != len(hydrated):
            raise ValueError(f"scores {len(scores)} != items {len(hydrated)}")
    except Exception as exc:  # noqa: BLE001
        scores = None
        acct["degraded"] = f"carry_rerank_unavailable:{type(exc).__name__}"
    if scores is None:
        ranked = [(None, c, r) for c, r in hydrated]
    else:
        ranked = sorted(((sc, c, r) for sc, (c, r) in zip(scores, hydrated)), key=lambda t: -t[0])
        kept = [t for t in ranked if t[0] >= floor]
        acct["dropped_floor"] = len(ranked) - len(kept)
        acct["scores_dropped_floor"] = [round(t[0], 4) for t in ranked if t[0] < floor]
        ranked = kept
    acct["dropped_cap"] = max(0, len(ranked) - cap)
    ranked = ranked[:cap]
    items = [_carried_bundle_item(r, sc, resolve_document) for sc, _, r in ranked]
    acct["admitted"] = len(items)
    acct["scores"] = [(round(sc, 4) if sc is not None else None) for sc, _, _ in ranked]
    acct["admitted_ids"] = [r["chunk_id"] for _, _, r in ranked]
    return items, acct

def _prompt_stats(messages: list[dict], carry_context, carried_in_prompt: int) -> dict:
    """CARRY-ACCOUNTING-V1 (P0.e): what the model was actually given —
    prompt size and how many carried items entered it. Yielded first by
    both generators, recorded in result.meta["prompt"] and the receipt."""
    return {"prompt_chars": sum(len(str(m.get("content") or "")) for m in messages),
            "messages": len(messages), "carry_in": len(list(carry_context or [])),
            "carry_in_prompt": int(carried_in_prompt)}

def _litellm_generate(model: str, query: str, bundle: dict,
                      graph_facts: list, history, carry_context,
                      reasoning: str | None = None,
                      reasoning_blend: list[str] | None = None,
                      style: str = "neutral", plan=None, coverage: dict | None = None):
    """LLM-PROVIDER-LAYER-V1: stream tokens from ANY provider through
    LiteLLM (OpenAI-format model strings: openai/gpt-4o,
    anthropic/claude-..., gemini/..., groq/..., ollama/...). Credentials
    come from the configured provider row; grounding prompt identical to
    the Ollama path. Yields {'token': str} or one {'error': ...}."""
    import litellm

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend, style=style, plan=plan, coverage=coverage)
    yield {"prompt": _prompt_stats(messages, carry_context,
                                   sum(1 for c in (carry_context or [])[:30] if getattr(c, "preview", "")))}
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
                     style: str = "neutral", plan=None, coverage: dict | None = None):
    """Stream tokens from the local Ollama daemon over a grounded
    prompt. Yields {'token': str} pieces or one {'error': ...}.

    Prompt assembly is the SHARED builder — this function previously
    duplicated it inline, which let the two backends drift."""
    import httpx

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend, style=style, plan=plan, coverage=coverage)
    yield {"prompt": _prompt_stats(messages, carry_context,
                                   sum(1 for c in (carry_context or [])[:30] if getattr(c, "preview", "")))}

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


def _merged_degraded(fast: dict, stale) -> list[dict]:
    """Route-level degradations (sparse fallback, parked reranker, stale projections) + the engine's deadline
    receipts (P1.d `<lane>_timeout` / `rerank_timeout` / `embed_deadline`, P1.e `graph_degraded` / `wildcard`),
    one entry per component (the engine also carries the parked-reranker note; it is not repeated)."""
    from orchestrator.api.fast import degradations
    from polymath_shared.evidence_assembly import stale_projection_degradation
    out = list(degradations()) + list(stale_projection_degradation(stale))
    seen = {d.get("component") for d in out if isinstance(d, dict)}
    for d in ((fast or {}).get("meta") or {}).get("degraded") or []:
        if isinstance(d, dict) and d.get("component") not in seen:
            out.append(d)
            seen.add(d.get("component"))
    return out


def chat_events(req: StreamChatRequest, *, route: str = "chat/stream", receipt=None):
    """CHAT-RUNTIME-V1 (plan §3.7 / §4 P1.f): the ONE chat runtime — scope,
    compiler (off | shadow | on), retrieval composition (MODE-COMPOSITION-V1
    on CHAT-RETRIEVAL-V2; the v1 engines behind `retrieval: v1` / `latent` /
    `utility`), evidence bundle, CARRY-V2 admission, SYNTHESIS-V2 — as a
    generator of SSE frames (`phase`, `token`, `reasoning`, `answer`, `done`,
    `error`). `/chat/stream` streams the frames; `/chat` (and so MCP `ask`)
    drains them through `run_chat`. Same request ⇒ same plan, same evidence
    ids, same synthesis contract on every route.

    Request validation (message, mode, synthesizer) happens here, EAGERLY —
    typed HTTPExceptions before the first frame — so both transports reject
    the same requests with the same status (a streaming response cannot
    change its status once the first frame is out). The returned object is
    the frame generator.

    `route` ("chat/stream" | "chat") and `receipt` are transport tags only.
    The receipt payload is built once, in the runtime, for every turn that
    ran (`_receipt_payload`, `meta.route` = the route); `receipt(payload)` —
    default `_default_receipt_sink(route)` — adds the transport's `kind` and
    `client`. Neither changes the plan, the retrieval decision, the evidence
    ids or the synthesis."""
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
    sink = receipt or _default_receipt_sink(route)

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

        def _receipt(**kw) -> None:
            # the turn's one receipt, through the transport's writer; never breaks a turn
            try:
                sink(_receipt_payload(req, question=query, scope=scope, route=route, **kw))
            except Exception:  # noqa: BLE001
                pass
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
            _flag = _compiler_flag(getattr(req, "compiler", None))
            _retrieval_text = query
            _skip_retrieval = False
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
                    from polymath_shared.chat_plan import plan_receipt, retrieval_text_for
                    _plan_receipt = plan_receipt(_plan)
                    # COMPILED-RETRIEVAL-V1: search the compiled text, or not at all
                    _skip_retrieval = (not _plan.retrieval_required) and ui_mode != "ASK"
                    _retrieval_text = query if _skip_retrieval else retrieval_text_for(_plan)
                    _plan_receipt["retrieval_query"] = None if _skip_retrieval else _retrieval_text
                    _plan_receipt["retrieval_skipped"] = _skip_retrieval
                    yield _phase("compile", "Query compiled" if not _plan.fallback else "Query compiler fell back",
                                 task_type=_plan.task_type, retrieval_required=_plan.retrieval_required,
                                 queries=len(_plan.queries), fallback=_plan.fallback,
                                 mode=_flag, wall_ms=_plan.compiler.get("wall_ms"),
                                 retrieval_query=(None if _skip_retrieval else _retrieval_text[:160]))

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
                _msg = f"{ui_mode} retrieves over exactly one corpus; scope has {len(scope.corpus_ids)}"
                yield _sse("error", {
                    "error_code": "mode_requires_single_corpus",
                    "message": _msg})
                _receipt(wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode, answer=None, meta={},
                         error=f"mode_requires_single_corpus: {_msg[:200]}")
                return

            graph_facts: list = []
            latent_meta = None
            wildcard_lane = None
            _arrivals: dict = {}
            _aspects: dict = {}
            _weak: list = []
            # CHAT-RETRIEVAL-V2 / P1.e MODE-COMPOSITION-V1: every mode is a composition on the v2 engine
            # (VECTOR = A+B, HYBRID = A+B+C, GRAPH = HYBRID → bounded G, WILDCARD = HYBRID ∥ W) owned by
            # chat_retrieve_mode; the v1 engines stay behind `retrieval: v1` or `latent` (rollback boundary).
            from orchestrator.api.chat_retrieval import chat_retrieval_flag
            _rflag = chat_retrieval_flag(getattr(req, "retrieval", None))
            # `latent` / `utility` are v1 plan knobs: either keeps the turn on the v1 engines (as /chat always did)
            _v2_mode = _rflag in ("v2", "v2-single") and not req.latent and not req.utility
            # GRAPH bounds follow the compiled plan's relational verdict (plan §3.15 / §5 #14): `graph_useful: false`
            # keeps the expansion definitional (≤ 2 seeds); no compiler, or a fallback plan, keeps the default breadth.
            _graph_useful = True if (_flag != "on" or _plan is None or getattr(_plan, "fallback", False)) \
                else bool(getattr(_plan, "graph_useful", True))
            if _skip_retrieval:
                # NO-RETRIEVAL ROUTING (plan §3.1 evidence_policy=conversation):
                # the task lives in the conversation; the corpus is not searched.
                evidence_rows = []
                _trace = {}
                fast = {"selected_documents": [], "selected_sections": [], "trace": {}, "meta": {}, "evidence": []}
                _mark("retrieve")
                yield _phase("retrieve_skipped", "No corpus retrieval: the request is answered from the conversation",
                             task_type=_plan.task_type if _plan else None,
                             evidence_policy=_plan.evidence_policy if _plan else None)
                document_summaries = []
                section_summaries = []
            elif ui_mode == "GRAPH" and not _v2_mode:
                # graph-retrieval-v1 (rollback boundary: `retrieval: v1` or `latent`)
                yield _phase("retrieve", f"{ui_mode} retrieval over "
                                         f"{corpus_id}…", mode=ui_mode, query=_retrieval_text[:160])
                from orchestrator.api.graph import graph_retrieve
                g = graph_retrieve(_retrieval_text, corpus_id, latent=req.latent, utility=req.utility)
                # the answer event reads the retrieval result through `fast` on every path
                fast = {"meta": g.get("meta") or {}, "trace": g.get("trace") or {}, "evidence": [],
                        "selected_documents": [], "selected_sections": []}
                _trace = g.get("trace") or {}
                latent_meta = (g.get("meta") or {}).get("latent")
                evidence_rows = [
                    {"chunk_id": c["chunk_id"], "doc_id": d["doc_id"],
                     "parent_id": s["parent_id"]}
                    for d in g["documents"]
                    for s in d["sections"]
                    for c in s["evidence"]
                ]
                _mark("retrieve")
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
                yield _phase("retrieve", f"{ui_mode} retrieval over "
                                         f"{corpus_id}…", mode=ui_mode, query=_retrieval_text[:160])
                wildcard_lane = None
                if _v2_mode:
                    from orchestrator.api.chat_retrieval import chat_retrieve_mode
                    # MODE-COMPOSITION-V1 (plan §3.15, P1.e): lanes A/B/C fused at child level with provenance;
                    # GRAPH adds the bounded hop-1 over the FINAL evidence (§3.18), WILDCARD the parallel latent
                    # frontier (§3.19) — bridges ride `fast["wildcard"]`, never the evidence list.
                    fast = chat_retrieve_mode(
                        "VECTOR" if ui_mode == "FAST" else ui_mode, _retrieval_text, corpus_id,
                        graph_useful=_graph_useful,
                        exact_terms=tuple(_plan.exact_terms) if (_flag == "on" and _plan is not None) else (),
                        # P1.b: typed subqueries run lanes B + C on their own vectors (v2-single = A/B without them)
                        subqueries=tuple((q.id, q.type, q.query, q.weight) for q in _plan.queries if q.type != "PRIMARY")
                        if (_flag == "on" and _plan is not None and _rflag == "v2") else ())
                    _aspects = (fast.get("meta") or {}).get("aspects") or {}
                    _weak = (fast.get("meta") or {}).get("weak_aspects") or []
                    if ui_mode == "WILDCARD":
                        wildcard_lane = fast.get("wildcard") or []
                    if ui_mode == "GRAPH":
                        graph_facts = [
                            {"fact_id": f["fact_id"], "predicate": f["predicate"],
                             "subject": f["subject"], "object": f["object"]}
                            for f in (fast.get("graph_relationships") or [])
                        ]
                elif ui_mode == "FAST":
                    from orchestrator.api.fast import fast_retrieve
                    fast = fast_retrieve(_retrieval_text, corpus_id)
                elif ui_mode == "WILDCARD":
                    # DIVERGENT-RETRIEVAL-V1 (v1): the answer evidence IS
                    # FAST (wildcard never displaces it); the bridges
                    # ride the separate `wildcard` lane.
                    from orchestrator.api.wildcard import wildcard_retrieve
                    fast = wildcard_retrieve(_retrieval_text, corpus_id)
                    wildcard_lane = fast.get("wildcard") or []
                else:
                    from orchestrator.api.hybrid import hybrid_fast_retrieve
                    fast = hybrid_fast_retrieve(_retrieval_text, corpus_id,
                                                latent=req.latent, utility=req.utility)
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
                             lane_sizes=fast["trace"].get("lane_sizes"),
                             plan=(fast.get("meta") or {}).get("plan_version"),
                             degraded=[d.get("component") for d in ((fast.get("meta") or {}).get("degraded") or [])] or None,
                             aspects=len(_aspects) or None, weak_aspects=_weak or None)
                if ui_mode == "GRAPH":
                    # P1.e: the bounded stage already ran inside the composition; the phases carry its receipts
                    yield _phase("graph", "Expanding the canonical fact "
                                          "graph (hop-1, bounded)…",
                                 bounds=(fast.get("meta") or {}).get("graph_bounds"))
                    yield _phase("graph_done",
                                 f"{len(graph_facts)} canonical relationship(s)",
                                 graph_fact_count=len(graph_facts),
                                 relationships=graph_facts[:8],
                                 seeds=(fast.get("meta") or {}).get("graph_seeds"),
                                 degraded=(fast.get("meta") or {}).get("graph_degraded"))
                _arrivals = {c["chunk_id"]: c.get("arrivals") or ([c["arrival"]] if c.get("arrival") else [])
                             for c in fast["evidence"]}
                if wildcard_lane is not None:
                    yield _phase(
                        "wildcard",
                        f"{len(wildcard_lane)} frontier bridge(s) beyond "
                        f"the obvious neighborhood",
                        bridges=len(wildcard_lane),
                        degraded=((fast.get("meta") or {}).get("wildcard") or {}).get("degraded"))
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
                _receipt(wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode, answer=None, meta={},
                         error=f"{type(exc).__name__}: {str(exc)[:200]}")
                return
            _mark("assemble")
            # CARRY-V2: admitted carried evidence joins the bundle (tags, legend, used_evidence)
            _carry_meta: dict = {"in": len(req.carry_context), "admitted": 0}
            if req.carry_context and not _skip_retrieval:
                _cands, _cacct = _carry_candidates(req.carry_context, {c.get("chunk_id") for c in evidence_rows})
                _citems, _aacct = _admit_carry(
                    _cands, (_plan.resolved_request if (_flag == "on" and _plan is not None and _plan.resolved_request) else query))
                _carry_meta = {**_cacct, **_aacct}
                if _citems:
                    bundle.setdefault("evidence_bundle", []).extend(_citems)
                yield _phase("carry", f"Carried evidence: {_aacct['admitted']} of {len(req.carry_context)} admitted",
                             **{k: v for k, v in _carry_meta.items() if k not in ("scores", "admitted_ids")})
            elif req.carry_context:
                _carry_meta["skipped"] = "no_retrieval_turn"
            _mark("carry")
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
                    "carried": bool(item.get("carried")),
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
                # P1.e MODE-COMPOSITION-V1 receipts: the bounded graph stage (seeds / facts / fail-open reason)
                # and the frontier lane's diagnostics (sweep overlap, baseline, timeout) — `wildcard` below
                # stays the bridges the UI renders.
                "graph_bounds": (fast.get("meta") or {}).get("graph_bounds"),
                "graph_seeds": (fast.get("meta") or {}).get("graph_seeds"),
                "graph_degraded": (fast.get("meta") or {}).get("graph_degraded"),
                "wildcard_diagnostics": (fast.get("meta") or {}).get("wildcard"),
                # LATENT-DIAGNOSTICS-V1 (roadmap B5): the survival
                # attribution frame the UI chip + P6 read.
                "latent": latent_meta,
                # DIVERGENT-RETRIEVAL-V1: labelled DERIVED insights with
                # their real source children attached (owner-blessed
                # §0b carve-out) — never part of `chunks` evidence.
                "wildcard": (wildcard_lane
                             if ui_mode == "WILDCARD" else None),
                "chunks": chunk_inventory,
                # CARRY-V2 accounting (plan §3.5): in / hydrated / admitted / dropped_* / floor / scores
                "carry": _carry_meta,
                # CHAT-RETRIEVAL-V2 (plan §3.14): which plan retrieved, and every
                # final candidate's lane provenance (P1.a gate: 100 % have arrivals)
                "engine": (fast.get("meta") or {}).get("plan_version"),
                "arrivals": _arrivals,
                "lane_sizes": (fast.get("trace") or {}).get("lane_sizes"),
                # per-stage retrieval timings (embed / lanes / rerank_select / total) — P1.b/P1.d latency accounting
                "latency_ms": (fast.get("trace") or {}).get("latency_ms"),
                # P1.b aspect coverage: per compiled query, candidates in union / final; weak = none in final
                "aspects": _aspects,
                "weak_aspects": _weak,
                "final_detail": (fast.get("meta") or {}).get("final_detail"),
                # P1.c EVIDENCE-COMPOSER-V1: slot fills, per-document counts, dominance flag
                "composition": (fast.get("meta") or {}).get("composition"),
                # NEVER-ERROR-ON-A-COLD-MODEL: a lane that degraded
                # (e.g. reranker parked behind extraction) still answers
                # — the UI says so instead of the query failing. The engine's
                # deadline receipts (P1.d: `<lane>_timeout`, `rerank_timeout`,
                # `embed_deadline`; P1.e: `graph_degraded`, `wildcard`) ride the
                # same list so the answer event, the /chat JSON and the query
                # receipt all say WHY a turn's evidence differs (never silent).
                "degraded": _merged_degraded(fast, stale),
            }

            if llm_model is not None:
                yield _phase("generate",
                             f"Generating with {llm_model}…",
                             model=llm_model,
                             carried=_carry_meta.get("admitted", 0))
                full: list[str] = []
                _prompt_meta: dict = {}
                _gen = (_litellm_generate if llm_backend == "litellm"
                        else _ollama_generate)
                _style = _style_for(list(getattr(scope, "corpus_ids", None) or []))
                retrieval["style"] = _style
                for tok in _gen(
                        llm_model, query, bundle, graph_facts,
                        req.history, [],          # CARRY-V2: admitted carry already rides in the bundle
                        req.reasoning, req.reasoning_blend, style=_style,
                        plan=(_plan if _flag == "on" else None),
                        coverage=(_aspects if (_flag == "on" and len(_aspects) > 1) else None)):
                    if tok.get("prompt"):
                        _prompt_meta = dict(tok["prompt"])
                        continue
                    if tok.get("error"):
                        yield _sse("error", tok)
                        _receipt(wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode, answer=None, meta={},
                                 error=f"{tok.get('error_code') or 'generation_error'}: {str(tok.get('message') or '')[:200]}")
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
                _prompt_meta.update({"carry_in": _carry_meta.get("in", 0), "carry_in_prompt": _carry_meta.get("admitted", 0)})
                answer_text = "".join(full)
                from polymath_shared.funnel import funnel_from_trace
                used = _cited_chunk_ids(answer_text, _legend)
                funnel = funnel_from_trace(
                    _trace, selected=[e["chunk_id"] for e in _legend if e.get("chunk_id")],
                    cited=used, plan_version=(_trace or {}).get("plan"))
                retrieval["used_evidence"] = used
                retrieval["legend"] = [{"tag": e["tag"], "locator": e["locator"],
                                        "chunk_id": e.get("chunk_id"), "doc_id": e.get("doc_id"),
                                        "carried": bool(e.get("carried")), "carry_score": e.get("carry_score")}
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
                            **_plan_meta(_plan if _flag == "on" else None),
                            "prompt": _prompt_meta,
                            "carry": {k: v for k, v in _carry_meta.items() if k != "scores"},
                        },
                    },
                    "retrieval": retrieval,
                    "latency_ms": round(
                        (time.perf_counter() - t0) * 1000, 1),
                })
                yield _sse("done", {})
                _receipt(
                    wall_ms=_phase_ms["total"], ui_mode=retrieval.get("mode") or ui_mode,
                    answer=answer_text,
                    meta={"verdict": "generated", "synthesis_version": f"{llm_backend}:{llm_model}",
                          "model": llm_model, "latent": req.latent, "phase_ms": dict(_phase_ms),
                          "funnel": funnel, "used_evidence": used, "legend": retrieval["legend"],
                          "degraded": retrieval.get("degraded"), "plan": (_trace or {}).get("plan"),
                          "chat_plan": _plan_receipt or None, "prompt": _prompt_meta or None, "carry": _carry_meta,
                          "composition": retrieval.get("composition")})
                return

            yield _phase("synthesize", "Validating claims against "
                                       "evidence…")
            answer = grounded_answer(bundle, query)
            _mark("generate")
            _join_plan()
            if isinstance(answer, dict) and isinstance(answer.get("meta"), dict):
                answer["meta"].update(_plan_meta(_plan if _flag == "on" else None))
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
            retrieval["legend"] = [{"tag": e["tag"], "locator": e["locator"], "chunk_id": e.get("chunk_id"), "doc_id": e.get("doc_id"),
                                    "carried": bool(e.get("carried")), "carry_score": e.get("carry_score")} for e in _legend]
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
            _receipt(
                wall_ms=_phase_ms["total"], ui_mode=retrieval.get("mode") or ui_mode,
                answer=answer.get("answer"), result=answer,
                meta={"verdict": (answer.get("meta") or {}).get("verdict"),
                      "synthesis_version": (answer.get("meta") or {}).get("synthesis_version"),
                      "latent": req.latent, "phase_ms": dict(_phase_ms), "funnel": funnel,
                      "used_evidence": used, "degraded": retrieval.get("degraded"),
                      "plan": (_trace or {}).get("plan"), "chat_plan": _plan_receipt or None, "carry": _carry_meta,
                      "composition": retrieval.get("composition")})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {
                "message": str(exc.detail)}
            yield _sse("error", {"status": exc.status_code, **detail})
            _receipt(wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode,
                     answer=None, meta={}, error=f"HTTP {exc.status_code}: {str(detail)[:200]}")
        except Exception as exc:  # loud, typed-ish, never silent
            yield _sse("error", {"error_code": type(exc).__name__,
                                 "message": str(exc)[:300]})
            _receipt(wall_ms=(time.perf_counter() - t0) * 1000, ui_mode=ui_mode,
                     answer=None, meta={}, error=f"{type(exc).__name__}: {str(exc)[:200]}")

    return generate()


@router.post("/chat/stream")
async def chat_stream(req: StreamChatRequest) -> StreamingResponse:
    """The SSE transport of the chat runtime (CHAT-RUNTIME-V1): the frames of
    `chat_events`, unchanged, with the stream's own receipt writer."""
    return StreamingResponse(chat_events(req), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


#: HTTP status for the runtime's in-band error frames (frames without a `status`
#: — i.e. not an HTTPException inside the runtime): the typed codes the runtime
#: emits itself; an assembly failure is a 502 (as /chat always answered one).
_ERROR_STATUS = {"mode_requires_single_corpus": 422,
                 "ollama_unavailable": 502, "ollama_error": 502, "litellm_error": 502}


def _error_status(data: dict) -> int:
    if data.get("status"):
        return int(data["status"])
    code = str(data.get("error_code") or "")
    if code in _ERROR_STATUS:
        return _ERROR_STATUS[code]
    from polymath_shared.evidence_assembly import AssemblyError
    if code in {c.__name__ for c in (AssemblyError, *AssemblyError.__subclasses__())}:
        return 502
    return 500


def run_chat(req: StreamChatRequest, *, route: str = "chat", receipt=None) -> dict:
    """CHAT-RUNTIME-V1: drain the runtime's frames and return the answer as
    ONE JSON object — the /chat shape. The answer event's `result` (answer /
    citations / claims / meta for the deterministic synthesizer; answer /
    model / meta for an LLM) merged with the SAME `retrieval` block the
    stream's answer event carries (mode, engine, evidence inventory, legend,
    used_evidence, funnel, carry, chat_plan, aspects, composition, degraded
    …), `phases` (the phase frames, in order), `kind`, `latency_ms` and
    `runtime: "chat-runtime-v1"`. `meta.mode` is the EXECUTED mode
    (CHAT-MODE-TRUTH-V1, from the retrieval block: VECTOR | HYBRID | GRAPH |
    WILDCARD | ASK) and `meta` mirrors funnel / used_evidence / retrieval_mode
    / retrieval_engine for /chat's historical readers. Token and reasoning
    frames are transport-only and dropped.

    The generator is drained to its end BEFORE an error frame is raised, so
    the runtime's receipt for the turn is written exactly as on the stream;
    the error then surfaces as HTTPException(status, detail) with the frame's
    status (`_error_status`). Eager request validation raises from
    `chat_events` itself — the same HTTPException the stream route raises."""
    phases: list[dict] = []
    answer: dict | None = None
    error: dict | None = None
    cur: str | None = None
    for frame in chat_events(req, route=route, receipt=receipt):
        for line in str(frame).split("\n"):
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except Exception:  # noqa: BLE001 — every frame is JSON; never break the drain
                    continue
                if cur == "phase":
                    phases.append(data)
                elif cur == "answer":
                    answer = data
                elif cur == "error" and error is None:
                    error = data
    if error is not None:
        raise HTTPException(status_code=_error_status(error),
                            detail={k: v for k, v in error.items() if k != "status"} or {"message": "chat runtime error"})
    if answer is None:
        raise HTTPException(status_code=502, detail={"error_code": "no_answer",
                                                     "message": "the chat runtime produced no answer frame"})
    result = dict(answer.get("result") or {})
    retrieval = dict(answer.get("retrieval") or {})
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    result["meta"] = meta
    meta["mode"] = retrieval.get("mode")                       # the executed mode, never the requested label
    for src, dst in (("funnel", "funnel"), ("used_evidence", "used_evidence"),
                     ("mode", "retrieval_mode"), ("engine", "retrieval_engine")):
        if src in retrieval:
            meta.setdefault(dst, retrieval[src])
    result["retrieval"] = retrieval
    result["phases"] = phases
    result["kind"] = answer.get("kind")
    result.setdefault("latency_ms", answer.get("latency_ms"))
    result["runtime"] = RUNTIME_CONTRACT
    return result
