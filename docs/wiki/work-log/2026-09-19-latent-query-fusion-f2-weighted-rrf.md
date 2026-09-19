---
change_id: LATENT-QUERY-FUSION-V2-F2
owner: wildcard-investigation
date: 2026-09-19
status: unit_proven
architecture_impact: "LATENT-QUERY-FUSION-V2 F2 — deterministic lineage-aware weighted RRF over RankedLanes (shared, worktree `fusion/latent-query`, UNMERGED). NEW pure `shared/polymath_shared/ranked_fusion.py`: `fuse_ranked_lanes(lanes, *, weights, k, preserve_top_n, cap)` = weighted RRF (`Σ weight(lineage_class)/(k+local_rank)` per lane) + bounded local-winner preservation (each query's intra-RRF top-N reserved through the cap). Produces a CANDIDATE ordering only — no seating (C4/C5 gate at F3). No existing contract changed (candidate_engine untouched in F2); the module is not yet wired (F3). Weights PROVISIONAL, measured at F4."
last_reviewed: 2026-09-19
---

## Contract
F2 builds the deterministic inter-query fusion on top of F1's `RankedLane`. It replaces the flatten
(`fused_score = best-single-query RRF`) with weighted RRF + bounded local-winner preservation, so each
query's local top-N survives the `merged_candidate_max` cut and reaches C4/C5. Pure + unit-only here;
F3 wires it into the live path (flag-gated), F4 measures + merges.

## Changes
- NEW `shared/polymath_shared/ranked_fusion.py` (pure, duck-typed over `RankedLane`):
  - `FusionWeights{q0,subquery,bridge,profile,graph,other}` (PROVISIONAL defaults 1.0/0.6/0.5/0.6/0.5/0.4)
    + `weight_for(cls)`; `lineage_class(lane)` (role==q0 dominates; else origin, graph modality as the
    fallback graph signal). COMPLEMENTARY/DIVERGENT are NOT weights (C5 seat roles, decided at F3).
  - `fuse_ranked_lanes(...)` → `FusedResult{ordered, preserved_ids, trace}`. `fused(chunk) = Σ over
    lanes: weight(class)/(k+local_rank)`; every term kept as a `Contribution` (many-to-one lineage
    NOT collapsed). `preserved_winners(lanes, k, top_n)` = each query's top-N by an INTRA-query RRF
    over its own lanes; `_apply_cap` guarantees preserved chunks survive truncation.
  - Deterministic: ties broken by `chunk_id`; JSON-safe trace (`ranked-fusion-v1`).
- NEW `tests/determinism/test_ranked_fusion.py` (8). Register 11.329; scaffold TREE; this work-log.

Design note — F2 orders CANDIDATES, it does not seat. A preserved bridge winner earns a place in the
candidate set that reaches C4/C5, never an automatic final seat (owner Do-Not). The COMPLEMENTARY vs
DIVERGENT distinction and grounding gates remain C4/C5's at F3; the bridge carries a single provisional
fusion weight.

## Proof
`UNIT_PROVEN` (pure, deterministic; executed path = worktree copy —
`ranked_fusion.__file__` under `pmv4-fusion/shared`). 8/8 green:
- exact weighted-RRF math (`a` = 1.0/60 + 0.5/60; `b` = 1.0/61); lineage class + weight lookup
  (q0-origin GRAPH lane stays Q0); **bounded preservation — a bridge's local rank-0 chunk survives a
  cap of 3 despite a fused score far outside it, AND is truncated when `preserve_top_n=0` (the
  control)**; many-to-one lineage kept (a shared chunk retains all 3 query paths, not one score);
  per-query top-N reservation covers each query; weights change the ordering (heavy vs light bridge
  flips bwin vs the q0 rank-1 chunk); determinism + chunk_id tie-break; empty-input safe.

## Rejected claims
- NOT a selection/seating change: F2 returns a candidate ORDER; C4/C5 still judge every candidate (F3).
- NOT frozen weights: `FusionWeights` is fully configurable; defaults are provisional, measured at F4.
- NOT `WORKTREE_INTEGRATION_PROVEN`: candidate_engine is untouched at F2 (no wiring); that is F3.

## Open contract gaps
`contract_impact` for F2's files = none (NEW pure module, no consumer yet; candidate_engine unchanged).
The fusion contract becomes live at F3 (wire `fuse_ranked_lanes` into `retrieve_candidates`/select so
the flag-on union is the fused ordering; enrich lane `origin` from plan provenance; feed the existing
C4→C5→CA4→synthesis). F4 = merge + port-gated bounce + A/B (V2 vs WLK2C V1 vs pre-WLK2C) on WLK-10 +
survival + main harness + CA5 64×4; tune weights FROM DATA. Preserved but unresolved: the exact
`preserve_top_n` and per-class weights are F4 measurement outputs, not F2 commitments.
