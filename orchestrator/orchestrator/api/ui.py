"""UI support layer (POLYMATH-UI-V1): the thin endpoints the web chat
needs on top of the existing query product.

  GET  /corpora            corpus picker data (docs, readiness, purpose)
  GET  /documents          file-manager listing for one corpus
  POST /upload             multipart upload → canonical intake (same
                           submit_intake path as /intake; nothing new)
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

import base64
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

DETERMINISTIC = {
    "id": "deterministic-template-v3",
    "label": "Deterministic · grounded",
    "description": "Claim-validated assembly from stored evidence. "
                   "Every sentence cites a bundle item; unsupported "
                   "queries abstain.",
    "kind": "deterministic",
    "default": True,
}


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
def corpora() -> dict:
    with tx() as conn:
        # independent aggregates: joining documents AND runs onto
        # corpora cross-multiplies (measured: 60s+ on 12k runs)
        rows = conn.execute(
            """
            SELECT c.corpus_id, c.purpose, c.query_enabled,
                   COALESCE(d.docs, 0),
                   COALESCE(r.ready, 0) > 0
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
    return {"corpora": [
        {"corpus_id": r[0], "purpose": r[1], "query_enabled": r[2],
         "documents": r[3], "query_ready": r[4]}
        for r in rows if r[3] > 0 or r[1] == "production"
    ]}


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
            """SELECT run_id, status, created_at FROM runs
                WHERE corpus_id = %s ORDER BY created_at DESC LIMIT 25""",
            (corpus_id,)).fetchall()
    return {
        "corpus_id": corpus_id,
        "documents": [
            {"doc_id": r[0], "source_name": r[1], "media_type": r[2],
             "bytes": r[3], "created_at": str(r[4]), "chunks": r[5]}
            for r in rows
        ],
        "runs": [{"run_id": r[0], "status": r[1], "created_at": str(r[2])}
                 for r in runs],
    }


@router.post("/upload")
async def upload(corpus_id: str = Form(...),
                 file: UploadFile = File(...)) -> dict:
    """Multipart convenience wrapper over the canonical intake path."""
    from polymath_shared.intake_submission import (
        canonical_intake_payload,
        submit_intake,
    )

    raw = await file.read()
    if not raw:
        raise HTTPException(422, "empty file")
    media_type = file.content_type or "application/octet-stream"
    payload = canonical_intake_payload(
        corpus_id=corpus_id,
        source_name=file.filename or "upload.bin",
        media_type=media_type,
        content_b64=base64.b64encode(raw).decode(),
    )
    with tx() as conn:
        out = submit_intake(conn, payload)
    return {**out, "corpus_id": corpus_id,
            "source_name": file.filename, "bytes": len(raw)}


@router.get("/synthesizers")
def synthesizers() -> dict:
    return {"synthesizers": [DETERMINISTIC, *_ollama_models()]}


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
    removed: dict[str, int] = {}
    with tx() as conn:
        row = conn.execute("SELECT 1 FROM corpora WHERE corpus_id=%s",
                           (corpus_id,)).fetchone()
        if not row:
            raise HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN",
                                      "message": f"{corpus_id!r} not found"})
        doc_ids = [r[0] for r in conn.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s",
            (corpus_id,)).fetchall()]
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
        from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
        from polymath_shared.projection_contracts import qdrant_collection_name
        from polymath_shared.stores import qdrant_client

        client = qdrant_client(timeout=30)
        try:
            for contract in (NEURAL_EMBED_CONTRACT.contract_id,):
                name = qdrant_collection_name(corpus_id, contract)
                if client.collection_exists(name):
                    client.delete_collection(name)
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
    synthesizer: Optional[str] = "deterministic-template-v3"
    # LLM generation context: prior conversation turns and evidence
    # chunks carried from earlier answers in this chat, so a request
    # like "build a PBQ test from what we just studied" can use the
    # WHOLE session's retrieved material, not only this turn's.
    history: list[HistoryTurn] = []
    carry_context: list[CarriedChunk] = []


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


_LLM_SYSTEM = """You are Polymath's generation layer over an \
evidence-first retrieval system. You receive EVIDENCE blocks retrieved \
from the user's own corpus (current turn + material carried from \
earlier turns of this session).

Rules:
- Ground everything you produce in the provided evidence. When you use \
a piece of evidence, reference its [locator] so the user can audit it.
- If the user asks you to BUILD something (a quiz, a PBQ-style HTML \
test, flashcards, a study plan, code), build it fully, drawing the \
substance from the evidence. Emit complete artifacts (e.g., a full \
self-contained HTML document in an ```html code block).
- If the evidence does not contain what the user needs, say exactly \
what is missing instead of inventing facts.
- These answers are GENERATED and are labeled as such downstream; do \
not claim to be a validated source of truth."""


def _ollama_generate(model: str, query: str, bundle: dict,
                     graph_facts: list, history, carry_context):
    """Stream tokens from the local Ollama daemon over a grounded
    prompt. Yields {'token': str} pieces or one {'error': ...}."""
    import httpx

    ev_lines: list[str] = []
    for item in (bundle.get("evidence_bundle") or [])[:40]:
        span = item.get("source_span") or {}
        loc = span.get("locator") or ""
        text = (span.get("text") or "")[:900]
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

    messages = [{"role": "system", "content": _LLM_SYSTEM}]
    for turn in (history or [])[-12:]:
        if turn.role in ("user", "assistant") and turn.content:
            messages.append({"role": turn.role,
                             "content": turn.content[:4000]})
    messages.append({"role": "user",
                     "content": f"{context_block}\n\nREQUEST:\n{query}"})

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
    synth = req.synthesizer or "deterministic-template-v3"
    llm_model = synth[len("ollama:"):] if synth.startswith("ollama:") else None
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
            retrieval = {
                "mode": "VECTOR" if ui_mode == "FAST" else ui_mode,
                "evidence_count": len(evidence_rows),
                "graph_fact_count": len(graph_facts),
                "chunks": chunk_inventory,
            }

            if llm_model is not None:
                yield _phase("generate",
                             f"Generating with {llm_model}…",
                             model=llm_model,
                             carried=len(req.carry_context))
                full: list[str] = []
                for tok in _ollama_generate(
                        llm_model, query, bundle, graph_facts,
                        req.history, req.carry_context):
                    if tok.get("error"):
                        yield _sse("error", tok)
                        return
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
                            "synthesis_version": f"ollama:{llm_model}",
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
