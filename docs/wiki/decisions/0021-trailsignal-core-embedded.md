---
owner: governance
last_reviewed: 2026-09-20
last_touched: 2026-09-20
status: accepted
---
# ADR-0021 — TrailSignal's deterministic research core runs in process (`governance/trail/`)

- **Status:** accepted 2026-09-20 under the owner's consolidation migration (`docs/migration/MIGRATION_POLICY.md` "Trail embedding: authorized in principle, subject to dependency / license /
  source verification"; verification and design in `docs/migration/ADR-TRAIL-EMBEDDING.md`; decision record `AUTO_DECISIONS.md` M-012). Default mode stays `daemon`.

## Decision
1. `governance/trail/` holds the EXACT import closure of TrailSignal's `ResearchOperationService` (16 modules, 6,944 lines) plus the registry data and config it reads and its MIT licence —
   BYTE-IDENTICAL to TrailSignal A41 @ `de64d84`, every file sha256-pinned in `PROVENANCE.json`, pinned by `tests/contracts/test_trail_core_embedding.py`. No TrailSignal line is edited.
2. One Polymath-authored file, `governance/trail/embedded.py`, does what TrailSignal's daemon composition root and MCP tool layer do: builds the service over the compiled registry snapshot,
   implements TrailSignal's store port (`commit`, `load`, `load_admitted`) on SQLite (first commit wins; durable when `POLYMATH_TRAIL_STORE` names a file), and exposes an `httpx` transport that
   answers the daemon's JSON-RPC `tools/call`.
3. `POLYMATH_TRAIL_MODE=embedded` makes the worker build the SAME `TrailMCPClient` over that transport (loaded by file path); `exec_external`, `trail_client`, the request / result envelopes and the
   refusal path are unchanged. Unset / `daemon` = today's behaviour.
4. Layer rule: dependency-map owner `trail_governance` (`governance/`) may import nothing of the runtime. TrailSignal never reads or writes Polymath state.

## What does not change
TrailSignal's logical ownership (registry, admission, freshness, independence, judgement, territory, qualification, the only score / refusal), LAW 1, LAW 2, ADR-063's split. This is a deployment
boundary change only (MIGRATION_POLICY INV-5).

## Consequences
- One checkout runs the governed loop without TrailSignal's daemon, Postgres or Temporal.
- One new third-party dependency, `packageurl` (pure Python), pulled by TrailSignal's platform contracts; it must be added to `pyproject.toml` and installed in the merge window. Until then the
  embedded-core tests run under TrailSignal's interpreter and SKIP — with the reason printed — under this repo's.
- ~57 % of the imported lines are contract models unrelated to research (`data_os`, `discovery`, `platform`); trimming them is a separate change that re-pins `PROVENANCE.json`.
- D1 and M1-01..03 live in this code. They are NOT fixed here; fixing them is a documented TrailSignal behaviour change, separate from the embedding.
