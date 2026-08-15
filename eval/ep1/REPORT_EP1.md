# EP1 Entity-Proposal Qualification Report

Status: FROZEN
Date: 2026-08-14
Outcome: **FAIL — all sanctioned mechanisms measured; escalation required**

## Corpora and gold (frozen before implementation)

| Artifact | Content | sha256 (corpus dir) |
|---|---|---|
| EP1 development corpus | `eval/gold/realistic_smoke_v1/` (4 docs: psych/tech/research/transcript) | SHA256SUMS committed |
| EP1 development gold | `eval/gold/ep1_dev_gold.yaml` (208 mentions, entity-only) | file-hashed in artifacts |
| EP1 held-out corpus | `eval/gold/heldout_ep1_v1/` (4 fresh docs, same classes) | `20ac884d…` `822efcc1…` `c34a5cc8…` `ec978ec8…` |
| EP1 held-out gold | `eval/gold/ep1_heldout_gold.yaml` (103 mentions) | file-hashed |
| Measurement harness | `eval/ep1/harness_entity.py` (deterministic, per-arm artifacts) | committed |

Held-out extraction outputs were NOT inspected before the arms were
frozen; the held-out set remains untouched for a future qualifying run.

## Baseline (production labels, threshold 0.5)

| Metric | Value |
|---|---|
| exact-span precision | 0.167 |
| exact-span recall | 0.077 |
| overlap-span recall | 0.312 |
| multiword recall | 0.390 |
| core-type accuracy | 0.846 |
| bare-head rate | 0.51 |
| false-span rate | 0.323 |

Bare-head dominates: half of all proposals are head-only substrings of
the intended multiword concepts.

## Arms (measured independently, artifacts frozen)

| Arm | overlap R | mw R | type acc | false | Verdict |
|---|---|---|---|---|---|
| A labels-v2 (descriptive, bounded 20) | 0.351 | 0.398 | 0.822 | 0.291 | FAIL — marginal, type accuracy drops |
| B deterministic span completion | 0.317 | 0.398 | 0.818 | 0.312 | FAIL — no recall gain, exact precision drops |
| C A+B | 0.351 | 0.398 | 0.822 | 0.284 | FAIL — same as A |
| D per-class threshold 0.35 (concept-ish labels only, per A/B failure) | 0.447 | 0.517 | **0.742** | 0.336 | FAIL — recall up, type accuracy collapses |

## Downstream precision check (combined candidate, no production change)

threshold-v2 entities + lexical-evidence-v2 + rule pack 1.1.0 over the
smoke corpus produced fact spam on doc 02 (is_a ×20, derived_from ×24)
and 3 `causes` edges on doc 04 — the precision-first bar is violated.
The lower-threshold concept spans feed the frozen compiler noisy
pairings; the compiler stays correct (type gates) but the entity layer
pollutes its input.

## Conclusion

- Label engineering within a bounded budget: no material gain.
- Deterministic span completion: no gain; conservative rules cannot
  recover spans the model does not propose; aggressive rules overshoot.
- Per-class threshold lowering: the only recall lever, and it destroys
  core-type accuracy and downstream fact precision.
- The pinned GLiNER medium-v2.1 with uni-encoder prompts does not
  reliably propose multiword concept spans on long-form prose at a
  usable precision/recall operating point.

Per the EP1 brief: **do not endlessly tune — escalate.** The next step
is a model/provider qualification experiment (a different proposal
model, or a supervised span-expansion model), following the same
measured protocol (frozen dev+held-out sets above are reusable; the
held-out set has never been inspected).

## Downstream status

- EP1 FAIL: I1 remains blocked. Production entity policy, rule pack
  1.0.1 default, and all frozen Q1/Q1-R artifacts are unchanged.
- No production extraction code was changed by EP1.
