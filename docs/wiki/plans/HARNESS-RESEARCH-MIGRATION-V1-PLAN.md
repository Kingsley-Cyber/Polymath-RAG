---
change_id: HARNESS-RESEARCH-MIGRATION-V1
owner: governance
owner_directive_date: 2026-09-13
last_reviewed: 2026-09-13
status: plan-of-record + cutover ledger (updated in the same commit as every slice)
architecture_impact: "ADR-0019 (Polymath) + ADR-063 (Trail): harness-executed hypothesis research; durable hypothesis state; Trail priors/admission/qualification/scoring as bounded operations; Trail-owned live-web acquisition leaves the product-discovery critical path; research/ and research_* retired after cutover."
---

# HARNESS-RESEARCH-MIGRATION-V1 — plan of record and cutover ledger

> Owner directive (2026-09-13): "Migrate Polymath + TrailSignal to the Harness-Executed Hypothesis Research Architecture" — a live,
> governed migration; no parallel replacement; one authoritative implementation of each responsibility; a migration matrix that is the
> cutover ledger, not a stale plan. §7 below is that ledger. Refactor 0013 tracks slices; ADR-0019 is the Polymath authority.

## 0. Ownership (the questions asked at every checkpoint)

| question | owner | where it is enforced |
|---|---|---|
| Who owns knowledge? | Polymath (chunks, parents, graph, latent structures, retrieval lineage) | `shared/polymath_shared/retrieval.py`, `/retrieve`, evidence refs of kind chunk/document/graph_fact/graph_hop/parent_map |
| Who owns hypothesis state? | Polymath (`adapter_hypotheses` + `adapter_hypothesis_transitions`, pure state machine) | migration 0062, `shared/polymath_shared/adapter/hypotheses.py` (R2) |
| Who owns opportunity-domain rules? | TrailSignal (compiled registry snapshot of its CSV priors; source/evidence-role policy; gates) | Trail `data/*.csv` → `TrailRegistrySnapshotV1` (Trail HR1), `trail.product_discovery` manifest supplies the workflow |
| Who owns evidence admission? | TrailSignal (`evidence.admit` bounded operation) | Trail HR2/HR3; Polymath stores `EvidenceAdmissionV1` projections only |
| Who owns live-world execution? | The host harness (Claude Code / Hermes / Codex) through `HARNESS_ACTION` | ADR-0019 §2; no runtime module names a search engine, browser or source SDK (neutrality test) |
| Who owns scoring? | TrailSignal deterministic engine (LAW 1); only after gates | Trail `opportunity.score` (HR2/HR3); Polymath refuses any model/harness field named score |
| More than one implementation per authority? | After R5: no (§7 rows carry the deletion criterion) | dead-reference audit §12 |

## 1. Invariants (enforced in code, tests named in §9)

1. No domain reasoning step may require a specific web/search implementation (source-neutrality test extends to source names).
2. No live-world claim may be created from Trail CSV priors (`trail_prior` refs are refused in every evidence-role citation).
3. No harness observation becomes evidence until Trail admits it (AGENT_REASON context builder includes only Polymath evidence and `field_evidence` admitted by Trail; raw receipts never enter a context).
4. No hypothesis loses its Polymath chunk/graph lineage as it evolves (a transition row without parent ids and cause refs is refused by the state machine and by a database CHECK).
5. Adding a source is a registry-data operation (fixture test: a new source row routes a directive with zero code change).
6. LAW 1: no model, harness, θ, φ, Polymath step or CSV prior produces the authoritative score; scoring runs only after the gates.

## 2. Target runtime loop → step types

