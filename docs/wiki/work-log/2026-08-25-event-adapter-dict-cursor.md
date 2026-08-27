---
change_id: EVENT-ADAPTER-DICT-CURSOR-FIX
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: none
---

# EVENT-ADAPTER-DICT-CURSOR FIX (2026-08-25)

## Contract

`normalize_event(conn, event_type, payload, run_id)` returns a canonical
payload or raises `LegacyEventUnrecoverable`. Owner: shared deterministic
policy (`shared/polymath_shared/event_adapter.py`). Recovery consults the
caller-provided cursor only; no new I/O owners.

## Changes

1. Root cause (measured live): `_recover_from_intake_artifact` consumed
   rows with tuple unpacking `(payload,)`, but production claims run a
   dict_row cursor; unpacking the single-key dict `{"payload": …}` binds
   the KEY STRING `"payload"`, then `json.loads("payload")` raised
   JSONDecodeError(char 0), escaped the typed handler, aborted the whole
   claim transaction, and crash-looped extract (registration rolled back
   every iteration → no worker_registrations row) while intake froze its
   heartbeat after first registration. Same class in the intake.v1
   branch (`row[0]` on dict rows).
2. Fix: row access via `_row_value` accepting dict AND tuple rows;
   `json.loads` guarded so unparseable/scalar artifact payloads fail
   CLOSED with the typed exception.
3. New tests: tests/determinism/test_event_adapter_dict_cursor.py —
   recovery pinned under BOTH cursor factories + fail-closed cases +
   canonical-payload passthrough.

## Proof

- Reproduction against live poison head (outbox event 743564,
  scale_dataset run): JSONDecodeError at event_adapter.py:61 pre-fix;
  recovery returns routing_card doc_id post-fix.
- pytest tests/determinism/test_event_adapter_dict_cursor.py 10/10.
- Focused core green:
  test_event_adapter_dict_cursor + test_receipt_verdict_store +
  test_lock_contention_v2 + test_incremental_census +
  test_execution_bundle + test_claim_starvation = 34/34, seconds, no
  hang.
- Live-fleet proof after deploy: extract/intake register with HEAD build
  sha, heartbeats advance across polls, fence verdict PASS.

## Rejected claims

- NOT claiming recovered events all succeed downstream — only that
  normalization can no longer crash the claim transaction.
- NOT changing the fence's newest-row-per-type selection; live fleet
  regains registrations, which resolves the observed FAIL. Fence
  hardening (ignore dead registrations) is a separate admitted slice.
- NOT treating RECEIPT-BUDGET-V1 as validated; it stays reverted
  (0010c9c); no budget code path exists at HEAD.

## Open contract gaps

- worker_registrations retains dead quarantined rows that the fence can
  misread as fleet members when a live worker lacks a fresh row
  (observed during this incident). Candidate hardening slice, not done
  here.
- Restart READY-backfill still emits bare payloads for tickets whose
  producing events were consumed (handoff trap #3); adapter now recovers
  or fails them typed, but backfill payload completeness remains open.
