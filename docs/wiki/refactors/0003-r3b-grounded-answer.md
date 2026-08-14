---
triggered_by: RAG E2E gate R3b
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0003: R3b grounded answer generation + /chat

R3b (second critical-path gate) turned the /chat stub into a grounded
answer path. Changes:

- `contracts/answer/v1/chat_response.schema.json` — versioned wire
  payload: answer prose, citations that reference R3a bundle item ids
  (with source documents + locators), validated claim ledger, meta.
- `shared/polymath_shared/answer_synthesis.py` — deterministic
  propose → validate → render pipeline. v1 proposer is a template
  (one claim per bundle claim item); the validator treats ALL proposer
  output as untrusted: supports must resolve to real bundle items,
  ≥1 support must be a claim item, every meaningful token of the
  claim text must appear in its supporting claim surfaces (fabrication
  class rejected), malformed output fails closed. Conflicts (same
  target/predicate, different subject; same pair, different predicate)
  are marked on both sides and never arbitrated. Epistemic scope
  (attributed/speculative/hypothetical/conditional) survives into
  prose and the ledger. Empty/insufficient evidence → explicit
  grounded abstention.
- `orchestrator/orchestrator/api/chat.py` — real POST /chat: reuses
  the R3a lane fetchers + resolvers (no retrieval re-implementation),
  assembles the bundle, then `grounded_answer`. Assembly failures stay
  loud (502).
- Tests: 13 determinism + 4 contract + 2 live E2E (cited grounded
  conflict answer; abstention on insufficient evidence).

Affected dependents verified: R3a files untouched (no evidence-semantics
change); `/retrieve` and `/evidence` unchanged; dependency map unchanged
(orchestrator → contracts + shared only). Reverse dependents of the new
contract: none yet (M1 MCP later).

Proof: 108 unit + 16 integration tests green; three guards green.
See work log `2026-08-14-r3b-grounded-answer.md`.
