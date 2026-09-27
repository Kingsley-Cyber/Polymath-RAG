"""DEEP-RESEARCH-MODE-V1 DR2 — `POST /research/deep`: the breadth × depth research loop (shared/polymath_shared/deep_research)
over THIS request's libraries, streamed on the chat's own frame types — `phase` (progress), `token` (the report), `answer`
(kind "deep": the report, its resolved citations and the run's counts), `error`, `done` — plus SSE comment heartbeats so a
proxy never sees a silent stream.

Scope: the libraries are resolved and checked once, here, for the caller (a friend only reaches libraries they may read);
every search then names exactly those libraries AND runs under the caller's principal, so no step can widen the scope (K1).
The planning and extraction calls use the chat compiler's governed lanes (per-lane limiter); the report is written by the
composer's model, like a chat answer. One deep run at a time per person. A client that disconnects cancels the run.

Research moves (DR6, plan §10; on unless the request or POLYMATH_DEEP_RESEARCH_MOVES=0 turns them off): each planned search
is broad / deep / adjacent / inverse and goes to the search built for it (`move_request`), and the reranker drops a planned
search that misses the question before it runs (`_gate_port`, fail-open). The request's `mode` stays the base mode.

The research experience (DR7, plan §11.3): `POST /research/deep/plan` makes the plan card (the level-1 plan alone, one LLM
call); the run takes the confirmed `plan` in place of its level-1 planner; `POST /research/deep/finish` ends the caller's run
early and still writes the report; with moves, a `coverage` frame follows each level; the answer carries the deterministic
evidence model (`report_model`) and the sentence audit of the report (`audit`)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue as _queue
import threading
import time
from collections.abc import Sequence
from dataclasses import replace
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
MOVES_ENV = "POLYMATH_DEEP_RESEARCH_MOVES"   # "0" forces moves off for every request
#: §10.1: the canonical §33 intent a move's search runs under (the reserved surfaces DR0 named reach deep research here)
MOVE_INTENT = {"adjacent": "RELATIONSHIP", "inverse": "COMPARISON"}
GATE_ORIGIN = "DEEP_RESEARCH"                # the probe gate's origin for a deep research query (§10.4)
PLAN_QUERY_CHARS, PLAN_GOAL_CHARS = (3, 300), 2000   # a goal: at most the question's own length (the report prompt holds it)
_RUNNING: dict[str, threading.Event] = {}     # the caller's run: its cancel event
_FINISH: dict[str, threading.Event] = {}      # the caller's run: its Finish-now event (DR7c)
_LOCK = threading.Lock()
_END = object()


class DeepPlanGoal(BaseModel):
    """One goal of a confirmed plan (§11.3): its query is searched at level 1 with its move."""
    goal: str = ""
    query: str
    move: str = "broad"


class DeepResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    preset: str = "standard"                 # quick 3×1 · standard 3×2 · thorough 4×2
    mode: str = "HYBRID"                     # the retrieval mode every search uses (with moves: the base mode)
    synthesizer: str | None = None           # the composer's model writes the report (like chat)
    moves: bool = True                       # DR6 research moves (§10); POLYMATH_DEEP_RESEARCH_MOVES=0 forces them off
    plan: list[DeepPlanGoal] | None = None   # DR7a: the confirmed plan; it replaces the level-1 planner call


class DeepPlanRequest(BaseModel):
    """`POST /research/deep/plan` (§11.3). `mode` is accepted for the same shape as a run; planning searches nothing."""
    question: str = Field(min_length=3, max_length=2000)
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    preset: str = "standard"
    mode: str = "HYBRID"
    moves: bool = True


def moves_enabled(req: DeepResearchRequest | DeepPlanRequest) -> bool:
    return bool(req.moves) and os.environ.get(MOVES_ENV, "1").strip().lower() not in ("0", "false", "off", "no")


def confirmed_plan(req: DeepResearchRequest, breadth: int) -> tuple[tuple[str, str, str], ...] | None:
    """The request's confirmed plan as (goal, query, move) items, or None. §11.3: at most 2 × breadth goals, each query 3-300
    characters (spaces trimmed), each move in MOVES; also refused: an empty plan (the page's own rule) and a goal longer than
    the question may be. Any of these is one typed 422 PLAN_INVALID listing every problem. A repeated query is allowed, as
    the page allows it: every confirmed goal is searched."""
    if req.plan is None:
        return None
    problems = [] if req.plan else ["the plan has no goals"]
    if len(req.plan) > 2 * breadth:
        problems.append(f"at most {2 * breadth} goals for this preset, got {len(req.plan)}")
    lo, hi = PLAN_QUERY_CHARS
    for n, item in enumerate(req.plan, 1):
        query = item.query.strip()
        if not lo <= len(query) <= hi:
            problems.append(f"goal {n}: the query must be {lo}-{hi} characters")
        if item.move not in DR.MOVES:
            problems.append(f"goal {n}: the move must be one of {list(DR.MOVES)}")
        if len(item.goal) > PLAN_GOAL_CHARS:
            problems.append(f"goal {n}: the goal must be at most {PLAN_GOAL_CHARS} characters")
    if problems:
        raise HTTPException(422, {"error_code": "PLAN_INVALID", "message": "; ".join(problems)})
    return tuple((item.goal.strip(), item.query.strip(), item.move) for item in req.plan)


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


def _libraries(req: DeepResearchRequest | DeepPlanRequest) -> list[str]:
    from orchestrator.web_scope import require_corpora
    ids = [c for c in ([req.corpus_id] if req.corpus_id else []) + list(req.corpus_ids or []) if c]
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise HTTPException(422, {"error_code": "LIBRARY_REQUIRED", "message": "name at least one library"})
    require_corpora(ids)                     # a friend may only research libraries they can read
    return ids


def _build_rows(response: dict[str, Any], corpus_ids: list[str], limit: int, explore: bool = False) -> list[dict[str, Any]]:
    from orchestrator.api.evidence_rows import build_evidence_rows
    from polymath_shared.db import tx
    with tx() as conn:
        return build_evidence_rows(conn, response, corpus_ids, limit=limit, explore=explore)


def evidence_rows_of(out: dict[str, Any], corpus_ids: list[str], limit: int, *, explore: bool = False) -> list[dict[str, Any]]:
    """DR4: `/retrieve` builds `evidence_rows` only on the default lane; the engine modes (HYBRID, FAST, GRAPH, WILDCARD,
    GNN) answer with a flat `evidence` list and ignore `evidence: true`. Build the same rows from that list, in its order,
    the way chat does (`chat.attach_evidence_rows`), so a search in any mode feeds the research. `explore` (a broad move):
    the EXPLORE cap, 2 rows per document, interleaved, so the rows spread."""
    if out.get("evidence_rows"):
        return list(out["evidence_rows"])
    ids = list(dict.fromkeys(e["chunk_id"] for e in out.get("evidence") or [] if isinstance(e, dict) and e.get("chunk_id")))
    if not ids:
        return []
    return _build_rows({"child_evidence": [{"chunk_id": cid, "rerank_score": float(len(ids) - i)} for i, cid in enumerate(ids)],
                        "selected_documents": [], "graph_facts": []}, corpus_ids, limit, explore=explore)


def move_request(query: str, libraries: Sequence[str], mode: str, move: str | None = None,
                 anchor_docs: Sequence[str] = ()) -> tuple[Any, bool]:
    """(the `/retrieve` request, whether its rows take the EXPLORE cap) for one planned search (§10.1):
        broad     the base mode; rows with the EXPLORE cap (2 per document) so they spread
        deep      anchored: the default lane inside the anchor documents (DOCUMENT-SCOPED-RETRIEVE-V1); else the base mode
        adjacent  the base mode with intent RELATIONSHIP;  inverse  the base mode with intent COMPARISON
    The intent rides only a base mode whose v2 path honours it (HYBRID / GRAPH / WILDCARD); in FAST or GNN the move searches
    without it. `move` None (moves off) = DR4's request, field for field."""
    from orchestrator.api.retrieve import (
        INTENT_MODES,
        RetrieveRequest,
        retrieve_engine_flag,
    )
    base = {"query": query, "corpus_ids": list(libraries), "limit": ROWS_PER_SEARCH, "evidence": True}
    if move == "deep" and anchor_docs:
        return RetrieveRequest(**base, document_ids=list(anchor_docs)), False
    intent = MOVE_INTENT.get(move or "")
    if intent and mode in INTENT_MODES and retrieve_engine_flag() == "v2":
        return RetrieveRequest(**base, mode=mode, intent=intent), False
    return RetrieveRequest(**base, mode=mode), move == "broad"


def _retrieve_port(loop: asyncio.AbstractEventLoop, principal: str | None, mode: str, aliases: _Aliases):
    from orchestrator.api.retrieve import _retrieve_impl

    def retrieve(query: str, scope: Any, *, move: str | None = None, anchor_docs: Sequence[str] = ()) -> list[DR.Row]:
        req, explore = move_request(query, list(scope), mode, move, anchor_docs)

        async def call() -> dict:
            with principal_context.acting_as(principal):
                return await _retrieve_impl(req)
        out = asyncio.run_coroutine_threadsafe(call(), loop).result(timeout=PORT_TIMEOUT_S)
        rows = []
        for r in evidence_rows_of(out or {}, list(scope), ROWS_PER_SEARCH, explore=explore):
            text = str(r.get("text_clean") or r.get("text") or "").strip()
            if not r.get("id") or not text:
                continue
            rows.append(DR.Row(cid=aliases.alias(r), text=text, source=str(r.get("source") or r.get("title") or ""),
                               score=float(r.get("score") or 0.0), doc_id=str(r.get("doc_id") or ""),
                               title=str(r.get("title") or "")))
        return rows[:ROWS_PER_SEARCH]
    return retrieve


def _gate_port(floor: float):
    """§10.4: the relevance gate. The reranker scores each planned search against the ORIGINAL question, through chat's
    probe gate (one bounded cross-encoder call, origin DEEP_RESEARCH). A judge error or timeout raises, so the engine keeps
    the searches and counts them (fail-open); a search the judge left unscored (reranker parked) comes back without a score."""
    from orchestrator.api import chat_retrieval
    from polymath_shared.probe_gate import gate_probes

    def gate(question: str, items: Sequence[tuple[str, str]]) -> dict[str, float]:
        _dropped, receipt = gate_probes(question, [(qid, GATE_ORIGIN, text) for qid, text in items],
                                        chat_retrieval._rerank_children, floor=floor, gated_origins=(GATE_ORIGIN,))
        if receipt.get("error"):
            raise RuntimeError(f"relevance gate: {receipt['error']}")
        return {qid: float(s["score"]) for qid, s in receipt["scores"].items()}
    return gate


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
        kwargs = {"model": model, "messages": messages, "stream": True, "timeout": 300, "max_tokens": _chat_max_tokens(),
                  **_litellm_credentials(model)}
        try:
            from polymath_shared.reasoning_policy import CHAT_SYNTHESIS, apply_litellm
            apply_litellm(kwargs, CHAT_SYNTHESIS, model)   # chat's thinking rule: DeepSeek v4 thinking on can answer nothing
        except Exception as exc:  # noqa: BLE001 — the overlay is additive, as in chat
            log.warning("deep research report: reasoning policy not applied: %s", type(exc).__name__)
        stream = litellm.completion(**kwargs)
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
                "level_done": "Finished a round", "stopped": "Research stopped",
                "gate": "Checked the planned searches against the question"}
