---
change_id: RESTORATION-PROVENANCE-HOOK
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "Engine only: an observation's free-text context may carry `intent: <search intent id>`; population.evidence_cards reads it into field records (intent_id, gap_id) and product_reality.join into joined products (job_id). Manifest 0.5.1 (two objective sentences). No contract, schema, shared/, workers/ or Trail change. Not merged."
last_reviewed: 2026-09-21
---

# Exploration-memory preparation — provenance check of the restoration, and the ONE hook added

## Contract
Owner instruction 2026-09-21: do NOT start the Semantic Exploration Memory; verify the restoration preserves the provenance it will need; add only the smallest hook for a fact that would otherwise be permanently unrecoverable. No ExplorationIndex, novelty policy, duplicate suppression or COMPOSE controller. Branch `restoration/provenance-hooks` stacked on `restoration/evidence-route-retrieval` `36d1d17`.

## Changes
- CHECK (READ, against the code of slices 1–5): stable versioned evidence / origin refs — chunk ids are content hashes, `fev_*` ids are minted from (action, observation), lead ids are `stable_id` hashes, hypothesis ids hash (run, step, ordinal), every revision is immutable with a transition that names `cause_refs` → RECONSTRUCTIBLE. Lead / latent structure → hypothesis — `lead_ids[]` / `latent_structure_ids[]` on the ledger (Slice 1) → PRESENT. Evidence exposure — every issued step persists `context.evidence_refs`; the readable 60 rows are a pure function of those refs + stored outputs (`EB.hydrate`), and the host journal now stores rows, `allocation` and `materials` → RECONSTRUCTIBLE. Semantic input roles — `knowledge_support[].evidence_role` per cited id, `primitives.evidence_refs` per family, `bridges[].hop_refs` per hop → PRESENT. Output refs — every pass of every step is its own `adapter_steps` row with a receipt hash → PRESENT. Revision causes — transitions → PRESENT. Producer / contract version — run ref carries adapter + workflow versions, every domain output carries `_domain.binding_sha256`, the view carries `view_version`, plans carry `compiler: semantic.v1`, Trail results carry the registry snapshot → PRESENT. Gap → intent — `H_plan.intent_index` (Slice 2) and `O_plan.reality_plan` (Slice 3) → PRESENT.
- THE ONE GAP: observation → intent. A receipt's `tool_trace` counts queries per intent; an observation never says which intent found it, so gap → outcome could not be reconstructed after a run. HOOK: the step objectives of `I_research` and `P_reality` ask the harness to write `intent: <intent id>` into the observation's free-text `context` (the same convention as `concept:` / `lead:`; no contract change); `population.evidence_cards` reads it into `field_records[].intent_id` and derives `gap_id` from the id's last segment; `product_reality.join` reads it into `existing_products[].job_id` when it names a planned job. Absent stays absent — never inferred.

## Proof
EXECUTED, no database: the two extended assertions (`test_adapter_research_fidelity`, `test_adapter_product_reality`) + the scripted full run + dossier + lived-world suites 41 / 41; engine suite 609 / 609. UNIT_PROVEN + WORKTREE_INTEGRATION_PROVEN (engine). Guards 0 / 0 / 0 / READY.

## Rejected claims
- "Exploration memory has started." Nothing was built: no index, no policy, no controller.
- "Every observation will carry its intent." Only when the harness writes the tag; a missing tag is recorded as `null`, and the live rate is measurable per run (count of non-null `intent_id`).

## Open contract gaps
- ADAPTER_RUNTIME / MCP_SURFACE: NOT_AFFECTED. Deployed skill copy: engine files changed → same `deploy_ecommerce_skill.py` step as slices 2–5.
- Owed live: L15 share of admitted observations with a non-null `intent_id` on the first post-merge run.
