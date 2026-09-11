---
title: "WORK LOG — U-2 bounded persistence canary: chain PROVEN, hold ACTIVE on a named broken transition"
change_id: U2-PERSISTENCE-CANARY-V1
date: 2026-09-10
owner: governance
last_reviewed: 2026-09-10
status: complete (canary executed); VERDICT = HOLD ACTIVE
register: 11.200
package: "scripts/u2_persistence_canary.py + docs/wiki/experiments/u2-persistence-canary-2026-09-10/"
architecture_impact: "none — one bounded document through the REAL production path. No code changed, no backfill resumed, auto-mint scope untouched."
---

> **Ledger:** owner authorization 2026-09-10 workstream C — ONE bounded persistence-capable pMAP canary,
> because the 11.192 probe persisted nothing. Register **11.200**. Spend: **1 Groq request**.

## Contract

Requested outcome: close `provider response → MappingOutcome → compiler → durable pMAP → projection`.

- **Smallest acceptance:** one document, measured exactly before and after, run through the REAL production
  path, with the invariant `requested → dispatched → provider outcome → compiled → persisted → projected`
  reconciling and no unexplained parents or requests.
- **Owner / public contract:** unchanged. `POLYMATH_DOC_PARENT_MAP_CORPUS` stays `rag-canary`.
- **Inputs/outputs/persistence:** mints ONE ticket for ONE pinned run; the supervised stage worker does the rest.
- **Dependency edges:** gates cinema resumption → S14+ cutover phases.
- **Verifier / rollback:** `scripts/u2_persistence_canary.py` (re-runnable, `--execute` gated); the 5 maps
  produced are real work and are kept.

## Changes

- `scripts/u2_persistence_canary.py` — the instrument (dry-run by default; `--execute` mints exactly one ticket).
- `docs/wiki/experiments/u2-persistence-canary-2026-09-10/` — `README.md`, `before.json`, `canary-result.json`.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — register **11.200**; scaffold + `scripts/README.md`.

## Proof

- **Target:** `doc_6a5301e0043db44f…` (cinema, 5 eligible parents — the smallest unmapped document). Before:
  0 maps, 0 projected, **2 stale `partial` batches** with `valid_count=0` and `raw_response_hash NULL` across
  33 local attempts ⇒ the 11.185 `LIMITER_REFUSED` cascade in miniature.
- **The invariant reconciles:** requested 5 = eligible 5 (excluded 0) → **1** HTTP dispatch →
  `compiler_complete 1`, partial/invalid/empty/429/failures/limiter_refusals all **0** → 5 compiled →
  **5 persisted** (5 new `map_id`s) → **5 projected** (`polymath_document_parent_maps_embed_e794ec4cab197a3f`) →
  `parents_mapped 5`, `unresolved 0`, 1 attempt, 0 retry waste. **No unexplained parents, no unexplained
  requests, no silent loss.**
- **D-3 (NEW, material):** the worker then raised
  `DOC_PARENT_MAP_INCOMPLETE: unresolved=0 partial=2 refusals=0 http_fail=0` and the ticket re-armed to
  `ready`. `outcome.complete` is False because `batches_partial=2` counts the two **stale, never-dispatched**
  batch rows — `unresolved=0` proves every eligible parent IS mapped.
  `_is_transient_incomplete()` is False, so it is a hard `RuntimeError`, not a transient hold
  (`doc_parent_map_stage_worker.py:256-261`; `doc_parent_map_worker.py:406-408`). Watched 90 s: batches 3,
  with-HTTP 1, maps 5 — **no re-dispatch** (the autopilot had re-parked the slot), so blast radius was zero.
- **D-4:** `llm_controller_state` has **no row for any pMAP lane** (`map_groq2…6`,
  `map_fallback_openrouter`) before or after; the dispatch incremented no durable `day_count`. 11.192's
  "+1 per dispatch" was in-process only. No request is lost — the batch row and artifact account for it — but
  the limiter is not a usable local RPD ledger for pMAP.
- **Cleanup:** the canary's own ticket closed **by pinned ticket id** with `archived_reason` recording D-3 and
  `last_error_note` preserved. 0 `ready`/`leased` tickets anywhere. The 5 maps and 5 projections are kept.

## Rejected claims

- **"The chain reconciles, so clear the hold."** REJECTED — the arithmetic reconciles, but the owner named
  `MappingOutcome` explicitly in the chain, and `MappingOutcome.complete` is WRONG: the stage's own verdict
  contradicts its verified result. With D-1 and D-2 still open from the closure audit, the accounting is not
  complete to the bar the owner set. Reported as "the exact broken transition", per instruction.
- **"The chain is broken — maps were lost."** REJECTED — 5 returned, 5 persisted, 5 projected, byte-checked
  against new `map_id`s and a Qdrant count. Nothing was lost.
- **"Resume cinema now; it clearly works."** REJECTED — the owner gated resumption on the hold clearing, and
  D-3 means a resumed backfill would report failure on documents it actually completed.
- **"Fix D-3 while here."** REJECTED for this slice — the owner's instruction on non-reconciliation is to stop
  cinema work and report the exact broken transition. The fix is specified, not applied.
- **"Delete the 2 stale batch rows so the document reports complete."** REJECTED — they are forensic evidence
  of the refusal cascade, and deleting data to make a check pass is the opposite of the fix.

## Open contract gaps

- **D-3 unfixed:** completeness must be a function of `unresolved_parent_ids` (already computed and correct),
  not of `batches_partial` — or never-dispatched rows (`raw_response_hash IS NULL`) must be excluded from the
  partial tally. Worker code ⇒ stale-bundle fence ⇒ one bounce.
- **D-1 and D-2 unfixed** (closure audit 11.196).
- **D-4:** pMAP limiter counters are not persisted.
- The canary proves ONE document. A second unmapped cinema document should pass all six checks after D-3 is
  fixed before resumption is considered.
- `u2_persistence_canary.py` has no automated test; it IS the test, and it is provider-spending, so it stays
  `--execute`-gated.
