---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E2: the adapter-run substrate (migration 0061, service/store, step worker, /adapter routes, 7 MCP tools) with a proven crash-resume"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E2
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.260
architecture_impact: "New durable authority for adapter runs (stores/postgres/migrations/0061: adapter_runs, adapter_steps, adapter_results — additive; existing tables untouched). shared/polymath_shared/adapter/{store,service}.py compose the pure core with Postgres; workers/workers/adapter_step_worker.py executes automatic steps (knowledge steps over the orchestrator HTTP API — workers never import orchestrator); orchestrator/api/adapter.py + 7 adapter_* MCP tools are the ONE public surface; capabilities advertises adapter v1. Second admitted manifest polymath.knowledge_brief (Trail-free). EXTERNAL_OPERATION steps are typed gaps until E4. Live only after the production worktree takes this code + a bounce."
---

> Plan §11 E2: list one admitted adapter; start one durable run; execute/retrieve one automatic step; issue one typed
> AGENT_REASON step; validate one submission; resume after a controlled restart; compile one terminal result with receipts.

## Contract
A real production path — not a fixture — on the existing Postgres/lease discipline: one committed unit per step; a
crashed worker leaves an expiring lease and the next worker re-executes the ISSUED step idempotently; the agent's
reasoning is a validated `AdapterSubmissionV1` with a receipt; the terminal `AdapterResultV1` carries lineage to the
Polymath evidence identities it used. E0 proved `artifacts`/`receipts`/`outbox_events`/`stage_tickets` all REFERENCE
`runs(run_id)` (corpus-scoped, ingestion lifecycle), so the adapter run needs its own tables.

## Changes
- **`stores/postgres/migrations/0061_adapter_runs.sql`** — `adapter_runs` (identity + plan-§4 versions, transition state, lease,
  typed failure/gap, UNIQUE idempotency_key), `adapter_steps` (PK run_id+sequence: issued AdapterStepV1, submission, output,
  AdapterStepReceiptV1, ExternalOperationReceiptV1), `adapter_results` (AdapterResultV1 + hash). Additive, `IF NOT EXISTS`.
  **Rollback**: `DROP TABLE adapter_results, adapter_steps, adapter_runs;` (owner-run). **Replay proof**: applied to the dev store
  and re-applied idempotently (0 changes); CI applies it to a fresh Postgres in order.
- **`shared/polymath_shared/adapter/store.py`** — SQL over the caller's `db.tx` connection: insert/load/save run, idempotency lookup,
  step rows (issue → finish with receipt/output/submission/external), results, `claim_run` (FOR UPDATE SKIP LOCKED, lease),
  `renew_lease`, `release_lease`. **`service.py`** — `list_adapters`, `start` (idempotent on `adapter_id:idempotency_key`; input
  validated; run opens `running`), `next_step`, `submit` (accept → `running`; rejection receipted, step stays open), `status`,
  `result` (synthesised for cancelled/failed/gap runs), `cancel`, and **`advance`** — the step engine: issue → execute automatic
  steps through injected executors → stop at AGENT_REASON / COMPILE_RESULT / typed gap / budget; evidence refs accumulate per
  step (`_evidence_refs`) and bound the agent's context; `_compile_result` builds lineage (evidence ids, query receipts, step
  receipt hashes, external operations) and validates the result contract. `RunState.options` carries request_options.
- **`workers/workers/adapter_step_worker.py`** — claim/advance/release loop (`--once`, `--max-steps`, `--lease-s`, `--crash-after`
  test hook); executors: `POLYMATH_RETRIEVE` (`POST /retrieve` — EXPLORE contract rows, or lane hits normalised to chunk rows),
  `POLYMATH_COMPILE_PLAN` (`/retrieve/plan`), `POLYMATH_GRAPH_EXPAND` (EXPLORE graph rows), `VALIDATE`, `BRANCH`,
  `EXTERNAL_OPERATION` → typed gaps `TRAIL_CAPABILITY_PLANNED` / `TRAIL_CONNECTOR_PENDING` (E4). Executor exceptions become a
  typed `STEP_EXECUTOR_ERROR` failure receipt, never a silent skip.
