---
change_id: CONSOLIDATION-MIGRATION-PHASE7-REGISTRY-STATE
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — an environment hook in the imported engine's registry loader (unused by default), a registry-source line in one operation's output, and contract pins. No runtime, contract, manifest or Trail change. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 7: one registry — measured, pinned, and handed to the owner

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 7: ensure there is one authoritative registry; Trail owns admission / judgement / qualification / score; legacy engine logic may remain only as explicitly
non-authoritative. `MIGRATION_POLICY.md` INV-3, INV-5 (embedding changes the deployment boundary only) and the standing rule "never tune a registry, gate, threshold or freshness window to pass".
Decision `AUTO_DECISIONS.md` M-014.

## Changes
- `adapters/ecommerce/python/registry.py` — `SRC` honours `OPPORTUNITY_RESEARCH_REGISTRY_SRC` (unset by default: standalone behaviour unchanged). It is the switch the governed binding will use once the
  owner decides the drifted rows.
- `adapters/ecommerce/binding.py` — `population.nominate` output states its registry source, build id, seed and friction-family counts; the binding explicitly does NOT redirect the source today.
- `tests/contracts/test_registry_single_authority_state.py` (3) — pins the measured state.

## Proof
- Row-level diff of the nine shared tables (`governance/trail/data` vs `adapters/ecommerce/registry/trailsignal`): identical headers; the engine mirror is a STRICT SUPERSET; drift = 10 friction
  families, 6 niche candidates, 6 seeds; nothing TrailSignal has is missing from the mirror.
- The redirect was TRIED: with the engine's compiler pointed at TrailSignal's byte-pinned tables it returns 236 errors (`seed-0613: unknown friction_family 'tool_access'` …) and no snapshot. 236 of
  TrailSignal's own seed rows reference friction families its `friction_library.csv` does not define; the mirror's 10 extra rows are exactly those definitions (the engine's README called them an
  upstream patch). TrailSignal's own compiler tolerates the gap; the engine's fails closed.
- Pins: strict-superset + exact drift counts; "every family TrailSignal's seeds miss is one the mirror defines"; TrailSignal's tables alone fail the engine compiler while the mirror passes (out of process).
- Engine suite 609 / 609; population, e2e, dossier and provenance tests green; `PROVENANCE.json` untouched. Guards 0 / 0 / 0 / READY.

## Rejected claims
- "There is one registry." There is ONE GOVERNANCE registry — TrailSignal's, used for every admission, judgement, qualification and score. Population PRIORS in governed mode still come from the engine's
  superset mirror, and the operation's output says so.
- "The drift is noise to delete." The friction-family part of it repairs a referential gap in TrailSignal's own data.

## Open contract gaps
- OWNER DECISION (not made here — it changes what the governance registry can project): upstream the 22 rows into TrailSignal's registry (re-pin `PROVENANCE.json`; the mirror is then deleted and the binding
  sets `OPPORTUNITY_RESEARCH_REGISTRY_SRC`), or drop them from the engine (236 seeds then cannot be nominated from TrailSignal's data). Relaxing the engine's compiler check is NOT an option.
- No architecture contract is affected: NOT_AFFECTED.
