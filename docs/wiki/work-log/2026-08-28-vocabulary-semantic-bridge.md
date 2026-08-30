---
change_id: VOCABULARY-SEMANTIC-BRIDGE
owner: governance
date: 2026-08-28
status: implemented
architecture_impact: none (repair/measurement log)
last_reviewed: 2026-08-29
---

# 2026-08-28 — Vocabulary semantic bridge: contract repaired, semantics rejected

Full report: `eval/v5/VOCABULARY-SEMANTIC-BRIDGE-FINAL.md`.

Question asked: is the deterministic vocabulary / concept-family layer
forgotten or deliberately disconnected? Answer: **forgotten for the
contract, unproven for the semantics** — and those are two different
defects.

## What was wrong

`build_concept_families` keyed concept support on `parent_id`, but
SUMMARY-WORKER-FLEET-V1 (dff12ef, 2026-08-24) moved the caller to a
direct DB read assembling `("summary_id","entities","concepts","summary")`.
Support identity resolved `None` for every row, all 1,775 parent
neighbourhoods collapsed onto one sentinel, the collapsed family scored
support 1, and the `min_support >= 2` precision guard rejected it. Zero
families, zero aliases, no error — while the unit suite stayed green
because it feeds the pre-refactor payload shape. The `AGENTS.md`
callsite-drift trap, one refactor later.

## What was fixed

Explicit `support_id` in the worker SELECT/assembly; explicit
`_support_identity()` that raises typed `MissingSupportIdentity` rather
than collapsing. Support is the PARENT EVIDENCE NEIGHBOURHOOD, proved not
assumed: 3,016 parent_summaries rows cover only 1,775 distinct parent_ids
(1,241 parents carry two summary rows), so `summary_id` would let one
neighbourhood corroborate itself and clear the guard. New production-shape
matrix A–G plus a mutation-tested callsite pin.

## Why production backfill is NO-GO

With the contract repaired the layer runs, and its output is wrong. It
merges concepts on **co-occurrence** and uses that as **synonymy**:

- canary: `EDR` and `SIEM` declared aliases of each other, plus six
  heading fragments, in one family
- hard negatives: 6/7 wrong (`incident response`↔`infrared spectroscopy`,
  `microsoft`↔`microsoft word`, `about the author`↔`siem`)
- production scale: 10,688 concepts collapse to 3 families, one with
  10,060 members
- anti-scaling: family count FALLS as evidence grows (5→4→3→2 at
  100→1000 parents); time is quadratic (31.2 s at 3,015 parents)

The one correct case (`EDR` ↔ `endpoint detection and response`) is
structurally identical to the EDR/SIEM failure from the algorithm's point
of view, so no threshold fixes it. The layer was validated at 24 parent
summaries and does not survive 1,775.

Second, independent gap: `ASK.related_concepts` cannot populate even with
families present — the writer never sets `concept_families.definition`
(nor writes `concept_vocabulary` at all) while `ask.py::_concept_graph`
matches solely on `definition`.

## Constraints honoured

reach.py untouched (R1E REJECT stands); FAST/HYBRID/GRAPH unchanged and
not recommended as eval candidates; `min_support=2` never lowered; no
embeddings, no LLM normalization, no admission changes. Summary routing
re-verified (PASS) and abstention re-verified (PASS). Full suite: 979
passed / 83 failed, failure set byte-identical to baseline.

Child-boilerplate ranking defect recorded as OBSERVED and left in scope
for separate work.


## Contract

Qualify semantic family merging for the vocabulary layer without loosening admission.

## Changes

Vocabulary semantic bridge evaluation; concept_families kept EMPTY in production after failed qualification.

## Proof

6/7 hard negatives wrong — merge unsafe; measured and reported (VOCABULARY-SEMANTIC-BRIDGE-FINAL.md).

## Rejected claims

No production merge enabled; co-occurrence merging rejected by measurement.

## Open contract gaps

A qualified semantic merge needs a different signal than co-occurrence before re-proposal.
