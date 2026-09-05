---
title: "WORK LOG — ENRICH-DOC-PARTITION-V1 + ENRICH-LADDER-FANOUT-V1: enrichment ran one worker wide with a one-at-a-time repair ladder while nine lanes idled"
change_id: ENRICH-DOC-PARTITION-V1
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.80
package: workers/workers/summary_worker_impl.py
architecture_impact: "Summary worker only. parent_enrichment no longer takes the corpus-wide sweep lock; each document is claimed with a transaction-scoped advisory try-lock so two workers sweep disjoint documents of one corpus concurrently (the summary_jobs keys they upsert are therefore disjoint — the 11.75 deadlock cannot recur). The semantic-failover and hard-case escape ladders fan their calls out on the same lane-cap-sized pool the microbatch pass already uses. No schema, contract, pin or API change."
---

# WORK LOG — ENRICH-DOC-PARTITION-V1 + ENRICH-LADDER-FANOUT-V1

Owner (2026-09-05 14:00Z): "what is the concurrency setting for enrichment, it's too slow."

## Contract

- **Setting (unchanged):** `POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY=9` microbatches in flight per worker for the first pass; the per-call pool is the sum of the involved lanes' `conc_cap` (3–4 each across the nine-lane pin) capped at 12; two `summaries` slots under the supervisor.
- **Law 1 — partition, don't serialize.** `_do_enrichment` claims each document with `_doc_sweep_lock(conn, stage, corpus, doc)` (`pg_try_advisory_xact_lock` on `summary-sweep|parent_enrichment|<corpus>|doc:<doc>`); a held document is skipped, never waited on. The other four sweeping handlers keep the corpus-level `_sweep_lock`.
- **Law 2 — the ladder is as wide as the lanes.** `_complete_fb` (semantic failover, ring+1) and `_complete_escape` (minimal escape, ring+2) run through `_fan_out(items, one, _pool_width(items, ring))`, order-preserving; each lane still self-gates through its own AIMD limiter.
- Identity, gating, persistence and the failure taxonomy are untouched.

## Why (measured, 12:00–14:00Z, corpus `cinema`)

- 311 enrichment calls across 9 lanes in 2 h = one call per lane every ~3.5 min against ~31 concurrent slots: lanes ~95 % idle. Throughput 1,063 READY + 383 INVALID = 12 parents/min; 3,479 parents left = ~5 h at that rate.
- `summaries2` logged 315 `SUMMARY_SWEEP_BUSY` yields: the second worker never enriched cinema. Root cause: SUMMARY-SWEEP-SERIALIZATION-V1 (11.75) locked the whole corpus to stop a deadlock whose real condition was two workers upserting the same `summary_jobs` keys — a per-document partition gives disjoint keys with no serialization.
- The sweeping worker's timeline shows 50–94 s gaps between waves: the microbatch pass runs 9-wide, then every INVALID parent (25–50 % per lane) walks a strictly sequential ladder (`for item in items: complete_one`).
- Lane quality in the same window (READY / INVALID by preceding lane): gemini6b 123/8, gemini5b 75/5, gemini5 74/16, gemini6 82/26, openrouter3 87/42, openrouter5 55/26, openrouter1 78/77, nvidia 66/70 at 102 s mean wall, openrouter2 35/51.

## Changes

- `workers/workers/summary_worker_impl.py`: `_doc_sweep_lock`, `_fan_out`; `_do_enrichment` drops the corpus lock and claims per document (`skipped_docs` counted); `_pool_width(items, ring)` factored out of `_complete`; `_complete_fb` / `_complete_escape` fan out.
- `tests/determinism/test_summary_sweep_serialization.py`: `test_enrichment_partitions_the_corpus_by_document` (real Postgres, two sessions), `test_ladder_fan_out_is_concurrent_and_ordered` (6 × 0.3 s calls < 1 s, order kept), `test_enrichment_ladders_fan_out_in_source`; the structural law now requires the per-document lock for `_do_enrichment` (regex, substring-safe).

## Proof