#: engine event fields a phase frame carries (moves: `move` + `goal_id` on a search; `moves`, `goal_id` and, at level 1,
#: `goals` + `confirmed` on a plan; the gate's counts)
_PHASE_FIELDS = ("depth", "completed", "total", "new_learnings", "reason", "move", "moves", "scored", "dropped", "failed_open",
                 "goal_id", "goals", "confirmed", "user_kept")


def _phase(ev: dict[str, Any], t0: float) -> dict[str, Any]:
    stage = str(ev.get("stage") or "research")
    label = _STAGE_LABEL.get(stage, stage)
    if ev.get("query") and stage in ("retrieve", "extract"):
        label = f"{label}: {str(ev['query'])[:120]}"
    if stage == "level_done" and ev.get("new_learnings") is not None:
        label = f"{label}: {ev['new_learnings']} new findings"
    if stage == "stopped" and ev.get("reason"):
        label = f"{label} ({ev['reason']})"
    if stage == "gate" and ev.get("dropped"):
        label = f"{label}: {ev['dropped']} dropped as off the question"
    frame = {"stage": f"deep_{stage}", "label": label, "t": int((time.monotonic() - t0) * 1000),
             **{k: v for k, v in ev.items() if k in _PHASE_FIELDS}}
    if "move" in ev and ev.get("query"):
        frame["query"] = str(ev["query"])[:120]         # the rail labels a search by its move: "Broad · <query>"
        frame.update({k: ev[k] for k in ("rows", "status") if k in ev})   # DR7c's feed: passages, empty / error
    return frame


