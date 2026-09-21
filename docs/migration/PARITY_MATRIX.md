# Migration Parity Matrix

> Agent-owned. Evidence levels: READ · STATICALLY_VERIFIED · UNIT_EXECUTED · INTEGRATION_EXECUTED · REAL_INPUT_EXECUTED ·
> HISTORICAL_ARTIFACT_ONLY · STUBBED. "Historical" = run `calib_books_01` (2026-09-04) unless noted. Migrated path: **Phase 2 (`072f1cc`)** — every AutoResearch capability below is IMPORTED at `adapters/ecommerce/` and its own suite passes there (609 / 609, fixture-driven). A row's "Migrated path" stays "—" until that capability is BOUND to the adapter runtime through `DOMAIN_OPERATION` (ADR-0020, Phase 3 `076eb6b`).
> **Composed (`92efc79`):** `config/adapters/ecommerce.product_research.json` runs every BOUND capability below in ONE scripted run through the existing runtime (stub TrailSignal, in-memory store) and a negative control — evidence level for the composition: INTEGRATION_EXECUTED; REAL_INPUT_EXECUTED: none yet.
> **Against the real TrailSignal code (`b766678`):** the same run with `POLYMATH_TRAIL_MODE=embedded` ends `completed` with a defensible rejection (field evidence admitted, fabricated review / supplier sources rejected, score refused `HARD_GATE_UNMET`). Agent, harness and sources are still scripted — REAL_INPUT_EXECUTED: none yet.
> Parity is structural (HM §6: invariants + the nine canaries), never exact-output matching. Baseline caveat: the historical run FAILS canary 2.