| owner node | Polymath step type (manifest `trail.product_discovery` 2.0.0) | notes |
|---|---|---|
| POLYMATH_RETRIEVE, POLYMATH_GRAPH_EXPAND | existing | chunks + parent context + graph |
| θ GENERATE_HYPOTHESES | AGENT_REASON `theta_op: generate_hypotheses` → HypothesisStateV1[] (≤8) | cites Polymath evidence only |
| TRAIL_PROJECT_PRIORS | EXTERNAL_OPERATION `registry.project` | returns coordinates + snapshot id/hash; refs of kind `trail_prior` |
| φ FILTER / MERGE / KILL / CHALLENGE | EXTERNAL_OPERATION `hypotheses.judge` (Trail deterministic) → transitions applied by the engine | redundancy, unsupported, self-corroboration |
| POLYMATH_MECHANISM_REASONING | POLYMATH_COMPILE_PLAN + POLYMATH_RETRIEVE (per surviving hypothesis) + AGENT_REASON `derive_mechanisms` | knowledge gaps typed on the hypothesis |
| TRAIL_COMPILE_EVIDENCE_GAPS | EXTERNAL_OPERATION `gaps.compile` → `HarnessActionV1` payload (search intents, source roles, freshness, independence, budget) | search_query_templates × source_registry |
| HARNESS_ACTION AGENT_RESEARCH → PAUSE → RECEIPT | HARNESS_ACTION (kind AGENT_RESEARCH); run status `awaiting_harness`; `adapter_submit` with a `HarnessResearchReceiptV1` | durable pause (issued step, `expires_at` null) |
| TRAIL_EVIDENCE_ADMISSION | EXTERNAL_OPERATION `evidence.admit` → `EvidenceAdmissionV1` (admitted `field_evidence` ids, rejections retained) | roles, suitability, freshness, provenance, independence, duplicates, polarity, hypothesis linkage |
| POLYMATH_RE-REASON, θ/φ REVISE/SPLIT/MERGE/KILL/STRENGTHEN | AGENT_REASON `revise_hypotheses` (proposes transitions) + EXTERNAL_OPERATION `hypotheses.judge` + BRANCH (bounded loop back to gap compilation, never straight to research) | transitions with cause refs |
| PHYSICAL JOB / MECHANISM DERIVATION | AGENT_REASON `derive_physical_jobs` | friction primitives from the projection |
| TRAIL PRODUCT TERRITORY QUALIFICATION | EXTERNAL_OPERATION `territory.project` | product_territories priors |
| HARNESS_ACTION PRODUCT_REALITY_CHECK → TRAIL MARKET DELTA | HARNESS_ACTION (kind PRODUCT_REALITY_CHECK) → `evidence.admit` → EXTERNAL_OPERATION `opportunity.qualify` (stage market_delta) | competition/price/complaints/saturation roles |
| HARNESS_ACTION SUPPLIER_RESEARCH → TRAIL SUPPLY QUALIFICATION | HARNESS_ACTION (kind SUPPLIER_RESEARCH) → `evidence.admit` (role supply, never demand) → `opportunity.qualify` (stage supply) | supplier URL/identity/price/MOQ/variants/lead time/limitations |
| TRAIL DETERMINISTIC SCORE | EXTERNAL_OPERATION `opportunity.score` | only after gates; score record id + provenance |
| FINAL PRODUCT OPPORTUNITY | COMPILE_RESULT (output schema §3.4) | product concept, mechanism, population, evidence chain, lineage, contradictions, competitors, delta, supplier facts, score, uncertainty, cheapest falsification experiment |

## 3. Contracts

### 3.1 Polymath `contracts/adapter/v1` (additive within v1 per `contracts/README.md`)
| contract | status | content |
|---|---|---|
| `adapter_manifest` / `adapter_step` / `adapter_step_receipt` | extend enum | `HARNESS_ACTION` joins the closed vocabulary; step gains `cognitive_op` (theta/phi/null), `theta_op`, `harness_action`; context gains `hypotheses[]`, evidence kinds `field_evidence` (admitted) and `trail_prior` (never citable) |
| `harness_action` (HarnessActionV1) | DONE R1 | action_id, run_id, step_id, hypothesis_ids[], action_kind, objective, evidence_gaps[] (evidence_role = pattern string; the vocabulary is manifest `evidence_roles` + Trail snapshot data), search_intents[], preferred/disallowed_source_roles[], freshness_requirement, geography, language, minimum_independent_sources, success_condition, falsification_condition, budget{max_queries,max_sources,max_observations}, registry_snapshot{snapshot_id,content_hash}, issued_at |
| `harness_receipt` (HarnessResearchReceiptV1) | DONE R1 | action_id, run_id, harness_id, started_at, completed_at, sources[]{source_id,url,source_class,retrieved_at,published_at_if_known}, observations[]{observation_id,source_id,claim,paraphrase_or_excerpt,metric_if_present,context}, tool_trace[]{search_intent_id,tool_class}, limitations[] — validated as provenance shape only |
| `hypothesis_state` (HypothesisStateV1) | DONE R1 | owner §3 field list: identity, parents, revision, statement, mechanism, population/activity/task/context/suspected_friction, status, knowledge_support[], trail_priors[], field_evidence_ids[], assumptions/contradictions/falsifiers/knowledge_gaps, timestamps |
| `hypothesis_transition` (HypothesisTransitionV1) | DONE R1 | kind ∈ {GENERATE, REVISE, SPLIT, MERGE, WEAKEN, STRENGTHEN, CONTRADICT, KILL, PROMOTE}, actor ∈ {theta, phi, runtime}, step_id, sequence, parent_hypothesis_ids[], child_hypothesis_ids[], cause_refs[] (≥1: chunk/graph_fact/trail_prior/field_evidence/admission ids), from/to revision, resulting_status, reason_code |
| `evidence_admission` (EvidenceAdmissionV1) | DONE R1 | Trail verdict projection per observation: admitted_evidence_id, observation_id, role, source_class, source_suitability, freshness, provenance, independence_group, duplicate_of, polarity, hypothesis_ids[], stage_relevance, limitations, trail_admission_record_id; rejected observations retained with reason |
| `adapter_submission` | extend | `kind` ∈ {reasoning, receipt}; `payload` = reasoning payload or HarnessResearchReceiptV1 |
| `adapter_result` | extend lineage | hypothesis_ids[], admitted_evidence_ids[], harness_action_ids[], harness_ids[], registry_snapshot_ids[], trail_score_record_ids[] |

