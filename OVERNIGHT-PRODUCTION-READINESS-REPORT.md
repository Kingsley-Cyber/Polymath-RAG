# OVERNIGHT-PRODUCTION-READINESS-REPORT (2026-08-25)

Unattended window: control/performance recovery → GO + freeze →
retrieval contract audits → three-mode benchmark. Final HEAD:
`0ef35d7`. Fleet: PASS 13/13 fence, one control, detached boot.

## 1–2. Starting state / fleet recovery

Session opened on handoff `9b29e9b` with a stale-code fleet. Recovery
surfaced THREE live defects the previous session's component tests
could not see:

| defect | measured impact | fix |
|---|---|---|
| event_adapter tuple-unpack under dict_row cursor (`4bc430d`) | extract never registered; intake heartbeat frozen; infinite crash-loop | cursor-agnostic row access + typed fail-closed; 10 regression tests |
| advance_tickets arity TypeError since store cutover (`ad81e24`) | **1,864 consecutive failed ticks** — no advancement/promotion/census for hours fleet-wide | call site fixed; entry-point wiring + signature pinned |
| dead extract registration masked live fleet in fence | misleading STALE rows | resolved by real registrations; fence hardening noted as future slice |

Fleet now: pipeline profile, kimi_v1+enforce+spacy, boots MUST be
`disown`ed (one boot was killed by shell recycling; measured).

## 3. Control/performance changes (all committed)

1. CENSUS-PHASE-TIMING-V1: always-on phase telemetry, per-tick phase
   table to `/tmp/polymath_fleet/tick_phases.jsonl` (`ad81e24`,
   `4e7e701`).
2. BULK-RECEIPT-COMPLETENESS-V1 (`1c872f3`): one corpus-scoped anti-
   join per projection replaces per-run loops.
3. SCHEDULER-BULK-V1 (`a56df8e`): bulk gap scheduling; keys byte-
   identical (test-pinned).
4. FOREGROUND-UNDER-BACKLOG (`4b0fe16`, `9331f9a`): two-lane claim
   ordering; scale-10k mass archived superseded.

## 4. Performance GO/NO-GO: **GO — architecture FROZEN**

Report: `eval/v5/scale/CONTROL-PERFORMANCE-FINAL-CLOSEOUT.md`.

Headline measurements:

| metric | before | after |
|---|---|---|
| cold-seed tick | 3226 s (historical) / >100 min (live repro) | **100 s** |
| incremental census | ~24 min cadence | **0.31 s** |
| schedule_gaps phase | 51–55 s/tick | 4.6–7 s |
| receipt completeness | >100 min cold | ~0.23 s |
| new-doc → query_ready under load | hours (unbounded stall) | **≈90 s** |

53.8-min attribution ≥95%: per-run receipt EXISTS loops × documents
table carrying 390k dead tuples with last_analyze=NULL (both measured;
offline instrumented full pass + SQL-bucket ledger committed).

## 5. Retrieval contract work COMPLETED

- RETRIEVAL-CHUNK-HIERARCHY-V1 (`c491d64`): actual chunker behavior
  documented; frozen params pinned by contract hash.
- RETRIEVAL-STORAGE-CONTRACT-V1 (`c491d64`): Postgres/Qdrant/Neo4j/
  lexical audited against LIVE stores. Flagged gaps: G1 mixed embedding
  contracts across corpora (settings default is hash-embed!), G2 missing
  charter payload metadata, G3 concept alias fields, G4 NO BM25 index,
  GRAPH hop2-vs-charter-hop1 unmeasured.
- CORPUS-MAP-QUERY-CONTRACT-V1 / EVIDENCE-BUNDLE-CONTRACT-V1: NOT
  STARTED.

## 6. Three-mode benchmark: PARTIAL (harness done, judging not)

30/30 query×mode cells executed on release-books-v1 @ neural contract
(`0ef35d7`). Behavioral sanity verified (exact procedure hit; paraphrase
hit; typed graph facts like "splunk|uses|field aliasing"). No accuracy
claims — needs sealed judged set. VECTOR ~0.6 s, HYBRID ~0.9–1.9 s,
GRAPH ~0.95 s incl. embed round trip.

## 7. Real-corpus pilot: NOT STARTED (next window)

Blocked sensibly behind G1 decision (which corpora get neural
projections) and G4 (lexical index) if HYBRID precision matters.

## 8. Commits created

4bc430d · ad81e24 · 1c872f3 · 4e7e701 · a56df8e · 45254bf · 9331f9a ·
4a3086a · c491d64 · 0ef35d7 (10 commits, each with work-log entry).

## 9. Tests executed

Focused core repeatedly green (up to 38/38); determinism suite run:
only pre-existing failures remain (3 bundle-pin stale-authority hashes,
2 vocabulary IndexErrors — handoff trap #7). New regressions added:
event_adapter dict-cursor ×10, advance_tickets wiring, scheduler bulk
×3, claim-lane pin, bulk verdict seeding.

## 10. Measured performance changes

See §4 table. Plus: VACUUM ANALYZE applied to documents/
projection_receipts/chunks/runs/stage_tickets (documents was 38× bloat,
never analyzed).

## 11. Known remaining blockers

1. G1 embedding-contract split (owner-relevant: default is hash).
2. G4 no lexical index.
3. advance_tickets DAG walk ~12 s/tick at current pending volume.
4. Autovacuum tuning deferred.
5. Pilot corpus selection.

## 12. Exact next action

Decide G1 (neural cutover default?) then run the Stage-K pilot on a
50–100 doc real corpus through ingest.py; judge three-mode results on
its sealed query set.
