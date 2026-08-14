---
owner: store
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# ADR-0002: Postgres for durable state, not Mongo

## Context

v3.3 used Mongo for everything: documents, runs, receipts, config, the
control plane's run ledger. The control plane's atomicity depended on
Mongo's `findOneAndUpdate` semantics. There are no transactions across
collections, which means the receipt + side-effect gap documented in
ISSUES_REPORT.md §1.2 is unfixable in Mongo without standing up a
replica set and using multi-document transactions (which were a 4.0
feature with rough edges).

## Decision

Postgres is the durable state store. Tables: `runs`, `stage_attempts`,
`outbox`, `control_heartbeats`, `users`, `settings`, `artifacts_index`.

Mongo is gone from the compose file.

## Consequences

Easier:
- Multi-statement transactions. A stage's durable write + receipt +
  status transition can be a single `BEGIN; ... COMMIT;`.
- `LISTEN/NOTIFY` for cheap wakeups (the control plane ticks on a
  NOTIFY, not a poll).
- `JSONB` columns keep the schema-less feel of Mongo where it matters
  (run payloads, receipt metadata) while still being indexable.
- Mature backup/restore story. `pg_dump` + PITR.

Harder:
- Every Mongo query has to be rewritten. Most are straightforward
  (`find` → `SELECT`, `update_one` → `UPDATE ... WHERE ... RETURNING`).
- Mongo's `ObjectId` is gone; everything is `BIGSERIAL` or `TEXT` with
  the content-hash identity scheme from ADR-0001.

## Triggered refactors

- `docs/wiki/refactors/0003-mongo-to-postgres-migration.md`
