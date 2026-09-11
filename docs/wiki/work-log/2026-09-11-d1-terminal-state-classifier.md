---
title: "WORK LOG — D-1 terminal-state classifier; D-2 shown to be a non-defect"
change_id: TERMINAL-STATE-V1
date: 2026-09-11
owner: worker
last_reviewed: 2026-09-11
status: complete (D-1 fixed + 18 regression cases; D-2 disproven as a defect)
register: 11.205
package: "workers/workers/doc_parent_map_worker.py + tests/determinism/test_terminal_state_classifier.py"
architecture_impact: "One terminal-state vocabulary for pMAP batch outcomes, classified from real dispatch metadata. No limiter behaviour changed, no schema change, no new table."
---

> **Ledger:** owner directive 2026-09-11 — "fix D-1 before cinema"; keep six distinct outcomes; add regression
> tests proving classification from real dispatch metadata; do not redesign limiter behaviour. Register **11.205**.

## Contract

- **Smallest acceptance:** a request that was actually dispatched but returned empty output is never recorded
  as `LIMITER_REFUSED`; the six outcomes stay distinct; classification derives from dispatch metadata.
- **Owner / public contract:** the durable marker vocabulary on `document_parent_map_batches.last_error`
  changes from `COMPILER_<class>` to the six terminal states. No schema change.
- **Verifier / rollback:** `tests/determinism/test_terminal_state_classifier.py`; `git revert`.

## Changes

- `doc_parent_map_worker.py` — `classify_terminal_state()` (pure) + the six constants
  `LIMITER_REFUSED · HTTP_429 · PROVIDER_ERROR · PROVIDER_EMPTY · COMPILER_REJECTED · SUCCESS`, and
  `DISPATCHED_TERMINAL_STATES` (every state except `LIMITER_REFUSED` — i.e. those that COST a request).
- All **three** recording sites now derive the marker from metadata: the `MapInferError` path uses
  `exc.dispatched` (the boundary's own flag, never the error text); the untyped-fault path records
  `PROVIDER_ERROR`; the 2xx path classifies body-empty vs compiler-rejected vs success.
- `record_batch_result()` gains a **downgrade guard**: writing a `LIMITER_REFUSED` marker onto a row that
  already has a `raw_response_hash` leaves the existing marker intact. That is the exact mechanism that
  produced D-1 — `raw_response_hash` is `COALESCE`d so it never clears, while `last_error` was overwritten
  unconditionally, so a later local refusal relabelled a row that had provably spent a request.
- `tests/determinism/test_doc_parent_map_worker.py` — the one assertion pinning the retired `COMPILER_EMPTY`
  marker updated to `PROVIDER_EMPTY`, with the reason recorded inline.

## Proof

- **18 regression cases** in `test_terminal_state_classifier.py`: an 11-case parametrised table over real
  metadata (not-dispatched → `LIMITER_REFUSED`; dispatched 429 → `HTTP_429`; dispatched fault →
  `PROVIDER_ERROR`; dispatched empty/whitespace/None body → `PROVIDER_EMPTY`; dispatched + all mapped →
  `SUCCESS`; dispatched + nothing compiled → `COMPILER_REJECTED`), the D-1 case stated explicitly, the
  six-states-distinct invariant, the dispatched-set partition, and four tests over the recorder's SQL proving
  the guard is set for a local refusal (including a wrapped legacy message) and NOT set for any dispatched
  state or for success.
- pMAP suites green (`-k "parent_map or pmap or map_batches"`, 0 failures).
- Classifier smoke, printed from the shipped function: `not dispatched → LIMITER_REFUSED`,
  `429 → HTTP_429`, `HTTP_500 → PROVIDER_ERROR`, `empty body → PROVIDER_EMPTY`,
  `all mapped → SUCCESS`, `nothing compiled → COMPILER_REJECTED`.

## D-2 — investigated, and it is NOT a defect

The 6 "frozen" batches (90 parents) were measured against `claim_batch`'s own predicate:

```
WHERE status IN ('pending','partial','leased')
  AND (lease_expires_at IS NULL OR lease_expires_at < now())
```

**All 6 evaluate `claimable = True`.** An expired lease is already reclaimable — that is the documented
dead-worker recovery path. They sat untouched because **no `doc_parent_map` ticket existed for their runs**
(cinema auto-mint is scoped to `rag-canary`), so nothing ever attempted a claim. The 90 parents become
schedulable the moment the backfill mints tickets for those six documents, through the normal path.

**No lease surgery was performed** — it would have been unnecessary mutation of forensic state to fix a
problem that does not exist.

## Rejected claims

- **"Parse the error text to decide whether a request was dispatched."** REJECTED — that is how D-1 happened.
  `exc.dispatched` is the boundary's own metadata.
- **"Clear `raw_response_hash` when a later attempt is refused."** REJECTED — the hash is the only durable
  proof a request was spent; erasing it would destroy the evidence rather than fix the label.
- **"UPDATE the 3 historical rows to their correct terminal state."** REJECTED — forensic evidence. The fix is
  forward-only; the audit (11.196) records what they are.
- **"Reap the 6 leases."** REJECTED after measurement — they are already claimable (above).

## Open contract gaps

- The 3 historical misbooked rows keep their `LIMITER_REFUSED` marker by design. Any census over historical
  data must read them with 11.196 in hand.
- `classify_terminal_state` is not yet used by the summary or doc_profile workers; they keep their own markers.
