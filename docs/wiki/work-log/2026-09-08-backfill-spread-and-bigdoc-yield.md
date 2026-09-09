---
title: "WORK LOG — Parent-MAP backfill: account-spread + large-doc batch cap, BOTH FIXED"
change_id: BACKFILL-SPREAD-V1
date: 2026-09-08
owner: governance (backfill tooling; migration coverage)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.177, 11.178
package: scripts/parent_map_backfill.py, tests/determinism/test_parent_map_backfill_spread.py, shared/polymath_shared/document_profile/map_batches.py, tests/determinism/test_map_batches.py, scripts/scaffold_polymath_v4.py, docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md
architecture_impact: "RETRIEVAL-MIGRATION-DEPENDENCY-V1 S12 (cinema coverage). Two backfill defects were diagnosed while advancing cinema parent-MAP coverage 551→704. (1) FIXED — the backfill routed map inference through `route()`, whose capacity view is BLIND for these map lanes in a dedicated process (their limiter lanes are unregistered → every account reads a tied full-budget placeholder), so the only spread was a 6 s reservation that expired during real multi-second calls and collapsed to a lexical-first pin (649/657 calls on map_groq1). Replaced with explicit ROUND-ROBIN across the six distinct-account endpoints; each endpoint keeps its own AIMD limiter for per-account backoff. Live-verified even spread; unit-tested. (2) GATED — the residual coverage wall is the map inference YIELD on large documents (≥~430 parents map ≈0 even in isolation, capacity fine), NOT capacity/concurrency/pinning. Root-caused with evidence and handed to a dedicated task. No contract changed; the backfill is still resumable/idempotent."
---

> **Ledger row:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12**. The migration ledger's status table is the control point; this work-log is the evidence.

# WORK LOG — backfill account-spread fix + large-doc yield finding

## Contract

Advance cinema parent-MAP coverage (the cutover gate) via the owner-authorized backfill, and per the
execution law "if a gate fails, fix and retest rather than silently bypass" — diagnose why the
campaign was stuck. Keep the backfill resumable/idempotent/contract-scoped; no paid fallbacks.

## Changes (steps — exact commands + evidence)

- **`scripts/parent_map_backfill.py` `_routed_infer` → BACKFILL-SPREAD-V1:** replaced the
  `route()`-based lane pick (+ `next(iter(eps))` fail-open) with explicit thread-safe ROUND-ROBIN over
  the ordered endpoint list. Rationale in-code: `route()` is blind for unregistered map lanes → tied
  placeholders → lexical-first pin once the 6 s reservation expires under real calls.
- **`tests/determinism/test_parent_map_backfill_spread.py`** (new, declared in scaffold): 60 calls →
  exactly 10 per account (max−min==0); empty pool raises. GREEN.
- **Ledger S12** updated with coverage 704 + both findings.

## Proof

- **Unit:** `test_parent_map_backfill_spread.py` 2/2 GREEN (perfect 6-way spread; empty-pool raise).
- **Live qualification (before → after the fix):** a full cinema run pre-fix = lane_spread
  `{map_groq1: 649, map_groq2: 1, map_groq3: 2, map_groq4: 1, map_groq5: 2, map_groq6: 2}`; post-fix =
  `{map_groq1: 110, 2: 110, 3: 110, 4: 109, 5: 109, 6: 109}`, distinct_accounts_used 6.
- **Coverage advanced 551 → 704 / 11,993** across the session's runs (resumable/idempotent).
- **Capacity is available:** a direct `groq/compound-mini` probe on 3 map endpoints returned "OK" in
  ~0.5 s, 0 errors — the residual wall is not rate-limiting.

## Rejected claims

- **NOT a router regression.** The router's CONCURRENCY-SPREAD-V1 spread is healthy in isolation (60
  sequential/burst → 10 per account; live `route()` clean 6-way, 0 no-capacity). The pin was the
  BACKFILL's use of `route()` on unregistered lanes, not the router.
- **NOT concurrency, NOT capacity.** The large-doc yield reproduces at `--concurrency 1` and in a
  single-doc isolated `run_document_mapping`, with the endpoints answering fine.

## Open contract gaps

- **FIXED — large-document batch OVER-SIZING (map-batches-v2).** Docs ≥~430 parents mapped ≈0
  (Ken Dancyger **2/430**; Hey Whipple 0/469). **Root cause (corrected after capture — it was NOT
  input size):** `map_batches.plan_batches` capped batches by a token-envelope alias COUNT
  (`mapping_only_capacity`=60), but `groq/compound-mini` reliably returns a COMPLETE structured map
  only for SMALL batches — measured: **10-15 aliases 100% (10/10, 15/15 ×3), 20 mostly, ≥25 flakily
  EMPTY/partial** even though the prompt is tiny (~16 KB at 60 aliases). The token envelope was not the
  ceiling — the model's structured-output reliability is. **Fix:** `MAP_RELIABILITY_CAP=15` applied in
  `mapping_only_capacity`; `BATCH_PLANNER_VERSION`→`map-batches-v2` (batch_hash changes → large docs
  re-batch into 15s; maps persist by map_hash; resumable; small docs' single ≤15-batch unchanged).
  **Proof:** `test_map_batches` pins updated (capacity==15; 40→[15,15,10]; 60→4×15; 150→10×15); 24
  planner-dependent tests GREEN. **Qualified live:** the 469-parent Hey Whipple that mapped ~0 under
  the 60-cap mapped **75/469 in one capacity-limited pass** under the 15-cap (~20× better maps/call);
  15-alias batches measured 100% reliable under fresh capacity. **Remaining:** completing all cinema
  large docs is now purely CAPACITY-gated (multi-session — this session's diagnosis spent today's
  budget), resumable via `parent_map_backfill.py --corpus cinema --project --concurrency 6`. Cinema
  coverage → cutover (S13/S14, owner QUERY_READY flip) no longer batch-size-blocked.
