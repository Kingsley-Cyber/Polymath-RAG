---
change_id: CA4-EVIDENCE-GRADING
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA4 — evidence support-role grading (DIRECT/PARTIAL/RELATED) + a multi-signal answerability gate. Pure shared grade_evidence + a flag-gated epistemic condition in answer_synthesis.render_answer + ui.py threading. Resolves the unsupported-hallucination gate: an answer must be grounded in >=1 DIRECT/PARTIAL chunk, else it states the gap instead of fabricating from adjacent RELATED material. Flag POLYMATH_CHAT_EVIDENCE_ROLES, default-off => byte-identical. LIVE_PATH_PROVEN after merge + flag-on bounce."
last_reviewed: 2026-09-18
---

## Contract
CA4 grades each final-evidence chunk DIRECT/PARTIAL/RELATED from MULTI-SIGNAL (need satisfaction +
constraint satisfaction + semantic relevance — NOT a rerank-score band) and derives a query
epistemic state. The state drives the answerability gate: lexical coverage stays necessary but is
not sufficient — an answer must also be grounded in >=1 DIRECT or PARTIAL chunk. When only adjacent
RELATED material exists (e.g. semantic bleed on an out-of-domain query), the answer states the gap
rather than fabricating a source-supported claim. RELATED is usable, not failed; SYNTHETIC_INSIGHT
stays a distinct reasoning product (not graded here).

## Changes
- `shared/polymath_shared/query_constraints.py`: `EVIDENCE_ROLES` + `grade_evidence(evidence, plan)
  -> ({chunk_id: role}, epistemic)`. DIRECT = user-need (retrieved by a USER-origin subquery) AND
  relevant (rerank_score > 0) AND satisfies every HARD source constraint; PARTIAL = user-need +
  relevant but NOT the named source; RELATED = bridge-only or not relevant. `epistemic` =
  `{directly_established, establishes_need (>=1 DIRECT|PARTIAL), n_direct, n_partial, n_related}`.
- `shared/polymath_shared/answer_synthesis.py` `render_answer`: multi-signal gate — when the bundle
  carries `epistemic` and `establishes_need is False`, verdict → `insufficient_evidence` (states the
  gap) even if lexical coverage passes. Bundle WITHOUT `epistemic` (flag-off) ⇒ byte-identical.
- `orchestrator/orchestrator/api/ui.py`: flag-gated (`POLYMATH_CHAT_EVIDENCE_ROLES`) grading of
  `fast["evidence"]`; `bundle["support_roles"]` + `bundle["epistemic"]`; receipt `retrieval.epistemic`.
- NEW `tests/determinism/test_evidence_grading.py` (9 tests); TREE decl.

## Proof
UNIT_PROVEN (executed path = this worktree): 9 grading tests — DIRECT/PARTIAL/RELATED by signal;
profile-only chunk RELATED even if relevant; HARD source=DIRECT / relevant-non-source=PARTIAL; SOFT
does not gate DIRECT; out-of-domain (all rerank<0) → all RELATED, establishes_need False; a PARTIAL
still establishes the need; no-plan fallback. The render_answer GATE proven via the existing
`grounded_answer`+`_bundle` fixture: base bundle → answered; `epistemic.establishes_need=False` →
abstains (states the gap); `=True` → unchanged. `test_answer_synthesis` (full suite) green — the gate
is byte-identical without the `epistemic` key. py_compile + preflight clean.
LIVE_PATH_PROVEN after merge + `POLYMATH_CHAT_EVIDENCE_ROLES=1` bounce (numbers in register/CONTINUITY):
supported queries carry DIRECT grades + answer normally; HARD source evidence = DIRECT, supplemental
= PARTIAL/RELATED; a spurious-PRIMARY out-of-domain query grades all-RELATED → states the gap (no
fabricated evidence) → the §23 unsupported-hallucination gate holds at 0.

## Rejected claims
- Determining role primarily from rerank-score BANDS (rejected per the owner — role is need +
  constraint + relevance + coverage; relevance uses the cross-encoder SIGN, not a tuned threshold).
- Converting absence of DIRECT into automatic refusal for ALL cases (rejected — the gate fires only
  when NOTHING is DIRECT *or* PARTIAL; a PARTIAL answer is still produced).
- Grading SYNTHETIC_INSIGHT as evidence (rejected — it is a reasoning product, kept separate).

## Open contract gaps
- SYNTHESIS / RETRIEVAL_RECEIPT: **UPDATED** — bundle carries `support_roles`/`epistemic`; receipt
  `epistemic`; the answerability verdict is now multi-signal (flag-on).
- RESOLUTION_STATE (P10): **TESTED_UNCHANGED** — grading reads the same aspect/evidence; no change to
  the resolution round.
- The RICHER epistemic OUTPUT (present RELATED material as an explicitly-labelled SYNTHETIC_INSIGHT
  narrative when direct support is absent but related exists): **DEFERRED** — CA4 states the gap +
  surfaces the grades/roles; the synthetic-insight PROSE rendering is a bounded follow-on.
- Detector false-positives ("the X system/method", bare author names) still harmless (unresolved) —
  tightening DEFERRED.
- Full 64×4 qualification vs baseline + the 6 acceptance cases: **DEFERRED to CA5**.