### 3.2 Trail contracts (Pydantic, `contexts/planning/public` + `contexts/evidence/public` + `contexts/scoring/public`, ADR-063)
`TrailRegistrySnapshotV1` (snapshot_id, schema_version, compiler_version, content_hash, compiled_at, activity_taxonomy, niche_seeds, friction_primitives,
product_territories, search_intents, source_roles, prior_candidates, seasonal_priors, scoring_policy); `RegistryProjectionRequestV1`/`RegistryProjectionV1`;
`EvidenceGapCompileRequestV1`/`ResearchDirectiveV1` (reused shape from the unmerged OCP1 draft: directive_id, gap_refs, queries → search_intents,
required_capabilities → source_roles, stopping_rule_refs, budgets); `HarnessResearchReceiptV1` (mirror of the Polymath wire contract);
`EvidenceAdmissionV1` + `AdmittedObservationV1`; `HypothesisJudgementV1` (φ verdicts); `QualificationV1` (states reuse the OCP draft vocabulary:
PROMOTED, PROVISIONAL, REJECTED, UNPROVEN, NO_DEFENSIBLE_BRIDGE; stages market_delta, supply); `OpportunityScoreV1` (doc 08 engine output +
provenance). All strict/frozen, registered in `schemas/registry.yaml`, generated into `schemas/generated/v2/`.

### 3.3 Source registry evolution (registry data, not workflow code)
`data/source_registry.csv` stays the owner-authored file (Trail treats `data/` as user-owned). A new agent-authored side table
`data/source_capabilities.csv` (joined on `source_id`) declares: `source_class, domains_or_patterns, supported_research_stages,
supported_evidence_roles, search_intent_support, freshness_policy, independence_group, product_search_capability, supplier_search_capability,
limitations, enabled`. The compiler joins both; a source absent from the side table is `enabled=false` for directive routing. Adding
Reddit/YouTube/TikTok/Facebook groups/Amazon/Walmart/Etsy/eBay/Home Depot/Lowes/Alibaba/CJ/1688/manufacturer sites/forums = rows.
`data/search_query_templates.csv` compiles to `SearchIntent` (intent id, evidence goal, roles, template with slots); no engine is named.

### 3.4 Final result output schema (`trail.product_discovery` 2.0.0)
`product_concept{title, mechanism_explanation, population, activity, context, problem}`, `evidence_chain[]` (hypothesis transitions with cause refs),
`polymath_lineage{chunk_ids, graph_fact_ids}`, `field_evidence[]` (admitted ids, roles, polarity), `contradictions[]`, `competing_products[]`,
`product_delta`, `supply{supplier_url, supplier_identity, platform, unit_price, moq, variants, lead_time, customization, shipping, limitations, retrieved_at}`,
`trail_score{record_id, score, subscores, confidence, provenance}`, `remaining_uncertainty[]`, `cheapest_falsification_experiment`.

## 4. Hypothesis state machine (Polymath, generic)
States: `proposed → filtered | retained → (revised | split | merged | weakened | strengthened | contradicted)* → killed | promoted`.
Rules: GENERATE needs ≥1 knowledge_support ref; SPLIT/MERGE record parent→children and children→parents; KILL/REJECT/MERGE verdicts are
accepted only from φ (Trail judgement or a closed Polymath VALIDATE rule such as identical-statement dedupe), never from θ alone; every
transition carries ≥1 cause ref of an allowed kind; revisions are immutable rows (a new revision per transition); the current view is a
projection. θ proposals that fail these rules are rejected with the reason and retained on the step receipt.

