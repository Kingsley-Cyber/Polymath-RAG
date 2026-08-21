# INGEST RUNBOOK — Polymath V5

## Starting the stack

One command from cold: `scripts/boot_polymath.sh` (installed as LaunchAgent
`com.polymath.v5`). Stores via docker; sidecars, orchestrator, control and
workers under the single supervisor. Verify:
`/tmp/polymath_fleet/supervisor_state.json` shows 14/14 alive, ports
8740/8742/8743/8744 answer /manifest (reranker: /ready), 7200 /health.

## Bulk corpus ingestion

1. Write a manifest (see `eval/i4/manifest.yaml`): corpus_id + document
   sources (md/epub/pdf/docx; absolute paths fine).
2. Submit: `execute_manifest(conn, load_manifest(p), p)` — idempotent;
   already-ingested content (GLOBAL dedup by content hash) is skipped, so a
   document can live in ONE corpus at a time.
3. Progress: `runs` by status; `stage_tickets` by (stage,status); extract
   perf artifact per run (`artifacts.payload->'perf'`).
4. Convergence: every run `query_ready`.

## Expected throughput (measured, single M-series MPS host)

- Extraction is provider-bound; batched pass-1 transport (32 texts/request,
  `POLYMATH_GLINER_BATCH`) plus grouped /rescue batching.
- Book-scale reference numbers live in docs/PERFORMANCE_REPORT.md.
- Concurrent extract + embed contend for MPS: expect either to slow while
  the other runs heavy batches.

## Failure interpretation

| signal | meaning | action |
|---|---|---|
| ticket ready→leased loops | stage outlives its lease AND worker predates lease-keeper | restart that worker slot |
| ticket failed att=3 | bounded retry exhausted on a deterministic failure | fix cause; per-ticket re-drive SQL (docs/RUNBOOK.md) |
| 'timed out' on project_qdrant | store/embedder call outliving client timeout | check MPS contention; batching already in place |
| worker slot quarantined | crash loop | read slot log; fix; clear state file; restart supervisor |
| run reconciling, no open tickets | control tick advancing; wait one tick | — |

## After semantics-affecting deploys

Restart the fleet (the semantic-bundle fence only blocks SEMANTIC drift;
plumbing changes require a restart to take effect — the supervisor makes a
rolling restart one `kill <pid>` per slot).
