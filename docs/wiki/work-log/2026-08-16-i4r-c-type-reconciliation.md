---
change_id: i4r-c-type-reconciliation
owner: worker
date: 2026-08-16
status: complete
architecture_impact: extends-rescue-lane-behind-flag
last_reviewed: 2026-08-16
---

# I4R-C: type reconciliation

## Contract

Third staged I4R sub-gate: an entity occupying a trigger-governed slot
whose canonical type is incompatible with the slot signature (rule
pack subject_core/object_core, via the I3R-R1 trigger_predicate_id) is
re-queried over its full argument NP with the NORMAL policy vocabulary
(temporal directive §10). Only a full-span, slot-legal canonical
prediction re-types the entity (pass_kind=type_reconciliation);
refusals and slot-illegal answers keep the original entity and the
pairing abstains downstream — no deterministic type rewrite.

## Changes

- workers/rescue.py: _slot_types + type_reconciliation_candidates +
  apply_type_reconciliation (dedup, batched /rescue, audit with
  re_typed_to per query).
- workers/extract_worker.py: passes the rule pack to apply_rescue.
- tests/determinism/test_i4r_c_type_reconciliation.py (4 tests).

## Proof

Cumulative frozen-I4 measurement (A+B+C): identical to A+B —
TP 12 / FP 6 / FN 14, P 0.667, R 0.462; envelope 7/8; must-not 18/18;
provenance 17/17 exact. Audit: 9 candidates; GLiNER full-span-answered
several ("harbor terminal"→Location 0.718, "chief medical officer"→
Person 0.713) but NONE of the answers were slot-legal, so 0 re-types
applied — the stage is precision-safe and has zero effect on this
holdout (the Nimbus-class defect did not arise as a slot-incompatible
candidate here). Frozen evidence restored byte-identically.

## Rejected claims

- No claim that type reconciliation helps frozen I4 — measured zero
  delta, recorded as such.

## Open contract gaps

- I4R-D frame arbitration pending; combined run after.
