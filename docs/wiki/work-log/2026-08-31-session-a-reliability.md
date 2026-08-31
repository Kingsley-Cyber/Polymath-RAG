---
change_id: SESSION-A-RELIABILITY-V1
owner: control-plane
date: 2026-08-31
status: complete
architecture_impact: shared projection_want authority (3 consumers rewired); reconciliation E2E convergence test; semantic failover (gate-reject cross-lane retry) + row-truth done-check; corpus 65/65 READY
last_reviewed: 2026-08-31
---

# WORK LOG — SESSION A (roadmap: control/enrichment reliability)

## Contract
SESSION-ROADMAP.md Session A: (1) 1C carry-gap with an END-TO-END
acceptance, (2) ONE want-set authority, (3) failover on parse/gate
rejection with the semantic/source eligibility split.

## Changes
- WANT-SET-AUTHORITY-V1: `polymath_shared/projection_want.py` owns the
  F6 children-only rule (SQL fragment + the three consumer-shaped
  helpers); verify/census/tickets rewired to import it; determinism
  test pins the imports (routing_child's inherent children-only
  definition explicitly excluded from the pin — different rule).
- RECONCILIATION-CONVERGENCE-E2E: run pinned to a stale contract with
  an open re-armed ticket (the live latent shape) → reconcile → carry
  → advance (WITH a DAG-less parent_enrichment ticket present — the
  census-killer regression) → owed stage re-executed → census promote
  → query_ready, NO manual re-pin. Second test: a stale-dependency
  stage regenerates instead of carrying and the successor is NOT
  promoted while regenerating.
- **Diagnosis REVISED, task chip dismissed**: the E2E proved the 1C
  carry mechanics were CORRECT all along (tickets+attempts+artifacts
  all copied per-run; open tickets correctly re-owe their work). The
  2026-08-31 outage was entirely the census KeyError + want-set drift.
  The open-ticket stage not carrying is intended semantics: owed work
  re-executes receipt-incrementally on the successor.
- SEMANTIC-FAILOVER-V1: `SEMANTIC_FAILOVER_ELIGIBLE` (UNPARSEABLE /
  UNKNOWN_REF / GISTS_BELOW_FLOOR / EMPTY / NO_RESPONSE) vs
  INELIGIBLE (INPUT_OVER_CEILING — another model cannot repair a bad
  source). `compile_with_semantic_failover` (pure, transport-agnostic):
  exactly ONE cross-lane retry, re-gated identically, both lanes'
  dispositions recorded on double failure; surfaced as
  ENRICHMENT_SEMANTIC_FAILOVER (silent-fallback accounting).
- ROW-TRUTH-DONE: enrichment done-ness now reads the ROW (READY, or
  INVALID with an ineligible class) — a pre-fix run had marked a job
  COMPLETE against an INVALID row, skipping it forever.

## Proof
- test_reconciliation_convergence 2/2; test_latent_contract_gate 12/12
  (one-retry-only, both-lanes-fail typed detail, source-never-retries);
  test_projection_want_authority 2/2; suite at the 8-failure baseline.
- Authority live: census missing=0, barrier clean through the shared
  helpers on the real corpus.
- LIVE recovery: the stuck Learning SQL ENRICH_UNPARSEABLE section —
  unreachable before (job-state lie) — re-enriched on the button press
  after ROW-TRUTH-DONE; corpus now **65/65 READY, zero INVALID**.

## Rejected claims
- "There is a 1C successor artifact carry-gap" — REFUTED by the E2E;
  the belief came from diagnosing during the census outage.

## Open contract gaps
- The E2E models the owed stage's worker completion inline (ticket
  flip + ok attempt); a full fleet-in-the-loop variant would need a
  live worker harness — deliberate scope cut.