## 5. Registry snapshot (Trail)
Compiler input = the nine CSVs + `source_capabilities.csv` + `config/evidence_gates.json` + `config/scoring_weights.json` + `config/weights.yaml`;
output = one immutable `TrailRegistrySnapshotV1` with `content_hash` over canonical JSON; every projection, directive, admission and score
record carries the snapshot id; a CSV edit never changes runtime behaviour until a new build. Enforced: prior ≠ observation ≠ demand ≠ proof ≠
market reality (projection records carry `authority_class = PRIOR`; admission refuses PRIOR refs as evidence).

## 6. Trail operations (ADR-063: bounded synchronous deterministic operations)
`registry.project`, `gaps.compile`, `evidence.admit`, `hypotheses.judge`, `territory.project`, `opportunity.qualify`, `opportunity.score` — each
enters the shared daemon → typed application port → deterministic pure function → one atomic audit operation + immutable result in Data OS,
never creating Temporal state (the ADR-034/037 `dataset.query` exception pattern), principal-bound (`polymath` principal, new capability
enum members), idempotent on `idempotency_key`. Polymath calls them only through `trail_client` (EXTERNAL_OPERATION); `crawl/scrape/extract/
discover` remain generic Trail tools that the product-discovery adapter no longer requires.

## 7. MIGRATION MATRIX — the cutover ledger (§19 columns)

Legend: SM = state migration required, CM = caller migration required, TC = temporary compatibility. Status column: PENDING | IN_PROGRESS | CUT_OVER | REMOVED.

