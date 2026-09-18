---
change_id: CA5-EVALUATOR-DECLINE-FIX
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "EVALUATOR MEASUREMENT-ONLY (eval/ + tests/). The librarian qualification harness now recognizes the system's standard abstention (answer_synthesis.ABSTENTION_MESSAGE) as a DECLINE, so a CA4 gate-abstention that still retrieved docs is counted as a decline, not a hallucination. NO change to gold, thresholds, retrieval, ranking, or the CA4 gate. No fleet code; no bounce."
last_reviewed: 2026-09-18
---

## Contract
Measurement correctness only. `hallucinated_evidence = unsupported and ranked and not declined`. The
decline detector missed the system's own abstention phrase, so a CA4 gate-abstention with retrieved
docs (the nondeterministic spurious-PRIMARY case) would be MISCOUNTED as a hallucination. This closes
that evaluator gap. It does NOT touch gold labels, acceptance thresholds, CA4 epistemic grading, or
any supported/unsupported retrieval behavior.

## Changes
- `eval/librarian_qualification/harness.py`: extract `declined(answer, ranked)` from the inline
  detection; add the phrase `"enough grounded evidence"` (from `answer_synthesis.ABSTENTION_MESSAGE`,
  "I don't have enough grounded evidence to answer this question.") to `_DECLINE_PHRASES`. The
  prior phrases and the empty-answer rule are unchanged; `evaluate_query` now calls `declined(...)`.
- NEW `tests/determinism/test_qualification_harness_decline.py` (7 tests); TREE decl.

## Proof
UNIT_PROVEN (executed path = this worktree): a retrieved-doc abstention → `declined=True`, so
`hallucinated=False`; a substantive answer on an unsupported query → still `hallucinated=True`
(genuine hallucination preserved); empty-answer/no-docs → decline; every prior decline phrase still
recognized; a supported-query answer is never a hallucination. `py_compile` clean.

## Rejected claims
- Changing gold, thresholds, or CA4 grading/behavior (rejected — strictly evaluator decline-detection).
- Broadening detection to mask genuine hallucinations (rejected — a substantive non-decline answer on
  an unsupported query is still flagged; the added phrase matches only the abstention message).

## Open contract gaps
- RAG_QUALIFICATION (evaluator): **UPDATED** — decline-detection completeness. Production retrieval
  contracts: **NOT_AFFECTED** (no fleet code touched; no bounce).
- CA5 authoritative 64×4 run: **DEFERRED to the run itself** (next).