| Capability | Historical AutoResearch | Current governed path | Migrated path | Evidence level | Status | Notes |
|---|---|---|---|---|---|---|
| Niche understanding | prompt, free-text `signal` | input validation only (`A_understand`) | — | HISTORICAL_ARTIFACT_ONLY / READ | NOT STARTED | output unvalidated in the original |
| Knowledge intake + lenses + lineage law | `corpus_polymath.rows_from_packet`, `lens_gate`, `lineage_ref_errors` / `validate_relevance_map` | evidence-boundary rows reach the agent; no lens, no lineage law | `DOMAIN_OPERATION` `ecommerce` / `knowledge.corpus_evidence`, `understanding.lenses`, `understanding.validate_primitives` | INTEGRATION_EXECUTED (authoritative EvidencePacket example through `service.advance`, in-memory store) | BOUND — not yet in a product manifest | one id space = the runtime's evidence ids (M-008); not yet run on a live packet |
| Population discovery | 62 leads over 5 lanes; communities outside the seed | absent | `DOMAIN_OPERATION` `population.nominate` | INTEGRATION_EXECUTED (real executor; 4 lanes incl. LATENT; deterministic) | BOUND — nomination + queries; instantiation from admitted observations pending | leads feed `research.plan` |
| VOI ranking | `rank_leads` | absent | same operation (`ranked_lead_ids`, `batch`) | INTEGRATION_EXECUTED | BOUND | the engine's clock-stamping `queue` is not used |
| Evidence cards | 15 clusters, anchor / thin | absent (Trail owns independence) | `population.evidence_cards` over TrailSignal-ADMITTED observations | INTEGRATION_EXECUTED (constructed admissions) | BOUND | per SOURCE, not per person (a receipt has no author); independence groups are TrailSignal's as given |
| Lived situations | 6 field-anchored (novel run) | absent | `population.validate_situations` (+ `knowledge.corpus_questions`) | INTEGRATION_EXECUTED | BOUND — agent step not yet in a manifest | FIELD_ANCHORED needs an ANCHOR cluster; single-platform evidence cannot anchor under Trail's independence rule |
| Bridge validation | `bridge.validate_bridge / hop_refs` | schema + citation check only | `DOMAIN_OPERATION` `ecommerce` / `hypotheses.validate_bridge` (`adapters/ecommerce/binding.py`) | INTEGRATION_EXECUTED (fixture manifest through `service.advance`, in-memory store) | BOUND — not yet in a product manifest | engine-shaped hypotheses; mapping onto `HypothesisStateV1` is Phase 5 |
| Portfolio validation | `validate_portfolio`, anchors | absent | same operation (`portfolio_errors`); `validate_hypothesis_anchors` not yet bound | INTEGRATION_EXECUTED | BOUND (portfolio) · NOT STARTED (anchors) | the portfolio law sent a fixture run back to reasoning |
| Hypothesis generation | 5 (3 supported / 2 rejected); 4 all rejected (novel) | 4 agent hypotheses, ledger + transitions | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED (R2a, to `L_judge`) | NOT STARTED | two lifecycles today |
| Semantic review | 4 verdicts per run (fresh subagent) | Trail judge is the authority | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | advisory after migration |
| Gap compilation | 27 gaps / 189 queries | Trail `gaps.compile` (generic templates) | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | split WHAT / HOW |
| Channel-specific research | Reddit only executed; 6 other channels CODE | improvised by the agent in R2a (15 queries) | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | |
| Research planning (Trail WHAT / engine HOW) | `gap_compiler` + `channel_queries` (27 gaps / 189 queries) | TrailSignal generic templates only (defect D6) | `DOMAIN_OPERATION` `research.plan` enriches the `research_directive` the runtime already hands to the harness | INTEGRATION_EXECUTED (stub TrailSignal through the production client; contract-valid `HarnessActionV1`) + smoke on the real R2a directive | BOUND | Trail intents keep their slots first; overflow counted; no runtime change |
| Field observation capture | 146 observations, 78 field records | 15 observations submitted in 3 receipts | — | HISTORICAL_ARTIFACT_ONLY · REAL_INPUT_EXECUTED | NOT STARTED | |
| Evidence provenance | 0 / 146 carry harvest dates | harvest dates REQUIRED by the receipt builder | — | STATICALLY_VERIFIED · REAL_INPUT_EXECUTED | NOT STARTED | capture paths must stamp dates |
| Product ideation | prompt + `validate_concepts` | `N_jobs` physical jobs | — | HISTORICAL_ARTIFACT_ONLY · STUBBED | NOT STARTED | governed side FIX only |
| Multiple product concepts | 5 | one free-form `product_opportunity` | `products.validate_concepts` (3–6 distinct form factors) | INTEGRATION_EXECUTED | BOUND — agent step not yet in a manifest | support is DERIVED from the ledger (M-010) |
| Product variations | 2 per concept | none | same operation (≥ 2 distinct variations per concept) | INTEGRATION_EXECUTED | BOUND | variations are also sourcing search terms |
| Existing-product research | never executed (channel commands only) | `P_reality` FIX only | — | READ · STUBBED | NOT STARTED | new work in both systems |
| Supplier planning | `sourcing_plan_compiler` per concept | `S_supply` built from the wrong directive (M1-07) | `supply.plan` (one job per concept per channel + directive enrichment) | INTEGRATION_EXECUTED | BOUND | round-robin across concepts within Trail's query budget |
| Alibaba | 96 candidates → 8 leads | never run | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | supplier name hard-coded `unresolved` |
| CJ | 39 candidates → 0 leads | never run | — | HISTORICAL_ARTIFACT_ONLY | NOT STARTED | price empty, MOQ = policy constant |
| Price parsing | `_parse_price` (59 rows parsed) | reused by `adapter_receipt._supplier_items` | — | HISTORICAL_ARTIFACT_ONLY · UNIT_EXECUTED | NOT STARTED | Trail discards `metric_if_present` |
| MOQ parsing | `_parse_moq` | as above | `supply.leads` → `executors.supplier` (`_parse_price`, `_parse_moq`, marked channel defaults) | INTEGRATION_EXECUTED | BOUND | non-USD and ambiguous ranges refuse to guess |
| Lead assembly | 8 leads (mechanism × supplier join) | none | `supply.leads` → `executors.join_leads` + `interleave_leads` | INTEGRATION_EXECUTED | BOUND | NO engine score or verdict in governed mode; "unresolved" is not a supplier name |
| Trail admission | n/a (own `verifiers.py`) | 3 runs: 8 admitted / 7 `STALE_BEYOND_POLICY` | — | REAL_INPUT_EXECUTED | KEEP | |
| Trail judgement | n/a | 2 runs; third died (D1); M1-01 / 02 / 03 reproduced | — | REAL_INPUT_EXECUTED · UNIT_EXECUTED | KEEP, defects open | |
| Qualification | own `satisfaction` | never on real input | — | STUBBED | KEEP | 4 of 7 gates never evaluated |
| Score / refusal | own `evidence_score` | never on real input | — | STUBBED | KEEP | |
| ReportModel | `report.build_model` | `build_model_from_governed` | `adapters/ecommerce/python/report.py` `build_model_from_governed` — now uses the result's typed concepts + variations, supplier join, coverage, mechanisms, lived world, registry snapshot | INTEGRATION_EXECUTED (journal of a complete scripted run; also the real-TrailSignal run) | MIGRATED (host-side, M-013) | the older adapter's result still maps as before |
| HTML rendering | no HTML exists for the qualified run | R2a dossier rendered | same file, `render` + `_render_governed` + `_render_lived_world`; five authority labels on every governed block | INTEGRATION_EXECUTED | MIGRATED | no engine score in a governed dossier; a refused run reads as a refusal; owner's dossier specification still UNCONFIRMED |
| Hermes deployment | deployed copy v2.3.0, parity true | n/a | — | STATICALLY_VERIFIED | NOT STARTED | reason for the copy unknown |
| Ecommerce corpus isolation | single-corpus era | `search_atoms` unscoped; fix parked uncommitted (Item 2D, 10 tests green in its worktree) | — | UNIT_EXECUTED (worktree) | PARKED | required before ANY second corpus |

