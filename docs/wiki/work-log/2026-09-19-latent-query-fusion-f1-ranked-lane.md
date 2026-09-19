---
change_id: LATENT-QUERY-FUSION-V2-F1
owner: wildcard-investigation
date: 2026-09-19
status: worktree_integration_proven
architecture_impact: "LATENT-QUERY-FUSION-V2 F1 — RankedLane representation + observability ONLY (shared, worktree `fusion/latent-query`, UNMERGED; flag `POLYMATH_CHAT_LATENT_FUSION` default-off ⇒ retrieval byte-identical). NEW pure `shared/polymath_shared/ranked_lane.py` (`RankedLane`/`LaneResult`, `build_ranked_lanes`, `lane_memberships`, `ranked_lanes_receipt`). `candidate_engine.retrieve_candidates` gains a flag-gated capture BEFORE the union that records each query's LOCAL ranked list (q0 / subquery / bridge), preserving local ranks + multi-lane membership per chunk, and attaches a JSON receipt `trace['ranked_lanes']`. NO selection change: flag-off adds nothing; flag-on leaves the union ids/order/fused_score identical. F2 will fuse over these lanes (lineage-aware weighted RRF + bounded local-winner preservation); F3 wires to the existing C4→C5→CA4 spine."
last_reviewed: 2026-09-19
---

## Contract
F1 is the first V2 slice and is deliberately representation/observability ONLY (owner: "The first
implementation slice should be representation/observability only: RankedLane, local ranks preserved,
multiple lane memberships preserved per chunk, flag-off behavior unchanged"). It establishes the
`RankedLane` as a first-class structure that captures what the pre-V2 flatten destroys — each query's
LOCAL ranked list — without touching selection. F2 builds deterministic inter-query fusion on top.

## Changes
- NEW `shared/polymath_shared/ranked_lane.py` (pure, duck-typed over `CandidateEvidence`):
  - `RankedLane{query_id, query_text, role, origin, lane, modality, results:[LaneResult]}` +
    `LaneResult{chunk_id, local_rank, score, doc_id}`; helpers `rank_of`/`top`/`to_receipt`.
  - `build_ranked_lanes(items, *, primary_query_id, primary_query_text, query_meta)` — groups the
    per-lane candidate lists (pre-union, still in retrieval-rank order) into one `RankedLane` per
    (query_id, lane); `local_rank` = positional index within the group (faithful: the engine appends
    hits in `LaneHit.rank` order and never reorders a lane before the union). Deterministic.
  - `lane_memberships(lanes)` (chunk → every (query,lane,local_rank)) and `ranked_lanes_receipt(...)`
    (JSON-safe, includes `multi_lane_chunks`).
- `shared/polymath_shared/candidate_engine.py`: `import os`; a flag-gated capture immediately BEFORE
  the union (`POLYMATH_CHAT_LATENT_FUSION==1`) that builds `ranked_lanes` from
  `lane_a/b/c/d + sub_items + lane_e/f/g/h` with `{sq.query_id: {text, role: qtype}}` meta; and a
  flag-gated `trace['ranked_lanes'] = ranked_lanes_receipt(...)`. Default-off ⇒ `ranked_lanes` stays
  None ⇒ no import, no capture, no trace key.
- NEW `tests/determinism/test_ranked_lane.py` (pure) + 2 engine-level tests appended to
  `tests/determinism/test_candidate_engine.py`. Register 11.328; scaffold TREE; this work-log.

Why subquery local rank is captured POSITIONALLY, not from a stored field: subquery `CandidateEvidence`
deliberately omit `dense_rank`/`sparse_rank` — setting them would make the union's primary-score line
(`query_scores[ctx.query_id] = Σ rrf(rank)`) award a bridge-only chunk a spurious q0 score. So the
rank is never stored on the shared field; F1 reads it from list position instead (equivalent, since
the lists are in rank order and `_sink_noisy` already rewrites ranks to positions).

## Proof
`UNIT_PROVEN` + `WORKTREE_INTEGRATION_PROVEN` (executed path verified = the worktree copy:
`polymath_shared.ranked_lane.__file__` resolves under `pmv4-fusion/shared`; `candidate_engine` is
`shared/`, worktree-unit-testable per the editable-.pth rule). 51/51 green:
- `test_ranked_lane.py` (9): local ranks positional+ordered; **a bridge's local rank-1 captured as
  local_rank 0** (the exact fact the flatten drops); multi-lane membership NOT collapsed; sparse vs
  dense score source; lane order = first appearance; graph modality; empty chunk_id skipped; receipt
  JSON-safe with `multi_lane_chunks`; deterministic (identical receipt twice); missing-provenance
  fallback to q0.
- `test_candidate_engine.py` (+2): flag-off ⇒ no `ranked_lanes` key (strict no-op); flag-on ⇒ receipt
  present AND `on_union == off_union` (chunk ids, order, fused_score all identical — **selection
  unchanged**) AND each subquery is its own lane with `local_rank==0` at the head AND
  `multi_lane_chunks >= 1`.

Live observability probe (receipt visible on a real `/api/chat` turn) is DEFERRED to F3/F4 (worktree
is isolated; the fleet runs MAIN with the flag off). No merge, no bounce.

## Rejected claims
- NOT a selection change: F1 does not fuse, seat, or re-rank anything. `on_union == off_union` is the
  receipt for that.
- NOT storing subquery rank on `dense_rank`/`sparse_rank` (would leak a spurious q0 primary score).
- NOT `LIVE_PATH_PROVEN`: the live receipt on a real turn is F3/F4. No probe privileges wc01/05/07.

## Open contract gaps
`contract_impact.py --range 0887188..HEAD` (deterministic) → CANDIDATE_ENGINE changed; transitive
consumers ACCEPTANCE / PROFILE_YIELD_RECEIPT / RESOLUTION_STATE / RETRIEVAL_RECEIPT. Dispositions:

| contract | disposition | evidence |
|---|---|---|
| CANDIDATE_ENGINE | UPDATED (additive, flag-gated) | capture + receipt behind `POLYMATH_CHAT_LATENT_FUSION`; flag-off byte-identical (`on_union == off_union`); `test_candidate_engine.py` green incl. 2 new |
| RETRIEVAL_RECEIPT | UPDATED (additive key) | `trace['ranked_lanes']` appears ONLY when the flag is on; absent by default (tested both ways) |
| PROFILE_YIELD_RECEIPT | TESTED_UNCHANGED | `test_profile_yield.py` green (flag-off default) |
| RESOLUTION_STATE | TESTED_UNCHANGED | `test_evidence_resolution.py` green (flag-off default) |
| ACCEPTANCE | NOT_AFFECTED | consumes the union/evidence, which is byte-identical flag-off; live `test_cross_domain_routing.py` DEFERRED (integration, live services) |

No unresolved/blocked impact. F2 (deterministic lineage-aware weighted RRF over these lanes + bounded
local-winner preservation) is the next slice and is where the fusion contract actually changes; F3
wires the fused set into C4→C5→CA4; F4 merges + port-gated bounce + A/B vs WLK2C V1 vs pre-WLK2C.
Origin enrichment for bridge subqueries (USER/PROFILE/GRAPH/BRIDGE/WILDCARD) is carried at F3 from the
plan's provenance; at the engine layer F1 records `qtype` as the descriptive `role` only.
