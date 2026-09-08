---
title: "WORK LOG — R6b Resolution-Lift probe lane (lifted terms → children)"
change_id: RESOLUTION-LIFT-PROBE-V1
date: 2026-09-08
owner: worker (live-reader precision lane, reversible + default-off)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.163
package: shared/polymath_shared/candidate_engine.py, orchestrator/orchestrator/api/chat_retrieval.py, shared/polymath_shared/query_intent.py, shared/polymath_shared/resolution_lift.py, tests/determinism/test_candidate_engine.py, docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md
architecture_impact: "R6b closes Resolution Lift: candidate_engine gains lane F — the corpus's precise vocabulary probed as ORIGINAL children. The injected `lift_search` (chat_retrieval) profile-nominates docs, gathers ≤3 source-derived lift terms (resolution_lift_gather), embeds them, dense-child-searches each, and returns the children tagged with the lifted term; the engine unions lane F LAST and the cross-encoder judges them (§12 'vocabulary discovers, source chunks prove'). Additive + default-off (`resolution_lift_enabled`, set per intent by apply_intent_policy from policy.resolution_lift != off) ⇒ flag-off byte-identical. Also a §10 quality gate: `is_meaningful_term` drops bare-numeric DISCOVERED terms (page/figure refs) so lift surfaces precision vocabulary, not source noise."
---

> **Ledger row:** `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` phase **P3** — this work-log is the EVIDENCE for that ledger row (the MD phase table is the control point; this does not duplicate it).

# WORK LOG — R6b Resolution-Lift probe lane

## Contract

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §12/§18/§50: Resolution Lift "creates bounded second-pass
probes" — the lifted terms fetch source children that the judge then ranks. After the R6 core
(11.160) + gatherer (11.162), this wires the probe into retrieval as an additive lane.

Owner: `worker`. Verifier: `test_candidate_engine.py` (lane F) + `chat_regression --check`
(flag-off) + a live lane probe. Rollback: `resolution_lift_enabled` off (default) / intent
policy off.

## Changes

- **`candidate_engine.py`:** `LANE_F = "RESOLUTION_LIFT"`; `CandidateBudget.resolution_lift_
  enabled`/`resolution_lift_children`; injected `lift_search`; lane F block (mirrors lane E) —
  the lifted-term child rows become CandidateEvidence with the `RESOLUTION_LIFT` arrival,
  unioned LAST; receipted (`trace["resolution_lift"]` incl. the terms probed).
- **`chat_retrieval.py`:** the `lift_search` closure — profile-nominate → `gather_lift_
  candidates` (LiveLiftSources) → embed the ≤3 terms → dense child search each → child rows
  tagged with `lifted_term`. Guarded; zero cost when off. Injected at the engine call.
- **`query_intent.py`:** `apply_intent_policy` sets `resolution_lift_enabled` from the intent's
  `policy.resolution_lift` (!= off).
- **`resolution_lift.py`:** `is_meaningful_term` — a §10 quality gate dropping bare-numeric
  discovered terms; `rank_lift_candidates` applies it.

## Proof

- **Unit:** `test_candidate_engine.py` lane-F case — off byte-identical + never calls
  `lift_search`; on adds children with the `RESOLUTION_LIFT` arrival + receipts the terms. Full
  determinism suite green.
- **Flag OFF byte-identical:** `chat_regression --check` → `131 rows, 0 failing`.
- **LIVE (cinema):** intent/flag on → lane F probes 6 children/query from ≤3 source-derived
  lift terms; **union grows (+6) with 0 candidates lost** (additive; exact-lookup preserved).
  After the meaningfulness gate the lifted terms are letter-bearing source identifiers (e.g.
  "IEEE", corpus figure/code refs), not bare page numbers.

## Rejected claims

- **Not** a hard gate / not lossy (additive lane, unioned last; flag-off byte-identical).
- **Not** hallucinated expansion: every lifted term is a corpus record; the judge validates.
- **Not** evidence-by-assertion: lift terms only fetch children; the cross-encoder ranks them.

## Open contract gaps

- **Lift-term quality is corpus-bound:** the value of the lifted terms depends on the corpus's
  own TERM/exact_identifier vocabulary; on corpora whose identifiers are mostly figure/page
  refs the lane is safe (additive, judged) but adds little. **GATED refinements:** a persisted
  corpus DF index (rarity at query time) + preferring semantic TERM/CONCEPT/ATOM over noisy
  MAP_IDs. Do not present lift uplift as proven on arbitrary corpora.
- **Next:** P5 SEEALSO/BRIDGE fan-out; P6/P7 intent-conditioned graph auto-route + destination
  MAP; P8 synthesis evidence-role bundle; P9 breadth; P10–P13 measurement.