| # | current component | current authority | target component | target authority | SM | CM | TC | cutover criterion | deletion criterion | dead-code verification | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | `STEP_TYPES` (8) in `shared/polymath_shared/adapter/contracts.py:16` + enum in 3 schemas | ADR-0018 §2 | closed vocabulary of 9 (+HARNESS_ACTION) | ADR-0019 §2 | no | no | no (additive) | contract test asserts 9 everywhere | n/a | `test_adapter_contract_v1::test_step_vocabulary_is_closed_and_identical_everywhere` | CUT_OVER (R1, 11.266); engine mechanics R2 (11.267) |
| P2 | hypotheses as one AGENT_REASON payload (`C_hypotheses` output_schema) | manifest v1 | `HypothesisStateV1` rows + transitions (0062) | ADR-0019 §4 | yes: none live (2 completed runs are knowledge_brief/substack; no trail runs) | yes: manifest 2.0.0, executors, result compiler | no | R2 tests A + F green on Postgres | v1 `C_hypotheses` payload shape gone with manifest 1.0.0 | grep `"hypotheses"` outputs in runtime = only the ledger module | SUBSTRATE CUT_OVER (R2, 11.267); manifest at R4 |
| P3 | `D_discover` = `discover.submit` via `_exec_discover` (`adapter_step_worker.py:266`) | manifest v1 + ADR-0018 §5 | HARNESS_ACTION AGENT_RESEARCH issued from `gaps.compile` | ADR-0019 §1/§2 | no | yes (manifest) | no | R4: live run issues an AGENT_RESEARCH action and resumes on receipt | `_exec_discover`, `_hypothesis_queries`, `discovery_request` (client builder) removed at R4 | symbol sweep §12 returns 0 hits in runtime+tests+docs (except history) | PENDING (R4) |
| P4 | `E_acquire` = `scrape.submit`+`extract.submit` via `_exec_acquire_extract` (`:289`) | manifest v1 | harness receipt → `evidence.admit` | ADR-0019 | no | yes | no | same as P3 | `_exec_acquire_extract`, `_leads_from_prior`, `batch_request`, `extraction_request`, `crawl_request` (already dead), gap codes TRAIL_NO_LEADS/TRAIL_DISCOVERY_*/TRAIL_ACQUISITION_* removed at R4 | sweep §12 | PENDING (R4) |
| P5 | `F_normalize` (agent maps Trail records into the ontology) | manifest v1 | removed; Trail `registry.project` + `evidence.admit` do it deterministically | ADR-0019 §1 | no | yes | no | R4 manifest | step id gone; `trail_record` evidence kind removed from `adapter_step.schema.json` enum when no manifest uses it | sweep `trail_record_ids` = 0 | PENDING (R4) |
| P6 | `G_gates`/`I_score` planned `commerce.research.*` (Trail C1/C2) | ADR-0018 §5, Trail graph C1/C2 | `evidence.admit` + `opportunity.qualify` + `opportunity.score` (Trail HR2/HR3) | ADR-0019 §8, ADR-063 | no | yes | no | Trail HR3 WORKING + live run reaches score | `planned_node: C1/C2` references gone | manifest has no `availability: planned` steps after HR3 | PENDING (R3/R4) |
| P7 | `H_gap_loop` → `D_discover` (loop into Trail acquisition) | manifest v1 | BRANCH → `revise_hypotheses` → `gaps.compile` (loop through Polymath reasoning) | ADR-0019 | no | yes | no | R4 manifest test: no branch targets a HARNESS_ACTION directly | — | pure-core test G | PENDING (R4) |
| P8 | `exec_external` dispatch on operation kinds (`:236`) | E4 | `exec_external` dispatches by `external.operation_kind` to the bounded ops; two-phase pending path retained for any Temporal op | ADR-0019 §8 | no | no | no | R4 | Trail acquisition kinds removed from the dispatch | sweep | PENDING (R4) |
| P9 | `trail_client.py` builders `discovery_request/crawl_request/batch_request/extraction_request/page_request/operation_reference/cancel_command` | E4 | keep `TrailMCPClient` + JWT + envelopes; builders for the 7 bounded ops; acquisition builders removed | ADR-0019 | no | yes | no | R4 | acquisition builders + their tests (`test_trail_client.py:30-63`) replaced | sweep | PENDING (R4) |
| P10 | `research/` package (9,758 LOC), `research/registry/trailsignal/*.csv` (8 identical + 3 drifted ahead of Trail `data/`), `research/python/registry.py` compiler, `research_*` MCP tools (`mcp_server.py:352-431`), `.github/workflows/research-harness.yml`, TREE entries, `scripts/README.md` rows, Hermes skill symlink | E6 "migration input" | none (semantics migrated: θ/φ vocabulary, hypothesis statuses, evidence-before-supply, NO_DEFENSIBLE_BRIDGE, compiler laws → manifest + contracts + Trail compiler) | ADR-0019 §7 | drifted rows: owner decision D2 (upstream to Trail `data/`) | Hermes skill symlink → owner action O6 | FROZEN banner (R0) | R5 acceptance green | remove package, tools, workflow, TREE rows, README rows at R5 | `test_research_package_removed` guard + sweep `research_` / `research/` | FROZEN (R0) |
| P11 | `_TOOL_NAMES` research_* in `mcp_server.py:586-591`; prompt text `:73-74` | E6 | 7 `adapter_*` tools only | ADR-0019 | no | yes (Hermes prompt) | no | R5 | with P10 | `test_mcp_server_v2` tool list | PENDING (R5) |
| P12 | `.env.example` lacks every Trail/adapter variable name | gap | names documented (`POLYMATH_TRAIL_MCP_URL`, `TRAIL_SIGNAL_MCP_TOKEN_POLYMATH`, `TRAIL_SIGNAL_MCP_JWT_SECRET`, `POLYMATH_TRAIL_PRINCIPAL`, `POLYMATH_TRAIL_AUDIT_IDENTITY`, `POLYMATH_ADAPTER_HTTP_TIMEOUT_S`, `POLYMATH_ADAPTER_LEASE_S`) | repo hygiene | no | no | no | R2 | n/a | grep | CUT_OVER (R2, 11.267) |
| P13 | `max_external_operations` budget (optional) | ADR-0018 | + `max_harness_actions`, `max_hypotheses` budgets | ADR-0019 | no | no | no | R1 | n/a | contract test | CUT_OVER (R1, 11.266) |
| P14 | `test_adapter_runtime_neutrality.py` (adapter ids + domain words) | E7 | + source names (reddit, youtube, tiktok, facebook, amazon, walmart, etsy, ebay, homedepot, lowes, alibaba, cj, 1688, searxng, google, exa, camofox, playwright, crawl4ai) forbidden in runtime, worker, manifests, tests of the runtime | ADR-0019 §6 | no | no | no | R1 | n/a | the test itself | CUT_OVER (R1, 11.266) |
| P15 | `tests/determinism/test_adapter_trail_connector.py` (stub Trail discover/scrape/extract) | E4 | replaced by stub tests of the 7 bounded ops + receipt admission | ADR-0019 | no | yes | no | R4 | old test removed with P3/P4 | CI | PENDING (R4) |
| P16 | `config/adapters/trail.product_discovery.json` 1.0.0 (A–K) | manifest v1 | 2.0.0 on the §2 loop (same file, same adapter_id; workflow_version 2.0.0; output_schema §3.4) | ADR-0019 | no live runs | yes | no (`adapter_list` shows one manifest) | R4 tests + live run to the first Trail gap | v1 step ids gone | manifest test | PENDING (R4) |
| P17 | `contracts/adapter/v1/adapter_manifest.example.json` (= v1 trail manifest) | E1 | example = 2.0.0 manifest | ADR-0019 | no | no | no | R4 | — | contract test | PENDING (R4) |
| T1 | Trail `data/*.csv` (9 curated files; only 4 read by the v1 CLI; rubric/taxonomy/friction/territories/seasonal unread) | AGENTS.md (v1 ledger), user-owned | `TrailRegistrySnapshotV1` compiler (HR1) reads all nine + `source_capabilities.csv`; CSVs stay authored data | ADR-063 | no (files unchanged) | v1 CLI keeps reading (frozen, not extended) | yes: v1 CLI and snapshot coexist until v1 toolkit quarantine (repo_layout migration map) | HR1 VERIFIED (replay byte-identical) | v1 `src/niche_research/` quarantine per repo_layout, separate slice | Trail architecture tests | PENDING (R3) |
| T2 | Trail scoring #1: `src/niche_research/scoring.py` + `config/scoring_weights.json` (13 rubric dims, 0–5, bands) — `scoring_rubric.csv` has NO reader | v1 CLI | deterministic QUALIFICATION bands (dimensions derived from admitted evidence + gates) inside `contexts/scoring` (HR2) — owner decision D1 | ADR-063 | no | v1 CLI frozen | yes during v1 coexistence | HR2 replay + D1 confirmed | v1 quarantine | LAW 1 guards | PENDING (R3) |
| T3 | Trail scoring #2: `signal_engine/score.py` five-axis engine (doc 08), fixture kernel only | doc 08 (Tier-2), v1 | THE authoritative `opportunity.score` in `contexts/scoring` fed by role→axis signals derived from admitted evidence (no LLM classify) — D1 | ADR-063, repo_layout migration map ("migrate deterministic parts into scoring context") | no | none live | yes | HR2 byte-replay of the camping fixture 0.72 through the v2 path | `signal_engine/` quarantine after HR2 | guards 5/9/12 | PENDING (R3) |
| T4 | Trail graph C1/C2/Q1/C3 (PENDING, behind P9) | ADR-015 sequencing | SUPERSEDED; A32 + HR1–HR4 are the active commerce path; P9 not a prerequisite for the first loop | ADR-063 | no | no | no | A32 VERIFIED | n/a (history retained) | governor DAG checks | PENDING (R3) |
| T5 | Trail unmerged OCP branch line (`codex/a30…`, `codex/a31…`, `codex/ocp1…`, `codex/ocp2…`: ADR-061/062, OCP1 planning contracts, Trail-owned IR, Trail→Polymath bridge) | not authority (never on main) | vocabulary reused (ResearchDirective, ProposalGate receipts, QualificationState, FactStatus, CapabilityManifest); composition rejected (Polymath owns hypothesis state; harness owns the web) — owner decision D3 | ADR-063 §context | no | no | no | D3 recorded | branches deleted or archived by the owner | — | OWNER (D3) |
| T6 | Trail `PrincipalCapabilityV5` (10 members) + `config/v2/toolsets/core.yaml` + `principals.yaml` (4 principals, no `polymath`) | ADR-040 | V6 adds the 7 bounded-operation capabilities; `polymath` principal + `mcp.polymath.bearer` secret alias — owner action O1 | ADR-063 | no | Polymath `trail_client` CAPABILITIES list | no | HR3 | n/a | auth runtime assertion (`runtime.py:150-187`) | PENDING (R3 + O1) |
| T7 | Trail generic `discover/crawl/scrape/extract` tools | ADR-015/040 | unchanged; no longer required by product discovery | ADR-063 | no | no | no | R4 | never (independently useful) | — | RETAINED |
| T8 | Trail stack down on this host (Temporal :7233, Postgres :15433, VersityGW :7070, MinIO/HAProxy :19000, daemon :8767, SearXNG :8080) | environment | up for HR3 verification and R5 — owner action O4 | — | — | — | — | O4 | — | — | OWNER (O4) |
| S1 | `docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md` §7/§8/E3/E5/E6 + START-HERE items 4–6 | owner plan V1 | this plan | ADR-0019 | no | no | no | R0 banner | never (owner history) | — | CUT_OVER (R0) |
| S2 | Trail `docs/build/COGNITIVE_ADAPTER_*` (superseded pointers to the V1 plan) | PR #2 | pointers updated to this plan in the A32 governance slice | ADR-063 | no | no | no | A32 | — | — | PENDING (R3) |