- Sweep-serialization file: 6 passed on the dev Postgres. Enrichment test set (microbatch, concurrency setting, transient hold): green.
- Live: the edit fenced the fleet at 14:04Z (expected, one restart round); both summaries workers respawned on this code. Throughput receipts are recorded in the register row from the 20-minute watcher (READY per 5 min, sweep-busy count, lease owners).

## Rejected claims

- "Raise `ENRICHMENT_BATCH_CONCURRENCY`." Rejected: the first pass was not the wall; the sequential ladder and the idle second worker were. Raising it would only widen the wave before the same serial tail.
- "Drop the sweep lock entirely." Rejected: the corpus lock still protects the four stages whose keys are not document-scoped; only enrichment is partitioned.
- "Retire nvidia (nemotron) from the pin now." Not done here — it is the owner's dedicated lane; the numbers above (102 s mean wall, 51 % INVALID) are the case for removing it, and with the ladder fanned out its slowness no longer gates the other eight lanes.

## Open contract gaps

- Per-document locks live until the holder's transaction ends (the whole ticket); a worker that finished document X still holds it, so a peer skips it — harmless because X is done, but a long-running ticket holds up to the corpus's document count of advisory locks.
- Lane quality gating (`ENRICH_GISTS_BELOW_FLOOR` 221, `ENRICH_UNKNOWN_REF` 152, `ENRICH_NO_RESPONSE` 150 in 2 h) is a model-quality signal per lane; a per-lane INVALID-rate receipt in `/fleet` would make the pin decision measurable without log archaeology.

## Addendum (14:20Z) — ENRICH-OUTCOME-DURABILITY-V1, ladder receipts, nvidia retired from the pin

The first slice (per-document partition + ladder fan-out) was live at 14:09Z; the 14:14Z watcher sample still showed 8 READY per 5 min. Thread dumps of both workers (six SIGUSR1 samples each) put the main thread in `_complete_fb → _fan_out` every time, and the DB showed the real defect:

- **Outcomes never landed.** `parent_enrichments` for cinema held 8,370 READY rows and **zero** INVALID rows; `summary_jobs` held 8,370 COMPLETE and zero FAILED — while the logs gated hundreds of parents INVALID and 8 terminal `ENRICH_HARD_CASE`. INVALID/terminal rows were written on the ticket's OUTER transaction, and a corpus-sweep ticket almost never commits (yielded, bounced, fenced or killed first). So every sweep re-ran the same failing parents through the three-call ladder, and "terminal" was never terminal. Fix: every compiled parent's outcome is persisted in its own committed `_ptx()` transaction (the READY path already was).
- **Ladder calls were invisible.** Only the primary microbatch call logged `ENRICH_CALL`; the failover and escape calls logged nothing, so a "nothing in flight 50 %" reading from the logs was false. Both now log `ENRICH_CALL_LADDER` with lane, wall and error.
- **nvidia set the tail of every wave.** Per-call wall 82–114 s (others 6–45 s) and 51 % INVALID; with parent-sharding it appeared in nearly every document's primary wave and again as a ring+1/ring+2 lane in the ladder waves. Retired from `stage_pins.parent_enrichment` in `config/cloud_providers.json` (provider block kept; re-adding the name restores it; enrichment identity excludes the lane so nothing re-enriches). Pin is now the 8 gemini/openrouter lanes. `stage_pin()` re-reads the file per call, so it applied without a restart; both workers were restarted anyway (14:22Z, pids 3479/3493) to load the durability change.
- Gate observation for the owner (not changed): `gist_coverage_floor = 0.8` means one missing gist rejects any parent with ≤ 4 children. READY rate by parent size on cinema: 1 child 50 %, 2 → 60 %, 3 → 68 %, 4 → 77 %, 5+ → 78–79 %. 1,214 of the 3,444 remaining parents have ≤ 2 children.

Tests: `test_enrichment_outcomes_persist_in_their_own_transactions` (no compiled parent persisted on the outer connection; ladder receipts present). Sweep file + microbatch + concurrency-setting tests: 25 passed.
