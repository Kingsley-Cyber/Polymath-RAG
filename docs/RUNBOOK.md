# POLYMATH V5 — OPERATIONS RUNBOOK

Branch `architecture/evidence-first-v5`. Postgres is the sole authority;
Neo4j/Qdrant are rebuildable projections; raw provider evidence is immutable
(L1) and interpretation never deletes it.

## Start / stop

```bash
# stores (docker)
docker compose up -d postgres redis qdrant neo4j

# sidecars (own venvs, "assumed running" by the fleet)
cd sidecars/spacy_runtime  && nohup .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8744 & cd -
# gliner sidecar: same pattern, port 8740 (pinned urchade/gliner_medium-v2.1)

# supervised worker fleet (CP2.1: bounded auto-restart, quarantine, state file)
./scripts/run_fleet_supervised.sh legacy_v1 on 1.3.0 legacy_v1
# state: ~/PolymathRuntime/logs/fleet/supervisor_state.json · logs: ~/PolymathRuntime/logs/fleet/*.log

# orchestrator (retrieval API, :7200)
cd orchestrator && nohup ../.venv/bin/python -m uvicorn orchestrator.main:app \
  --host 127.0.0.1 --port 7200 >> ../var/log/api.log & cd -
```

Environment contract (all workers + drivers): `POLYMATH_PG_DSN`,
`POLYMATH_SYNTAX_PROVIDER=spacy`, `POLYMATH_RESCUE=on`,
`POLYMATH_WORKER_RULE_PACK_VERSION=1.3.0`, `POLYMATH_CHUNKER=legacy_v1`,
`POLYMATH_RELATION_PIPELINE=legacy_v1`. **The eval drivers read the DSN from
settings — running them without the env yields pool timeouts, not errors.**

## Health

```bash
curl -s localhost:7200/health            # orchestrator
curl -s localhost:8740/manifest          # gliner pin
curl -s localhost:8744/manifest          # spacy pin
python3 -c "import json;print(json.load(open(__import__('os').path.expanduser('~/PolymathRuntime/logs/fleet/supervisor_state.json'))))"
# DB: SELECT worker_type,status,COUNT(*) FROM worker_registrations GROUP BY 1,2;
```

## Ingest a corpus

Write a manifest (see `eval/i4/manifest.yaml`), then:

```python
from polymath_shared.manifest import load_manifest
from control.manifest_ingest import execute_manifest   # idempotent by content hash
```
Convergence: `runs.status='query_ready'` per document. Stage progress:
`stage_tickets` by `(stage,status)`. EPUB/PDF/DOCX materialize at intake.

## Failure recovery

| symptom | action |
|---|---|
| worker process dies | none — supervisor restarts (bounded), control re-leases |
| worker crash-loops | slot QUARANTINED; read `~/PolymathRuntime/logs/fleet/<name>.log`, fix, delete state file, restart fleet |
| worker alive but stale binary | semantic-bundle fence refuses claims; restart fleet after deploys — **plumbing changes don't move the fence hash by design** |
| ticket `failed`, attempt=3 | bounded retry exhausted (deterministic failure). Fix cause, then re-drive: wipe corpus + resubmit (content-addressed ids make it idempotent) |
| Neo4j lost/suspect | `eval/v5/reconstruct.py --corpora <...>` — full wipe + exact rebuild from Postgres |
| Qdrant collection lost | same tool, `--qdrant-corpus <id>` — re-embed + rebuild, exact |
| semantic state suspect | `eval/v5/shadow_settlement.py --corpus <id>` (ledger reproduces settlement, UNRULED_SEMANTIC_DELTA must be 0) and `eval/v5/replay_full.py` (fact-id set identity) |
| orphaned semantic rows | `verify_worker.reconcile_semantic_residue` (dry-run default) + `reconcile_graph_residue` |

## Verification suite

```bash
.venv/bin/python -m pytest tests/                      # 596 gates
.venv/bin/python eval/i4/verify_i4.py --phase facts    # frozen surface metrics
.venv/bin/python eval/census/verify_census.py --corpus i4-fresh-acceptance-v1
.venv/bin/python eval/sealed/report.py --corpus <id> [--set <sealed-set>]
```

## Run the test suites

SEALED-TEST-ISOLATION-V1 (2026-11-20): no test reaches a live store or the live fleet unless you opt in. The rules live in
`tests/sealed_env.py`; `tests/conftest.py` enforces them.

1. Start a throwaway Postgres on a port other than 5432 (the suite refuses 5432):

   ```bash
   docker run -d --rm --name pmv4-sealed-pg -e POSTGRES_USER=polymath -e POSTGRES_PASSWORD=polymath-dev -e POSTGRES_DB=polymath -p 127.0.0.1:55432:5432 postgres:16-alpine
   ```

2. Apply every migration in order:

   ```bash
   for f in stores/postgres/migrations/*.sql; do docker exec -i pmv4-sealed-pg psql -U polymath -d polymath -v ON_ERROR_STOP=1 -q < "$f" || break; done
   ```

3. Run the suites in a clean environment (`POLYMATH_PG_DSN` follows `POLYMATH_TEST_DSN` on its own). From a worktree that
   uses the live checkout's `.venv`, `PYTHONPATH` must name the worktree's four packages, or the editable install loads `main`'s:

   ```bash
   env -i HOME="$HOME" PATH="$PATH" PYTHONPATH="$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control" POLYMATH_TEST_DSN=postgresql://polymath:polymath-dev@127.0.0.1:55432/polymath .venv/bin/python -m pytest tests/contracts tests/determinism -p no:cacheprovider
   ```

4. Read the `live-fleet guard` section at the end of the output: every line is code that tried to reach a live port and was
   refused (no connection was made).
5. Remove the database: `docker rm -f pmv4-sealed-pg`.

| Variable | Effect |
|---|---|
| `POLYMATH_TEST_DSN` | the sealed database. Unset: database tests skip. Port 5432 or no port: the session stops before any test. |
| `POLYMATH_LIVE_PROBES=1` | runs the declared live probes (`sealed_env.live_fleet(...)`) and the `frontend-v2` live tiers against the running fleet. They write live query receipts and may spend model calls. |
| `POLYMATH_INTEGRATION=1` | lets `tests/integration/` reach the live stores (that bucket's own opt-in). |

## Sealed qualification

`eval/sealed/README.md` — seal BEFORE ingestion; verify; run; stamp; replay.
Engineering fixes mid-run move the code commit and BREAK the seal loudly:
re-seal explicitly with `--force` and record why. Never tune against sealed
material.

## Known limitations (release posture)

The V4 semantic-freeze limitations carry forward (plan: KNOWN LIMITATIONS),
plus at book scale: provider type instability fragments same-surface
identities (`harvard` Location vs Organization) — the row-51 homonym-guard
trade-off, measured, not yet ruled on.

## Addenda (book-scale cycle)

- The reranker sidecar (:8743) is a HARD dependency of FAST retrieval:
  `nohup .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8743 --app-dir sidecars/reranker &`
- Per-ticket re-drive (lighter than corpus wipe), for budget-exhausted
  deterministic failures after the cause is fixed:
  `UPDATE stage_tickets SET status='ready', attempt=0, lease_owner=NULL,
   lease_expires_at=NULL, last_error_note='operator re-drive: <why>' WHERE …`
- stage_attempts rows are keyed by deterministic attempt id: retries UPDATE
  the same row; filter monitoring on `completed_at`, never `started_at`.
- After a reboot: docker stores self-heal; restart sidecars (8740/8742/8743/8744,
  spacy has its OWN venv), then the supervised fleet, then the orchestrator.
