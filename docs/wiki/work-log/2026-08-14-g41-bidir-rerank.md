---
change_id: g41-bidir-rerank
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: G3 promoted to production default; graph traversal unchanged (bidir NOT promoted)
---

# G4.1: bidirectional hop1 + G3 reranker + G3 default promotion

## Contract

Promote G3 reranking to the production default on completed G3+G5
evidence; keep production graph traversal outgoing-only; then run one
narrow G4.1 qualification — outgoing-hop1+reranker vs bidirectional-
hop1+reranker on the frozen G4 12-query set — to determine whether
reranking suppresses bidirectional noise (q09) while retaining useful
hub evidence. Promote bidir ONLY if downstream selected-evidence
quality passes; otherwise stop with the measured failure. No
extraction/weight/cap/predicate/hop changes.

## Changes

- `shared/polymath_shared/settings.py`: `sidecars.g3_reranker`
  default → True (POLYMATH_G3_RERANKER=0 disables; loud failure when
  the sidecar is missing).
- Gate 7f now runs by default (skip only when explicitly disabled)
  and applies the production rerank path; passes.
- `deployment/launchd/ai.polymath.reranker.plist` + Makefile
  `dev-reranker` (promotion operations).
- `eval/g4/qualify_g41.py` + `g41_metrics.json` + `REPORT_G41.md`
  (frozen): A vs B, top-10 selected-evidence quality.
- Harness maintenance: C1 integration cleanup/assertions made
  corpus-scoped (join-based) — prefix patterns collided with
  content-hash ids from other corpora; stale Qdrant collections
  removed (store hygiene).

## Proof

- G4.1: hub useful B>A PASS (30 vs 0); top-k useful B>=A PASS (67 vs
  12); q09 FAIL (17→10 selected noise remains); A-useful window
  retention FAIL (composition churn in q03/q04/q10); caps,
  determinism, latency, provenance all PASS.
- Full suites green after promotion: 165 unit + 24 integration.

## Rejected claims

- Bidirectional hop1 NOT promoted (measured failure on the
  noise-suppression criterion). No new weights/caps. hop2 remains
  rejected. Extraction/compiler/rule-pack/entity model untouched.

## Open contract gaps

- Narrow follow-up identified: generic seed eligibility (the q09
  "the system" class of generic Concept hubs must not seed
  expansion, or must require stronger lexical identity). Not
  implemented; requires its own baseline-vs-candidate measurement.
