---
change_id: bootstrap-v4
owner: governance
date: 2026-08-13
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: complete
architecture_impact: baseline
---

# Bootstrap the Polymath v4 repository

## Contract

Create a reproducible repository scaffold whose architecture, dependency
map, managed scripts, and work-log rules agree and pass their static checks.

## Changes

- Accepted Postgres as workflow authority and the other stores as
  rebuildable or disposable layers.
- Defined one resident Mac GLiNER runtime for the entity and evidence passes.
- Added machine-readable dependency ownership, script registration, and
  append-only work logs.
- Added preflight, repository guard, and wiki audit entrypoints.

## Proof

The scaffold was materialized twice with no file changes on the second run.
Preflight, repository guard, wiki audit, Python compilation, and Compose
configuration passed. The unchanged test suite reported 5 passed, and all
four JSON schemas passed Draft 2020-12 meta-validation. A negative guard
fixture rejected an architecture edit missing its changelog, ADR, refactor,
and work-log companions.

## Rejected claims

- Two Mac GLiNER processes were rejected because they load the same model
  twice without measured evidence that the duplication helps.
- Automatic cloud routing was rejected until the local production path is
  proven.

## Open contract gaps

- Model revision, weights digest, thresholds, batching, and readiness probe
  remain unpinned until the target-Mac qualification experiment.
- Production intake, receipts, compiler wiring, and recovery are planned but
  remain placeholders.