## Real-input capability coverage — 2026-09-21 (owner direction "finish core functionality"; corpus `cinema` by the owner's instruction for this run)

Five REAL runs of `ecommerce.product_research` through the HOSTED endpoint (`https://mcp.kingsleylab.xyz/mcp`, host vantage) as the non-admin principal `prn_accept_e2e`, embedded Trail (`POLYMATH_TRAIL_MODE=embedded`, durable store), this
session as agent host and harness executor with real web tools (`opencli` Reddit / YouTube / Amazon, Exa search + fetch). Evidence summary (no corpus text): `eval/consolidation_e2e/2026-09-21-real-ecommerce-e2e.json`. Artifacts (journal,
receipts, tool traces, dossier) are kept OUTSIDE the repository: `~/PolymathRuntime/e2e/2026-09-21-real-ecommerce-e2e/`.

| Run | Ended | Classification |
|---|---|---|
| 1 `adr_d503e87f…` | `J_admit` · `TRAIL_REFUSED` | FAILED (software): receipt ⇔ Trail contract drift → fixed 11.381 |
| 2 `adr_47b7277c…` | `L_judge` · `PHI_VERDICT_INVALID` | FAILED (software): D1, an empty admission was not a citable cause → fixed 11.382 |
| 3 `adr_ebbcdd56…` | `Z_refuse_lineage` · `LINEAGE_LAW_UNSATISFIED` | VALID typed refusal — caused by the harness driver replaying row ids this run did not retrieve (driver mistake; the law was right) |
| 4 `adr_ebd92926…` | `Q_admit` · `TRAIL_REFUSED` | FAILED (software): Trail's cross-field receipt rule not checked at submit; triggered by a harness timestamp mistake → fixed 11.383 |
| **5 `adr_c994b32a…`** | **`X_compile` · `completed`, 78 steps** | **VALID governed outcome: Trail REFUSED the score for all four hypotheses (`HARD_GATE_UNMET`)** |

