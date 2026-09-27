"""DEEP-RESEARCH-MODE-V1 DR2 — `POST /research/deep`: the breadth × depth research loop (shared/polymath_shared/deep_research)
over THIS request's libraries, streamed on the chat's own frame types — `phase` (progress), `token` (the report), `answer`
(kind "deep": the report, its resolved citations and the run's counts), `error`, `done` — plus SSE comment heartbeats so a
proxy never sees a silent stream.

Scope: the libraries are resolved and checked once, here, for the caller (a friend only reaches libraries they may read);
every search then names exactly those libraries AND runs under the caller's principal, so no step can widen the scope (K1).
The planning and extraction calls use the chat compiler's governed lanes (per-lane limiter); the report is written by the
composer's model, like a chat answer. One deep run at a time per person. A client that disconnects cancels the run."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue as _queue
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from polymath_shared import deep_research as DR
from polymath_shared import principal_context
from pydantic import BaseModel, Field

router = APIRouter()
log = logging.getLogger(__name__)

HEARTBEAT_S = float(os.environ.get("POLYMATH_DEEP_RESEARCH_HEARTBEAT_S", "15"))
PORT_TIMEOUT_S = 60.0
ROWS_PER_SEARCH = 10
_RUNNING: dict[str, threading.Event] = {}
_LOCK = threading.Lock()
_END = object()


class DeepResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    preset: str = "standard"                 # quick 3×1 · standard 3×2 · thorough 4×2
    mode: str = "HYBRID"                     # the retrieval mode every search uses
    synthesizer: str | None = None           # the composer's model writes the report (like chat)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _Aliases:
    """Short per-run citation ids (c1, c2, …) for the model; the real evidence row stays behind each alias."""

    def __init__(self) -> None:
        self._by_id: dict[str, str] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def alias(self, row: dict[str, Any]) -> str:
        rid = str(row.get("id"))
        with self._lock:
            if rid not in self._by_id:
                self._by_id[rid] = f"c{len(self._by_id) + 1}"
                self.rows[self._by_id[rid]] = row
            return self._by_id[rid]


def _libraries(req: DeepResearchRequest) -> list[str]:
    from orchestrator.web_scope import require_corpora
    ids = [c for c in ([req.corpus_id] if req.corpus_id else []) + list(req.corpus_ids or []) if c]
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise HTTPException(422, {"error_code": "LIBRARY_REQUIRED", "message": "name at least one library"})
    require_corpora(ids)                     # a friend may only research libraries they can read
    return ids


def _build_rows(response: dict[str, Any], corpus_ids: list[str], limit: int) -> list[dict[str, Any]]:
    from orchestrator.api.evidence_rows import build_evidence_rows
    from polymath_shared.db import tx
    with tx() as conn:
        return build_evidence_rows(conn, response, corpus_ids, limit=limit, explore=False)


def evidence_rows_of(out: dict[str, Any], corpus_ids: list[str], limit: int) -> list[dict[str, Any]]:
    """DR4: `/retrieve` builds `evidence_rows` only on the default lane; the engine modes (HYBRID, FAST, GRAPH, WILDCARD,
    GNN) answer with a flat `evidence` list and ignore `evidence: true`. Build the same rows from that list, in its order,
    the way chat does (`chat.attach_evidence_rows`), so a search in any mode feeds the research."""
    if out.get("evidence_rows"):
        return list(out["evidence_rows"])
    ids = list(dict.fromkeys(e["chunk_id"] for e in out.get("evidence") or [] if isinstance(e, dict) and e.get("chunk_id")))
    if not ids:
        return []
    return _build_rows({"child_evidence": [{"chunk_id": cid, "rerank_score": float(len(ids) - i)} for i, cid in enumerate(ids)],
                        "selected_documents": [], "graph_facts": []}, corpus_ids, limit)


def _retrieve_port(loop: asyncio.AbstractEventLoop, principal: str | None, mode: str, aliases: _Aliases):
    from orchestrator.api.retrieve import RetrieveRequest, _retrieve_impl

    def retrieve(query: str, scope: Any) -> list[DR.Row]:
        async def call() -> dict:
            with principal_context.acting_as(principal):
                return await _retrieve_impl(RetrieveRequest(query=query, corpus_ids=list(scope), mode=mode,
                                                            limit=ROWS_PER_SEARCH, evidence=True))
        out = asyncio.run_coroutine_threadsafe(call(), loop).result(timeout=PORT_TIMEOUT_S)
        rows = []
        for r in evidence_rows_of(out or {}, list(scope), ROWS_PER_SEARCH):
            text = str(r.get("text_clean") or r.get("text") or "").strip()
            if not r.get("id") or not text:
                continue
            rows.append(DR.Row(cid=aliases.alias(r), text=text, source=str(r.get("source") or r.get("title") or ""),
                               score=float(r.get("score") or 0.0)))
        return rows[:ROWS_PER_SEARCH]
    return retrieve


def research_lane_names(stage_pin_fn, compiler_stage: str) -> list[str]:
    """DR0: the `deep_research` stage pin (config/llm_accounts.yaml), else the chat compiler's lanes."""
    return list(stage_pin_fn("deep_research") or stage_pin_fn(compiler_stage) or [])


