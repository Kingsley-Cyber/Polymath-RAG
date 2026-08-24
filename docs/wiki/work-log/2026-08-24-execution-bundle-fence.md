---
change_id: execution-bundle-fence-v1
owner: worker
date: 2026-08-24
status: complete
architecture_impact: none (operational integrity; new identity fields, no boundary change)
last_reviewed: 2026-08-24
---

# EXECUTION-BUNDLE-FENCE-V1: per-execution code/config identity

## Contract

Every durable knowledge object must be attributable to the exact
code+configuration that produced it. A worker whose in-memory code no
longer matches the repository on disk (or whose bundle differs from the
fleet's active bundle) must refuse to claim work loudly instead of
producing provenance-orphaned knowledge.

Smallest acceptance criteria:

1. Worker startup computes `execution_bundle_hash` over: git HEAD,
   dirty-tree flag, semantic authority sha, rule-pack file hash,
   ontology file hash, pinned extraction env vars.
2. Registration heartbeat carries the bundle (worker_registrations).
3. Claim gate: a worker whose fast disk fingerprint drifted since boot,
   or whose bundle differs from the fleet-active bundle row, refuses
   claims with reason BUNDLE_MISMATCH / BUNDLE_STALE.
4. Accepted facts record provenance.generated_by_bundle_hash.
5. verify_live_build reports bundle uniformity across the fleet and
   matches workers against a freshly computed on-disk bundle.
6. Determinism tests cover: stability, sensitivity (ontology/env/dirty),
   claim refusal, fleet-uniform registry logic.

## Inputs / outputs / persistence

Inputs: repo files at boot, env, DB heartbeats. Persistence: migration
0031 (execution_bundles table + worker_registrations columns),
facts.provenance JSONB gains generated_by_bundle_hash. No boundary or
ownership change; control remains workflow authority.

## Changes

- shared/polymath_shared/execution_bundle.py (new, deterministic)
- stores/postgres/migrations/0031_execution_bundles.sql (new)
- shared/polymath_shared/worker_runtime.py (claim gate)
- workers/workers/extract_worker.py + registration writer (stamp)
- eval/v5/verify_live_build.py (bundle section)
- tests/determinism/test_execution_bundle.py (new)

## Proof

See test suite + live drift drill in session log.

## Rejected claims

- "build_sha == HEAD proves current code": false — that check passes
  for stale processes when HEAD itself is unchanged while files were
  edited after process start (observed in P0.7 parity debugging).

## Open contract gaps

- Sidecar model revisions are recorded from pinned contracts, not live
  sidecar manifest queries (deferred; sidecars already pin via verify_pin).
