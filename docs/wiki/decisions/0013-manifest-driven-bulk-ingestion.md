---
owner: governance
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: accepted
---

# ADR 0013: Manifest-driven bulk ingestion (gate I1)

## Context

Manual per-file intake calls do not scale to real corpora. I1 must
ingest a collection of documents safely, resumably, idempotently, and
observably — WITHOUT a second ingestion implementation. The existing
single-document path (intake event → control plane → workers →
query_ready) remains the only execution path.

## Decision

A versioned, closed-schema manifest (YAML, `contracts/ingestion/v1/
manifest.schema.json`) DECLARES what should be ingested for one
corpus:

- paths resolve relative to the manifest file (never process cwd);
- unknown fields and duplicate sources are deterministic validation
  failures (documented policy: loud, never silent dedupe);
- manifest identity is the content hash of its canonical semantic
  form (documents sorted by locator → order-stable). Manifest identity
  ≠ document content identity ≠ run identity;
- media types are inferred from extensions, using ONLY the I0
  materializer formats (no new parsers in I1);
- a manifest is an ingestion DECLARATION, not desired-state
  reconciliation: documents absent from a later manifest are NEVER
  deleted (deletion is deferred until explicitly designed).

Planning (read-only) and execution live in `control/control/
manifest_ingest.py`:

- plan derives per-source actions (INGEST / NOOP / RETRY /
  SKIP_DISABLED / ERROR_MISSING / ERROR_INVALID) from authoritative
  Postgres state — document rows by content identity, runs by
  content-derived run id, run status, and source locator lineage
  (same locator + different content identity = changed content);
- execute submits intake work through the ONE shared intake writer
  (`shared/polymath_shared/intake_submission.py`, the same function
  POST /intake uses) with a configurable batch bound. RETRY re-arms a
  terminal failed run's outbox events (delivered_at NULL) and
  re-enters it into the census candidate set — stage history and
  receipts are never deleted, and idempotency keys make redelivery
  safe;
- status reports reconciliation from authoritative run state, never
  subprocess exit codes;
- the CLI (`scripts/ingest.py`, `make ingest-plan/run/status`) never
  invokes workers and never bypasses outbox, leases, receipts, census,
  or verification.

## Consequences

- Orchestrator POST /intake now delegates to the shared writer
  (behavior identical; single-document regression suite stays green).
- Frozen I1 fixture (`tests/fixtures/i1/`) covers md/txt/pdf, disabled,
  missing, duplicate, unknown-field, and changed-content cases.
- Deletion/tombstoning is explicitly DEFERRED (documented
  non-semantics), as are directory watching, crawling, remote
  sources, and ingestion UI.
