"""Deterministic retrieval primitives (Phase G1).

Three parallel lanes, no lane is a gate:

  document router — RetrievalProfile vs query (conceptual discovery)
  parent router   — parent summaries vs query (topic localization)
  global child    — child chunks vs query (precise evidence recall)

Fusion is reciprocal rank fusion (deterministic). A child hit survives
even when its document scores zero — the hierarchy enriches retrieval;
it never suppresses recall. Reranking (G3) and the neural embedder
contract (G2) attach behind these same primitives.

Graph expansion is bounded: entity-surface matching into Neo4j, at most
GRAPH_HOPS hops, only high/medium traversal-weight predicates from the
rule pack. The graph is an expansion mechanism, never the recall gate.
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
    length = max(len(_TOKEN_RE.findall(body)), 1)
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
class LaneHit:
    id: str
    score: float
    why: str = ""


@dataclass
class RetrievalResult:
    query: str
    doc_ranking: list[LaneHit] = field(default_factory=list)
    parent_ranking: list[LaneHit] = field(default_factory=list)
    child_ranking: list[LaneHit] = field(default_factory=list)
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
    """Execute the three lanes and fuse. Fetchers supply rows:

    fetch_profiles -> [{doc_id, retrieval_profile}]
    fetch_parents  -> [{chunk_id, doc_id, summary}]
    fetch_children -> [{chunk_id, doc_id, parent_id, text}] (fallback lane)
    child_search   -> [{chunk_id, doc_id, parent_id, text, vector_score}] (Qdrant)
    """
    result = RetrievalResult(query=query)

    doc_scores: dict[str, tuple[float, str]] = {}
    for row in fetch_profiles():
        profile = row["retrieval_profile"] or {}
        score, why = score_profile(query, profile)
        if score > 0:
            doc_scores[row["doc_id"]] = (score, "+".join(why) or "profile")
    result.doc_ranking = [
        LaneHit(id=doc_id, score=score, why=why)
        for doc_id, (score, why) in sorted(doc_scores.items(), key=lambda kv: (-kv[1][0], kv[0]))
    ]

    parent_hits: list[LaneHit] = []
    for row in fetch_parents():
        score = lexical_score(query, row.get("summary") or "")
        if score > 0:
            parent_hits.append(LaneHit(id=row["chunk_id"], score=score, why="summary"))
    result.parent_ranking = sorted(parent_hits, key=lambda h: (-h.score, h.id))

    children = child_search(50)
    child_hits: list[LaneHit] = []
    for row in children:
        score = lexical_score(query, row.get("text") or "")
        if score > 0:
            child_hits.append(LaneHit(id=row["chunk_id"], score=score, why="text"))
    result.child_ranking = sorted(child_hits, key=lambda h: (-h.score, h.id))

    # Fusion: doc lane + parents promoted to their documents + children
    # promoted to their documents. Child hits are ALWAYS kept (the
    # document router is never a recall gate).
    parent_doc: dict[str, str] = {}
    for row in fetch_parents():
        parent_doc[row["chunk_id"]] = row["doc_id"]
    child_doc: dict[str, str] = {}
    child_rows: dict[str, dict] = {}
    for row in children:
        child_doc[row["chunk_id"]] = row["doc_id"]
        child_rows[row["chunk_id"]] = row

    fused_docs = rrf([
        [h.id for h in result.doc_ranking],
        [parent_doc.get(h.id, "") for h in result.parent_ranking],
        [child_doc.get(h.id, "") for h in result.child_ranking],
    ])
    selected_doc_ids = [d for d in fused_docs if d]

    # Attach profile summary to each selected document for the trace.
    profile_map = {row["doc_id"]: row["retrieval_profile"] or {} for row in fetch_profiles()}
    result.selected_documents = [
        {
            "doc_id": doc_id,
            "semantic_summary": profile_map.get(doc_id, {}).get("semantic_summary", ""),
            "rank": rank,
        }
        for rank, doc_id in enumerate(selected_doc_ids[:10])
    ]

    # Child evidence: top child hits regardless of document ranking.
    evidence: dict[str, dict] = {}
    for hit in result.child_ranking[:30]:
        row = child_rows.get(hit.id) or {
            "chunk_id": hit.id,
            "doc_id": child_doc.get(hit.id, ""),
            "parent_id": "",
            "text": "",
        }
        evidence[hit.id] = {
            "chunk_id": hit.id,
            "doc_id": row["doc_id"],
            "parent_id": row.get("parent_id") or "",
            "text": row.get("text") or "",
            "score": hit.score,
        }

    # Fallback lane: if Qdrant is down, fetch_children provides texts.
    if not evidence:
        for row in fetch_children(50):
            score = lexical_score(query, row.get("text") or "")
            if score > 0:
                evidence[row["chunk_id"]] = {
                    "chunk_id": row["chunk_id"],
                    "doc_id": row["doc_id"],
                    "parent_id": row.get("parent_id") or "",
                    "text": row.get("text") or "",
                    "score": score,
                }

    # Parent expansion: siblings under the same parent join the bundle.
    expanded: dict[str, dict] = dict(evidence)
    siblings_of = _siblings_for(evidence, fetch_children)
    for chunk_id, siblings in siblings_of.items():
        for sib in siblings:
            expanded[sib["chunk_id"]] = sib

    result.selected_children = sorted(
        expanded.values(), key=lambda c: (-c["score"], c["chunk_id"])
    )[:40]
    return result


def _siblings_for(
    evidence: dict[str, dict],
    fetch_children: Callable[[int], list[dict]],
) -> dict[str, list[dict]]:
    parents = {c["parent_id"] for c in evidence.values() if c.get("parent_id")}
    if not parents:
        return {}
    rows = fetch_children(2000)
    by_parent: dict[str, list[dict]] = {}
    for row in rows:
        by_parent.setdefault(row.get("parent_id") or "", []).append({
            "chunk_id": row["chunk_id"],
            "doc_id": row["doc_id"],
            "parent_id": row.get("parent_id") or "",
            "text": row.get("text") or "",
            "score": 0.0,
        })
    return {p: by_parent.get(p, []) for p in parents}


def graph_expansion(
    entity_surfaces: list[str],
    *,
    expand: Callable[[list[str]], list[dict]],
) -> list[dict]:
    """Bounded graph expansion: match surfaces into Neo4j, walk high/
    medium-weight edges (the rule pack's traversal policy), return the
    facts with provenance. Never a recall gate."""
    if not entity_surfaces:
        return []
    facts = expand(entity_surfaces[:10])
    return facts[:GRAPH_MAX_FACTS]