def _complete_port(key: str):
    """Planning and extraction on the chat compiler's governed lanes (limiter-admitted), two attempts across lanes."""
    from orchestrator.api.ui import _compiler_attempt_order
    from polymath_shared.chat_plan import COMPILER_STAGE
    from polymath_shared.llm_extraction.client import LLMExtractionClient
    from polymath_shared.llm_extraction.pool import cloud_endpoints, stage_pin
    names = research_lane_names(stage_pin, COMPILER_STAGE)
    endpoints = [e for e in cloud_endpoints() if e.name in names]
    if not endpoints:
        raise HTTPException(503, {"error_code": "NO_RESEARCH_LANE", "message": "no model lane is configured for research"})

    def complete(prompt: str, *, system: str, max_tokens: int) -> str:
        failures = []
        for ep in _compiler_attempt_order(endpoints, key, max_attempts=2):
            client = LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key, api_key=ep.api_key,
                                         cloud_opts=ep.cloud_opts, timeout_s=PORT_TIMEOUT_S, max_attempts=1)
            client.endpoint_name = ep.name
            client.attempt_stage, client.attempt_function = "deep_research", "DEEP_RESEARCH"
            text, error = client.complete_one(prompt, system_prompt=system, max_tokens=max_tokens)
            if not error and text and text.strip():
                return text
            failures.append(error or "empty")
        raise RuntimeError("research lanes failed: " + ",".join(failures))
    return complete


