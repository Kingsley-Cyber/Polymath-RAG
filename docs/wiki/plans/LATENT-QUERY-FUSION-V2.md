---
title: "LATENT-QUERY-FUSION-V2 — query-stratified multi-stage fusion with preserved local ranks"
date: 2026-09-19
last_reviewed: 2026-09-19
status: "DONE — F1-F4 built (register 11.328-11.334), checkpoint tag v4-latent-query-fusion-v2; live with the flag on (11.408). Status refreshed 2026-09-24 (11.463)."
owner: "@king"
scope: "Replace the flatten-too-early union (one global RRF dominated by q0) with query-stratified fusion: each query (q0 / subquery / BRIDGE) ranks its own evidence locally, those local ranks are preserved (a RankedLane per query), then a lineage-aware weighted RRF fuses across queries with bounded local-winner preservation — feeding the EXISTING C4→C5→CA4→synthesis spine. Behind POLYMATH_CHAT_LATENT_FUSION (default-off), A/B against WLK2C V1. Extends candidate representation + fusion; does NOT rewrite CandidateEngine unless investigation proves necessary."
---

# LATENT-QUERY-FUSION-V2 (implementation plan-of-record)

**Authority:** owner `/goal` (2026-09-19). **Grounded in WLK2C V1** (registers 11.315–326), which PROVED
latent-query activation works end-to-end (wc01 causal chain: grounded bridge → valid bridge↔q0 →
COMPLEMENTARY seat q0 dropped) but whose flattened fusion is intentionally NOT the final architecture.

## Architectural lock (do not violate)
```
retrieval modalities → INTRA-query fusion → RankedLane per q0/subquery/bridge
→ bounded local-winner preservation → INTER-query lineage-aware fusion → C4 → C5 → CA4 → synthesis
```
A normal RAG asks "what chunks rank highest for q0?". This system asks "what information needs (explicit
+ latent) must be satisfied, and what evidence ranks highest FOR EACH?" — then fuses. Different ranking
authorities at different stages: retrieval rank (does this passage answer THIS local need?) → fusion
(how strongly discovered across lanes?) → C4 semantic gate (is this local need legitimately tied to q0?)
→ C5 portfolio (does it add useful information?) → CA4 (what can we claim?).

## Investigation findings (root cause — why V1's flatten kills bridge winners)
Read of `shared/polymath_shared/candidate_engine.py`:
- **Per-query RRF contributions already exist.** The union loop (l.968–1052) accumulates
  `query_scores[qid]` (each query's RRF contribution to a chunk) and sets
  `query_scores[ctx.query_id]` = Σ RRF over hierarchy/dense/sparse ranks. `CandidateEvidence` carries
  `dense_rank`/`sparse_rank`/`hierarchy_rank`/`dense_score`/`sparse_score`/`fused_score`/`query_scores`/
  `arrivals`/`query_ids`. So multi-lane provenance is PARTLY present.
- **The kill:** `fused_score = best-single-query RRF + bounded agreement` (l.1015–1021), i.e. `best =
  max(query_scores.values())`. A bridge's LOCAL rank-1 candidate has a single-lane RRF ≈ `1/(60+1)` ≈
  0.016; a q0 chunk sums three lanes ≈ 0.049. So bridge winners rank BELOW q0 winners and are
  **truncated at `merged_candidate_max`=120** (l.1051) before `judged_prefix` (l.1265–1321, doc-fair) or
  the reranker ever see them. wc07: union query_ids = {q0:104, q1:10, q2:6, p0:11}, ZERO bridge ids.
- **What's missing:** each query's **LOCAL RANK** (its position within that query's own ranked list) is
  NOT stored first-class — only the RRF contribution. And there is no reservation that guarantees each
  query's local top-N survives the union cut. `aspect_prefix_seats` (l.1339–1347) reserves JUDGED seats
  per aspect, but only for candidates that already survived the union — too late for truncated bridges.

**Conclusion:** the V2 delta is concentrated — capture per-query local ranks (RankedLane), and fuse with
bounded local-winner preservation so each query's top-N survives to C4/C5. C4/C5/CA4/C6 are reused.

## RankedLane representation (the unlock)
```
RankedLane { query_id, query_text, role, origin (USER|PROFILE|GRAPH|BRIDGE|WILDCARD), lane (DENSE|SPARSE|
             HIERARCHY|GRAPH), results: [ {chunk_id, local_rank, score} ] }
```
A candidate's discovery becomes many-to-one and rank-rich (not a single flattened score):
`discoveries: [{query_id, role, lane, local_rank, score, origin_query, bridge_id}]`. C0's many-to-one
lineage was exactly the right prior decision — do NOT collapse it before C4.

## Phase slices (narrow; worktree `fusion/latent-query`; F1 first)
| slice | what | proof |
|---|---|---|
| **F1** | REPRESENTATION / OBSERVABILITY ONLY. `RankedLane` type + capture each query's local ranked list at retrieval; preserve multiple lane memberships per chunk; a receipt (`retrieval.ranked_lanes`) showing each query's local top-N (e.g. "bridge A ranks Laban #1"). **NO selection change; flag-off byte-identical.** | UNIT (pure builder) + a live observability probe |
| **F2** | Deterministic lineage-aware **weighted RRF** over the RankedLanes: `fusion(chunk)=Σ lane_weight/(k+local_rank_i)`, weights per role (q0 1.0 / COMPLEMENTARY 0.6 / DIVERGENT 0.3 / GRAPH 0.5 — **provisional, measured at F4, not frozen**), with **bounded local-winner preservation** (each query's top-N reserved through `merged_candidate_max`/`judged_prefix`). Preserve component contributions. | UNIT (pure, deterministic) |
| **F3** | Feed the fused candidate set (with lineage) into the EXISTING C4 (semantic gate) → C5 (portfolio) → CA4 → synthesis. Flag-gated `POLYMATH_CHAT_LATENT_FUSION`; V2 replaces the pool/fusion, downstream unchanged. | LIVE (proven at F4) |
| **F4** | Merge + port-gated bounce + **A/B**: V2 vs WLK2C V1 vs pre-WLK2C, on WLK-10 + 4-mode survival + main harness + CA5 64×4 vs the frozen baselines. Measure lane weights + coverage; tune weights FROM DATA. | LIVE_PATH_PROVEN |

## Proof discipline
The fusion is deterministic (RRF over ranks) → **unit-testable** with synthetic lanes (F1/F2 fully
provable in the worktree). F3 orchestrator wiring is live-only (proven at F4). Flag default-off ⇒ the
live path is byte-identical (V1/pre-WLK2C untouched) until F4.

## Do NOT
- rewrite `CandidateEngine` unless investigation proves it necessary (prefer an ADAPTER: retrieval →
  RankedLane[] → fusion → existing CandidateEvidence[] → C4/C5);
- hardcode wc01/wc05/wc07 (they are DIAGNOSTIC PROBES, not optimization targets);
- blindly increase global K; freeze speculative lane weights before F4 measurement;
- give bridge-local winners AUTOMATIC final seats (they still pass C4 semantic + C5 portfolio);
- collapse many-to-one lineage before C4; make F1 change selection.

## Acceptance (F4)
V2 lifts bridge-candidate REACH (wc07-class: bridge local winners survive to C4/C5) WITHOUT: harming
DIRECT/q0 answers, regressing CA5, letting a bridge overpower q0, or materially harming latency. A/B
must show V2 ≥ V1 on latent coverage with no DIRECT/CA5 regression. A valid null (V2 no better than V1)
is allowed and reported honestly. WLK2C V1 + the 2026-09-18 baselines remain immutable.
