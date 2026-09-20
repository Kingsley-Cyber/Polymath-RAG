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

import hashlib
import json
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
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
#: New chats take the FIRST OFFERED id of this comma-separated preference list (POLYMATH_DEFAULT_SYNTHESIZER): a provider
#: whose key is missing is skipped, never a dead default. Order measured 2026-09-06 on one grounded question: OpenCode's
#: glm-5-free is the owner's first choice; Alibaba's deepseek-v4-flash-0731 answered in 16–23 s WITH [S#] citation tags
#: (qwen3.8-max, the reasoning model, answered in 42 s without tags); gemma4:31b-cloud is the free-tier fallback.
_PREFERRED_DEFAULTS = [x.strip() for x in os.environ.get(
    "POLYMATH_DEFAULT_SYNTHESIZER",
    "litellm:anthropic/deepseek-v4-flash-0731,litellm:openai/big-pickle,litellm:openai/mimo-v2.5-free,litellm:openai/nemotron-3.5-lightning-free,ollama:gemma4:31b-cloud").split(",") if x.strip()]
_PREFERRED_DEFAULT = _PREFERRED_DEFAULTS[0] if _PREFERRED_DEFAULTS else "ollama:gemma4:31b-cloud"


def _default_synthesizer() -> str:
    """The id a request without a synthesizer gets: the first OFFERED preference (a provider whose key is missing is
    skipped), else the first offered model, else the raw first preference. Same rule as the dropdown's default — a
    request that names nothing must never be routed to a hidden provider (measured 2026-09-06: an empty synthesizer
    fell to `litellm:openai/glm-5-free` while the OpenCode key was unset → LiteLLM 'Missing credentials')."""
    offered = [e["id"] for e in (*_litellm_models(), *_ollama_models())]
    for pref in _PREFERRED_DEFAULTS:
        if pref in offered:
            return pref
    return offered[0] if offered else _PREFERRED_DEFAULT

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
            "provider": "ollama-free",
            "provider_label": "Ollama cloud (free)",
            "model": name,
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
                                          AND pr.status = 'READY')) AS enrich_failed,
                   -- RAG-PIPELINE-FINISH Phase 18: the vNext substrate row badge —
                   -- active parent maps (pMAP coverage). Cheap indexed (doc_id) subquery,
                   -- same shape as the enrichment counts. Full per-doc status (profile /
                   -- unresolved / blockers) is GET /documents/{doc_id}/status.
                   (SELECT COUNT(DISTINCT m.parent_id) FROM document_parent_maps m
                     WHERE m.doc_id = d.doc_id AND m.active) AS map_active
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
             "parents": r[6], "enriched": r[7], "enrich_failed": r[8],
             "map_active": r[9]}
            for r in rows
        ],
        "runs": [{"run_id": r[0], "status": r[1], "created_at": str(r[2]),
                  "error": r[3]}
                 for r in runs],
    }


@router.get("/documents/{doc_id}/status")
def document_status_view(doc_id: str) -> dict:
    """CANONICAL-DOCUMENT-STATUS-V1 (RAG-PIPELINE-FINISH Phase 18): the one authoritative
    per-document aggregate for the Files/status UI — identity, chunks, profile
    (present/valid/vnext/versions/counts), pMAP (eligible/mapped/excluded/unresolved/
    batches), per-doc vnext_ready, stages (ticket/status/attempt/error), functional-pool
    lane health, and the ordered blocker list. Read-only durable Postgres; no provider call."""
    from polymath_shared.document_status import document_status
    with tx() as conn:
        st = document_status(conn, doc_id=doc_id, detail=True)
    if not st.get("found"):
        raise HTTPException(404, {"error_code": "DOCUMENT_UNKNOWN",
                                  "message": f"document {doc_id!r} not found"})
    return st


@router.get("/control_plane")
def control_plane(corpus_id: str, request: Request) -> dict:
    """CONTROL-PLANE-STATUS-V1: is the machinery processing documents healthy? Corpus
    summary + per functional pool (GRAPH_EXTRACTION / DOCUMENT_PROFILE / PMAP / CHAT)
    queue depth, lane health, and provider accounting (limiter_refused ≠ HTTP 429).
    GAP-1: also the single composed `control_ready` verdict — sidecar readiness lives
    in app state (not Postgres), so it is read here and passed through, not recomputed
    by the caller."""
    from polymath_shared.control_plane_status import control_plane_status
    try:
        sidecars = {name: s.is_ready() for name, s in request.app.state.sidecars.items()}
    except AttributeError:
        sidecars = {}
    with tx() as conn:
        return control_plane_status(conn, corpus_id=corpus_id, sidecars=sidecars)


@router.get("/control_plane/pool/{function}")
def control_plane_pool(function: str) -> dict:
    """Model → account/key lanes for one functional pool (config + live limiter state,
    NEVER a secret value)."""
    from polymath_shared.control_plane_status import pool_lanes_detail
    with tx() as conn:
        return pool_lanes_detail(conn, function=function)


