---
change_id: CI-SEARCH-ATOMS-PIN
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Tests + the contract map only: the search_atoms caller pin counts the SEE ALSO line search; the change-impact map lists the pin and maps chat_retrieval.py to CANDIDATE_ENGINE. No runtime change."
last_reviewed: 2026-09-24
---

# CI fix: the search_atoms caller pin counts the SEE ALSO line search

## Contract
- CI `contracts` on `c36ac730` (pushed 2026-09-24) failed one test that was green on `12ea1b87`:
  `tests/contracts/test_search_atoms_callers_scoped.py::test_the_live_callers_pass_the_request_corpus_not_a_constant`.
- The owner's standing word (2026-09-24): "i decide for all your deficiencies found to be resolved".

## Changes
- The cause: SEEALSO-HOP-V1 (11.472) added a fourth `search_atoms` call in `chat_retrieval.py`, and SEEALSO-BLEND-V1
  (11.475) replaced it with the blend's line search. The pin expects exactly three calls. Every call passes the request
  corpus (`[corpus_id]`), so the pin's rule held; only its count was stale.
- `tests/contracts/test_search_atoms_callers_scoped.py`: four calls, each `[corpus_id]`, plus a new check that the only
  call with a document filter is the blend's (`doc_ids=q_docs`: the question's own documents).
- Why the slice missed it: `chat_retrieval.py` belonged to no contract, so `contract_impact.py` never listed the pin.
  `architecture/contract-dependencies.yaml`:
  - CANDIDATE_ENGINE gains the path `orchestrator/orchestrator/api/chat_retrieval.py` (the lane callbacks the engine
    runs) and the test `tests/contracts/test_search_atoms_callers_scoped.py`;
  - PROFILE_ATOM gains the tests `test_profile_atom_corpus_scope.py` and `test_search_atoms_callers_scoped.py`.

## Proof
- `pytest tests/contracts/` (what CI's `contracts` job runs), safe recipe: 145 tests, 0 failures.
- `contract_impact.py --files orchestrator/orchestrator/api/chat_retrieval.py` now lists CANDIDATE_ENGINE and the pin.
- CI `determinism` on `c36ac730` = the same 13 pre-existing failures as `12ea1b87` (diffed by test id): no regression
  there.

## Rejected claims
- "Loosen the pin to at least three calls": an exact list is what catches an unscoped or constant-scoped new caller, so
  the count stays exact and gains the document-filter check.

## Open contract gaps
- CANDIDATE_ENGINE, PROFILE_ATOM: UPDATED (the map only: a path and tests added; no code changed). No transitive runtime
  impact.
