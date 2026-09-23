---
change_id: DOCUMENT-RAG-E7-TARGET-DERIVED-FROM
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared + orchestrator code on branch fix/compiled-query-derived-from (NOT merged, NOT live). CompiledQuery gains `derived_from`, the reference a subquery was derived from (a profile concept key, a nominated doc id, a gap claim id). `target` keeps only an information need. The subquery-provenance receipt rows gain `derived_from`. The evidence packet's `provenance.derived_from` keeps its values: it reads the new field, and legacy rows fall back to `target`."
last_reviewed: 2026-09-23
---

# E7: references leave `target` for their own field, `derived_from`

## Contract
- Plan of record `docs/wiki/plans/DOCUMENT-RAG-COMPLETION-V1.md` Part B: "Fix `target`. Stop writing doc ids into `target`;
  source references go to their own field. Check the consumers first."
- `CompiledQuery` (`shared/polymath_shared/chat_plan.py`) defines `target` as "the information need this subquery localizes
  (planner-supplied; never fabricated)".
- The owner's kickoff queue (2026-09-23): E4 → E3 → E7 → S1 → S2.
- Three writers broke that definition:
  - bridges and Corpus Explore stored the concept key in `target` (`bridge_integration.py:97`);
  - PROFILE expansion stored the nominated doc id (`ui.py:1910`);
  - resolution rounds stored the claim id (`evidence_resolution.py:125`).
- Consumers checked (READ, 2026-09-23). No frontend, MCP or script reads the subquery `target`.
  - `subquery_provenance.py:77`: the receipt rows.
  - `evidence_packet.py:97` and `:188`: `provenance.derived_from`, which read `target`.

## Changes
- `shared/polymath_shared/chat_plan.py`: `CompiledQuery.derived_from: str | None = None`. It is additive, and `asdict`
  carries it into the plan receipt (`chat_plan.queries[]`).
- `shared/polymath_shared/bridge_integration.py`: bridges and Corpus Explore set `derived_from` = the concept key (it was
  `target`). Docstrings updated.
- `orchestrator/orchestrator/api/ui.py` (`_add_profile_expansion`): `derived_from` = the nominated doc id (it was `target`).
- `shared/polymath_shared/evidence_resolution.py` (`_resolution_query`): `derived_from` = the claim id. `target` = the claim's
  `next_information_need`, the actual need, or None when absent.
- `shared/polymath_shared/subquery_provenance.py`: the receipt rows gain `derived_from`.
- `shared/polymath_shared/evidence_packet.py`:
  - `_plan_index` carries `derived_from`;
  - a row with NO `derived_from` key (a receipt written before E7) resolves through `target`, which then held the reference;
  - `provenance.derived_from` reads the new field, so the values are unchanged for all three writers.
- Tests:
  - NEW `tests/determinism/test_compiled_query_derived_from.py` (5 tests): bridge / PROFILE / resolution writers, the
    provenance rows, and the packet (a need never leaks into `derived_from`; CompiledQuery objects work too).
  - **Three existing assertions pinned the misuse this slice fixes.** Each now asserts the SAME reference on `derived_from`,
    plus that `target` holds only a need (None, or the need text). No assertion was dropped or weakened.
    - `test_bridge_integration.py::test_bridges_to_subqueries_carry_lineage`: `sq.target == "docFACS"` →
      `sq.derived_from == "docFACS"` + `sq.target is None`.
    - `test_corpus_explore.py::test_expansion_appends_corpus_explore_subquery_preserves_q0`: `target` → `derived_from`, plus
      `target is None`.
    - `test_evidence_resolution.py::test_gap_fires_targeted_resolution_query`: `target == "claim_0"` →
      `derived_from == "claim_0"` + `target == "sound design ambience"`. Its module docstring was updated to match.
  - `test_evidence_packet.py` is untouched and stays green: its legacy-style row (`target` only) proves the fallback.

## Proof
- **Red first:** all 5 new tests failed on `82c66dd` (AttributeError / TypeError: no `derived_from`; the packet returned
  None for a new-style row).
- **Directly affected suites** (the new file, test_evidence_packet, test_bridge_integration, test_corpus_explore,
  test_subquery_provenance, test_evidence_resolution): 65 passed. The worktree PYTHONPATH was verified with `find_spec`.
- **Lint:** ruff finds the same (file, code) findings on the touched files as on the base. The new test file is clean.
- **Broad run (EXECUTED):** the 35 suites (contract_impact's list, the writers' suites, and every suite that imports
  `chat_plan`), with the worktree PYTHONPATH, no `.env` and `-k "not test_live_"`.
  - Branch: 407 passed, 2 failed, 1 skipped, 9 deselected.
  - Base `82c66dd` (throwaway detached worktree, same 34 suites that exist there): 402 passed, the SAME 2 failed, 1 skipped,
    9 deselected.
  - The 2 are the known pre-existing failures (compiler-on-both-routes; handlers-wired). The +5 are the new tests.
  - Every live `:7200` caller in the list is a `test_live_*` function (deselected), and DB-backed tests fail auth, so
    nothing reached the fleet database.

## Rejected claims
- "Moving the reference changes the evidence packet": no. `provenance.derived_from` values are identical for bridges,
  Corpus Explore, PROFILE expansion, resolution and legacy rows.
- "A claim id is an information need": it is a reference. The need is the claim's `next_information_need`.
- "`annotate_subquery_provenance` must validate `derived_from` against the scout's nominations": no. The bridge compiler
  already validates concept keys upstream ("activation, not invention"), and a claim id is not a scout link. Annotation
  records the field.

## Open contract gaps
- Contract impact (`scripts/contract_impact.py --files …`, EXECUTED):
  - `QUERY_PLANNER`: UPDATED (`CompiledQuery.derived_from`, additive, default None).
  - `SUBQUERY_PROVENANCE`: UPDATED. The receipt rows gain `derived_from`; `target` holds only a need (bridge / PROFILE rows:
    None).
  - `RESOLUTION_STATE`: UPDATED. The resolution subquery's `target` = the claim's need; `derived_from` = the claim id.
  - `EVIDENCE_PACKET`: TESTED_UNCHANGED. `provenance.derived_from` values are identical for every writer and for legacy rows
    (the schema leaves it untyped).
  - `EVIDENCE_BOUNDARY_API`, `PROFILE_SCOUT_WIRING`: TESTED_UNCHANGED. The only `ui.py` change is one keyword inside
    profile expansion.
  - Transitive `ACCEPTANCE`, `ADAPTER_RUNTIME`, `CANDIDATE_ENGINE`, `MCP_SURFACE`, `PROFILE_YIELD_RECEIPT`,
    `RETRIEVAL_RECEIPT`: TESTED_UNCHANGED (the broad run above).
  - DEFERRED: `tests/integration/test_cross_domain_routing.py`. It cannot be collected under the worktree PYTHONPATH (it
    imports `orchestrator.orchestrator.*`) and is skip-gated behind `POLYMATH_INTEGRATION=1`.
- The planner still never fills `target`. Part B's later slices add `expected_contribution` / `evidence_requirement` from
  the one planning call.
- BLOCKED: merge + bounce, on the owner's word.
