"""
LATENT-QUERY-FUSION-V2 · F1 — RankedLane representation (observability only).

Each query (q0 / subquery / bridge) ranks its OWN evidence locally. Before V2, the
candidate engine flattens every query's hits into ONE global RRF dominated by q0, so a
bridge's local rank-1 chunk is truncated before the reranker/C4 ever see it. This module
captures those per-query local ranked lists as first-class ``RankedLane`` objects,
preserving two facts the flatten destroys:

  1. each chunk's **local rank** WITHIN a query+lane (its position in that lane's own list);
  2. each chunk's membership in **multiple lanes** (found by q0-dense AND a bridge-dense).

F1 is representation + observability ONLY: pure, deterministic, no selection. F2 fuses over
these (lineage-aware weighted RRF with bounded local-winner preservation); F3 wires the
fused set into the existing C4 → C5 → CA4 spine. Nothing here privileges any probe.

The builder is duck-typed over ``CandidateEvidence`` (chunk_id / doc_id / query_ids /
arrivals / dense_score / sparse_score), so it is unit-testable with plain stand-ins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# ── canonical retrieval-lane families (coarse modality over the engine's fine arrival labels) ──
MODALITY_DENSE = "DENSE"
MODALITY_SPARSE = "SPARSE"
MODALITY_HIERARCHY = "HIERARCHY"
MODALITY_GRAPH = "GRAPH"
MODALITY_OTHER = "OTHER"

ROLE_Q0 = "q0"
ORIGIN_USER = "USER"

#: engine arrival label → coarse modality. The label strings are the engine's stable lane
#: contract constants (candidate_engine.LANE_*/ARRIVAL_*); duplicated here (not imported) to
#: keep this module free of a candidate_engine import cycle. Unknown labels fall to OTHER.
_MODALITY: dict[str, str] = {
    "HIERARCHICAL_ROUTE": MODALITY_HIERARCHY,
    "GLOBAL_DENSE_CHILD": MODALITY_DENSE,
    "GLOBAL_SPARSE_CHILD": MODALITY_SPARSE,
    "LATENT_RESCUE": MODALITY_DENSE,
    "SHADOW_DUALREAD": MODALITY_DENSE,
    "RESOLUTION_LIFT": MODALITY_DENSE,
    "SEEALSO_FANOUT": MODALITY_GRAPH,
    "GRAPH_DEST": MODALITY_GRAPH,
    "NEIGHBOR_EXPANSION": MODALITY_OTHER,
}


def modality_for(lane: str) -> str:
    """Coarse modality family for an engine arrival label (OTHER when unknown)."""
    return _MODALITY.get(lane, MODALITY_OTHER)


@dataclass(frozen=True)
class LaneResult:
    """One chunk's placement inside a single lane's local ranking."""
    chunk_id: str
    local_rank: int          #: 0-based position within THIS lane's own ranked list
    score: float             #: the lane's own similarity/score at that position
    doc_id: str = ""


@dataclass
class RankedLane:
    """One query's locally-ranked evidence for one retrieval lane.

    ``role``/``origin`` are DESCRIPTIVE provenance, never a selection authority — C4/C5 still
    own admission. ``origin`` for bridge subqueries is enriched at F3 (the plan layer knows
    provenance); at the engine layer a subquery carries its ``qtype`` as ``role`` only.
    """
    query_id: str
    query_text: str
    role: str                #: q0 | <subquery qtype> | BRIDGE … (descriptive)
    origin: str              #: USER | PROFILE | GRAPH | BRIDGE | WILDCARD
    lane: str                #: the engine arrival label (e.g. GLOBAL_DENSE_CHILD)
    modality: str            #: coarse family: DENSE | SPARSE | HIERARCHY | GRAPH | OTHER
    results: list[LaneResult] = field(default_factory=list)

    def rank_of(self, chunk_id: str) -> Optional[int]:
        """This chunk's local rank in this lane, or None if the lane never ranked it."""
        for r in self.results:
            if r.chunk_id == chunk_id:
                return r.local_rank
        return None

    def top(self, n: int) -> list[LaneResult]:
        return self.results[: max(0, n)]

    def to_receipt(self, *, top_n: int = 5) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text[:160],
            "role": self.role,
            "origin": self.origin,
            "lane": self.lane,
            "modality": self.modality,
            "size": len(self.results),
            "top": [
                {"chunk_id": r.chunk_id, "local_rank": r.local_rank, "score": round(r.score, 6), "doc_id": r.doc_id}
                for r in self.results[: max(0, top_n)]
            ],
        }


