---
change_id: CA3-CONSTRAINT-ALIGNMENT
owner: constraint-aware-retrieval
date: 2026-09-18
status: complete
architecture_impact: "CONSTRAINT-AWARE-RETRIEVAL-V1 CA3 — THE FIRST RANKING CHANGE. Pure shared align_by_constraint (post-rerank portfolio partition; no numeric boost, cross-encoder unchanged) + flag-gated ui.py wiring (POLYMATH_CHAT_CONSTRAINT_ALIGN, default-off => byte-identical). When q0 carries a RESOLVED explicit constraint, evidence is reordered so constraint-satisfying evidence leads per strength (HARD lead / SOFT bounded / EXPLORATORY anchor), semantic order preserved within each portfolio. LIVE_PATH_PROVEN after merge + flag-on bounce."
last_reviewed: 2026-09-18
---

## Contract
CA3 is the first ranking change: `semantic rerank → constraint alignment → portfolio order`. The
cross-encoder remains the semantic-relevance authority; alignment runs AFTER it and ONLY reorders
the already-reranked evidence when q0 carries a resolved explicit constraint. Semantic order is
preserved WITHIN each portfolio — no score is added or tuned (D5 modified form). Distinct signals:
semantic relevance (how useful) vs constraint satisfaction (does it answer the question asked);
neither erases the other.

## Changes
- `shared/polymath_shared/query_constraints.py`:
  - `align_by_constraint(evidence, targets, strength)` — pure reorder of reranked evidence (dicts
    with `doc_id`). HARD: constraint-satisfying evidence leads (DIRECT portfolio), everything else
    follows (RELATED/supplemental), rerank order kept within each. SOFT: bounded — lift the source's
    best chunk to rank 2 only if it is below (never a demotion, top result keeps rank 1).
    EXPLORATORY: identity (anchor only). Identity on no-targets / unknown strength / source-absent.
    Never adds or drops an item.
  - `align_evidence_for_constraints(evidence, constraints)` — governing tier (HARD > SOFT >
    EXPLORATORY) over RESOLVED SOURCE constraints; identity when nothing resolved.
- `orchestrator/orchestrator/api/ui.py`: flag-gated (`POLYMATH_CHAT_CONSTRAINT_ALIGN`, default off)
  block right before `assemble_evidence_bundle`, applied to `evidence_rows` (common to all modes, so
  `evidence_order`→bundle→legend→synthesis inherit the order). Receipt `retrieval.constraint_alignment`
  = `{applied, strength, targets, value}`.
- NEW `tests/determinism/test_constraint_alignment.py` (15 tests); TREE decl.

## Proof
Pure helper UNIT_PROVEN (executed path = this worktree): 15/15 alignment tests — HARD source leads
(doc #1), order preserved within portfolios, multiple source chunks lead in order; SOFT lifts a
buried source to rank 2 but never demotes an already-high source and keeps the top result at #1;
EXPLORATORY + no-target/unknown/source-absent = identity; never adds/drops; HARD governs over SOFT;
only resolved constraints act. CA0/CA1 re-run green. ui.py `py_compile` + `agent_preflight` clean.
LIVE_PATH_PROVEN after merging to production + setting `POLYMATH_CHAT_CONSTRAINT_ALIGN=1` + a
port-gated bounce (numbers in the register row + CONTINUITY):
- HARD "In Murch's book…" → Murch now leads the evidence (doc #1); the highly-relevant non-source
  passage remains as RELATED/supplemental below it.
- Control (no named source) → identical ranking to pre-CA3 (byte-identical when no resolved constraint).
- SOFT/EXPLORATORY behave per spec; success@10 maintained; no regression vs the committed baseline.

## Rejected claims
- Numeric boost (`rerank_score + source_bonus`) or RRF/rerank weight tuning (rejected — D5: partition,
  not tuning; the cross-encoder is untouched).
- Murch-specific rule (rejected — generic over any resolved SOURCE constraint).
- Forcing all source evidence ahead for SOFT (rejected — SOFT is bounded, never demotes a stronger result).
- Changing gold labels (rejected).

## Open contract gaps
- CANDIDATE_ENGINE / RERANK: **TESTED_UNCHANGED** — CA3 runs strictly AFTER rerank; candidate
  generation, fusion and the cross-encoder are untouched.
- EVIDENCE_SELECTION / RETRIEVAL_RECEIPT: **UPDATED** — evidence ORDER now reflects the constraint
  partition (flag-on); additive `constraint_alignment` receipt.
- SYNTHESIS: **UPDATED (order only)** — synthesis sees the partitioned order; formal DIRECT/PARTIAL/
  RELATED role tagging + need→evidence threading is **DEFERRED to CA4**.
- QUERY_PLANNER: TESTED_UNCHANGED (consumes resolved constraints from CA2).
- Full qualification vs baseline + the 6 admission acceptance cases: **DEFERRED to CA5**.
