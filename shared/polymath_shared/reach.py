"""R1E Pass-2 corpus reach: complementary documents beyond the direct
Pass-1 winner set.

DAG, no recursion:
    query -> Pass 1 -> ConceptState -> Pass 2 -> stop

Pass 2 is SUMMARY-LED over documents EXCLUDED at retrieval time
(doc_id NOT IN excluded set), using a deterministic retrieval
representation = original query + bounded Pass-1 concepts/themes
(no LLM, no HyDE, no free-form questions). Exact evidence remains
child text; reach evidence is tagged reach_pass=2 with seed
provenance and is NEVER direct factual support.

ConceptState admission is deterministic and provenance-bound:
  - profile core concepts of selected documents
  - terms repeated across >=2 selected children
  - admitted entity surfaces attached to selected evidence
  - predicates of facts evidenced by selected children
  - terms of selected document summaries
Generic bare heads (the frozen entity-admission GENERIC_HEAD
vocabulary) never become high-authority expansion seeds.

SUMMARIES ROUTE. CHILDREN PROVE. Pass 1 is never rewritten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from polymath_shared.entity_admission import GENERIC_HEAD
from polymath_shared.pass1 import LaneHit, Pass1Result, aggregate_documents_n

REACH_PLAN_VERSION = "corpus-reach-v1"

PASS1_DIRECT = "PASS1_DIRECT"
PASS2_CORPUS_REACH = "PASS2_CORPUS_REACH"

ARRIVAL_REACH_SECTION_LED = "REACH_SECTION_LED"
ARRIVAL_REACH_LEXICAL = "REACH_LEXICAL"


@dataclass(frozen=True)
class CorpusReachPlan:
    plan_version: str = REACH_PLAN_VERSION
    enabled: bool = True
    exclude_pass1_documents: bool = True

    max_seed_concepts: int = 6

    document_summary_top_k: int = 15
    section_summary_top_k: int = 15
    lexical_enabled: bool = False
    lexical_top_k: int = 15

    rrf_k: int = 60

    max_reach_documents: int = 3
    max_sections_per_document: int = 2
    max_children_per_section: int = 2
    max_reach_children: int = 6

    rerank_enabled: bool = True


REACH_DEFAULT_PLAN = CorpusReachPlan()

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
_STOP = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were be "
    "been being that this these those it its they them their there here which who whom whose "
    "what when where why how not no nor so such than too very can could may might must shall "
    "should will would do does did done have has had i you he she we us our your his her him "
    "me my own into over under again once more most other some any all both each few between "
    "during before after above below up down out off about also just only because while since "
    "through against after before during between into like make use one two new first last next "
    "same different many much little several various every within without upon via per "
    "actions additional alter attributing provides makes gives requires involves becomes "
    "remains appears seems".split()
)


def _is_content_term(term: str) -> bool:
    words = [w for w in term.split() if w not in _STOP and len(w) >= 3]
    return len(words) >= 1 and words[-1].lower() not in GENERIC_HEAD


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP}


@dataclass
class Pass1ConceptState:
    original_query: str
    concepts: list[dict]
    entities: list[dict]
    relationships: list[str]
    section_themes: list[str]
    source_doc_ids: list[str]

    @property
    def expansion_terms(self) -> list[str]:
        return [c["term"] for c in self.concepts]

    def serialized_query(self) -> str:
        """Deterministic Pass-2 retrieval input: original query first,
        then canonical concept terms. Recorded in the trace."""
        if not self.expansion_terms:
            return self.original_query
        return self.original_query + " " + " ".join(self.expansion_terms)


def _admit_term(term: str) -> bool:
    """Generic-seed guard: bare generic heads never become expansion
    seeds (entity-admission lessons; frozen GENERIC_HEAD vocabulary).
    Stopwords and near-stopword terms are never admitted."""
    return _is_content_term(term)


def build_concept_state(
    pass1_result: Pass1Result,
    *,
    max_seed_concepts: int = 6,
    profile_concepts: Optional[dict[str, list[str]]] = None,
    entities_for_evidence: Optional[Callable[[list[str]], list[dict]]] = None,
    predicates_for_evidence: Optional[Callable[[list[str]], list[str]]] = None,
) -> Pass1ConceptState:
    profile_concepts = profile_concepts or {}
    selected_docs = [d.doc_id for d in pass1_result.selected_documents]
    children = pass1_result.final_evidence
    child_texts = [c.get("text") or "" for c in children]
    child_ids = [c["chunk_id"] for c in children]

    scored: dict[str, tuple[int, list[str]]] = {}

    def add(term: str, weight: int, reason: str) -> None:
        term = " ".join(term.split())
        if not term or not _admit_term(term):
            return
        if term not in scored:
            scored[term] = (weight, [])
        if weight > scored[term][0]:
            scored[term] = (weight, scored[term][1])
        if reason not in scored[term][1]:
            scored[term][1].append(reason)

    # profile core concepts of selected documents (strongest signal)
    for doc_id in selected_docs:
        for concept in profile_concepts.get(doc_id, []):
            if concept:
                add(concept.lower(), 5, "profile_core_concept")
    # admitted entities attached to selected evidence
    if entities_for_evidence is not None and child_ids:
        for ent in entities_for_evidence(child_ids):
            surface = (ent.get("normalized_surface") or "").strip()
            if surface:
                add(surface.lower(), 4, "entity")
    # predicates of facts evidenced by selected children
    if predicates_for_evidence is not None and child_ids:
        for pred in predicates_for_evidence(child_ids):
            add(pred.replace("_", " ").lower(), 3, "relationship")
    # terms repeated across >=2 selected children
    doc_freq: dict[str, int] = {}
    for text in child_texts:
        for t in _tokens(text):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    for t, n in doc_freq.items():
        if n >= 2:
            add(t, 2, "multi_child")
    # selected document summary terms (weakest)
    for d in pass1_result.selected_documents:
        for h in d.document_summary_hits:
            for t in _tokens(h.text):
                add(t, 1, "summary")

    ranked = sorted(
        ((term, weight, reasons) for term, (weight, reasons) in scored.items()),
        key=lambda x: (-x[1], x[0]),
    )[:max_seed_concepts]

    return Pass1ConceptState(
        original_query=pass1_result.query,
        concepts=[{"term": term, "weight": weight, "reasons": reasons,
                   "provenance": "pass1"}
                  for term, weight, reasons in ranked],
        entities=[e for e in (entities_for_evidence(child_ids) if entities_for_evidence and child_ids else [])],
        relationships=predicates_for_evidence(child_ids) if predicates_for_evidence and child_ids else [],
        section_themes=[s.get("summary_id", "") for s in pass1_result.selected_sections],
        source_doc_ids=selected_docs,
    )


@dataclass
class ReachDocumentCandidate:
    doc_id: str
    corpus_id: str
    summary_hits: list[LaneHit] = field(default_factory=list)
    section_hits: list[LaneHit] = field(default_factory=list)
    lexical_hits: list[LaneHit] = field(default_factory=list)
    rrf_contributions: dict[str, float] = field(default_factory=dict)
    aggregate_score: float = 0.0
    aggregate_rank: int = -1
    seed_concepts: list[str] = field(default_factory=list)


@dataclass
class ReachResult:
    query: str
    plan: CorpusReachPlan
    concept_state: Pass1ConceptState
    reach_query: str
    excluded_doc_ids: list[str]
    documents: list[ReachDocumentCandidate]
    selected_documents: list[ReachDocumentCandidate]
    selected_sections: list[dict]
    final_evidence: list[dict]
    trace: dict


def reach_retrieve(
    query: str,
    pass1_result: Pass1Result,
    *,
    plan: CorpusReachPlan = REACH_DEFAULT_PLAN,
    embed_query: Callable[[str], list[float]],
    routing_search: Callable[[str, list[float], dict], list[dict]],
    lexical_search: Optional[Callable[[str, int], list[LaneHit]]] = None,
    rerank_children: Optional[Callable[[str, list[dict]], list[dict]]] = None,
    concept_state: Optional[Pass1ConceptState] = None,
) -> ReachResult:
    excluded = sorted({d.doc_id for d in pass1_result.selected_documents})
    concept_state = concept_state or build_concept_state(pass1_result)
    reach_query = concept_state.serialized_query()
    qvec = embed_query(reach_query)

    def search(kind: str, top_k: int) -> list[LaneHit]:
        filters = {
            "representation_kind": kind,
            "corpus_id": (pass1_result.plan.corpus_ids or (None,))[0],
            "exclude_doc_ids": excluded,
        }
        hits: list[LaneHit] = []
        rows = routing_search("", qvec, filters)[:top_k]
        for i, row in enumerate(rows):
            payload = row.get("payload") or {}
            hits.append(LaneHit(
                representation_kind=kind, rank=i,
                raw_similarity=float(row.get("score") or 0.0),
                corpus_id=payload.get("corpus_id", ""),
                doc_id=payload.get("doc_id", ""),
                parent_id=payload.get("parent_id", ""),
                chunk_id=payload.get("chunk_id") or "",
                summary_id=payload.get("summary_id") or "",
                source_name=payload.get("source_name", ""),
                text=payload.get("text", ""),
            ))
        return hits

    doc_lane = search("routing_document_summary", plan.document_summary_top_k)
    section_lane = search("routing_section_summary", plan.section_summary_top_k)
    lexical_lane: list[LaneHit] = []
    if plan.lexical_enabled and lexical_search is not None:
        hits = lexical_search(reach_query, plan.lexical_top_k)
        lexical_lane = [h for h in hits if h.doc_id not in excluded]
        for rank, h in enumerate(lexical_lane):
            h.rank = rank

    lanes = [
        ("routing_document_summary", doc_lane),
        ("routing_section_summary", section_lane),
    ]
    if lexical_lane:
        lanes.append(("reach_lexical", lexical_lane))

    by_doc: dict[str, ReachDocumentCandidate] = {}
    for kind, lane in lanes:
        for hit in lane:
            cand = by_doc.setdefault(hit.doc_id, ReachDocumentCandidate(
                doc_id=hit.doc_id, corpus_id=hit.corpus_id))
            if kind == "routing_document_summary":
                cand.summary_hits.append(hit)
            elif kind == "routing_section_summary":
                cand.section_hits.append(hit)
            else:
                cand.lexical_hits.append(hit)
            cand.rrf_contributions[kind] = cand.rrf_contributions.get(kind, 0.0) + \
                1.0 / (plan.rrf_k + hit.rank + 1)
    documents = list(by_doc.values())
    for cand in documents:
        cand.aggregate_score = sum(cand.rrf_contributions.values())
        # seed provenance: concepts whose terms appear in the doc summary
        cand.seed_concepts = [
            c["term"] for c in concept_state.concepts
            if any(c["term"].lower() in (h.text or "").lower() for h in cand.summary_hits)
        ]
    documents.sort(key=lambda c: (-c.aggregate_score, c.doc_id))
    for rank, cand in enumerate(documents):
        cand.aggregate_rank = rank
    selected_documents = documents[: plan.max_reach_documents]

    # section resolution within reach documents
    sections: list[dict] = []
    for doc in selected_documents:
        for hit in sorted(doc.section_hits, key=lambda h: h.rank):
            if hit.parent_id not in {s["parent_id"] for s in sections}:
                sections.append({
                    "doc_id": doc.doc_id, "parent_id": hit.parent_id,
                    "summary_id": hit.summary_id, "source_name": hit.source_name,
                    "best_section_rank": hit.rank, "from": ["reach_section"],
                })
    sections = sections[: plan.max_sections_per_document * len(selected_documents)]

    # filtered child deepening with the Pass-2 retrieval representation
    evidence: dict[str, dict] = {}
    for section in sections:
        filters = {
            "representation_kind": "routing_child",
            "corpus_id": (pass1_result.plan.corpus_ids or (None,))[0],
            "doc_id": section["doc_id"],
            "parent_id": section["parent_id"],
        }
        rows = routing_search("", qvec, filters)[: plan.max_children_per_section]
        for row in rows:
            payload = row.get("payload") or {}
            cid = payload.get("chunk_id") or ""
            if cid not in evidence:
                evidence[cid] = {
                    "chunk_id": cid,
                    "doc_id": payload.get("doc_id", ""),
                    "parent_id": payload.get("parent_id", ""),
                    "text": payload.get("text", ""),
                    "source_name": payload.get("source_name", ""),
                    "similarity": float(row.get("score") or 0.0),
                    "arrival": ARRIVAL_REACH_SECTION_LED,
                    "reach_pass": 2,
                    "seed_concepts": next(
                        (d.seed_concepts for d in selected_documents
                         if d.doc_id == payload.get("doc_id")), []),
                }
    # lexical reach children (only if the lexical lane is qualified on)
    for hit in lexical_lane:
        if hit.chunk_id in evidence:
            continue
        if hit.doc_id not in {d.doc_id for d in selected_documents}:
            continue
        evidence[hit.chunk_id] = {
            "chunk_id": hit.chunk_id,
            "doc_id": hit.doc_id,
            "parent_id": hit.parent_id,
            "text": hit.text,
            "source_name": hit.source_name,
            "similarity": hit.raw_similarity,
            "arrival": ARRIVAL_REACH_LEXICAL,
            "reach_pass": 2,
            "seed_concepts": [],
        }

    final_evidence = sorted(evidence.values(), key=lambda c: (
        c["doc_id"], c.get("arrival") or "", c["chunk_id"]))[: plan.max_reach_children]

    pre_g3 = [c["chunk_id"] for c in final_evidence]
    post_g3 = list(pre_g3)
    g3_scores: dict[str, float] = {}
    if plan.rerank_enabled and rerank_children is not None and final_evidence:
        reranked = rerank_children(query, final_evidence)
        post_g3 = [c["chunk_id"] for c in reranked]
        assert set(post_g3) == set(pre_g3), "G3 changed the reach candidate set"
        g3_scores = {c["chunk_id"]: c.get("rerank_score") for c in reranked}
        final_evidence = sorted(final_evidence, key=lambda c: post_g3.index(c["chunk_id"]))
        for c in final_evidence:
            c["g3_score"] = g3_scores.get(c["chunk_id"])

    trace = {
        "plan": plan.plan_version,
        "reach_query": reach_query,
        "concept_state": {
            "concepts": concept_state.concepts,
            "relationships": concept_state.relationships,
            "source_doc_ids": concept_state.source_doc_ids,
        },
        "excluded_doc_ids": excluded,
        "lane_sizes": {
            "document_summary": len(doc_lane),
            "section_summary": len(section_lane),
            "lexical": len(lexical_lane),
        },
        "pre_g3_order": pre_g3,
        "post_g3_order": post_g3,
    }

    return ReachResult(
        query=query,
        plan=plan,
        concept_state=concept_state,
        reach_query=reach_query,
        excluded_doc_ids=excluded,
        documents=documents,
        selected_documents=selected_documents,
        selected_sections=sections,
        final_evidence=final_evidence,
        trace=trace,
    )
