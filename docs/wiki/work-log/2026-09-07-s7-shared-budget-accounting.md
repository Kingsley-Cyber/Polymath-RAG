---
title: "WORK LOG — S7a Groq shared-budget accounting (limiter capacity snapshot + account aggregation)"
change_id: DOCUMENT-SEMANTIC-INDEX-V1-S7A-ACCOUNTING
date: 2026-09-07
owner: shared (limiter read-only accessor + pure aggregation)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.148
package: shared/polymath_shared/llm_extraction/limiter.py, shared/polymath_shared/document_profile/groq_accounts.py, tests/determinism/test_groq_accounts.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Builds the SHARED-BUDGET ACCOUNTING that groq_router.choose consumes (GROQ-ROUTING-POLICY-V1 §2 / slice S7) — the owner-named gate before scaled parent-MAP generation. AdaptiveLimiter gains a READ-ONLY capacity_snapshot() (remaining_rpd/rolling_rpm/tpm_used/in_flight/locked_until/breaker_open); groq_accounts.account_states aggregates an account's TWO model lanes (compound + compound-mini) into ONE shared AccountState (the correction: both models draw down the one key's quota). Additive + read-only: the limiter stays the enforcement authority; no selection behavior changes here (the wiring is S7b, flag-gated). No scheduler added."
---

# WORK LOG — S7a Groq shared-budget accounting

## Contract

Owner /goal (2026-09-07) step 2: "Implement the account-shared Compound + Compound-Mini
budget/account state required by the existing `groq_router.choose`. Reuse the existing
extraction limiter/controller as enforcement authority. Do not create another scheduler."
The router (11.134) is pure and takes injected `AccountState`; nothing yet produces it
from live limiter state. This slice is that producer — the "shared-budget accounting"
the owner named as a gate before parent-MAP backfill.

Owner: `shared`. Public contract: `AdaptiveLimiter.capacity_snapshot()` (read-only);
`groq_accounts.account_states(lane_snapshots, account_of, account_rpd)` +
`snapshot_from_registry(...)`. Rollback: delete the accessor + module (nothing reads
them yet). Verifier: `tests/determinism/test_groq_accounts.py`.

OUT of scope (S7b, next): replacing the run-hash lane rotation with router selection
(flag-gated), the config compound-mini lanes, and the live routing canary.

## Changes

- **`limiter.py`**: `AdaptiveLimiter.capacity_snapshot(now=)` — a read-only view
  (remaining_rpd from spec.rpd − today's day_count, rolling_rpm/tpm_used from the token
  buckets, in_flight from the semaphore, locked_until = `_not_before`, breaker_open).
  Monotonic clock, matching `_not_before`. No state mutation; the limiter stays the
  enforcement authority.
- **`groq_accounts.py`** (new, pure): `account_states` groups lanes by account and
  aggregates — RPD = account budget − SUM(lane day usage) (SHARED, not per-lane),
  RPM/TPM/in-flight sum, locked_until = max, breaker = any. `snapshot_from_registry`
  reads live `capacity_snapshot()`s from the limiter registry and aggregates.
- **test + scaffold**: 6 pins; two TREE lines; this work-log.

## Proof

```
.venv/bin/python -m pytest tests/determinism/test_groq_accounts.py tests/determinism/test_groq_router.py -q  -> 18 passed
.venv/bin/python scripts/repo_guard.py / wiki_worm.py --check / agent_preflight.py -> ok
```

Pins: two model lanes of one account (day 100 + 50, shared quota 250) → one AccountState
with `remaining_rpd == 100` (SHARED); breaker/lock aggregate; a live `AdaptiveLimiter`'s
`capacity_snapshot()` reports the required fields; and the assembled states drive
`groq_router.choose` to the least-loaded account (K1 at 200/250 used → picks fresh K2).

## Rejected claims

- **Not** a scheduler: `capacity_snapshot` reads; the limiter enforces; the router selects.
- **Not** a selection change: nothing yet consumes `account_states` for routing — the
  flag-gated wiring is S7b. Additive + read-only, so the live path is unchanged.

## Open contract gaps

- S7b wires `choose` into the Groq compound/mini lane selection behind a reversible flag,
  adds the config compound-mini lanes, and runs a controlled live routing canary.
- The live registry lookup by lane NAME (`snapshot_from_registry`) is duck-typed; S7b
  binds it to the real `LimiterRegistry` (lanes keyed by (provider, api_key)).
