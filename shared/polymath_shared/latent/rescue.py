"""Latent rescue lane (plan §1.5) — HYBRID only, GRAPH inherits.

Two filtered searches with the SAME query vector over the latent point
kinds; collapse by parent; the engine deepens those parents through its
ORIGINAL children. Latent text itself is NEVER evidence. Fail-open with
a hard wall-clock budget: any exception, overrun, or malformed payload
degrades to parents=[] with `degraded` set — retrieval never fails
because enrichment exists."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from polymath_shared.latent.contract import (
    LATENT_KIND_ABSTRACTION,
    LATENT_KIND_TRANSFER,
)

ARRIVAL_LATENT_RESCUE = "LATENT_RESCUE"


@dataclass
class LatentParent:
    parent_id: str
    doc_id: str
    source_name: str
    best_score: float
    channels: dict = field(default_factory=dict)   # kind -> best rank


@dataclass
class LatentRescue:
    parents: list[LatentParent] = field(default_factory=list)
    degraded: str | None = None
    latency_ms: float = 0.0


def latent_rescue_parents(
    qvec: list[float],
    *,
    corpus_id: str,
    plan,
    routing_search,
    skip_parent_ids: frozenset[str] = frozenset(),
    clock=time.monotonic,
) -> LatentRescue:
    t0 = clock()
    budget_s = getattr(plan, "latent_budget_ms", 250) / 1000.0
    by_parent: dict[str, LatentParent] = {}
    try:
        for kind, top_k in (
                (LATENT_KIND_ABSTRACTION,
                 getattr(plan, "latent_abstraction_top_k", 8)),
                (LATENT_KIND_TRANSFER,
                 getattr(plan, "latent_transfer_top_k", 8))):
            if clock() - t0 > budget_s:
                return LatentRescue(parents=[], degraded="budget_exceeded",
                                    latency_ms=(clock() - t0) * 1000)
            rows = routing_search("", qvec, {
                "representation_kind": kind, "corpus_id": corpus_id})[:top_k]
            for rank, row in enumerate(rows):
                payload = row.get("payload") or {}
                pid = payload.get("parent_id") or ""
                if not pid or pid in skip_parent_ids:
                    continue
                score = float(row.get("score") or 0.0)
                lp = by_parent.get(pid)
                if lp is None:
                    lp = by_parent[pid] = LatentParent(
                        parent_id=pid,
                        doc_id=payload.get("doc_id") or "",
                        source_name=payload.get("source_name") or "",
                        best_score=score)
                lp.best_score = max(lp.best_score, score)
                lp.channels[kind] = min(lp.channels.get(kind, rank), rank)
    except Exception as exc:
        return LatentRescue(parents=[], degraded=f"{type(exc).__name__}",
                            latency_ms=(clock() - t0) * 1000)
    parents = sorted(by_parent.values(),
                     key=lambda p: (-p.best_score, p.parent_id))
    parents = parents[: getattr(plan, "latent_max_parents", 3)]
    return LatentRescue(parents=parents,
                        latency_ms=(clock() - t0) * 1000)
