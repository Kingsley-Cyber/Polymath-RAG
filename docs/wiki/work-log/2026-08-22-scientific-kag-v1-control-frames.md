---
change_id: scientific-kag-v1-control-frames
owner: worker
date: 2026-08-22
status: complete
architecture_impact: adds-deterministic-infinitive-control-to-v2
last_reviewed: 2026-08-22
---

# SCIENTIFIC-KAG-V1 SLICE B (phase 5): infinitive control frames

## Contract

Owner decision: control frames land BEFORE scientific predicates,
because without them relation direction is corrupted
("ToT allows LMs to explore paths" must yield LMs explores paths,
never ToT explores paths). Mandatory provenance:
binding_source CONTROL_OBJECT / CONTROL_SUBJECT and a stored
dependency_path. Fail closed when ambiguous.

## Changes

1. `contracts.py`: BindingSource gains CONTROL_SUBJECT / CONTROL_OBJECT;
   both join V2_BINDING_SOURCES (the hard rule accepts them).
2. `observability.py`: discipline map registers both as UD_PRIMARY.
3. `workers/workers/kimi_v2_candidates.py`:
   - authored lists SUBJECT_CONTROL_VERBS {use, leverage, attempt, try,
     begin, continue, fail, help} and OBJECT_CONTROL_VERBS {allow,
     enable, permit, require, cause} — the owner's lists verbatim.
   - `_control_controller`: fires only when the embedded predicate token
     has NO own subject and its governor is the matrix verb under
     xcomp/ccomp/advcl. Subject-control inherits the matrix nsubj;
     object-control takes the unique entity-bearing argument child of
     the matrix verb BETWEEN matrix and embedded token — which selects
     LMs over ToT regardless of en_core_web_sm's arc quirks.
   - zero or multiple controllers → no candidate (fail-closed);
     dependency_path records `control[lemma:frame]`.
   - one hop only; embedded explicit arguments always win.

## Proof

- Object control: "Acme allows Bitwork to use Cipher." → exactly one
  uses-fact Bitwork→Cipher, CONTROL_OBJECT, matrix subject excluded.
- Subject control: "ToT attempts to create benchmarks." → ToT→benchmarks,
  CONTROL_SUBJECT.
- Coordination: conj-linked controllers each bind; matrix never binds.
- Unlicensed matrix verb ("imagined") → no controller invented.
- Full suite: 861 → 865 passed.

## Sequencing note

The owner's exact stress sentences use embedded verbs whose predicates
(`trained_on`, solve-class) are licensed by pack v1.4.0 (phase 4). The
control mechanism is proven above with currently licensed lemmas; the
verbatim trio joins the validation suite once v1.4.0 lands.

## Open gaps

Phase 4 pack v1.4.0 + type ontology hierarchy; phase 6 temporal model;
acceptance harness; validation suite.
