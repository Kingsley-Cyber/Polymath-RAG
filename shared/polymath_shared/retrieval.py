"""Deterministic retrieval primitives (Phase G1/G2).

Four independently inspectable lanes, no lane is a gate:

  document semantic lane   RetrievalProfile vs query (conceptual discovery)
  parent semantic lane     parent summaries vs query (topic localization)
  child dense lane         Qdrant vectors under the active embed contract
  child lexical lane       exact/sparse term evidence

Fusion is reciprocal rank fusion over RANKS only (G2 gate 6): score
distributions across representations are not comparable, and no
score-normalization coefficient is invented here. A child hit survives
even when its document and parent both score zero — the hierarchy
enriches retrieval; it never suppresses recall.

Every dense hit carries representation provenance: source id,
representation_kind, contract id, raw rank and raw score (G2 gate 3).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")

_STOPWORDS = frozenset(
    "a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being that this these those it its it's they them their there here which who "
    "whom whose what when where why how not no nor so such than too very can could may might "
    "must shall should will would do does did done have has had i you he she we us our your "
    "his her him me my own into over under again once more most other some any all both each "
    "few between during before after above below up down out off".split()
)

LEXICAL_CONTRACT_ID = "lexical-v1"

PROFILE_FIELD_WEIGHTS = {
    "semantic_summary": 3.0,
    "core_concepts": 2.5,
    "use_for_questions_about": 2.0,
    "methods": 2.0,
    "primary_domains": 1.5,
    "secondary_domains": 1.2,
    "problems_addressed": 1.2,
    "connects_to_domains": 1.0,
}

GRAPH_HOPS = 2
GRAPH_MAX_FACTS = 20


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def lexical_score(query: str, text: str) -> float:
    """Deterministic term-overlap score (BM25-flavored, no model)."""
    q = _TOKEN_RE.findall(query.lower())
    if not q:
        return 0.0
    body = text.lower()
    hits = 0
    for term in q:
        if term in _STOPWORDS:
            continue
        count = len(re.findall(re.escape(term), body))
        if count:
            hits += 1 + math.log(1 + count) * 1.2
    return hits / len(q)


def score_profile(query: str, profile: dict) -> tuple[float, list[str]]:
    """Weighted match over the profile fields; returns (score, why)."""
    total = 0.0
    why: list[str] = []
    for field, weight in PROFILE_FIELD_WEIGHTS.items():
        value = profile.get(field)
        if not value:
            continue
        text = " ".join(value) if isinstance(value, list) else str(value)
        s = lexical_score(query, text)
        if s > 0:
            total += weight * s
            why.append(field)
    return total, why


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal rank fusion over ranked id lists (deterministic)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return [item for item, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


@dataclass
class RetrievalHit:
    """One lane hit with representation provenance (G2 gate 3)."""
    source_id: str
    representation_kind: str
    contract_id: str
    raw_score: float = 0.0
    rank: int = -1
    corpus_id: str = ""
    document_id: str = ""
    parent_id: str = ""
    chunk_id: str = ""
    why: str = ""


@dataclass
class RetrievalResult:
    query: str
    document_ranking: list[RetrievalHit] = field(default_factory=list)
    parent_ranking: list[RetrievalHit] = field(default_factory=list)
    child_dense_ranking: list[RetrievalHit] = field(default_factory=list)
    child_lexical_ranking: list[RetrievalHit] = field(default_factory=list)
    selected_documents: list[dict] = field(default_factory=list)
    selected_children: list[dict] = field(default_factory=list)
    graph_facts: list[dict] = field(default_factory=list)


def run_lanes(
    query: str,
    *,
    fetch_profiles: Callable[[], list[dict]],
    fetch_parents: Callable[[], list[dict]],
    fetch_children: Callable[[int], list[dict]],
    child_search: Callable[[int], list[dict]],
) -> RetrievalResult:
    """Execute the four lanes independently, then fuse by rank.

    Fetchers supply rows:

    fetch_profiles -> [{doc_id, retrieval_profile, corpus_id?}]
    fetch_parents  -> [{chunk_id, doc_id, summary}]
    fetch_children -> [{chunk_id, doc_id, parent_id, text, corpus_id?}]
    child_search   -> [{chunk_id, doc_id, parent_id, text, vector_score,
                        contract_id, corpus_id}] (dense lane; may be empty)
    """
    result = RetrievalResult(query=query)

    # -- document semantic lane ---------------------------------------------
    doc_scores: dict[str, tuple[float, str]] = {}
    profile_map: dict[str, dict] = {}
    for row in fetch_profiles():
        profile = row["retrieval_profile"] or {}
        profile_map[row["doc_id"]] = profile
        score, why = score_profile(query, profile)
        if score > 0:
            doc_scores[row["doc_id"]] = (score, "+".join(why) or "profile")
    for rank, (doc_id, (score, why)) in enumerate(
        sorted(doc_scores.items(), key=lambda kv: (-kv[1][0], kv[0]))
    ):
        result.document_ranking.append(RetrievalHit(
            source_id=doc_id,
            representation_kind="document_profile",
            contract_id=LEXICAL_CONTRACT_ID,
            raw_score=score,
            rank=rank,
            document_id=doc_id,
            why=why,
        ))

    # -- parent semantic lane -----------------------------------------------
    parent_rows = fetch_parents()
    parent_hits: list[RetrievalHit] = []
    for row in parent_rows:
        score = lexical_score(query, row.get("summary") or "")
        if score > 0:
            parent_hits.append(RetrievalHit(
                source_id=row["chunk_id"],
                representation_kind="parent_summary",
                contract_id=LEXICAL_CONTRACT_ID,
                raw_score=score,
                document_id=row["doc_id"],
                chunk_id=row["chunk_id"],
                why="summary",
            ))
    result.parent_ranking = sorted(parent_hits, key=lambda h: (-h.raw_score, h.source_id))
    for rank, hit in enumerate(result.parent_ranking):
        hit.rank = rank

    # -- child dense lane (Qdrant under the active contract) ----------------
    # A dense hit requires an actual vector score: rows without one are
    # not dense evidence and must not pollute the fusion with zero-score
    # promotions.
    dense_rows = child_search(50)
    dense_hits: list[RetrievalHit] = []
    for row in dense_rows:
        if not row.get("chunk_id") or row.get("vector_score") is None:
            continue
        dense_hits.append(RetrievalHit(
            source_id=row["chunk_id"],
            representation_kind="child_chunk",
            contract_id=row.get("contract_id") or "unknown",
            raw_score=float(row.get("vector_score") or 0.0),
            corpus_id=row.get("corpus_id", ""),
            document_id=row["doc_id"],
            parent_id=row.get("parent_id", ""),
            chunk_id=row["chunk_id"],
            why="dense",
        ))
    result.child_dense_ranking = sorted(
        dense_hits, key=lambda h: (-h.raw_score, h.source_id)
    )[:50]
    for rank, hit in enumerate(result.child_dense_ranking):
        hit.rank = rank

    # -- child lexical lane (exact/sparse evidence) -------------------------
    child_rows = fetch_children(2000)
    child_texts: dict[str, dict] = {
        row["chunk_id"]: row for row in child_rows if row.get("text")
    }
    lexical_hits: list[RetrievalHit] = []
    for row in child_rows:
        score = lexical_score(query, row.get("text") or "")
        if score > 0:
            lexical_hits.append(RetrievalHit(
                source_id=row["chunk_id"],
                representation_kind="child_chunk",
                contract_id=LEXICAL_CONTRACT_ID,
                raw_score=score,
                corpus_id=row.get("corpus_id", ""),
                document_id=row["doc_id"],
                parent_id=row.get("parent_id", ""),
                chunk_id=row["chunk_id"],
                why="lexical",
            ))
    result.child_lexical_ranking = sorted(
        lexical_hits, key=lambda h: (-h.raw_score, h.source_id)
    )[:50]
    for rank, hit in enumerate(result.child_lexical_ranking):
        hit.rank = rank

    # -- fusion over ranks only (G2 gate 6) ---------------------------------
    parent_doc = {r["chunk_id"]: r["doc_id"] for r in parent_rows}
    dense_doc = {h.chunk_id: h.document_id for h in result.child_dense_ranking}
    lexical_doc = {h.chunk_id: h.document_id for h in result.child_lexical_ranking}

    fused_docs = rrf([
        [h.source_id for h in result.document_ranking],
        [parent_doc.get(h.chunk_id, "") for h in result.parent_ranking],
        [dense_doc.get(h.chunk_id, "") for h in result.child_dense_ranking],
        [lexical_doc.get(h.chunk_id, "") for h in result.child_lexical_ranking],
    ])
    result.selected_documents = [
        {
            "doc_id": doc_id,
            "semantic_summary": profile_map.get(doc_id, {}).get("semantic_summary", ""),
            "rank": rank,
        }
        for rank, doc_id in enumerate([d for d in fused_docs if d][:10])
    ]

    # -- child evidence: dense and lexical union, ranked by RRF --------------
    dense_rows_by_id = {row["chunk_id"]: row for row in dense_rows if row.get("chunk_id")}
    evidence: dict[str, dict] = {}
    for hit in rrf([
        [h.chunk_id for h in result.child_dense_ranking],
        [h.chunk_id for h in result.child_lexical_ranking],
    ]):
        row = dense_rows_by_id.get(hit) or child_texts.get(hit) or {}
        evidence[hit] = {
            "chunk_id": hit,
            "doc_id": row.get("doc_id", ""),
            "parent_id": row.get("parent_id", ""),
            "text": row.get("text", ""),
            "contract_ids": sorted({
                h.contract_id for h in result.child_dense_ranking + result.child_lexical_ranking
                if h.chunk_id == hit
            }),
        }

    # Parent expansion: siblings under the same parent join the bundle.
    parents_of = {c.get("parent_id") for c in evidence.values() if c.get("parent_id")}
    if parents_of:
        for row in child_rows:
            if row.get("parent_id") in parents_of:
                evidence.setdefault(row["chunk_id"], {
                    "chunk_id": row["chunk_id"],
                    "doc_id": row["doc_id"],
                    "parent_id": row.get("parent_id", ""),
                    "text": row.get("text", ""),
                    "contract_ids": [],
                })

    result.selected_children = sorted(
        evidence.values(), key=lambda c: c["chunk_id"]
    )[:40]
    return result


def graph_expansion(
    entity_surfaces: list[str],
    *,
    expand: Callable[[list[str]], list[dict]],
) -> list[dict]:
    """Bounded graph expansion from retrieved evidence seeds.

    MONOTONIC with respect to recall: it adds candidates; it never
    removes independently retrieved ones (G4 policy, tested)."""
    if not entity_surfaces:
        return []
    facts = expand(entity_surfaces[:10])
    return facts[:GRAPH_MAX_FACTS]
