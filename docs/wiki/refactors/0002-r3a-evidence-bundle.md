---
triggered_by: RAG E2E gate R3a
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0002: R3a grounded EvidenceBundle assembly

R3a (first critical-path gate) required a deterministic bridge from
retrieval artifacts to answer-grounding evidence. This refactor added:

- `contracts/answer/v1/evidence_bundle.schema.json` — versioned wire
  payload for the bundle (claims + evidence-only items, source spans,
  provenance, epistemics, applicability, retrieval lanes).
- `shared/polymath_shared/evidence_assembly.py` — deterministic
  assembler with injected resolvers (no stores; same pattern as
  `retrieval.run_lanes`). Typed `AssemblyError` subclasses make
  unresolvable references and missing provenance LOUD.
- `orchestrator/orchestrator/api/evidence.py` — POST /evidence read
  endpoint; runs the same four lanes plus graph expansion, then
  assembles; maps assembly failures to HTTP 502 with error codes.
- Tests: deterministic invariants (direct fact, relation, conflicting
  evidence, missing provenance, duplicates, scope retention,
  determinism), contract schema validation, and a live-store E2E
  (traceable bundle + loud 502 for a claim without evidence).

Affected dependents verified: `/retrieve` untouched (its trace remains
the G1/G2 contract); no extraction change, no migration, no frozen
corpus touched; `architecture/dependencies.json` unchanged (no new
owner or edge — orchestrator still depends on contracts + shared).
Reverse dependent of the new contract: R3b (`/chat`), pending.

Proof: 91 unit + 14 integration tests green; three guards green.
See work log `2026-08-14-r3a-evidence-bundle.md`.
