"""R1B Pass-1 summary-led retrieval engine.

SUMMARIES ROUTE / CHILDREN PROVE / GLOBAL CHILD SEARCH PROTECTS
RECALL.

Three independent neural searches (document summary, section summary,
global child) over the qualified routing projection → RRF (versioned k,
per-lane contributions preserved) → explicit document aggregation →
bounded document resolution → section resolution → FILTERED child
deepening (corpus + doc + parent filters) → global-child rescue union
→ dedupe → G3 (order-only) → bounded hierarchical Pass-1 evidence.

Routing summaries are NEVER exact evidence (R1A/D4/D4.1): they
establish document/section relevance; only CHILD hits become exact
evidence candidates. The retrieval trace keeps full diagnostics; the
final evidence set is a bounded child structure.

Determinism: identical (query, plan, corpus state, pinned models)
produce identical semantic output. No thresholds invented here — this
is broad retrieval → structured routing → bounded candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# PASS1-RETRIEVAL-V2 (2026-08-30): entity cards join document fusion as a
# fourth RRF lane (audit F2), and the breadth caps are re-derived from the
# owner's retrieval style rather than inherited constants (audit F7):
# "summaries for breadth AND depth", "teach it, never inventory it",
# "completeness overrides brevity". Derivation, measured on live corpora
# (parents ~24-40/book at ~850w, ~5 children/parent, chunks ~1.2K chars):
#   - sections are the teaching unit -> 3 sections/doc breadth (was 2) and
#     a deeper section lane (12) so section context outranks stray children
#   - child lane 24 (was 20): rescue pool scales with the deeper descent
#   - final evidence 12/15 (was 10/12): fits the synthesis budget at 2K
#     chars/item while adding one more proving child per answer
PLAN_VERSION = "pass1-retrieval-v2"

REPRESENTATION_KIND_DOCUMENT_SUMMARY = "routing_document_summary"
REPRESENTATION_KIND_SECTION_SUMMARY = "routing_section_summary"
REPRESENTATION_KIND_CHILD = "routing_child"
REPRESENTATION_KIND_ENTITY_CARD = "routing_entity"

ARRIVAL_DOCUMENT_LED = "DOCUMENT_LED"
ARRIVAL_SECTION_LED = "SECTION_LED"
ARRIVAL_GLOBAL_CHILD_RESCUE = "GLOBAL_CHILD_RESCUE"
ARRIVAL_MULTI_REPRESENTATION = "MULTI_REPRESENTATION"
#: NEIGHBOR-EXPANSION-V1: admitted because it is adjacent to a ranked
#: candidate, not because it was retrieved on its own merit.
ARRIVAL_NEIGHBOR_EXPANSION = "NEIGHBOR_EXPANSION"


@dataclass(frozen=True)
class Pass1RetrievalPlan:
    """Versioned deterministic Pass-1 retrieval plan (R1B).

    Same query + same plan + same corpus state => same structure."""

    plan_version: str = PLAN_VERSION
    corpus_ids: Optional[tuple[str, ...]] = None

    document_summary_enabled: bool = True
    document_summary_top_k: int = 10
    section_summary_enabled: bool = True
    section_summary_top_k: int = 12
    global_child_enabled: bool = True
    global_child_top_k: int = 24

    # ENTITY-CARD-LANE (audit F2): graph extractions vote in document
    # fusion — one card ranks, every document it evidences receives its
    # RRF contribution (bounded per card).
    entity_card_enabled: bool = True
    entity_card_top_k: int = 8
    entity_card_max_docs_per_card: int = 4

    rrf_k: int = 60

    max_documents: int = 5
    max_sections_per_document: int = 3
    max_children_per_section: int = 3
    global_child_rescue_max: int = 3

    rerank_enabled: bool = True

    final_max_children: int = 12
    final_max_total_items: int = 15

    #: RESCUE-SLOT-RESERVATION-V1 (2026-08-27). `global_child_rescue_max`
    #: was structurally dead: rescue children are appended AFTER every
    #: deepened child (up to max_documents × max_sections_per_document ×
    #: max_children_per_section = 30 by default) and the list is then cut
    #: to `final_max_children` = 10, so on any dense corpus the recall-
    #: safety lane was always truncated away. MEASURED LIVE on
    #: cysa-study-v1: 0 of 10 delivered chunks arrived via rescue
    #: (7 MULTI_REPRESENTATION, 3 SECTION_LED) while the answer the user
    #: asked for sat mid-document, exactly the case rescue exists to
    #: catch. Reserving slots keeps the hierarchy dominant while
    #: guaranteeing the global child lane can always seat its best hits.
    #: Reservation never grows the candidate set — it only decides which
    #: `final_max_children` survive.
    rescue_reserved_slots: int = 2

    #: NEIGHBOR-EXPANSION-V1 (2026-08-27). Number of adjacent chunks
    #: (chunk_index ± n, same document) to admit alongside a surviving
    #: child. Answers that run past one chunk boundary — enumerations,
    #: objectives maps, procedures — are otherwise delivered as a
    #: fragment: MEASURED, the CySA objectives map ends at subdomain 1.5
    #: and domains 2/3/4 live in the NEXT chunk, which nothing pulled in.
    #: Simulated ±1 expansion took coverage from one domain to all four.
    #: DEFAULT 0 (off): breadth-first retrieval is correct for ordinary
    #: questions and the frozen plan must not change under them. The
    #: depth profile turns it on (see query_shape.enumeration_plan).
    neighbor_expansion: int = 0
    neighbor_expansion_max: int = 8

    #: DOCUMENT-REGION-V1. When true, children whose persisted
    #: `region_role` is a demoted role (front matter, marketing, TOC,
    #: index, bibliography, OCR placeholder) SINK to the end of the
    #: child lane instead of competing on similarity alone.
    #:
    #: This is DEMOTION, never deletion: every chunk stays indexed and
    #: still reaches the model if nothing better exists, and an explicit
    #: document-metadata question turns the demotion off entirely (see
    #: query_shape.is_document_metadata_query). Necessary because
    #: similarity CANNOT separate these: MEASURED, an author biography
    #: scored 0.5955 against the correct objectives map at 0.4894 for a
    #: technical question, so any score floor removes the answer first.
    demote_noisy_regions: bool = True


PASS1_DEFAULT_PLAN = Pass1RetrievalPlan()


@dataclass
class LaneHit:
    representation_kind: str
    rank: int
    raw_similarity: float
    corpus_id: str
    doc_id: str
    parent_id: str
    chunk_id: str
    summary_id: str
    source_name: str
    text: str


@dataclass
class DocumentCandidate:
    doc_id: str
    corpus_id: str
    document_summary_hits: list[LaneHit] = field(default_factory=list)
    entity_card_hits: list[LaneHit] = field(default_factory=list)
    section_summary_hits: list[LaneHit] = field(default_factory=list)
    global_child_hits: list[LaneHit] = field(default_factory=list)
    child_lexical_hits: list[LaneHit] = field(default_factory=list)
    rrf_contributions: dict[str, float] = field(default_factory=dict)
    best_document_summary_rank: Optional[int] = None
    best_section_summary_rank: Optional[int] = None
    best_child_rank: Optional[int] = None
    best_lexical_rank: Optional[int] = None
    aggregate_score: float = 0.0
    aggregate_rank: int = -1

    @property
    def representation_kinds_present(self) -> list[str]:
        kinds = []
        if self.document_summary_hits:
            kinds.append(REPRESENTATION_KIND_DOCUMENT_SUMMARY)
        if self.section_summary_hits:
            kinds.append(REPRESENTATION_KIND_SECTION_SUMMARY)
        if self.global_child_hits:
            kinds.append(REPRESENTATION_KIND_CHILD)
        if self.child_lexical_hits:
            kinds.append("child_lexical")
        if self.entity_card_hits:
            kinds.append(REPRESENTATION_KIND_ENTITY_CARD)
        return kinds


@dataclass
class Pass1Result:
    query: str
    plan: Pass1RetrievalPlan
    document_summary_lane: list[LaneHit]
    section_summary_lane: list[LaneHit]
    global_child_lane: list[LaneHit]
    documents: list[DocumentCandidate]
    selected_documents: list[DocumentCandidate]
    selected_sections: list[dict]
    deepened_children: list[dict]
    rescue_children: list[dict]
    final_evidence: list[dict]
    trace: dict


def _rrf_score(rank: int, k: int) -> float:
    return 1.0 / (k + rank + 1)


def aggregate_documents(
    doc_lane: list[LaneHit],
    section_lane: list[LaneHit],
    child_lane: list[LaneHit],
    k: int,
) -> list[DocumentCandidate]:
    """RRF over the three independent doc-level rankings, preserving
    per-lane contributions for diagnostics (deterministic, inspectable).
    R1D: the FAST three-lane signature is frozen; HYBRID uses
    aggregate_documents_n with a fourth lexical lane."""
    return aggregate_documents_n(
        [(REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_lane),
         (REPRESENTATION_KIND_SECTION_SUMMARY, section_lane),
         (REPRESENTATION_KIND_CHILD, child_lane)],
        k=k,
    )


def aggregate_documents_n(
    lanes: list[tuple[str, list[LaneHit]]],
    k: int,
) -> list[DocumentCandidate]:
    by_doc: dict[str, DocumentCandidate] = {}

    def ensure(hit: LaneHit) -> DocumentCandidate:
        cand = by_doc.get(hit.doc_id)
        if cand is None:
            cand = DocumentCandidate(doc_id=hit.doc_id, corpus_id=hit.corpus_id)
            by_doc[hit.doc_id] = cand
        return cand

    for kind, lane in lanes:
        attr = {
            REPRESENTATION_KIND_DOCUMENT_SUMMARY: "document_summary_hits",
            REPRESENTATION_KIND_SECTION_SUMMARY: "section_summary_hits",
            REPRESENTATION_KIND_CHILD: "global_child_hits",
            "child_lexical": "child_lexical_hits",
            REPRESENTATION_KIND_ENTITY_CARD: "entity_card_hits",
        }[kind]
        seen: set[str] = set()
        for hit in lane:
            cand = ensure(hit)
            getattr(cand, attr).append(hit)
            if hit.doc_id not in seen:
                seen.add(hit.doc_id)
                contrib = _rrf_score(hit.rank, k)
                cand.rrf_contributions[kind] = (
                    cand.rrf_contributions.get(kind, 0.0) + contrib
                )

    candidates = list(by_doc.values())
    for cand in candidates:
        cand.aggregate_score = sum(cand.rrf_contributions.values())
        cand.best_document_summary_rank = min(
            (h.rank for h in cand.document_summary_hits), default=None)
        cand.best_section_summary_rank = min(
            (h.rank for h in cand.section_summary_hits), default=None)
        cand.best_child_rank = min(
            (h.rank for h in cand.global_child_hits), default=None)
        cand.best_lexical_rank = min(
            (h.rank for h in cand.child_lexical_hits), default=None)
    candidates.sort(key=lambda c: (-c.aggregate_score, c.doc_id))
    for rank, cand in enumerate(candidates):
        cand.aggregate_rank = rank
    return candidates


def resolve_sections(
    selected_docs: list[DocumentCandidate],
    max_sections_per_document: int,
) -> list[dict]:
    """Sections within winning documents, from section-summary hits and
    parents of the doc's global-child hits. Bounded, deterministic."""
    resolved: list[dict] = []
    for doc in selected_docs:
        section_order: dict[str, dict] = {}
        for hit in doc.section_summary_hits:
            pid = hit.parent_id
            slot = section_order.setdefault(pid, {
                "doc_id": doc.doc_id, "parent_id": pid,
                "summary_id": hit.summary_id, "source_name": hit.source_name,
                "best_section_rank": hit.rank, "best_similarity": hit.raw_similarity,
                "from": ["section_summary"],
            })
            if hit.rank < slot["best_section_rank"]:
                slot["best_section_rank"] = hit.rank
                slot["best_similarity"] = hit.raw_similarity
        for hit in doc.global_child_hits:
            pid = hit.parent_id
            if pid not in section_order:
                section_order[pid] = {
                    "doc_id": doc.doc_id, "parent_id": pid,
                    "summary_id": "", "source_name": hit.source_name,
                    "best_section_rank": hit.rank, "best_similarity": hit.raw_similarity,
                    "from": ["child_rescue"],
                }
            else:
                section_order[pid]["from"].append("child_rescue")
        ordered = sorted(
            section_order.values(),
            key=lambda s: (s["best_section_rank"], s["parent_id"]),
        )[:max_sections_per_document]
        resolved.extend(ordered)
    return resolved


