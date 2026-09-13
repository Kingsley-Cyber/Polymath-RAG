---
owner: governance
last_reviewed: 2026-09-13
last_touched: 2026-09-13
status: accepted
---
# ADR-0018 — The cognitive-adapter boundary (COGNITIVE-ADAPTER-TRAIL-E2E-V1)

- **Status:** accepted 2026-09-13 under the owner directive COGNITIVE-ADAPTER-TRAIL-E2E-V1 (`docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md`
  §0–§6, issue #4). The directive fixes the architecture (Polymath = composition root; TrailSignal = internal subgraph through its public
  boundary; typed AGENT_REASON steps; no second workflow engine); this ADR records the executor's application of plan §6 (placement) and
  §4/§5 (contracts, closed vocabulary). The owner may amend names or placement; the E0 gap matrix (11.258) is the evidence base.

## Context
Polymath already runs an agent-driven workflow (`research_*`: SQLite/JSON state driven out-of-process through a subprocess) and a
durable ingestion control plane (Postgres `runs`/`stage_tickets`/`receipts`/`outbox_events`, the control tick, leased workers).
The owner wants ONE end-to-end product: a connected agent (Hermes) opens one Polymath MCP connection, starts one adapter run,
Polymath supplies knowledge and workflow discipline, TrailSignal supplies web/evidence/scoring through its public MCP surface, and
the final domain result is fetched under the same run_id. The E0 matrix proved the existing tables cannot host such a run (corpus-scoped
`runs`, no per-step payload, no BRANCH, no external-operation reference) and that `research/` + `mcp_server/` sit outside the layer map.

## Decision
1. **One adapter-run authority in Polymath.** A versioned `AdapterManifestV1` (semantic workflow only: identity + schema versions +
   a CLOSED step list + branch predicates + budgets) drives a durable adapter run. No caller-supplied code, callbacks, shell, or
   arbitrary graph expressions; manifests are declared configuration under `config/adapters/`.
2. **Closed step vocabulary (8):** `POLYMATH_RETRIEVE`, `POLYMATH_COMPILE_PLAN`, `POLYMATH_GRAPH_EXPAND`, `EXTERNAL_OPERATION`,
   `AGENT_REASON`, `VALIDATE`, `BRANCH`, `COMPILE_RESULT`. `AGENT_REASON` is the ONLY step a connected agent answers; every other
   step is executed by the runtime. A step type is added only when an admitted adapter needs it and tests prove generic semantics.
3. **Versioned wire contracts** in `contracts/adapter/v1/`: `AdapterManifestV1`, `AdapterRunRequestV1`, `AdapterRunRefV1`,
   `AdapterRunStatusV1`, `AdapterStepV1`, `AdapterSubmissionV1`, `AdapterStepReceiptV1`, `ExternalOperationReceiptV1`, `AdapterResultV1`.
   Every run/status/result repeats `adapter_id`, `adapter_version`, `workflow_version`, `retrieval_policy_version`,
   `input_schema_version`, `output_schema_version`; frozen at release per `contracts/README.md`.
4. **Placement under EXISTING owners (no new top-level path, no `ARCHITECTURE.md`/`dependencies.json` edit):**
   `contracts/adapter/v1/` (wire schemas); `shared/polymath_shared/adapter/` (pure: contract access, manifest loader + graph integrity,
   closed predicate evaluator, transition rules, submission validation — no I/O); `orchestrator/orchestrator/mcp_server.py` (thin
   `adapter_list/start/next/submit/status/result/cancel` tools, E2); `workers/workers/adapter_step_worker.py` (durable automatic-step
   execution + external-operation polling, E2); ONE migration `stores/postgres/migrations/0061_adapter_runs.sql` (`adapter_runs`,
   `adapter_steps`, step receipts, `external_operation_ref`; justified by E0 gaps 1/2/4/5), reusing `outbox_events`,
   `receipts.stage_transaction`, ticket leasing and the side-stage own-ticket precedent — never a second scheduler.
5. **Authority split.** Polymath owns the adapter run, its steps, validation of agent submissions, and cross-system lineage; TrailSignal
   owns every Trail sub-operation (Polymath stores `ExternalOperationReceiptV1` references only — never Trail state, bytes, CSV/Postgres/blob);
   the numeric opportunity score originates only in Trail (LAW 1); leads are never evidence.
6. **`research_*` is migration input** (plan §10): it becomes `trail.product_discovery` steps or a thin compatibility wrapper after an
   equivalence proof; no second product-research authority remains.

## Consequences
Easier: one public MCP surface for any cognitive workload; restart-safe runs on the proven Postgres/lease/outbox substrate; agent
reasoning is a typed, validated submission with a receipt; a second adapter (`substack.article_development`) reuses the runtime with
different semantics. Harder: a new migration and worker to maintain; Trail's commerce capabilities (C1/C2) do not exist yet, so the
reference adapter's evidence-gate and scoring steps are `planned` until Trail's graph reaches them. New failure modes: budget
exhaustion (typed `terminal_gap`), submission rejection (schema / uncited evidence), external-operation failure/cancel (typed, no
fabricated outputs).

## Triggered refactors
- `docs/wiki/refactors/0012-cognitive-adapter-runtime.md`
