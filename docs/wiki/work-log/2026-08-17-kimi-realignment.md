---
change_id: kimi-architecture-realignment-v1
owner: worker
date: 2026-08-17
status: in-progress
architecture_impact: realigns-candidate-generation-to-kimi-ud-role-binding
last_reviewed: 2026-08-17
---

# KIMI-ARCHITECTURE-REALIGNMENT-V1

## Contract

Realign extraction to the original Kimi two-pass GLiNER + deterministic
predicate compiler architecture per ADR-0016. The core change:
candidate arguments derive from the UD dependency tree (not left×right
positional pairing), PropBank ARG0/ARG1 roles are assigned to
endpoints, and type compatibility runs AFTER structural candidates
exist. Production default stays legacy_v1 until separately qualified.

## §0 Baseline (frozen at start)

HEAD: 1b4dc96. Tree clean. Suite: 296 passed / 53 skipped.
I4 baseline (legacy_v1 + rescue-D): TP=12 FP=5 FN=14 P=.706 R=.462.
Model: urchade/gliner_medium-v2.1 @ 40ec4193, threshold 0.5.

## Changes

(in progress)

## Changes

- workers/workers/kimi_candidates.py: UD-anchored candidate generation
  (trigger head → syntactic dependents → entity mapping → structural
  argument candidates), type precheck AFTER structural candidates,
  bounded linear recall fallback, binding_source discipline.
- workers/workers/extract_worker.py: dispatch to kimi_v1 or legacy_v1
  via POLYMATH_RELATION_PIPELINE env (default legacy_v1).
- tests/determinism/test_kimi_candidates.py: 6 tests (UD binding,
  structural candidate before type check, no explosion, fallback,
  token mapping, dispatch).
- eval/kimi_realignment_v1/REPORT.md: full measurement report.

## Proof

- 6 unit tests green; full suite 296+6=302 passed / 53 skipped.
- Frozen I4: legacy TP=12/FP=5/FN=14 P=.706 R=.462 → kimi TP=11/FP=5/
  FN=15 P=.688 R=.423. No P/R improvement (quality blocked on model
  typing), but diagnostic honesty improved: key sentence now shows
  TYPE_PRECHECK_IMPOSSIBLE with structural context instead of the
  misleading SUBJECT_ENDPOINT_UNAVAILABLE. No FP regression. No
  explosion. All safety gates held.
- Frozen evidence restored byte-identically (d26a1c37...).

## Rejected claims

- No claim that kimi_v1 improves extraction quality: it does not on
  frozen I4. The architecture is correct; the remaining bottleneck
  is the frozen model's type classification.

## Open contract gaps

- PropBank ARG0/ARG1 role assignment is structurally ready (UD args
  classified) but not yet wired into the compiler as semantic role
  evidence (the role assignment bridge from Phase 8 of the directive
  remains future work).
- I5, model qualification, predicate signatures: not started.
