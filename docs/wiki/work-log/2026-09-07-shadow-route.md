---
title: "WORK LOG — S8 shadow runtime route (profile → parent-map → child, measured)"
change_id: SHADOW-ROUTE-CANARY-V1
date: 2026-09-07
owner: worker (evaluation-only shadow measurement)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.154
package: shared/polymath_shared/document_profile/shadow_route.py, scripts/shadow_route_canary.py, tests/determinism/test_shadow_route.py, docs/wiki/experiments/shadow-route-2026-09-07.{json,md}, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "The S8 shadow route: a NEW pure, store-abstracted module (shadow_route) that runs global profile → ONE filtered parent-map search → child deepening and returns the §17 shadow receipt, plus a read-only canary that records its coverage against the current child lane. ADDITIVE ONLY — it edits nothing in candidate_engine, the orchestrator query path, ranking, QUERY_READY, or any live reader; the S8 gate ('no production rank effect yet') is structural. Headline finding: shadow coverage tracks parent-map backfill completeness in near-lockstep (fully-mapped docs 0.80-1.00 overlap; partial docs Blain 33%→0.242, Anatomy 11%→0.017), while document nomination (1.0) and parent-resolve-into-source-doc (0.972) hold regardless. The routing substrate is sound; the remaining gap is unmapped parents, closed by the paced backfill (11.153), not by code."
---

# WORK LOG — S8 shadow runtime route (step 5: backfill → SHADOW → dual-read)

## Contract

Owner /goal step 5: "controlled cohorts → backfill → **shadow** → dual-read → ...".
Roadmap S8: run global profile → parent maps → child deepening as a SHADOW, record
candidate overlap and misses, **gate: no production rank effect yet**. This is the query-
path integration's first, non-blocking slice — the measurement that qualifies the routing
substrate before S9 makes it consumable.

Owner: `worker`. Verifier: `tests/determinism/test_shadow_route.py` (pure logic) +
`scripts/shadow_route_canary.py` (live measurement). Rollback: n/a — nothing live changes;
the module is additive and the canary is read-only.

## Changes

- **`shared/polymath_shared/document_profile/shadow_route.py`** (new): pure, store-
  abstracted route (search callables injected, exactly like `candidate_engine`).
  `shadow_route(query_vec, profile_search, map_search, child_search) → ShadowReceipt`
  (§17 fields: `profile_doc_candidates`, `parent_map_candidates`, `resolved_parent_ids`,
  `shadow_child_candidates`, `latency_ms`, `degraded`). Graceful degradation — a shadow
  never raises. Pure coverage math: `overlap_with_final`, `gold_hit`, `doc_nomination_hit`.
  This SAME module later backs the S9 dual-read lane.
- **`scripts/shadow_route_canary.py`** (new): wires the real searches — `rrf_rank` over
  the profile collection (the qualified nominator), ONE `doc_id`-filtered `routing`-vector
  search over the parent-map collection (§17 perf rule), a `parent_id`-filtered child
  search over the routing collection; `final` baseline = a plain dense child search in the
  source doc. Reports the §17 receipt + coverage per doc/probe. Read-only.
- **`tests/determinism/test_shadow_route.py`** (new): 6 fakes-only cases — pipeline +
  receipt shape, dedup/order, the single-filtered-map-search contract, the two miss
  reasons (`no_nominated_docs`, `no_resolved_parents`), never-raises degradation, coverage
  math. `6/6` green.
- **experiment JSON + MD**, **scripts/README** row, **TREE** entries, this work-log,
  **register 11.154**, ledger S8 row + Repo-truth block.

## Proof

- **Unit (deterministic):** `.venv/bin/python tests/determinism/test_shadow_route.py` →
  `6/6 passed`.
- **LIVE (read-only, 36 probes, 6 mapped cinema docs):**
  `POLYMATH_GROQ_ROUTER=1 .venv/bin/python scripts/shadow_route_canary.py --corpus cinema --per-doc 3`
  → nomination **1.000**, parent-resolve **0.972**, mean overlap 0.665, median latency
  143 ms, `no_production_rank_effect: true`. Per-doc overlap tracks mapped-parent fraction:
  100%-mapped docs 0.80–1.00; Blain (33%) 0.242; Anatomy (11%) 0.017.

## Rejected claims

- **Not** a production change (no candidate_engine / query-path / ranking / QUERY_READY
  edit). **Not** a routing-quality failure (nomination + resolve hold across all docs; the
  gap is unmapped parents). **Not** a drop-in replacement (overlap is a coverage signal;
  S9 dual-read unions, not replaces).

## Open contract gaps → next dependency

- The low-overlap docs are the two the backfill left partial — completing the paced
  parent-MAP backfill (11.153) lifts their overlap; re-run this canary to confirm.
- **Next (step 5): S9 dual-read** — allow Hybrid to CONSUME the shadow candidates (union
  with direct child retrieval, which stays unrestricted) behind a reversible flag, gated
  on frozen-eval non-regression + exact-lookup control. THIS is the first slice that
  changes a live reader; it is separately gated and will be flagged before it lands.