## 8. Slices (each follows the 12-step protocol: truth → authority → contract → replacement → state/callers → compatibility proof → switch → verify → remove → audit → governance → commit)

| slice | repo | content | gate to start | gate to finish |
|---|---|---|---|---|
| R0 | Polymath | this plan, ADR-0019, refactor 0013, banners, `research/` FROZEN | truth established (§11) | guards green, register 11.265 |
| R1 | Polymath | contracts §3.1 + examples + contract tests; neutrality test with source names; budgets | R0 | `test_adapter_contract_v1` + neutrality green |
| R2 | Polymath | migration 0062; `hypotheses.py` pure state machine; HARNESS_ACTION issue/pause/receipt in transitions/service/store/worker/API/MCP; admitted-only context; `.env.example` | R1 | tests A, F, G (pure + Postgres), restart test |
| R3 | Trail | ADR-063 + A32 governance; HR1 snapshot compiler + contracts + replay; HR2 admission/qualification/scoring + replay; HR3 bounded MCP ops + audit records; HR4 loop canary | R2 (contracts agreed) + owner D1/D3/D4 | Trail governance green; HR3 needs O1/O4 for VERIFIED |
| R4 | Polymath | manifest 2.0.0; executors for the 7 ops; remove P3/P4/P5/P8/P9/P15 surfaces; tests B, C, D(proj), E, H, I, J | R2 (+ R3 contracts for stubs) | live run reaches the first Trail op; dead-reference audit clean |
| R5 | both | live acceptance through `scripts/adapter_mcp_acceptance.py` with a real harness executing actions; remove `research/`, `research_*`, workflow; final audit | R3 HR3 WORKING, O1, O4 | §20 completion definition |

