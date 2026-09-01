---
change_id: EXTRACTION-THROUGHPUT-V2
owner: governance
date: 2026-09-01
status: complete (live benchmark = the ecom-meta-v1 re-extraction)
architecture_impact: cloud extraction dispatch (rank slicing, size packing, receipts, 413 ladder); migration 0044
last_reviewed: 2026-09-01
---

# WORK LOG — EXTRACTION-THROUGHPUT-V2 (the dispatch redesign)

## Contract
Owner 2026-09-01 ("the extraction control design is really the most
buggy... analyze this ingest, it may lead to redesign or fixes to
ensure speed and deterministic" → analysis → "i bless off build it").
The 4-book live post-mortem that drove it: 74 cloud calls → 39×413 +
23×429 + 12×200 (84% failure); two docs hash-collided onto one gemini
lane while six lanes idled; the finished doc ran 35 calls in 347 s
(effective concurrency ≈ 1); every stage failure re-bought the whole
document; the failed ticket waited ≥6 min for re-arm.

## Changes
1. SIZE-BUDGETED PACKING — `request_char_budget` per lane in the
   registry (groq 18000 / gemini 120000 / nvidia 60000; CloudEndpoint
   field, default 60000). Batches pack to the doc's slice minimum;
   an oversize single neighborhood routes ALONE to the biggest-budget
   lane. 413s are now impossible by construction, not survivable.
2. RANK SLICING — each active doc owns a DISJOINT slice of the ring:
   n_lanes = ring // active_docs, base = active_rank × n_lanes
   (absolute ring positions via `select_cloud_endpoint_abs`; ranks
   cannot collide the way hash+offset walks can). A lone doc takes
   the whole fleet; a full queue degrades to per-doc affinity.
   Unknown rank/active (narrowed test doubles, non-worker callers)
   degrades to single-lane at the doc's hash home — the frozen shape.
3. PER-BATCH RECEIPTS (migration 0044 `extraction_call_receipts`) —
   every parsed call's raw response persists content-addressed by
   (contract identity, batch content); a stage retry REPLAYS cached
   raws through the exact same sanitize path
   (`LLMExtractionClient.extract_from_raw`) and pays only for calls
   it never made. Raw model output only — the gate re-runs on every
   replay, so replays are byte-equivalent and never bypass
   validation.
4. 413 LADDER + NO-HALVE — 413 splits the batch on the same lane; a
   single still-over batch escapes cross-HOST (never the same
   provider family — ring-adjacent groq→groq was the fatal shape);
   and 413 no longer records an AIMD failure (payload ≠ rate; the
   halving starved healthy lanes).
5. Transport failover under slicing: a dead lane fails over OUTSIDE
   the doc's own slice (lane_i + n_lanes), once, counted.
6. Warm start: confirmed already present (AdaptiveLimiter.restore
   adopts the persisted effective limit) — no change needed.

## Proof
- test_throughput_v2.py — 8 green: disjoint rank slices; lone doc
  engages ≥8 lanes; unknown context = single lane; packing never
  exceeds the slice budget; oversize routes to the big-budget lane;
  cached receipts replay with ZERO network calls; the whole-family
  413 storm splits then escapes cross-host; dispatch deterministic.
- extraction pool + depth-spread suites still green (27 total).
- LIVE BENCHMARK: the fleet bounce drifts the contract; the four
  reconciling ecom-meta-v1 runs auto-mint successors and re-extract
  under V2 — same corpus, before/after timing recorded in the
  continuity report when it lands.

## Post-review hardening (same day, owner-directed)
- FRESH-BUDGET invariant PINNED (test_reconciliation_convergence):
  a strike-exhausted old ticket never poisons the successor — new
  contract → new budget; old attempts → immutable audit. Verified
  ALREADY structural (per-run ticket ids mint fresh rows); the pin
  keeps refactors honest. The review's diagram assumed a gap that
  does not exist.
- `scripts/retry_failed_stage.py` (RETRY-TOOL-V1): the first-class
  SAME-contract strike reset (replaces the hand-SQL used live when
  the 413 fix landed without drift).
- OUTPUT-AWARE SPLIT: finish_reason=length on a multi-item batch now
  splits like a payload condition (dense sections overflow OUTPUT
  budgets even when input fits) — the review's "your next failure
  mode isn't 413" point, closed same-day, test-pinned.

## Rejected claims
- "Rotate ring offsets to fix collisions" — ranks, not rotations:
  hash+offset walks can still collide; disjoint rank slices cannot.
- "Serialize LLMCallResult into the receipt" — rejected: nested
  dataclass rehydration drift risk; the receipt stores RAW TEXT and
  the sanitize gate re-runs on replay (cheaper AND safer).
- Piece 6 of the analysis (fast first retry for failed tickets) —
  deferred: the census re-arm loop already re-drives within its
  tick cadence; measure the residual latency under V2 before adding
  a special case.

## Open contract gaps
- `spread_decision`/EXTRACT-DEPTH-SPREAD-V1 is subsumed by rank
  slicing (active_docs=1 ⇒ whole fleet); the function and its tests
  remain as the decision-contract pins for the degraded path.
- Receipt vacuum: extraction_call_receipts grows with corpus scale;
  rows are re-derivable spend-savers, safe to TRUNCATE any time.
- test_lane_affinity_steal fails only while a live ingest holds real
  ready extract tickets (claim-pool interference) — state-dependent
  test debt, joins the existing list.