def _lane_score(item, modality: str) -> float:
    """The lane-appropriate similarity for a candidate (sparse lanes prefer sparse_score)."""
    d = getattr(item, "dense_score", None)
    s = getattr(item, "sparse_score", None)
    if modality == MODALITY_SPARSE:
        return float(s if s is not None else (d if d is not None else 0.0))
    return float(d if d is not None else (s if s is not None else 0.0))


def build_ranked_lanes(
    items: Iterable,
    *,
    primary_query_id: str,
    primary_query_text: str = "",
    query_meta: Optional[dict] = None,
) -> list[RankedLane]:
    """Group candidate items into one ``RankedLane`` per (query_id, lane), preserving each
    query's LOCAL rank order.

    ``items`` must be the per-lane candidate lists BEFORE the union merge (each item then
    carries exactly one arrival and one query_id, and the lists are already in retrieval
    rank order). ``local_rank`` is the item's positional index within its (query_id, lane)
    group — faithful because the engine appends hits in ``LaneHit.rank`` order and never
    reorders a lane list before the union. Deterministic: lane output order follows first
    appearance; result order follows input order.
    """
    query_meta = query_meta or {}
    lanes: dict[tuple[str, str], RankedLane] = {}
    order: list[tuple[str, str]] = []
    for it in items:
        chunk_id = getattr(it, "chunk_id", "") or ""
        if not chunk_id:
            continue
        qids = getattr(it, "query_ids", None) or [primary_query_id]
        arrivals = getattr(it, "arrivals", None) or [""]
        qid = qids[0]
        lane = arrivals[0]
        key = (qid, lane)
        rl = lanes.get(key)
        if rl is None:
            meta = query_meta.get(qid, {})
            is_primary = qid == primary_query_id
            rl = RankedLane(
                query_id=qid,
                query_text=str(meta.get("text") or (primary_query_text if is_primary else "")),
                role=str(meta.get("role") or (ROLE_Q0 if is_primary else "")),
                origin=str(meta.get("origin") or (ORIGIN_USER if is_primary else "")),
                lane=lane,
                modality=modality_for(lane),
            )
            lanes[key] = rl
            order.append(key)
        rl.results.append(
            LaneResult(
                chunk_id=chunk_id,
                local_rank=len(rl.results),  # positional within this (query, lane); lists are in rank order
                score=_lane_score(it, rl.modality),
                doc_id=getattr(it, "doc_id", "") or "",
            )
        )
    return [lanes[k] for k in order]


def lane_memberships(lanes: Iterable[RankedLane]) -> dict[str, list[dict]]:
    """chunk_id → every (query_id, lane, modality, local_rank) that ranked it. The explicit
    proof that multi-lane membership survives (a chunk seen by q0-dense AND a bridge-dense
    keeps BOTH placements, never collapsed to one flattened score)."""
    out: dict[str, list[dict]] = {}
    for rl in lanes:
        for r in rl.results:
            out.setdefault(r.chunk_id, []).append(
                {"query_id": rl.query_id, "lane": rl.lane, "modality": rl.modality, "local_rank": r.local_rank}
            )
    return out


def ranked_lanes_receipt(lanes: list[RankedLane], *, top_n: int = 5) -> dict:
    """JSON-safe observability receipt (``retrieval.ranked_lanes``): every lane's local top-N,
    plus how many chunks are shared across ≥2 lanes (the preserved multi-membership signal)."""
    memberships = lane_memberships(lanes)
    multi = sum(1 for placements in memberships.values() if len(placements) >= 2)
    return {
        "contract": "ranked-lanes-v1",
        "n_lanes": len(lanes),
        "n_queries": len({rl.query_id for rl in lanes}),
        "n_chunks": len(memberships),
        "multi_lane_chunks": multi,
        "lanes": [rl.to_receipt(top_n=top_n) for rl in lanes],
    }
