"""CANDIDATE-RETRIEVAL-V1 — the CHAT-RETRIEVAL-V2 candidate engine
(CHAT-QUERY-COMPILER-PLAN §3.14, §3.21, §3.22; phase P1.a).

Three independent experts, fused at the CHILD level with full provenance;
no lane is an authority over another:

    LANE A  HIERARCHICAL_ROUTE   doc summaries → documents → section
                                 summaries → children (context, breadth)
    LANE B  GLOBAL_DENSE_CHILD   every child, dense, no document prerequisite
    LANE C  GLOBAL_SPARSE_CHILD  every child, BM25 sparse, no document
                                 prerequisite (exact terms)

    UNION + DEDUPE (provenance kept) → one cross-encoder rerank over a
    bounded prefix → final evidence.

Pure given the injected search callables (no Qdrant, no Postgres here):

    dense_search(kind, top_k, extra_filters) -> [{payload, score}]  (desc)
    sparse_search(top_k)                    -> [{payload, score}]  (desc), raises when unavailable
    region_lookup(chunk_ids)                -> {chunk_id: region_role}

Seams the plan closes here (§3.21): #1 sparse runs ONCE (lane C; the
adapter is built without the routing companion probe); #2 no Postgres
lexical fallback — an unavailable sparse lane is DEGRADED, dense lanes
continue; #3 no plan copy — one `CandidateBudget` is consumed directly;
#4 one budget authority; #14 the query shape is read from the RESOLVED
request (`shape_budget`). Rescue caps do not exist: B and C are lanes.
`hybrid-retrieval-v1` / `pass1-retrieval-v2` are untouched for /retrieve,
/ask and TRAIL.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Iterable, Optional

from polymath_shared.pass1 import (
    REPRESENTATION_KIND_CHILD,
    REPRESENTATION_KIND_DOCUMENT_SUMMARY,
    REPRESENTATION_KIND_ENTITY_CARD,
    REPRESENTATION_KIND_SECTION_SUMMARY,
    DocumentCandidate,
    LaneHit,
    _rrf_score,
    aggregate_documents_n,
    resolve_sections,
)
from polymath_shared.query_shape import is_document_metadata_query, is_enumeration_query

CANDIDATE_ENGINE_VERSION = "candidate-retrieval-v1"
CHAT_RETRIEVAL_PLAN_VERSION = "chat-retrieval-v2"

LANE_A = "HIERARCHICAL_ROUTE"
LANE_B = "GLOBAL_DENSE_CHILD"
LANE_C = "GLOBAL_SPARSE_CHILD"
ARRIVAL_NEIGHBOR = "NEIGHBOR_EXPANSION"
LANES = (LANE_A, LANE_B, LANE_C)


@dataclass(frozen=True)
class CandidateBudget:
    """ONE budget authority for chat retrieval (§3.8, §3.21 #4). Modes
    override only what they genuinely need (P1.e)."""
    hierarchy_doc_k: int = 16
    hierarchy_section_k: int = 24
    hierarchy_child_k: int = 3              # children deepened per section
    hierarchy_max_documents: int = 6
    hierarchy_max_sections_per_document: int = 2
    entity_card_k: int = 8                  # routing votes only (never evidence)
    entity_card_max_docs_per_card: int = 4
    global_dense_k: int = 50
    global_sparse_k: int = 40
    merged_candidate_max: int = 120
    #: MEASURED 2026-09-05: the reranker sidecar scores ~4 pairs/s on this
    #: machine (10 → 2.4 s, 30 → 7.6 s, 100 → 24 s), so the whole union
    #: cannot be judged per turn yet (§3.8 "until the sidecar cap is
    #: raised"). The rerank prefix is fusion order; the funnel shows what
    #: it costs (LOST_AT_RERANK vs LOST_AT_UNION_TRUNCATION).
    rerank_max: int = 20
    synthesis_max: int = 15
    rrf_k: int = 60
    neighbor_expansion: int = 0
    neighbor_expansion_max: int = 8
    demote_noisy_regions: bool = True
    lanes: tuple[str, ...] = LANES

    def to_dict(self) -> dict:
        d = asdict(self)
        d["lanes"] = list(self.lanes)
        return d


def shape_budget(resolved_request: str, budget: CandidateBudget) -> CandidateBudget:
    """QUERY-SHAPE on the RESOLVED request (§3.21 #14): depth profile for
    completeness questions, region demotion lifted for document-metadata
    questions. Deterministic; same predicates as `query_shape`."""
    out = budget
    if is_enumeration_query(resolved_request):
        out = replace(out, hierarchy_section_k=max(out.hierarchy_section_k, 32),
                      hierarchy_max_sections_per_document=max(out.hierarchy_max_sections_per_document, 8),
                      hierarchy_child_k=max(out.hierarchy_child_k, 4),
                      global_dense_k=max(out.global_dense_k, 60),
                      rerank_max=max(out.rerank_max, 28), synthesis_max=max(out.synthesis_max, 28),
                      neighbor_expansion=max(out.neighbor_expansion, 1))
    if is_document_metadata_query(resolved_request):
        out = replace(out, demote_noisy_regions=False)
    return out


#: Query-side only (the BM25 projection is frozen, §3.23). The collection
#: applies an IDF modifier to the query, but the stored values are RAW term
#: frequencies (no BM25 k1/b saturation), so a chunk repeating common query
#: tokens ("animation" ×8, "style" ×12) still outscores one rare identifier.
#: MEASURED 2026-09-05 (fixture L, "UPA"): bare token → gold rank 1; the
#: compiler's "UPA animation studio history style" → gold outside the top
#: 200. Lane C therefore searches the EXACT TERMS ALONE when the plan has
#: any (that is its job: what the user literally said), and otherwise the
#: topical text with function words stripped.
_SPARSE_STOPWORDS = frozenset("""a an and are as at be been but by can could did do does for from had has have he her
his how i if in into is it its of on or our she so than that the their them then there these they this to
was we were what when where which who why will with would you your about above after again all also am any
because before being below between both down during each few further here more most not now off once only other
out over own same should some such through too under until up very while""".split())


def sparse_query_for(text: str, exact_terms: Iterable[str] | None = None) -> tuple[list[str], str]:
    """Tokens lane C searches, and which rule chose them ("exact_terms" |
    "topical" | "raw"). Pure; deterministic."""
    from polymath_shared.sparse_bm25 import tokenize
    exact = [t for t in (exact_terms or []) if str(t).strip()]
    if exact:
        toks = tokenize(" ".join(str(t) for t in exact))
        if toks:
            return toks, "exact_terms"
    toks = [t for t in tokenize(text) if t not in _SPARSE_STOPWORDS]
    if toks:
        return toks, "topical"
    return tokenize(text), "raw"


def sparse_vector_for(text: str, exact_terms: Iterable[str] | None = None) -> tuple[Optional[tuple[tuple[int, ...], tuple[float, ...]]], str]:
    """(indices, values) for lane C from `sparse_query_for` — one tf per token."""
    from collections import Counter
    from polymath_shared.sparse_bm25 import token_index
    toks, rule = sparse_query_for(text, exact_terms)
    if not toks:
        return None, rule
    counts = Counter(token_index(t) for t in toks)
    items = sorted(counts.items())
    return (tuple(i for i, _ in items), tuple(float(v) for _, v in items)), rule


@dataclass(frozen=True)
class SearchContext:
    """Immutable per-turn search inputs (§3.22): one query vector, one
    sparse query, shared by every lane."""
    query: str
    corpus_id: str
    collection: str
    qvec: tuple[float, ...]
    sparse_query: Optional[tuple[tuple[int, ...], tuple[float, ...]]] = None
    exact_terms: tuple[str, ...] = ()
    hidden_generations: tuple[str, ...] = ()
    query_id: str = "q0"
    sparse_rule: str = "topical"          # which rule built sparse_query (receipted)


@dataclass
class CandidateEvidence:
    chunk_id: str
    doc_id: str
    parent_id: str
    source_name: str
    text: str
    arrivals: list[str] = field(default_factory=list)
    query_ids: list[str] = field(default_factory=list)
    hierarchy_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    rerank_score: Optional[float] = None
    fused_score: float = 0.0
    document_rank: Optional[int] = None
    is_neighbor: bool = False
    region_role: Optional[str] = None

    def to_row(self) -> dict:
        """The evidence dict shape the orchestrator, assembler and funnel
        already consume (`arrival` = first arrival, plus the full list)."""
        return {"chunk_id": self.chunk_id, "doc_id": self.doc_id, "parent_id": self.parent_id,
                "source_name": self.source_name, "text": self.text,
                "arrival": (self.arrivals[0] if self.arrivals else None), "arrivals": list(self.arrivals),
                "query_ids": list(self.query_ids), "hierarchy_rank": self.hierarchy_rank,
                "dense_rank": self.dense_rank, "sparse_rank": self.sparse_rank,
                "dense_score": self.dense_score, "sparse_score": self.sparse_score,
                "rerank_score": self.rerank_score, "fused_score": round(self.fused_score, 6),
                "document_rank": self.document_rank, "is_neighbor": self.is_neighbor,
                "region_role": self.region_role,
                "similarity": self.dense_score if self.dense_score is not None else self.sparse_score}


@dataclass
class CandidateResult:
    context: SearchContext
    budget: CandidateBudget
    documents: list[DocumentCandidate]
    selected_documents: list[DocumentCandidate]
    selected_sections: list[dict]
    lane_a: list[CandidateEvidence]
    lane_b: list[CandidateEvidence]
    lane_c: list[CandidateEvidence]
    union: list[CandidateEvidence]           # fused order, capped at merged_candidate_max
    union_ids_uncapped: list[str]            # RETRIEVAL-FUNNEL-V1 `union` (before the cap)
    degraded: list[dict]
    timings_ms: dict
    trace: dict


def _hits(kind: str, rows: Iterable[dict], corpus_id: str, top_k: int, *,
          card_k: int = 0, card_max_docs: int = 0) -> list[LaneHit]:
    """Raw adapter rows → LaneHits (rank = position). Entity cards expand
    to one vote per (card, doc), exactly as pass1 does."""
    hits: list[LaneHit] = []
    for i, row in enumerate(list(rows)[:top_k]):
        payload = row.get("payload") or {}
        score = float(row.get("score") or 0.0)
        if kind == REPRESENTATION_KIND_ENTITY_CARD:
            if i >= card_k:
                continue
            docs = list(payload.get("doc_ids") or [])
            if not docs and payload.get("doc_id"):
                docs = [payload["doc_id"]]
            for d in docs[:card_max_docs]:
                hits.append(LaneHit(representation_kind=kind, rank=i, raw_similarity=score,
                                    corpus_id=payload.get("corpus_id", corpus_id), doc_id=d, parent_id="",
                                    chunk_id="", summary_id=payload.get("summary_id") or "",
                                    source_name=payload.get("source_name", ""), text=payload.get("text", "")))
            continue
        hits.append(LaneHit(representation_kind=kind, rank=i, raw_similarity=score,
                            corpus_id=payload.get("corpus_id", corpus_id), doc_id=payload.get("doc_id", ""),
                            parent_id=payload.get("parent_id", ""), chunk_id=payload.get("chunk_id") or "",
                            summary_id=payload.get("summary_id") or "", source_name=payload.get("source_name", ""),
                            text=payload.get("text", "")))
    return hits


def _sink_noisy(hits: list[LaneHit], roles: dict) -> list[LaneHit]:
    """DOCUMENT-REGION-V1 inside a lane: demote, never delete."""
    if not roles:
        return hits
    from polymath_shared.document_region import is_noisy
    out = sorted(hits, key=lambda h: (1 if is_noisy(roles.get(h.chunk_id)) else 0, h.rank))
    for i, h in enumerate(out):
        h.rank = i
    return out


def retrieve_candidates(ctx: SearchContext, budget: CandidateBudget, *,
                        dense_search: Callable[[str, int, Optional[dict]], list[dict]],
                        sparse_search: Callable[[int], list[dict]],
                        region_lookup: Optional[Callable[[list[str]], dict]] = None) -> CandidateResult:
    timings: dict[str, float] = {}
    degraded: list[dict] = []
    lanes = set(budget.lanes)

    def timed(name: str, fn):
        t0 = time.perf_counter()
        try:
            return fn()
        finally:
            timings[name] = round((time.perf_counter() - t0) * 1000, 1)

    # ---- global child lanes (B, C) --------------------------------------
    child_rows = timed("global_dense_child", lambda: dense_search(REPRESENTATION_KIND_CHILD, budget.global_dense_k, None)) \
        if (LANE_B in lanes or LANE_A in lanes) else []
    child_lane = _hits(REPRESENTATION_KIND_CHILD, child_rows, ctx.corpus_id, budget.global_dense_k)
    roles: dict = {}
    if budget.demote_noisy_regions and region_lookup is not None and child_lane:
        try:
            roles = region_lookup([h.chunk_id for h in child_lane if h.chunk_id]) or {}
        except Exception:  # noqa: BLE001 — demotion is best-effort
            roles = {}
        child_lane = _sink_noisy(child_lane, roles)

    sparse_lane: list[LaneHit] = []
    if LANE_C in lanes:
        try:
            sparse_rows = timed("global_sparse_child", lambda: sparse_search(budget.global_sparse_k))
            sparse_lane = _hits("child_lexical", sparse_rows, ctx.corpus_id, budget.global_sparse_k)
        except Exception as exc:  # noqa: BLE001 — §3.21 #2: DEGRADED, never a Postgres scan
            degraded.append({"component": "sparse_lane", "effect": "no exact-match lane this turn; dense lanes only",
                             "reason": f"{type(exc).__name__}: {str(exc)[:160]}"})

    # ---- lane A: hierarchical route --------------------------------------
    doc_lane: list[LaneHit] = []
    section_lane: list[LaneHit] = []
    card_lane: list[LaneHit] = []
    documents: list[DocumentCandidate] = []
    selected_documents: list[DocumentCandidate] = []
    selected_sections: list[dict] = []
    lane_a: list[CandidateEvidence] = []
    if LANE_A in lanes:
        doc_lane = _hits(REPRESENTATION_KIND_DOCUMENT_SUMMARY,
                         timed("document_summary", lambda: dense_search(REPRESENTATION_KIND_DOCUMENT_SUMMARY, budget.hierarchy_doc_k, None)),
                         ctx.corpus_id, budget.hierarchy_doc_k)
        section_lane = _hits(REPRESENTATION_KIND_SECTION_SUMMARY,
                             timed("section_summary", lambda: dense_search(REPRESENTATION_KIND_SECTION_SUMMARY, budget.hierarchy_section_k, None)),
                             ctx.corpus_id, budget.hierarchy_section_k)
        if budget.entity_card_k > 0:
            try:
                card_lane = _hits(REPRESENTATION_KIND_ENTITY_CARD,
                                  timed("entity_card", lambda: dense_search(REPRESENTATION_KIND_ENTITY_CARD,
                                                                            budget.entity_card_k * budget.entity_card_max_docs_per_card, None)),
                                  ctx.corpus_id, budget.entity_card_k * budget.entity_card_max_docs_per_card,
                                  card_k=budget.entity_card_k, card_max_docs=budget.entity_card_max_docs_per_card)
            except Exception:  # noqa: BLE001 — routing votes only
                card_lane = []
        documents = aggregate_documents_n(
            [(REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_lane), (REPRESENTATION_KIND_SECTION_SUMMARY, section_lane),
             (REPRESENTATION_KIND_CHILD, child_lane), (REPRESENTATION_KIND_ENTITY_CARD, card_lane)], k=budget.rrf_k)
        selected_documents = documents[:budget.hierarchy_max_documents]
        selected_sections = resolve_sections(selected_documents, budget.hierarchy_max_sections_per_document)
        doc_rank = {d.doc_id: d.aggregate_rank for d in selected_documents}
        t0 = time.perf_counter()
        seen_a: set[str] = set()
        for section in selected_sections:
            rows = dense_search(REPRESENTATION_KIND_CHILD, budget.hierarchy_child_k,
                                {"doc_id": section["doc_id"], "parent_id": section["parent_id"]})
            for h in _hits(REPRESENTATION_KIND_CHILD, rows, ctx.corpus_id, budget.hierarchy_child_k):
                if not h.chunk_id or h.chunk_id in seen_a:
                    continue
                seen_a.add(h.chunk_id)
                lane_a.append(CandidateEvidence(
                    chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name, text=h.text,
                    arrivals=[LANE_A], query_ids=[ctx.query_id], hierarchy_rank=len(lane_a), dense_score=h.raw_similarity,
                    document_rank=doc_rank.get(h.doc_id)))
        timings["hierarchical_children"] = round((time.perf_counter() - t0) * 1000, 1)

    lane_b = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_B], query_ids=[ctx.query_id], dense_rank=h.rank,
                                dense_score=h.raw_similarity, region_role=roles.get(h.chunk_id))
              for h in child_lane if h.chunk_id] if LANE_B in lanes else []
    lane_c = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_C], query_ids=[ctx.query_id], sparse_rank=h.rank,
                                sparse_score=h.raw_similarity)
              for h in sparse_lane if h.chunk_id]

    # ---- union + dedupe + provenance-preserving fusion --------------------
    by_id: dict[str, CandidateEvidence] = {}
    for lane_items in (lane_a, lane_b, lane_c):
        for c in lane_items:
            cur = by_id.get(c.chunk_id)
            if cur is None:
                by_id[c.chunk_id] = replace_candidate(c)
                continue
            for a in c.arrivals:
                if a not in cur.arrivals:
                    cur.arrivals.append(a)
            for q in c.query_ids:
                if q not in cur.query_ids:
                    cur.query_ids.append(q)
            if cur.hierarchy_rank is None:
                cur.hierarchy_rank = c.hierarchy_rank
            if cur.dense_rank is None:
                cur.dense_rank, cur.dense_score = c.dense_rank, (c.dense_score if c.dense_score is not None else cur.dense_score)
            if cur.sparse_rank is None:
                cur.sparse_rank, cur.sparse_score = c.sparse_rank, c.sparse_score
            if cur.document_rank is None:
                cur.document_rank = c.document_rank
            if not cur.text and c.text:
                cur.text = c.text
    for c in by_id.values():
        c.fused_score = sum(_rrf_score(r, budget.rrf_k) for r in (c.hierarchy_rank, c.dense_rank, c.sparse_rank) if r is not None)
        if c.region_role is None:
            c.region_role = roles.get(c.chunk_id)
    fused = sorted(by_id.values(), key=lambda c: (-c.fused_score, c.chunk_id))
    if budget.demote_noisy_regions and roles:
        from polymath_shared.document_region import is_noisy
        fused = sorted(fused, key=lambda c: 1 if is_noisy(c.region_role) else 0)   # stable: order kept within groups
    union_ids_uncapped = [c.chunk_id for c in fused]
    union = fused[:budget.merged_candidate_max]

    trace = {
        "plan": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION, "rrf_k": budget.rrf_k,
        "budget": budget.to_dict(),
        "lane_sizes": {"document_summary": len(doc_lane), "section_summary": len(section_lane), "entity_card": len(card_lane),
                       "hierarchical_children": len(lane_a), "global_dense_child": len(lane_b), "global_sparse_child": len(lane_c),
                       "union": len(union), "union_uncapped": len(union_ids_uncapped)},
        "funnel_lanes": {"hierarchical": [c.chunk_id for c in lane_a], "global_dense_child": [c.chunk_id for c in lane_b],
                         "global_sparse_child": [c.chunk_id for c in lane_c]},
        "funnel_union": union_ids_uncapped,
        "document_candidates": [{"doc_id": d.doc_id, "aggregate_rank": d.aggregate_rank, "aggregate_score": round(d.aggregate_score, 6),
                                 "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                                 "representation_kinds_present": d.representation_kinds_present} for d in documents],
        "multi_lane": sum(1 for c in union if len(c.arrivals) > 1),
        "sparse_rule": ctx.sparse_rule, "exact_terms": list(ctx.exact_terms),
        "degraded": list(degraded), "timings_ms": dict(timings),
    }
    return CandidateResult(context=ctx, budget=budget, documents=documents, selected_documents=selected_documents,
                           selected_sections=selected_sections, lane_a=lane_a, lane_b=lane_b, lane_c=lane_c,
                           union=union, union_ids_uncapped=union_ids_uncapped, degraded=degraded, timings_ms=timings, trace=trace)


def replace_candidate(c: CandidateEvidence) -> CandidateEvidence:
    return CandidateEvidence(**{**c.__dict__, "arrivals": list(c.arrivals), "query_ids": list(c.query_ids)})


def select_evidence(result: CandidateResult, budget: CandidateBudget, *,
                    rerank_children: Optional[Callable[[str, list[dict]], list[dict]]] = None,
                    neighbor_lookup: Optional[Callable[[list[dict], int], list[dict]]] = None) -> tuple[list[CandidateEvidence], dict]:
    """One cross-encoder judgement over the fusion-ordered prefix
    (`rerank_max`), pure relevance to `synthesis_max`, then the depth
    profile's neighbour expansion (additive, after the judge — the
    candidate set the reranker scored is never changed). P1.c owns the
    composition slots; here relevance order is the whole law."""
    prefix = result.union[:budget.rerank_max]
    pre = [c.chunk_id for c in prefix]
    post = list(pre)
    scores: dict[str, float] = {}
    if rerank_children is not None and prefix:
        rows = [c.to_row() for c in prefix]
        reranked = rerank_children(result.context.query, rows)
        post = [r["chunk_id"] for r in reranked]
        assert set(post) == set(pre), "rerank changed the candidate set"
        scores = {r["chunk_id"]: r.get("rerank_score") for r in reranked}
        by_id = {c.chunk_id: c for c in prefix}
        prefix = [by_id[cid] for cid in post]
        for c in prefix:
            c.rerank_score = scores.get(c.chunk_id)
    final = list(prefix[:budget.synthesis_max])
    added = 0
    if budget.neighbor_expansion > 0 and neighbor_lookup is not None and final:
        try:
            neighbours = neighbor_lookup([{"doc_id": c.doc_id, "chunk_id": c.chunk_id} for c in final], budget.neighbor_expansion) or []
        except Exception:  # noqa: BLE001 — additive, never fails the turn
            neighbours = []
        have = {c.chunk_id for c in final}
        for n in neighbours:
            cid = n.get("chunk_id")
            if not cid or cid in have:
                continue
            have.add(cid)
            final.append(CandidateEvidence(chunk_id=cid, doc_id=n.get("doc_id", ""), parent_id=n.get("parent_id", ""),
                                           source_name=n.get("source_name", ""), text=n.get("text", ""),
                                           arrivals=[ARRIVAL_NEIGHBOR], query_ids=[result.context.query_id], is_neighbor=True))
            added += 1
            if added >= budget.neighbor_expansion_max:
                break
    trace = {"pre_g3_order": pre, "post_g3_order": post, "g3_scores": scores, "rerank_prefix": len(pre),
             "neighbors_added": added, "final": [c.chunk_id for c in final]}
    return final, trace