def _truncate_reserving_rescue(candidates: list[dict], limit: int,
                               reserved: int,
                               rescue_arrivals: tuple[str, ...] = (
                                   ARRIVAL_GLOBAL_CHILD_RESCUE,),
                               ) -> list[dict]:
    """Cut to `limit`, keeping up to `reserved` seats for rescue-lane
    candidates that the hierarchy would otherwise evict.

    ADDITIVE-SEED-SEAM-V1 (pre-refactor for LATENT-TRANSFER-LAYER-V1
    Phase D, spec'd there verbatim): `rescue_arrivals` generalizes the
    reservation to any additive seed lane (latent rescue, entity-card
    rescue) — the default keeps today's behavior byte-identical, and
    every future lane plugs in here instead of forking this function.

    Order is preserved (hierarchy first, then rescue), so this only
    changes WHICH candidates survive, never their relative order. With
    `reserved=0`, or when nothing was rescued, or when everything fits,
    the result is identical to a plain `candidates[:limit]`.
    """
    if limit <= 0 or len(candidates) <= limit:
        return candidates[:limit] if limit >= 0 else candidates
    rescue = [c for c in candidates
              if c.get("arrival") in rescue_arrivals]
    if not rescue or reserved <= 0:
        return candidates[:limit]
    seats = min(reserved, len(rescue), limit)
    hierarchy = [c for c in candidates
                 if c.get("arrival") not in rescue_arrivals]
    kept_ids = {c["chunk_id"] for c in hierarchy[:limit - seats]}
    kept_ids.update(c["chunk_id"] for c in rescue[:seats])
    return [c for c in candidates if c["chunk_id"] in kept_ids][:limit]