def _worker(req: DeepResearchRequest, libraries: list[str], synth: str, principal: str | None, loop: asyncio.AbstractEventLoop,
            out: _queue.Queue, cancel: threading.Event, finish: threading.Event | None = None,
            plan: tuple[tuple[str, str, str], ...] | None = None) -> None:
    """The run, on its own thread: research events, then the report, then the answer, then _END."""
    t0 = time.monotonic()
    try:
        aliases = _Aliases()
        moves = moves_enabled(req)
        config = DR.Config.preset(req.preset, score_floor=float("-inf"), moves=moves)

        def on_event(ev: dict[str, Any]) -> None:
            if ev.get("stage") == "coverage":             # DR7b (moves): after each level, the goals' meters in their own frame
                out.put(("coverage", {"goals": ev["goals"], "documents": ev["documents"], "passages": ev["passages"],
                                      "level": ev["depth"]}))
            else:
                out.put(("phase", _phase(ev, t0)))
        outcome = DR.run_research(req.question, tuple(libraries),
                                  retrieve=_retrieve_port(loop, principal, req.mode.upper(), aliases),
                                  complete=_complete_port(req.question), config=config, on_event=on_event, cancel=cancel,
                                  gate=_gate_port(config.gate_floor) if moves else None, finish=finish, plan=plan)
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
        if cancel.is_set():
            out.put(("error", {"error_code": "CANCELLED", "message": "the research was stopped"}))
            return
        if not text.strip():
            out.put(("error", {"error_code": "REPORT_EMPTY", "summary": summary,
                               "message": "the model returned an empty report; try again or pick another model"}))
            return
        valid, unknown = DR.validate_report_citations(text, outcome)
        # DR7b: the evidence model the page renders (never the model's tone), and which report sentences carry no valid cid
        summary["report_model"] = DR.evidence_model(outcome, intent=DR.question_intent(req.question),
                                                    evaluative=DR.is_evaluative(req.question),
                                                    preset=req.preset.strip().lower(), model=synth)
        summary["audit"] = DR.audit_report(text, outcome.evidence)
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
        shape = DR.Config.preset(req.preset)
    except ValueError as exc:
        raise HTTPException(422, {"error_code": "UNKNOWN_PRESET", "message": str(exc)}) from None
    plan = confirmed_plan(req, shape.breadth)
    who = principal or "owner"
    cancel, finish = threading.Event(), threading.Event()
    with _LOCK:
        if who in _RUNNING:
            raise HTTPException(409, {"error_code": "DEEP_RESEARCH_BUSY", "message": "one deep research run at a time; stop the other first"})
        _RUNNING[who] = cancel
        _FINISH[who] = finish

    async def events():
        loop = asyncio.get_running_loop()
        out: _queue.Queue = _queue.Queue()
        t0 = time.monotonic()
        answer: dict[str, Any] | None = None
        failure: str | None = None
        worker = threading.Thread(target=_worker, args=(req, libraries, synth, principal, loop, out, cancel, finish, plan),
                                  daemon=True, name="deep-research")
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
                if _FINISH.get(who) is finish:
                    del _FINISH[who]
            try:
                from polymath_shared.db import tx
                from polymath_shared.query_receipts import record_query_receipt
                meta = {"route": "research/deep", "model": synth, "deep_research": receipt_block(answer)}
                record_query_receipt(tx, kind="deep_research", question=req.question, req=req, scope_corpora=libraries,
                                     scope_kind="explicit", wall_ms=(time.monotonic() - t0) * 1000.0,
                                     out={"meta": meta}, error=failure)
            except Exception as exc:  # noqa: BLE001 — receipts never break a stream
                log.warning("deep research receipt not written: %s", type(exc).__name__)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def receipt_block(answer: dict[str, Any] | None) -> dict[str, Any] | None:
    """The receipt's `deep_research`: the answer's run counts and audit. The evidence model's texts stay out, only its counts
    go in (`report_model_counts`): the receipt's meta is capped at 64 KB, and past the cap the whole meta is lost."""
    block = ((answer or {}).get("result") or {}).get("meta", {}).get("deep_research")
    if not isinstance(block, dict) or "report_model" not in block:
        return block
    model = block["report_model"]
    findings = [f for goal in model["goals"] for f in goal["findings"]]
    return {**{k: v for k, v in block.items() if k != "report_model"},
            "report_model_counts": {"goals": len(model["goals"]), "findings": len(findings),
                                    "confidence": {c: sum(1 for f in findings if f["confidence"] == c)
                                                   for c in ("strong", "single_source", "contested")},
                                    "counter": len(model["counter"]), "open_questions": len(model["open_questions"]),
                                    "sources": len(model["sources"])}}


