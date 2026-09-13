---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E1: admit the cognitive-adapter boundary (ADR-0018, contracts/adapter/v1, pure shared core, admitted reference manifest)"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.259
architecture_impact: "Adds the adapter boundary under EXISTING owners: contracts/adapter/v1 (9 versioned wire contracts), shared/polymath_shared/adapter/ (pure, I/O-free core: contract access, manifest loader + graph integrity, closed predicate evaluator, deterministic transitions, submission validation), config/adapters/trail.product_discovery.json (the admitted reference manifest). ADR-0018 + refactor 0012. No runtime process, table, MCP tool or worker changes yet (E2); no ARCHITECTURE.md / dependencies.json change (shared may depend on contracts)."
---

> Plan §11 E1: prove Polymath is the composition root, existing control/worker/Postgres remains the workflow authority, agent-reason
> steps are typed submissions, Trail operations stay Trail-authoritative, `research_*` has one migration path, no plugin framework
> or second scheduler.

## Contract
Admit the SMALLEST adapter-workload boundary through the normal ADR/refactor/scaffold/work-log rules: versioned public contracts,
a closed step vocabulary, ownership, persistence mapping (proven in E0), failure modes, verifier and rollback — with no runtime
mutation. Everything must be deterministic and unit-proven before E2 wires it to Postgres, MCP and a worker.

## Changes
- **ADR-0018** `docs/wiki/decisions/0018-cognitive-adapter-boundary.md` (accepted under the owner directive) + **refactor 0012**
  `docs/wiki/refactors/0012-cognitive-adapter-runtime.md` (E0–E7 ledger, in_progress).
- **`contracts/adapter/v1/`**: `adapter_manifest`, `adapter_run_request`, `adapter_run_ref`, `adapter_run_status`, `adapter_step`,
  `adapter_submission`, `adapter_step_receipt`, `external_operation_receipt`, `adapter_result` — each `*.schema.json` (2020-12,
  `$id`/title/description, `additionalProperties: false`) + `*.example.json`; the manifest example IS the `trail.product_discovery`
  reference workflow (plan §7.2 A–K mapped onto the 8 step types; Trail steps carry `availability: working|planned` + `planned_node`).
- **`tests/contracts/test_adapter_contract_v1.py`** (15 tests): every example validates; the step vocabulary is closed and identical in
  manifest/step/receipt; manifest graph integrity (unique ids, every next/branch target exists, terminal = COMPILE_RESULT, reachable);
  no executable definitions in a manifest; identity fields agree across ref/status/result; the submission example satisfies its
  step's output_schema and cites only supplied evidence; result lineage references known receipts/operations.
- **`shared/polymath_shared/adapter/`** (`__init__`, `contracts.py`, `manifest.py`, `transitions.py`): schema access + `validate`/
  `assert_valid` + `stable_hash`; `Manifest`/`load_manifest`/`list_manifests` (fail LOUD on a malformed file) + `graph_integrity_errors`;
  `RunState` (immutable), `evaluate_predicate` (closed: exists/count_gte/count_lt/equals/all_of/any_of; unknown op → False),
  `next_step_id` (BRANCH resolved here, a taken branch counts a loop), `issue_step` (budgets enforced → `BudgetExhausted`; validated
  `AdapterStepV1`), `validate_submission` (output_schema + "cite only supplied evidence": every `*_ids` value must be a context id),
  `accept_submission` (only the awaiting step; identical replay idempotent; different payload rejected), `record_automatic_output`,
  `cancel_run` (terminal, idempotent), `terminal_gap` (typed), `complete_run`, `run_status_view` (validated `AdapterRunStatusV1`).
- **`config/adapters/trail.product_discovery.json`** — the admitted manifest (config is read by `list_manifests`).
- **`tests/determinism/test_adapter_runtime_pure.py`** (12 tests): manifest ↔ example identity; five broken-manifest shapes caught;
  malformed file fails loudly; predicates; a FULL walk of the reference manifest (agent step issued at sequence 5 → schema and
  uncited-evidence rejections → acceptance → bounded gap loop: exactly 3 loops then exit → scoring → interpretation → COMPILE_RESULT →
  completed; terminal never issues; cancel idempotent); budget exhaustion → typed `terminal_gap`; input validation; determinism of
  issued steps and hashes.
- scaffold TREE: every file above declared.

## Proof
- `pytest tests/contracts/test_adapter_contract_v1.py` → 15 passed; `pytest tests/determinism/test_adapter_runtime_pure.py` → 12 passed.
- Guards green (preflight / repo_guard / wiki_worm) on this commit; `wiki_worm` lists refactor 0012 as open (by design until E7).
- No process, table, tool or worker changed: `git diff --stat` touches only `contracts/`, `shared/polymath_shared/adapter/`, `config/adapters/`,
  `tests/`, `scripts/scaffold_polymath_v4.py`, `docs/`.

## Rejected claims
- **"Put the adapter in a new top-level `cognitive/` tree"** — REJECTED (plan §6, ARCHITECTURE.md §4): existing owners suffice and avoid
  the ARCHITECTURE/dependencies companion cascade.
- **"Let manifests carry callbacks / expressions for branching"** — REJECTED: predicates are a closed six-op vocabulary over dotted paths;
  `graph_integrity_errors` + the contract test refuse anything else.
- **"Acceptance rules as free text only"** — PARTIALLY REJECTED: free-text rules stay in the contract for humans, but the runtime enforces two
  machine rules on every submission (output_schema; cited `*_ids` ⊆ context evidence) — an agent can never cite evidence it was not given.
- **"Trail steps can be executed now"** — NOT CLAIMED: `G_gates`/`I_score` are `planned` (Trail C1/C2); the reference result example is a
  `terminal_gap` with `TRAIL_CAPABILITY_PLANNED` to make that honest.

## Open contract gaps
- E2 (next): migration `0061_adapter_runs.sql`, the seven MCP tools + `capabilities.MCP_TOOLS` + `_TOOL_NAMES`, `adapter_step_worker`,
  a restart-resume integration test, fleet bounce (workers/ edit).
- Owner may rename contracts/placement via ADR review (plan §4); ADR-0018 records the executor's application of the directive.
