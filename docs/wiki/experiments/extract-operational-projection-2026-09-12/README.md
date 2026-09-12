---
change_id: EXTRACT-OPERATIONAL-PROJECTION-V1
date: 2026-09-12
last_reviewed: 2026-09-12
status: evidence (frozen)
architecture_impact: none (read-only measurement + shadow-parity evidence backing the §20A hot-path migration)
---

# Control Plane / Files hot-path fix: EXPLAIN before/after + shadow parity

Backs `EXTRACT-OPERATIONAL-PROJECTION-V1` (register 11.214), the mandatory §20A
hot-path migration from the execution authority
(`POLYMATH_EXECUTION_AUTHORITY_XML_FINALIZED.md`). Full machine-readable numbers:
`before-after.json`.

## Root cause (confirmed, not assumed)

`EXPLAIN (ANALYZE, BUFFERS)` on `control_plane_status.py::_graph_provider`'s exact SQL
(cinema, the largest corpus) showed a `Seq Scan on artifacts` filtering
`jsonb_exists(payload, 'llm_extraction') AND stage='extract'` touching **45,346 buffer
reads (~354 MB)** for a query that logically needs six small integers summed over 67
rows. `document_status.py::corpus_document_summaries`'s extract-join showed the
identical pattern (46,857 reads, ~362 MB). `artifacts.payload` is TOAST-heavy by
construction (108 extract-stage rows average 116 KB, max 789 KB; 455 of the table's
456 MB is TOAST for only 1,107 logical rows) — `jsonb_exists()` and `->` both force a
full detoast of the value being tested, and Postgres evaluates that filter across
effectively the whole table on every poll, not just the matching rows. This is the
exact defect the execution authority named, now measured rather than assumed.

## Fix

- Migration `stores/postgres/migrations/0057_extract_operational_projection.sql`:
  seven additive, nullable columns on `artifacts` (`extract_stats_present`,
  `extract_llm_calls`, `extract_entity_count`, `extract_relation_count`,
  `extract_neighborhoods_sent`, `extract_neighborhoods_unaccounted`,
  `extract_neighborhoods_dropped`).
- `shared/polymath_shared/extract_projection.py`: the ONE derivation
  (`derive_extract_projection`) both known writers of `stage='extract'` artifacts call
  — `receipts.py::_StageWrite.artifact` and `control/reconciliation.py`'s
  carry-forward INSERT — so a provider/model/contract change cannot silently create
  projection drift between them.
- Backfilled all 108 existing rows (`scripts/backfill_extract_projection.py`, bounded/
  resumable/idempotent).
- Cut over both named hot readers to the new columns; `artifacts.payload` itself is
  untouched — still authoritative for forensic/replay/detail reads
  (`document_status()`, the single-document detail view, intentionally still reads it).

## Result

See `before-after.json` for the full numbers. Headline:

| Query | Before | After | Speedup |
|---|---|---|---|
| `_graph_provider` (cinema) | 605 ms, ~354 MB touched | 4.1 ms, ~1.4 MB touched | ~147x |
| `corpus_document_summaries` extract-join (cinema) | 489 ms, ~362 MB touched | 5.7 ms, ~4.6 MB touched | ~85x |

Both plans now show zero payload/TOAST access — `Filter: (extract_stats_present AND
stage = 'extract')`, a plain boolean column check.

**Shadow parity: 100% of 108 eligible rows, 0 mismatches**, across all four corpora
that have extract-stage artifacts (cinema, ecom-meta-v1, rag-canary, d7-h1-test) —
verified by `scripts/verify_extract_projection_parity.py`, which compares the OLD
JSONB derivation against the NEW columns row-by-row.

**Controls (must not regress):** `pipeline_health`/`control_ready` (12.2 ms / 1.9 ms),
`_pmap_provider` (13.7 ms), `_queue_by_pool` (14.5 ms) — all consistent with the prior
CONTROL-PLANE-HONESTY-V1 session's numbers (register 11.211); pMAP's own operational
read was not touched, per the authority's own non-goal ("pMAP... already fast unless
current measurements prove otherwise" — they did not).

## Found, but explicitly out of scope for this gate

Profiling `corpus_document_summaries()` end-to-end on cinema (155 ms total, vs. 10.6 ms
on rag-canary) surfaced that its OTHER counters — chunks-by-tier, map-eligible-parents,
both querying `chunks` directly, no JSONB/TOAST involved at all — cost ~150 ms on
cinema specifically. `EXPLAIN` shows this is the query planner CORRECTLY choosing a
sequential scan over `chunks` (96,391 rows / 215 MB) because cinema's 67 documents own
84,152 of those rows (87% of the whole table) — at that selectivity a Seq Scan beats
the existing `chunks_doc_idx (doc_id, chunk_index)`. This is a genuinely different
problem (proportional to raw chunk volume, not a TOAST-avoidable inefficiency) that
would need its own maintained summary/cache to fix — a separate migration decision,
not a corollary of this one. Documented for a future slice; not part of this gate,
which the authority scopes explicitly to `artifacts.payload`.

## outbox_events scoping (§20A phase H) — checked, no fix needed

No unscoped-then-filtered anti-pattern was found. `corpus_document_summaries`'s
extract-join already scopes `outbox_events` by a `doc_id` IN-list at join time, and the
table itself is small (2,486 rows / 12 MB) — `EXPLAIN` shows sub-2ms cost via the
existing `outbox_events_run_type_idx (run_id, event_type)` even before this migration.
Per phase H's own instruction ("add the narrowest justified index only if the plan
needs it"), no index was added, because the plan does not need one.
