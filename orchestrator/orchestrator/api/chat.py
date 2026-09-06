"""Chat API. POST /chat — the one-shot JSON transport of CHAT-RUNTIME-V1.

CHAT-RUNTIME-V1 (CHAT-QUERY-COMPILER-PLAN §3.7 / §4 P1.f): /chat has no
retrieval, compiler or synthesis logic of its own. It maps its request onto
the runtime's request (`stream_request`, the field table below), runs
`run_chat` — which drains the SAME generator `/chat/stream` streams — and
returns the answer frame as one JSON object. MCP `ask` posts here and
inherits everything: the compiler, the CHAT-RETRIEVAL-V2 compositions,
aspect coverage, the evidence composer, CARRY-V2 and SYNTHESIS-V2. An
identical request yields the identical compiled plan, retrieval decision,
evidence ids, carry admission, executed mode, degraded list and synthesis
contract on both routes; what differs is transport — one body instead of
frames, and the receipt's `kind` (`chat`) and `client` (the caller's user
agent) on the same receipt payload the stream writes.

Historical contract kept: without `synthesizer` the deterministic grounded
synthesizer answers (claims validated against the bundle; answer /
citations / claims / meta as before — contracts/answer/v2), `meta.mode` is
the EXECUTED mode (CHAT-MODE-TRUTH-V1), `evidence: true` appends
RETRIEVE-EVIDENCE-ROWS-V1 rows. Assembly failures stay loud (502).
"""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from polymath_shared.db import tx
from polymath_shared.query_receipts import Timer, record_query_receipt

from .ui import CarriedChunk, HistoryTurn, StreamChatRequest, run_chat

router = APIRouter()

#: /chat answers deterministically unless a synthesizer is named: its JSON
#: contract (claims validated against the bundle) predates the LLM layer, and
#: MCP `ask` / TRAIL read `claims` and `citations` from it.
CHAT_DEFAULT_SYNTHESIZER = "deterministic-template-v3"


class ChatRequest(BaseModel):
    message: str
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    workspace: str | None = None
    all_authorized: bool = False
    mode: str | None = None
    latent: bool | None = None
    utility: bool | None = None
    # CHAT-RETRIEVAL-V2 P1.a: per-request override (v1 | v2) for evaluation and A/B.
    retrieval: str | None = None
    # CHAT-EVIDENCE-ROWS-V1 (2026-09-03): also return the answer's evidence as
    # RETRIEVE-EVIDENCE-ROWS-V1 rows (human source, timecodes, attested facts)
    # so an agent gets the FULL answer path AND contract rows in one call.
    evidence: bool = False
    # CHAT-RUNTIME-V1 (P1.f): the runtime's remaining inputs, mirrored from
    # StreamChatRequest so an API / MCP caller can drive the same turn the UI
    # drives. Every default keeps /chat's historical behaviour.
    synthesizer: str | None = None        # None -> CHAT_DEFAULT_SYNTHESIZER (the stream's None is the UI LLM)
    history: list[HistoryTurn] = []
    carry_context: list[CarriedChunk] = []
    compiler: str | None = None           # off | shadow | on; None -> POLYMATH_CHAT_COMPILER
    reasoning: str | None = None
    reasoning_blend: list[str] = []


def stream_request(req: ChatRequest) -> StreamChatRequest:
    """CHAT-REQUEST-MAP-V1: ChatRequest → StreamChatRequest, field by field.

        message            → message
        corpus_id, corpus_ids, workspace, all_authorized
                           → the same four (QUERY-SCOPE-V1, resolved by the runtime)
        mode               → mode; None/"" → resolve_chat_mode(None) = HYBRID
                             (CHAT-DEFAULT-HYBRID-V1). Explicit modes pass
                             through: the runtime is the one validator
                             (FAST/VECTOR, HYBRID, GRAPH, WILDCARD, ASK → 422
                             `unknown_mode` otherwise; LEGACY has no runtime path)
        latent, utility    → latent, utility (v1 plan knobs; `utility` was added
                             to StreamChatRequest for this mapping)
        retrieval          → retrieval (v1 | v2 | v2-single)
        synthesizer        → synthesizer; None → deterministic-template-v3
        history            → history (HistoryTurn)
        carry_context      → carry_context (CarriedChunk, CARRY-V2)
        compiler           → compiler (off | shadow | on)
        reasoning, reasoning_blend → the same
        evidence           → NOT a runtime input: a /chat response add-on applied
                             after the turn (`attach_evidence_rows`, built from
                             the answer's own citations — never a second retrieval)
    """
    return StreamChatRequest(
        message=req.message,
        corpus_id=req.corpus_id, corpus_ids=req.corpus_ids,
        workspace=req.workspace, all_authorized=req.all_authorized,
        mode=(req.mode or resolve_chat_mode(None)),
        latent=req.latent, utility=req.utility, retrieval=req.retrieval,
        synthesizer=(req.synthesizer or CHAT_DEFAULT_SYNTHESIZER),
        history=list(req.history or []), carry_context=list(req.carry_context or []),
        compiler=req.compiler, reasoning=req.reasoning,
        reasoning_blend=list(req.reasoning_blend or []),
    )


