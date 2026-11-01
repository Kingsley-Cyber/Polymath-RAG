"""POST /product/search — product search over ANY corpus (product-search-v1, PRODUCT-SEARCH-E2E 2026-11-01).

The owner: "it shouldnt really expect a niche it uses a corpus to find products"; "it should prompt people with cj dropshipping
finds"; "users of the connector and link works seamlessly as me". Two ways in, one answer shape:

  * WITHOUT `hypotheses`: ONE chat-runtime turn (`ui.run_chat`, the same generator /chat/stream streams) in FORCED product mode
    with the app's default LLM synthesizer (`ui._default_synthesizer()`, unless `model` names one): scope and retrieval as any
    chat turn (steered toward hypothesis material), product hypotheses written from the corpus, CJ Dropshipping searched per
    hypothesis, Alibaba handed to the user's local Agent Reach, ending with the OFFER of the full governed run.
  * WITH `hypotheses` ([{title, search_terms[]}]): the caller's agent did the reasoning; only the CJ / Alibaba lookups run (no
    retrieval, no model).
Response: {contract, route, answer, verdict, model, product_research, evidence (tag, chunk_id, source, text <= 400 chars),
retrieval (mode, engine, evidence_count, used_evidence, degraded, corpus_ids), phases, kind, latency_ms, runtime}. No corpus
given = the scope the runtime resolves for the caller (all_authorized, narrowed to what the caller may use): nothing → the
resolver's typed QUERY_SCOPE_EMPTY naming list_corpora — never a silent empty answer; several libraries → the runtime routes the
request to the best one (product-library-routing-v1, receipted in product_research.receipts.routing). The caller's principal flows through (adapter-run style: carried into the worker thread explicitly). One query receipt
per call, kind `product` (meta.route `product/search`, meta.product_search = counts and statuses only)."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from polymath_shared import principal_context
from polymath_shared.db import tx
from polymath_shared.query_receipts import Timer, record_query_receipt

router = APIRouter()
ROUTE = "product/search"
KIND = "product"


class ProductHypothesisIn(BaseModel):
    title: str
    search_terms: list[str] = []
    problem: str | None = None
    audience: str | None = None


class ProductSearchRequest(BaseModel):
    message: str
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    geography: str | None = None
    model: str | None = None
    hypotheses: list[ProductHypothesisIn] | None = None
    limit_per_hypothesis: int | None = None


def _options(req: ProductSearchRequest) -> dict[str, Any]:
    return {"geography": req.geography, "limit_per_hypothesis": req.limit_per_hypothesis}


def _named(req: ProductSearchRequest) -> bool:
    return bool(req.corpus_id or req.corpus_ids)


def _scope_kind(req: ProductSearchRequest) -> str:
    return "corpus" if req.corpus_id else "corpora" if req.corpus_ids else "all_authorized"


def _resolve_corpora(req: ProductSearchRequest) -> list[str]:
    """The libraries this caller's request names (or may use, when it names none), through the runtime's own scope resolver."""
    from types import SimpleNamespace

    from orchestrator.api.retrieve import resolve_http_scope
    probe = SimpleNamespace(corpus_id=req.corpus_id, corpus_ids=req.corpus_ids, workspace=None, all_authorized=not _named(req))
    with tx() as conn:
        return list(resolve_http_scope(conn, probe).corpus_ids)


def _with_agent_hypotheses(req: ProductSearchRequest, message: str, principal: str | None) -> tuple[dict[str, Any], dict]:
    """The caller's own hypotheses: CJ / Alibaba lookups only. Returns (response, receipt meta)."""
    from polymath_shared.product_search import ProductTurn, detect
    from polymath_shared.product_search.service import CONTRACT
    note = None
    try:
        corpora = _resolve_corpora(req)
    except HTTPException as exc:
        code = exc.detail.get("error_code") if isinstance(exc.detail, dict) else None
        if _named(req) or code not in ("QUERY_SCOPE_EMPTY", "QUERY_SCOPE_REQUIRED"):
            raise
        # the lookups need no library; the offer of the full run does: it says so instead of failing the lookups
        corpora = []
    if not corpora:
        note = ("no library was resolved for this caller: name corpus_ids (list_corpora lists them) when you start the full "
                "research run")
    turn = ProductTurn(detect(message, force=True), message=message, corpus_ids=corpora, principal_id=principal, options=_options(req))
    block, verdict, md = turn.finish_agent([h.model_dump() for h in req.hypotheses or []])
    if note:
        block["limitations"].append(note)
    return ({"contract": CONTRACT, "route": ROUTE, "answer": md, "verdict": verdict, "model": None, "product_research": block,
             "evidence": [], "retrieval": None, "phases": [], "kind": KIND, "source": "agent_hypotheses"},
            {"verdict": verdict, "product_search": turn.receipt(), "route": ROUTE})


