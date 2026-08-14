---
change_id: r3a-evidence-bundle
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: new wire contract (no boundary change)
---

# R3a: grounded EvidenceBundle assembly

## Contract

Assemble a deterministic evidence bundle from retrieved facts and child
evidence such that every candidate claim is traceable to fact/entity
IDs, source document, exact evidence span, provenance, epistemics,
scope, and retrieval lane. No answer claim may exist downstream unless
R3a can point to supporting evidence. R3a assembles evidence only —
it does not decide final answer prose (that is R3b).

Acceptance (all required):
- every evidence item resolves to a real source;
- every fact/reference ID resolves;
- exact evidence span is recoverable;
- no unsupported synthetic claims are introduced;
- duplicate evidence is collapsed deterministically;
- conflicting evidence can coexist;
- scoped/conditional facts keep their scope;
- missing provenance fails loudly, not silently;
- bundle ordering is deterministic for identical inputs;
- tests cover direct fact, relation, conflicting evidence, and missing
  provenance.

Owner: orchestrator serves the read endpoint; shared owns the
deterministic assembler policy. Public contract:
`contracts/answer/v1/evidence_bundle.schema.json` (new wire payload,
orchestrator output). Reverse dependent: R3b (`/chat`), pending.

Inputs: query + retrieval artifacts (`graph_facts` from the Neo4j
expansion lane, `child_evidence` from dense/lexical lanes). Outputs:
`{query, evidence_bundle, meta}` with `claim` items (one per
fact_id+evidence_id) and `evidence` items (one per retrieved chunk
without a fact). Persistence: none — pure read path. Failure modes:
unresolved fact_id, claim with zero evidence rows, missing
entity/document/chunk, empty provenance → typed `AssemblyError` →
HTTP 502 with error_code (loud, never silent omission).

## Changes

- `contracts/answer/v1/evidence_bundle.schema.json` (new).
- `shared/polymath_shared/evidence_assembly.py` (new): deterministic
  assembler with injected resolvers, same pattern as
  `retrieval.run_lanes`; typed errors.
- `orchestrator/orchestrator/api/evidence.py` (new): POST /evidence;
  reuses the /retrieve lane fetchers; 502 mapping for assembly errors.
- `orchestrator/orchestrator/main.py`: register the evidence router.
- Tests: `tests/determinism/test_evidence_assembly.py`,
  `tests/contracts/test_evidence_bundle_contract.py`,
  `tests/integration/test_evidence_bundle_e2e.py` (live stores).
- Governance: refactor entry 0002, architecture changelog entry, TREE
  registration for all new paths, RAG_E2E_CHECKLIST R3a → COMPLETE.

Dependency edges: orchestrator → shared (existing edge); dependency
map unchanged. `/retrieve` untouched. No extraction change, no
migration, no frozen corpus touched.

## Proof

- Unit/contract: 14 new tests green (91 unit total, 17 skipped).
- Integration: 14 passed, 2 skipped — includes live POST /evidence
  returning a fully traceable bundle and a loud 502
  (UnresolvedEvidenceError) for a claim without evidence.
- `make guards` green (preflight, repo guard, wiki worm).
- Contract schema validated by jsonschema in tests.

## Rejected claims

- No answer generation here (R3b).
- No synthetic claims: evidence-only items carry `claim_candidate:
  null`, enforced by the assembler and asserted in tests.
- Span granularity stays chunk-level (current `evidence.span_offsets`
  payload); finer entity/trigger offsets are a measured extraction
  change, out of R3a scope.

## Open contract gaps

- R3b consumes this contract; nothing else pending on R3a.