def _report_tokens(synth: str, system: str, prompt: str, cancel: threading.Event):
    """Yield the report's text pieces from the composer's model (litellm or Ollama ids, as chat accepts them)."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    if synth.startswith("litellm:"):
        import litellm
        from orchestrator.api.ui import _chat_max_tokens, _litellm_credentials
        model = synth[len("litellm:"):]
        stream = litellm.completion(model=model, messages=messages, stream=True, timeout=300, max_tokens=_chat_max_tokens(),
                                    **_litellm_credentials(model))
        for chunk in stream:
            if cancel.is_set():
                return
            piece = getattr(chunk.choices[0].delta, "content", None) if chunk.choices else None
            if piece:
                yield piece
    elif synth.startswith("ollama:"):
        import httpx
        from orchestrator.api.ui import OLLAMA_URL
        with httpx.stream("POST", f"{OLLAMA_URL}/api/chat", timeout=300,
                          json={"model": synth[len("ollama:"):], "messages": messages, "stream": True}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancel.is_set():
                    return
                if line.strip():
                    piece = (json.loads(line).get("message") or {}).get("content")
                    if piece:
                        yield piece
    else:
        raise ValueError(f"unknown synthesizer {synth!r}")


_STAGE_LABEL = {"plan": "Planning searches", "retrieve": "Searching", "extract": "Reading what came back",
                "level_done": "Finished a round", "stopped": "Research stopped"}


def _phase(ev: dict[str, Any], t0: float) -> dict[str, Any]:
    stage = str(ev.get("stage") or "research")
    label = _STAGE_LABEL.get(stage, stage)
    if ev.get("query") and stage in ("retrieve", "extract"):
        label = f"{label}: {str(ev['query'])[:120]}"
    if stage == "level_done" and ev.get("new_learnings") is not None:
        label = f"{label}: {ev['new_learnings']} new findings"
    if stage == "stopped" and ev.get("reason"):
        label = f"{label} ({ev['reason']})"
    return {"stage": f"deep_{stage}", "label": label, "t": int((time.monotonic() - t0) * 1000),
            **{k: v for k, v in ev.items() if k in ("depth", "completed", "total", "new_learnings", "reason")}}


def _worker(req: DeepResearchRequest, libraries: list[str], synth: str, principal: str | None, loop: asyncio.AbstractEventLoop,
            out: _queue.Queue, cancel: threading.Event) -> None:
    """The run, on its own thread: research events, then the report, then the answer, then _END."""
    t0 = time.monotonic()
    try:
        aliases = _Aliases()
        config = DR.Config.preset(req.preset, score_floor=float("-inf"))
        outcome = DR.run_research(req.question, tuple(libraries),
                                  retrieve=_retrieve_port(loop, principal, req.mode.upper(), aliases),
                                  complete=_complete_port(req.question), config=config,
                                  on_event=lambda ev: out.put(("phase", _phase(ev, t0))), cancel=cancel)
        summary = outcome.summary()
        if cancel.is_set() or outcome.stop_reason == "cancelled":
            out.put(("error", {"error_code": "CANCELLED", "message": "the research was stopped"}))
            return
        if not outcome.learnings:
            code = "RESEARCH_FAILED" if (outcome.retrieval_errors or outcome.llm_errors) else "NOTHING_FOUND"
            message = ("every search or model call failed" if code == "RESEARCH_FAILED"
                       else "the libraries hold nothing on this question")
            out.put(("error", {"error_code": code, "message": message, "summary": summary}))
            return
        out.put(("phase", {"stage": "deep_report", "label": "Writing the report", "t": int((time.monotonic() - t0) * 1000)}))
        system, prompt = outcome.report_prompt(req.question)
        text = ""
        for piece in _report_tokens(synth, system, prompt, cancel):
            text += piece
            out.put(("token", {"token": piece}))
        valid, unknown = DR.validate_report_citations(text, outcome)
        citations = [{"cid": c, **{k: (aliases.rows.get(c) or {}).get(k) for k in ("id", "kind", "doc_id", "corpus_id", "title", "source")},
                      "text": str((aliases.rows.get(c) or {}).get("text_clean") or "")[:600]} for c in valid]
        out.put(("answer", {"kind": "deep", "latency_ms": int((time.monotonic() - t0) * 1000),
                            "result": {"text": text, "model": synth, "citations": citations, "unknown_citations": list(unknown),
                                       "meta": {"verdict": "supported" if valid else "unsupported", "deep_research": summary}},
                            "retrieval": None}))
    except Exception as exc:  # noqa: BLE001 — the stream reports the failure; the message never carries source text
        out.put(("error", {"error_code": type(exc).__name__, "message": str(exc)[:300]}))
    finally:
        out.put((_END, None))


@router.post("/research/deep")
async def deep_research(req: DeepResearchRequest) -> StreamingResponse:
    libraries = _libraries(req)
    principal = principal_context.current()
    from orchestrator.api.ui import _default_synthesizer
    synth = req.synthesizer or _default_synthesizer()
    if not synth.startswith(("litellm:", "ollama:")):
        raise HTTPException(422, {"error_code": "UNKNOWN_SYNTHESIZER", "message": f"{synth!r}"})
    try:
        DR.Config.preset(req.preset)
    except ValueError as exc:
        raise HTTPException(422, {"error_code": "UNKNOWN_PRESET", "message": str(exc)}) from None
    who = principal or "owner"
    cancel = threading.Event()
    with _LOCK:
        if who in _RUNNING:
            raise HTTPException(409, {"error_code": "DEEP_RESEARCH_BUSY", "message": "one deep research run at a time; stop the other first"})
        _RUNNING[who] = cancel

    async def events():
        loop = asyncio.get_running_loop()
        out: _queue.Queue = _queue.Queue()
        t0 = time.monotonic()
        answer: dict[str, Any] | None = None
        failure: str | None = None
        worker = threading.Thread(target=_worker, args=(req, libraries, synth, principal, loop, out, cancel), daemon=True,
                                  name="deep-research")
        try:
            yield _sse("phase", {"stage": "deep_start", "label": f"Deep research over {', '.join(libraries)}", "t": 0,
                                 "preset": req.preset})
            worker.start()
            while True:
                try:
                    kind, data = await asyncio.to_thread(out.get, True, HEARTBEAT_S)
                except _queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if kind is _END:
                    break
                if kind == "answer":
                    answer = data
                elif kind == "error":
                    failure = str(data.get("error_code"))
                yield _sse(kind, data)
            yield _sse("done", {})
        finally:
            cancel.set()                                   # a disconnect (or any exit) stops the run
            with _LOCK:
                if _RUNNING.get(who) is cancel:
                    del _RUNNING[who]
            try:
                from polymath_shared.db import tx
                from polymath_shared.query_receipts import record_query_receipt
                meta = {"route": "research/deep", "model": synth,
                        "deep_research": ((answer or {}).get("result") or {}).get("meta", {}).get("deep_research")}
                record_query_receipt(tx, kind="deep_research", question=req.question, req=req, scope_corpora=libraries,
                                     scope_kind="explicit", wall_ms=(time.monotonic() - t0) * 1000.0,
                                     out={"meta": meta}, error=failure)
            except Exception as exc:  # noqa: BLE001 — receipts never break a stream
                log.warning("deep research receipt not written: %s", type(exc).__name__)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