@router.get("/control_plane/predicates")
def control_plane_predicates(corpus_id: str, limit: int = 40) -> dict:
    """Bounded predicate distribution for the GRAPH_EXTRACTION drill-down (top N; opened on
    demand, not on every render). Catches an extraction/compiler collapse (few predicates)."""
    limit = max(1, min(int(limit), 200))
    with tx() as conn:
        rows = conn.execute(
            "SELECT f.predicate, COUNT(*) FROM facts f JOIN evidence ev ON ev.fact_id=f.fact_id "
            "JOIN documents d ON d.doc_id=ev.doc_id WHERE d.corpus_id=%s AND f.decision='ACCEPT' "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT %s", (corpus_id, limit)).fetchall()
    return {"corpus_id": corpus_id, "predicates": [{"predicate": p, "count": n} for p, n in rows]}


@router.get("/documents/summary")
def documents_summary(corpus_id: str) -> dict:
    """Per-document OPERATIONAL summary for the Files list (Parents / pMAP / Graph /
    Profile / Ready) — one bounded batch of corpus-level aggregates (no N+1). The frontend
    merges this into the /documents rows by doc_id."""
    from polymath_shared.document_status import corpus_document_summaries
    with tx() as conn:
        return {"corpus_id": corpus_id, "summaries": corpus_document_summaries(conn, corpus_id=corpus_id)}


_UPLOAD_EXTENSIONS = {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}


@router.post("/upload")
async def upload(corpus_id: str = Form(...),
                 file: UploadFile = File(...),
                 allow_near_duplicate: str = Form("")) -> dict:
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
    # NEAR-DUPLICATE-GUARD-V1 override ("keep both"): rides in the
    # canonical payload's config, so the overridden run has its own
    # identity and the intake worker's layer 3 sees it. Layers 1 and 2
    # (identical bytes / identical text) are never overridable.
    keep_both = allow_near_duplicate.strip().lower() in ("1", "true", "yes", "on")
    payload = canonical_intake_payload(
        corpus_id=corpus_id,
        source_name=source_name,
        media_type=file.content_type or "application/octet-stream",
        content_ref=ref,
        config={"allow_near_duplicate": True} if keep_both else None,
    )
    with tx() as conn:
        out = submit_intake(conn, payload)
    return {**out, "corpus_id": corpus_id, "source_name": source_name,
            "bytes": ref["bytes"], "sha256": ref["sha256"],
            "near_duplicate_override": keep_both}


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
                # MODEL-PICKER-V1: the dropdown groups by provider (collapsible sections)
                "provider": row["provider_id"],
                "provider_label": base,
                "model": m.split("/", 1)[-1],
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
            except Exception as exc:  # noqa: BLE001
                if optional:
                    conn.execute("ROLLBACK TO SAVEPOINT docdel")
                    # B2 follow-up: a skipped optional table is receipted WITH its reason — a bare "skipped" hid
                    # the projection-receipt rows that then kept the verify reconciler from pruning the graph
                    removed[key] = f"skipped: {type(exc).__name__}: {str(exc)[:80]}"
                else:
                    raise

        # facts evidenced ONLY by this document
        orphan_facts = [r[0] for r in conn.execute(
            """SELECT DISTINCT e.fact_id FROM evidence e
                WHERE e.doc_id=%s AND NOT EXISTS
                  (SELECT 1 FROM evidence e2
                    WHERE e2.fact_id=e.fact_id AND e2.doc_id<>%s)""",
            (doc_id, doc_id)).fetchall()]
        evidence_ids = [r[0] for r in conn.execute(
            "SELECT evidence_id FROM evidence WHERE doc_id=%s", (doc_id,)).fetchall()]
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

        # B2 follow-up (2026-09-06): this step matched Chunk nodes by a `doc_id` property they do not carry and
        # never touched the Document / Fact / Evidence nodes, so a deleted document left its whole derived
        # subgraph behind (measured: Document 1, Fact 987, Evidence 1,061, Chunk 1,975 orphans after one
        # delete; found by test_no_derived_node_outlives_its_postgres_row). The four kinds are now pruned by
        # the ids Postgres just released — the same doctrine as the verify reconciler — and each count is
        # receipted. Facts: only the ones this document evidenced alone (`orphan_facts`); shared facts stand.
        with neo4j_driver() as driver:
            with driver.session() as s:
                def _n(cypher: str, **params) -> int:
                    out = s.run(cypher, **params).single()
                    return int(out["n"]) if out and out["n"] is not None else 0
                removed["neo4j_chunks"] = sum(
                    _n("MATCH (c:Chunk) WHERE c.chunk_id IN $ids DETACH DELETE c RETURN count(*) AS n",
                       ids=chunk_ids[i:i + 1000]) for i in range(0, len(chunk_ids), 1000)) if chunk_ids else 0
                removed["neo4j_evidence"] = sum(
                    _n("MATCH (e:Evidence) WHERE e.evidence_id IN $ids DETACH DELETE e RETURN count(*) AS n",
                       ids=evidence_ids[i:i + 1000]) for i in range(0, len(evidence_ids), 1000)) if evidence_ids else 0
                removed["neo4j_facts"] = sum(
                    _n("MATCH (f:Fact) WHERE f.fact_id IN $ids DETACH DELETE f RETURN count(*) AS n",
                       ids=orphan_facts[i:i + 1000]) for i in range(0, len(orphan_facts), 1000)) if orphan_facts else 0
                removed["neo4j_rel_edges"] = sum(
                    _n("MATCH ()-[r:REL]->() WHERE r.fact_id IN $ids DELETE r RETURN count(*) AS n",
                       ids=orphan_facts[i:i + 1000]) for i in range(0, len(orphan_facts), 1000)) if orphan_facts else 0
                removed["neo4j_documents"] = _n(
                    "MATCH (d:Document {doc_id: $d}) DETACH DELETE d RETURN count(*) AS n", d=doc_id)
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
    # Move the first OFFERED preferred id to the front (new chats take
    # synths[0]); an unoffered preference (key missing) is skipped.
    offered = {e["id"]: i for i, e in enumerate(entries)}
    for pref in _PREFERRED_DEFAULTS:
        if pref in offered:
            entries.insert(0, entries.pop(offered[pref]))
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
    """One-shot connectivity/credential test for a configured model.

    Recorded like the extraction lanes' `probe`: a connectivity test IS an external model
    attempt, it spends a few tokens, and its failures (401, 429, missing credentials) are
    the evidence a model-selection argument turns on. `limiter_bypassed=True` — there is
    no lane limiter on this path."""
    import litellm
    import time as _time
    from polymath_shared.conformance.attempts import (Attempt as _At, attempt_context as _actx,
                                                      record as _rec)

    _base = dict(lane=f"chat_synth:{req.model.split('/')[0]}" if "/" in req.model
                 else "chat_synth",
                 model=req.model,
                 provider=(req.model.split("/")[0] if "/" in req.model else None),
                 limiter_admitted=False, limiter_bypassed=True, http_dispatched=True)
    _t0 = _time.perf_counter()
    with _actx(function="CHAT", stage="llm_test"):
        try:
            out = litellm.completion(
                model=req.model,
                messages=[{"role": "user", "content": "Reply with exactly: ok"}],
                max_tokens=20, timeout=30, **_litellm_credentials(req.model))
            text = (out.choices[0].message.content or "").strip()
            _rec(_At(success=True, http_status=200,
                     latency_ms=int((_time.perf_counter() - _t0) * 1000), **_base))
            return {"ok": True, "model": req.model, "reply": text[:80]}
        except Exception as exc:
            _rec(_At(success=False, error_class=type(exc).__name__,
                     latency_ms=int((_time.perf_counter() - _t0) * 1000), **_base))
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
    synthesizer: Optional[str] = None  # None -> _default_synthesizer() (first OFFERED preference)
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
    # COMPILER-CORPUS-CONTEXT-V1 (B16): per-request override of the title ranker — "off" | "sparse" | "dense";
    # None = the env default (measurement arms and an owner toggle, never a persisted setting)
    titles_rank: Optional[str] = None
    # CHAT-RETRIEVAL-V2 P1.a: per-request override of POLYMATH_CHAT_RETRIEVAL
    # (v1 = hybrid-retrieval-v1, v2 = chat-retrieval-v2) for evaluation and A/B.
    retrieval: Optional[str] = None
    # CORPUS-EXPLORER-V1: the user-facing "Corpus Explore" toggle (per query/conversation). RUNS only when
    # this is true AND the server capability POLYMATH_CORPUS_EXPLORER is on (default off). Additive; when
    # off the turn is pre-feature-equivalent V2.
    corpus_explorer: bool = False
    # REASONING-BOUNDARY-V1: evidence-only mode. When true, run the FULL pipeline (compiler -> Corpus
    # Explore -> retrieval -> C4/C5 -> CA4) and return a versioned EvidencePacket, skipping synthesis +
    # reviewer (no nested Polymath answer). Additive; false = the normal chat/synthesis path, unchanged.
    evidence_only: bool = False


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


#: PRESENTATION-V1 (owner design contract 2026-09-06, "the LLM's answer-generation
#: instructions should cooperate with the renderer"): READING-HIERARCHY-V1 set the
#: answer as a reading document (15.5 px prose / 78ch, headings 21/18/16, bold as a
#: highlighted anchor, citations as footnotes). Measured before this block (10 fixture-B
#: questions, deepseek-v4-flash): bold covered 6 % of the words at the median (17 % at
#: the worst), two one-sentence paragraphs per answer, bold lines standing in for
#: headings, a 2.5-line bold thesis. The v3.3 style layer below asks for those shapes
#: ("bold thesis", "at least one visible structure", KVP by default); this contract is
#: appended AFTER it and takes precedence on display shape only — authority, citation
#: and completeness rules are untouched.
_PRESENTATION_CONTRACT = "presentation-v2"
_PRESENTATION_BLOCK = """Information-presentation contract. The renderer sets each \
answer as a reading document — 15.5 px prose in a 78-character column, headings \
21 / 18 / 16, bold rendered as a highlighted anchor, citations as footnote tags — \
so write the shape that typography expects. Where a display rule above and this \
contract disagree, this contract wins.
- Length follows the question, never the amount of evidence: a factual \
question is one to three paragraphs (under about 200 words); an explanation \
or comparison three to six (under about 450 words); a build, rewrite or \
create request delivers the artifact itself with at most two short framing \
paragraphs. Go longer only when the user asks for depth, a full draft, or an \
enumeration that needs it. Never restate the question, never pad with generic \
advice, and never add a closing summary or a "next steps" list the user did \
not ask for.
- Paragraphs are the default unit: short, information-dense, two to five \
sentences (about 40–110 words) each. Split a paragraph where the mechanism \
changes; never run everything into one undifferentiated block.
- No one-sentence paragraph spam: a lone sentence stands alone only as the \
opening conclusion or a closing caveat.
- Progressive explanation: the conclusion in plain prose first, then the \
mechanism, then evidence and detail. A reader who stops after any paragraph \
holds a correct picture.
- Headings only when they clarify structure. An answer under about eight \
paragraphs has NO headings; a longer one has at most three, each covering \
several paragraphs or a substantial group of items. Never a heading per \
theme, per paragraph or per bullet group, never a heading on a short answer, \
never a bold line standing in for a heading, and never headings that merely \
restate the question's parts.
- Lists only for genuinely parallel items (steps, alternatives, members of a \
set), each item a short phrase or one sentence; an item that needs explanation \
is a paragraph. When completeness demands a long enumeration, it is one list \
under one lead paragraph, not a list under a heading per group.
- Tables only for comparisons or structured data: two or more comparable items \
with two or more attributes. Never a table for a single fact list or for \
narrated prose.
- Bold only for semantic anchors — a concept, a distinction, a critical term, a \
decision label: a bold span is at most FIVE words, most paragraphs carry zero \
or one, and no sentence, clause, bullet lead-in or conclusion is ever bold in \
full. The eye must learn what matters from the bold alone.
- `**key:** value` rundowns, ASCII maps and "at least one visible structure" are \
options, not requirements: use them only when the content is a configuration, a \
pipeline, or a comparison the reader would otherwise have to reconstruct. A \
plain factual answer is paragraphs.
- Citation tags stay at the END of the sentence or paragraph they support — \
never inside headings or bold anchors."""

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
        f"{_LLM_GROUNDING}{layer}\n\n{POLYMATH_STYLE_PROMPT}\n\n{_PRESENTATION_BLOCK}\n\n"
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
    seen_chunks: set[str] = set()
    for item in bundle.get("evidence_bundle") or []:
        if len(out) >= _LEGEND_ITEMS:
            break
        # EVIDENCE-DIET-V1 (backlog B11, measured 2026-09-06): document- and section-summary rows were offered
        # 569 / 960 times in a day and cited 0 times; they cost prompt space and [S#] tags the model never used.
        # The prompt now carries PASSAGES only; a passage's parent context rides its own legend line as a
        # breadcrumb ("book › section") instead of a separate row. The bundle itself is unchanged (the
        # deterministic synthesizer and /retrieve keep their summaries).
        if item.get("text_kind") in _SUMMARY_TEXT_KINDS:
            continue
        # GRAPH-EVIDENCE-HYGIENE-V1 (backlog B8): the assembler turns every graph fact into a `claim`
        # item carrying its provenance passage and sorts claims FIRST. Those passages were never judged.
        # Facts now ride the labelled RELATIONS `[G#]` block (ELITE-MODE D), bound to a proving `[S#]`
        # only when that child is already in the judged legend. Unjudged provenance is never an [S#].
        if item.get("kind") == "claim":
            continue
        span = item.get("source_span") or {}
        loc = span.get("locator") or ""
        text = (span.get("text") or "")[:_EVIDENCE_TEXT_CHARS]
        if loc and text:
            m = _LOC_CHUNK_RE.match(str(loc))
            cid = (m.group(1) if m else (item.get("source_chunk_id") or None))
            if cid and cid in seen_chunks:            # B8: one tag per passage (S1 = S4 duplicates were real)
                continue
            if cid:
                seen_chunks.add(cid)
            out.append({"tag": f"S{len(out) + 1}", "locator": loc,
                        "chunk_id": cid,
                        "doc_id": item.get("source_document_id"), "text": text,
                        "breadcrumb": _breadcrumb(item),
                        "carried": bool(item.get("carried")), "carry_score": item.get("carry_score")})
    return out


#: EVIDENCE-DIET-V1: the assembler's summary kinds (never prompt rows); carried items have no text_kind
_SUMMARY_TEXT_KINDS = ("document_summary", "section_summary")


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_SOURCE_SUFFIX_RE = re.compile(r"(?:\s*\d+)?(?:_[0-9a-f]{6,}|\s*\(\d+\))+$", re.I)   # " 1_9e6b68fb", " (1)"


def _clean_crumb(part: str) -> str:
    """One breadcrumb segment: Markdown links → their text, whitespace collapsed, ≤ 90 chars."""
    part = _MD_LINK_RE.sub(r"\1", str(part or ""))
    part = re.sub(r"\s+", " ", part).strip(" #›-–—:|")
    return part[:90].rstrip()


def _clean_source(name: str) -> str:
    """A document's display name: extension and content-hash / '(1)' suffixes removed."""
    name = str(name or "").strip()
    name = re.sub(r"\.(md|html?|pdf|epub|txt|docx?)$", "", name, flags=re.I)
    return _clean_crumb(_SOURCE_SUFFIX_RE.sub("", name))


def _breadcrumb(item: dict) -> str:
    """"book › section" for a passage — the assembler's presentation join (heading_path; every cinema
    child has one) with source › title as the fallback and the bare source name as the floor. Segments
    are cleaned for reading: no file extension or hash suffix on the book, no Markdown link syntax in
    headings, at most three segments."""
    pres = item.get("presentation") or {}
    source = ((item.get("applicability") or {}).get("source_name") or pres.get("source_name") or "").strip()
    human = (pres.get("human_locator") or "").strip()
    if human:
        parts = [x for x in human.split("›")]
        head = _clean_source(parts[0]) if parts else ""
        tail = [c for c in (_clean_crumb(x) for x in parts[1:]) if c]
        if len(tail) > 2:
            tail = [tail[0], tail[-1]]
        segs = [x for x in [head, *tail] if x]
        if segs:
            return " › ".join(segs)
    title = _clean_crumb(pres.get("title") or "")
    book = _clean_source(source)
    return f"{book} › {title}" if book and title else (book or title)


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


def _profile_scout(message: str, corpus_ids) -> tuple[list[str], object | None, dict]:
    """PROFILE-SCOUT-V1 (P5b) - pre-plan corpus reconnaissance that REPLACES the retired B16 title
    injection. Flag POLYMATH_PROFILE_SCOUT (default off). Embeds the message once, runs the two
    existing profile projections (profile_nominate -> doc_ids, search_atoms -> atom hits) per
    corpus, normalizes into ScoutHits and fuses them (deterministic RRF, P5a), then returns the
    nominated documents' source_names as the compiler's corpus conditioning (the same titles=
    channel), the fused `ProfileScoutResult` (for P6 subquery-provenance annotation; None when
    off/failed), plus a receipt. Fail-open: any failure returns [], None and the compiler runs
    without conditioning. Never raises. The scout informs the planner; it never gates. Live=L1-L5."""
    import time as _t
    enabled = os.environ.get("POLYMATH_PROFILE_SCOUT", "0") == "1"
    rec: dict = {"contract": "profile-scout-v1", "enabled": enabled}
    if not enabled:
        return [], None, rec
    corpora = [c for c in (corpus_ids or []) if c]
    if not corpora:
        rec["reason"] = "no_corpus"
        return [], None, rec
    t0 = _t.perf_counter()
    try:
        from polymath_shared.document_profile import profile_atom_projection as _pap
        from polymath_shared.document_profile import projection as _pj
        from polymath_shared.document_profile.profile_scout import (
            atom_hits_from_search, fuse_profile_scout_hits, profile_hits_from_doc_ids)
        from polymath_shared.embedding_contracts import active_contract
        from polymath_shared.settings import get_settings as _gs
        from polymath_shared.surface_registry import ATOM_KINDS, BY_KIND
        from orchestrator.api.fast import _embed_queries
        from qdrant_client import QdrantClient as _QC

        contract_id = active_contract().contract_id
        qv = list(_embed_queries([message])[0])

        def _group_of(kind):
            pol = BY_KIND.get(kind)
            return pol.group if pol else None

        client = _QC(url=_gs().stores.qdrant_url, timeout=10)
        profile_hits: list = []
        atom_hits: list = []
        try:
            for corpus_id in corpora:
                doc_ids = _pj.profile_nominate(client, _pj.collection_name(contract_id), qv, corpus_id, k=8)
                profile_hits.extend(profile_hits_from_doc_ids(doc_ids))
                rows = _pap.search_atoms(client, _pap.collection_name(contract_id), qv, ATOM_KINDS, k=12)
                atom_hits.extend(atom_hits_from_search(rows, group_of=_group_of))
        finally:
            client.close()
        result = fuse_profile_scout_hits(profile_hits, atom_hits)
        names = _scout_source_names([n.doc_id for n in result.nominations], corpora)
        rec.update({"nominations": len(result.nominations), "n_injected": len(names),
                    "ms": round((_t.perf_counter() - t0) * 1000, 1)})
        return names, result, rec
    except Exception as exc:  # noqa: BLE001 - reconnaissance is optional; the compiler runs without it
        rec.update({"reason": f"scout:{type(exc).__name__}", "error": str(exc)[:120],
                    "ms": round((_t.perf_counter() - t0) * 1000, 1)})
        return [], None, rec


def _scout_source_names(doc_ids, corpora) -> list[str]:
    """Map the scout's nominated doc_ids to their source_name (the compiler's title channel),
    preserving nomination order. A read; never breaks the compile."""
    ids = [d for d in doc_ids if d]
    if not ids:
        return []
    try:
        with tx() as conn:
            rows = conn.execute(
                "SELECT doc_id, source_name FROM documents WHERE doc_id = ANY(%s) AND corpus_id = ANY(%s)",
                (ids, corpora)).fetchall()
    except Exception:  # noqa: BLE001 - the catalog is a read; never breaks the compile
        return []
    by_id = {r[0]: r[1] for r in rows}
    return [by_id[d] for d in ids if by_id.get(d)]


def _corpus_source_index(corpora) -> dict[str, str]:
    """CA1/CA2 identity index: {doc_id: source_name} for the active corpus/corpora. A cheap
    metadata read, called ONLY when the plan carries an explicit constraint (no cost on the common
    path). Never breaks the compile."""
    try:
        with tx() as conn:
            rows = conn.execute(
                "SELECT doc_id, source_name FROM documents WHERE corpus_id = ANY(%s)",
                (list(corpora),)).fetchall()
    except Exception:  # noqa: BLE001 - a read; never breaks the compile
        return {}
    return {r[0]: r[1] for r in rows if r[0] and r[1]}


def _resolve_plan_constraints(plan, scout_result, corpora) -> None:
    """CONSTRAINT-AWARE-RETRIEVAL-V1 CA2 — resolve the plan's explicit SOURCE constraints to corpus
    doc_ids (deterministic identity, corpus-scoped; Scout as bounded confirmation). Populates
    `plan.explicit_constraints[*].resolved_targets` for the receipt. NO ranking effect — CA2 only
    enriches the plan; ranking use is CA3. Fail-open; only touches the corpus index when a
    constraint is present."""
    cons = getattr(plan, "explicit_constraints", None)
    if not cons:
        return
    from polymath_shared.query_constraints import resolve_constraint_targets
    src_index = _corpus_source_index(corpora)
    noms = [getattr(n, "doc_id", "") for n in (getattr(scout_result, "nominations", None) or [])]
    plan.explicit_constraints = resolve_constraint_targets(
        cons, src_index, scout_nominations=noms,
        corpus_id=(list(corpora)[0] if corpora else None))


def _maybe_resolve(plan, fast, aspects, weak, retrieve_fn) -> dict | None:
    """EVIDENCE-RESOLUTION-V1 (librarian P10) — bounded, evidence-driven resolution round on the
    LIVE path. After round 1, the weak aspects (subqueries that reached NO final evidence) are the
    unresolved needs; if a material one remains, fire ONE targeted round 2 through the SAME
    retrieval machinery (`retrieve_fn`) and MERGE its new source children into `fast["evidence"]`
    (so synthesis uses the new evidence). Explicit stop: at most one round; no gap ⇒ no round 2.
    Reuses the planner/engine — no second RAG pipeline. Flag `POLYMATH_CHAT_RESOLUTION`, fail-open."""
    from polymath_shared.evidence_resolution import (ClaimState, RetrievalState,
                                                     plan_resolution_round, resolution_receipt)
    # A material need is a REQUIRED (q0-derived, origin=USER) aspect that reached NO final evidence.
    # Exploratory PROFILE-expansion probes (origin=PROFILE) are NOT required needs — a profile probe
    # finding nothing is not an evidence gap, so it must not trigger a resolution round.
    origin_of = {q.id: getattr(q, "origin", "USER") for q in (plan.queries or [])}
    claims = []
    for i, qid in enumerate(weak or []):
        if origin_of.get(str(qid), "USER") != "USER":
            continue
        need = ((aspects.get(qid) or {}).get("query")) or ""
        if not need:
            continue
        claims.append(ClaimState(claim_id=str(qid), importance=max(0.5, 0.9 - 0.1 * i),
                                 evidence_state="UNSUPPORTED", next_information_need=need))
    state = RetrievalState(original_query=plan.original_request, round=1, unresolved_needs=tuple(claims),
                           evidence_chunks=tuple(c.get("chunk_id") for c in (fast.get("evidence") or [])))
    decision = plan_resolution_round(state)
    rec = resolution_receipt(state, decision)
    if not decision.should_resolve or decision.query is None:
        return rec                                   # round 1 sufficient — explicit stop, no round 2
    fast2 = retrieve_fn(decision.query.query)         # ONE bounded round 2, existing machinery
    have = {c.get("chunk_id") for c in (fast.get("evidence") or [])}
    new_ev = [c for c in (fast2.get("evidence") or []) if c.get("chunk_id") and c.get("chunk_id") not in have][:6]
    if new_ev:
        fast["evidence"] = (fast.get("evidence") or []) + new_ev   # merge → evidence_rows → synthesis
    rec["round2"] = {"query": decision.query.query, "claim": decision.claim.claim_id if decision.claim else None,
                     "new_evidence": len(new_ev),
                     "new_docs": sorted({c.get("doc_id") for c in new_ev if c.get("doc_id")})}
    return rec


def _compute_profile_yield(plan, aspects) -> dict | None:
    """P11 (PROFILE-YIELD-RECEIPT-V1): of the PROFILE-origin subqueries the profile expansion added,
    how many surfaced FINAL evidence (the aspect trace's `final` > 0)? Distinguishes profile
    expansion OCCURRING from it actually PRODUCING source evidence. None when no PROFILE subquery
    ran (profile-expansion flag off)."""
    prof = [q for q in (plan.queries if plan is not None else []) if getattr(q, "origin", "USER") == "PROFILE"]
    if not prof:
        return None
    yielded = [q.id for q in prof if int(((aspects or {}).get(q.id) or {}).get("final") or 0) > 0]
    denom = len(prof)
    return {"contract": "profile-yield-v1", "profile_subqueries": denom,
            "profile_subqueries_with_evidence": len(yielded),
            "profile_expansion_evidence_yield": round(len(yielded) / denom, 3) if denom else 0.0,
            "expansion_occurred": denom > 0, "expansion_yielded_evidence": len(yielded) > 0,
            "yielded_query_ids": yielded}


def _add_profile_expansion(plan, scout_result) -> None:
    """PROFILE-EXPANSION-V1 (librarian P11): turn the top scout nominations into a bounded number of
    PROFILE-origin subqueries so the corpus profile can DISCOVER documents q0's literal terms would
    miss. Additive — q0 and its aspect subqueries are untouched; the scout INFORMS, never gates.
    Flag `POLYMATH_CHAT_PROFILE_EXPANSION` (default off), fail-open. Each added subquery searches a
    verbatim matched surface of a nominated document; whether it yields FINAL evidence is the P11
    `profile_expansion_evidence_yield` metric (computed post-retrieval from the aspect trace)."""
    if os.environ.get("POLYMATH_CHAT_PROFILE_EXPANSION", "0") != "1":
        return
    noms = list(getattr(scout_result, "nominations", None) or ())
    if not noms:
        return
    # q0 AUTHORITY: profile-expansion SUPPLEMENTS an existing q0 retrieval — it must never CREATE
    # retrieval where the compiler decided none. A no-retrieval / general-knowledge / corpus-absent
    # query (no PRIMARY) must NOT gain fabricated evidence from the scout's fail-open nominations.
    if not any(q.type == "PRIMARY" for q in plan.queries):
        return
    from polymath_shared.chat_plan import MAX_QUERY_WORDS, CompiledQuery
    max_add = int(os.environ.get("POLYMATH_CHAT_PROFILE_EXPANSION_MAX", "2"))
    existing = {(q.query or "").strip().lower() for q in plan.queries}
    added = 0
    for nom in noms:
        if added >= max_add:
            break
        text = (getattr(nom, "representative_text", None) or "").strip()
        if not text:
            continue
        q = " ".join(text.split()[:MAX_QUERY_WORDS]).strip()
        if not q or q.lower() in existing:
            continue
        plan.queries.append(CompiledQuery(
            id=f"p{added}", type="ENTITY", query=q, weight=0.6, role="bridge", origin="PROFILE",
            inspired_by_profile=[nom.doc_id], profile_surface=getattr(nom, "representative_surface", None),
            target=nom.doc_id))
        existing.add(q.lower())
        added += 1
    plan.compiler["profile_expansion"] = {"added": added, "flag": True}


#: WLK2C C3-live — the bounded concept-bridge model (the WILDCARD cloud-Gemma path via the local Ollama
#: daemon). One call, low temperature, capped tokens, bounded timeout. Configurable; defaults to the
#: free-tier gemma the synthesizer catalog already uses.
_BRIDGE_MODEL = (os.environ.get("POLYMATH_BRIDGE_MODEL", "gemma4:31b-cloud") or "gemma4:31b-cloud").split("ollama:")[-1]
_BRIDGE_TIMEOUT_S = float(os.environ.get("POLYMATH_BRIDGE_TIMEOUT_S", "12"))
_BRIDGE_NUM_PREDICT = int(os.environ.get("POLYMATH_BRIDGE_NUM_PREDICT", "700"))

#: CORPUS-EXPLORER-V1: origins that ride the WLK2C latent pass (C4 grading + latent-pool exposure). Adding
#: a latent origin here (not scattered `== "BRIDGE"` checks) routes CORPUS_EXPLORE through the same C4/C5
#: gate as a Scout BRIDGE. When POLYMATH_CORPUS_EXPLORER is off no CORPUS_EXPLORE origin is ever produced,
#: so this set behaves identically to the old BRIDGE-only checks (flag-off = pre-feature-equivalent).
LATENT_ORIGINS = ("BRIDGE", "CORPUS_EXPLORE")


def _add_bridge_expansion(plan, scout_result) -> None:
    """WLK2C C3-live (bounded concept-bridge compiler). Flag `POLYMATH_CHAT_BRIDGE_COMPILER` (default
    off). ACTIVATION of grounded scout-nominated concepts, never invention. Runs AFTER Scout (it needs
    the nominations) and after profile-expansion (so tier-1 reuse sees existing subqueries). q0 authority:
    no PRIMARY ⇒ no expansion. FAIL-OPEN — a timeout, provider error, malformed/empty output, or zero
    admitted bridges leaves the pre-WLK2C plan untouched; bridge generation NEVER blocks the answer. ONE
    bounded Gemma call, ≤4 bridges. C3 only adds structurally-valid BRIDGE_CANDIDATE subqueries with full
    lineage; C4 owns the decisive bridge↔q0 semantic rejection. Records the C6 observability metrics
    (attempted/succeeded/generated/admitted/rejected/fallback_reason/latency_ms) on plan.compiler."""
    if os.environ.get("POLYMATH_CHAT_BRIDGE_COMPILER", "0") != "1":
        return
    if not any(q.type == "PRIMARY" for q in plan.queries):
        return
    noms = list(getattr(scout_result, "nominations", None) or ())
    if not noms:
        return
    import time as _t
    diag = {"attempted": False, "succeeded": False, "generated": 0, "admitted": 0, "rejected": 0,
            "fallback_reason": None, "latency_ms": 0.0}
    t0 = _t.perf_counter()
    try:
        from polymath_shared.bridge_integration import plan_bridge_expansion

        def _bridge_generate(prompt: str) -> str:
            import httpx
            r = httpx.post(f"{OLLAMA_URL}/api/chat",
                           json={"model": _BRIDGE_MODEL, "stream": False, "think": False,
                                 "messages": [{"role": "user", "content": prompt}],
                                 "options": {"temperature": 0.1, "num_predict": _BRIDGE_NUM_PREDICT}},
                           timeout=httpx.Timeout(_BRIDGE_TIMEOUT_S, connect=5))
            r.raise_for_status()
            return ((r.json() or {}).get("message") or {}).get("content") or ""

        diag["attempted"] = True
        res = plan_bridge_expansion(plan, noms, generate=_bridge_generate)
        diag["generated"] = res.get("generated") or 0
        diag["admitted"] = res.get("admitted") or 0
        diag["rejected"] = max(0, (res.get("generated") or 0) - (res.get("admitted") or 0))
        diag["succeeded"] = (res.get("added") or 0) > 0
        if not res.get("eligible", False):
            diag["fallback_reason"] = res.get("reason")
        elif (res.get("added") or 0) == 0:
            diag["fallback_reason"] = "no_valid_bridges"
    except Exception as exc:  # noqa: BLE001 — FAIL-OPEN: the optional bridge layer never blocks the answer
        diag["fallback_reason"] = f"error:{type(exc).__name__}"
    diag["latency_ms"] = round((_t.perf_counter() - t0) * 1000, 1)
    try:
        plan.compiler["bridge_expansion"] = {**(plan.compiler.get("bridge_expansion") or {}), **diag}
    except Exception:  # noqa: BLE001
        pass


def _add_corpus_explore_expansion(plan, message, corpus_ids, scout_result, *, enabled: bool,
                                  upstream_error: str | None = None) -> None:
    """CORPUS-EXPLORER-V1 CE4 (live). TWO-LAYER GATE: the server capability `POLYMATH_CORPUS_EXPLORER`
    (default off) AND the per-request `enabled` flag (the "Corpus Explore" toggle) must BOTH be true; a
    fallback plan is skipped. Builds a NON-GENERATIVE, concept-keyed activation set from the corpus's own
    CONCEPT/THEORY atoms (`search_atoms`, INDEPENDENT of Scout — Scout nominations are optional
    corroboration), then REUSES the WLK2C bridge compiler to emit CORPUS_EXPLORE-origin subqueries. Runs
    LAST in `_finish` (after annotate, which would otherwise strip the activation `inspired_by_profile`
    links). q0 authority (no PRIMARY ⇒ nothing). FAIL-OPEN throughout — activation/generation never blocks
    the answer. One bounded Gemma call (the reused bridge model), ≤N bridges.

    CORPUS-EXPLORE-FIRING-V1: every gate below fills a `FiringState`; the resulting receipt
    (`plan.compiler['corpus_explore_firing']`, exactly ONE cause code per non-firing request) is written on
    EVERY path, so no fallback is silent. Observation only — no gate, threshold or ranking changed."""
    from polymath_shared.corpus_explore_firing import FiringState, fallback_blocks_explorer, firing_receipt
    st = FiringState(capability_on=os.environ.get("POLYMATH_CORPUS_EXPLORER", "0") == "1",
                     requested=bool(enabled),
                     plan_fallback=bool(getattr(plan, "fallback", False)),
                     has_primary=any(q.type == "PRIMARY" for q in (plan.queries or [])),
                     upstream_error=upstream_error, intent=(getattr(plan, "intent", "") or None))
    try:
        st.fallback_reason = str((plan.compiler or {}).get("reason") or "")[:120] or None
    except Exception:  # noqa: BLE001
        pass
    # CORPUS-EXPLORE-FIRING-V1 Phase B: a NO-JUDGMENT fallback (compiler unreachable / too late /
    # unparseable) no longer closes the explorer — it has a q0 PRIMARY and a deterministic intent, and the
    # Scout BRIDGE expansion has always run on it. An INVALID-JUDGMENT fallback (`invalid_plan:*`) still
    # closes it. Kill switch `POLYMATH_CORPUS_EXPLORER_FALLBACK_OPEN` (default 0 = the pre-fix gate).
    st.fallback_blocks = fallback_blocks_explorer(st.fallback_reason) if st.plan_fallback else True
    if not st.has_primary:
        try:
            if not getattr(plan, "retrieval_required", True):
                st.no_primary_reason = f"retrieval_not_required:{getattr(plan, 'task_type', '') or ''}"
        except Exception:  # noqa: BLE001
            pass

    def _stamp() -> None:
        try:
            plan.compiler["corpus_explore_firing"] = firing_receipt(st)
        except Exception:  # noqa: BLE001
            pass

    if (not st.requested or not st.capability_on or (st.plan_fallback and st.fallback_blocks)
            or not st.has_primary or upstream_error):
        _stamp()
        return
    import time as _t
    diag = {"attempted": False, "activations": 0, "added": 0, "fallback_reason": None, "latency_ms": 0.0}
    t0 = _t.perf_counter()
    try:
        from polymath_shared.corpus_activation import (
            CONCEPT_ATOM_KINDS, activate_corpus, activation_receipt)
        from polymath_shared.corpus_explore import plan_corpus_explore_expansion
        from polymath_shared.document_profile import profile_atom_projection as _pap
        from polymath_shared.embedding_contracts import active_contract
        from polymath_shared.settings import get_settings as _gs
        from orchestrator.api.fast import _embed_queries
        from qdrant_client import QdrantClient as _QC

        corpora = [c for c in (corpus_ids or []) if c]
        if not corpora:
            diag["fallback_reason"] = "no_corpus"
            st.no_corpus = True
        else:
            contract_id = active_contract().contract_id
            st.stage = "embed"
            qv = list(_embed_queries([message])[0])
            max_acts = int(os.environ.get("POLYMATH_CORPUS_EXPLORER_MAX_ACTIVATIONS", "8"))
            max_add = int(os.environ.get("POLYMATH_CORPUS_EXPLORER_MAX_BRIDGES", "4"))
            min_grounding = int(os.environ.get("POLYMATH_CORPUS_EXPLORER_MIN_GROUNDING", "1"))
            st.stage = "search"
            client = _QC(url=_gs().stores.qdrant_url, timeout=10)
            adiag: dict = {}
            try:
                def _fetch(cid):
                    return _pap.search_atoms(client, _pap.collection_name(contract_id), qv,
                                             CONCEPT_ATOM_KINDS, k=12)
                activations = activate_corpus(
                    corpus_ids=corpora, fetch_atoms=_fetch,
                    scout_nominations=getattr(scout_result, "nominations", None),
                    max_activations=max_acts, min_grounding=min_grounding, diag=adiag)
                st.n_hits = adiag.get("n_hits")
                st.fetch_errors = len(adiag.get("fetch_errors") or [])
                st.n_candidates = len(activations)
                if not st.n_hits and not st.fetch_errors:
                    # zero hits: is there anything to search at all? (NO_ATOM_COVERAGE vs ATOMS_EMPTY)
                    try:
                        from qdrant_client.http import models as _qm
                        st.atom_universe = int(client.count(
                            _pap.collection_name(contract_id), exact=False,
                            count_filter=_qm.Filter(must=[_qm.FieldCondition(
                                key="atom_kind", match=_qm.MatchAny(any=list(CONCEPT_ATOM_KINDS)))])).count)
                    except Exception:  # noqa: BLE001
                        st.atom_universe = None
            finally:
                client.close()
            st.stage = "expand"
            diag["activations"] = len(activations)
            plan.compiler["corpus_activation"] = activation_receipt(activations)
            if not activations:
                diag["fallback_reason"] = "no_activations"
            else:
                def _explore_generate(prompt: str) -> str:
                    import httpx
                    r = httpx.post(f"{OLLAMA_URL}/api/chat",
                                   json={"model": _BRIDGE_MODEL, "stream": False, "think": False,
                                         "messages": [{"role": "user", "content": prompt}],
                                         "options": {"temperature": 0.1, "num_predict": _BRIDGE_NUM_PREDICT}},
                                   timeout=httpx.Timeout(_BRIDGE_TIMEOUT_S, connect=5))
                    r.raise_for_status()
                    return ((r.json() or {}).get("message") or {}).get("content") or ""

                diag["attempted"] = True
                res = plan_corpus_explore_expansion(plan, activations, generate=_explore_generate,
                                                    max_add=max_add)
                diag["added"] = res.get("added") or 0
                st.eligible = bool(res.get("eligible", False))
                st.eligible_reason = res.get("reason")
                st.intent = res.get("intent") or st.intent
                st.generate_error = res.get("generate_error")
                st.json_status = res.get("json_status")
                st.generated = res.get("generated")
                st.admitted = res.get("admitted")
                st.added = diag["added"]
                if not res.get("eligible", False):
                    diag["fallback_reason"] = res.get("reason")
                elif (res.get("added") or 0) == 0:
                    diag["fallback_reason"] = "no_valid_bridges"
    except Exception as exc:  # noqa: BLE001 — FAIL-OPEN: the optional explorer never blocks the answer
        diag["fallback_reason"] = f"error:{type(exc).__name__}"
        if st.stage in ("embed", "search"):
            st.atoms_error = type(exc).__name__
        else:
            st.explorer_error = type(exc).__name__
    diag["latency_ms"] = round((_t.perf_counter() - t0) * 1000, 1)
    try:
        plan.compiler["corpus_explore_expansion"] = {
            **(plan.compiler.get("corpus_explore_expansion") or {}), **diag}
    except Exception:  # noqa: BLE001
        pass
    _stamp()


def _turn_firing_receipt(plan, *, requested: bool, compiler_flag: str, retrieval_skipped: bool) -> dict:
    """CORPUS-EXPLORE-FIRING-V1: the TURN-level firing receipt. The plan-level receipt says whether the
    explorer added subqueries; the turn can still not fire (no plan at all, a shadow compiler whose plan
    never reaches retrieval, or a turn that skipped retrieval). Re-stamps the plan receipt so
    `chat_plan.compiler.corpus_explore_firing` is the turn's one truth. Never raises."""
    from polymath_shared.corpus_explore_firing import turn_receipt
    rec = None
    try:
        rec = (getattr(plan, "compiler", None) or {}).get("corpus_explore_firing") if plan is not None else None
    except Exception:  # noqa: BLE001
        rec = None
    out = turn_receipt(rec, capability_on=os.environ.get("POLYMATH_CORPUS_EXPLORER", "0") == "1",
                       requested=requested, compiler_applied=(compiler_flag == "on"),
                       retrieval_skipped=retrieval_skipped, compiler_flag=compiler_flag)
    try:
        if plan is not None and isinstance(getattr(plan, "compiler", None), dict):
            plan.compiler["corpus_explore_firing"] = out
    except Exception:  # noqa: BLE001
        pass
    return out


def _bridge_role(q) -> str:
    """The C2 proposed role of a BRIDGE subquery (encoded in its reason `bridge/<role> <- …`)."""
    reason = str(getattr(q, "reason", "") or "")
    if reason.startswith("bridge/"):
        r = reason[7:].split()[0].strip().upper()
        if r in ("COMPLEMENTARY", "DIVERGENT"):
            return r
    return "COMPLEMENTARY"


def _selected_lineage(elig: dict, bridges: dict) -> dict | None:
    """The WINNING bridge lineage for a seated latent chunk (persisted on the final evidence — not just
    a seat_role). Picks the first admissible path (they are evaluated best-first)."""
    for lr in (elig.get("lineage_results") or []):
        if lr.get("state") in ("COMPLEMENTARY_ELIGIBLE", "DIVERGENT_ELIGIBLE"):
            bid = lr.get("bridge_id")
            return {"bridge_id": bid, "origin_query": (bridges.get(bid) or {}).get("query"),
                    "proposed_role": lr.get("proposed_role"), "c4_state": lr.get("state"),
                    "scores": lr.get("scores")}
    return None


def _apply_latent_selection(fast, plan, q0_text) -> dict | None:
    """WLK2C C4-live/C5-live — an ADDITIVE second portfolio pass. Grades the BOUNDED bridge pool
    (`fast['latent_pool']`) with C4 and re-seats [q0 evidence + latent] with C5, gated by the q0
    grounding, WITHOUT mutating the q0 rows in place: it reassigns `fast['evidence']` to a NEW list.
    Flag `POLYMATH_CHAT_LATENT_SELECTION` (default off) / no bridges / no pool ⇒ returns None and leaves
    `fast['evidence']` untouched (byte-identical, trivial rollback). q0 stays primary; the FINAL CA4
    grade + answerability gate still run downstream on the result (C5 never bypasses CA4). Fail-open:
    any error leaves the pre-WLK2C evidence intact. Returns the C6 calibration receipt."""
    if os.environ.get("POLYMATH_CHAT_LATENT_SELECTION", "0") != "1":
        return None
    pool_extra = fast.get("latent_pool")
    if not pool_extra or plan is None:
        return None
    bridges = {q.id: {"query": q.query, "proposed_role": _bridge_role(q)}
               for q in plan.queries if getattr(q, "origin", "") in LATENT_ORIGINS}
    if not bridges:
        return None
    import time as _t
    try:
        from orchestrator.api.fast import _rerank_children
        from polymath_shared.latent_selection import grade_and_seat_latent
        from polymath_shared.query_constraints import grade_evidence
        q0_ev = list(fast.get("evidence") or [])
        try:
            _g, epi = grade_evidence(q0_ev, plan)                      # q0 grounding (preliminary CA4)
            establishes_need = bool(epi.get("establishes_need", True)); n_direct = int(epi.get("n_direct", 0))
        except Exception:  # noqa: BLE001
            establishes_need, n_direct = True, 0

        def _row(r, orig):
            return {"chunk_id": r.get("chunk_id"), "doc_id": r.get("doc_id"), "parent_id": r.get("parent_id"),
                    "text": r.get("text", ""), "query_ids": r.get("query_ids") or [],
                    "q0_score": (r.get("g3_score") if orig else r.get("q0_score")),
                    "source_name": r.get("source_name", ""), "_orig": (r if orig else None)}
        combined = [_row(r, True) for r in q0_ev] + [_row(r, False) for r in pool_extra]
        t0 = _t.perf_counter()
        seated, tr = grade_and_seat_latent(q0_text=q0_text, pool=combined, bridges=bridges,
                                           rerank=_rerank_children, capacity=max(1, len(q0_ev)),
                                           establishes_need=establishes_need, has_direct_grounding=(n_direct >= 1))
        seat_ms = round((_t.perf_counter() - t0) * 1000, 1)

        new_ev = []
        for s in seated:
            c = s["cand"]; orig = c.get("_orig")
            row = dict(orig) if orig else {
                "chunk_id": c["chunk_id"], "doc_id": c.get("doc_id"), "parent_id": c.get("parent_id"),
                "text": c.get("text", ""), "source_name": c.get("source_name", ""),
                "query_ids": c.get("query_ids") or [], "g3_score": c.get("q0_score"),
                "arrival": "LATENT_BRIDGE", "role": "LATENT"}
            row["latent_role"] = s["seat_role"]
            if s["seat_role"] in ("COMPLEMENTARY", "DIVERGENT"):
                sl = _selected_lineage(s.get("eligibility") or {}, bridges)
                if sl:
                    row["latent_lineage"] = sl
            new_ev.append(row)
        fast["evidence"] = new_ev                                     # additive second pass — q0 rows copied, not mutated
        return {"enabled": True, "n_bridges": tr.get("n_bridges"), "establishes_need": establishes_need,
                "n_direct": n_direct, "divergent_allowed": tr.get("divergent_allowed"),
                "counts": {k: tr.get(k) for k in ("direct", "complementary", "divergent", "fill")},
                "bridge_q0": tr.get("bridge_q0"), "graded": tr.get("graded"),
                "latency_ms": {"portfolio_seating": seat_ms}}
    except Exception as exc:  # noqa: BLE001 — FAIL-OPEN: never break the turn on the latent layer
        return {"enabled": True, "error": f"{type(exc).__name__}"}


def _compile_chat_plan(message: str, history, corpus_ids, *, session_key: str | None = None,
                       titles_rank: str | None = None, corpus_explorer: bool = False):
    """CHAT-INTENT-PLAN-V1 through the `chat_compiler` stage pin (plan §3.2):
    one cheap lane, one call, strict local validation, deterministic fallback.
    The lane is chosen per session key (ring), each lane self-gates through
    its own limiter. Never raises. PROFILE-SCOUT-V1: profile reconnaissance conditions the
    compiler when POLYMATH_PROFILE_SCOUT is on (B16 title injection retired)."""
    from polymath_shared.chat_plan import COMPILER_STAGE, compile_plan, fallback_plan
    try:
        titles, scout_result, scout_rec = _profile_scout(message, corpus_ids)
    except Exception as exc:  # noqa: BLE001
        titles, scout_result, scout_rec = [], None, {"contract": "profile-scout-v1", "reason": f"scout:{type(exc).__name__}"}

    def _finish(plan):
        """P6/P11: (1) optionally add bounded PROFILE-origin subqueries from the scout's
        nominations (profile-driven discovery), then (2) annotate every subquery with
        deterministic provenance (q0 authority, scout links validated). Fail-open — never a turn
        breaker; q0 and its aspects are untouched."""
        _upstream_err = None
        try:
            _add_profile_expansion(plan, scout_result)
            _add_bridge_expansion(plan, scout_result)                   # WLK2C C3: bounded concept-bridge compiler (flag-gated, fail-open)
            from polymath_shared.subquery_provenance import annotate_subquery_provenance
            annotate_subquery_provenance(plan, scout_result)
            _resolve_plan_constraints(plan, scout_result, corpus_ids)   # CA2: identity resolution, no ranking effect
        except Exception as exc:  # noqa: BLE001
            _upstream_err = type(exc).__name__
        try:
            # CORPUS-EXPLORER-V1 CE4: two-layer-gated (capability x per-request) concept-activation-derived
            # exploration. LAST — after annotate (which would strip the activation inspired_by links).
            # CORPUS-EXPLORE-FIRING-V1: an upstream finish failure still skips the explorer (unchanged
            # behavior) but is now COUNTED in the firing receipt instead of vanishing.
            _add_corpus_explore_expansion(plan, message, corpus_ids, scout_result, enabled=corpus_explorer,
                                          upstream_error=_upstream_err)
        except Exception:  # noqa: BLE001
            pass
        return plan
    try:
        from polymath_shared.llm_extraction.client import LLMExtractionClient
        from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin
        key = session_key or message[:64]
        pin = stage_pin(COMPILER_STAGE) or []
        endpoints = [e for e in cloud_endpoints() if e.name in pin]
        if not endpoints:
            plan = fallback_plan(message, reason="compiler_unavailable:no_active_lane")
            plan.compiler["scout"] = scout_rec
            return _finish(plan)
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
            # REASONING-BOUNDARY-V1: mark this as the chat-COMPILER (STRUCTURED_COMPILER) so _chat overlays
            # the reasoning-budget policy at runtime (no-op unless POLYMATH_REASONING_POLICY=1). Only the
            # compiler's dedicated client carries this attribute; document-extraction clients never do, so
            # extraction is byte-identical and its contract hash is untouched.
            client.reasoning_role = "STRUCTURED_COMPILER"

            def _complete(system_prompt: str, user_prompt: str, max_tokens: int, _c=client):
                return _c.complete_one(user_prompt, system_prompt=system_prompt, max_tokens=max_tokens)
            plan = compile_plan(message, history, corpus_ids, _complete, model=f"{ep.name}:{ep.model}", titles=titles)
            plan.compiler["lane"] = ep.name
            plan.compiler["scout"] = scout_rec
            plan.compiler["attempt"] = attempt_no
            if last is not None:
                plan.compiler["first_failure"] = last
            if not plan.fallback or not str(plan.compiler.get("reason", "")).startswith("transport:"):
                return _finish(plan)
            _COMPILER_LANE_FAILED_AT[ep.name] = time.time()
            last = f"{ep.name}:{plan.compiler.get('reason')}"
        return _finish(plan)
    except Exception as exc:  # noqa: BLE001 — a missing pin / dark lane is a receipted fallback
        plan = fallback_plan(message, reason=f"compiler_unavailable:{type(exc).__name__}")
        plan.compiler["scout"] = scout_rec
        return _finish(plan)


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
        return {"prompt_contract": _SYNTHESIS_CONTRACT, "presentation_contract": _PRESENTATION_CONTRACT}
    return {"prompt_contract": _SYNTHESIS_CONTRACT, "presentation_contract": _PRESENTATION_CONTRACT,
            "task_type": plan.task_type, "evidence_policy": plan.evidence_policy,
            "response_type": plan.response_type, "retrieval_required": plan.retrieval_required,
            "compiler_fallback": bool(plan.fallback)}


#: P8b (§44–§47) synthesis-role presentation. Default OFF ⇒ the grounded prompt is byte-identical.
_SYNTH_ROLE_ORDER = {"DIRECT": 0, "PRECISION": 1, "RELATIONAL": 2, "LATENT": 3}
_SYNTH_ROLE_GUIDANCE = (
    "EVIDENCE ROLES — each [S#] is tagged by role: DIRECT answers the question; PRECISION gives the "
    "corpus's precise vocabulary/mechanism for it; RELATIONAL is a source-attested connection; LATENT "
    "extends with related knowledge the user may not have asked for. Lead with the DIRECT answer, then "
    "use PRECISION to sharpen it, RELATIONAL to connect, and LATENT to extend — never let LATENT or "
    "RELATIONAL substitute for a DIRECT answer.")


def _synth_roles_enabled() -> bool:
    return os.environ.get("POLYMATH_CHAT_SYNTH_ROLES", "").strip().lower() in ("1", "true", "yes", "on")


#: ELITE-MODE-RETRIEVAL-SYNTHESIS-V1 — orientation (profile/map) and derived (wildcard)
#: blocks. Absent keys ⇒ the grounded prompt is byte-identical to pre-slice C.
_ORIENTATION_MAX_DOCS = 3
_ORIENTATION_MAX_MAPS = 6
_DERIVED_MAX = 3
_RELATIONS_MAX = 20
_ORIENTATION_GUIDANCE = (
    "ORIENTATION is routing metadata compiled from the document profile and parent map. "
    "It is NOT a source quote. Do not cite it as [S#]. Use it only to know which book and "
    "section you are in before reading EVIDENCE.")
_DERIVED_GUIDANCE = (
    "DERIVED INSIGHTS come from the abstract/latent layer (enrichment abstraction, transfer, or profile atom). "
    "They are NOT book quotes. Cite them as [A#] and say they are derived. Each insight GROUNDS IN "
    "a proving [S#] when that child is in EVIDENCE. Never replace a missing DIRECT answer with [A#]. "
    "Lead with EVIDENCE; then use [A#] for analogical or cross-domain argument.")
_RELATIONS_GUIDANCE = (
    "RELATIONS are source-attested graph facts. Cite them as [G#]. "
    "A [G#] that names proves: [S#] is grounded in that child. "
    "Do not assert a [G#] that has no proving child. "
    "Use [G#] to structure how entities relate, then prove it with [S#].")


def _load_orientation(conn, doc_ids: list[str], parent_ids: list[str]) -> dict:
    """Postgres-backed orientation for the synthesizer: compiled profile ONE/SUMMARY
    (prefer doc-profile-v3.2 when both generations exist) plus active parent maps.
    Fail-open: a missing row is omitted, never invented."""
    docs: list[dict] = []
    maps: list[dict] = []
    ids = [d for d in dict.fromkeys(doc_ids or ()) if d][:_ORIENTATION_MAX_DOCS]
    pids = [p for p in dict.fromkeys(parent_ids or ()) if p][:_ORIENTATION_MAX_MAPS]
    if ids:
        rows = conn.execute(
            """SELECT DISTINCT ON (a.payload->'doc_profile'->>'doc_id')
                      a.payload->'doc_profile'->>'doc_id',
                      a.payload->'doc_profile'->>'prompt_version',
                      a.payload->'doc_profile'->'compiled',
                      d.source_name
                 FROM artifacts a
                 JOIN runs r ON r.run_id = a.run_id
                 JOIN documents d ON d.doc_id = (a.payload->'doc_profile'->>'doc_id')
                WHERE a.stage = 'doc_profile'
                  AND a.payload->'doc_profile'->>'doc_id' = ANY(%s)
                ORDER BY a.payload->'doc_profile'->>'doc_id',
                         (a.payload->'doc_profile'->>'prompt_version' = 'doc-profile-v3.2') DESC,
                         a.created_at DESC""",
            (ids,),
        ).fetchall()
        by_id = {str(r[0]): r for r in rows}
        for did in ids:
            r = by_id.get(did)
            if not r:
                continue
            compiled = r[2] or {}
            docs.append({
                "doc_id": did,
                "title": (r[3] or "").rsplit(".", 1)[0],
                "one": (compiled.get("one") or compiled.get("one_liner") or "")[:240],
                "summary": (compiled.get("summary") or "")[:400],
                "prompt_version": r[1],
            })
    if pids:
        for r in conn.execute(
            """SELECT parent_id, routing_signature, semantic_hooks
                 FROM document_parent_maps
                WHERE parent_id = ANY(%s) AND active
                ORDER BY parent_id""",
            (pids,),
        ).fetchall():
            hooks = r[2] if isinstance(r[2], list) else []
            maps.append({
                "parent_id": r[0],
                "signature": (r[1] or "")[:160],
                "hooks": [str(h) for h in hooks[:3]],
            })
    return {"docs": docs, "maps": maps}


def _render_orientation(orientation: dict | None) -> str:
    if not orientation:
        return ""
    docs = orientation.get("docs") or []
    maps = orientation.get("maps") or []
    if not docs and not maps:
        return ""
    lines = [_ORIENTATION_GUIDANCE, "", "ORIENTATION (not citable):"]
    for d in docs:
        title = (d.get("title") or d.get("doc_id") or "document").strip()
        lines.append(f"DOC: {title}")
        if d.get("one"):
            lines.append(f"ONE: {d['one']}")
        if d.get("summary"):
            lines.append(f"SUMMARY: {d['summary']}")
    for m in maps:
        hooks = "; ".join(m.get("hooks") or [])
        sig = (m.get("signature") or "").strip()
        if sig:
            extra = f" · hooks: {hooks}" if hooks else ""
            lines.append(f"MAP: {sig}{extra}")
    return "\n".join(lines)


def _render_derived(wildcard_lane, tag_by_chunk: dict[str, str]) -> tuple[str, int]:
    if not wildcard_lane:
        return "", 0
    blocks: list[str] = []
    for i, br in enumerate(list(wildcard_lane)[:_DERIVED_MAX], 1):
        if not isinstance(br, dict):
            continue
        principle = (br.get("principle") or "").strip()
        transfer = (br.get("why_it_may_transfer") or "").strip()
        ev = br.get("source_evidence") or {}
        cid = ev.get("chunk_id") or ""
        tag = tag_by_chunk.get(cid) if cid else None
        if not principle and not transfer:
            continue
        lines = [f"[A{i}] PRINCIPLE: {principle or '(unspecified)'}"]
        if transfer:
            lines.append(f"     TRANSFER: {transfer}")
        if tag:
            lines.append(f"     GROUNDS IN: [{tag}]")
        elif (ev.get("text") or "").strip():
            lines.append(f"     GROUNDS IN (attached child, not an [S#]): {(ev.get('text') or '')[:320]}")
        verified = br.get("verified")
        if verified is False:
            lines.append("     SUPPORT: unverified")
        blocks.append("\n".join(lines))
    if not blocks:
        return "", 0
    return _DERIVED_GUIDANCE + "\n\nDERIVED INSIGHTS (not source quotes):\n" + "\n\n".join(blocks), len(blocks)


def _proving_tag(fact: dict, tag_by_chunk: dict[str, str], bundle: dict | None) -> str | None:
    cid = str(fact.get("chunk_id") or "")
    if cid and cid in tag_by_chunk:
        return tag_by_chunk[cid]
    fid = fact.get("fact_id")
    if not fid or not isinstance(bundle, dict):
        return None
    for item in bundle.get("evidence_bundle") or []:
        if item.get("kind") != "claim" or item.get("fact_id") != fid:
            continue
        span = item.get("source_span") or {}
        pcid = str(span.get("chunk_id") or "")
        if pcid and pcid in tag_by_chunk:
            return tag_by_chunk[pcid]
    return None


def _render_relations(graph_facts: list, tag_by_chunk: dict[str, str],
                      bundle: dict | None = None) -> tuple[str, int]:
    if not graph_facts:
        return "", 0
    blocks: list[str] = []
    n = 0
    for f in list(graph_facts)[:_RELATIONS_MAX]:
        if not isinstance(f, dict):
            continue
        sub, pred, obj = f.get("subject"), f.get("predicate"), f.get("object")
        if not (sub and pred and obj):
            continue
        n += 1
        lines = [f"[G{n}] {sub} —{pred}→ {obj}"]
        prove = _proving_tag(f, tag_by_chunk, bundle)
        if prove:
            lines.append(f"     proves: [{prove}]")
        else:
            lines.append("     proves: none — do not treat as source-backed this turn")
        blocks.append("\n".join(lines))
    if not blocks:
        return "", 0
    return _RELATIONS_GUIDANCE + "\n\nRELATIONS (attested, not evidence rows):\n" + "\n".join(blocks), n


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
    _roles = bundle.get("evidence_roles") or {}
    _role_present = bool(_synth_roles_enabled() and _roles)
    _entries = list(_evidence_legend(bundle))
    if _role_present:
        # P8b: PRESENT evidence grouped by role — DIRECT first, then PRECISION / RELATIONAL / LATENT.
        # A STABLE sort by role only (ties keep tag order); the [S#] tag→locator mapping is unchanged,
        # so citations are unaffected — only the presentation order + a per-tag role label change.
        _entries.sort(key=lambda e: _SYNTH_ROLE_ORDER.get(_roles.get(e.get("chunk_id")), 0))
    for e in _entries:
        crumb = e.get("breadcrumb") or ""
        _role = _roles.get(e.get("chunk_id")) if _role_present else None
        _lbl = f" ({_role})" if _role else ""
        # EVIDENCE-DIET-V1: the passage header names its book › section; the legend maps the tag to that
        # breadcrumb (the raw locator stays on the answer event and the receipt for the UI and traces)
        ev_lines.append(f"[{e['tag']}]{_lbl} {crumb}\n{e['text']}" if crumb else f"[{e['tag']}]{_lbl}\n{e['text']}")
        legend.append(f"[{e['tag']}] = {crumb or e['locator']}")
    carried = [
        f"[{c.locator}]\n{c.preview}" for c in (carry_context or [])[:30]
        if c.preview
    ]
    context_block = ""
    if ev_lines:
        if _role_present:
            context_block += (_SYNTH_ROLE_GUIDANCE + "\n\n")
        context_block += ("EVIDENCE (this turn):\n" + "\n---\n".join(ev_lines))
        context_block += ("\n\nSOURCE TAGS:\n" + "\n".join(legend))
    if carried:
        context_block += ("\n\nEVIDENCE (carried from earlier turns):\n"
                          + "\n---\n".join(carried))
    if not context_block:
        context_block = "EVIDENCE: none retrieved for this turn" + (
            " (by design: this request is answered from the conversation and the user's own text)."
            if plan is not None and not plan.retrieval_required else ".")
    orient = _render_orientation(bundle.get("orientation") if isinstance(bundle, dict) else None)
    tag_by_chunk = {str(e.get("chunk_id")): e["tag"] for e in _entries if e.get("chunk_id") and e.get("tag")}
    derived, _ = _render_derived(
        (bundle.get("derived_insights") if isinstance(bundle, dict) else None), tag_by_chunk)
    relations, _ = _render_relations(graph_facts, tag_by_chunk, bundle if isinstance(bundle, dict) else None)
    # ELITE-MODE D/F: ORIENTATION → EVIDENCE (DIRECT) → RELATIONS [G#] → DERIVED [A#].
    context_block = "\n\n".join(p for p in (orient, context_block, relations, derived) if p)
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
#: CARRY-ARTIFACT-V1: a transform / continue turn keeps up to this many of the previous answer's cited passages
_CARRY_ARTIFACT_CAP = int(os.environ.get("POLYMATH_CARRY_ARTIFACT_CAP", "16"))
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
    # GENERATION-BOUND-V1 (measured 2026-09-06): LiteLLM sends Anthropic-format
    # providers DEFAULT_MAX_TOKENS = 4096 when no bound is given; deepseek-v4-flash
    # (Alibaba Model Studio) spends most of that on reasoning, so long artifacts
    # ended mid-sentence with no error and no receipt (a 66-char "answer" once,
    # a 5,773-char one cut at "which is what separates" another time; 1 of 10
    # baseline answers cut). The chat path now sends its own bound, records the
    # provider's finish_reason, and retries ONCE without the bound when a
    # provider rejects the number — every branch is receipted, never silent.
    bound = _chat_max_tokens()
    kwargs = dict(model=model, messages=messages, stream=True, timeout=300,
                  **_litellm_credentials(model))
    # REASONING-BOUNDARY-V1: overlay the CHAT_SYNTHESIS reasoning policy (LOW). No-op unless
    # POLYMATH_REASONING_POLICY=1; output budget stays with the max_tokens bound below (separate).
    try:
        from polymath_shared.reasoning_policy import CHAT_SYNTHESIS as _RB_CS, apply_litellm as _RB_apply
        _rb_applied = _RB_apply(kwargs, _RB_CS, model)
        if _rb_applied:
            import json as _RB_js
            import logging as _RB_lg
            _RB_lg.getLogger("polymath.reasoning").info("reasoning_policy %s", _RB_js.dumps(_rb_applied))
    except Exception:  # noqa: BLE001 — the reasoning overlay is additive; never break synthesis
        pass
    finish = None
    bound_sent = bool(bound)
    # PROVIDER-ATTEMPT-LEDGER-V4: answer synthesis is an EXTERNAL MODEL ATTEMPT on a paid
    # provider, and it recorded nothing — §15's ledger covered extraction and the query
    # compiler only. The loop below can make TWO attempts (bound refused, then retried
    # without it) and the first one survived merely as a `degraded` SSE event, which is
    # per-call evidence in a stream the user closes. `limiter_bypassed=True`: this path
    # has no lane limiter at all, a state the ledger could not express before 0059.
    from polymath_shared.conformance.attempts import (Attempt as _At, attempt_context as _actx,
                                                      record as _rec)
    _lane = f"chat_synth:{model.split('/')[0]}" if "/" in model else "chat_synth"
    _abase = dict(lane=_lane, model=model, provider=(model.split("/")[0] if "/" in model
                                                     else None),
                  limiter_admitted=False, limiter_bypassed=True, http_dispatched=True)
    # One correlation id for the whole retry loop, captured WITHOUT holding a context
    # open across the stream's yields (see _AttemptOutcome for what that cost).
    from polymath_shared.conformance.attempts import current_context as _curctx
    _corr = _curctx().get("correlation_id") or uuid.uuid4().hex[:24]

    def _rec_attempt(**kw):
        with _actx(function="CHAT", stage="answer_synthesis", correlation_id=_corr):
            _rec(_At(**kw, **_abase))

    for attempt, with_bound in enumerate([True, False] if bound else [False]):
        started = False
        _t0 = time.perf_counter()
        _digest, _chars = hashlib.sha256(), 0
        try:
            stream = litellm.completion(**kwargs, **({"max_tokens": bound} if with_bound else {}))
            for chunk in stream:
                started = True
                piece = ""
                rpiece = ""
                try:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    piece = delta.content or ""
                    # REASONING-STREAM-V1: providers that expose model
                    # thinking surface it as reasoning_content.
                    rpiece = getattr(delta, "reasoning_content", None) or ""
                    if getattr(choice, "finish_reason", None):
                        finish = str(choice.finish_reason)
                except Exception:
                    piece = ""
                if rpiece:
                    yield {"reasoning": rpiece}
                if piece:
                    _digest.update(piece.encode("utf-8", "replace"))
                    _chars += len(piece)
                    yield {"token": piece}
            _rec_attempt(success=True, http_status=200,
                         response_hash=(_digest.hexdigest()[:32] if _chars else None),
                         latency_ms=int((time.perf_counter() - _t0) * 1000))
            break
        except Exception as exc:
            _rec_attempt(success=False, error_class=type(exc).__name__,
                         latency_ms=int((time.perf_counter() - _t0) * 1000))
            if with_bound and not started and _bound_rejected(exc):
                bound_sent = False
                yield {"degraded": {"component": "generation", "state": "bound refused",
                                    "reason": f"max_tokens_rejected:{bound}",
                                    "effect": f"the provider refused max_tokens={bound}; generated once more without a bound",
                                    "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}}
                continue
            yield {"error": True, "error_code": "litellm_error",
                   "message": f"{type(exc).__name__}: {str(exc)[:280]}"}
            return
    yield {"finish": {"finish_reason": finish, "max_tokens": bound if bound_sent else None}}


def _chat_max_tokens() -> int:
    """GENERATION-BOUND-V1: the output bound the chat path sends to LiteLLM
    providers (POLYMATH_CHAT_MAX_TOKENS; 0 = send none and accept LiteLLM's
    provider default, 4096 for Anthropic-format APIs). Default 16000 → 6000 on
    2026-09-07 (owner: "it generates too much and too long"; a 179 s / ~3,500-word
    CREATE answer): the ceiling backs the contract's length rule, it is not the
    lever — 6000 still holds any artifact the contract allows."""
    try:
        return max(0, int(os.environ.get("POLYMATH_CHAT_MAX_TOKENS", "6000")))
    except ValueError:
        return 6000


def _bound_rejected(exc: BaseException) -> bool:
    """A provider refusing the number itself (e.g. 'max_tokens: 16000 > 8192
    maximum') — retry without it; any other error is the provider's answer."""
    text = str(exc).lower()
    return "max_tokens" in text or "max_completion_tokens" in text or "max output tokens" in text


class _AttemptOutcome:
    """One provider attempt whose outcome is only known at one of several exits.

    A streaming generator can end at `done`, at an error chunk, at a non-200, or at an
    exception, and recording at each exit duplicates the row or misses one. This records
    exactly once, in `__exit__`, from whatever the last marker said — so the ledger keeps
    one row per DISPATCH, which is what `attempt_ordinal` is counting."""

    def __init__(self, url: str, model: str):
        from urllib.parse import urlparse
        self._base = dict(lane="chat_synth:ollama", model=model,
                          provider=urlparse(url).netloc or None,
                          limiter_admitted=False, limiter_bypassed=True,
                          http_dispatched=True)
        self._status = None
        self._ok = False
        self._error = None
        self._t0 = time.perf_counter()
        self._corr = None
        # §15's response_hash, accumulated as the stream arrives so nothing is buffered.
        # Two attempts returning the SAME body — a stuck model, a cached edge, an error
        # page served with HTTP 200 — are invisible in status codes and obvious here.
        self._digest = hashlib.sha256()
        self._chars = 0

    def status(self, code): self._status = code
    def ok(self): self._ok = True
    def failed(self, error_class): self._error = error_class

    def chunk(self, piece: str):
        """Feed one streamed piece into the digest (never stored, only hashed)."""
        if piece:
            self._digest.update(piece.encode("utf-8", "replace"))
            self._chars += len(piece)

    def __enter__(self):
        # CAPTURE the ambient correlation id; do NOT hold a context open across the
        # stream's yields. A contextvar token is only valid in the Context that made it,
        # and Starlette resumes a sync streaming generator in another one — holding the
        # context open raised "Token was created in a different Context" on exit, which
        # surfaced as a stream error on every chat answer.
        from polymath_shared.conformance.attempts import current_context
        self._corr = current_context().get("correlation_id") or uuid.uuid4().hex[:24]
        return self

    def __exit__(self, *exc):
        from polymath_shared.conformance.attempts import Attempt, attempt_context, record
        err = self._error or (f"HTTP_{self._status}"
                              if (self._status and self._status >= 400) else
                              (None if self._ok else "INCOMPLETE_STREAM"))
        # the context wraps the WRITE only — no yield can happen inside it
        with attempt_context(function="CHAT", stage="answer_synthesis",
                             correlation_id=self._corr):
            record(Attempt(success=self._ok and err is None, http_status=self._status,
                           error_class=err,
                           response_hash=(self._digest.hexdigest()[:32]
                                          if self._chars else None),
                           latency_ms=int((time.perf_counter() - self._t0) * 1000),
                           **self._base))
        return False


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

    # PROVIDER-ATTEMPT-LEDGER-V4: the daemon is local, but the MODEL need not be —
    # `gemma4:31b-cloud` is in the default catalog and routes through this same daemon to
    # a cloud service. Excluding this seam as "local" would be true of the hop and false
    # of the spend, so it records like any other. One row per dispatch, written in a
    # `finally` because the stream has several exits (done, error chunk, non-200, retry).
    _out = _AttemptOutcome(f"{OLLAMA_URL}", model)
    with _out:
        yield from _ollama_generate_inner(_out, model, messages)


def _ollama_generate_inner(_out, model: str, messages: list[dict]):
    import httpx

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
            _out.status(r.status_code)
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
                    _out.failed("OLLAMA_ERROR_CHUNK")
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
                    _out.chunk(piece)
                    yield {"token": piece}
                if chunk.get("done"):
                    _out.ok()
                    return
    except Exception as exc:
        _out.failed(type(exc).__name__)
        yield {"error": True, "error_code": "ollama_unavailable",
               "message": f"{type(exc).__name__}: {exc}"[:300]}


def _ollama_stream_plain(model: str, messages: list[dict]):
    """Fallback stream without `think` for models that reject it.

    Its own dispatch, so its own ledger row: the caller already recorded the attempt that
    was refused for `think`, and a retry that also fails must not hide behind it."""
    _out = _AttemptOutcome(f"{OLLAMA_URL}", model)
    with _out:
        yield from _ollama_stream_plain_inner(_out, model, messages)


def _ollama_stream_plain_inner(_out, model: str, messages: list[dict]):
    import httpx

    try:
        with httpx.stream(
                "POST", f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
                timeout=httpx.Timeout(300, connect=10)) as r:
            _out.status(r.status_code)
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
                    _out.failed("OLLAMA_ERROR_CHUNK")
                    yield {"error": True, "error_code": "ollama_error",
                           "message": str(chunk["error"])[:300]}
                    return
                piece = (chunk.get("message") or {}).get("content", "")
                if piece:
                    _out.chunk(piece)
                    yield {"token": piece}
                if chunk.get("done"):
                    _out.ok()
                    return
    except Exception as exc:
        _out.failed(type(exc).__name__)
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
    synth = req.synthesizer or _default_synthesizer()   # never a hidden provider (see _default_synthesizer)
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
            _firing: dict = {}

            def _stamp_firing() -> dict:
                # CORPUS-EXPLORE-FIRING-V1: the turn's ONE firing receipt (exactly one cause per miss),
                # recorded once to the JSONL rate ledger. Observation only; never breaks a turn.
                try:
                    from polymath_shared.corpus_explore_firing import record as _ce_record
                    rec = _turn_firing_receipt(_plan, requested=bool(getattr(req, "corpus_explorer", False)),
                                               compiler_flag=_flag, retrieval_skipped=_skip_retrieval)
                    if not _firing:
                        _ce_record(rec, q0=query)
                    _firing.clear()
                    _firing.update(rec)
                except Exception:  # noqa: BLE001
                    pass
                return _firing

            if _flag != "off":
                from concurrent.futures import ThreadPoolExecutor
                _session_key = (req.workspace or req.corpus_id or query[:64])
                _corpora = list(scope.corpus_ids)
                # SHADOW runs beside retrieval (no added latency, receipt
                # only); ON (P0.c) is the serial stage 0 the plan describes.
                _plan_future = ThreadPoolExecutor(max_workers=1).submit(
                    _compile_chat_plan, query, req.history, _corpora, session_key=_session_key,
                    titles_rank=getattr(req, "titles_rank", None),
                    corpus_explorer=bool(getattr(req, "corpus_explorer", False)))
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
                    _stamp_firing()
                    yield _phase("compile", "Query compiled" if not _plan.fallback else "Query compiler fell back",
                                 task_type=_plan.task_type, retrieval_required=_plan.retrieval_required,
                                 queries=len(_plan.queries), fallback=_plan.fallback,
                                 mode=_flag, wall_ms=_plan.compiler.get("wall_ms"),
                                 scout=(_plan.compiler.get("scout") or {}).get("n_injected"),
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
                    _stamp_firing()
                elif not _firing:
                    _stamp_firing()

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
            orientation: dict = {"docs": [], "maps": []}
            _arrivals: dict = {}
            _aspects: dict = {}
            _weak: list = []
            _resolution: dict | None = None   # P10 evidence-resolution receipt (bounded round 2)
            _constraint_align: dict | None = None   # CA3 constraint-alignment receipt (post-rerank partition)
            _grades_by_chunk: dict = {}              # CA4 per-chunk support_role (DIRECT/PARTIAL/RELATED)
            _epistemic: dict | None = None           # CA4 query epistemic state (drives the answerability gate)
            _latent_receipt: dict | None = None      # WLK2C C6 latent-selection calibration receipt
            # CHAT-RETRIEVAL-V2 / P1.e MODE-COMPOSITION-V1: every mode is a composition on the v2 engine
            # (VECTOR = A+B, HYBRID = A+B+C, GRAPH = HYBRID → bounded G, WILDCARD = HYBRID ∥ W) owned by
            # chat_retrieve_mode; the v1 engines stay behind `retrieval: v1` or `latent` (rollback boundary).
            from orchestrator.api.chat_retrieval import chat_retrieval_flag
            _rflag = chat_retrieval_flag(getattr(req, "retrieval", None))
            # `latent` / `utility` are v1 plan knobs: either keeps the turn on the v1 engines (as /chat always did)
            # B12 LATENT-COMPOSITION-V1: ✨ (`req.latent`) no longer drops the turn to the v1 engine — it enables lane D
            # inside the v2 composition (see the budget below); `utility` remains a v1 knob.
            _v2_mode = _rflag in ("v2", "v2-single") and not req.utility
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
                     "subject": f["subject"], "object": f["object"],
                     "chunk_id": f.get("chunk_id")}
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
                    from orchestrator.api.chat_retrieval import default_budget as _default_budget, intent_policy_enabled as _ip_on
                    from polymath_shared.query_intent import apply_intent_policy as _apply_intent, policy_for as _policy_for
                    from dataclasses import replace as _replace
                    # FINAL-PLAN P2b: intent→budget policy (default off, byte-identical when off);
                    # the explicit ✨ (req.latent) always wins the latent toggle.
                    _ip = bool(_ip_on() and _plan is not None and getattr(_plan, "intent", ""))
                    _budget = _apply_intent(_plan.intent, _default_budget()) if _ip else _default_budget()
                    if req.latent:
                        _budget = _replace(_budget, latent_enabled=True)                       # B12: ✨ = lane D
                    _latent_kw = {"budget": _budget} if (req.latent or _ip) else {}
                    # FINAL-PLAN P6 (§37/§38): intent-conditioned graph ASSIST on a HYBRID turn
                    # (RELATIONSHIP → graph=auto), default off; never changes the public mode (§2).
                    _pol = _policy_for(_plan.intent) if _ip else None
                    _graph_assist = _pol.graph if _pol is not None else "off"
                    fast = chat_retrieve_mode(
                        "VECTOR" if ui_mode == "FAST" else ui_mode, _retrieval_text, corpus_id,
                        graph_useful=_graph_useful, graph_assist=_graph_assist, **_latent_kw,
                        exact_terms=tuple(_plan.exact_terms) if (_flag == "on" and _plan is not None) else (),
                        # P1.b: typed subqueries run lanes B + C on their own vectors (v2-single = A/B without them)
                        # LATENT-QUERY-FUSION-V2 F4: carry the plan's EXISTING per-query origin provenance
                        # (USER/PROFILE/GRAPH/BRIDGE/WILDCARD) so V2 fusion weights each lane by lineage class.
                        subqueries=tuple((q.id, q.type, q.query, q.weight, getattr(q, "origin", "")) for q in _plan.queries if q.type != "PRIMARY")
                        if (_flag == "on" and _plan is not None and _rflag == "v2") else (),
                        # WLK2C: the BRIDGE subquery ids, so chat_retrieve_v2 exposes their candidates in the
                        # latent pool regardless of fused rank (bridge candidates rarely top the q0-dominated union).
                        latent_bridge_ids=tuple(q.id for q in _plan.queries if getattr(q, "origin", "") in LATENT_ORIGINS)
                        if (_flag == "on" and _plan is not None) else ())
                    _aspects = (fast.get("meta") or {}).get("aspects") or {}
                    _weak = (fast.get("meta") or {}).get("weak_aspects") or []
                    if ui_mode == "WILDCARD":
                        wildcard_lane = fast.get("wildcard") or []
                    if ui_mode == "GRAPH" or fast.get("graph_relationships"):   # P6: surface graph-assist facts too
                        graph_facts = [
                            {"fact_id": f["fact_id"], "predicate": f["predicate"],
                             "subject": f["subject"], "object": f["object"],
                             "chunk_id": f.get("chunk_id")}
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
                # P10 EVIDENCE-RESOLUTION: a bounded round 2 for a still-unsupported need, merged
                # into fast["evidence"] BEFORE the bundle is built so synthesis uses it. Flag-gated,
                # fail-open, at most one round (uses the same engine; never a second RAG pipeline).
                try:
                    if (os.environ.get("POLYMATH_CHAT_RESOLUTION", "0") == "1"
                            and _plan is not None and ui_mode in ("FAST", "HYBRID") and _aspects):
                        def _resolve_retrieve(_q: str):
                            return chat_retrieve_mode("VECTOR" if ui_mode == "FAST" else ui_mode, _q, corpus_id)
                        _resolution = _maybe_resolve(_plan, fast, _aspects, _weak, _resolve_retrieve)
                except Exception:  # noqa: BLE001 — resolution is additive; never break the turn
                    _resolution = None
                # WLK2C C4-live/C5-live: the additive latent second pass (flag-gated, fail-open). Runs
                # BEFORE CA3/CA4 so they grade + gate the latent-aware evidence; reassigns fast["evidence"].
                _latent_receipt = _apply_latent_selection(fast, _plan, _retrieval_text)
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
                    doc_ids = [d["doc_id"] for d in (fast.get("selected_documents") or []) if d.get("doc_id")]
                    if not doc_ids:
                        doc_ids = [c.get("doc_id") for c in (fast.get("evidence") or []) if c.get("doc_id")]
                    try:
                        orientation = _load_orientation(conn, doc_ids, parent_ids)
                    except Exception:  # noqa: BLE001 — orientation is additive; never break the turn
                        orientation = {"docs": [], "maps": []}
                section_summaries = [
                    {"chunk_id": r[0], "doc_id": r[1], "summary": r[2] or ""}
                    for r in rows
                ]

            # CONSTRAINT-AWARE-RETRIEVAL-V1 CA3: post-rerank portfolio partition. The cross-encoder
            # stays the semantic authority; when q0 carries a RESOLVED explicit constraint, reorder
            # the (already reranked) evidence so constraint-satisfying evidence leads per strength —
            # semantic order preserved WITHIN each portfolio, no score added/tuned. Flag-gated,
            # default-off ⇒ byte-identical; only reorders when a resolved constraint is present.
            if (os.environ.get("POLYMATH_CHAT_CONSTRAINT_ALIGN", "0") == "1"
                    and _plan is not None and evidence_rows
                    and any(getattr(c, "resolved_targets", None) for c in (getattr(_plan, "explicit_constraints", None) or []))):
                from polymath_shared.query_constraints import align_evidence_for_constraints
                _before = [c["doc_id"] for c in evidence_rows]
                evidence_rows = align_evidence_for_constraints(evidence_rows, _plan.explicit_constraints)
                _after = [c["doc_id"] for c in evidence_rows]
                _gov = next((c for s in ("HARD", "SOFT", "EXPLORATORY")
                             for c in _plan.explicit_constraints
                             if c.kind == "SOURCE" and c.resolved_targets and c.strength == s), None)
                _constraint_align = {"applied": _before != _after,
                                     "strength": getattr(_gov, "strength", None),
                                     "targets": getattr(_gov, "resolved_targets", []),
                                     "value": getattr(_gov, "value", None)}

            # CONSTRAINT-AWARE-RETRIEVAL-V1 CA4: deterministic evidence-role grading (DIRECT/PARTIAL/
            # RELATED) + a query epistemic state, from the reranked evidence + the plan's needs and
            # resolved constraints. Flag-gated; the epistemic state rides the bundle so the synthesis
            # answerability gate requires ≥1 DIRECT/PARTIAL chunk (else it states the gap, not a
            # fabricated claim). Default-off ⇒ no grades, byte-identical.
            if (os.environ.get("POLYMATH_CHAT_EVIDENCE_ROLES", "0") == "1"
                    and _plan is not None and (fast.get("evidence"))):
                from polymath_shared.query_constraints import grade_evidence
                _grades_by_chunk, _epistemic = grade_evidence(fast.get("evidence") or [], _plan)

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
            # P8b (§44–§47): the retrieval evidence-role per chunk (DIRECT/PRECISION/RELATIONAL/LATENT)
            # rides the bundle for role-aware synthesis presentation (POLYMATH_CHAT_SYNTH_ROLES);
            # default-off ⇒ the grounded prompt is byte-identical. assemble_evidence_bundle is untouched.
            bundle["evidence_roles"] = {c.get("chunk_id"): c.get("role") for c in evidence_rows
                                        if c.get("chunk_id") and c.get("role")}
            # CA4: per-chunk support grades + the epistemic verdict ride the bundle. `epistemic`
            # drives render_answer's multi-signal answerability gate (grounded in ≥1 DIRECT/PARTIAL).
            if _epistemic is not None:
                bundle["support_roles"] = _grades_by_chunk
                bundle["epistemic"] = _epistemic
            bundle["orientation"] = orientation
            bundle["derived_insights"] = list(wildcard_lane or [])
            # CARRY-V2: admitted carried evidence joins the bundle (tags, legend, used_evidence)
            _carry_meta: dict = {"in": len(req.carry_context), "admitted": 0}
            if req.carry_context:
                _cands, _cacct = _carry_candidates(req.carry_context, {c.get("chunk_id") for c in evidence_rows})
                if _skip_retrieval:
                    # CARRY-ARTIFACT-V1 (owner 2026-09-07: "did you use the corpus?" after a rewrite turn came back
                    # ungrounded): a transform / continue turn does not search, but it works ON the previous answer,
                    # so the evidence that answer cited stays in the bundle — no relevance gate (a passage's score
                    # against "put the prompt in XML" is meaningless), no reranker call, newest first, capped.
                    _citems, _aacct = _admit_carry(
                        _cands, query, scorer=lambda _q, texts: [1.0] * len(texts), floor=0.0, cap=_CARRY_ARTIFACT_CAP)
                    _aacct["mode"] = "artifact"
                else:
                    _citems, _aacct = _admit_carry(
                        _cands, (_plan.resolved_request if (_flag == "on" and _plan is not None and _plan.resolved_request) else query))
                    _aacct["mode"] = "judged"
                _carry_meta = {**_cacct, **_aacct}
                if _citems:
                    bundle.setdefault("evidence_bundle", []).extend(_citems)
                yield _phase("carry", (f"Carried evidence: {_aacct['admitted']} of {len(req.carry_context)} kept for the rewrite"
                                       if _skip_retrieval else f"Carried evidence: {_aacct['admitted']} of {len(req.carry_context)} admitted"),
                             **{k: v for k, v in _carry_meta.items() if k not in ("scores", "admitted_ids")})
            _mark("carry")
            _legend = _evidence_legend(bundle)
            _tag_by_chunk = {str(e.get("chunk_id")): e["tag"] for e in _legend if e.get("chunk_id") and e.get("tag")}
            _, _derived_n = _render_derived(wildcard_lane, _tag_by_chunk)
            _, _relations_n = _render_relations(graph_facts, _tag_by_chunk, bundle)
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
                "orientation_docs": len((orientation or {}).get("docs") or []),
                "maps_in_prompt": len((orientation or {}).get("maps") or []),
                "derived_in_prompt": _derived_n,
                "relations_in_prompt": _relations_n,
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
                # CONSTRAINT-AWARE-RETRIEVAL-V1 CA2: explicit SOURCE constraints detected in q0 +
                # their deterministically resolved corpus doc_ids. RECEIPT ONLY — no ranking effect
                # until CA3. Empty for the common (unconstrained) query.
                "explicit_constraints": [
                    {"kind": c.kind, "value": c.value, "strength": c.strength,
                     "resolved_targets": c.resolved_targets, "confidence": c.confidence,
                     "reason": c.reason}
                    for c in (getattr(_plan, "explicit_constraints", None) or [])] if _plan else [],
                # CA3: whether the post-rerank portfolio partition reordered the evidence (flag-gated).
                "constraint_alignment": _constraint_align,
                # CA4: query epistemic state (DIRECT/PARTIAL/RELATED counts + whether the corpus
                # directly establishes the need). None when the grading flag is off.
                "epistemic": _epistemic,
                "latent_selection": _latent_receipt,     # WLK2C C6: bridge/eligibility/seat calibration (incl. rejects)
                # P11 profile_expansion_evidence_yield: of the PROFILE-origin subqueries, how many
                # surfaced FINAL evidence (aspect final > 0). None unless profile-expansion is on.
                "profile_yield": _compute_profile_yield(_plan, _aspects),
                "resolution": _resolution,   # P10: bounded round-2 receipt (hop_2_fired, reason, round2)
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

            if getattr(req, "evidence_only", False):
                # REASONING-BOUNDARY-V1: the evidence boundary. The full pipeline (compiler -> Corpus
                # Explore -> retrieval -> C4/C5 -> CA4) has run; emit the validated EvidencePacket and
                # STOP. NO synthesis LLM, NO reviewer — this is evidence, not an answer. External agents
                # (Claude Code/Hermes) do their OWN final reasoning over it (no nested Polymath synthesis).
                from polymath_shared.evidence_packet import build_evidence_packet
                if _plan_receipt:
                    retrieval["chat_plan"] = _plan_receipt
                if getattr(req, "corpus_explorer", False):
                    retrieval["corpus_explore_firing"] = dict(_firing or _stamp_firing())
                _comp = (getattr(_plan, "compiler", None) or {}) if _plan is not None else {}
                _ce = _comp.get("corpus_explore_expansion") or {}
                # RB5 — TEXT IS EVIDENCE, NOT A PREVIEW. The inventory rows carry a 240-char UI preview of each chunk.
                # Resolve the retrieved chunk for EXACTLY the rows the packet will present (same rows, same order) so
                # the packet can carry a bounded verbatim excerpt. Presentation only: nothing here selects, ranks,
                # grades or seats anything, and a resolver miss falls back to the preview (the packet then says so).
                from polymath_shared.evidence_packet import DEFAULT_MAX_ROWS as _PK_ROWS
                _full_texts: dict = {}
                for _prow in (fast.get("evidence") or [])[:_PK_ROWS]:
                    _pcid = _prow.get("chunk_id")
                    if not _pcid or _pcid in _full_texts:
                        continue
                    try:
                        _pch = _resolve_chunk(_pcid)
                    except Exception:  # noqa: BLE001 — text hydration can never fail an evidence turn
                        _pch = None
                    if _pch and _pch.get("text"):
                        _full_texts[_pcid] = _pch["text"]
                _packet = build_evidence_packet(
                    q0=req.message,
                    retrieval_mode=retrieval.get("mode") or ui_mode,
                    plan_queries=(list(_plan.queries) if _plan is not None else []),
                    evidence_rows=(fast.get("evidence") or []),
                    ca4_grades=_grades_by_chunk,
                    full_texts=_full_texts,
                    receipts={"activation": _comp.get("corpus_activation"),
                              "bridges": _comp.get("bridge_expansion"),
                              "corpus_explore": _ce,
                              "fusion": (fast.get("trace") or {}).get("ranked_lanes"),
                              "firing": (_firing or _stamp_firing())},
                    corpus_explorer_requested=bool(getattr(req, "corpus_explorer", False)),
                    corpus_explorer_used=bool((_ce or {}).get("added")),
                ).to_dict()
                _phase_ms["total"] = round((time.perf_counter() - t0) * 1000, 1)
                yield _sse("answer", {
                    "kind": "evidence",
                    "result": {"evidence_packet": _packet, "synthesis_performed": False},
                    "retrieval": retrieval,
                    "latency_ms": _phase_ms["total"],
                })
                yield _sse("done", {})
                _receipt(wall_ms=_phase_ms["total"], ui_mode=retrieval.get("mode") or ui_mode,
                         answer=None,
                         meta={"verdict": "evidence_only", "evidence_only": True,
                               "n_evidence": len(_packet.get("evidence") or []),
                               "phase_ms": dict(_phase_ms), "chat_plan": _plan_receipt or None})
                return

            if llm_model is not None:
                yield _phase("generate",
                             f"Generating with {llm_model}…",
                             model=llm_model,
                             carried=_carry_meta.get("admitted", 0))
                full: list[str] = []
                _prompt_meta: dict = {}
                _gen_meta: dict = {}
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
                    if tok.get("degraded"):
                        # GENERATION-BOUND-V1: a provider refused the bound → retried without it (receipted)
                        retrieval.setdefault("degraded", []).append(dict(tok["degraded"]))
                        continue
                    if "finish" in tok:
                        _gen_meta = dict(tok["finish"] or {})
                        if _gen_meta.get("finish_reason") == "length":
                            # the provider stopped at its output bound: the answer is CUT — say so on
                            # the answer event, the /chat JSON and the query receipt (never silent)
                            retrieval.setdefault("degraded", []).append(
                                {"component": "generation", "state": "cut", "reason": "truncated:max_tokens",
                                 "effect": f"the answer stopped at the provider's output bound ({_gen_meta.get('max_tokens') or 'provider default'} tokens); it is incomplete",
                                 "detail": f"finish_reason=length at max_tokens={_gen_meta.get('max_tokens')}"})
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
                                        "breadcrumb": e.get("breadcrumb") or "",          # EVIDENCE-DIET-V1: book › section
                                        "carried": bool(e.get("carried")), "carry_score": e.get("carry_score")}
                                       for e in _legend]
                retrieval["funnel"] = {"version": funnel["version"], "counts": funnel["counts"],
                                       "lane_counts": funnel["lane_counts"], "multi_lane": funnel["multi_lane"]}
                if getattr(req, "corpus_explorer", False):
                    retrieval["corpus_explore_firing"] = dict(_firing or _stamp_firing())
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
                            "generation": _gen_meta or None,
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
                          "generation": _gen_meta or None, "composition": retrieval.get("composition")})
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
                                    "breadcrumb": e.get("breadcrumb") or "",
                                    "carried": bool(e.get("carried")), "carry_score": e.get("carry_score")} for e in _legend]
            retrieval["funnel"] = {"version": funnel["version"], "counts": funnel["counts"],
                                   "lane_counts": funnel["lane_counts"], "multi_lane": funnel["multi_lane"]}
            if getattr(req, "corpus_explorer", False):
                retrieval["corpus_explore_firing"] = dict(_firing or _stamp_firing())
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
