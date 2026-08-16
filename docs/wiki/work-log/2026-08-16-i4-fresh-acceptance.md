---
change_id: i4-fresh-acceptance
owner: governance
date: 2026-08-16
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: complete
architecture_impact: none (acceptance only; no production change)
---

# Work Log: 2026-08-16 — I4 fresh heterogeneous production acceptance — FAIL

## Contract

Fresh untouched holdout after the I3R repair regression. Freeze a
capability matrix derived from executable config, a five-document
heterogeneous corpus (healthcare/cloud/manufacturing/edtech/
supply-chain), three-class fact gold (26 supported positives, 8
out-of-envelope, 18 must-not-assert), four-tier entity gold, and 10
retrieval questions — all frozen BEFORE the first extraction
(FROZEN_STATE.json). Run the real production path and score every
gate. No tuning, no code changes, no gold changes after freeze.

## Changes

- `eval/i4/matrix.py` + `capability_matrix.json` + `CAPABILITY_MATRIX.md`
  (frozen compiler capability derivation).
- `eval/i4/corpus/*` (5 fresh documents), `eval/i4/gold/*`
  (entity/fact/concept gold), `eval/i4/questions` inside concept gold,
  `eval/i4/manifest.yaml` + `manifest_reversed.yaml`,
  `eval/i4/freeze.py` + `FROZEN_STATE.json`,
  `eval/i4/verify_i4.py`, `eval/i4/evidence/evidence.json`,
  `eval/i4/REPORT.md`.

## Proof

- Control plane: 5/5 query_ready; replay/order/concurrency/interrupt/
  reconstruction/race/versioning all hash-equal PASS; isolation clean.
- Entities: durable referential + graph-eligible recall 1.000
  (factless durability holds on fresh domains).
- Facts: TP 10 / FP 10 / FN 16 → P 0.500, R 0.385 — FAIL vs the
  frozen bar (P>=0.95, R>=0.70). FP ownership: GLiNER boundary
  contraction (bare "Crestline" span), boundary variants of gold
  surfaces, leads/has_role shared-trigger double emission,
  member_of envelope violation. FN ownership: compound proper nouns
  not proposed / typing drift.
- Must-not-assert 18/18; provenance 18/18 exact; retrieval 10/10
  top-5; graph parity clean.
- I3/I3R regression classes all remain green.

## Rejected claims

- No production acceptance. No repairs attempted. No gold or
  capability-matrix edits after freeze. No claim that the compiler
  reintroduced I3 failure classes — the FPs are binding artifacts of
  fresh-domain GLiNER spans and one shared-trigger surface.

## Open contract gaps

- A named repair gate (e.g., I4R) must own remediation: GLiNER
  boundary/typing handling and the leads/has_role shared-trigger
  emission surface.
