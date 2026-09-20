"""
LATENT-QUERY-FUSION-V2 · F2 — deterministic lineage-aware weighted RRF over RankedLanes.

The pre-V2 union sets ``fused_score = best-single-query RRF + agreement``, so a bridge's local
rank-1 chunk (single-lane RRF ≈ 1/(60+1)) loses to a q0 multi-lane chunk and is truncated before
C4/C5 ever judge it. F2 replaces that flatten with a two-part rule over the F1 ``RankedLane`` objects:

  1. **weighted RRF** — ``fused(chunk) = Σ over lanes L containing chunk: weight(L) / (k + local_rank_L)``.
     ``weight`` is per LINEAGE CLASS (q0 / subquery / bridge / profile / graph), so a query's provenance
     — not its raw candidate count — sets its pull. Every contributing (query, lane, local_rank, weight)
     term is retained (many-to-one lineage is NOT collapsed; C4 needs the paths).
  2. **bounded local-winner preservation** — each query's own top-N (by an intra-query RRF over that
     query's lanes) is reserved so it SURVIVES the ``merged_candidate_max`` cut, even when its fused
     score ranks below the cap. This is what lets a bridge's local winner reach C4/C5.

F2 produces a CANDIDATE ordering only. It does NOT seat anything: C4 (semantic gate) and C5 (portfolio)
still judge every candidate at F3, and a preserved winner gets no automatic final seat. Weights are
PROVISIONAL (owner: measured at F4, never frozen here); COMPLEMENTARY/DIVERGENT are C5 seat roles decided
downstream, NOT fusion weights — a bridge carries one provisional weight and is still judged.

Pure + deterministic (ties broken by chunk_id). Duck-typed over ``ranked_lane.RankedLane``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from polymath_shared.ranked_lane import MODALITY_GRAPH, ROLE_Q0, RankedLane

# ── lineage weight classes (a query's provenance → its pull in the fusion) ──────────────────────────
CLASS_Q0 = "Q0"
CLASS_SUBQUERY = "SUBQUERY"     # USER-origin decomposition subquery
CLASS_BRIDGE = "BRIDGE"         # BRIDGE-origin latent subquery (C4/C5 refine to COMPLEMENTARY/DIVERGENT)
CLASS_PROFILE = "PROFILE"       # PROFILE-origin (Scout) expansion
CLASS_GRAPH = "GRAPH"           # graph-origin / graph-modality lane on a non-q0 query
CLASS_OTHER = "OTHER"


@dataclass(frozen=True)
class FusionWeights:
    """Per-lineage-class weights for the inter-query weighted RRF.

    PROVISIONAL defaults (owner: measured at F4, NEVER frozen here). q0 leads; a bridge carries ONE
    weight (the COMPLEMENTARY/DIVERGENT split is a C5 seat decision at F3, not a fusion weight).
    """
    q0: float = 1.0
    subquery: float = 0.6
    bridge: float = 0.5
    profile: float = 0.6
    graph: float = 0.5
    other: float = 0.4

    def weight_for(self, cls: str) -> float:
        return {
            CLASS_Q0: self.q0,
            CLASS_SUBQUERY: self.subquery,
            CLASS_BRIDGE: self.bridge,
            CLASS_PROFILE: self.profile,
            CLASS_GRAPH: self.graph,
            CLASS_OTHER: self.other,
        }.get(cls, self.other)

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "FusionWeights":
        """Config-driven weights via `POLYMATH_FUSION_W_<CLASS>` (F4 step-6 calibration surface). The
        defaults ARE the A/B-validated values — unfitted, never tuned to a specific benchmark query
        (owner: values must generalize). An unset/invalid var falls back to its default."""
        import os
        e = env if env is not None else os.environ

        def g(name: str, default: float) -> float:
            try:
                return float(e.get(name, default))
            except (TypeError, ValueError):
                return default

        return cls(q0=g("POLYMATH_FUSION_W_Q0", 1.0), subquery=g("POLYMATH_FUSION_W_SUBQUERY", 0.6),
                   bridge=g("POLYMATH_FUSION_W_BRIDGE", 0.5), profile=g("POLYMATH_FUSION_W_PROFILE", 0.6),
                   graph=g("POLYMATH_FUSION_W_GRAPH", 0.5), other=g("POLYMATH_FUSION_W_OTHER", 0.4))


def lineage_class(lane: RankedLane) -> str:
    """Classify a lane by its query's provenance. ``role == q0`` dominates (q0's OWN graph lane is still
    q0, not GRAPH); otherwise origin decides, with graph modality as the fallback graph signal."""
    if lane.role == ROLE_Q0:
        return CLASS_Q0
    origin = (lane.origin or "").upper()
    if origin in ("BRIDGE", "CORPUS_EXPLORE"):
        # CORPUS-EXPLORER-V1: corpus-activation-derived exploration rides the SAME fusion class/weight as
        # a Scout-derived BRIDGE (owner lock: V1 tests the activation source, not a new ranking policy).
        return CLASS_BRIDGE
    if origin == "PROFILE":
        return CLASS_PROFILE
    if origin == "GRAPH" or lane.modality == MODALITY_GRAPH:
        return CLASS_GRAPH
    if origin == "USER":
        return CLASS_SUBQUERY
    return CLASS_OTHER


def _rrf(k: int, local_rank: int) -> float:
    """Reciprocal-rank term for a 0-based local rank."""
    return 1.0 / (k + local_rank)


@dataclass(frozen=True)
class Contribution:
    """One lane's contribution to a chunk's fused score (a lineage path, never collapsed away)."""
    query_id: str
    lane: str
    modality: str
    lineage_class: str
    local_rank: int
    weight: float
    term: float          #: weight * rrf(k, local_rank)


@dataclass
class FusedChunk:
    chunk_id: str
    doc_id: str
    fused_score: float
    preserved: bool
    contributions: list[Contribution] = field(default_factory=list)

    @property
    def query_ids(self) -> list[str]:
        seen: list[str] = []
        for c in self.contributions:
            if c.query_id not in seen:
                seen.append(c.query_id)
        return seen

    def to_receipt(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "fused_score": round(self.fused_score, 6),
            "preserved": self.preserved,
            "query_ids": self.query_ids,
            "contributions": [
                {"query_id": c.query_id, "lane": c.lane, "lineage_class": c.lineage_class,
                 "local_rank": c.local_rank, "weight": c.weight, "term": round(c.term, 6)}
                for c in self.contributions
            ],
        }


@dataclass
class FusedResult:
    ordered: list[FusedChunk]        #: capped, preserved-guaranteed, deterministic (desc fused_score, then id)
    preserved_ids: set               #: chunk_ids reserved by per-query top-N
    trace: dict

    def ids(self) -> list[str]:
        return [fc.chunk_id for fc in self.ordered]


def preserved_winners(lanes: Iterable[RankedLane], *, k: int = 60, top_n: int = 5) -> set:
    """Each query's local top-N by an INTRA-query RRF over that query's own lanes (dense+sparse+…).
    This is the "RankedLane per query" of the architectural lock — the winners that must survive the
    inter-query cut. top_n <= 0 disables preservation (empty set)."""
    if top_n <= 0:
        return set()
    by_query: dict[str, dict[str, float]] = {}
    for lane in lanes:
        scores = by_query.setdefault(lane.query_id, {})
        for r in lane.results:
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + _rrf(k, r.local_rank)
    preserved: set = set()
    for scores in by_query.values():
        for cid, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]:
            preserved.add(cid)
    return preserved


def _apply_cap(ranked: list[FusedChunk], *, cap: int) -> list[FusedChunk]:
    """Truncate to a STRICT ceiling of ``cap`` candidates (V2 changes WHO survives the cut, never
    expands it). PRESERVED chunks take seats first — so a query's local winner survives even when its
    fused score ranks below the cap — and the remaining seats fill by fused score. The output is never
    longer than ``cap``; if preserved chunks alone exceed ``cap``, the top-``cap`` preserved (by fused
    score) are kept."""
    if cap <= 0 or len(ranked) <= cap:
        return ranked
    preserved = [fc for fc in ranked if fc.preserved]        # both already in fused (desc score) order
    others = [fc for fc in ranked if not fc.preserved]
    keep: list[FusedChunk] = preserved[:cap]                 # preserved reserve seats, up to the ceiling
    for fc in others:                                        # fill the rest by fused score
        if len(keep) >= cap:
            break
        keep.append(fc)
    return sorted(keep, key=lambda fc: (-fc.fused_score, fc.chunk_id))


def fuse_ranked_lanes(
    lanes: Iterable[RankedLane],
    *,
    weights: Optional[FusionWeights] = None,
    k: int = 60,
    preserve_top_n: int = 5,
    cap: int = 120,
) -> FusedResult:
    """Fuse per-(query, lane) RankedLanes into one candidate ordering via lineage-aware weighted RRF
    with bounded local-winner preservation. Pure + deterministic. Produces candidates only — C4/C5
    (F3) still gate every one."""
    weights = weights or FusionWeights()
    lanes = list(lanes)
    by_chunk: dict[str, FusedChunk] = {}
    for lane in lanes:
        cls = lineage_class(lane)
        w = weights.weight_for(cls)
        for r in lane.results:
            fc = by_chunk.get(r.chunk_id)
            if fc is None:
                fc = FusedChunk(chunk_id=r.chunk_id, doc_id=r.doc_id, fused_score=0.0, preserved=False)
                by_chunk[r.chunk_id] = fc
            term = w * _rrf(k, r.local_rank)
            fc.fused_score += term
            fc.contributions.append(Contribution(
                query_id=lane.query_id, lane=lane.lane, modality=lane.modality, lineage_class=cls,
                local_rank=r.local_rank, weight=w, term=term,
            ))
    preserved = preserved_winners(lanes, k=k, top_n=preserve_top_n)
    for cid in preserved:
        if cid in by_chunk:
            by_chunk[cid].preserved = True
    ranked = sorted(by_chunk.values(), key=lambda fc: (-fc.fused_score, fc.chunk_id))
    capped = _apply_cap(ranked, cap=cap)
    preserved_in = {fc.chunk_id for fc in capped if fc.preserved}
    trace = {
        "contract": "ranked-fusion-v1",
        "n_lanes": len(lanes),
        "n_chunks": len(by_chunk),
        "n_preserved": len(preserved & set(by_chunk)),
        "preserved_survived_cap": len(preserved_in),
        "cap": cap,
        "k": k,
        "preserve_top_n": preserve_top_n,
        "weights": {"q0": weights.q0, "subquery": weights.subquery, "bridge": weights.bridge,
                    "profile": weights.profile, "graph": weights.graph, "other": weights.other},
        "top": [fc.to_receipt() for fc in capped[:8]],
    }
    return FusedResult(ordered=capped, preserved_ids=preserved & set(by_chunk), trace=trace)
