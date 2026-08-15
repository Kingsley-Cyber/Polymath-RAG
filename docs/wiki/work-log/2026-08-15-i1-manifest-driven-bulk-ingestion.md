---
change_id: i1-manifest-driven-bulk-ingestion
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: docs/wiki/decisions/0013-manifest-driven-bulk-ingestion.md
---

# I1: manifest-driven bulk ingestion

## Contract

Build a deterministic manifest-driven bulk ingestion interface:
manifest → validation → plan → intake submissions → the EXISTING
event/control-plane pipeline. No second ingestion implementation; no
direct worker invocation; no bypass of outbox, leases, receipts,
census, or verification. Idempotent, resumable, observable; corpus
isolation via the declared corpus_id; content identity (not mtime)
as the authority; deletions are out of scope (declaration, not
desired-state reconciliation).

## Changes

- Manifest contract v1 (closed schema; unknown fields + duplicate
  sources fail validation), pure policy module, shared intake writer
  (orchestrator delegates — one execution path), control-plane
  plan/execute/status, CLI + Makefile targets, frozen fixture,
  determinism + integration suites. Full detail: refactor 0010.

## Proof

- CLI live run (frozen fixture, real control plane):
  PLAN 1: new=6, disabled=1, missing=1, invalid=0, retry=0
  EXECUTION 1: submitted=6 → all 6 query_ready
  EXECUTION 2 (replay): submitted=0
  PLAN 3: new=0, noop=6, query_ready=6
  manifest_id deterministic: manifest_e0551d662b…
- Integration gates: read-only plan (cwd-independent), idempotent
  execution, changed-content re-drive (exactly 1 re-submission,
  lineage preserved: 2 content versions under one locator),
  partial-failure resume (RETRY re-arms only the failed run;
  completed runs untouched — attempt counts unchanged), missing/
  disabled deterministic handling, batch-bounded resumable
  submission, corpus propagation through documents/chunks/Qdrant/
  Neo4j, census gap-free after convergence.
- Suites: unit/determinism/contracts 0 failures; integration 0
  failures; guards green.

## Rejected claims

- No deletion semantics implemented (manifest absence ≠ deletion
  authorization) — deferred, documented.
- No directory watching, crawling, web ingestion, remote stores,
  cloud adapters, GPU tuning, or UI.
- No new document parsers (I0 formats only).

## Open contract gaps

- Deletion/tombstoning design is deferred to a future milestone.
