---
change_id: CONSOLIDATION-MIGRATION-PHASE4-EVIDENCE-INTAKE
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none beyond ADR-0020 — three more operations behind the existing DOMAIN_OPERATION door, and a DOMAIN_OPERATION input may now select a LIST of dotted paths. Branch `migration/ecommerce-consolidation`, not merged, live fleet untouched."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 4: EvidencePacket integration

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 4: replace obsolete Polymath synthesis dependencies with current evidence contracts; preserve EvidencePacket,
provenance, CA4, utility roles, Corpus Explore and graph / wildcard lineage; adapt domain boundaries instead of deleting useful reasoning. Gate:
existing ecommerce understanding logic consumes current Polymath evidence and produces valid downstream structures. `MIGRATION_POLICY.md` INV-3, INV-6.
Decision `docs/migration/AUTO_DECISIONS.md` M-008.

## Changes
- `adapters/ecommerce/binding.py` — three operations, each a WRAP of existing engine code:
  - `knowledge.corpus_evidence`: the adapter runtime's evidence-boundary rows (from `B_retrieve` / `B_graph`-style steps) are rebuilt as packet
    evidence items and mapped by the engine's OWN `corpus_polymath.rows_from_packet`, so a row keeps its text, utility role, CA4 grade, `c4_valid`,
    origin, packet query ids, excerpt flags and the `can_establish / cannot_establish` authority hints. No HTTP from domain code — the runtime already
    retrieved. Rows without chunk id, text or corpus (graph facts) are COUNTED in `skipped`, never dropped silently; none usable = typed gap.
    ONE id space: the row id is the runtime's evidence id (the standalone `polymath:chunk:` prefix is dropped at this boundary).
  - `understanding.lenses`: `executors.lens_gate` over the seed signal + those rows.
  - `understanding.validate_primitives`: the lineage law (interpretation objects schema-valid; every `evidence_ref` exists, is CLASSIFIED and is not
    IRRELEVANT). Invalid is an OUTPUT so a `BRANCH` can return the run to reasoning.
- `adapters/ecommerce/python/lived_world.py` + `controller.py` — the primitives check that was inlined in `controller.cmd_submit` is now ONE function,
  `lived_world.validate_primitives`, called by both the controller and the binding (behaviour unchanged; the engine suite proves it).
- `shared/polymath_shared/adapter/manifest.py` + `workers/workers/adapter_step_worker.py` — a `DOMAIN_OPERATION` input may be a dotted path OR a
  non-empty list of dotted paths (one operation can take several knowledge steps' rows).
- Tests: `tests/determinism/test_adapter_ecommerce_knowledge_intake.py` (6), fixture manifest `fixture.knowledge_intake.json`, +2 manifest cases in
  `test_adapter_domain_operation.py` (now 25).
- NOT changed: `corpus_polymath.py`'s HTTP client (stays for standalone use; nothing in governed mode calls it), the engine's two schema byte
  copies (M-008: their sha / byte-equality pins now run against THIS repo on every engine-suite run, so drift is caught in one checkout).

## Proof
- GATE — `test_engine_understanding_consumes_current_polymath_evidence_through_the_runtime`: the knowledge executors return the AUTHORITATIVE
  `contracts/evidence/v1/evidence_packet.example.json` mapped by the runtime's own `evidence_boundary.rows_from_packet`; the run goes
  `retrieve, graph, intake, lenses, interpret, lineage, route, interpret, lineage, route, compile` through `service.advance` with the real
  `exec_domain`. The agent's first interpretation cites an UNCLASSIFIED row → the engine's lineage law fails it → the `BRANCH` returns it to
  reasoning → the classified resubmission passes. The id the agent was SHOWN in `context.evidence_refs` is the id the engine's law checked.
- Field-preservation pin: text, doc id, utility role, CA4 grade, `c4_valid`, origin, `text_truncated`, `text_chars` survive the mapping row by row.
- Engine suite after the extraction: 609 / 609 + `doctor` (via `test_ecommerce_engine_import.py`). New + Phase 3 tests 31; neutrality, purity,
  contract suites green. All database-free, `POLYMATH_PG_DSN` unset. Guards 0 / 0 / 0 / READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN` on a contract EXAMPLE packet. NOT proven on a live packet (Phase 11-E).

## Rejected claims
- "Polymath synthesis dependencies are removed from the engine." In governed mode nothing reaches them; the standalone corpus client and its query
  compiler still exist in the import and are retired only after parity (Phase 12).
- "Defect D2 is fixed." The adapter still sends hypothesis STATEMENTS to `/chat/evidence` at `F_retrieve`; the engine's field-anchored corpus
  questions (`lived_world.py:618`) are the fix and belong to Phase 5.
- "Graph facts feed the engine." They are counted and skipped: a fact row has no text to cite. Carrying attested facts is an open point.

## Open contract gaps
- `ADAPTER_RUNTIME` — UPDATED (manifest validation accepts list-valued `config.inputs`; no schema change: `config` is a free object).
- `EVIDENCE_PACKET` / evidence boundary — TESTED_UNCHANGED (the example packet and `rows_from_packet` are read, not modified).
- `MCP_SURFACE` — NOT_AFFECTED.
- Database-backed adapter suites — DEFERRED to the merge window (unchanged from Phase 3).
