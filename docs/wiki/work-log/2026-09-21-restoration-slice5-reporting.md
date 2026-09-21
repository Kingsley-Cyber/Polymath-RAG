---
change_id: RESTORATION-SLICE-5-REPORTING
owner: "@king"
date: 2026-09-21
status: complete
architecture_impact: "ADAPTER_RUNTIME: the terminal result may carry the DERIVED semantic view when the manifest's include names hypothesis_semantics (a rendering in the outcome document; the ledger stays the record, nothing reads it back). Engine: the host journal records the bounded materials an issued step carried; the governed dossier renders hypothesis state, transduction, per-concept existing products and registry coordinates from that state instead of the four-field step view. Manifest ecommerce.product_research 0.5.0 (include list only). No Trail, contract-schema or workers change. Not merged, not deployed."
last_reviewed: 2026-09-21
---

# Restoration Slice 5 — reporting and auditability (reference §13)

## Contract
Owner build reference §13 (exit = the dossier renders real hypothesis fields, a transduction section, per-concept existing products and a governance section; the journal records materials). Does not depend on Slice 4. Branch `restoration/reporting` (worktree `../pmv4-reporting`) STACKED on Slice 3 `d32c285`. No new renderer (§6): the engine's existing `report.py` / `governed_run.py`.

## Changes
- `shared/polymath_shared/adapter/service.py` `_compile_result`: include key `hypothesis_semantics` → `SV.build(..., include_absorbed=True)` over the ledger, the outputs and every stored step — the whole story, killed and merged hypotheses included.
- Manifest 0.5.0: `X_compile.include` += `hypothesis_semantics`, `primitives`, `latent_structures`, `bridges`, `priors`, `territories`, `intent_index` (audit L16 / delta D-d; Slice 3 already added `existing_products`, `concept_reality`, `reality_plan`).
- `adapters/ecommerce/python/governed_run.py`: `record_next` stores `materials` per issued step through `_materials_record` — BOUNDED (120 kB per value, 300 kB per step; a larger value is recorded by name + size), plus `evidence.allocation` (audit L15). Execution semantics and ids only.
- `adapters/ecommerce/python/report.py`: hypothesis rows come from the result's view → else the newest `hypothesis_semantics` the journal shows the agent was given → ONLY then the four-field step context, and the dossier SAYS which (`hypothesis_state_from`; an empty column is explained, never shown as a finding) — population · activity · task · context, mechanism, friction, revision, field + / −, corpus support, contradictions, open gaps, falsifiers (audit L14). `bridges` is no longer hard-coded `[]`. NEW blocks + renderers: `transduction` (transferable invariants, primitive families, latent structures, per hypothesis its DECLARED origin leads / structures — "not declared" when it declared none — and its bridge with the first-inference boundary, gaps, alternatives, falsifiers); `product_reality` (each GENERATED CONCEPT card lists its EXISTING products underneath; a contesting product is marked); `coordinates` (TrailSignal's priors / territories, "never evidence"). Authority labels on every new block; no score is computed anywhere.
- Tests: NEW `tests/determinism/test_adapter_dossier_fidelity.py` (8) on the complete scripted run + the dossier built OUT OF PROCESS through the engine's CLI.

## Proof
EXECUTED in the worktree, no database, no network: new file 8 / 8; the pre-existing dossier suite 2 / 2 untouched; DB-free adapter suites + Slices 1–3 all green; engine suite 609 / 609. Before (HISTORICAL, run 5): mechanism / population / friction columns empty, support 0, `bridges: []`, no existing-products section, materials not reconstructible. Now (fixture): every row carries `runners · running`, support ≥ 1 and a revision; every bridge renders with its inference boundary; `running belt` appears as an EXISTING product under its concept and never in the concept list; an older journal degrades in two honest steps. UNIT_PROVEN + WORKTREE_INTEGRATION_PROVEN. Guards 0 / 0 / 0 / READY.

## Rejected claims
- "The view is now persisted state." The RESULT — an outcome document — carries a rendering; no step, ledger or Trail path reads it.
- "The dossier shows hypothesis-relative support / contradiction." It shows per-hypothesis counts from TrailSignal's admission polarity as it exists today (global per observation); the relation itself is Slice 4.
- "Territory names are rendered." Trail still returns the constant `product_territory`; the name appears once Slice 4 returns it (`territory_name` is already read).

## Open contract gaps
- ADAPTER_RUNTIME: UPDATED (additive; `adapter_result.output` is an open object) — tests green. MCP_SURFACE: TESTED_UNCHANGED.
- DEPLOYED SKILL COPY: `report.py`, `governed_run.py` changed → `scripts/deploy_ecommerce_skill.py` after the merge.
- Owed live: L12 a real journal's dossier shows non-empty hypothesis columns and `hypothesis_state_from: RESULT`; L13 result size stays within the hosted response limits on a real run (the view is bounded: 400-char text, 12-item lists).