def _forced_turn(req: ProductSearchRequest, message: str, receipt) -> dict[str, Any]:
    """One chat-runtime turn in forced product mode; the answer reshaped for an agent."""
    from orchestrator.api import evidence as evidence_mod
    from orchestrator.api.ui import StreamChatRequest, run_chat
    from polymath_shared.product_search.service import CONTRACT, compact_evidence
    sreq = StreamChatRequest(message=message, corpus_id=req.corpus_id, corpus_ids=req.corpus_ids, all_authorized=not _named(req),
                             mode="HYBRID", synthesizer=req.model or None, product=True, product_options=_options(req))
    # several libraries in scope are routed to one inside the runtime (product-library-routing-v1); its errors pass through typed
    out = run_chat(sreq, route=ROUTE, receipt=receipt)
    retrieval = out.get("retrieval") or {}
    previews = {str(c.get("locator")): c.get("preview") for c in retrieval.get("chunks") or [] if c.get("locator")}

    def text_of(chunk_id: str) -> str | None:
        return (evidence_mod._resolve_chunk(chunk_id) or {}).get("text")

    research = out.get("product_research")
    return {"contract": CONTRACT, "route": ROUTE, "answer": out.get("answer"), "verdict": (out.get("meta") or {}).get("verdict"),
            "model": out.get("model"), "product_research": research,
            "evidence": compact_evidence(retrieval.get("legend") or [], text_of, previews),
            "retrieval": {"mode": retrieval.get("mode"), "engine": retrieval.get("engine"),
                          "evidence_count": retrieval.get("evidence_count"), "used_evidence": retrieval.get("used_evidence"),
                          "degraded": retrieval.get("degraded"),
                          "corpus_ids": (research or {}).get("corpus_ids") or list(req.corpus_ids or ([req.corpus_id] if req.corpus_id else []))},
            "phases": out.get("phases") or [], "kind": out.get("kind"), "latency_ms": out.get("latency_ms"),
            "runtime": out.get("runtime")}


@router.post("/product/search")
async def product_search(req: ProductSearchRequest, request: Request) -> dict:
    """product-search-v1 — see the module docstring. 422 `message_required` for an empty message, `bad_hypotheses` when every
    supplied hypothesis lacks a title; every other refusal is the runtime's or the scope resolver's own typed error."""
    message = " ".join(str(req.message or "").split())
    client = request.headers.get("user-agent", "")
    principal = principal_context.current()
    receipted: list[str] = []

    def _sink(payload: dict) -> None:
        receipted.append(record_query_receipt(tx, kind=KIND, client=client, **payload) or "")

    with Timer() as t:
        try:
            if not message:
                raise HTTPException(422, {"error_code": "message_required", "message": "message is the user's product request"})
            if req.hypotheses is not None and req.hypotheses and not any(h.title.strip() for h in req.hypotheses):
                raise HTTPException(422, {"error_code": "bad_hypotheses",
                                          "message": "each hypothesis needs a title (and 1-3 search_terms)"})

            def _work() -> dict:
                with principal_context.acting_as(principal):
                    if req.hypotheses:
                        out, meta = _with_agent_hypotheses(req, message, principal)
                        out["latency_ms"] = round((time.perf_counter() - t.t0) * 1000.0, 1)
                        record_query_receipt(tx, kind=KIND, question=message, req=req,
                                             scope_corpora=list((out.get("product_research") or {}).get("corpus_ids") or []),
                                             scope_kind=_scope_kind(req), wall_ms=out["latency_ms"],
                                             out={"answer": out["answer"], "meta": meta}, client=client)
                        receipted.append("agent_hypotheses")
                        return out
                    return _forced_turn(req, message, _sink)
            return await run_in_threadpool(_work)
        except Exception as exc:  # noqa: BLE001 — record, then re-raise unchanged
            if not receipted:
                detail = getattr(exc, "detail", None)
                record_query_receipt(tx, kind=KIND, question=message or req.message, req=req,
                                     scope_corpora=[req.corpus_id] if req.corpus_id else list(req.corpus_ids or []),
                                     scope_kind=_scope_kind(req), wall_ms=(time.perf_counter() - t.t0) * 1000.0,
                                     error=f"{type(exc).__name__}: {detail if detail is not None else exc}", client=client)
            raise