def _chat_impl(req: ChatRequest, *, receipt=None) -> dict:
    """The /chat body: ONE runtime turn (`run_chat`, the same frames the
    stream emits, drained), then the /chat-only evidence-rows add-on.
    Synchronous — it runs in a worker thread, exactly like the stream's
    generator under Starlette's iterate_in_threadpool."""
    out = run_chat(stream_request(req), route="chat", receipt=receipt)
    if req.evidence:
        attach_evidence_rows(out, req)
    return out


_LOC_CHUNK = re.compile(r"^chunk:([A-Za-z0-9_]+)")


def resolve_chat_mode(requested: str | None) -> str:
    """CHAT-DEFAULT-HYBRID-V1 (plan P0.a, measured 2026-09-05): `/chat` with
    no mode ran the frozen LEGACY regression path (12,732 claims, a 437 KB
    triple dump, 30–50 s) and stamped it HYBRID. The default for chat is
    HYBRID. `/retrieve` keeps retrieval_modes.DEFAULT_MODE for its own frozen
    evaluations. CHAT-RUNTIME-V1 (P1.f): `stream_request` takes the DEFAULT
    from here; an explicit mode is validated by the runtime itself (the one
    authority for both routes), where LEGACY no longer has a path."""
    from polymath_shared.retrieval_modes import MODE_HYBRID, validate_mode
    return validate_mode(requested or MODE_HYBRID)


def attach_evidence_rows(out: dict, req: "ChatRequest") -> dict:
    """CHAT-EVIDENCE-ROWS-V1: the answer's own citations as RETRIEVE-EVIDENCE-
    ROWS-V1 rows. Built from `citations[].locators` (chunk ids) and
    `source_document_ids`, so it is identical on every answer path (FAST,
    HYBRID, GRAPH) and never a second retrieval."""
    from orchestrator.api.evidence_rows import build_evidence_rows

    chunk_ids: list[str] = []
    doc_ids: list[str] = []
    for c in sorted(out.get("citations") or [], key=lambda x: x.get("citation_id") or 0):
        for loc in c.get("locators") or []:
            m = _LOC_CHUNK.match(str(loc))
            if m and m.group(1) not in chunk_ids:
                chunk_ids.append(m.group(1))
        for d in c.get("source_document_ids") or []:
            if d not in doc_ids:
                doc_ids.append(d)
    corpus_ids = list(req.corpus_ids or ([req.corpus_id] if req.corpus_id else []))
    try:
        with tx() as conn:
            out["evidence_rows"] = build_evidence_rows(
                conn,
                {"child_evidence": [{"chunk_id": cid, "rerank_score": float(len(chunk_ids) - i)} for i, cid in enumerate(chunk_ids)],
                 "selected_documents": [{"doc_id": d, "rerank_score": 0.0} for d in doc_ids],
                 "graph_facts": []},
                corpus_ids, limit=max(12, len(chunk_ids)), explore=False)
        out["evidence_contract"] = "retrieve-evidence-rows-v1"
    except Exception as exc:  # noqa: BLE001 — rows are an add-on; the answer already stands
        out["evidence_rows"] = []
        out["evidence_rows_error"] = f"{type(exc).__name__}: {exc}"[:200]
    meta = out.setdefault("meta", {})
    # CHAT-MODE-TRUTH-V1 (plan P0.a): the executed mode is stamped by
    # run_chat; never label a LEGACY answer as HYBRID by default.
    meta.setdefault("mode", "UNKNOWN")
    meta["requested_mode"] = req.mode
    return out


@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> dict:
    """QUERY-RECEIPTS-V1 on the JSON transport. The runtime writes the turn's
    receipt through `_sink` — kind `chat`, the caller's user agent: the
    transport's tags on the same payload the stream receipts (`route: chat`
    in its meta). A request the runtime rejected before it ran (empty
    message, unknown mode or synthesizer) never reached the runtime's
    writer and is receipted here, so every /chat call leaves exactly one row
    — best effort, off the critical path (polymath_shared.query_receipts)."""
    client = request.headers.get("user-agent", "")
    receipted: list[str] = []

    def _sink(payload: dict) -> None:
        receipted.append(record_query_receipt(tx, kind="chat", client=client, **payload) or "")

    with Timer() as t:
        try:
            return await run_in_threadpool(_chat_impl, req, receipt=_sink)
        except Exception as exc:  # noqa: BLE001 — record, then re-raise unchanged
            if not receipted:
                detail = getattr(exc, "detail", None)
                scope_corpora = [req.corpus_id] if req.corpus_id else list(req.corpus_ids or [])
                scope_kind = ("corpus" if req.corpus_id else "corpora" if req.corpus_ids
                              else "workspace" if req.workspace else "all_authorized" if req.all_authorized else None)
                record_query_receipt(tx, kind="chat", question=req.message, req=req,
                                     scope_corpora=scope_corpora, scope_kind=scope_kind,
                                     wall_ms=(time.perf_counter() - t.t0) * 1000.0,
                                     error=f"{type(exc).__name__}: {detail if detail is not None else exc}",
                                     client=client)
            raise
