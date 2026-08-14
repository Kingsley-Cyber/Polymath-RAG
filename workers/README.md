# Workers

Queue-driven. Idempotent. Crash-safe. One worker per stage.

## Layout

```
workers/
└── workers/
    ├── intake_worker.py  : parse + chunk
    ├── embed_worker.py   : calls embedder sidecar
    ├── extract_worker.py : calls gliner-runtime twice, then compiler
    └── promote_worker.py : writes to qdrant + neo4j, issues query_ready
```

## Idempotency

Every job is keyed on (run_id, stage, contract_hash). The queue
(Redis in v1) dedupes by key. Re-running a job on the same input is
a no-op, provably, because the content hash is the same.

## Crash safety

Every job's durable write + receipt + status transition is a single
Postgres transaction. If the worker crashes mid-transaction, Postgres
rolls back; the next tick of the control plane sees the run still in
its previous state and re-enqueues.
