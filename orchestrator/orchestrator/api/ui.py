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


@router.get("/documents")
def documents(corpus_id: str) -> dict:
    with tx() as conn:
        row = conn.execute("SELECT 1 FROM corpora WHERE corpus_id=%s",
                           (corpus_id,)).fetchone()
        if not row:
            raise HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN",
                                      "message": f"corpus {corpus_id!r} not found"})
        rows = conn.execute(
            """
            SELECT d.doc_id, d.source_name, d.media_type, d.byte_length,
                   d.created_at,
                   COUNT(c.chunk_id) FILTER (WHERE c.tier='child') AS children
              FROM documents d
              LEFT JOIN chunks c ON c.doc_id = d.doc_id
             WHERE d.corpus_id = %s
             GROUP BY d.doc_id, d.source_name, d.media_type, d.byte_length,
                      d.created_at
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
             "bytes": r[3], "created_at": str(r[4]), "chunks": r[5]}
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


@router.delete("/corpora/{corpus_id}")
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
earlier turns of this session). The user is STUDYING this material — \
teach it, never inventory it.

Grounding rules (non-negotiable; they override anything below):
- Everything you assert must come from the provided evidence. Cite by \
appending [locator] at the END of the sentence or paragraph a claim \
comes from — never interrupt a sentence with a citation, never open \
with boilerplate like "Based on the evidence in your corpus".
- If the user asks you to BUILD something (a quiz, a PBQ-style HTML \
test, flashcards, a study plan, code), build it fully, drawing the \
substance from the evidence. Emit complete artifacts (e.g., a full \
self-contained HTML document in an ```html code block).
- If the evidence does not contain what the user needs, say exactly \
what is missing instead of inventing facts.
- When the material has an exam angle (objectives, question formats, \
common traps), end with a brief "for the exam" note drawn from the \
evidence.
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


def _llm_system_prompt() -> str:
    """Grounding core + the v3.3 style layer + date context (the v3.3
    freshness block minus its live-web lines — v4 has no web lane)."""
    from datetime import datetime

    from orchestrator.api.polymath_style import POLYMATH_STYLE_PROMPT

    current = datetime.now().astimezone()
    return (
        f"{_LLM_GROUNDING}\n\n{POLYMATH_STYLE_PROMPT}\n\n"
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
_EVIDENCE_TEXT_CHARS = int(
    os.environ.get("POLYMATH_EVIDENCE_TEXT_CHARS", "1600"))


def _grounded_messages(query: str, bundle: dict, graph_facts: list,
                       history, carry_context,
                       reasoning: str | None = None,
                       reasoning_blend: list[str] | None = None) -> list[dict]:
    """Shared grounded-prompt assembly for every LLM backend.

    `reasoning`/`reasoning_blend` apply the v3.3 reasoning layer
    (orchestrator.api.reasoning, ported verbatim): templates prepend to
    the user prompt after the RAG context is assembled — the exact
    v3.3 composition point."""
    ev_lines: list[str] = []
    for item in (bundle.get("evidence_bundle") or [])[:40]:
        span = item.get("source_span") or {}
        loc = span.get("locator") or ""
        text = (span.get("text") or "")[:_EVIDENCE_TEXT_CHARS]
        if loc and text:
            ev_lines.append(f"[{loc}]\n{text}")
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
    if carried:
        context_block += ("\n\nEVIDENCE (carried from earlier turns):\n"
                          + "\n---\n".join(carried))
    if not context_block:
        context_block = "EVIDENCE: none retrieved for this turn."
    messages = [{"role": "system", "content": _llm_system_prompt()}]
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
                      reasoning_blend: list[str] | None = None):
    """LLM-PROVIDER-LAYER-V1: stream tokens from ANY provider through
    LiteLLM (OpenAI-format model strings: openai/gpt-4o,
    anthropic/claude-..., gemini/..., groq/..., ollama/...). Credentials
    come from the configured provider row; grounding prompt identical to
    the Ollama path. Yields {'token': str} or one {'error': ...}."""
    import litellm

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend)
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
                     reasoning_blend: list[str] | None = None):
    """Stream tokens from the local Ollama daemon over a grounded
    prompt. Yields {'token': str} pieces or one {'error': ...}.

    Prompt assembly is the SHARED builder — this function previously
    duplicated it inline, which let the two backends drift."""
    import httpx

    messages = _grounded_messages(query, bundle, graph_facts,
                                  history, carry_context,
                                  reasoning, reasoning_blend)

    try:
        with httpx.stream(
                "POST", f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": messages, "stream": True,
                      "think": True},
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
    if ui_mode not in ("FAST", "HYBRID", "GRAPH", "ASK"):
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
        try:
            yield _phase("scope", "Resolving query scope…")
            with tx() as conn:
                scope = resolve_http_scope(conn, req)
            yield _phase("scope_ok", "Scope resolved",
                         mode=scope.mode, corpora=list(scope.corpus_ids))

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
            if ui_mode == "GRAPH":
                from orchestrator.api.graph import graph_retrieve
                g = graph_retrieve(query, corpus_id)
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
                if ui_mode == "FAST":
                    from orchestrator.api.fast import fast_retrieve
                    fast = fast_retrieve(query, corpus_id)
                else:
                    from orchestrator.api.hybrid import hybrid_fast_retrieve
                    fast = hybrid_fast_retrieve(query, corpus_id)
                evidence_rows = [
                    {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                     "parent_id": c["parent_id"]}
                    for c in fast["evidence"]
                ]
                yield _phase("retrieve_done", "Evidence selected",
                             evidence_count=len(evidence_rows),
                             lane_sizes=fast["trace"].get("lane_sizes"))
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
                chunk_inventory.append({
                    "locator": loc,
                    "doc_id": item.get("source_document_id"),
                    "kind": item.get("text_kind") or item.get("kind"),
                    "preview": (span.get("text") or "")[:220],
                })
            from orchestrator.api.fast import degradations
            from polymath_shared.evidence_assembly import stale_projection_degradation

            retrieval = {
                "mode": "VECTOR" if ui_mode == "FAST" else ui_mode,
                "evidence_count": len(evidence_rows),
                "graph_fact_count": len(graph_facts),
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
                for tok in _gen(
                        llm_model, query, bundle, graph_facts,
                        req.history, req.carry_context,
                        req.reasoning, req.reasoning_blend):
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
                yield _sse("answer", {
                    "kind": "llm",
                    "result": {
                        "answer": "".join(full),
                        "model": llm_model,
                        "meta": {
                            "verdict": "generated",
                            "abstained": False,
                            "synthesis_version": f"{llm_backend}:{llm_model}",
                        },
                    },
                    "retrieval": retrieval,
                    "latency_ms": round(
                        (time.perf_counter() - t0) * 1000, 1),
                })
                yield _sse("done", {})
                return

            yield _phase("synthesize", "Validating claims against "
                                       "evidence…")
            answer = grounded_answer(bundle, query)

            yield _sse("answer", {
                "kind": "chat",
                "result": answer,
                "retrieval": retrieval,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            })
            yield _sse("done", {})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {
                "message": str(exc.detail)}
            yield _sse("error", {"status": exc.status_code, **detail})
        except Exception as exc:  # loud, typed-ish, never silent
            yield _sse("error", {"error_code": type(exc).__name__,
                                 "message": str(exc)[:300]})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
