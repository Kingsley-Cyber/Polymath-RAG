"""CHAT-RETRIEVAL-V2 route (plan §3.14 / §4 P1.a; P1.d CONCURRENCY-DEADLINES-V1
§3.16): the chat path's HYBRID retrieval on the CANDIDATE-RETRIEVAL-V1 engine.

    one readiness check → lane C STARTS (BM25 for the primary and every
    subquery needs only the compiled text) → ONE embedding (all distinct
    texts, one call) → lanes A / B concurrently through the SHARED
    FastSearcher filters, lane C joined from its head start → union with
    provenance → exactly ONE bounded rerank under a deadline → final evidence

Wall-clock budgets (`CandidateBudget`): the embedding is a hard dependency
(its breach is receipted, never dropped); a core lane past `lane_deadline_s`
is dropped and receipted `<lane>_timeout`; a judge past `rerank_deadline_s`
yields fusion order and `rerank_timeout`. Everything lands in
`meta.degraded`; per-stage `latency_ms` rides the trace.

Returns the same dict shape as `hybrid_fast_retrieve` so the stream
handler, /chat, the bundle assembler and the funnel consume it unchanged;
`meta.plan_version` / `trace.plan` say `chat-retrieval-v2`. /retrieve,
/ask and TRAIL keep `hybrid-retrieval-v1` (rollback boundary: the
`POLYMATH_CHAT_RETRIEVAL=v1` flag or a per-request `retrieval: "v1"`).

P1.e — MODE-COMPOSITION-V1 (§3.15, §3.18, §3.19): the chat modes are
compositions of the same primitives, owned by `chat_retrieve_mode`:

    VECTOR (FAST)   A + B
    HYBRID          A + B + C                      (the default)
    GRAPH           HYBRID → bounded G over the FINAL evidence
                    (≤ 8 seeds, ≤ 2 when the plan says the question is
                    not relational; hop-1; ≤ 20 facts; fail-open)
    WILDCARD        HYBRID ∥ W — the latent sweep joins the per-turn pool
                    the moment the one embedding returns (same vector, no
                    second call); baseline exclusion + validation wait for
                    the final evidence; ≤ 3 bridges, never in the evidence
                    list; bounded by `wildcard_deadline_s`

The primary vector reaches the graph seeds and the sweep through the
`on_context` seam of `chat_retrieve_v2` (the immutable SearchContext +
the turn's pool) — never through the result dict.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import CancelledError, Executor, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from typing import Callable, Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from polymath_shared.candidate_engine import (
    CANDIDATE_ENGINE_VERSION,
    CHAT_RETRIEVAL_PLAN_VERSION,
    CONCURRENCY_CONTRACT,
    LANE_A,
    LANE_B,
    LANE_C,
    LANES,
    CandidateBudget,
    SearchContext,
    SubQuery,
    retrieve_candidates,
    select_evidence,
    shape_budget,
    sparse_vector_for,
)
from polymath_shared.divergent import DIVERGENT_DEFAULT_PLAN, divergent_finish, divergent_sweep
#: P1.e: the finish stops STARTING validations at the frontier deadline; a validation already in flight may overrun by
#: at most one reranker call — the route waits this bounded grace for the partial result instead of abandoning it.
WILDCARD_FINISH_GRACE_S = 1.5
from polymath_shared.retrieval_modes import (
    GRAPH_DEFINITIONAL_MAX_SEEDS,
    GRAPH_MAX_FACTS,
    GRAPH_MAX_SEEDS,
    MODE_FAST,
    MODE_GRAPH,
    MODE_HYBRID,
    MODE_VECTOR,
    MODE_WILDCARD,
)
from polymath_shared.settings import get_settings

from orchestrator.api.fast import (
    _RERANK_DEGRADED,
    FastSearcher,
    _begin_retrieval,
    _corpus_collections,
    _embed_queries,
    _ensure_fast_ready,
    _neighbor_lookup,
    _presentation_joins,
    _region_lookup,
    _rerank_children,
    degradations,
    entity_card_probe,
)
from orchestrator.api.graph import _selected_surfaces
from orchestrator.api.retrieve import graph_expand_or_502

_FLAG_ENV = "POLYMATH_CHAT_RETRIEVAL"        # v1 | v2 (default v2 after the P1.a gate)


def chat_retrieval_flag(override: str | None = None) -> str:
    """v1 | v2 | v2-single (v2 with the compiled subqueries ignored — A/B only)."""
    v = (override or os.environ.get(_FLAG_ENV, "v2") or "v2").strip().lower()
    return v if v in ("v1", "v2", "v2-single") else "v2"


#: env-tunable knobs on the one budget authority, POLYMATH_CHAT_<NAME> (measurement only; the defaults are the contract)
_INT_KNOBS = ("rerank_max", "synthesis_max", "global_dense_k", "global_sparse_k", "merged_candidate_max", "max_workers",
              "latent_enabled", "latent_max_parents", "latent_children_per_parent", "latent_budget_ms",   # B12 lane D
              "hierarchy_route_documents",                                                              # SECTION-ROUTING-V1
              # EVIDENCE-DIET-V1 step 3: POLYMATH_CHAT_RERANK_ROUND_ROBIN (0/1), POLYMATH_CHAT_RERANK_DOC_CAP, POLYMATH_CHAT_RERANK_MAX_FAIR
              "rerank_round_robin", "rerank_doc_cap", "rerank_max_fair")
_FLOAT_KNOBS = ("embed_deadline_s", "lane_deadline_s", "rerank_deadline_s",     # P1.d wall-clock budgets
                "wildcard_deadline_s",                                            # P1.e frontier budget
                "wildcard_finish_budget_s", "wildcard_unverified_fill_s")        # B12 finish budget + unverified fill


def default_budget() -> CandidateBudget:
    b = CandidateBudget()
    over = {}
    for name, cast in [(n, int) for n in _INT_KNOBS] + [(n, float) for n in _FLOAT_KNOBS]:
        raw = os.environ.get(f"POLYMATH_CHAT_{name.upper()}")
        if raw:
            try:
                over[name] = cast(raw)
            except ValueError:
                pass
    return replace(b, **over) if over else b


def chat_retrieve_v2(query: str, corpus_id: str, *, exact_terms: tuple[str, ...] = (),
                     budget: Optional[CandidateBudget] = None, query_id: str = "q0",
                     subqueries: tuple = (), lanes: Optional[tuple] = None,
                     on_context: Optional[Callable[[SearchContext, Executor], None]] = None) -> dict:
    """`subqueries`: (id, type, text, weight) tuples from the compiled plan (non-PRIMARY);
    they run lanes B + C on their own vectors (one batched embedding call for all texts).
    `lanes` (P1.d/P1.e, evaluation and mode composition): restrict the engine to these lane
    names — VECTOR = (HIERARCHICAL_ROUTE, GLOBAL_DENSE_CHILD), HYBRID = all three (default).
    `on_context` (P1.e): called ONCE, in this thread, with the immutable SearchContext (the
    primary vector, the corpus's hidden generations, …) and the turn's pool — right after the
    embedding returned and before the lanes are submitted. The mode compositions take the
    primary vector here (graph entity-card seeds, the wildcard sweep submitted to the same
    pool); it must not raise. None (the default) changes nothing."""
    _begin_retrieval()
    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "HYBRID requires an explicit corpus_id (authorized corpus scope)"})
    if lanes:
        unknown = [str(x) for x in lanes if x not in LANES]
        if unknown:
            raise HTTPException(status_code=422, detail={
                "error_code": "unknown_lane", "message": f"unknown retrieval lane(s) {unknown}; known: {list(LANES)}"})
    _ensure_fast_ready(corpus_id)
    collections = _corpus_collections([corpus_id])
    collection = collections[corpus_id]
    budget = shape_budget(query, budget or default_budget())          # §3.21 #14: shape on the resolved text
    if lanes:
        budget = replace(budget, lanes=tuple(x for x in LANES if x in set(lanes)))   # canonical lane order
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable", "message": f"qdrant unavailable: {type(exc).__name__}"}) from exc
    t_all = time.perf_counter()
    extra_degraded: list[dict] = []
    prestart_ms: dict[str, float] = {}          # each key written once, by the thread that ran that lane
    judge_ms: dict[str, float] = {}
    # ONE bounded pool per turn, shared by the pre-started sparse lanes, the engine's lanes and the judge.
    pool = ThreadPoolExecutor(max_workers=max(1, int(budget.max_workers)), thread_name_prefix="chat-lanes")
    try:
        # §3.21 #1: built WITHOUT the query → no bm25 companion probe beside the dense lanes;
        # lane C is the one sparse search of the turn.
        searcher = FastSearcher(client, collections)
        hidden = tuple(searcher._hidden_for(corpus_id) or ())      # warm the generation cache ONCE, before any lane thread reads it
        sub_specs = [tuple(x) for x in (subqueries or ())][: budget.max_subqueries]
        texts = [query] + [t for (_, _, t, _) in sub_specs if t and t != query]
        distinct = list(dict.fromkeys(texts))
        sparse_q, sparse_rule = None, "raw"
        try:
            sparse_q, sparse_rule = sparse_vector_for(query, exact_terms)   # exact terms alone when present
        except Exception:  # noqa: BLE001 — lane C degrades in the engine
            sparse_q = None
        sub_sparse: dict[str, tuple] = {}                                    # subquery sparse queries need no vector either
        for (sid, _stype, stext, _sweight) in sub_specs:
            if stext and stext != query:
                sub_sparse[str(sid)] = sparse_vector_for(stext, ())

        def dense_search(kind: str, top_k: int, extra: dict | None = None, qvec=None) -> list[dict]:
            filters = {"representation_kind": kind, "corpus_id": corpus_id}
            if extra:
                filters.update(extra)
            return searcher._search(collection, list(qvec if qvec is not None else vecs[query]), filters, limit=top_k)

        def latent_search(_collection: str, v, filters: dict) -> list[dict]:
            # B12 lane D: the latent kinds live in the same collection; `latent_rescue_parents` passes the kind + corpus
            return searcher._search(collection, list(v), dict(filters), limit=max(budget.latent_abstraction_top_k, budget.latent_transfer_top_k))

        def sparse_search(top_k: int, sparse_query=None) -> list[dict]:
            return searcher.sparse_search(collection, sparse_query if sparse_query is not None else sparse_q,
                                          {"representation_kind": "routing_child", "corpus_id": corpus_id}, limit=top_k)

        def _prestart(name: str, top_k: int, sparse_query) -> list[dict]:
            t0 = time.perf_counter()
            try:
                return sparse_search(top_k, sparse_query)
            finally:
                prestart_ms[name] = round((time.perf_counter() - t0) * 1000, 1)

        # STAGE 2 head start (§3.16): BM25 needs no vector — lane C for the primary and for every subquery is
        # submitted BEFORE the embedding call and handed to the engine pre-started (it never searches them again).
        prestarted: dict = {}
        if LANE_C in budget.lanes:
            if sparse_q is not None:
                prestarted["global_sparse_child"] = pool.submit(_prestart, "global_sparse_child", budget.global_sparse_k, sparse_q)
            for sid, (sv, _rule) in sub_sparse.items():
                if sv is not None:
                    prestarted[f"sub_{sid}_sparse"] = pool.submit(_prestart, f"sub_{sid}_sparse", budget.subquery_sparse_k, sv)
        # STAGE 1: ONE embedding for all distinct texts. A hard dependency (no vector, no dense lane), so the turn
        # waits for it; exceeding `embed_deadline_s` is receipted, never a dropped stage.
        t0 = time.perf_counter()
        vecs = dict(zip(distinct, _embed_queries(distinct)))               # ONE call, one vector per distinct text
        qvec = vecs[query]
        embed_ms = round((time.perf_counter() - t0) * 1000, 1)
        if embed_ms > budget.embed_deadline_s * 1000:
            extra_degraded.append({"component": "embed_deadline",
                                   "effect": "dense lanes started late (the embedding is a hard dependency; the turn waited for it)",
                                   "reason": f"embedding took {embed_ms:.0f} ms; embed_deadline_s={budget.embed_deadline_s:g}"})
        subs: list[SubQuery] = []
        for (sid, stype, stext, sweight) in sub_specs:
            if not stext or stext == query:
                continue
            sv, srule = sub_sparse[str(sid)]
            subs.append(SubQuery(query_id=str(sid), qtype=str(stype), text=str(stext), weight=float(sweight or 1.0),
                                 qvec=tuple(vecs[stext]), sparse_query=sv, sparse_rule=srule))
        ctx = SearchContext(query=query, corpus_id=corpus_id, collection=collection, qvec=tuple(qvec),
                            sparse_query=sparse_q, exact_terms=tuple(exact_terms or ()),
                            hidden_generations=hidden, query_id=query_id, sparse_rule=sparse_rule)
        if on_context is not None:
            on_context(ctx, pool)          # P1.e: the vector exists — a frontier may start beside the dense lanes
        # STAGES 2–3: concurrent lanes under `lane_deadline_s` → union with provenance (the engine)
        result = retrieve_candidates(ctx, budget, dense_search=dense_search, sparse_search=sparse_search, latent_search=latent_search,
                                     region_lookup=_region_lookup, subqueries=subs, executor=pool, prestarted=prestarted)

        # STAGE 4: exactly ONE judge call per turn, under `rerank_deadline_s`. Past it the turn proceeds in
        # fusion order (a complete, correct answer — the judge only reorders) and says so; the late sidecar
        # call is not awaited (it finishes in the background).
        def _judge_with_deadline(q: str, rows: list[dict]) -> list[dict]:
            def _judge():
                out = _rerank_children(q, rows)
                return out, _RERANK_DEGRADED.get()      # a parked sidecar is noted in the WORKER's context (ContextVar)
            t1 = time.perf_counter()
            fut = pool.submit(_judge)
            try:
                out, note = fut.result(timeout=budget.rerank_deadline_s)
            except FutureTimeout:
                extra_degraded.append({"component": "rerank_timeout",
                                       "effect": "results ordered by fusion (the judge missed its deadline); same candidate set, same recall",
                                       "reason": f"no judgement after {budget.rerank_deadline_s:g} s — late result ignored"})
                return rows
            finally:
                judge_ms["rerank"] = round((time.perf_counter() - t1) * 1000, 1)
            if note:
                _RERANK_DEGRADED.set(note)              # carry it into this request's context so degradations() reports it
            return out

        t2 = time.perf_counter()
        final, sel = select_evidence(result, budget, rerank_children=_judge_with_deadline, neighbor_lookup=_neighbor_lookup)
        select_ms = round((time.perf_counter() - t2) * 1000, 1)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)   # a late lane or judge never holds the turn; queued work is dropped
        client.close()
    total_ms = round((time.perf_counter() - t_all) * 1000, 1)

    # per-stage receipts (P1.d): embed · sparse_prestart · each lane · union · rerank · compose · total
    # (`rerank_select` = the whole selection stage, kept for chat_baseline / chat_m_replay)
    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    engine_t = dict(result.timings_ms)
    rerank_only = judge_ms.get("rerank", 0.0)
    latency_ms.update({
        "embed": embed_ms, "embedded_texts": len(distinct),
        "sparse_prestart": prestart_ms.get("global_sparse_child"),      # lane C's own time, overlapped with the embedding
        "lanes": engine_t.get("core_wall"), "lanes_primary_batch": engine_t.get("lanes_wall"), "union": engine_t.get("union"),
        "rerank": rerank_only, "compose": round(select_ms - rerank_only, 1), "rerank_select": select_ms,
        "total": total_ms,
        **{f"lane_{k}": v for k, v in engine_t.items() if k not in ("core_wall", "lanes_wall", "union")},
    })
    _p = _presentation_joins([c.chunk_id for c in final], [c.doc_id for c in final])
    trace = {**result.trace, **sel, "latency_ms": latency_ms}
    rows = []
    for c in final:
        r = c.to_row()
        r.update({"g3_score": c.rerank_score, "locator": f"chunk:{c.chunk_id}",
                  "source_name": c.source_name or _p.get(c.doc_id, {}).get("source_name", ""),
                  "title": _p.get(c.chunk_id, {}).get("title", ""), "heading_path": _p.get(c.chunk_id, {}).get("heading_path", ""),
                  "human_locator": _p.get(c.chunk_id, {}).get("human_locator", ""), "text": (c.text or "")[:240]})
        rows.append(r)
    return {
        "query": query,
        "meta": {
            "mode": MODE_HYBRID, "plan_version": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION,
            "corpus_id": corpus_id, "rrf_k": budget.rrf_k, "budget": budget.to_dict(),
            "lanes": list(budget.lanes),
            "lexical_enabled": LANE_C in budget.lanes, "mmr": "NOT_IN_V2",
            "deadlines": {"contract": CONCURRENCY_CONTRACT, "embed_deadline_s": budget.embed_deadline_s,
                          "lane_deadline_s": budget.lane_deadline_s, "rerank_deadline_s": budget.rerank_deadline_s,
                          "max_workers": max(1, int(budget.max_workers))},
            "selected_document_count": len(result.selected_documents), "selected_section_count": len(result.selected_sections),
            "evidence_count": len(rows), "candidates": len(result.union), "multi_lane": trace.get("multi_lane"),
            "subqueries": trace.get("subqueries"), "weak_aspects": trace.get("weak_aspects"), "weak_reasons": trace.get("weak_reasons"),
            "aspect_seated": trace.get("aspect_seated"), "aspect_best": trace.get("aspect_best"), "final_detail": trace.get("final_detail"),
            "composition": trace.get("composition"),
            "aspects": {qid: {**a, "final": (trace.get("aspect_final") or {}).get(qid, 0), "prefix": (trace.get("aspect_prefix") or {}).get(qid),
                              "best": (trace.get("aspect_best") or {}).get(qid), "weak": (trace.get("weak_reasons") or {}).get(qid)}
                        for qid, a in (trace.get("aspects") or {}).items()},
            # reranker / sparse notes (ContextVar), the engine's lane receipts (sparse outage, `<lane>_timeout`),
            # then the route's own (`embed_deadline`, `rerank_timeout`)
            "degraded": degradations() + list(result.degraded) + extra_degraded,
            # lane liveness for v2 = the per-lane sizes + degradations above (the v1 liveness
            # table is keyed on rescue lanes that do not exist here)
            "liveness": None,
            "latent": None,
        },
        "selected_documents": [
            {"doc_id": d.doc_id, "corpus_id": d.corpus_id, "aggregate_rank": d.aggregate_rank,
             "aggregate_score": round(d.aggregate_score, 6),
             "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
             "representation_kinds_present": d.representation_kinds_present,
             "document_summary": ({"summary_id": d.document_summary_hits[0].summary_id, "text": d.document_summary_hits[0].text}
                                  if d.document_summary_hits else None),
             "why": {"best_document_summary_rank": d.best_document_summary_rank, "best_section_summary_rank": d.best_section_summary_rank,
                     "best_child_rank": d.best_child_rank, "best_lexical_rank": d.best_lexical_rank}}
            for d in result.selected_documents],
        "selected_sections": [
            {"doc_id": s["doc_id"], "parent_id": s["parent_id"], "summary_id": s["summary_id"], "source_name": s["source_name"],
             "best_section_rank": s["best_section_rank"], "from": sorted(set(s["from"]))}
            for s in result.selected_sections],
        "evidence": rows,
        "trace": trace,
    }


# ---------------------------------------------------------------------------------------------------------
# P1.e — MODE-COMPOSITION-V1 (§3.15, §3.18, §3.19, §3.21 #5–#9/#16): modes are compositions of the primitives
# ---------------------------------------------------------------------------------------------------------
MODE_COMPOSITION_CONTRACT = "mode-composition-v1"

#: mode → the engine lanes it enables (the ONLY thing a mode changes inside the core)
MODE_LANES: dict[str, tuple[str, ...]] = {
    MODE_VECTOR: (LANE_A, LANE_B),
    MODE_FAST: (LANE_A, LANE_B),
    MODE_HYBRID: LANES,
    MODE_GRAPH: LANES,
    MODE_WILDCARD: LANES,
}


def chat_retrieve_mode(mode: str, query: str, corpus_id: str, *, graph_useful: bool = True, **kw) -> dict:
    """One engine, four compositions (§3.15). VECTOR / FAST = A + B; HYBRID = A + B + C; GRAPH = HYBRID +
    bounded hop-1 over the FINAL evidence (`_attach_graph`; global winners seed exactly like hierarchy
    winners, §3.21 #5–#6; the primary vector is reused for the entity-card seeds, #7); WILDCARD = HYBRID ∥
    the latent sweep (`_retrieve_wildcard`, §3.19). `graph_useful` is the compiled plan's relational
    verdict (GRAPH only): False keeps the expansion definitional (≤ GRAPH_DEFINITIONAL_MAX_SEEDS seeds).
    `kw` is forwarded to `chat_retrieve_v2` (exact_terms, subqueries, budget, query_id); the lane set and
    the `on_context` seam belong to the composition. HYBRID is byte-for-byte `chat_retrieve_v2`."""
    m = (mode or MODE_HYBRID).strip().upper()
    if m not in MODE_LANES:
        raise HTTPException(status_code=422, detail={
            "error_code": "unknown_mode",
            "message": f"unknown chat retrieval mode {mode!r}; compositions: {sorted(set(MODE_LANES))}"})
    for reserved in ("lanes", "on_context"):
        if reserved in kw:
            raise TypeError(f"chat_retrieve_mode owns {reserved!r}; select a mode instead")
    lanes = MODE_LANES[m]
    if m == MODE_WILDCARD:
        return _retrieve_wildcard(query, corpus_id, lanes=lanes, **kw)
    if m == MODE_GRAPH:
        seen: dict = {}

        def _capture(ctx: SearchContext, _pool: Executor) -> None:
            seen["qvec"] = ctx.qvec            # the ONE primary vector, handed on explicitly (§3.21 #7)

        out = chat_retrieve_v2(query, corpus_id, lanes=lanes, on_context=_capture, **kw)
        out["meta"]["mode"] = MODE_GRAPH
        _attach_graph(out, query, corpus_id, qvec=seen.get("qvec"), graph_useful=graph_useful)
        return out
    out = chat_retrieve_v2(query, corpus_id, lanes=lanes, **kw)
    out["meta"]["mode"] = MODE_VECTOR if m in (MODE_VECTOR, MODE_FAST) else MODE_HYBRID
    return out


def _attach_graph(out: dict, query: str, corpus_id: str, *, qvec, graph_useful: bool) -> None:
    """Bounded G after evidence (§3.18): seeds are the FINAL evidence's surfaces (query terms first, then
    every final chunk — a GLOBAL_DENSE_CHILD winner seeds like a hierarchy winner) plus entity-card seeds
    resolved with the primary vector (no second embedding); the D2 resolver keeps card seeds first and caps
    the resolved seeds at `max_seeds` (8, or GRAPH_DEFINITIONAL_MAX_SEEDS when the plan says the question is
    not relational); hop-1; ≤ GRAPH_MAX_FACTS facts. Fail-open: an expansion failure leaves the HYBRID
    answer intact and is receipted as `graph_degraded` (meta.graph_degraded + meta.degraded)."""
    meta, trace = out["meta"], out["trace"]
    evidence = out.get("evidence") or []
    seeds_max = GRAPH_MAX_SEEDS if graph_useful else GRAPH_DEFINITIONAL_MAX_SEEDS
    t0 = time.perf_counter()
    surfaces = list(_selected_surfaces(query, evidence))           # ≤ 12 candidate surfaces; the resolver caps the seeds
    card_seed_ids: list[str] = []
    card_probe = "skipped:no_vector"
    if qvec is not None:
        try:
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=30)
            try:
                cards = entity_card_probe(client, _corpus_collections([corpus_id]), corpus_id, query, list(qvec), limit=seeds_max)
            finally:
                client.close()
            card_seed_ids = [c["entity_id"] for c in cards if c.get("entity_id")][:seeds_max]
            card_probe = "ok"
        except Exception as exc:  # noqa: BLE001 — seeding is fail-open; surfaces still seed
            card_seed_ids, card_probe = [], f"degraded:{type(exc).__name__}"
    facts: list[dict] = []
    degraded_reason: Optional[str] = None
    try:
        facts = list(graph_expand_or_502(surfaces, [corpus_id], [c["chunk_id"] for c in evidence],
                                         seed_entity_ids=card_seed_ids, max_seeds=seeds_max) or [])[:GRAPH_MAX_FACTS]
    except HTTPException as exc:
        d = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        degraded_reason = f"{d.get('error_code') or 'http_' + str(exc.status_code)}: {str(d.get('message') or '')[:160]}"
    except Exception as exc:  # noqa: BLE001 — the graph is a bounded optional stage, never the answer
        degraded_reason = f"{type(exc).__name__}: {str(exc)[:160]}"
    graph_ms = round((time.perf_counter() - t0) * 1000, 1)
    out["graph_relationships"] = [
        {"fact_id": f["fact_id"], "predicate": f["predicate"], "subject_id": f.get("subject_id"), "subject": f["subject"],
         "object_id": f.get("object_id"), "object": f["object"]}
        for f in facts]
    meta["graph_bounds"] = {"max_seeds": seeds_max, "max_facts": GRAPH_MAX_FACTS, "graph_useful": bool(graph_useful),
                            "hops": 1, "contract": MODE_COMPOSITION_CONTRACT}
    meta["graph_fact_count"] = len(facts)
    meta["graph_seeds"] = {"surfaces": len(surfaces), "cards": len(card_seed_ids), "max_seeds": seeds_max, "card_probe": card_probe}
    meta["graph_degraded"] = degraded_reason
    if degraded_reason:
        meta["degraded"] = list(meta.get("degraded") or []) + [{
            "component": "graph_degraded",
            "effect": "no graph relationships this turn; the HYBRID evidence stands",
            "reason": degraded_reason}]
    trace["graph_seed_surfaces"] = surfaces
    trace["graph_seed_cards"] = list(card_seed_ids)
    trace.setdefault("latency_ms", {})["graph"] = graph_ms


def _unverified_bridges(slots: list, *, children_of, baseline: dict, quota: int, fill_deadline: float, plan, qtoks) -> list[dict]:
    """B12: bridges for parents the finish budget never reached — the sweep's own ranking (hop1), the parent's best
    routing child fetched WITHOUT the judge (one Qdrant call each, under `fill_deadline`), `verified: False`,
    `source_support: None`. Never a chunk already in the evidence; never more than `quota`; fail-open per parent."""
    out: list[dict] = []
    obvious_parents = set(baseline.get("parent_ids") or ()); obvious_chunks = set(baseline.get("chunk_ids") or ()); obvious_docs = set(baseline.get("doc_ids") or ())
    for slot in sorted(slots, key=lambda x: (-float(x.get("hop1") or 0.0), str(x.get("parent_id")))):
        if len(out) >= quota or time.perf_counter() > fill_deadline:
            break
        if slot.get("parent_id") in obvious_parents:
            continue
        try:
            rows = children_of(slot["parent_id"]) or []
        except Exception:  # noqa: BLE001 — fail-open per parent
            rows = []
        kids = [(x.get("payload") or {}) for x in rows]
        kids = [k for k in kids if (k.get("text") or "").strip() and k.get("chunk_id") not in obvious_chunks]
        if not kids:
            continue
        best = kids[0]
        overlap = _jaccard_tokens(qtoks, (best.get("text") or ""))
        same_doc = slot.get("doc_id") in obvious_docs
        novelty = plan.borderline_novelty if overlap > plan.obvious_lexical_cap else (plan.borderline_novelty + (1.0 - plan.borderline_novelty) / 2 if same_doc else 1.0)
        principle = slot.get("abstraction") or slot.get("transfer") or ""
        out.append({"parent_id": slot["parent_id"], "doc_id": slot.get("doc_id") or "", "source_name": slot.get("source_name") or "",
                    "principle": principle, "why_it_may_transfer": (slot.get("transfer") if slot.get("abstraction") else "") or "",
                    "source_evidence": {"chunk_id": best.get("chunk_id"), "text": (best.get("text") or "")[:plan.source_text_chars],
                                        "source_name": best.get("source_name") or slot.get("source_name") or ""},
                    "scores": {"latent_alignment": round(float(slot.get("hop1") or 0.0), 4), "source_support": None, "novelty": novelty,
                               "value": round(float(slot.get("hop1") or 0.0) * novelty, 4)},
                    "channels": sorted(set(slot.get("channels") or [])), "verified": False})
    return out


def _jaccard_tokens(qtoks: set, text: str) -> float:
    toks = {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}
    return (len(qtoks & toks) / len(qtoks | toks)) if (qtoks or toks) else 0.0


def _retrieve_wildcard(query: str, corpus_id: str, *, lanes: tuple, budget: Optional[CandidateBudget] = None, **kw) -> dict:
    """WILDCARD = HYBRID core ∥ W (§3.19). The latent sweep (`divergent_sweep`) is submitted to the core's
    per-turn pool from `on_context` — i.e. the moment the ONE embedding returns, beside the dense lanes, with
    the same vector (no second embedding call, §3.21 #8) through a searcher of its own that reuses the core's
    hidden-generation guard. Only what needs the core result waits for it: the baseline = the FINAL evidence
    neighbourhood (doc_ids / parent_ids / chunk_ids, §3.21 #16) → `divergent_finish` (exclusion, two-hop
    validation, novelty). ≤ 3 bridges, none whose source chunk is in the evidence list; they ride the separate
    `wildcard` lane and never enter evidence ranking. The frontier is optional: everything after the core is
    bounded by `wildcard_deadline_s` (a late sweep or validation is abandoned, receipted `wildcard_timeout`)
    and every failure degrades to an empty lane with a reason in `meta.wildcard.degraded`. The vector is
    closed over once (`children_of(parent_id)` reads a fixed tuple) — no function-attribute state (#9)."""
    plan = DIVERGENT_DEFAULT_PLAN
    deadline_s = float((budget or default_budget()).wildcard_deadline_s)
    collections = _corpus_collections([corpus_id])
    coll = collections[corpus_id]
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable", "message": f"qdrant unavailable: {type(exc).__name__}"}) from exc
    t_turn = time.perf_counter()
    sweep: dict = {"future": None, "error": None, "searcher": None, "qvec": None, "started_ms": None}
    finish_pool: Optional[ThreadPoolExecutor] = None
    try:
        def _on_context(ctx: SearchContext, pool: Executor) -> None:
            searcher = FastSearcher(client, collections)                     # no query → no companion probe (§3.21 #1)
            searcher._hidden_cache = {corpus_id: list(ctx.hidden_generations)}   # the core's guard; no second DB read, no thread race
            qvec = tuple(ctx.qvec)

            def _latent_search(kind: str, v, top_k: int) -> list[dict]:
                return searcher._search(coll, list(v), {"representation_kind": kind, "corpus_id": corpus_id}, limit=top_k)

            def _sweep():
                sweep["started_ms"] = round((time.perf_counter() - t_turn) * 1000, 1)
                t0 = time.perf_counter()
                parents = divergent_sweep(qvec, _latent_search, plan)
                return parents, round((time.perf_counter() - t0) * 1000, 1)

            sweep["searcher"], sweep["qvec"] = searcher, qvec
            try:
                sweep["future"] = pool.submit(_sweep)                          # T=0 of the dense lanes, same pool
            except Exception as exc:  # noqa: BLE001 — the frontier is optional
                sweep["error"] = f"sweep_not_submitted:{type(exc).__name__}"

        out = chat_retrieve_v2(query, corpus_id, lanes=lanes, budget=budget, on_context=_on_context, **kw)
        meta, trace = out["meta"], out["trace"]
        meta["mode"] = MODE_WILDCARD
        evidence = out.get("evidence") or []
        baseline = {"doc_ids": {e.get("doc_id") for e in evidence if e.get("doc_id")},
                    "parent_ids": {e.get("parent_id") for e in evidence if e.get("parent_id")},
                    "chunk_ids": {e.get("chunk_id") for e in evidence if e.get("chunk_id")}}
        t_core = time.perf_counter()
        deadline = t_core + deadline_s                                   # the sweep must have landed by here
        finish_budget_s = float((budget or default_budget()).wildcard_finish_budget_s)
        fill_s = float((budget or default_budget()).wildcard_unverified_fill_s)
        finish_deadline = t_core + max(deadline_s, finish_budget_s)     # B12: the finish has its own, larger budget
        receipt: dict = {
            "contract": MODE_COMPOSITION_CONTRACT, "plan": plan.plan_version, "deadline_s": deadline_s,
            "max_bridges": plan.max_bridges, "latent_top_k": plan.latent_top_k, "candidate_parents": plan.candidate_parents,
            "baseline_chunks": len(baseline["chunk_ids"]), "baseline_parents": len(baseline["parent_ids"]),
            "baseline_docs": len(baseline["doc_ids"]),
            "sweep_started_ms": sweep["started_ms"], "core_done_ms": round((t_core - t_turn) * 1000, 1),
            "sweep_done_before_core": bool(sweep["future"] is not None and sweep["future"].done()),
            "sweep_ms": None, "finish_ms": None,
            "latent_candidates": 0, "excluded_obvious": 0, "support_filtered": 0, "excluded_in_evidence": 0,
            "returned": 0, "reranker": None, "degraded": None,
        }
        bridges: list[dict] = []
        parents: Optional[dict] = None
        fut = sweep["future"]
        if fut is None:
            receipt["degraded"] = sweep["error"] or "sweep_not_started"
        else:
            try:
                parents, receipt["sweep_ms"] = fut.result(timeout=max(0.0, deadline - time.perf_counter()))
            except FutureTimeout:
                receipt["degraded"] = "wildcard_timeout:sweep"
            except CancelledError:
                receipt["degraded"] = "sweep_cancelled"           # the pool closed before the sweep got a worker
            except Exception as exc:  # noqa: BLE001
                receipt["degraded"] = f"sweep_error:{type(exc).__name__}"
        if parents is not None:
            searcher, qvec = sweep["searcher"], sweep["qvec"]

            def _expired() -> None:
                # an abandoned validation (deadline passed, result ignored) must not keep the stores and the
                # reranker busy: every further call raises, divergent_finish treats it as a fail-open miss
                if time.perf_counter() > finish_deadline + WILDCARD_FINISH_GRACE_S + fill_s:
                    raise TimeoutError("wildcard deadline passed; frontier abandoned")

            def _children_of(parent_id: str, _v: tuple = qvec) -> list[dict]:   # closure over ONE fixed vector (#9)
                _expired()
                return searcher._search(coll, list(_v), {"representation_kind": "routing_child", "corpus_id": corpus_id,
                                                          "parent_id": parent_id}, limit=50)

            def _rerank_pairs(anchor: str, texts: list[str]):
                # the cross-encoder stays the sole relevance authority — here it scores (latent surface, source child)
                _expired()
                cands = [{"chunk_id": str(i), "text": t} for i, t in enumerate(texts)]
                ranked = _rerank_children(anchor, cands)
                by_id = {c["chunk_id"]: c.get("rerank_score") for c in ranked}
                scores = [by_id.get(str(i)) for i in range(len(texts))]
                if any(sc is None for sc in scores):
                    return None
                import math
                return [1.0 / (1.0 + math.exp(-float(sc))) for sc in scores]   # raw logits → 0-1 for the support floor

            finish_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wildcard-finish")
            t1 = time.perf_counter()
            f2 = finish_pool.submit(divergent_finish, query, parents, children_of=_children_of, baseline=baseline,
                                    rerank_pairs=_rerank_pairs, plan=plan, deadline=finish_deadline)
            try:
                w = f2.result(timeout=max(0.0, finish_deadline + WILDCARD_FINISH_GRACE_S - time.perf_counter()))
                receipt["finish_ms"] = round((time.perf_counter() - t1) * 1000, 1)
                receipt.update({k: w["diagnostics"].get(k) for k in ("latent_candidates", "excluded_obvious", "support_filtered", "reranker",
                                                                       "partial", "parents_validated", "parents_skipped")})
                for b in w["wildcard"]:
                    if (b.get("source_evidence") or {}).get("chunk_id") in baseline["chunk_ids"]:
                        receipt["excluded_in_evidence"] += 1          # a bridge never duplicates an evidence chunk
                        continue
                    b.setdefault("verified", True)
                    bridges.append(b)
                receipt["verified_bridges"] = len(bridges)
                skipped = (w["diagnostics"].get("skipped_parents") or [])
                if skipped and len(bridges) < plan.max_bridges:
                    qtoks = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
                    extra = _unverified_bridges(skipped, children_of=_children_of, baseline=baseline, quota=plan.max_bridges - len(bridges),
                                                fill_deadline=time.perf_counter() + fill_s, plan=plan, qtoks=qtoks)
                    bridges.extend(extra)
                    receipt["unverified_bridges"] = len(extra)
                    if extra:
                        # the judge missed part or all of its budget: the lane is degraded even though it delivered —
                        # `wildcard_timeout:finish` when nothing was validated, `wildcard_partial:unverified` otherwise
                        receipt["degraded"] = receipt["degraded"] or (
                            "wildcard_timeout:finish" if not w["diagnostics"].get("parents_validated") else "wildcard_partial:unverified")
                bridges = bridges[:plan.max_bridges]
                if not bridges and w["diagnostics"].get("partial") and not w["diagnostics"].get("parents_validated"):
                    receipt["degraded"] = "wildcard_timeout:finish"          # the budget did not fit a single validation
            except FutureTimeout:
                receipt["finish_ms"] = round((time.perf_counter() - t1) * 1000, 1)
                receipt["degraded"] = "wildcard_timeout:finish"
                # B12: the validated frontier is lost, the sweep is not — ship its top parents unverified
                frontier = [dict(x) for x in (parents or {}).values() if x.get("parent_id") not in baseline["parent_ids"]]
                qtoks = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
                extra = _unverified_bridges(frontier[:plan.candidate_parents], children_of=_children_of, baseline=baseline,
                                            quota=plan.max_bridges, fill_deadline=time.perf_counter() + fill_s, plan=plan, qtoks=qtoks)
                bridges.extend(extra)
                receipt["verified_bridges"] = 0
                receipt["unverified_bridges"] = len(extra)
            except Exception as exc:  # noqa: BLE001
                receipt["degraded"] = f"finish_error:{type(exc).__name__}"
        receipt["returned"] = len(bridges)
        receipt.setdefault("verified_bridges", sum(1 for b in bridges if b.get("verified", True)))
        receipt.setdefault("unverified_bridges", sum(1 for b in bridges if b.get("verified", True) is False))
        out["wildcard"] = bridges
        meta["wildcard"] = receipt
        meta["wildcard_plan"] = plan.plan_version
        if receipt["degraded"]:
            meta["degraded"] = list(meta.get("degraded") or []) + [{
                "component": "wildcard",
                "state": ("unverified" if bridges else None),
                "effect": (f"{len(bridges)} frontier bridge(s) shipped UNVERIFIED — the two-hop judge missed its budget; the core evidence stands"
                           if bridges else "no frontier bridges this turn; the core evidence stands"),
                "reason": receipt["degraded"]}]
        lat = trace.setdefault("latency_ms", {})
        lat["wildcard"] = round((time.perf_counter() - t_core) * 1000, 1)     # the frontier's extension of the turn
        lat["wildcard_sweep"] = receipt["sweep_ms"]                             # the sweep's own time (overlapped with the lanes)
        return out
    finally:
        if finish_pool is not None:
            finish_pool.shutdown(wait=False, cancel_futures=True)   # a late validation never holds the turn
        client.close()
