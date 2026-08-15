---
change_id: em1-model-qualification
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (measurement only; no production change)
---

# EM1: entity model qualification

## Contract

Determine whether replacing ONLY the entity-proposal model recovers
realistic long-form entity coverage. Four pinned candidates (baseline
medium-v2.1; large-v2.1; large-v2.5; NuNER_Zero) under one fair
inference contract; threshold grid chosen on DEV only; promotion
floors (overlap ≥0.55, multiword ≥0.55) with precision-first safety;
the winning model chosen BEFORE the held-out set is ever scored.
No production stack change during selection.

## Changes

- `eval/em1/models.yaml` (frozen pins: repos @ exact revisions,
  licenses, contract, grid).
- `eval/em1/qualify_em1.py` (new): direct-API fair-contract runner
  with file-sha256 snapshots, load/peak-memory records, and
  determinism re-checks per (model, threshold).
- 28 frozen grid artifacts in `eval/em1/artifacts/`.
- `eval/em1/REPORT_EM1.md` (frozen): measurements + FAIL verdict.
- No production extraction code changed.

## Proof

- Measurement-integrity finding: the EP1 baseline was scored on
  spans corrupted by a sidecar offset misalignment in the EP1
  harness; the EM1 clean direct-API contract supersedes it as the
  honest baseline (EP1 artifacts left untouched).
- Clean baseline: overlap 0.356–0.452, multiword 0.449–0.551,
  type acc 0.824, false 0.296 (at 0.45).
- A-large-v21: overlap ≤0.534, mw ≤0.644, type acc 0.766, false
  0.42 — below overlap floor. FAIL.
- B-large-v25: overlap 0.606, mw 0.695 at 0.40 — clears recall
  floors but false-span 0.48 (+18 pts) and type acc 0.70 (−14 pts):
  precision-first safety FAIL.
- C-nuner-zero: overlap ≤0.538, exact precision ~0.02. FAIL.
- Determinism verified on every run; operational records in the
  artifacts (cold/warm load, peak MPS 744–1752MB, no OOM on 32GB).
- heldout_ep1_v1 NOT run — preserved for the escalated experiment.

## Rejected claims

- No signature/scope/compiler/label/threshold production change; no
  hybrid evidence; no model switch; no held-out consumption.

## Open contract gaps

- EM1 FAIL. I1 remains BLOCKED. Escalation per the brief: a different
  entity architecture/provider (supervised span-expansion or
  decoder-based) under a new explicit gate, reusing the frozen
  EP1/EM1 protocol and the preserved one-shot held-out set.