@router.post("/research/deep/plan")
async def deep_research_plan(req: DeepPlanRequest) -> dict[str, Any]:
    """DR7a (§11.3): the plan card. The run's level-1 plan made alone, in ONE planner call on the research lanes, after the
    same library and preset checks as a run, with the question's type and an estimate of the run it would start. Not part of
    the one-run lock: a person may plan while a run streams. A failed or empty plan is a 502 (PLAN_FAILED / PLAN_EMPTY):
    the page can still start the run without one."""
    libraries = _libraries(req)
    try:
        config = DR.Config.preset(req.preset, moves=moves_enabled(req))
    except ValueError as exc:
        raise HTTPException(422, {"error_code": "UNKNOWN_PRESET", "message": str(exc)}) from None
    complete = _complete_port(req.question)
    try:
        draft = await asyncio.to_thread(DR.plan_goals, req.question, complete=complete, config=config)
    except Exception as exc:  # noqa: BLE001 — the card says planning failed; the class only, never the message
        log.warning("deep research plan failed: %s", type(exc).__name__)
        raise HTTPException(502, {"error_code": "PLAN_FAILED",
                                  "message": f"the planner failed ({type(exc).__name__}); start without a plan"}) from None
    if not draft.goals:
        raise HTTPException(502, {"error_code": "PLAN_EMPTY", "message": "the planner wrote no usable search; start without a plan"})
    return {"intent": DR.question_intent(req.question), "evaluative": DR.is_evaluative(req.question),
            "preset": req.preset.strip().lower(),
            "goals": [{"id": g.id, "goal": g.goal, "query": g.query, "move": g.move} for g in draft.goals],
            "estimate": DR.estimate(replace(config, first_width=len(draft.goals)), planned=True),
            "libraries": libraries, "moves": config.moves}


@router.post("/research/deep/finish", status_code=202)
async def deep_research_finish() -> dict[str, Any]:
    """DR7c (§11.3): Finish now (the page posts `{}`). The caller's run starts nothing new, lets the calls in flight finish,
    and writes the report from what it found (stop reason `finished_early`): 202 `{"finishing": true}`. 404
    NO_DEEP_RESEARCH_RUN when the caller has no run."""
    who = principal_context.current() or "owner"
    with _LOCK:
        finish = _FINISH.get(who)
    if finish is None:
        raise HTTPException(404, {"error_code": "NO_DEEP_RESEARCH_RUN", "message": "you have no deep research run to finish"})
    finish.set()
    return {"finishing": True}
