---
change_id: r3b-grounded-answer
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (answer path completes the R3b gate on the existing boundaries)
---

# R3b: grounded answer generation + /chat

## Contract

Implement POST /chat end to end: user query → R3a EvidenceBundle →
answer synthesis → claim/evidence validation → final answer +
citations. Core invariant: no factual assertion survives into the
final answer unless supported by one or more concrete EvidenceBundle
items. R3b decides prose; R3a remains the sole grounding/evidence
assembly boundary.

Acceptance (all required):
- /chat consumes the R3a EvidenceBundle boundary;
- every factual claim in the returned answer maps to ≥1 bundle item;
- every citation resolves to a real bundle item and retains the
  underlying source locator;
- answer generation cannot cite evidence outside its input bundle;
- evidence-only bundle items may inform prose but do not become
  unsupported factual claims;
- conflicting evidence is represented as conflict/uncertainty, never
  silently arbitrated;
- scoped/conditional evidence remains scoped/conditional in the answer;
- attributed/speculative/hypothetical facts keep their epistemic
  qualification;
- empty or insufficient evidence produces an explicit grounded
  abstention;
- malformed model output fails closed or is repaired deterministically;
- citation ordering is deterministic;
- identical synthetic model output + identical bundle produces
  identical validated response;
- tests cover direct answer, multi-source, conflict, scope,
  evidence-only input, unsupported generated claim, fake citation,
  insufficient evidence, malformed model output;
- one live E2E: query → /evidence → synthesis → /chat → cited
  grounded answer.

## Owner and public contract

- Owner: orchestrator serves POST /chat; shared owns the deterministic
  synthesis/validation/rendering policy.
- Public contract: `contracts/answer/v1/chat_response.schema.json`
  (new wire payload). Reverse dependents: none yet (M1 MCP later).

## Design decisions (admitted)

- The model is NOT trusted to obey grounding by prompting alone: it
  emits a structured intermediate (`claims` with `support` bundle item
  ids); a deterministic validator then decides what may render.
- v1 synthesis is a deterministic template proposer (one claim per
  bundle claim item, text = claim_candidate). The validator treats
  every proposer as untrusted, so an LLM proposer can replace it later
  without changing the trust boundary.
- Bundle item ids are derived content-hashes of R3a items
  (`bitem_<sha256[:16]>`) — no R3a contract change needed; the R3a
  bundle ordering is already deterministic.
- Grounding check (deterministic): every meaningful token of a claim
  text must appear in the union of its support items' claim surfaces —
  the "founded in 2019" fabrication class is rejected, fail-closed.
- Conflict: claim items sharing the same entity pair with different
  predicates are marked `conflicts_with` on both sides; the renderer
  keeps both and states the conflict. No arbitration.
- Epistemic rendering: attributed → "According to <source>,";
  speculative → "It is possible that"; hypothetical → "Hypothetically";
  conditional → "Under the stated condition". Scope stays visible in
  `claims[].epistemics`.
- Retrieval is NOT re-implemented: the /chat endpoint reuses the R3a
  lane fetchers and resolvers; the synthesizer receives only the
  bundle (no direct Postgres/Neo4j/Qdrant access).
- No Stage-2 canonicalization (C1), no reranking (R2), no extraction
  change, no E1.

## Inputs, outputs, persistence, failure modes

- Inputs: query + R3a EvidenceBundle.
- Outputs: `{answer, citations, claims, meta}` per
  `contracts/answer/v1/chat_response.schema.json`.
- Persistence: none. Pure read path.
- Failure modes: R3a assembly errors → 502 (unchanged); unsupported/
  malformed/fake-cited claims → status `unsupported`, excluded from
  prose, reported in `claims` (fail-closed, never silent); empty
  bundle or zero supported claims → explicit grounded abstention.

## Dependency edges

- orchestrator → shared (existing edge). No dependency map change.
- New files: `contracts/answer/v1/chat_response.schema.json`,
  `shared/polymath_shared/answer_synthesis.py`, rewritten
  `orchestrator/orchestrator/api/chat.py`, three test files.
- Reverse dependents: none yet.

## Verifier and rollback boundary

- Verifier: unit/contract/integration tests, `make guards`, live E2E.
- Rollback boundary: restore the /chat stub, delete the new files and
  TREE entries. R3a files untouched (no evidence-semantics change).

## Changes

- `contracts/answer/v1/chat_response.schema.json` (new).
- `shared/polymath_shared/answer_synthesis.py` (new): deterministic
  propose → validate → render; template proposer v1; untrusted-input
  validator (fake citations, fabrication tokens, malformed output,
  evidence-only support all fail closed); deterministic conflict
  marking; epistemic-scoped rendering; explicit abstention.
- `orchestrator/orchestrator/api/chat.py` (rewritten stub): real POST
  /chat reusing the R3a fetchers/resolvers; 502 stays loud.
- Tests: `tests/determinism/test_answer_synthesis.py` (13),
  `tests/contracts/test_chat_response_contract.py` (4),
  `tests/integration/test_chat_e2e.py` (2, live stores).
- Governance: refactor entry 0003, architecture changelog entry, TREE
  registration, RAG_E2E_CHECKLIST R3b → COMPLETE.

Dependency edges: orchestrator → shared (existing edge); dependency
map unchanged. R3a files untouched (no evidence-semantics change).
No extraction change, no migration, no frozen corpus touched.

## Proof

- Unit/contract: 17 new tests green (108 unit total, 19 skipped).
- Integration: 16 passed, 2 skipped — includes live query →
  /evidence → synthesis → /chat → cited grounded answer (conflict
  represented, both founders shown, citations resolve to real bundle
  item ids with locators) and explicit abstention on insufficient
  evidence.
- `make guards` green (preflight, repo guard, wiki worm).
- Contract schema validated by jsonschema in tests.

## Rejected claims

- No retrieval re-implementation in the synthesizer.
- No invented citations (only bundle item ids can be cited).
- No consensus-merging of conflicts.
- No C1/C2, R2, extraction, or E1 work.

## Open contract gaps

- LLM-based prose synthesis is a future proposer swap; the validator
  and renderer are the frozen trust boundary.
