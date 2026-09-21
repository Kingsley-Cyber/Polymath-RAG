---
change_id: D1-EMPTY-ADMISSION-IS-A-CAUSE
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "ADAPTER_RUNTIME: `store.admission_ids` now returns every admission TrailSignal made for a run, including one that admitted nothing (read from the harness action row). No schema change. Branch `fix/d1-empty-admission-cause`."
last_reviewed: 2026-09-21
---

# D1 — an admission that admitted nothing is still a citable cause

## Contract
Owner direction 2026-09-21 (real E2E; a software failure is not a valid outcome). `AGENT_OPERATING_DOCTRINE.md` "Existing defects": a recorded defect that BLOCKS acceptance is addressed. D1 was recorded and deferred as non-blocking
(`CONTINUATION.md` "Known defects"); real input made it blocking.

## Changes
- FOUND AGAIN (REAL_INPUT_EXECUTED, run `adr_47b7277c04f3b756903ff89f796b35aa`: hosted endpoint, non-admin principal, corpus `cinema`, embedded Trail, two real research rounds). Round 1: Trail admitted 8 of 20 real observations; judgement
  strengthened two hypotheses and weakened one. Round 2: Trail admitted 0 of 6 (first-person practitioner blogs are not registered sources). Trail's next `hypotheses.judge` cited that EMPTY admission (`hadm_fca1f9b81a83`) as the cause of
  its verdicts; the runtime refused it — "not an allowed cause in this step" — and the run ended `terminal_gap: PHI_VERDICT_INVALID` at `L_judge`.
- Cause: `store.admission_ids` read admission ids from `adapter_admitted_evidence` only, so an admission with zero admitted rows did not exist for `_allowed_causes`. The admission IS persisted (`adapter_harness_actions.admission`).
  The defect is in Polymath's store, not in Trail's byte-pinned code.
- Fix: `admission_ids` = admitted-evidence admissions ∪ the run's harness-action admissions. Same change in the in-memory store double.

## Proof
- `tests/determinism/test_adapter_empty_admission_cause.py` (3): an empty second admission is an allowed `evidence_admission` cause; another run's admission is not; the Postgres query reads both tables.
- Throwaway Postgres (66 migrations): `admission_ids` returns `['hadm_empty', 'hadm_first']` for one non-empty and one empty admission; the Postgres-backed adapter suites + ownership + harness action = 40 passed. Container removed.

## Rejected claims
- "Run 2 was a governed rejection." No: Trail's governance inside it was real (admission, judgement), but the run died on this software defect before qualification. It is recorded as FAILED at `L_judge`.

## Open contract gaps
- `ADAPTER_RUNTIME`: **UPDATED** (allowed-cause set; no contract or schema change). `ADAPTER_CONTRACT_V1`, `MCP_SURFACE`: **NOT_AFFECTED**.
- M1-01..03 and the other recorded defects: unchanged, **DEFERRED** unless real input makes them blocking.
