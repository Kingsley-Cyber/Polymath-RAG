"""R1D HYBRID retrieval: FAST + lexical + document-level MMR.

Reuses the FAST engine primitives (pass1.py) — no clone. HYBRID adds:

  - an independent global-child LEXICAL lane (exact terminology,
    acronyms, quoted phrases, identifiers), corpus-filtered, reusing
    the existing lexical_score primitive;
  - RRF over FOUR rankings (k=60), per-lane contributions preserved;
  - document aggregation over four representations (doc summary
    neural, section summary neural, child neural, child lexical);
  - optional document-level MMR diversity over the qualified
    DOCUMENT_RETRIEVAL_SUMMARY neural vectors (lambda grid frozen
    before measurement; lambda=1.0 = relevance-only baseline);
  - LEXICAL_RESCUE arrival for strong lexical hits not reached by
    hierarchy deepening or neural rescue;
  - G3 after the bounded child pool (candidate-set invariant);
  - the same bounded hierarchical evidence budget as FAST.

SUMMARIES ROUTE. CHILDREN PROVE. GLOBAL CHILD SEARCH PROTECTS
RECALL. LEXICAL SEARCH PROTECTS EXACT TERMINOLOGY. DIVERSITY
PROTECTS SYNTHESIS BREADTH.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from polymath_shared.pass1 import (
    ARRIVAL_GLOBAL_CHILD_RESCUE,
    ARRIVAL_MULTI_REPRESENTATION,
    ARRIVAL_SECTION_LED,
    PASS1_DEFAULT_PLAN,
    Pass1RetrievalPlan,
    Pass1Result,
    LaneHit,
    _expand_neighbors,
    _truncate_reserving_rescue,
    aggregate_documents_n,
    resolve_sections,
)

HYBRID_PLAN_VERSION = "hybrid-retrieval-v1"

ARRIVAL_LEXICAL_RESCUE = "LEXICAL_RESCUE"


@dataclass(frozen=True)
class HybridRetrievalPlan:
    """Versioned deterministic HYBRID plan (FAST + lexical + MMR)."""

    plan_version: str = HYBRID_PLAN_VERSION
    corpus_ids: Optional[tuple[str, ...]] = None

    document_summary_enabled: bool = True
    document_summary_top_k: int = 10
    section_summary_enabled: bool = True
    section_summary_top_k: int = 10
    global_child_enabled: bool = True
    global_child_top_k: int = 20
    lexical_enabled: bool = True
    lexical_top_k: int = 20

    rrf_k: int = 60

    mmr_enabled: bool = False
    mmr_lambda: float = 1.0

    max_documents: int = 5
    max_sections_per_document: int = 2
    max_children_per_section: int = 3
    global_child_rescue_max: int = 3
    lexical_rescue_max: int = 3

    rerank_enabled: bool = True

    final_max_children: int = 10
    final_max_total_items: int = 12

    #: See pass1 for both. Defaults preserve HYBRID's frozen behaviour:
    #: rescue reservation only changes WHICH candidates survive a cut
    #: that was already happening, and neighbour expansion is off until
    #: the depth profile turns it on.
    rescue_reserved_slots: int = 2
    neighbor_expansion: int = 0
    neighbor_expansion_max: int = 8


HYBRID_DEFAULT_PLAN = HybridRetrievalPlan()

MMR_LAMBDA_GRID = (1.0, 0.9, 0.8, 0.7)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def mmr_select(
    candidates: list,
    *,
    relevance: dict[str, float],
    vectors: dict[str, list[float]],
    lambda_: float,
    max_documents: int,
) -> list:
    """Document-level MMR: relevance vs redundancy to already-selected
    documents, similarity from qualified document-summary vectors.
    lambda_=1.0 is the relevance-only baseline. Deterministic ties by
    doc_id."""
    remaining = sorted(candidates, key=lambda c: (-relevance.get(c.doc_id, 0.0), c.doc_id))
    selected: list = []
    while remaining and len(selected) < max_documents:
        best = None
        best_score = float("-inf")
        for cand in remaining:
            rel = relevance.get(cand.doc_id, 0.0)
            red = max(
                (_cosine(vectors.get(cand.doc_id, []), vectors.get(s.doc_id, []))
                 for s in selected),
                default=0.0,
            )
            score = lambda_ * rel - (1.0 - lambda_) * red
            if score > best_score or (score == best_score and best is not None
                                      and cand.doc_id < best.doc_id):
                best = cand
                best_score = score
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
    return selected


@dataclass
class HybridResult:
    query: str
    plan: HybridRetrievalPlan
    result: Pass1Result
    documents: list
    lexical_lane: list[LaneHit]
    mmr_applied: bool
    selected_documents: list
    selected_sections: list[dict]
    final_evidence: list[dict]
    trace: dict


def hybrid_retrieve(
    query: str,
    *,
    plan: HybridRetrievalPlan = HYBRID_DEFAULT_PLAN,
    embed_query: Callable[[str], list[float]],
    routing_search: Callable[[str, list[float], dict], list[dict]],
    lexical_search: Callable[[str, int], list[LaneHit]],
    rerank_children: Optional[Callable[[str, list[dict]], list[dict]]] = None,
    summary_vectors: Optional[Callable[[str, list[str]], dict[str, list[float]]]] = None,
    neighbor_lookup: Optional[Callable[[list[dict], int], list[dict]]] = None,
) -> HybridResult:
    from polymath_shared.pass1 import (
        REPRESENTATION_KIND_CHILD,
        REPRESENTATION_KIND_DOCUMENT_SUMMARY,
        REPRESENTATION_KIND_SECTION_SUMMARY,
        pass1_retrieve,
    )

    # FAST-compatible base execution (no lexical, no MMR) — the shared
    # engine stays authoritative for the neural stages.
    fast_plan = Pass1RetrievalPlan(
        corpus_ids=plan.corpus_ids,
        document_summary_enabled=plan.document_summary_enabled,
        document_summary_top_k=plan.document_summary_top_k,
        section_summary_enabled=plan.section_summary_enabled,
        section_summary_top_k=plan.section_summary_top_k,
        global_child_enabled=plan.global_child_enabled,
        global_child_top_k=plan.global_child_top_k,
        rrf_k=plan.rrf_k,
        max_documents=plan.max_documents,
        max_sections_per_document=plan.max_sections_per_document,
        max_children_per_section=plan.max_children_per_section,
        global_child_rescue_max=plan.global_child_rescue_max,
        rerank_enabled=False,
        final_max_children=plan.final_max_children,
        final_max_total_items=plan.final_max_total_items,
    )
    fast = pass1_retrieve(
        query,
        plan=fast_plan,
        embed_query=embed_query,
        routing_search=routing_search,
        rerank_children=None,
    )

    # independent lexical child lane (exact terminology)
    lexical_lane: list[LaneHit] = []
    if plan.lexical_enabled and lexical_search is not None:
        hits = lexical_search(query, plan.lexical_top_k)
        for rank, h in enumerate(hits):
            h.rank = rank
        lexical_lane = hits

    # four-lane RRF aggregation
    documents = aggregate_documents_n([
        (REPRESENTATION_KIND_DOCUMENT_SUMMARY, fast.document_summary_lane),
        (REPRESENTATION_KIND_SECTION_SUMMARY, fast.section_summary_lane),
        (REPRESENTATION_KIND_CHILD, fast.global_child_lane),
        ("child_lexical", lexical_lane),
    ], k=plan.rrf_k)

    # document resolution with optional MMR
    selected_documents: list = []
    if plan.mmr_enabled and summary_vectors is not None and documents:
        relevance = {d.doc_id: d.aggregate_score for d in documents}
        vecs = summary_vectors(
            query,
            [d.doc_id for d in documents[: plan.max_documents * 3]],
        )
        selected_documents = mmr_select(
            documents[: plan.max_documents * 3],
            relevance=relevance,
            vectors=vecs,
            lambda_=plan.mmr_lambda,
            max_documents=plan.max_documents,
        )
    else:
        selected_documents = documents[: plan.max_documents]

    # section resolution: neural section hits + parents of neural AND
    # lexical child hits (lexical cannot bypass hierarchy provenance)
    sections = resolve_sections(selected_documents, plan.max_sections_per_document)
    lexical_parents = {
        h.parent_id: h for h in lexical_lane
        if any(d.doc_id == h.doc_id for d in selected_documents)
    }
    for pid, hit in lexical_parents.items():
        if any(s["parent_id"] == pid for s in sections):
            continue
        sections.append({
            "doc_id": hit.doc_id, "parent_id": pid,
            "summary_id": "", "source_name": hit.source_name,
            "best_section_rank": hit.rank, "best_similarity": hit.raw_similarity,
            "from": ["lexical_rescue"],
        })
    sections = sorted(
        sections,
        key=lambda s: (s["best_section_rank"], s["parent_id"]),
    )[: plan.max_sections_per_document * len(selected_documents)]

    # filtered deepening + neural rescue (shared FAST primitives via fast)
    deepened = {c["chunk_id"]: c for c in fast.deepened_children}
    rescue_neural = {c["chunk_id"]: c for c in fast.rescue_children}
    rescue_lexical: dict[str, dict] = {}
    for hit in lexical_lane[: plan.lexical_rescue_max]:
        if hit.chunk_id in deepened or hit.chunk_id in rescue_neural:
            continue
        rescue_lexical.setdefault(hit.chunk_id, {
            "chunk_id": hit.chunk_id,
            "doc_id": hit.doc_id,
            "parent_id": hit.parent_id,
            "text": hit.text,
            "source_name": hit.source_name,
            "similarity": hit.raw_similarity,
            "arrival": ARRIVAL_LEXICAL_RESCUE,
            "lexical_rank": hit.rank,
        })

    final_candidates: list[dict] = []
    for doc in selected_documents:
        doc_children = [c for c in deepened.values() if c["doc_id"] == doc.doc_id]
        doc_children.sort(key=lambda c: c.get("depth_rank", 10**9))
        for c in doc_children:
            c = dict(c)
            if any(h.chunk_id == c["chunk_id"] for h in doc.global_child_hits):
                c["arrival"] = ARRIVAL_MULTI_REPRESENTATION
            c["document_rank"] = doc.aggregate_rank
            final_candidates.append(c)
    for c in sorted(rescue_neural.values(), key=lambda c: c.get("global_rank", 10**9)):
        final_candidates.append(dict(c))
    for c in sorted(rescue_lexical.values(), key=lambda c: c.get("lexical_rank", 10**9)):
        final_candidates.append(dict(c))

    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for c in final_candidates:
        if c["chunk_id"] in seen_ids:
            continue
        seen_ids.add(c["chunk_id"])
        deduped.append(c)
    # RESCUE-SLOT-RESERVATION-V1 (see pass1): the neural and lexical
    # rescue lanes are appended after every deepened child, so a flat
    # cut here silently deleted both recall lanes on dense corpora.
    deduped = _truncate_reserving_rescue(
        deduped, plan.final_max_children,
        getattr(plan, "rescue_reserved_slots", 2))

    pre_g3 = [c["chunk_id"] for c in deduped]
    post_g3 = list(pre_g3)
    g3_scores: dict[str, float] = {}
    if plan.rerank_enabled and rerank_children is not None and deduped:
        reranked = rerank_children(query, deduped)
        post_g3 = [c["chunk_id"] for c in reranked]
        assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"
        g3_scores = {c["chunk_id"]: c.get("rerank_score") for c in reranked}
        deduped = sorted(deduped, key=lambda c: post_g3.index(c["chunk_id"]))
        for c in deduped:
            c["rerank_score"] = g3_scores.get(c["chunk_id"])

    # NEIGHBOR-EXPANSION-V1: after G3, for the same reason as pass1.
    deduped, neighbors_added = _expand_neighbors(
        deduped, plan, neighbor_lookup)

    final_evidence: list[dict] = []
    total = 0
    for doc in selected_documents:
        for c in [i for i in deduped if i["doc_id"] == doc.doc_id]:
            if total >= plan.final_max_total_items:
                break
            final_evidence.append(c)
            total += 1
    for c in deduped:
        if total >= plan.final_max_total_items:
            break
        if c["chunk_id"] not in {i["chunk_id"] for i in final_evidence}:
            final_evidence.append(c)
            total += 1

    trace = {
        "plan": plan.plan_version,
        "rrf_k": plan.rrf_k,
        "mmr_enabled": plan.mmr_enabled,
        "mmr_lambda": plan.mmr_lambda,
        "lane_sizes": {
            "document_summary": len(fast.document_summary_lane),
            "section_summary": len(fast.section_summary_lane),
            "global_child": len(fast.global_child_lane),
            "child_lexical": len(lexical_lane),
        },
        "document_candidates": [
            {
                "doc_id": d.doc_id,
                "aggregate_rank": d.aggregate_rank,
                "aggregate_score": round(d.aggregate_score, 6),
                "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                "representation_kinds_present": d.representation_kinds_present,
            }
            for d in documents
        ],
        "pre_g3_order": pre_g3,
        "post_g3_order": post_g3,
        "g3_scores": g3_scores,
        "rescue_seated": sum(
            1 for c in final_evidence
            if c.get("arrival") in (ARRIVAL_GLOBAL_CHILD_RESCUE,
                                    ARRIVAL_LEXICAL_RESCUE)),
        "neighbors_added": neighbors_added,
    }

    return HybridResult(
        query=query,
        plan=plan,
        result=fast,
        documents=documents,
        lexical_lane=lexical_lane,
        mmr_applied=plan.mmr_enabled,
        selected_documents=selected_documents,
        selected_sections=sections,
        final_evidence=final_evidence,
        trace=trace,
    )
