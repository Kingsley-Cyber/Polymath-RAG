---
change_id: CONSOLIDATION-MIGRATION-PREMERGE-VALIDATION
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none beyond ADR-0020's addendum — one defect fix in the `materials` sibling key (strictly opt-in), one declared dependency, one isolation-guarded integration test. Branch `migration/ecommerce-consolidation`, NOT merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — pre-merge validation on an isolated Postgres, and one defect it found

## Contract
`docs/migration/AGENT_OPERATING_DOCTRINE.md` §7 (NOW: the missing embedded-Trail dependency; NEXT: merge-window validation), §10 (classify failures), §14 (never use the production database / fleet as a
test harness; prefer isolated databases). `EXECUTION_PLAN.md` "preparing production merge" = a broad-suite gate.

## Changes
- `workers/pyproject.toml` — `packageurl-python>=0.16,<1` (TrailSignal's platform contracts import it; the worker hosts the embedded core). Installed additively into the shared `.venv` with
  `uv pip install` (0.17.6, the version TrailSignal pins); no resync.
- `shared/polymath_shared/adapter/service.py` — DEFECT FIX (classified: migration defect). `_materials` returned a `materials` key carrying an error whenever the run could not be loaded, even for a step
  whose manifest never declared `config.show`; `tests/determinism/test_adapter_evidence_boundary.py` pins `next_step`'s exact keys and caught it. Now OPT-IN FIRST: no `config.show`, or opt-in cannot be
  determined → NO key. A read failure is reported in `materials.error` only for a step that opted in.
- `tests/integration/test_adapter_ecommerce_product_research_pg.py` — the complete scripted run on the REAL Postgres adapter store. It REFUSES to run unless `POLYMATH_ISOLATED_PG=1` is set with the DSN,
  because between steps the run is committed `running` (what a live worker claims).
- `tests/determinism/test_adapter_ecommerce_product_research_e2e.py` — pins the opt-in rule (a step without `config.show` answers with exactly `kind, step, status, evidence`).

## Proof
- Under THIS repo's interpreter, after the install: the 12 TrailSignal-dependent tests pass (embedded core 4, replay equivalence 3, the complete run against the real TrailSignal code 1, provenance 4) —
  previously they skipped here.
- ISOLATED Postgres (throwaway `postgres:16-alpine` container on 127.0.0.1:55432, the image already on this machine, all 65 repository migrations applied, removed afterwards): the Postgres-backed adapter
  suites `test_adapter_service_store`, `_harness_action`, `_evidence_boundary`, `_product_discovery_loop` and `tests/integration/test_adapter_runtime_restart` — first run 40 passed / 1 FAILED (the defect
  above), after the fix **41 / 41**. The new real-store run: `completed`; 15 `DOMAIN_OPERATION` rows `executed` in the real step table (no step-type constraint exists in migration 0061, so NO Postgres
  migration is needed); 3 ledger hypotheses moved by TrailSignal's verdicts; 8 admitted-evidence rows; run deleted afterwards.
- Database-free set after the fix: 43 passed. Guards 0 / 0 / 0 / READY.
- Evidence class: `INTEGRATION_EXECUTED` on an isolated real Postgres + scripted inputs. NOT `MERGED`, NOT `DEPLOYED`.

## Rejected claims
- "The merge window was executed." It was NOT. The fleet was stopped for it, the merge into `production` was DENIED by the session's permission gate (production deploy), and the fleet was rebooted from the
  UNCHANGED `production` checkout. Side effect, stated plainly: that boot made live the already-committed TG4 change that had been waiting for its next bounce (`6708301`, Server A legacy tools lead with
  DEPRECATED) — running bundle `9cb421b4eeed` → `fa72e3b1adde`. Nothing of this branch is live. `packageurl-python` IS now installed in the live environment (additive, pure Python).

## Open contract gaps
- `ADAPTER_RUNTIME` — UPDATED (the opt-in fix) and TESTED on the real store. `MCP_SURFACE` — TESTED_UNCHANGED (parity + server suites green).
- The merge itself + ONE bounce + Hermes MCP reload remain, and need the owner to run or permit them.
