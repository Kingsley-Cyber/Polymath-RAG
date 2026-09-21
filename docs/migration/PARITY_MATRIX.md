# Migration Parity Matrix

> Agent-owned. Evidence levels: READ · STATICALLY_VERIFIED · UNIT_EXECUTED · INTEGRATION_EXECUTED · REAL_INPUT_EXECUTED ·
> HISTORICAL_ARTIFACT_ONLY · STUBBED. "Historical" = run `calib_books_01` (2026-09-04) unless noted. Migrated path: **Phase 2 (`072f1cc`)** — every AutoResearch capability below is IMPORTED at `adapters/ecommerce/` and its own suite passes there (609 / 609, fixture-driven). A row's "Migrated path" stays "—" until that capability is BOUND to the adapter runtime through `DOMAIN_OPERATION` (ADR-0020, Phase 3 `076eb6b`).
> Parity is structural (HM §6: invariants + the nine canaries), never exact-output matching. Baseline caveat: the historical run FAILS canary 2.

| Capability | Historical AutoResearch | Current governed path | Migrated path | Evidence level | Status | Notes |
|---|---|---|---|---|---|---|
| Niche understanding | prompt, free-text `signal` | input validation only (`A_understand`) | — | HISTORICAL_ARTIFACT_ONLY / READ | NOT STARTED | output unvalidated in the original |
| Population discovery | 62 leads over 5 lanes; communities outside the seed | absent | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | LOST on the governed path |
| VOI ranking | `rank_leads` | absent | — | READ | NOT STARTED | |
| Evidence cards | 15 clusters, anchor / thin | absent (Trail owns independence) | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | advisory only after migration |
| Lived situations | 6 field-anchored (novel run) | absent | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | |
| Bridge validation | `bridge.validate_bridge / hop_refs` | schema + citation check only | `DOMAIN_OPERATION` `ecommerce` / `hypotheses.validate_bridge` (`adapters/ecommerce/binding.py`) | INTEGRATION_EXECUTED (fixture manifest through `service.advance`, in-memory store) | BOUND — not yet in a product manifest | engine-shaped hypotheses; mapping onto `HypothesisStateV1` is Phase 5 |
| Portfolio validation | `validate_portfolio`, anchors | absent | same operation (`portfolio_errors`); `validate_hypothesis_anchors` not yet bound | INTEGRATION_EXECUTED | BOUND (portfolio) · NOT STARTED (anchors) | the portfolio law sent a fixture run back to reasoning |
| Hypothesis generation | 5 (3 supported / 2 rejected); 4 all rejected (novel) | 4 agent hypotheses, ledger + transitions | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED (R2a, to `L_judge`) | NOT STARTED | two lifecycles today |
| Semantic review | 4 verdicts per run (fresh subagent) | Trail judge is the authority | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | advisory after migration |
| Gap compilation | 27 gaps / 189 queries | Trail `gaps.compile` (generic templates) | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | split WHAT / HOW |
| Channel-specific research | Reddit only executed; 6 other channels CODE | improvised by the agent in R2a (15 queries) | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | |
| Field observation capture | 146 observations, 78 field records | 15 observations submitted in 3 receipts | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | |
| Evidence provenance | 0 / 146 carry harvest dates | harvest dates REQUIRED by the receipt builder | — | STATICALLY_VERIFIED · REAL_INPUT_EXECUTED | NOT STARTED | capture paths must stamp dates |
| Product ideation | prompt + `validate_concepts` | `N_jobs` physical jobs | — | HISTORICAL_ARTIFACT_ONLY · STUBBED | NOT STARTED | governed side FIX only |
| Multiple product concepts | 5 | one free-form `product_opportunity` | — | HISTORICAL_ARTIFACT_ONLY · READ | NOT STARTED | LOST |
| Product variations | 2 per concept | none | — | HISTORICAL_ARTIFACT_ONLY · READ | NOT STARTED | LOST |
| Existing-product research | never executed (channel commands only) | `P_reality` FIX only | — | READ · STUBBED | NOT STARTED | new work in both systems |
| Supplier planning | `sourcing_plan_compiler` per concept | `S_supply` built from the wrong directive (M1-07) | — | HISTORICAL_ARTIFACT_ONLY · UNIT_EXECUTED (defect reproduced, STUBBED Trail) | NOT STARTED | |
| Alibaba | 96 candidates → 8 leads | never run | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | supplier name hard-coded `unresolved` |
| CJ | 39 candidates → 0 leads | never run | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | price empty, MOQ = policy constant |
| Price parsing | `_parse_price` (59 rows parsed) | reused by `adapter_receipt._supplier_items` | — | HISTORICAL_ARTIFACT_ONLY · UNIT_EXECUTED | NOT STARTED | Trail discards `metric_if_present` |
| MOQ parsing | `_parse_moq` | as above | — | HISTORICAL_ARTIFACT_ONLY · UNIT_EXECUTED | NOT STARTED | |
| Lead assembly | 8 leads (mechanism × supplier join) | none | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | join harvested, score left behind |
| Trail admission | n/a (own `verifiers.py`) | 3 runs: 8 admitted / 7 `STALE_BEYOND_POLICY` | — | REAL_INPUT_EXECUTED | KEEP | |
| Trail judgement | n/a | 2 runs; third died (D1); M1-01 / 02 / 03 reproduced | — | REAL_INPUT_EXECUTED · UNIT_EXECUTED | KEEP, defects open | |
| Qualification | own `satisfaction` | never on real input | — | STUBBED | KEEP | 4 of 7 gates never evaluated |
| Score / refusal | own `evidence_score` | never on real input | — | STUBBED | KEEP | |
| ReportModel | `report.build_model` | `build_model_from_governed` | — | UNIT_EXECUTED · REAL_INPUT_EXECUTED (gap dossier) | NOT STARTED | shows 0 observations on a terminal gap (D5) |
| HTML rendering | no HTML exists for the qualified run | R2a dossier rendered | — | REAL_INPUT_EXECUTED | NOT STARTED | |
| Hermes deployment | deployed copy v2.3.0, parity true | n/a | — | STATICALLY_VERIFIED | NOT STARTED | reason for the copy unknown |
| Ecommerce corpus isolation | single-corpus era | `search_atoms` unscoped; fix parked uncommitted (Item 2D, 10 tests green in its worktree) | — | UNIT_EXECUTED (worktree) | PARKED | required before ANY second corpus |
