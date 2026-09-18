---
title: "WORK LOG — agent-safety stack (1/2): semantic contract map + deterministic impact checker"
change_id: AGENT-SAFETY-IMPACT-TOOLING
date: 2026-09-18
owner: governance
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Adds the SEMANTIC contract-dependency layer (architecture/contract-dependencies.yaml) + a deterministic no-LLM impact checker (scripts/contract_impact.py) so agents compute change blast-radius from disk instead of chat memory. Complements the STRUCTURAL architecture/dependencies.json (layer/import rules) and graft (symbol-level callers, $0). Dev/CI only — no runtime dependency. Automation wiring (hooks/CI/AGENTS) is slice 2/2."
---

## Contract
Install a lightweight, removable, LLM-free contract-impact backbone: (1) a small machine-readable
semantic map of the Librarian/RAG architecture contracts; (2) a deterministic checker that maps a
git diff to the changed contracts and their transitive downstream consumers, so no impacted
contract can silently disappear. Reuse graft (symbol blast-radius) and ruff (static) — do not
install CodeGraph or a second graph. Acceptance: the checker computes the correct blast radius for
the real Librarian range and the map has no dangling edges.

## Changes
- New `architecture/contract-dependencies.yaml` — 19 contracts (SURFACE_REGISTRY, PROFILE_COMPILER,
  PROFILE_PROJECTION, PROFILE_ATOM, PROFILE_SCOUT_INPUT/FUSION/OUTPUT/WIRING, QUERY_INTENT/PLANNER,
  SUBQUERY_PROVENANCE, CANDIDATE_ENGINE, RETRIEVAL_RECEIPT, RESOLUTION_STATE, PROFILE_YIELD_RECEIPT,
  PROJECTION_LIFECYCLE, QDRANT/NEO4J_PROJECTION, ACCEPTANCE), each with owner/spec/paths/depends_on/
  consumed_by/tests/migration/status (live | pending | deferred).
- New `scripts/contract_impact.py` — `--staged` / `--range` / `--files`; prints CHANGED + TRANSITIVE
  IMPACT + tests-to-run + the disposition vocabulary; `--check` exits 3 if a DEFERRED contract is
  directly changed (out-of-scope guard, e.g. graph traversal / P10). No LLM; points to `graft callers`.
- New `tests/determinism/test_contract_impact.py` — 6 tests incl. the no-dangling-edges + paths-exist
  consistency guards on the real map.
- Scaffold TREE + scripts/README + register 11.290.

## Proof
`pytest tests/determinism/test_contract_impact.py` → 6 passed (closure, prefix-not-substring path
match, unmapped-file no-impact, tests union, no-dangling-edges, paths-exist). Ran live against real
ranges: `--range 43904ed..1b21038` (P5a) → CHANGED {PROFILE_SCOUT_FUSION, PROFILE_SCOUT_OUTPUT},
transitive {WIRING, QUERY_PLANNER, SUBQUERY_PROVENANCE, CANDIDATE_ENGINE, RETRIEVAL_RECEIPT,
PROFILE_YIELD_RECEIPT, ACCEPTANCE, RESOLUTION_STATE}; `--range cf1ee4f..1b21038` (full Librarian) →
10 changed contracts + correct downstream closure. `--check` exit 0 (no deferred contract directly
changed). repo_guard / wiki_worm green.

## Rejected claims
- Install CodeGraph (rejected — graft already provides deterministic symbol-level callers/blast-radius at $0).
- Require an LLM for impact (rejected — the closure is pure graph traversal over the contract map).
- Make it a runtime dependency (rejected — dev/CI only, removable, application runs without it).
- A second architecture authority (rejected — this is the semantic complement to dependencies.json, not a replacement).

## Open contract gaps
- Automation (git hook + Makefile target + CI workflow + ruff security rules) and the AGENTS.md workflow are slice 2/2.
- `PROFILE_SCOUT_INPUT` / `PROFILE_SCOUT_WIRING` have empty/placeholder `paths` until P5b writes the normalization + ui.py wiring; fill them then.
- Disposition enforcement is currently advisory (printed); the AGENTS.md workflow makes recording them mandatory in the work-log.
