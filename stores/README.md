# Stores

Durable state. Every store is bind-mounted, never in-app.

- `postgres/`: runs, stage_attempts, outbox, control_heartbeats,
  users, settings, artifacts_index. Migrations in `migrations/`.
- `qdrant/`: vectors. Per-corpus collections.
- `neo4j/`: graph. Constraints in `constraints/`.
- `redis/`: queue + cache. Ephemeral. Allowed to die.

## Migrations

`stores/postgres/migrations/` is append-only. New file = new
migration. Never edit a migration that has been applied. The
up/down split is mandatory.

## Migrations (initial)

The first migration creates the load-bearing tables. Subsequent
migrations add columns, add tables, add indexes.