## 9. Test requirements → tests
| req | test |
|---|---|
| A hypothesis lineage | `tests/determinism/test_hypothesis_state_machine.py` (pure) + `test_adapter_hypotheses_store.py` (Postgres) — revision/split/merge keep chunk/graph/evidence ancestry; a transition without cause refs is refused |
| B harness independence | `test_adapter_harness_action.py` — receipts from `harness_id` "hermes" and "claude-code" through the same runtime; no harness id in runtime source (neutrality) |
| C source extensibility | Trail `tests/replay/registry/test_source_extensibility.py` — add a fixture source row → directive routes to it; `git diff` of `src/` empty; Polymath side: `test_adapter_runtime_neutrality` source-name sweep |
| D evidence admission | Trail `tests/unit/evidence/test_admission.py` — unsuitable role/source pair rejected; duplicate/non-independent do not inflate counts; stale evidence per policy; contradictions preserved |
| E prior/evidence separation | Polymath `test_adapter_runtime_pure` — `trail_prior` cited as evidence → rejected; Trail — projection records cannot satisfy a gate |
| F pause/resume | `tests/integration/test_adapter_runtime_restart.py` extended: crash while `awaiting_harness`; receipt resumes the right run/hypotheses |
| G hypothesis loop | pure walk: evidence strengthens/weakens/splits/kills and triggers exactly one more bounded HARNESS_ACTION |
| H product stages | manifest test: PRODUCT_REALITY_CHECK and SUPPLIER_RESEARCH are distinct typed steps with distinct admission stages |
| I LAW 1 | submission/receipt schemas refuse any `score`/`opportunity_score` field; result `trail_score` only from an `opportunity.score` receipt |
| J dead-code guard | `tests/contracts/test_retired_paths.py` — the active adapter/worker cannot import or reference the retired acquisition path or `research/` |

