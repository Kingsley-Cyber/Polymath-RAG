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

## Proof (live drill, 2026-08-24)

1. Fleet restart on 8d7371a: all 8 pipeline workers registered ONE
   bundle hash (83e00583925b1a4e) — fleet uniformity.
2. Stale detection: after the next commit (fence config-source fix),
   verify_live_build flagged `recorded 83e00583 != fresh c98ced4c
   (stale memory)` with a CLEAN tree — exactly the blind spot this
   slice closes; build_sha==HEAD still passed at that moment.
3. Restart: fence PASS 12/12 including execution_bundle section
   (fresh=c98ced4cedc2, uniform, clean).
4. Output stamping: novel sentence probe produced fact
   developed_by ACCEPT carrying provenance.generated_by_bundle_hash =
   bundle_c98ced4cedc2c155. Pre-existing identical facts keep their
   original rows untouched (content identity idempotency).
5. worker_contracts now includes rule_pack_file_sha + ontology_file_sha,
   so semantic-file drift mints successor runs via existing contract
   reconciliation.

## Operational notes recorded

- 408 reconciling-status scale-10k runs carried legacy-shape chunked.v1
  events ({run_id, ticket_id}, no doc_id) from an earlier
  reconciliation writer generation. The extract worker consumed each
  once and crashed KeyError('doc_id'); events are now all delivered;
  no tickets burned (those runs have none); their work is carried by
  the active successor chain. Writer-side payload contract remains the
  durable fix candidate.
- One pre-existing dead ticket (probe-enf2, malformed event) predates
  this slice; watcher treats dead>0 as regression. Owner call: purge
  poison corpus or amend watcher baseline.
