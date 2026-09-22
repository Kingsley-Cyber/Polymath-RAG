---
change_id: RESTORATION-SLICE-4-TRAIL-CORRECTNESS
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "none in this repository. The change lives in the TRAIL repository: worktree ~/trail-signal-os-worktrees/R1-semantic-restoration, branch codex/r1-semantic-restoration off Trail origin/main de64d84, as an UNCOMMITTED working tree (Trail's agent-control guard refuses a commit without an owner-authorized task) plus a checksummed patch. ADR-069 is drafted as Proposed. governance/trail in this repository is untouched and NOT re-pinned."
last_reviewed: 2026-09-21
---

# Restoration Slice 4 — Trail contract and mapping correctness (reference §11) — implemented and proven in Trail's repo; WAITING for the owner

## Contract
Owner build reference §11, exit §11.7 (1–6) proven in Trail's own repo under Trail's own gate, ADR DRAFTED → then STOP for the owner's ADR acceptance; re-pin only after acceptance. Gate G2 of `CONTINUATION.md`: a clean worktree off Trail `origin/main` (never `~/trail-signal-os` local main), Trail's agent-control gate, an ADR only the owner accepts. `governance/trail/{src,config,data}` is byte-pinned and was not touched.

## Changes
(all in Trail, 25 files: 7 under `src/trail_signal/contexts`, 15 regenerated `schemas/generated/v2/*.json`, 1 new test, ADR-069 + its index row)
- STATED KNOWLEDGE SUPPORT: `ResearchHypothesisViewV1.knowledge_support_count` (optional; absent = a pre-ADR caller = 0 as before) → `HypothesisView` (was forced to 0).
- FIELD-AWARE MAPPING, LEXICAL KEPT: six optional `candidate_*` fields on `ResearchHypothesisViewV1` (FLAT on the registered model — a new contract class would need a policy / registry entry only the owner can authorize) → domain `SemanticCandidate`; `structured_strength` compares field to field (exact friction-family / territory id decisive; activity / task / context by shared tokens; predicates only beside another agreement; a NICHE SEED counts only when its activity, task or context also agrees — found by the test: a seed sharing only the family, "Neighborhood walking", outranked the primitive). Structured decides only when candidates are supplied AND a record agrees; otherwise the lexical ranking, unchanged. The coordinate records its path.
- COORDINATE MEANING ON THE WIRE: `ResearchPriorV1` += `label, section, match_strength, mapping_path`; `ResearchTerritoryV1` += `territory_name, mapping_path`.
- NO GUESSED GAP OWNER: `_gaps` refuses `GAP_HYPOTHESIS_LINK_MISSING` / `GAP_HYPOTHESIS_UNKNOWN`; one live hypothesis links unambiguously (admission's rule).
- HYPOTHESIS-RELATIVE RELATION: `ReceiptObservation.hypothesis_relations[{hypothesis_id, relation: SUPPORTS | CONTRADICTS | NEUTRAL}]` (optional) → kept on the admitted record for LINKED hypotheses; `polarity_for(hypothesis_id)`; judgement and qualification count through it; the scoring ENGINE (LAW 1) is not edited — the service resolves each hypothesis's inputs and leaves a NEUTRAL observation out; a record without relations serialises exactly as before.
- ADR `docs/adr/069_research_semantic_restoration.md` — Status **Proposed**, "NOT ACCEPTED", indexed.

## Proof
EXECUTED in the Trail worktree with ITS OWN interpreter (`.venv` created there; a `.pth` puts the worktree's `src` first — the shared A41 environment resolves `trail_signal` to A41, the same trap as Polymath's): `tests/integration/research/test_research_semantic_restoration.py` 6 / 6 through `ResearchOperationService.operate` over the real compiled registry (one test per §11.7 point; run-5's H1 verbatim: lexical finds none of `access_latency / occupied_hand / small_parts`, structured leads with the primitive itself); research contracts + BYTE-FOR-BYTE replays + store + MCP e2e: 27 / 27 (32 with the wider `-k research|evidence|scoring…` selection); `scripts/contracts/generate.py --check`: schemas checked. Trail governance validator: BEFORE any edit `PASS (0)`; AFTER: 0 code-law diagnostics (two real ones found and fixed on the way: `getattr` is forbidden in non-adapter source; an unregistered public model) and 6 `RUN_*` admission diagnostics — files changed outside any admitted slice's owned paths and the ADR index authority hash: exactly what only an accepted ADR + an owner-authorized slice resolve. `agentctl guard`: REFUSES a commit (`PROTECTED_PATH`, `UNAUTHORIZED_NEW_FILE`, `V2_OWNERSHIP`) — a deliberate gate, NOT bypassed (`AGENT_CONTROL_BYPASS` not used). Proof level: IMPLEMENTED + UNIT / INTEGRATION EXECUTED in Trail's repo; not committed, not merged, not pinned.

## Rejected claims
- "Trail maps semantics correctly" on the strength of a Polymath-side test: no Polymath test touches this; the proof is Trail's.
- "Slice 4 is done." It is implemented and proven; it is in force only after the owner accepts ADR-069, the Trail slices are admitted, and Polymath re-pins.
- "The registry data was repaired." It was not touched (reference §11.6: measure first).

## Open contract gaps
- OWNER GATE G-adr: accept / reject Trail ADR-069. The exact block is in `docs/migration/CONTINUATION.md`.
- AFTER ACCEPTANCE (not started, by design): (1) Trail: agentctl task + governance slice (ADR, graph node) + production slice, VERIFIED lockstep, merge to Trail main. (2) Polymath: re-pin `governance/trail/` (`PROVENANCE.json` + ADR-0021 addendum); `_payload_for` sends `knowledge_support_count` and the `candidate_*` fields from `semantic_view` (a closed projection beside `trail_projection`); the receipt contract's FOUR copies gain `hypothesis_relations` (contracts/adapter/v1, the engine's pinned copy, Trail's model — done here —, the deployed skill) plus `adapter_receipt.py` and the submit-time rules; `admission` contract allows the relation; the recorded Trail envelopes under `tests/fixtures/trail_recorded_envelopes` are re-recorded. `semantic_view` already reads `label`, `section`, `territory_name`, so the dossier and `bind_template({product_territory})` pick the names up with no further change.
- Artifact safety: the working tree in the Trail worktree is the source; a copy of the full diff is at `~/PolymathRuntime/handoff/trail-adr-069/trail_adr_069.patch` (sha256 `c9d8264ad1ae837cb780cbaa7a177d5a3f6ddb7973dc0c9ecc0f54b32e6766cd`, 782 lines, reverses cleanly against the worktree) with the validator output beside it.