def _expand_neighbors(candidates: list[dict], plan: Pass1RetrievalPlan,
                      neighbor_lookup) -> tuple[list[dict], int]:
    """NEIGHBOR-EXPANSION-V1: admit adjacent chunks so an answer that
    runs past a chunk boundary arrives whole.

    Neighbours are APPENDED after the ranked candidates and never
    displace one: this raises recall without reordering anything the
    ranker decided. Returns (candidates, added_count).
    """
    if plan.neighbor_expansion <= 0 or not candidates or neighbor_lookup is None:
        return candidates, 0
    want = [
        {"doc_id": c["doc_id"], "chunk_id": c["chunk_id"]}
        for c in candidates if c.get("doc_id") and c.get("chunk_id")
    ]
    try:
        neighbours = neighbor_lookup(want, plan.neighbor_expansion) or []
    except Exception:
        return candidates, 0  # expansion is additive; never fail the query
    have = {c["chunk_id"] for c in candidates}
    added: list[dict] = []
    for n in neighbours:
        cid = n.get("chunk_id")
        if not cid or cid in have:
            continue
        have.add(cid)
        added.append({
            "chunk_id": cid,
            "doc_id": n.get("doc_id", ""),
            "parent_id": n.get("parent_id", ""),
            "text": n.get("text", ""),
            "source_name": n.get("source_name", ""),
            "similarity": None,
            "arrival": ARRIVAL_NEIGHBOR_EXPANSION,
            "document_rank": None,
        })
        if len(added) >= plan.neighbor_expansion_max:
            break
    return candidates + added, len(added)


