---
change_id: U2-PERSISTENCE-CANARY-V1
date: 2026-09-10
last_reviewed: 2026-09-10
status: evidence (frozen)
architecture_impact: none (one bounded document through the REAL production path; no code changed, no backfill resumed, auto-mint scope untouched)
---

# U-2 persistence canary — the chain is PROVEN; the hold still stands on a named broken transition

Owner-authorized (2026-09-10): ONE bounded persistence-capable pMAP canary, because the 11.192 probe
deliberately persisted nothing and therefore could not close

```
provider response → MappingOutcome → compiler → durable pMAP → projection
```

Instrument: `scripts/u2_persistence_canary.py`. Machine-readable: `before.json`, `canary-result.json`.

## Scope — the smallest possible

| | |
|---|---|
| document | `doc_6a5301e0043db44f…` — *Laban-Bartenieff Movement Studies for Neonatal Movements.md* |
| corpus | `cinema` (the held corpus, one document only) |
| run | `run_6f829effbd730164…` |
| eligible parents | **5** — one batch (cap 15), the smallest unmapped document in the corpus |
| before | 0 maps, 0 projected, **2 stale `partial` batches** (`expected 5`, `valid 0`, `raw_response_hash NULL`, 33 local attempts ⇒ **never dispatched**) |
| auto-mint scope | **UNCHANGED** (`POLYMATH_DOC_PARENT_MAP_CORPUS=rag-canary`). One ticket minted by pinned run id — not a backfill. |
| spend | **1 Groq request** |

This document is the historical failure in miniature: 33 local attempts, zero HTTP, zero maps — the 11.185
`LIMITER_REFUSED` cascade.

## The invariant — RECONCILES

```
requested 5  =  eligible 5      (excluded 0)
      ↓
dispatched   1 HTTP
      ↓
provider     compiler_complete 1 · partial 0 · invalid 0 · empty 0 · http_429 0 · http_failures 0 · limiter_refusals 0
      ↓
compiled     5 accepted · 0 rejected
      ↓
persisted    5 active rows in document_parent_maps (5 new map_ids)
      ↓
projected    5 points in polymath_document_parent_maps_embed_e794ec4cab197a3f
      ↓
outcome      parents_mapped 5 · unresolved 0 · attempts 1 · retry waste 0
```

| check | result |
|---|---|
| requested == eligible | **PASS** |
| returned == persisted | **PASS** (5 = 5) |
| persisted == projected | **PASS** (5 = 5) |
| dispatch fully accounted | **PASS** (1 dispatch = 1 classified outcome) |
| no unresolved left | **PASS** (0) |
| limiter counters match dispatch | **FAIL** — see D-4 |

**No unexplained parents. No unexplained requests. No silent loss.** The persistence question this canary was
authorized to answer is **ANSWERED AFFIRMATIVELY**: a provider response does reach durable storage and the
projection intact.

## Two defects, and why the hold still stands

**D-3 — `MappingOutcome.complete` is false for a document that is fully mapped. (NEW, material.)**

The worker mapped all 5 parents and projected all 5, then raised:

```
RuntimeError: DOC_PARENT_MAP_INCOMPLETE: unresolved=0 partial=2 refusals=0 http_fail=0
```

`unresolved=0` — every eligible parent is mapped — yet `outcome.complete` is False because
`batches_partial=2` counts the two **stale, never-dispatched** historical batch rows.
`_is_transient_incomplete()` is False (no refusals/429/failures), so it is a hard `RuntimeError`, not a
transient hold, and the ticket **re-armed to `ready`** (`doc_parent_map_stage_worker.py:256-261`,
`doc_parent_map_worker.py:406-408`).

Consequences:
- A successful document reports **failure**. At cinema scale, a resumed backfill would report failures on
  documents it actually completed — a strong candidate explanation for the historical
  "+0 parents / 0 errored_docs" confusion this whole forensic hold began with.
- The re-armed ticket burns attempts. It did **not** re-dispatch here (watched 90 s: batches 3, HTTP 1, maps 5,
  unchanged — the autopilot had re-parked the slot), so blast radius was zero, but the arming is real.

**D-4 — the durable limiter has no counter for any pMAP lane.**
`llm_controller_state` contains rows for `gemini*`, `nvidia2`, `openrouter*` — and **none** for
`map_groq2…6` or `map_fallback_openrouter`, before or after. The dispatch incremented no durable `day_count`.
11.192's "local `day_count` +1 per dispatch" was observed **in-process**; it is not persisted for these lanes.
No request is lost (the batch row + artifact account for it), but the limiter is **not** a usable local RPD
ledger for pMAP.

## Verdict

```
U-2 FORENSIC HOLD: ACTIVE (NOT CLEARED)
```

The owner's arithmetic invariant reconciles end to end. What is **not** clean is the transition the owner
named explicitly in their own chain — `provider response → MappingOutcome → …`: **`MappingOutcome.complete`
is wrong**, so the stage's own verdict contradicts its verified result. Combined with the still-open D-1 from
the closure audit (3 historical batches with real provider consumption booked as `LIMITER_REFUSED`) and D-2
(6 batches frozen on leases expired 2026-09-09 04:54Z), the accounting is not yet complete to the bar the
owner set.

**The exact broken transition:** `MappingOutcome.complete` (and therefore the ticket outcome and the stage
receipt) is computed from **stale batch rows** rather than from **unresolved eligible parents**.

## Path to clearing

1. **Fix D-3**: make completeness a function of `unresolved_parent_ids` (already computed, already correct),
   not of `batches_partial`; or exclude never-dispatched batch rows (`raw_response_hash IS NULL`) from the
   partial tally. Worker code ⇒ stale-bundle fence ⇒ one bounce; the fleet is idle, so the window is cheap.
2. **Fix D-1** forward (classify a dispatched-but-empty completion as `EMPTY_COMPLETION`, never
   `LIMITER_REFUSED`) and **reap D-2's six leases by pinned batch id**.
3. **Persist limiter counters for the pMAP lanes** (D-4), so local RPD is auditable without reading artifacts.
4. Re-run this canary on a second unmapped cinema document; expect all six checks PASS.
5. Only then the bounded cinema resumption sequence.

## Cleanup

Cinema is left clean: the canary's own ticket was closed **by pinned ticket id** (never a status sweep) with
`archived_reason` recording D-3, and `last_error_note` preserved as forensic record. The 5 maps and 5
projections are **kept** — they are real, verified work. No other cinema ticket exists; there are **0**
`ready`/`leased` tickets anywhere. Auto-mint remains scoped to `rag-canary`.
