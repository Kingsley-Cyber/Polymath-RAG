---
change_id: entity-admission
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (experiment-only; production unchanged)
---

# E2/C1.1: entity admission qualification

## Contract

Measure a deterministic entity-admission layer between accepted GLiNER
spans and durable entity identity: GLOBAL / SCOPED / MENTION_ONLY,
decided from observable lexical/reference features (never GLiNER
confidence, never a model). Freeze an authored gold set; score the
candidate; project the admission-filtered G4 graph. Promote only if
local accuracy AND the downstream G4/G4.2 checkpoint both pass.

## Changes

- `eval/admission/entity_admission.py` (experiment-only policy
  entity-admission-v1, pure deterministic DAG + reasons).
- `eval/admission/admission_gold.json` (44 items, frozen hash
  70d09b80, three classes, adversarial cases included).
- `eval/admission/qualify_admission.py` + frozen metrics artifact +
  `REPORT.md`.
- Lifecycle inspection recorded: durable identity is assigned at
  candidates.py:121-122 (canonical_entity_id) — the boundary the
  admission layer precedes.

## Proof

- Local: accuracy 0.909; MENTION_ONLY P=1.0; GLOBAL R=1.0. Four
  error classes recorded (sentence-capitalization, digit-suffixed
  generics, weak modifiers, capitalized generic+noun).
- Downstream projection: generic hubs (the system/the model/the
  platform/the database) → MENTION_ONLY (dropped); multiword SCOPED
  hubs + named entities survive; component DxL leaves mis-classify
  GLOBAL via the digit signal (same class as "Model 3").

## Rejected claims

- Not promoted. No production change; no GLiNER/compiler/
  canonicalization change; no numeric fake confidence.

## Open contract gaps

- admission-v1.1 revision (version signal requires co-occurring
  proper/acronym signal or excludes hex-index suffixes; weak-modifier
  handling) → then the decisive downstream G4/G4.2 rerun with a
  rebuilt disposable projection.
