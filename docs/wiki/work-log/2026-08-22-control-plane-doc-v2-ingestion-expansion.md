---
change_id: control-plane-doc-v2-ingestion-expansion
owner: governance
date: 2026-08-22
status: complete
architecture_impact: documentation-only-diagnostic-expansion
last_reviewed: 2026-08-22
---

# CONTROL-PLANE DIAGNOSTIC: expand for PREDICATE-COMPILER-V2 ingestion

## Contract

Owner request: ensure `docs/INGESTION_CONTROL_PLANE.md` (the parallel
session's assessment, written at `8e78657`) adheres to the new
ingestion path. Documentation + measured diagnostics only; no runtime
change in this slice.

## Changes

Section 8 appended to `docs/INGESTION_CONTROL_PLANE.md`, all numbers
measured live:

1. **D9 (new defect):** `relation_pipeline` is absent from both the
   extract worker's advertised contracts and the run's pinned
   `execution_contract` — contract-pinned claiming cannot see the
   legacy/V2 split, so a mixed fleet can interleave association and
   dependency rows into one ledger with no objection. Fix surface
   anchored to `shared/polymath_shared/execution.py` (run dict, worker
   advertisement dict, compatibility-check key tuple).
2. **Intake-provenance diagnostics:** SQL over the migration-0023
   columns that turns "which generator produced this ledger" into a
   query (`binding_source` distribution + missing-trigger-token count),
   plus today's measured A/B table.
3. **D1+D2 re-measured:** today's failed v2 leg burned its retry
   budget in seconds exactly per D1/D2; forensics recipe via
   `receipts.error`.
4. Suggested order gains D9 between steps 2 and 3.

## Proof

- Worker contracts JSON captured from live `worker_registrations`
  (no `relation_pipeline` key).
- Provenance SQL executed against core-3-v1 both legs; numbers match
  the slice-4 work record.
- `receipts.error` path exercised today during leg-B forensics.

## Rejected claims

- "D9 needs a claiming-code change." — the compatibility check is
  generic over a key tuple; only data + one tuple literal change.
- "Mixed binding_source rows are harmless." — they make every A/B
  measurement untrustworthy, which is the doc's own D4 argument shape.

## Open contract gaps

- Implementing D9 is runtime work for the next admitted slice.
