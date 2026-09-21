---
change_id: FINISH-LINE-ITEM-2D-CORPUS-SCOPED-ATOM-SEARCH
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "`search_atoms` / `count_atoms` REQUIRE a corpus scope; every caller passes one; `activate_corpus` gains a cross-corpus tripwire. `shared/` + `orchestrator/` change on branch `item2/corpus-scoped-atoms` only — NOT merged; merging it needs a fleet bounce."
last_reviewed: 2026-09-20
---

# Finish-line Item 2D — atom search is corpus-scoped (the gate for any second corpus)

## Contract
Finish-line Item 2, sub-item D: `search_atoms` was unscoped, so with a second corpus Corpus Explore could activate concepts from the WRONG corpus. `docs/migration/EXECUTION_PLAN.md` Phase 10: "Fix / prove
corpus isolation first." `docs/migration/AUTO_DECISIONS.md` M-005: no second corpus before this is merged. Implemented earlier in this session and parked uncommitted; committed now so it cannot be lost and is
merge-ready. Behaviour with ONE corpus is unchanged.

## Changes
- `shared/polymath_shared/document_profile/profile_atom_projection.py` — `corpus_scope(corpus_ids)`; `search_atoms(..., *, corpus_ids)` and `count_atoms(..., *, corpus_ids, exact=False)` take a REQUIRED
  keyword scope and add a `corpus_id` MatchAny filter; an empty scope returns nothing (fail closed) instead of searching everything.
- `shared/polymath_shared/corpus_activation.py` — tripwire: an atom whose `corpus_id` is outside the requested scope is dropped and counted in `diag["cross_corpus_dropped"]` (the key appears only when
  non-zero, so the existing exact-dict pin stays valid).
- Callers: `orchestrator/orchestrator/api/ui.py` (scout, `_fetch`, atom universe), `orchestrator/orchestrator/api/chat_retrieval.py` (×3), `eval/corpus_explorer/ce8_substrate_probe.py`.
- Tests: `tests/determinism/test_profile_atom_corpus_scope.py` (in-memory Qdrant, adversarial two-corpus proof), `tests/contracts/test_search_atoms_callers_scoped.py` (AST pins: every call site passes `corpus_ids`).

## Proof
- 10 new tests pass; they were RED without the fix (recorded when the change was made). Database-free, no network (Qdrant `:memory:`).
- Executed path: the determinism test imports `polymath_shared` from THIS worktree (conftest puts `<root>/shared` first); the caller pins are AST reads of this worktree's files. The `orchestrator` call sites
  are therefore STATICALLY_VERIFIED here, not executed — their execution proof is the live path after merge + bounce.
- Guards 0 / 0 / 0 / READY in this worktree.
- Proof level: `UNIT_PROVEN` (`shared/`) + `STATICALLY_VERIFIED` (`orchestrator/` callers). NOT `MERGED`, NOT `LIVE_PATH_PROVEN`.

## Rejected claims
- "Corpus isolation is proven live." Only one corpus (`cinema`) exists; the two-corpus behaviour is proven in memory.

## Open contract gaps
- Retrieval / Corpus Explore contracts: TESTED_UNCHANGED for a single corpus (existing activation pins untouched and green); the live two-corpus check belongs to Phase 10.
- Merge order: after `migration/ecommerce-consolidation`; needs ONE bounce (`shared/` + `orchestrator/`).