## 10. Owner decisions and actions (recorded here; each row names what it unblocks)
| id | decision / action | recommendation | unblocks |
|---|---|---|---|
| D1 | Which Trail engine is THE authoritative opportunity score: the doc-08 five-axis engine (`signal_engine`, camping fixture 0.72) or the 13-dimension rubric (`scoring_weights.json`, bands) | doc-08 engine = the score (signals derived from admitted evidence by role); rubric = deterministic qualification bands + gates. One score, one qualification | HR2 |
| D2 | Polymath `research/registry/trailsignal/` drifted ahead of Trail `data/` (friction_library +10 rows fr-31..fr-40, niche_candidates +6 nc-037..nc-042, seed +6 seed-2001..2006, plus `friction_library.upstream.patch`) | upstream the delta into Trail `data/` (user-owned) before HR1 compiles the snapshot; otherwise drop | HR1 fidelity |
| D3 | Disposition of the unmerged Trail OCP branch line (ADR-061/062, OCP1 contracts) | archive as history; ADR-063 records the reuse/rejection; do not merge | R3 |
| D4 | Acceptance authority for Trail ADR-063 | recorded as "Repository owner through the explicit 2026-09-13 harness-executed hypothesis research migration instruction", following the ADR-039..060 precedent; owner may revert | R3 |
| D5 | Registry schema evolution via a side table (`data/source_capabilities.csv`) rather than editing the owner's `source_registry.csv` columns | side table (additive; owner file untouched) | HR1 |
| O1 | `polymath` principal + `mcp.polymath.bearer` alias in Trail `config/v2/{principals,secrets}.yaml`; `TRAIL_SIGNAL_MCP_JWT_SECRET` or a minted token in the fleet env | — | HR3 live, R5 |
| O4 | Trail stack up on this host | — | HR3 VERIFIED, R5 |
| O6 | Hermes skill symlink (`~/.hermes/skills/…` → `polymath-v4/research/`) retargeted to the adapter skill before `research/` is removed | — | R5 |

## 11. Repository truth at R0 (2026-09-13)
- Polymath origin/main 629278f; fleet worktree `production` @ 629278f; adapter runtime E0–E7 live; 2 completed adapter runs (knowledge_brief, substack), 0 trail runs.
- Trail origin/main 6d7ef2a (PR #2); owner checkout `~/trail-signal-os` main c5dd8a6 (75 behind, 12 dirty files — untouched); v2 contexts: acquisition, analytics, data_os, discovery, extraction, platform, workflow (no evidence/scoring/planning); ADR index 001–060 (046 absent); graph v2.8: P1R/P2/P3/P5 VERIFIED, P4/P4V BLOCKED, P4W/P6R/P7R/P8R/P9/C1/C2/Q1/C3 PENDING; ledger through A29.
- Trail governance baseline on origin/main with the LOCKED dependencies (`uv sync --python 3.12 --frozen`, then `.venv/bin/python scripts/architecture/validate_v2_governance.py --root . --check`): exactly ONE diagnostic — `RUN_CHANGE_COVERAGE` for A29 (PR #1/#2 added the two handoff docs outside A29 owned paths); secret scan PASS (1,525 files), manifest check PASS (181 artifacts). The architecture unittest stage has one pre-existing failure, `tests/architecture/test_agent_control.py::test_p4v_start_after_a27_commit_creates_controller` (expects `.agent-control/tasks/P4V` absent; it exists). A venv with only PyYAML + pydantic (the CI recipe) additionally errors on 4 tests that import pytest/fastmcp/aiohttp, and system python3 3.9 produces ~190 spurious diagnostics — neither is a repository failure. Recorded, not repaired by this migration except through the A32 slice's own owned paths.
- Trail curated CSVs: 9 files in `data/` (+ research_evidence, research_runs_index); readers: v1 CLI only (seed, candidates, templates, evidence); `scoring_rubric.csv` unread; `config/v2/sources.yaml` is network policy, not a source registry.

## 12. Dead-reference audit protocol (run before every CUT_OVER/REMOVED status change)
```
grep -rn -E "_exec_discover|_exec_acquire_extract|_hypothesis_queries|_leads_from_prior|discovery_request|crawl_request|batch_request|extraction_request|D_discover|E_acquire|F_normalize|G_gates|H_gap_loop|I_score|J_interpret|trail_record_ids|TRAIL_NO_LEADS|TRAIL_DISCOVERY_|TRAIL_ACQUISITION_|commerce\.research|research_init|research_step|research_submit|research_status|research_corpus|research_report|research/" --include=*.py --include=*.json --include=*.yml --include=*.yaml --include=*.md --include=*.sh . | grep -v -E "^./docs/wiki/(work-log|plans/PLAN-AUTHORITY-REGISTER|plans/CONTINUITY-REPORT|plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0-GAP-MATRIX|plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN)"
```
Expected after R5: zero lines outside append-only history. Trail side: `validate_v2_governance.py --check` + `agentctl guard` + `scan_repo_secrets.py` + `update_manifest.py --check`.
