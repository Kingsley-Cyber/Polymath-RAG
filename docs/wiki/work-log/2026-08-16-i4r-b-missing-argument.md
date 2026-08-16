---
change_id: i4r-b-missing-argument
owner: worker
date: 2026-08-16
status: complete
architecture_impact: extends-rescue-lane-behind-flag
last_reviewed: 2026-08-16
---

# I4R-B: missing-argument rescue

## Contract

Second staged I4R sub-gate (umbrella authorization 2026-08-16, staged
plan confirmed after the temporal-architecture alignment):
trigger-governed grammatical slots (nsubj/dobj/obl/pobj via
prep-hop, agent) whose noun chunk has NO GLiNER entity are re-queried
with the NORMAL policy vocabulary (pass-1 label set — temporal
directive §10: never slot-forced types); exact-full-span-only
acceptance; the canonical type flows into the existing type
compatibility machinery. Free-floating NPs never qualify.

## Changes

- workers/rescue.py: missing_argument_candidates + apply_missing_
  arguments (dedup, batched /rescue, pass_kind=missing_argument_
  rescue, canonical mapping recorded). ARGUMENT_DEPS covers UD and
  spaCy ClearNLP schemes; prepositional arguments reached via
  trigger->prep->pobj. Quantified NPs (nummod/quantmod children) are
  excluded on syntax alone — descriptions are not referential entity
  endpoints (surfaced by the B07 envelope audit, fixed as a general
  rule, not a fixture patch).
- workers/extract_worker.py: passes the profile label set (normal
  vocabulary) to apply_rescue.
- tests/determinism/test_i4r_b_missing_argument.py (6 tests).

## Proof

Cumulative frozen-I4 measurement (boundary + missing_argument):
TP 12 / FP 6 / FN 14 → P 0.667 (A: 0.625), R 0.462 (A: 0.385);
envelope 7/8; must-not 18/18; provenance 17/17 exact. The first
measurement showed envelope 6/8 (B07 asserted via the quantified NP
"two new surgeons"); the nummod exclusion restored 7/8 while keeping
the recall gain (+2 TP: Amara Osei, chief medical officer class).
Accepted rescues: Amara Osei (0.916), chief medical officer (0.713),
curriculum designer (0.522), Brightpath (0.608), assembly line (0.543).
Frozen evidence restored byte-identically; hashes verified.

## Rejected claims

- No slot-forced label querying (superseded by temporal directive).
- No claim of generalization — I5 decides.

## Open contract gaps

- I4R-C type reconciliation, I4R-D frame arbitration pending.
