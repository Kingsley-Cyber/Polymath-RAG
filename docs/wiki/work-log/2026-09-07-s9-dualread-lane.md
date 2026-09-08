---
title: "WORK LOG — S9 dual-read lane (profile→map→child as an additive HYBRID lane) + FINAL-PLAN P0"
change_id: RETRIEVAL-DUALREAD-LANE-V1
date: 2026-09-07
owner: worker (live-reader change, reversible + default-off)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.155, 11.156
package: docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md, shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/document_profile/projection.py, shared/polymath_shared/document_profile/parent_map_projection.py, tests/determinism/test_candidate_engine.py, scripts/dualread_qualify.py, docs/wiki/experiments/dualread-qualify-2026-09-07.json, scripts/README.md, scripts/scaffold_polymath_v4.py
architecture_impact: "Two things land together. (P0) The FINAL RETRIEVAL/ROUTING/SYNTHESIS plan is admitted verbatim into the repo as the query-time plan-of-record with a P0-P14 phase-execution ledger (owner authorized the full plan). (S9 / P1.spine) The first live-reader change of the migration: candidate_engine gains lane E — the DOCUMENT_PROFILE → PARENT_MAP → CHILD spine (R3→R5→R10) as an ADDITIVE lane unioned LAST, behind POLYMATH_CHAT_DUALREAD_ENABLED (default off). Flag off ⇒ lane E empty ⇒ the union is byte-identical to today (chat_regression --check green). It obeys the plan's §53 laws (raw query + exact terms + global raw child always survive; profile nomination never hard-gates; latent/precision additive). The nominator (profile RRF → ONE filtered parent-map search) is injected from chat_retrieval; the engine deepens each resolved parent through the ORIGINAL child lane (dense_search), exactly like lane D. Reusable search contracts added to the projection modules (profile_nominate, search_parent_maps)."
---

# WORK LOG — S9 dual-read lane + FINAL-PLAN P0

## Contract

Owner /goal step 5 (`…→ shadow → dual-read →…`) + FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1
P0/P1.spine. After S8 shadow qualified the profile→map→child routing (register 11.154),
S9 makes it CONSUMABLE by the live HYBRID path — additively, reversibly, default-off — and
freezes the owner's full retrieval plan into the repo as plan-of-record.

Owner: `worker`. Verifier: `test_candidate_engine.py` (lane-E unit tests) +
`scripts/chat_regression.py --check` (flag-off byte-identical) + `scripts/dualread_qualify.py`
(flag-on exact-lookup control, live Qdrant). Rollback: unset `POLYMATH_CHAT_DUALREAD_ENABLED`
(default off; the lane is inert).

## Changes

- **P0 — plan freeze:** `docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` (admitted
  verbatim + a P0–P14 phase-execution ledger + the governing-laws digest + the reconcile
  note vs the migration ledger). TREE + register 11.155.
- **`candidate_engine.py`:** `LANE_E = "SHADOW_DUALREAD"`; `CandidateBudget.dualread_enabled`
  (+ profile_docs / map_k / max_parents / children_per_parent / budget_ms), default off;
  `retrieve_candidates`/`_retrieve_on` gain an injected `dualread_search`; lane E block
  (mirrors lane D): the nominator returns resolved parents, each deepened via
  `dense_search(CHILD, k, {doc_id, parent_id})`; `lane_e` unioned LAST (existing lanes keep
  precedence, provenance merges). Receipted (`trace["dualread"]`, lane_sizes, funnel_lanes).
- **`chat_retrieval.py`:** `dualread_search` closure (profile RRF nominate → ONE filtered
  parent-map search, over the contract collections; zero cost when off) + injected at the
  engine call; the `POLYMATH_CHAT_DUALREAD_*` knobs added to `_INT_KNOBS`.
- **`projection.py` / `parent_map_projection.py`:** reusable read-only search contracts
  `profile_nominate()` (RRF over the qualified answer surfaces) + `search_parent_maps()`
  (§17 one-filtered-search rule) — shared by the shadow canary and the live lane.
- **`scripts/dualread_qualify.py`** (new): the S9 flag-on qualification (below).

## Proof

- **Flag OFF byte-identical:** `.venv/bin/python scripts/chat_regression.py --check` →
  `16 cases, 131 rows, 0 failing` (the union tuple is identical when lane E is empty).
- **Unit (deterministic, fakes-only):** `test_candidate_engine.py` — lane E off-by-default
  is byte-identical + never calls the nominator; on adds children with the `SHADOW_DUALREAD`
  arrival; a duplicate child MERGES provenance (one row, both lanes); `None` nominator with
  the flag on is inert. Full suite green.
- **Flag ON exact-lookup control (LIVE, in-process over Qdrant):**
  `scripts/dualread_qualify.py --corpus cinema --fixtures L,B` →
  - **L (exact identifiers): `gold_in_union` off 15/15 → on 15/15, 0 regressions** (dual-read
    contributed on 1 mapped-cohort turn). The exact-lookup control the gate requires.
  - **B (grounded QA): off 13/15 → on 13/15, 0 regressions** (dual-read contributed on 6
    turns). The 2 misses are present with the flag OFF too — a pre-existing union gap, not a
    dual-read regression.
  - PASS: on ≥ off for every question — the additive union (lane E last) cannot remove a
    gold chunk, and the live A/B confirms it. Evidence: `dualread-qualify-2026-09-07.json`.

## Rejected claims

- **Not** a ranking/behavior change by default: default off ⇒ byte-identical (proven).
- **Not** a hard gate: lane E is additive, unioned last; raw query / exact terms / global
  raw child all survive (§53). Profile nomination never removes evidence.
- **Not** a drop-in replacement for the direct lanes: it ADDS profile→map→child candidates;
  the cross-encoder still judges the union.

## Open contract gaps

- **P2 — intent-policy mapping (next dependency).** The compiler (`chat_plan.py::compile_plan` → `ChatPlan`)
  already emits `task_type`, typed `qtype` subqueries, `graph_useful`, `must_answer`,
  `exact_terms`, `entities`; `query_router.py::classify_query()` is a deterministic no-LLM
  intent classifier to extend. Add `classify_intent(plan) → Intent` (the plan's 10-intent
  vocabulary) over that output and map Intent→budget at the `shape_budget` seam
  (`candidate_engine.py:234`) — no new classifier LLM (§5). Then P3 Resolution Lift, P4
  micro-latent, … per the FINAL-PLAN phase ledger.
