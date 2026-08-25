---
change_id: BULK-RECEIPT-COMPLETENESS-V1
owner: control
date: 2026-08-25
status: implemented
architecture_impact: advancement-phase receipt evaluation is now corpus-scoped set-based; verdict-store semantics unchanged
---

# BULK-RECEIPT-COMPLETENESS-V1 (2026-08-25)

## Contract

Advancement may consult receipt state only through the explicit-state
verdict store (PRESENT/MISSING, asymmetric TTL); MISSING delays, never
creates, advancement. This slice changes HOW truth is derived: ONE
corpus-scoped anti-join per projection per tick, not one query per run.

## Changes

1. MEASURED LIVE REPRODUCTION of the historical 53.8-minute cold seed:
   after the arity fix, the first real tick ground >100 minutes inside
   ONE transaction — control process CPU ≈0, Postgres DataFileRead-bound,
   statement after statement the same chunks×documents×runs NOT-EXISTS
   per-run anti-join. Driver: `_runs_with_missing_receipts` looping
   4,316 pending runs × 2 projections per tick. Amplifier found on the
   same window: `documents` held **390,000 dead tuples vs 10,201 live**
   with `last_analyze=NULL` (never analyzed), projection_receipts 42k
   dead — every per-run plan was a bloated seq scan.
2. Fix: `_corpora_with_missing_chunk_receipts(conn, projection)` — ONE
   DISTINCT-corpus anti-join over chunks→documents→projection_receipts.
   Receipt truth IS corpus-scoped (chunks join runs via corpus_id), so
   this answers all pending runs at once. Verdict store seeded per run
   from that corpus-level truth; semantics unchanged.
3. `generation_barrier` switched to the same bulk helper (its per-run
   loop had the identical cost class).
4. Tests updated to the new surface (shape pin + bulk seeding map);
   cached-MISSING-blocks-with-zero-queries invariant kept verbatim.

## Proof

- Live DB, timing on: qdrant bulk anti-join **155.8 ms**, neo4j
  **78.1 ms** — all corpora, vs >100 minutes for the per-run loop
  (>40,000x on the measured window).
- pytest: receipt_verdict_store 5/5 (incl. new bulk-seeding test),
  lock_contention_v2 7/7, incremental_census 4/4,
  event_adapter_dict_cursor 10/10.
- Post-deploy: cold-seed tick wall time recorded from TICK-PHASE-TIMING
  telemetry into eval/v5/scale/ attribution artifacts.

## Rejected claims

- NOT claiming census-side `_missing_projection_receipts` (per-run,
  complete-runs only) is fixed here — it is a different, bounded path;
  its share comes out of the phase telemetry next.
- Dead-tuple bloat cleanup beyond ANALYZE (VACUUM FULL / autovacuum
  tuning) deliberately deferred; stats refresh alone was applied.

## Open contract gaps

- No pg_stat_statements in this Postgres; SQL-time attribution relies on
  the offline measuring-cursor driver instead.
