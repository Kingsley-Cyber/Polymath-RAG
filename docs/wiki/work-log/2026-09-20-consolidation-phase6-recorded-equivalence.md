---
change_id: CONSOLIDATION-MIGRATION-PHASE6-RECORDED-EQUIVALENCE
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — test fixtures and one test. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 6 validation 3: the embedded TrailSignal core reproduces recorded envelopes

## Contract
`docs/migration/ADR-TRAIL-EMBEDDING.md` "Validation" 3: the recorded request envelopes of the external-review M1 reproductions produce the same results from the embedded service as from TrailSignal's own
checkout. `EXECUTION_PLAN.md` Phase 6 gate: embedded operations pass equivalence / contract tests.

## Changes
- `tests/fixtures/trail_recorded_envelopes/` — the three recordings (`m1_01`, `m1_02`, `m1_03`) copied from branch `review/m1-reproductions`; the machine-local `trail_root` key was REMOVED on import (INV-7);
  nothing else changed. Each names `trail_head: de64d84`.
- `tests/determinism/test_trail_core_recorded_equivalence.py` — replays every recorded request through `governance/trail/embedded.operate` with the recordings' fixed clock and compares the whole envelope.

## Proof
- `m1_01` (admit → judge) and `m1_03` (registry projection → filter judgement): every replayed envelope is EQUAL to the recording — operation ids, registry snapshot id and hash, results, result hashes.
- `m1_02`: the recording holds the ERROR TrailSignal raised (finding M1-02, `ValidationError: admitted_evidence must carry exactly the admitted_evidence_ids`); the embedded copy raises the same error for the
  same request. Byte-identical code, identical behaviour — including the defect.
- Run under TrailSignal's interpreter (3 passed; with the other TrailSignal-dependent tests 8 passed); under this repo's interpreter the file SKIPS with the reason printed (`packageurl`).
- Guards 0 / 0 / 0 / READY.

## Rejected claims
- "TrailSignal's own test-suite was ported" (validation 2). Its research-operation tests target the Postgres store adapter and the MCP daemon, neither of which is imported; they do not apply to the embedded
  composition. The store port's contract (first commit wins, replay, `load_admitted`) is covered by `test_trail_core_embedded.py` instead.
- "The embedded core is correct." It is EQUIVALENT — M1-01..03 and D1 are reproduced, not fixed.

## Open contract gaps
- None affected: NOT_AFFECTED.
