# Next Session

## Start Here

Read:
1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `ARCHITECTURE.md`
4. `RAG_E2E_CHECKLIST.md` (next unchecked gate: I1)

## Last Completed

- **I4 fresh heterogeneous acceptance — FAIL (frozen, no production
  change)** (work log `2026-08-16-i4-fresh-acceptance.md`, report
  `eval/i4/REPORT.md`, frozen state `eval/i4/FROZEN_STATE.json`,
  verifier `eval/i4/verify_i4.py`, capability matrix
  `eval/i4/capability_matrix.json`). Fresh 5-doc corpus (healthcare/
  cloud/manufacturing/edtech/supply-chain), 26 supported positives,
  8 out-of-envelope, 18 must-not-assert, 4-tier entity gold, all
  frozen pre-extraction. Result: control plane / durability (1.000
  referential recall) / provenance (18/18 exact) / graph / retrieval
  (10/10) / must-not (18/18) all green; **fact bar FAIL — TP 10 /
  FP 10 / FN 16 → P 0.500, R 0.385** (required >=0.95 / >=0.70) and
  out-of-envelope 7/8. Classified owners (no repairs performed):
  (1) GLiNER fresh-domain span boundary contraction + typing drift
  (dominant FP/FN driver — model/labels/threshold remain FROZEN);
  (2) leads/has_role shared-trigger double emission (compiler
  candidate surface); (3) boundary-strict gold matching pairs FN+FP
  on surface variants. No I3/I3R class reappeared. **Next: STOP —
  a named repair gate (I4R) must be explicitly authorized; do not
  tune or repair autonomously.**
- **I3R — repository-realigned repair regression: PASS** (commits
  `8a0e89f`→`ce2545f`, closeout report `eval/i3_5doc/REPORT_I3R.md`).
  Typed trigger contract + rule pack v1.2.0 default; trigger-scoped
  argument frames; bounded local references; durable mentions/
  factless entities (migration 0009); verifier orphan semantics +
  revocable query_ready (invalidate_corpus_projections); exact
  provenance (migration 0010); real GLiNER pins. I3 rerun: false
  facts 8→0, reconstruction hash-equal, Q1/E3B locks byte-identical.

