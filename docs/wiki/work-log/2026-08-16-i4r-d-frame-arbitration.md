---
change_id: i4r-d-frame-arbitration
owner: worker
date: 2026-08-16
status: complete
architecture_impact: rule-pack-frames-compiler-arbitration
last_reviewed: 2026-08-16
---

# I4R-D: syntax-guided frame arbitration (rule pack v1.3.0)

## Contract

Fourth staged I4R sub-gate: predicate contracts declare the grammatical
constructions they own (rule-pack `frames` over trigger lexical class +
required dependency relations of the argument head tokens). spaCy
supplies the structure; deterministic predicate semantics decide.
leads owns the transitive verb construction (object = direct dobj);
has_role's verb arm owns prepositional/role constructions (pobj/obl);
nominal and multiword arms are unconstrained; rules without frames are
unconstrained (all 26 others byte-identical). A shared-trigger sentence
("X leads Y") satisfies one frame -> one fact; the other predicate's
candidate REJECTs (frame_violation).

## Changes

- core-predicates-v1.3.0.yaml (+ compiled_lexical-v1.3.0.json):
  frames on leads + has_role; loader v1.3.0 branch.
- compiler.py: compile_relation gains `syntax` (syntax-evidence-v1);
  stage 2b frame arbitration; _frame_satisfied + _head_token_of.
- extract_worker passes sl.syntax to compile_relation.
- tests/determinism/test_i4r_d_frame_arbitration.py (6 tests).

## Proof

Cumulative frozen-I4 measurement (A+B+C+D, pack 1.3.0):
TP 12 / FP 5 / FN 14 → P 0.706 (C: 0.667), R 0.462; envelope 7/8;
must-not 18/18; provenance 16/16 exact. Frame arbitration removed one
shared-trigger double emission without touching recall. Full suite
280 passed / 50 skipped (pack default remains 1.2.0 in production
settings; 1.3.0 is selected by POLYMATH_WORKER_RULE_PACK_VERSION for
the rescue configuration). Frozen evidence restored byte-identically.

## Rejected claims

- No claim frames generalize beyond the leadership class; I5 decides.
- No frame tuning against gold: the dobj/pobj split is a general
  grammatical distinction recorded before measurement.

## Open contract gaps

- Combined I4R evaluation (full phase set) runs next; I5 sealed
  holdout awaits separate authorization.
