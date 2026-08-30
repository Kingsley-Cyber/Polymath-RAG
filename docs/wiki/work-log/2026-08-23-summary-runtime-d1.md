---
change_id: summary-runtime-d1-storage
owner: worker
date: 2026-08-23
status: complete
architecture_impact: adds-summary-intelligence-storage
last_reviewed: 2026-08-23
---

# SUMMARY RUNTIME D1: storage substrate

## Contract

POLYMATH_STAGE_WORKER_IMPLEMENTATION storage minimum: six tables, each
with corpus_id / artifact_hash / contract_version /
created_by_worker / created_at / source_ids. Ticket state machine
READY→CLAIMED→RUNNING→COMPLETE|FAILED|RETRY_WAIT (+FAILED_PERMANENT
dead letter per D6). Idempotency: summary_artifacts.input_hash UNIQUE.

## Changes

`stores/postgres/migrations/0024_summary_intelligence.sql`: applied to
the live store; all six tables verified via information_schema.

## Proof

- Live application verified; tables present.
- Workers D2-D5 write through these tables; ticket lifecycle D6.

## Open gaps

D2-D6 workers/lifecycle; dedup slices; projections; acceptance tests.
## Rejected claims

(Historical entry — recorded in the entry body above.)

## Open contract gaps

(Historical entry — recorded in the entry body above.)
