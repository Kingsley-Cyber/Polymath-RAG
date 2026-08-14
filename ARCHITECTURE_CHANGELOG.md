# Architecture changelog

Dated diffs of every architectural change. Each entry links to the ADR
that motivated it and the refactor that implemented it.

## 2026-08-13: initial scaffold

- Skeleton created by `scripts/scaffold_polymath_v4.py` (sha: f82bf2fc9fb1).
- Accepted Postgres as workflow authority.
- Accepted one host-native GLiNER runtime serving two logical passes.
- Added machine-readable dependency ownership and repository work logs.

## 2026-08-13: Phase B production foundation (ADR-0006)

- Workflow schema lands: documents, chunks, entities, evidence, facts,
  artifacts, receipts, outbox, control leases and heartbeats (migration
  0002).
- Transactional receipt boundary implemented in `polymath_shared.receipts`.
- Deterministic rule pack + predicate compiler (YAML data, compiled DAG,
  §15 compile-time checks).
- No-LLM ingestion layer: sentence-aligned parent/child chunking and
  extractive summaries.
- Orchestrator `/intake` commits one run + one outbox event per canonical
  input; control plane runs as a separate process with a Postgres lease.
- GLiNER runtime manifest pinned to urchade/gliner_medium-v2.1 @
  40ec419; `/ready` performs a real forward pass.
- Packaging: uv workspace; deployment: launchd units + Makefile.