- **`orchestrator/orchestrator/api/adapter.py`** (mounted in `main.py`): `GET /adapter/list`, `POST /adapter/start`,
  `GET /adapter/{run}/next|status|result`, `POST /adapter/{run}/submit|cancel` — 404 unknown, 422 rejected (errors returned),
  409 result-not-terminal. **`capabilities.py`**: `adapter: v1`, endpoints, `ADAPTER_MCP_TOOLS`. **`mcp_server.py`**: the seven
  bearer-gated tools + `_TOOL_NAMES`.
- **`config/adapters/polymath.knowledge_brief.json`** — retrieve → AGENT_REASON brief (cite only supplied evidence) → compile.
  Retrieve steps in both manifests use `mode: EXPLORE` (the contract-rows view; measured: HYBRID/FAST/GRAPH answer with hits).
- **Tests**: `tests/determinism/test_adapter_service_store.py` (5: full substrate walk with a fake executor — receipts, rejection
  keeps the step open, acceptance, completion, lineage, result hash; idempotent start; cancel + synthesised result; lease
  claim/no-double-claim/renew/release/expiry; thin HTTP routes incl. 404/422/409), `tests/integration/test_adapter_runtime_restart.py`
  (LIVE, skips without the orchestrator: crash-resume with real retrieval), `test_mcp_server_v2.py` (+ the seven tools and their
  required arguments).

## Proof
- Substrate + routes + MCP surface: 10 green (`test_adapter_service_store.py`, `test_mcp_server_v2.py`); contracts 15; pure core 12.
- **Crash-resume, live** (`tests/integration/test_adapter_runtime_restart.py`, corpus `cinema`, orchestrator 127.0.0.1:7200):
  worker #1 executed RETRIEVE over HTTP (35 evidence refs) then `os._exit(137)` holding its lease → run still `running`, step
  `executed`, lease held → after the 2 s lease worker #2 resumed and issued the AGENT_REASON step whose `context.evidence_refs`
  ⊇ the pre-crash evidence → a submission citing two of those ids was accepted → worker #3 compiled → `adapter_result` =
  `completed`, lineage cites the same ids, 2 receipt hashes, `gap` null. Run `adr_fe7f45d7…` (deleted by the test's cleanup).
- Migration replay: dev store 3 tables present after apply + idempotent re-apply.
- Guards green on this commit; TREE declares every new file.

## Rejected claims
- **"Reuse `stage_tickets`/`outbox_events` for adapter steps"** — REJECTED (E0 + FK proof above).
- **"Execute knowledge steps in-process in the worker"** — REJECTED: workers may not import orchestrator (`architecture/dependencies.json`
  forbidden_imports); the HTTP seam is the one research/ already uses.
- **"HYBRID returns contract rows when evidence=true"** — DISPROVEN live (returns `evidence` hits); EXPLORE / evidence-only return
  `evidence_rows` (chunk/document/graph_fact/graph_hop); the executor now accepts either.
- **"The compile step's receipt belongs in the result lineage"** — REJECTED: the result is hashed before that receipt exists; the compile
  receipt records the result hash instead.

## Open contract gaps
- **Supervised slot**: the worker is not yet a `process_supervisor` slot (worker health there = a `worker_registrations` heartbeat that
  only `run_worker` emits); run it manually or add registration in the close-out. Production picks this code up only after the
  production worktree takes it (branch switch/merge) and a fleet bounce.
- **E4** wires `EXTERNAL_OPERATION` to TrailSignal's WORKING tools (discover/crawl/scrape/extract/paging/cancel) with
  `ExternalOperationReceiptV1`; until then those steps end runs with a typed gap.
- Result output for `trail.product_discovery` cannot satisfy its output_schema until Trail C1/C2 exist (`TRAIL_CAPABILITY_PLANNED`).
