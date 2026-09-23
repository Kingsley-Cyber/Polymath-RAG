---
change_id: DOCUMENT-RAG-E4-WILDCARD-ATOM-FRONTIER-RECEIPT
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "orchestrator code on branch fix/wildcard-atom-frontier-receipt (NOT merged, NOT live). The WILDCARD atom frontier's outcome (atoms, maps, parents added, error) is written into `meta.wildcard.atom_frontier` instead of being swallowed. No ranking or selection change."
last_reviewed: 2026-09-23
---

# E4: the WILDCARD atom frontier is receipted, never silent

## Contract
Plan of record `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md` §9 S0 (E4); owner kickoff 2026-09-23: "E4 (receipt the WILDCARD
atom-frontier failures)". ENRICHMENT-SURFACES-AUDIT §10 found the frontier inside a bare `except Exception: pass`
(`chat_retrieval.py:919`), with no receipt key. A failure left no trace, and a success could not be measured either.

## Changes
- `orchestrator/orchestrator/api/chat_retrieval.py` `_retrieve_wildcard`:
  - the sweep records `{"atoms", "maps", "parents_added", "error"}` for the atom frontier;
  - the WILDCARD receipt carries it as `atom_frontier`: set when the sweep finishes; None when the sweep timed out or never
    started;
  - the frontier stays optional and fail-open, and its exception class is recorded.
- `tests/determinism/test_chat_modes.py`, 2 tests added (none edited):
  - `test_wildcard_atom_frontier_failure_is_receipted_not_swallowed`: `search_atoms` raises, and the receipt names
    `RuntimeError`;
  - `test_wildcard_atom_frontier_counts_are_receipted`: 2 atoms and 2 maps produce counts, and at least 1 parent is added.

## Proof
- **Red first:** both new tests failed on `f74871d` with `KeyError: 'atom_frontier'`.
- **Import origin:** `orchestrator` → `pmv4-e4/orchestrator/orchestrator/__init__.py` (worktree PYTHONPATH recipe).
- **test_chat_modes** (`-k "not test_live_"`, no fleet DB): 28 passed, 1 failed. The failure is the known pre-existing
  `test_wildcard_sweep_overlaps_the_core…` timing assertion, which fails identically on production. The worktree run is slow
  (≈ 2 min) because it has no `.env`.
- Proof level: UNIT_PROVEN. After merge + bounce, a live WILDCARD turn's receipt must show `atom_frontier`.

## Rejected claims
- "The atom frontier works in the test harness": it never did. The harness fakes Qdrant, so the frontier always failed
  silently there. The new failure test makes that visible, and the counts test uses real call shapes.

## Open contract gaps
- The WILDCARD receipt (RETRIEVAL_RECEIPT family): UPDATED (an additive key; no consumer reads it yet).
- `scripts/contract_impact.py --range f74871d..HEAD`: "CONTRACT IMPACT: none" (chat_retrieval.py maps to no architecture contract): NOT_AFFECTED.
- BLOCKED: merge + bounce, on the owner's word.
