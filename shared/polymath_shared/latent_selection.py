"""WLK2C C4-live / C5-live orchestration (pure except the injected `rerank`; the cross-encoder is the
existing reranker, passed in). Ties C4 (latent_eligibility) + C5 (latent_portfolio) into one bounded
step over the judged candidate pool, so a q0-sub-floor bridge candidate can be graded and seated instead
of being dropped by q0-only selection.

Score reuse + one bounded budget (owner lock 2):
  q0 ↔ chunk    — REUSED from the pool (the existing rerank score); never recomputed here.
  q0 ↔ bridge   — computed ONCE per distinct bridge (1 rerank call for all bridges), cached.
  bridge ↔ chunk— computed ONCE per bridge over all of that bridge's candidates (1 call per bridge).
So the extra cost is 1 + (#distinct bridges) rerank calls, never per-candidate. All scores are logits;
C4 compares them in the sigmoid space against the existing floor.

Many-to-one (lock 1): every candidate is evaluated across ALL its bridge paths (C4 `evaluate_candidate`),
never collapsed. q0-primary + non-displacement (lock 3): seating is C5 `seat_portfolio`. Fail-open: a
rerank error degrades to no latent additions (the DIRECT/q0 portfolio is unaffected).
"""
from __future__ import annotations

from polymath_shared.latent_eligibility import DEFAULT_FLOOR, evaluate_candidate
from polymath_shared.latent_portfolio import (
    DEFAULT_DIRECT_PER_REP_CAP,
    DEFAULT_MAX_DIVERGENT,
    DEFAULT_MIN_ADEQUATE_DIRECT,
    seat_portfolio,
)


def _score_map(rerank, query, rows):
    """`rerank(query, rows)` → {chunk_id: rerank_score}. rows = [{chunk_id, text}]. Fail-open to {}."""
    if not rows:
        return {}
    try:
        out = rerank(query, [{"chunk_id": r["chunk_id"], "text": r.get("text", "")} for r in rows])
    except Exception:  # noqa: BLE001 — the latent layer is additive; a scoring failure never breaks the turn
        return {}
    scores = {}
    for r in (out or []):
        cid = r.get("chunk_id") if isinstance(r, dict) else None
        if cid is not None:
            scores[cid] = r.get("rerank_score")
    return scores


def grade_and_seat_latent(*, q0_text, pool, bridges, rerank, capacity,
                          floor: float = DEFAULT_FLOOR, bridge_valid_floor=None, divergent_local_floor=None,
                          direct_per_rep_cap: int = DEFAULT_DIRECT_PER_REP_CAP,
                          max_divergent: int = DEFAULT_MAX_DIVERGENT,
                          min_adequate_direct: int = DEFAULT_MIN_ADEQUATE_DIRECT,
                          complementary_cap: int | None = None) -> tuple[list, dict]:
    """Grade (C4) + seat (C5) the judged pool into a bounded latent-aware portfolio.

    `pool`  = the judged candidates, rerank-ordered, each `{chunk_id, doc_id, parent_id, text, query_ids,
              q0_score}` (q0_score = the existing q0 rerank logit — REUSED, never recomputed).
    `bridges` = `{bridge_id: {"query": bridge_query, "proposed_role": "COMPLEMENTARY"|"DIVERGENT"}}` — the
              BRIDGE-origin subqueries of the plan (the compiler's admitted bridges).
    `rerank(query, rows)` = the injected cross-encoder (returns rows with `rerank_score`).

    Returns `(seated, trace)`: `seated` = the bounded portfolio (each item = the pool candidate + a
    `seat_role` ∈ DIRECT/COMPLEMENTARY/DIVERGENT/RELATED + its C4 `eligibility` dict), and a `trace`
    (bridge_q0 scores + the C5 counts). Deterministic given the injected rerank."""
    bridges = bridges or {}
    bridge_ids = sorted(bridges)
    # q0 ↔ bridge — one call for all bridges, cached
    bridge_q0 = _score_map(rerank, q0_text,
                           [{"chunk_id": bid, "text": bridges[bid].get("query", "")} for bid in bridge_ids])
    # bridge ↔ chunk — one call per bridge over its candidates
    origin: dict = {}
    for bid in bridge_ids:
        rows = [{"chunk_id": c["chunk_id"], "text": c.get("text", "")}
                for c in pool if bid in set(c.get("query_ids") or [])]
        for cid, s in _score_map(rerank, bridges[bid].get("query", ""), rows).items():
            origin[(bid, cid)] = s

    graded: list = []
    for c in pool:
        cid = c["chunk_id"]
        cand_bridges = [bid for bid in (c.get("query_ids") or []) if bid in bridges]
        bpaths = [{"bridge_id": bid, "proposed_role": bridges[bid].get("proposed_role", "COMPLEMENTARY"),
                   "bridge_q0_score": bridge_q0.get(bid), "origin_chunk_score": origin.get((bid, cid))}
                  for bid in cand_bridges]
        ce = evaluate_candidate(chunk_id=cid, q0_chunk_score=c.get("q0_score"), bridge_paths=bpaths,
                                floor=floor, bridge_valid_floor=bridge_valid_floor,
                                divergent_local_floor=divergent_local_floor)
        graded.append({"chunk_id": cid, "parent_id": (c.get("parent_id") or c.get("doc_id") or cid),
                       "role": ce.role, "eligibility": ce.to_dict(), "cand": c})

    seated, ptrace = seat_portfolio(graded, capacity=capacity, direct_per_rep_cap=direct_per_rep_cap,
                                    max_divergent=max_divergent, min_adequate_direct=min_adequate_direct,
                                    complementary_cap=complementary_cap)
    return seated, {"bridge_q0": bridge_q0, "n_bridges": len(bridge_ids), **ptrace}
