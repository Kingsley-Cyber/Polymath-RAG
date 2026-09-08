"""S8 shadow runtime route — global profile → parent-map → child deepening, measured only.

RETRIEVAL-MIGRATION-DEPENDENCY-V1 §17 (shadow phase) / roadmap S8. Runs the vNext
semantic routing path as a SHADOW so its coverage can be recorded against the current
retrieval, with **no production rank effect**:

    query vector
        │
        ├─ 1. profile search  → nominated document ids          (profile_doc_candidates)
        │
        ├─ 2. ONE filtered parent-map search across the nominated docs
        │        (§17 performance rule: never one search per doc) → routing parents
        │                                                         (parent_map_candidates)
        │                                                         (resolved_parent_ids)
        │
        └─ 3. child deepening under the resolved parents         (shadow_child_candidates)

It returns a `ShadowReceipt` carrying the §17 shadow fields plus per-step latency; the
overlap-with-final and gold-hit measurements are computed by the caller (the canary /
the future dual-read lane) from the receipt, so this module stays a pure route.

Store-abstracted exactly like `candidate_engine`: the three searches are injected
callables, so the routing logic is pure and unit-testable with fakes, and the SAME module
later backs the S9 dual-read lane over the real Qdrant store. It never mutates retrieval,
ranking, `QUERY_READY`, or any store — additive and reversible by construction.

Injected search contracts (each takes an already-embedded query vector; all return
descending-by-score dict rows):

    profile_search(query_vec, k)              -> [{"doc_id", "score", ...}]
    map_search(query_vec, doc_ids, k)         -> [{"doc_id", "parent_id", "alias", "score", ...}]
    child_search(query_vec, doc_parent_pairs, k) -> [{"chunk_id", "doc_id", "parent_id", "score", ...}]

`map_search` MUST issue a single store query filtered to `doc_ids` (the §17 rule);
`child_search` receives the resolved `(doc_id, parent_id)` pairs and localizes the child
lane to them.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

ProfileSearch = Callable[[list[float], int], list[dict]]
MapSearch = Callable[[list[float], Sequence[str], int], list[dict]]
ChildSearch = Callable[[list[float], Sequence[tuple[str, str]], int], list[dict]]

SHADOW_ROUTE_VERSION = "shadow-route-v1"

#: Default candidate widths — deliberately generous (shadow measures coverage, not a
#: ranked turn); the caller tunes them per experiment.
DEFAULT_K_DOCS = 8
DEFAULT_K_PARENTS = 24
DEFAULT_K_CHILDREN = 40


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


@dataclass(frozen=True)
class ShadowReceipt:
    """The §17 shadow-phase receipt. `parent_map_candidates` keeps the raw map rows
    (doc_id/parent_id/alias/score) so misses are attributable; the id tuples are the
    deduped, order-preserving projections used for the coverage math."""

    profile_doc_candidates: tuple[str, ...]
    parent_map_candidates: tuple[dict, ...]
    resolved_parent_ids: tuple[str, ...]
    shadow_child_candidates: tuple[str, ...]
    latency_ms: dict
    degraded: tuple[str, ...] = ()
    version: str = SHADOW_ROUTE_VERSION

    def as_receipt(self) -> dict:
        return {
            "profile_doc_candidates": list(self.profile_doc_candidates),
            "parent_map_candidates": [dict(p) for p in self.parent_map_candidates],
            "resolved_parent_ids": list(self.resolved_parent_ids),
            "shadow_child_candidates": list(self.shadow_child_candidates),
            "latency_ms": dict(self.latency_ms),
            "degraded": list(self.degraded),
            "version": self.version,
        }


def shadow_route(
    query_vec: list[float],
    *,
    profile_search: ProfileSearch,
    map_search: MapSearch,
    child_search: ChildSearch,
    k_docs: int = DEFAULT_K_DOCS,
    k_parents: int = DEFAULT_K_PARENTS,
    k_children: int = DEFAULT_K_CHILDREN,
) -> ShadowReceipt:
    """Run profile → parent-map → child as a shadow and return the measurement receipt.

    A failure or empty result at any stage degrades gracefully (recorded in `degraded`)
    and short-circuits the downstream stages — a shadow never raises into the caller.
    """
    degraded: list[str] = []
    t0 = time.monotonic()

    # 1. nominate documents from the global profile index.
    try:
        prof_rows = profile_search(query_vec, k_docs) or []
    except Exception:  # noqa: BLE001 — a shadow must never raise into production.
        prof_rows, _ = [], degraded.append("profile_search_error")
    doc_ids = tuple(_dedupe(r.get("doc_id") for r in prof_rows))
    t1 = time.monotonic()

    # 2. ONE filtered parent-map search across the nominated docs (§17 performance rule).
    map_rows: list[dict] = []
    if doc_ids:
        try:
            map_rows = map_search(query_vec, list(doc_ids), k_parents) or []
        except Exception:  # noqa: BLE001
            degraded.append("map_search_error")
    elif not degraded:
        degraded.append("no_nominated_docs")
    resolved = tuple(_dedupe(m.get("parent_id") for m in map_rows))
    t2 = time.monotonic()

    # 3. deepen to child candidates under the resolved parents.
    child_rows: list[dict] = []
    if resolved:
        pairs, seen = [], set()
        for m in map_rows:
            pr = (m.get("doc_id", ""), m.get("parent_id", ""))
            if pr[1] and pr not in seen:
                seen.add(pr)
                pairs.append(pr)
        try:
            child_rows = child_search(query_vec, pairs, k_children) or []
        except Exception:  # noqa: BLE001
            degraded.append("child_search_error")
    elif doc_ids and not any(d.endswith("_error") for d in degraded):
        degraded.append("no_resolved_parents")
    child_ids = tuple(_dedupe(c.get("chunk_id") for c in child_rows))
    t3 = time.monotonic()

    return ShadowReceipt(
        profile_doc_candidates=doc_ids,
        parent_map_candidates=tuple(dict(m) for m in map_rows),
        resolved_parent_ids=resolved,
        shadow_child_candidates=child_ids,
        latency_ms={
            "profile": round((t1 - t0) * 1000, 2),
            "map": round((t2 - t1) * 1000, 2),
            "child": round((t3 - t2) * 1000, 2),
            "total": round((t3 - t0) * 1000, 2),
        },
        degraded=tuple(degraded),
    )


# --- coverage math (pure; the caller measures the receipt against the current lane) ----


def overlap_with_final(shadow_child_ids: Sequence[str], final_child_ids: Sequence[str]) -> float:
    """Fraction of the CURRENT final child set that the shadow path also recovered.

    Denominator is the current lane (what production would surface) — the shadow is asked
    to cover it, so 1.0 means the routing localized to every final child. 0.0 when the
    current lane is empty (no coverage claim is meaningful)."""
    final = set(final_child_ids)
    if not final:
        return 0.0
    return round(len(set(shadow_child_ids) & final) / len(final), 4)


def gold_hit(shadow_child_ids: Sequence[str], gold_ids: Sequence[str]) -> bool:
    """Did the shadow child set contain any gold chunk? False when no gold is given."""
    gold = set(gold_ids)
    return bool(gold) and bool(set(shadow_child_ids) & gold)


def doc_nomination_hit(profile_doc_candidates: Sequence[str], gold_doc_ids: Sequence[str]) -> bool:
    """Did the profile step nominate a gold source document? (localization prerequisite)."""
    gold = set(gold_doc_ids)
    return bool(gold) and bool(set(profile_doc_candidates) & gold)
