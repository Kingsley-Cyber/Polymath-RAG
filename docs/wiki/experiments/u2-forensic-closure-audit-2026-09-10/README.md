---
change_id: U2-FORENSIC-CLOSURE-AUDIT-V1
date: 2026-09-10
last_reviewed: 2026-09-10
status: evidence (frozen)
architecture_impact: none (read-only audit of durable state; zero provider calls, cinema untouched)
---

# U-2 forensic closure audit — verdict: **HOLD NOT CLEARED**

Tests the owner's seven acceptance criteria (2026-09-10) against **durable state**, not against the probe's
own summary. Zero provider requests were made: every number below comes from `document_parent_map_batches`,
`document_parent_maps` and `artifacts`. Machine-readable: `closure-audit.json`.

## Criteria

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | limiter admission vs actual HTTP dispatch | **FAILS (bounded)** | 926 batches terminally `LIMITER_REFUSED`; **3 of them carry a `raw_response_hash` with `valid_count=0`** — an HTTP response WAS received and hashed, yet the batch is classified as a LOCAL refusal. The invariant "LIMITER_REFUSED ⇒ zero provider consumption" does not hold for those 3. |
| 2 | per-account request accounting | PASSES | `per-account-rpd.json`: all 6 lanes, `day_count` +1 per dispatch, provider remaining decrements in step. |
| 3 | provider headers / RPD evidence | PASSES (weak spot) | `x-ratelimit-remaining-requests` captured on every success; limit 250 MEASURED. Weak spot: `provider_rpd_remaining_before` is `null` in **every** probe row — only the post-call value was captured, so the per-call delta is inferred from call order, never observed on both sides. |
| 4 | retry accounting | PASSES | Probe `max_attempts=1`. Durable: `attempt_count` per batch (the refusal cascade shows 14,617 local attempts across 925 batches with **0** HTTP — accounted, not hidden). |
| 5 | compiler / MAP yield | PASSES, and better than assumed | **REAL parents, batch 15: yield 1.000** across all 134 `done` batches (2,212 expected → 2,212 returned, mean 16.5/batch). The 0.005 "yield" of the 937 `partial` batches is the LOCAL refusal cascade, not model failure. |
| 6 | **maps returned vs maps persisted** | **PASSES** (closed here, NOT by the probe) | Parent-level: **2,312 maps returned → 2,312 have a persisted active row; 0 batches short.** |
| 7 | no unexplained dropped/unaccounted requests | **FAILS (same 3)** | Every other batch is classified by a recorded terminal error (LIMITER_REFUSED 926 · HTTP_429 11 · HTTP_413 3 · none 137). The 3 batches in row 1 are real provider consumption booked as local refusal. |

## Why the batch-level "735 missing maps" is NOT a loss

A naive batch join says 2,312 returned vs 1,577 persisted rows (Δ 735). That delta is **batch re-identity**, not
lost work: `grounding_hash` binds batch identity (P6/map-prompt-v2), so a re-run rebinds `batch_id`, while
persistence dedupes on `(doc_id, parent_id, map_contract)` — proven: active rows 1,577 == distinct
(doc,parent,contract) 1,577. A parent returned in three attempts persists once. The correct test is parent-level,
and it reconciles exactly (criterion 6).

## The two defects this audit found

**D-1 — dispatched-but-empty batches are booked as LOCAL refusals.** Three batches (2026-09-08, all
`expected_count=60`, real parents) received an HTTP response and produced zero maps, yet their terminal
`last_error` is `LIMITER_REFUSED`. One of the three hashes to `e3b0c44298fc1c14…` — the SHA-256 of the **empty
string**, i.e. an empty completion body. Consequence: the control plane's `limiter_refused` counter (which
11.187 deliberately keeps DISTINCT from real consumption) **overstates local refusals by 3 and understates real
dispatch by 3**. Magnitude is tiny (3 of 1,077 batches; ~3 requests against ~1,500/day capacity) and it does not
move the RPD conclusion or the cinema-finish estimate — but it is precisely the class of misclassification the
forensic hold exists to rule out, so it is reported, not waived. Note all three are `expected_count=60`: batch
60 on REAL parents is exactly where they occurred, which independently corroborates the 11.178 partial-map
concern and the decision to keep `MAP_RELIABILITY_CAP` at 15.

**D-2 — six batches frozen on expired leases.** `status='leased'`, `lease_owner=doc-parent-map-worker-v1`,
`lease_expires_at` **2026-09-09 04:54Z** — expired ~39 h before this audit and never returned to a claimable
state. They hold **90 parents** (5 × HTTP_429, 1 × LIMITER_REFUSED). This is real owed work that no resumption
will pick up until the leases are reaped. It is also a lease-reaping gap in its own right.

## What is NOT in dispute

The hold's original premise — "all six Groq accounts exhausted their RPD" — remains **DISPROVEN** (11.192:
~246–248 of ~250 remaining per account). Real-parent yield at the proven cap of 15 is **1.0**. Nothing in this
audit weakens either finding. What fails is the owner's *completeness* bar for the accounting, on a narrow and
now-quantified basis.

## Recommended path to closure (owner decides)

1. Fix D-1 forward: classify a batch's terminal state by whether HTTP was dispatched, so a dispatched-but-empty
   completion books as `EMPTY_COMPLETION`, never `LIMITER_REFUSED`. (Worker code — trips the stale-bundle fence,
   needs a bounce; fleet is idle so the window is cheap.)
2. Reap D-2's six expired leases back to a claimable state — **by pinned batch id, never a status sweep**
   (MEDIC SCOPING LAW).
3. **Do not** rewrite the three historical rows. They are forensic evidence.
4. Then either re-run this audit (expect 0 violations on new work) or accept D-1 as a known, bounded, documented
   exception and clear the hold explicitly on that basis.

**`U-2 FORENSIC HOLD: NOT CLEARED` as of 2026-09-10.** Cinema stays untouched; no bounded canary was run,
because the owner's instruction gates the canary on the hold clearing first.
