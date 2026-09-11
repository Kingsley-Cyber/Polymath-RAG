---
title: "WORK LOG — U-2 forensic closure audit: hold NOT cleared (2 bounded defects found in durable state)"
change_id: U2-FORENSIC-CLOSURE-AUDIT-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (audit); VERDICT = HOLD NOT CLEARED
register: 11.196
package: "docs/wiki/experiments/u2-forensic-closure-audit-2026-09-10/"
architecture_impact: "none — read-only audit of durable state. No provider call, no cinema touch, no historical row rewritten."
---

> **Ledger:** owner directive 2026-09-10 — clear the U-2 hold ONLY if the durable evidence closes ALL seven
> accounting questions; "do not clear merely because ~247/250 looks plausible". Register **11.196**.

## Contract

Requested outcome: decide whether the U-2 forensic hold can be cleared, against the owner's seven criteria.

- **Smallest acceptance:** each criterion answered from DURABLE state with a number, and any criterion that does
  not close named explicitly with its magnitude — hold remains if any is unresolved.
- **Owner / public contract:** none changed. The hold's state is the deliverable.
- **Inputs/outputs/persistence:** reads `document_parent_map_batches`, `document_parent_maps`, `artifacts`;
  writes one evidence folder. Zero provider requests.
- **Dependency edges:** gates the bounded cinema canary → cinema resumption → S14+ cutover phases.
- **Verifier / rollback:** `closure-audit.json` is re-derivable by re-running the queries; nothing to roll back.

## Changes

- `docs/wiki/experiments/u2-forensic-closure-audit-2026-09-10/` — `README.md` (criteria table + verdict) and
  `closure-audit.json` (machine-readable).
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.196**; scaffold TREE declarations.

## Proof

- **C6 maps returned vs persisted — CLOSED HERE, parent-level: 2,312 returned → 2,312 with a persisted active
  row, 0 batches short.** The probe could not close this (it wrote nothing to the DB by design). The naive
  batch-level delta of 735 is batch RE-IDENTITY: `grounding_hash` rebinds `batch_id` on re-run while persistence
  dedupes on `(doc_id,parent_id,map_contract)` — proven by active rows 1,577 == distinct triples 1,577.
- **C5 real-parent yield: 1.000** across all 134 `done` batches (2,212 expected → 2,212 returned, mean
  16.5/batch). The 937 `partial` batches' 0.005 is the LOCAL refusal cascade (14,617 attempts, 0 HTTP).
- **C1 + C7 FAIL, bounded:** of 926 terminally-`LIMITER_REFUSED` batches, **3** carry a `raw_response_hash` with
  `valid_count=0` — real provider consumption booked as a local refusal. One hash is
  `e3b0c44298fc1c14…` = SHA-256 of the empty string (an empty completion body). All three are
  `expected_count=60` on REAL parents, 2026-09-08.
- **D-2: 6 batches frozen on leases that expired 2026-09-09 04:54Z** (`doc-parent-map-worker-v1`), holding 90
  parents; 5 × HTTP_429, 1 × LIMITER_REFUSED. Never returned to a claimable state.
- Terminal-state coverage otherwise complete: LIMITER_REFUSED 926 · HTTP_429 11 · HTTP_413 3 · no-error 137.
- Guards: `agent_preflight` ok · `repo_guard` ok · `wiki_worm --check` ok.

## Rejected claims

- **"U-2's evidence closes the gate; clear the hold."** REJECTED — the probe's own checklist is not the owner's
  checklist. The probe wrote nothing to the DB, so it could not have answered "maps returned vs maps persisted"
  at all; that question was closed in THIS audit, from durable state. Two other criteria then failed.
- **"735 maps were lost between provider and storage."** REJECTED — batch re-identity + dedupe, proven above.
- **"The 3 misclassified batches are immaterial, so clear anyway."** REJECTED as MY call to make. The magnitude
  IS small (3 of 1,077 batches; it moves neither the RPD conclusion nor the cinema-finish estimate) — but the
  owner set completeness, not plausibility, as the bar. Waiving it is an owner decision, and the audit gives the
  exact number needed to make it.
- **"Fix the 3 historical rows so the invariant holds."** REJECTED — they are forensic evidence. Fix the
  classifier forward; never rewrite the record.
- **"Run the bounded cinema canary anyway since the premise is disproven."** REJECTED — the owner gated the
  canary on the hold clearing FIRST. Cinema untouched.

## Open contract gaps

- **D-1 not fixed:** terminal-state classification still books a dispatched-but-empty completion as
  `LIMITER_REFUSED`. Fix is worker code (`doc_parent_map_worker.py` error classification) — trips the
  stale-bundle fence, needs a bounce. Not done in this slice (audit only, and it is the owner's call whether to
  fix-then-reaudit or waive).
- **D-2 not reaped:** the 6 expired-lease batches remain frozen. Reaping must be BY PINNED BATCH ID, never a
  status sweep (MEDIC SCOPING LAW) — and it is owed work inside the dormant backlog the owner ordered classified
  before any mutation.
- **C3 weak spot:** `provider_rpd_remaining_before` was never captured (null in every probe row); the per-call
  RPD delta is inferred from call order. A future probe should capture headers on both sides.
- No automated guard asserts the LIMITER_REFUSED ⇒ zero-consumption invariant over durable state. This audit is
  a one-off query set, not a test.