def pass1_retrieve(
    query: str,
    *,
    plan: Pass1RetrievalPlan = PASS1_DEFAULT_PLAN,
    embed_query: Callable[[str], list[float]],
    routing_search: Callable[[str, list[float], dict], list[dict]],
    rerank_children: Optional[Callable[[str, list[dict]], list[dict]]] = None,
    neighbor_lookup: Optional[Callable[[list[dict], int], list[dict]]] = None,
    region_lookup: Optional[Callable[[list[str]], dict]] = None,
) -> Pass1Result:
    """Execute Pass-1. `routing_search(collection, vector, filters)` returns
    [{payload, score}] sorted by score desc; filters: representation_kind,
    corpus_id, and optional doc_id / parent_id.

    `neighbor_lookup(want, distance)` returns adjacent chunk rows for the
    given [{doc_id, chunk_id}] seeds; only called when the plan enables
    neighbour expansion (depth profile)."""
    from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name

    collections = []
    corpus_ids = list(plan.corpus_ids or [])
    if corpus_ids:
        collections = [
            (cid, qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id))
            for cid in corpus_ids
        ]
    else:
        collections = [(None, None)]  # cross-corpus: caller resolves

    qvec = embed_query(query)

    def search(kind: str, top_k: int, extra: Optional[dict] = None) -> list[LaneHit]:
        hits: list[LaneHit] = []
        for cid, collection in collections:
            filters = {"representation_kind": kind}
            if cid:
                filters["corpus_id"] = cid
            if extra:
                filters.update(extra)
            rows = routing_search(collection or "", qvec, filters)[:top_k]
            for i, row in enumerate(rows):
                payload = row.get("payload") or {}
                # ENTITY-CARD-LANE (F2): a card votes for EVERY document
                # it evidences (payload doc_ids, bounded) — one LaneHit
                # per (card, doc) at the card's rank, so RRF attributes
                # the vote per document.
                if kind == REPRESENTATION_KIND_ENTITY_CARD:
                    if i >= plan.entity_card_top_k:
                        continue          # votes expand; the CARD pool stays capped
                    docs = list(payload.get("doc_ids") or [])
                    if not docs and payload.get("doc_id"):
                        docs = [payload["doc_id"]]
                    for d in docs[:plan.entity_card_max_docs_per_card]:
                        hits.append(LaneHit(
                            representation_kind=kind, rank=i,
                            raw_similarity=float(row.get("score") or 0.0),
                            corpus_id=payload.get("corpus_id", cid or ""),
                            doc_id=d, parent_id="", chunk_id="",
                            summary_id=payload.get("summary_id") or "",
                            source_name=payload.get("source_name", ""),
                            text=payload.get("text", "")))
                    continue
                hits.append(LaneHit(
                    representation_kind=kind,
                    rank=i,
                    raw_similarity=float(row.get("score") or 0.0),
                    corpus_id=payload.get("corpus_id", cid or ""),
                    doc_id=payload.get("doc_id", ""),
                    parent_id=payload.get("parent_id", ""),
                    chunk_id=payload.get("chunk_id") or "",
                    summary_id=payload.get("summary_id") or "",
                    source_name=payload.get("source_name", ""),
                    text=payload.get("text", ""),
                ))
        hits.sort(key=lambda h: (-h.raw_similarity, h.doc_id, h.parent_id))
        # DOCUMENT-REGION-V1: sink demoted regions within the child lane
        # BEFORE the top_k cut, so boilerplate cannot occupy the slots
        # that answer-bearing children need. Order among non-demoted and
        # among demoted candidates is otherwise untouched.
        if (kind == REPRESENTATION_KIND_CHILD and plan.demote_noisy_regions
                and region_lookup is not None and hits):
            try:
                roles = region_lookup([h.chunk_id for h in hits if h.chunk_id])
            except Exception:
                roles = {}
            if roles:
                from polymath_shared.document_region import is_noisy
                hits.sort(key=lambda h: (
                    1 if is_noisy(roles.get(h.chunk_id)) else 0,
                    -h.raw_similarity, h.doc_id, h.parent_id))
        for rank, h in enumerate(hits):
            h.rank = rank
        return hits[:top_k]

    doc_lane = search(REPRESENTATION_KIND_DOCUMENT_SUMMARY, plan.document_summary_top_k) \
        if plan.document_summary_enabled else []
    section_lane = search(REPRESENTATION_KIND_SECTION_SUMMARY, plan.section_summary_top_k) \
        if plan.section_summary_enabled else []
    child_lane = search(REPRESENTATION_KIND_CHILD, plan.global_child_top_k) \
        if plan.global_child_enabled else []

    # ENTITY-CARD-LANE (F2): one card ranks once; every document it
    # evidences receives that rank's RRF vote (bounded per card). The
    # card payload carries doc_ids[]; the LaneHit doc_id is expanded so
    # aggregate_documents_n attributes the vote per document. Cards are
    # ROUTING only — they never become evidence (children prove).
    card_lane: list[LaneHit] = []
    if plan.entity_card_enabled:
        # search() expands each card into per-document votes (doc_ids)
        card_lane = search(REPRESENTATION_KIND_ENTITY_CARD,
                           plan.entity_card_top_k * plan.entity_card_max_docs_per_card)

    documents = aggregate_documents_n(
        [(REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_lane),
         (REPRESENTATION_KIND_SECTION_SUMMARY, section_lane),
         (REPRESENTATION_KIND_CHILD, child_lane),
         (REPRESENTATION_KIND_ENTITY_CARD, card_lane)],
        k=plan.rrf_k)
    selected_documents = documents[:plan.max_documents]
    selected_sections = resolve_sections(selected_documents, plan.max_sections_per_document)

    # -- filtered child deepening: corpus + doc + parent filters ------------
    deepened: dict[str, dict] = {}
    for section in selected_sections:
        rows = search(
            REPRESENTATION_KIND_CHILD,
            plan.max_children_per_section,
            extra={
                "doc_id": section["doc_id"],
                "parent_id": section["parent_id"],
            },
        )
        for row in rows[:plan.max_children_per_section]:
            if row.chunk_id not in deepened:
                deepened[row.chunk_id] = {
                    "chunk_id": row.chunk_id,
                    "doc_id": row.doc_id,
                    "parent_id": row.parent_id,
                    "text": row.text,
                    "source_name": row.source_name,
                    "similarity": row.raw_similarity,
                    "arrival": ARRIVAL_SECTION_LED,
                    "depth_rank": row.rank,
                }

    # -- global child rescue union (recall safety) --------------------------
    rescue: dict[str, dict] = {}
    for hit in child_lane[:plan.global_child_rescue_max]:
        if hit.chunk_id in deepened:
            continue
        if hit.chunk_id not in rescue:
            rescue[hit.chunk_id] = {
                "chunk_id": hit.chunk_id,
                "doc_id": hit.doc_id,
                "parent_id": hit.parent_id,
                "text": hit.text,
                "source_name": hit.source_name,
                "similarity": hit.raw_similarity,
                "arrival": ARRIVAL_GLOBAL_CHILD_RESCUE,
                "global_rank": hit.rank,
            }

    final_candidates: list[dict] = []
    for doc in selected_documents:
        doc_children = [c for c in deepened.values() if c["doc_id"] == doc.doc_id]
        doc_children.sort(key=lambda c: c["depth_rank"])
        for c in doc_children:
            c = dict(c)
            if doc.best_child_rank is not None and any(
                h.chunk_id == c["chunk_id"] for h in doc.global_child_hits
            ):
                c["arrival"] = ARRIVAL_MULTI_REPRESENTATION
            c["document_rank"] = doc.aggregate_rank
            final_candidates.append(c)
    for c in sorted(rescue.values(), key=lambda c: c.get("global_rank", 10**9)):
        final_candidates.append(dict(c))

    # dedupe by canonical chunk identity (deepened first, then rescue)
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for c in final_candidates:
        if c["chunk_id"] in seen_ids:
            continue
        seen_ids.add(c["chunk_id"])
        deduped.append(c)

    # DOCUMENT-REGION-V1: demote at the point where candidates compete
    # GLOBALLY. Sinking noisy children inside their own lane is not
    # enough: per-section deepening takes only max_children_per_section
    # candidates, so a front-matter section's children are admitted
    # regardless of their order within that section (MEASURED: the
    # author biography still arrived at rank 2 with lane-level demotion
    # alone). Here ~30 candidates compete for final_max_children slots,
    # so boilerplate loses to answer-bearing content — while remaining
    # eligible if slots are left over. Stable: order within each group
    # is untouched.
    _noisy_candidates = 0
    _noisy_demoted = 0
    if plan.demote_noisy_regions and region_lookup is not None and deduped:
        try:
            _roles = region_lookup([c["chunk_id"] for c in deduped])
        except Exception:
            _roles = {}
        if _roles:
            from polymath_shared.document_region import is_noisy
            for _c in deduped:
                _c["region_role"] = _roles.get(_c["chunk_id"])
            _before = [c["chunk_id"] for c in deduped]
            _noisy_candidates = sum(
                1 for c in deduped if is_noisy(c.get("region_role")))
            deduped = sorted(
                deduped, key=lambda c: 1 if is_noisy(c.get("region_role")) else 0)
            _noisy_demoted = sum(
                1 for i, c in enumerate(deduped)
                if is_noisy(c.get("region_role")) and _before[i] != c["chunk_id"])
            if _noisy_candidates and not _noisy_demoted:
                # already last: demotion had nothing to move, which is
                # still a contribution (the ordering is correct)
                _noisy_demoted = _noisy_candidates

    # RESCUE-SLOT-RESERVATION-V1: cut to final_max_children WITHOUT
    # letting hierarchy candidates evict the global child lane. The
    # reservation is a floor for rescue, never a quota: unused rescue
    # slots go straight back to the hierarchy, so a corpus with no
    # rescue hits gets byte-identical behaviour to before.
    deduped = _truncate_reserving_rescue(
        deduped, plan.final_max_children, plan.rescue_reserved_slots)

    # -- G3: candidate-set invariant (order only) ---------------------------
    pre_g3 = [c["chunk_id"] for c in deduped]
    post_g3 = list(pre_g3)
    g3_scores: dict[str, float] = {}
    if plan.rerank_enabled and rerank_children is not None and deduped:
        reranked = rerank_children(query, deduped)
        post_g3 = [c["chunk_id"] for c in reranked]
        assert set(post_g3) == set(pre_g3), "G3 changed the candidate set"
        g3_scores = {c["chunk_id"]: c.get("rerank_score") for c in reranked}
        deduped = sorted(
            deduped, key=lambda c: post_g3.index(c["chunk_id"])
        )
        for c in deduped:
            c["rerank_score"] = g3_scores.get(c["chunk_id"])

    # NEIGHBOR-EXPANSION-V1 runs AFTER G3 by construction: the reranker's
    # candidate-set invariant (asserted above) forbids changing the set
    # it scores, and an adjacent chunk is admitted for contiguity, not
    # for relevance — it was never a ranking candidate.
    deduped, neighbors_added = _expand_neighbors(deduped, plan, neighbor_lookup)

    # bounded hierarchical final evidence: per document -> sections ->
    # children; rescue children at the end.
    final_evidence: list[dict] = []
    total = 0
    for doc in selected_documents:
        doc_items = [c for c in deduped if c["doc_id"] == doc.doc_id]
        for c in doc_items:
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
        "lane_sizes": {
            "document_summary": len(doc_lane),
            "section_summary": len(section_lane),
            "global_child": len(child_lane),
        },
        "document_candidates": [
            {
                "doc_id": d.doc_id,
                "aggregate_rank": d.aggregate_rank,
                "aggregate_score": round(d.aggregate_score, 6),
                "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                "representation_kinds_present": d.representation_kinds_present,
                "best_document_summary_rank": d.best_document_summary_rank,
                "best_section_summary_rank": d.best_section_summary_rank,
                "best_child_rank": d.best_child_rank,
            }
            for d in documents
        ],
        "pre_g3_order": pre_g3,
        "post_g3_order": post_g3,
        "g3_scores": g3_scores,
        # PRODUCTION-REALITY-V1: every promoted lane emits BOTH its
        # opportunity and its contribution, so lane_liveness can tell a
        # correct zero from a dead lane on live traffic.
        "rescue_seated": sum(
            1 for c in final_evidence
            if c.get("arrival") == ARRIVAL_GLOBAL_CHILD_RESCUE),
        "rescue_candidates": len(rescue),
        "rescue_reserved_slots": plan.rescue_reserved_slots,
        "neighbors_added": neighbors_added,
        "neighbor_expansion": plan.neighbor_expansion,
        "rerank_enabled": plan.rerank_enabled,
        "demote_noisy_regions": plan.demote_noisy_regions,
        "noisy_candidates": _noisy_candidates,
        "noisy_demoted": _noisy_demoted,
    }

    return Pass1Result(
        query=query,
        plan=plan,
        document_summary_lane=doc_lane,
        section_summary_lane=section_lane,
        global_child_lane=child_lane,
        documents=documents,
        selected_documents=selected_documents,
        selected_sections=selected_sections,
        deepened_children=list(deepened.values()),
        rescue_children=list(rescue.values()),
        final_evidence=final_evidence,
        trace=trace,
    )
