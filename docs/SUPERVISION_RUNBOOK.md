# SUPERVISION RUNBOOK — Polymath V5

## Supervised processes (one supervisor, 14 slots)

`control.process_supervisor` is the process parent for the ENTIRE runtime:

| slot | health check |
|---|---|
| sidecar_gliner (:8740) | HTTP /manifest 200 |
| sidecar_spacy (:8744, own venv) | HTTP /manifest 200 |
| sidecar_embedder (:8742) | HTTP /manifest 200 |
| sidecar_reranker (:8743) | HTTP /ready 200 |
| orchestrator (:7200) | HTTP /health 200 |
| control + 8 workers | fresh worker_type registration heartbeat in Postgres |

Stores (Postgres/Redis/Qdrant/Neo4j) run under docker with restart policies
and are awaited, not supervised, by `scripts/boot_polymath.sh`.

## Boot behavior

LaunchAgent `com.polymath.v5` (installed from `deployment/com.polymath.v5.plist`)
runs `scripts/boot_polymath.sh` at login and keeps it alive: stores up →
wait for Postgres → supervisor owns everything else. Remove with
`launchctl unload -w ~/Library/LaunchAgents/com.polymath.v5.plist`.

## Restart policy

Bounded: >5 exits in 300s quarantines the SLOT (logged CRITICAL, recorded in
the state file and worker_registrations). Backoff grows with exit count.
Workers additionally renew their stage leases in-flight (60s keeper), so
long stages survive and genuine death still expires within one claim TTL.

## Verified fault matrix (live, with work in flight)

- gliner sidecar SIGKILL → healthy again in 20s; dependent worker crashes
  absorbed within budget; convergence; DETERMINISTIC replay; 0 duplicates.
- orchestrator SIGKILL → auto-restart, /health ok.
- worker SIGKILL (extract, verify) → restart ≤12s, re-registration,
  convergence, state hash byte-identical.
- full machine reboot → stores self-heal; boot script restores everything;
  in-flight corpus resumed from durable state with zero loss.

## Observability

`/tmp/polymath_fleet/supervisor_state.json` (pids, restarts, quarantine,
last exit codes) · per-slot logs in `/tmp/polymath_fleet/*.log` ·
`worker_registrations` table for capability/heartbeat/quarantine.

## Manual emergency recovery

1. `launchctl unload …` (stop auto-restart) → 2. inspect slot log →
3. fix cause → 4. `rm /tmp/polymath_fleet/supervisor_state.json` →
5. `launchctl load -w …` (or run boot script by hand). Budget-exhausted
tickets: per-ticket re-drive SQL in docs/RUNBOOK.md.

## Known wart

A worker whose sidecar dependency dies mid-claim can exit rather than fail
the ticket cleanly ("could not resolve the GLiNER pin"); the supervisor
absorbs this within the restart budget. Cosmetic under supervision; noted.
