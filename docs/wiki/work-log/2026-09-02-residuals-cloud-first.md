---
change_id: CLOUD-FIRST-V1 + STATUS-MONOTONE-V1 + ENV-OVERLAY-ON-SPAWN-V1 + GRACEFUL-LEASE-HANDBACK-V1 + DROP-TOLERANCE-SETTING + DELETE-PURGES-EXTRACTION-RECEIPTS + SPLIT-KEEPS-PARTIAL
owner: governance
date: 2026-09-02
status: complete (receipts appended below)
architecture_impact: lane policy floor (policy.py/settings.py/.env), run-status write discipline (receipts.py), supervisor spawn env + fence lease handback, coverage tolerance as a setting, document delete cascade, dispatch split back-fill
last_reviewed: 2026-09-02
---

# WORK LOG — owner-blessed cloud-first + the four residuals, root-caused or enforced

## Contract
Owner (2026-09-02): "I'll bless the cloud but these also must be fixed or
identified": (1) the unknown writer that reset a degraded run to
reconciling; (2) DROP_TOLERANCE as a setting recorded in the register;
(3) the two procedural rules — key rotation needs a fleet bounce, no
code edits during an open run — enforced in code; (4) DOCUMENT-DELETE
not purging extraction receipts. Owner asked that the fresh graphify
graph be used for the writer hunt.

## Changes
1. CLOUD-FIRST-V1 (owner-blessed): `policy.CLOUD_MIN_BYTES` 300_000 → 0,
   `WorkerSettings.cloud_min_bytes` default/floor → 0, .env
   `POLYMATH_WORKER_CLOUD_MIN_BYTES` 450000 → 0. Every non-empty
   document rides the cloud ring; the 4B local lane is no longer
   selected by size. `require_cloud_eligible` stays (0-byte sources and
   raised thresholds still refuse). Retires the 2026-08-29 rule under
   which small-doc lane choice was worker-affinity luck (Gambling: cloud
   → 69 entities/26 relations in 30 s; local → 23/0 in 166 s, degraded).
2. STATUS-MONOTONE-V1 (receipts.py `ReceiptWriter.run_status`) — THE
   UNKNOWN WRITER, root-caused: every chain worker (intake, extract,
   profile, canonicalize, project_*, compile_objects) writes
   `run_status("reconciling")` when its stage completes; a census
   re-armed project_qdrant completing at 08:06:26Z overwrote the
   `degraded` verdict set at 310 s. Found by a repo-wide grep for
   parameterized `UPDATE runs SET status = %s` (the graphify query
   returned a 700-node neighborhood; the AST graph has no SQL-literal
   edges, so it located callers, not the write). "reconciling" is now a
   PROGRESS write: applied only over intake/reconciling; verdict writes
   (degraded, query_ready, failed) stay explicit and unrestricted.
3. ENV-OVERLAY-ON-SPAWN-V1 (process_supervisor `_spawn`): children no
   longer inherit only the supervisor's boot snapshot — every spawn and
   respawn overlays the current `.env` (`_dotenv_overlay`, pure parser).
   Key rotation now needs a worker respawn (which the fence and the
   autopilot do routinely), not a fleet restart. Enforced, not procedural.
4. GRACEFUL-LEASE-HANDBACK-V1 (process_supervisor fence path): before a
   fence restart the supervisor hands the worker's leases back to
   `ready` WITHOUT consuming an attempt (`_release_leases_of_pid`,
   joined through worker_registrations.pid). Left alone, the heartbeat
   stopped, the expiry sweep charged owner-stale attempt+1, and two fence
   restarts cost Blue Ocean two of three attempts. The "no code edits
   during an open run" rule is now harmless instead of procedural.
5. DROP-TOLERANCE-SETTING: `ControlSettings.extraction_drop_tolerance`
   (default 0.10, register-recorded) threaded main → census →
   `coverage_verdict(drop_tolerance=)`; the module constant remains the
   fallback.
6. DELETE-PURGES-EXTRACTION-RECEIPTS (ui.py `_delete_document_tx`):
   `extraction_call_receipts` join the cascade (optional savepoint).
7. SPLIT-KEEPS-PARTIAL (llm_provider `_dispatch`, found by the legacy
   coverage pins): V2's output-aware split discarded the truncated
   call's partial packet; when the split singles quarantined, items the
   model had already returned were lost. Split results win; the partial
   back-fills only the neighborhoods the split could not return, so the
   coverage pass marks the cut item incomplete and re-issues it as
   before the split existed.
8. HERMETIC-LANE-DOUBLE (tests): four coverage-gate tests and audit
   test_3 monkeypatched `make_client`, which the THROUGHPUT-V2 cloud
   branch never calls — they had been hitting real endpoints. Wired to
   a single fake endpoint + the fake as the client factory; the two
   pre-V2 truncation pins rewritten to the split contract.

## Proof
- test_supervisor_env_overlay.py 3 green (parser, missing file, spawn
  wiring pin); test_incremental_census 5; test_fleet_autopilot_demand 6;
  test_family_interleave 5; test_client_resilience 21;
  test_fleet_v3_limits 7; test_throughput_v2 13; coverage gate,
  llm_extraction, extraction_pool, llm_audit_fixes updated to the
  cloud-first floor and the hermetic doubles — green (counts in the
  commit message).
- LIVE RECEIPT, ENV-OVERLAY-ON-SPAWN-V1: a probe variable appended to
  .env AFTER the fleet booted was present in the environment of the
  next respawned child (control.main pid 95405: value matched); probe
  removed. No fleet restart was needed.
- FULL determinism suite (post-change): 8 failures — the 5 pre-existing
  (killchain gaps, llm_controller stale fake, sval ×3) + 2 in
  test_graph_lifecycle_v2 that read the LIVE Postgres/Neo4j state
  while the receipt run was deleting and re-ingesting two documents
  (re-verify at rest) + test_syntax_readiness_v3 ×2 that PASSED on
  immediate rerun (DB-state flake, not code). The four 450 KB-threshold
  failures from earlier today now pass under the cloud-first floor.
- From-zero Gambling + Netnography receipts on the cloud-first fleet:
  appended below when terminal.

## Rejected claims
- Per-run watermarks for the census — the uncached-dirty clause covers
  the race at O(active runs).
- A hard coverage floor — contradicts the setting's own contract; the
  drop tolerance amends the drop rule only.
- Auto-restarting the fleet on `.env` change — a spawn-time overlay is
  deterministic and needs no restart; running workers refresh on their
  next respawn.

## Open contract gaps
- `_release_leases_of_pid` has no DB unit test (fixture columns for
  worker_registrations/stage_tickets not modeled in the harness); live
  receipt = the next fence restart's log line.
- Six pre-existing determinism failures remain chip-tracked (killchain
  gaps, sval ×3, llm_controller stale fake, plus any the full run shows).