| Capability | Evidence (run 5 unless stated) | What happened |
|---|---|---|
| Hosted MCP, per-principal authz, run ownership | REAL_INPUT_EXECUTED | every run `owner_principal_id = prn_accept_e2e`, `agent_identity = claude-code/agent-host-e2e`; friend `adapter_cancel` = 403 |
| Corpus knowledge → readable evidence rows | REAL_INPUT_EXECUTED | 122 → 200 refs from `cinema`; FINDING: the evidence-boundary WILDCARD pass returned 0 rows, the `retrieve` plan pass carried the run; the 60-row display cap returns the SAME first 60 rows at every step |
| `knowledge.corpus_evidence`, `understanding.lenses`, lineage law | REAL_INPUT_EXECUTED | law looped once in run 1 (`doc:` / `fact:` rows are shown as citable but refused), passed first time afterwards; typed refusal proven in run 3 |
| Population nomination, VOI, channel queries | REAL_INPUT_EXECUTED | 22 ranked leads; FINDING: queries are keyword fragments of the lead NAME / hypothesis STATEMENT — verbose agent wording gave 13 / 13 useless queries (run 1); plain community names + top-level gaps gave usable ones (run 2+) |
| Hypothesis ledger (generate, revise ×11) | REAL_INPUT_EXECUTED | four hypotheses; revisions cite admitted evidence; contradiction kept |
| Bridge + portfolio law | REAL_INPUT_EXECUTED | passed first time; bridges shrink honestly when a run does not retrieve a row |
| Trail `registry.project` | REAL_INPUT_EXECUTED | snapshot `trs-da9942986e52f832`; territories projected: body_mounted_access, one_hand_controls, modular_carry, environmental_protection … |
| Trail `hypotheses.judge` | REAL_INPUT_EXECUTED | ×3 per run: weakened → strengthened (carry, heavy lens) / weakened (buried accessories) / unchanged (rain) |
| Trail `gaps.compile` (field, supply) | REAL_INPUT_EXECUTED | compiles ONLY a step's top-level `knowledge_gaps`; per-hypothesis gaps in the ledger are ignored (FINDING) ; adds its own gate gaps |
| `research.plan` → directive | REAL_INPUT_EXECUTED | 66 intents / budget 24; intent ids Trail-valid after 11.381 |
| Harness field research | REAL_INPUT_EXECUTED | 24 + 6 + 4 directed queries; 11 real sources, 26 observations incl. counter-evidence; limitations reported |
| Trail `evidence.admit` | REAL_INPUT_EXECUTED | field: 8 / 20 admitted (8 `STALE_BEYOND_POLICY` at a 14-day policy, 4 `SOURCE_UNREGISTERED`), then 0 / 6, 0 / 0; product reality 5 / 9; supply 9 / 9. FINDING: the receipt has no polarity field — admitted counter-evidence is recorded "supporting" |
| Evidence cards, lived clusters | REAL_INPUT_EXECUTED | 3 clusters, all THIN (one thread each; author identity deliberately not recorded → 1 voice) |
| Lived situations law, corpus questions, revise, research loop ×3 | REAL_INPUT_EXECUTED | passed first time; a zero-admission round no longer kills the run (11.382) |
| Physical jobs, mechanisms, product concepts + product-set law | REAL_INPUT_EXECUTED | 4 mechanisms, 5 distinct concepts × 2 variations, each on admitted evidence |
| Trail `territory.project` | REAL_INPUT_EXECUTED | registry territories per hypothesis |
| Product reality (real products / competitors) | REAL_INPUT_EXECUTED | Peak Design Capture V3 (≈10,600 ratings, 79.95 USD), PGYTECH Beetle V2 (59.95), NEEWER GP67 (39.99), Falcam F38 (≈59); review complaints (rigid / wide straps, two-handed release); it CUT AGAINST two concepts (shared plate exists; wide-strap fit exists). FINDING: the directive's 4 templates key on the registry territory name — literal fill finds articles, the adapter-supplied product terms find products |
| Trail `opportunity.qualify` market_delta | REAL_INPUT_EXECUTED | carry hypothesis PROVISIONAL: competitor_review_analysis 1 / 2 ✗, current_price_checks 3 / 3 ✓ |
| `supply.plan` (S_gaps → S_plan) | REAL_INPUT_EXECUTED | 10 concept-derived supplier queries (Alibaba, CJ) |
| Supplier research (real sourcing) | REAL_INPUT_EXECUTED | 5 Alibaba listings with printed price tiers + MOQ + one lead time; CJ Dropshipping returned nothing usable (FAILED for that channel); no supplier offers a concept as designed — nearest components only |
| `supply.leads` (price / MOQ parse, concept join, coverage) | REAL_INPUT_EXECUTED | 4 leads: Shenzhen Qiyu 10.19 USD MOQ 2 · Shenzhen Hqs 2.80 USD MOQ 10 · Zhongshan Letu 10 USD MOQ 1 · neoprene showroom 0.99 USD MOQ 100; `pc_5` UNSOURCED |
| Trail `opportunity.qualify` supply | REAL_INPUT_EXECUTED | PROVISIONAL: current_price_checks 4 / 3 ✓, risk_review 0 / 1 ✗ |
| Trail `opportunity.score` | REAL_INPUT_EXECUTED (refusal) | `HARD_GATE_UNMET` ×4; for the carry hypothesis exactly `market_delta:competitor_review_analysis, supply:risk_review`. A POSITIVE score: NOT_REACHED |
| Interpretation + `X_compile` result + lineage | REAL_INPUT_EXECUTED | FINDING: the objective says "explain by record id" but only `trail_score_refs` may carry Trail record ids |
| Governed dossier (engine renderer, host-side journal) | REAL_INPUT_EXECUTED (render) | verdict "GOVERNED — TRAIL REFUSED TO SCORE"; five authority labels, populations, clusters, situations, bridge, 22 admitted / 22 rejected with reasons, 5 concepts + variations, supplier leads with price / MOQ / URL, held + rejected paths, unresolved, audit. PRODUCT-ARTIFACT GAPS: no "existing products" section (admitted competitor names / prices appear only in the observation list), Trail qualification gate results are not rendered, URLs are text not links |
| Trail audit store (durable, embedded) | REAL_INPUT_EXECUTED | 42 operations: admit 10 · gaps 10 · judge 12 · qualify 2 · score 1 · registry 5 · territory 2 |
| Commerce corpus `commerce-v1` | NOT_REACHED for the E2E (owner: use `cinema`) | 10 / 10 documents uploaded; 4 `query_ready`; 4 complete-but-`reconciling`; 2 `extract` tickets FAILED after 3 attempts on provider HTTP 503 |
| External-machine hosted acceptance | NOT_REACHED | every run here is host vantage |
