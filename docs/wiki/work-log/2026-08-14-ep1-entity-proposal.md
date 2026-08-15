---
change_id: ep1-entity-proposal
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (measurement only; no production change)
---

# EP1: entity-proposal qualification

## Contract

Increase reliable entity-span coverage on realistic long-form prose
without weakening semantic precision or compiler authority. Freeze a
development corpus + gold entity mentions, freeze an untouched
held-out corpus + gold, measure the baseline and separate mechanism
arms (label engineering, deterministic span completion, per-class
thresholds), and promote only a precision-first winner. On FAIL: do
not endlessly tune — record and escalate to a model change.

## Changes

- Frozen corpora + gold: `eval/gold/heldout_ep1_v1/` (4 fresh docs,
  hashes recorded before any implementation),
  `eval/gold/ep1_dev_gold.yaml` (208 mentions),
  `eval/gold/ep1_heldout_gold.yaml` (103 mentions). Entity mentions
  only; speakers/timestamps deliberately absent (noise proposals
  count as false spans).
- `eval/ep1/harness_entity.py` (new): deterministic entity metrics
  (exact/overlap recall, core-type accuracy, multiword recall,
  bare-head rate, false-span rate, per-doc/per-label) with arms
  baseline / labels-v2 / expand / both / threshold-v2 /
  threshold-v2-expand. Frozen artifacts in `eval/ep1/artifacts/`.
- `eval/ep1/REPORT_EP1.md` (frozen): full measurements + verdict.
- No production extraction code changed by EP1.

## Proof

- Baseline: overlap recall 0.312, multiword recall 0.390, bare-head
  rate 0.51, core-type accuracy 0.846.
- Arm A (labels-v2, bounded): marginal recall, type accuracy down →
  FAIL.
- Arm B (deterministic completion): no gain, exact precision down →
  FAIL.
- Arm D (per-class threshold 0.35 for concept-ish labels, sanctioned
  by A/B failure): overlap 0.447 / multiword 0.517 but type accuracy
  0.742 and downstream fact spam (is_a ×20, derived_from ×24, 3
  spurious causes) → FAIL precision-first.
- Held-out set untouched (never scored).

## Rejected claims

- No signature/scope/compiler change; no hybrid evidence; no global
  threshold change; no hand-authored rules for the smoke documents.

## Open contract gaps

- EP1 FAIL: I1 remains blocked. Escalation sanctioned per the EP1
  brief: a model/provider qualification experiment (new proposal
  model) using the same frozen protocol; the held-out set remains
  unexposed for that experiment's final run.
