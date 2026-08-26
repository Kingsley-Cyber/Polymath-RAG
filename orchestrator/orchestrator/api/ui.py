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

SYNTHESIZERS = [
    {
        "id": "deterministic-template-v3",
        "label": "Deterministic · grounded",
        "description": "Claim-validated assembly from stored evidence. "
                       "Every sentence cites a bundle item; unsupported "
                       "queries abstain.",
        "default": True,
    },
]


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
    return {"synthesizers": SYNTHESIZERS}


# ---------------------------------------------------------------- SSE

class StreamChatRequest(BaseModel):
    message: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    workspace: Optional[str] = None
    all_authorized: bool = False
    mode: Optional[str] = "HYBRID"        # VECTOR|HYBRID|GRAPH|ASK
    synthesizer: Optional[str] = "deterministic-template-v3"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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
    if req.synthesizer and req.synthesizer != "deterministic-template-v3":
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

            yield _phase("synthesize", "Validating claims against "
                                       "evidence…")
            answer = grounded_answer(bundle, query)

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

            yield _sse("answer", {
                "kind": "chat",
                "result": answer,
                "retrieval": {
                    "mode": "VECTOR" if ui_mode == "FAST" else ui_mode,
                    "evidence_count": len(evidence_rows),
                    "graph_fact_count": len(graph_facts),
                    "chunks": chunk_inventory,
                },
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
