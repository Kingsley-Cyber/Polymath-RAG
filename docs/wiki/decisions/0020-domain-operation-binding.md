---
owner: governance
last_reviewed: 2026-09-20
last_touched: 2026-09-20
status: accepted
---
# ADR-0020 — DOMAIN_OPERATION: a manifest step binds a domain's own code

- **Status:** accepted 2026-09-20 under the owner's consolidation migration (`docs/migration/MIGRATION_POLICY.md`; `EXECUTION_PLAN.md`
  Phase 3 "Domain binding seam"; decision record `docs/migration/AUTO_DECISIONS.md` M-007). Extends ADR-0018 decision 2 / ADR-0019 (the
  closed step vocabulary) by ONE member. Nothing else in ADR-0018 / ADR-0019 changes.

## Context
The adapter runtime executes manifests over a closed step vocabulary. Until now an adapter's domain intelligence could live in only
three places: the agent's reasoning (`AGENT_REASON`), the host harness (`HARNESS_ACTION`), or TrailSignal (`EXTERNAL_OPERATION`).
The ecommerce engine imported at `adapters/ecommerce/` (migration Phase 2) carries deterministic domain code that is none of these —
admissibility laws, ranking, query and sourcing planning, parsers, joins. The governed path had been re-deriving that behaviour
inside agent prompts, or not at all.

## Decision
1. **One new AUTOMATIC step type, `DOMAIN_OPERATION`.** Manifest step `config`: `domain` (a directory name under `adapters/`),
   `operation` (a dotted id), optional `inputs` (name → dotted path over `input` / `options` / `outputs` / `context`). `config.domain`
   and `config.operation` are invalid on any other step type.
2. **The existing worker executes it** through the existing `EXECUTORS` table (`exec_domain`). It runs
   `<repo>/adapters/<domain>/binding.py` OUT OF PROCESS with the worker's interpreter: one `domain_operation_request.v1` JSON object
   on stdin, one JSON object on stdout, a hard timeout, a 1 MB response cap, and a MINIMAL environment (no DSN, token or key is
   inherited). The resolved binding must sit inside `adapters/`.
3. **Domain failures use the existing typed semantics.** `{"ok": false, "code", "message"}` is a typed gap carrying the domain's own
   code. A crash, a non-zero exit, a timeout, an oversized or malformed response raises, which `service.advance` already records as
   `STEP_EXECUTOR_ERROR`. `{"ok": true, "output"}` becomes the step output, which `BRANCH` predicates can read — a domain verdict can
   return a run to reasoning.
4. **Domain code computes; it never owns state.** It receives values the manifest selected and returns a value. It cannot read or
   write the run, the hypothesis ledger, a store or Trail. The output carries `_domain` lineage: domain, operation, sha256 of the
   binding file (the engine is read from disk per call and is not part of the worker bundle hash).
5. **The runtime stays neutral.** The manifest names the domain; `service`, `transitions`, `manifest`, `contracts`, `store` and the
   worker never do (`test_adapter_runtime_neutrality.py` unchanged and green).
6. **Layer rule.** `architecture/dependencies.json` gains owner `domain_adapter` (`adapters/`) that may depend on nothing here and
   may not import `shared`, `orchestrator`, `worker`, `control` or `sidecar`. The boundary is the JSON request, not an import.

## Not decided here
No budget counter for the new type (`max_steps` bounds it). No second domain. No plugin / entry-point registry, no SDK. Which engine
functions are bound, and how their shapes map onto `HypothesisStateV1`, is migration Phases 4–5.

## Consequences
- The four step-type enums in `contracts/adapter/v1/` and `contracts.STEP_TYPES` gain one member; existing manifests stay valid. The
  closed-vocabulary pin in `tests/contracts/test_adapter_contract_v1.py` is extended by the same member in the same slice.
- `shared/` and `workers/` change, so merging this branch into the live checkout needs a fleet bounce.
- An out-of-process call costs tens of milliseconds per step; acceptable for a run measured in minutes.

## Alternatives rejected
`EXTERNAL_OPERATION` with another `system` (mixes domain planning into the executor that enforces Trail identity and LAW 1, and spends
Trail's budget) · overloading `VALIDATE` (documented closed and schema-free) · in-process import (the engine is ~40 flat top-level
modules named `store`, `graph`, `transitions`, `models`, …; it would also enter the stale-bundle fence) · host-side only (not governed,
not deterministic) · a plugin SDK (speculative).

## Addendum 2026-09-20 — an agent-answered step may be SHOWN prior step outputs (`materials`)
Composing the first product manifest on this seam exposed a gap that pre-dates it (external-review finding M1-08: `W_interpret` could not see TrailSignal's
records): an `AGENT_REASON` / `HARNESS_ACTION` step saw only `context` (evidence refs, live hypotheses). A domain law's errors, the lived clusters or Trail's
score records were invisible to the agent that had to act on them.

- A step the agent / harness answers may declare `config.show`: `{name: "outputs.<step>.<key>" | "input.<key>"}`. `manifest.py` refuses it on any other step type.
- `service.next_step` resolves it and returns a SIBLING key `materials` = `{values, missing, too_large, authority}` next to `step` and `evidence` — the same
  mechanism TG2a used for `evidence`. The `AdapterStepV1` contract, the citation rules and the hypothesis ledger are unchanged; materials are context for
  reasoning, never citable evidence. Values are bounded (400 kB per step; what does not fit is NAMED in `too_large`). A manifest without `config.show` gets no
  key at all, so the three pre-existing adapters behave exactly as before. A read failure is said in `materials.error`, never raised.
- `POLYMATH_RETRIEVE` / `POLYMATH_COMPILE_PLAN` / `POLYMATH_GRAPH_EXPAND` `config.source` may now also name a prior step output (`outputs.<step>.<key>`), so a
  domain operation can compile the need a knowledge step asks (an empty value falls through to the existing seed fallback).
