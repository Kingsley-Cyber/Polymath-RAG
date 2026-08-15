---
change_id: d4-text-support-admission
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (qualification REJECT; no production change)
---

# D4: TEXT-EVIDENCE SUPPORT ADMISSION — REJECT (insufficient signals)

## Contract

Establish TEXT support admission (retrieved → supported → selected)
with a deterministic, inspectable policy calibrated from frozen
development data; never an arbitrary threshold; never rank/top-k as
support; promote only if existing frozen signals demonstrate a
defensible precision-first operating point; otherwise STOP and report
insufficiency without inventing heuristics.

## Changes

- `eval/d4/queries.json`: frozen development set (7 answerable,
  6 unsupported incl. same-domain + keyword-trap), sha256
  `7731f57573aa511543d9b2e4742692c99d71de48d546c8323e79423f692e9e74`.
- `eval/d4/measure.py` + `eval/d4/analyze.py`: signal measurement and
  analysis over the FROZEN retrieval + G3 pipeline (no retrieval
  change made). Artifacts frozen under `eval/d4/artifacts/`
  (779 candidate records, 31 gold labels, full analysis).
- `eval/d4/REPORT.md`: qualification report.

## Proof

Signal separation (SUPPORTED vs UNSUPPORTED):

- dense: S_min 0.201 vs U_max 0.613 — no separation (zero-FP keeps
  1/24 TP).
- lexical: S_min 0.153 vs U_max 3.161 — no separation (zero-FP keeps
  2/31 TP).
- G3 rerank: S_min -2.63 vs U_max 6.50 — query-level feasible
  interval (6.5, 2.25] is EMPTY; no threshold admits all answerable
  queries while rejecting all unsupported.

Decisive counter-evidence: same-domain unsupported queries outscore
true positives (u5 → 6.44 on metacognitive_monitoring; u6 → 6.50 on
worker_pools; q5's true supporting passage scores 1.25–2.25). The G3
cross-encoder measures topical relatedness, not answer support.

Verdict: REJECT. Existing signals are insufficient for support
admission. No policy was implemented, no threshold was picked, no
heuristic was invented.

## Rejected claims

- No promotion of text-support-v1 from this data.
- The I2 skipped gates remain unrun (destructive/recovery gates wait
  for a support-admission decision).

## Open contract gaps

- An answerability/entailment signal is needed before TEXT support
  admission can be calibrated. Adding a model is explicitly a user
  decision (frozen baseline forbids model changes without
  qualification). Options for the user: (a) accept abstention-on-
  graph-only semantics for now, (b) authorize an entailment-model
  qualification track, (c) other.
