# Transduction Audit — 2026-09-21 — where latent-opportunity semantics are created, preserved, reduced, flattened or ignored

> AGENT-OWNED, READ-ONLY AUDIT. Brief: `OWNER_AUDIT_DIRECTIVE_2026-09-21.md`; controlling intent: `OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md`. Nothing was implemented, merged, deployed, bounced, repaired, spent or benchmarked.
> The three owner-reserved decisions are NOT resolved here (§13 gives evidence and options only). Canonical object: the 54-step `ecommerce.product_research`. Every finding is labelled
> **[EPR]** = ECOMMERCE.PRODUCT_RESEARCH · **[TPD]** = TRAIL.PRODUCT_DISCOVERY · **[BOTH]** (shared runtime or the embedded Trail core).
> Evidence labels: **EXECUTED** (code run this session, read-only) · **STATICALLY VERIFIED** (manifest / JSON Schema / pydantic config checked mechanically) · **READ** (code read, not run) ·
> **HISTORICAL RUN EVIDENCE** (run 5 `adr_c994b32a8c7287a9b0508f1f3a4c42e8`: read-only `SELECT` on `adapter_steps` / `adapter_hypotheses`, and `~/PolymathRuntime/e2e/2026-09-21-real-ecommerce-e2e/journal.json`) · **INFERRED**.

## 0. Session record and freshness check
`production` @ `515410e`, clean; guards `preflight=0 repo_guard=0 wiki_worm=0 bundle=READY`; fleet 13 worker types healthy, ONE bundle, `/ready` true, MCP :8930 ok, 0 running adapter runs (EXECUTED). Resources touched: repository files (read), the fleet
Postgres (read-only `SELECT`), the run-5 artifact directory (read). No Trail call, no orchestrator call, no provider call.

| # | Confirmed finding (directive) | Freshness 2026-09-21 |
|---|---|---|
| A | lexical registry / territory mapping | CURRENT — `governance/trail/src/trail_signal/contexts/planning/domain/gap_compiler.py:149` `derive_registry_coordinates`, `:179` `map_product_territories` (READ) |
| B | `context_view` = statement-only | CURRENT — `shared/polymath_shared/adapter/hypotheses.py:256–260`; called at `service.py:421`. 67 / 67 issued steps that carried hypotheses carried exactly `{hypothesis_id, revision, status, statement}` (HISTORICAL RUN EVIDENCE) |
| C | Trail `HypothesisView` thin, `knowledge_support_count=0` | CURRENT — `research_operations.py:166` (READ). Already recorded as D4 in `TRAIL-GROUND-TRUTH-DOSSIER.md` |
| D | first-hypothesis gap fallback | CURRENT — `research_operations.py:170–173` (READ) |

## 1. Executive finding
`ecommerce.product_research` DOES contain a semantic transformation layer: `C_primitives` emits 13 typed primitive families plus `latent_structures[]` (with `possible_populations` and `applicability_outside_source`), `C_population` turns them into NAMED and
LATENT population leads ranked by value of information with a discount for restating the seed, the ledger stores `population / activity / task / context / mechanism / suspected_friction` per hypothesis, `C_bridge` writes an explicit ≥ 3-hop path with an
evidence boundary, and `N_jobs` / `N_concepts` emit physical jobs, mechanisms with market vocabulary (`product_terms`) and typed concepts with variations BEFORE product reality. All of it is DURABLE (`adapter_steps.output`, `adapter_runs.outputs`,
`adapter_hypotheses.state`). **Nothing needs to be invented to hold it. What is missing is propagation:** every consumer boundary after creation hands on a thinner object than the one that exists — a 4-field hypothesis view to every step and to Trail;
opaque record ids back from Trail; unfilled `{activity} {task} {product_territory}` template slots to the harness although the ledger holds fields with those exact names; six-keyword fragments to the query compiler; no planning step at all for product reality;
a dossier that reads the 4-field view and therefore prints empty mechanism / population columns. Several of these are plain correctness defects (every hypothesis told "no knowledge support"; territory name dropped on the wire; a computed corpus question that
never reaches retrieval; revised gaps silently discarded). Severity: **P0 for the thesis** — in the as-built path Trail's vocabulary cannot act as a transformation grammar and hypothesis-specific intelligence does not survive to research — **not** a failed
migration and **not** an absent architecture. A new durable IR is NOT supported by the evidence; a derived read projection plus two small contract extensions is (§12, §14). Cross-domain transduction is mechanically possible and ranked first by the engine, but
unproven: run 5's seed named the population and the problem, and one standalone analogy stage was mapped during migration onto a Trail operation that does not perform it (§7).

## 2. Canonical production workflow — [EPR] semantic dataflow as built
```
input.seed ─┬─► B_plan (/retrieve/plan)  ─┐ rows      B_retrieve / B_graph = evidence boundary, need = seed        (run 5: boundary returned 0 chunk rows; B_plan carried the run)
            │                             ├─► B_intake knowledge.corpus_evidence ─► corpus_evidence (one id space)
            └─► B_lenses understanding.lenses (engine lenses.yaml; keyword hit on seed + rows) ─► lenses
C_primitives θ  ◄ evidence.rows (≤ 60) + materials{lenses}            ─► primitives{13 families, latent_structures[], population_leads[], row_relevance}
C_lineage   understanding.validate_primitives                          ─► valid, row_relevance, latent_structures        (primitives themselves are NOT re-emitted)
C_population population.nominate ◄ seed, primitives, latent_structures ─► population_leads, community_leads, ranked_lead_ids, batch (top 4 VOI), channel_queries per lead
C_hypotheses θ ◄ materials{lenses, leads, ranked ids, latent_structures}   ✗ primitives   ✗ analogies     ─► proposals ─► LEDGER rev 0 (all typed fields)
C_bridge θ  ◄ materials{generated_hypotheses (full proposals), lenses}  ✗ latent_structures ✗ leads      ─► bridges[] (stored in outputs only; keyed by hypothesis_id)
C_bridge_law hypotheses.validate_bridge                                 ─► admissible / errors
D_project   Trail registry.project  ◄ {hypothesis_id, revision, status, statement}                        ─► priors[{record_id, prior_role, hypothesis_ids}]   (label / overlap / section dropped on the wire)
E_filter    Trail hypotheses.judge  ◄ same 4 fields, knowledge_support_count forced 0                     ─► WEAKEN / NO_KNOWLEDGE_SUPPORT for EVERY hypothesis
F_plan / F_retrieve / F_graph ◄ hypothesis STATEMENTS                                                     ─► rows (citable ids; never readable — §10)
G_mechanisms θ ◄ 4-field hypotheses, NO materials                       ─► REVISE transitions + top-level knowledge_gaps[{hypothesis_id, question, role}]
H_gaps      Trail gaps.compile ◄ 4-field hypotheses + top-level gaps + newest open_gaps                   ─► research_directive{evidence_gaps, search_intents = UNFILLED slot templates}
H_plan      research.plan ◄ directive, 4-field hypotheses, leads, batch ─► directive + channel intents (first 6 keywords of each gap question / lead name)
I_research  HARNESS ◄ harness_action{gaps, intents, roles, budget} + materials{leads, plan counts}        ─► receipt{observations[{claim, context, role, hypothesis_ids}]}     (no relation / polarity field)
J_admit     Trail evidence.admit                                        ─► admitted[{…, polarity (role or leading negation), hypothesis_ids}]
J_cards     population.evidence_cards ◄ admissions, receipts, C_hypotheses GENERATION-TIME proposals       ─► field_records, participant_cards, lived_clusters (community × suspected_friction)
K_situations θ → K_situations_law → K_questions knowledge.corpus_questions ─► need      ✗ never reaches K_retrieve (boundary scope excludes `outputs`; the seed is re-sent)
K_revise θ  ◄ materials{lived_situations, lived_clusters, bridges}      ─► REVISE + open_gaps      (open_gaps shadowed by L_judge's; `changes.knowledge_gaps / contradictions / assumptions` silently ignored)
L_judge     Trail hypotheses.judge (revision)                           ─► verdicts (+ Trail's gate gaps) ─► M_loop ─► G_mechanisms … (≤ 3 rounds)
N_jobs θ    ◄ 4-field hypotheses, NO materials                          ─► physical_jobs[{hypothesis_id, job, mechanism}]
N_concepts θ ◄ materials{situations, clusters, field_records, physical_jobs} ─► mechanisms[{…, product_terms[]}], product_concepts[{form_factor, target_moment, buyer, differentiator, variations[]}]
O_territory Trail territory.project ◄ 4-field hypotheses + physical_jobs ─► territories[{territory_id, territory: "product_territory"}] + directive{evidence_gaps: [], 4 UNFILLED templates}
P_reality   HARNESS ◄ that directive verbatim + materials{product_concepts}   ✗ mechanisms.product_terms ✗ territories ✗ physical_jobs        (NO planning step; NO join step)
Q_admit → R_qualify → S_gaps → S_plan supply.plan ◄ concepts, mechanisms ─► per-concept sourcing jobs ─► S_supply → T_admit → T_leads supply.leads → U_qualify → V_score → W_interpret → X_compile
```
Six channels carry information between steps; each finding below names the channel it concerns (READ `service.py`, `transitions.py`, `adapter_step_worker.py`):

| Channel | Built at | Carries | Hard limit |
|---|---|---|---|
| `step.context.hypotheses` | `service.py:421` ← `hypotheses.py:256` | live hypotheses, 4 fields | `contracts/adapter/v1/adapter_step.schema.json` items `additionalProperties: false`, statement ≤ 2000 (STATICALLY VERIFIED) |
| `step.context.evidence_refs` + sibling `evidence.rows` | `service.py:514` `_context_refs`; `evidence_boundary.py:371` `hydrate` | ≤ 200 citable ids; ≤ 60 READABLE rows (field 24 / chunk 20 / graph 10 / other 6 + spillover), stable ref order | §10 |
| sibling `materials` | `service.py:173` `_materials` ← manifest `config.show` | named dotted paths over `outputs` / `input` only — never the ledger; ≤ 400 kB | opt-in per step; not part of `AdapterStepV1`; NOT written to the host journal (`governed_run.py:77–88`) |
| `DOMAIN_OPERATION` inputs | `adapter_step_worker.py:551–556` | manifest-selected paths over `input / options / outputs / context` | `context.hypotheses` is again the 4-field view |
| Trail payload | `adapter_step_worker.py:383` `_payload_for` | 4-field hypotheses + per-operation extras | Trail wire models are `extra="forbid"` (`kernel/contracts.py:27`; `ResearchHypothesisViewV1` `operations.py:862`) (STATICALLY VERIFIED) |
| `harness_action` | `service.py:318` `_compile_harness_action` | NEWEST `research_directive` in outputs + manifest `harness` block + hypothesis ids | `harness_action.schema.json` `additionalProperties: false`; an intent has no `hypothesis_id` / `gap_id` field |

## 3. Compatibility workflow — [TPD] `trail.product_discovery` 2.2.0 (28 steps) — separate, never the basis of a production claim
`A_understand → B_plan / B_retrieve / B_graph → C_hypotheses → D_project → E_filter → F_* → G_mechanisms → H_gaps → I_research → J_admit → K_revise → L_judge → M_loop → N_jobs → O_territory → P_reality → Q_admit → R_qualify → S_supply → T_admit → U_qualify →
V_score → W_interpret → X_compile` (STATICALLY VERIFIED). No `DOMAIN_OPERATION`, no `config.show` on any step, no lenses, primitives, latent structures, population nomination, bridge / portfolio law, lived situations, corpus questions, product concepts or
sourcing plan. Every harness action is Trail's directive verbatim. The only product concept is `W_interpret.product_opportunity.product_concept`, written AFTER product reality and the score. The third-party statements "no semantic representation", "no
cross-domain machinery", "product concept after market search" are TRUE for [TPD] and FALSE for [EPR]. Everything in §5 marked [BOTH] applies here unchanged; everything marked [EPR] does not exist here to be lost.

## 4. Semantic inventory — lifecycle per object ([EPR] unless marked)
Durability is uniform and is not the problem: every step output is durable in `adapter_steps.output` (every loop pass) and `adapter_runs.outputs` (newest pass per step id); the ledger is durable in `adapter_hypotheses` (every revision). The columns that
differ are reach. T = reaches Trail · Q = reaches the query compiler · P = reaches product reality · D = rendered by the dossier.

| Object / field | Created at · by | Source evidence | Stored in | Next consumer → what it ACTUALLY receives | Dropped / ignored | T | Q | P | D |
|---|---|---|---|---|---|---|---|---|---|
| `lenses[]` {name, question} | `B_lenses` · engine `executors.lens_gate` (keyword hit on seed + row text; `lenses.yaml`) | seed + corpus rows | outputs | `C_primitives`, `C_hypotheses`, `C_bridge` via materials | — | ✗ | ✗ | ✗ | ✔ |
| `primitives.drivers / behaviors / adaptations / constraints / workarounds / physical_interactions / latent_values / unresolved_questions / inferred` | `C_primitives` · agent θ | `evidence_refs{field:[ids]}`, `row_relevance` | outputs | `C_population`: `drivers`, `constraints`, `behaviors` only as a TOKEN BAG for the VOI `impact` term (`lived_world.py:270`) | `adaptations`, `workarounds`, `physical_interactions`, `latent_values`, `unresolved_questions`, `inferred`: NO governed consumer (READ: grep over `binding.py` + the 13 bound functions). Not shown to `C_hypotheses`; not in `X_compile.include` | ✗ | ✗ | ✗ | ✗ |
| `primitives.frictions[]` | same | same | outputs | registry nomination ONLY when an item equals a friction-family id verbatim (`lived_world.py:118`); token bag for VOI | free-text frictions never match a family id (run 5: 4 free-text frictions → 0 matches) | ✗ | ✗ | ✗ | ✗ |
| `primitives.shared_predicates[]` | same | same | outputs | registry index lookup `index_by_predicate` (`lived_world.py:117–125`) | non-discriminating: see §6 | ✗ | ✗ | ✗ | ✗ |
| `primitives.physical_jobs[]` (corpus-side) | same | same | outputs | VOI token bag | never joined to `N_jobs.physical_jobs` | ✗ | ✗ | ✗ | ✗ |
| `primitives.transferable_invariants[]` | same | same | outputs | NONE in the governed manifest. Standalone consumers `signal_gate`, `structural_lookup`, `_corpus_analogies` (`executors.py:69,80,131`) are not bound | the whole field (run 5: 3 well-formed invariants, zero readers) | ✗ | ✗ | ✗ | ✗ |
| `primitives.generative_signal` | same | — | outputs | NONE — schema-required, no gate reads it (`signal_gate` unbound) | `false` would not stop a run | ✗ | ✗ | ✗ | ✗ |
| `latent_structures[]` {id, kind (24), text, evidence_refs, possible_populations, applicability_outside_source} | `C_primitives` → re-emitted by `C_lineage` | cited rows, lineage law | outputs | `C_population` → NAMED leads per `possible_populations`, LATENT lead per searchable kind; `C_hypotheses` via materials | `applicability_outside_source` survives only as a lead's `why` string; not shown to `C_bridge`, `G_mechanisms`, `K_revise`, `N_*`; not in `X_compile.include` | ✗ | via lead queries | ✗ | ✗ |
| `population_leads / community_leads` {lane, search_mode, latent_structure_id, expected_frictions, voi, seed_population, channel_queries} | `C_population` · engine | primitives, registry mirror | outputs | `C_hypotheses` (materials), `H_plan` (batch queries), `I_research` (materials), `J_cards` | NO id links a hypothesis to the lead or structure it came from (`hypothesis_state` has no such field) | ✗ | ✔ (name → 6 keywords) | ✗ | ✔ |
| Hypothesis `population / activity / task / context / mechanism / suspected_friction` | `C_hypotheses`, revised by `G_mechanisms` / `K_revise` / `N_jobs` · θ | `supporting_evidence_ids` | LEDGER (every revision) | every later step, every Trail operation, `H_plan`, `N_concepts_law`, `S_plan`, `T_leads`: `{hypothesis_id, revision, status, statement}`. `J_cards` alone reads `suspected_friction` — from the GENERATION-TIME proposal in `outputs.C_hypotheses`, never the revised ledger; SPLIT children are absent there → `unassigned` | six fields × every consumer | ✗ | ✗ | ✗ | ✗ (report reads the 4-field view → columns empty, `report.py:155–165`) |
| Hypothesis `knowledge_support[]` | ledger | cited ids + roles | LEDGER | Trail: count forced to 0 (`research_operations.py:166`) | the whole relation | ✗ | — | — | ✗ (count read from the 4-field view = 0) |
| Hypothesis `knowledge_gaps[]` (per hypothesis, with `gap_id`) | `C_hypotheses` | — | LEDGER | NONE. `gaps.compile` harvests only a step's TOP-LEVEL `knowledge_gaps` (`adapter_step_worker.py:398–401`) | all; and a REVISE carrying `changes.knowledge_gaps` is silently ignored (`hypotheses.py:31, 235–238`; run 5: 4 / 4 `G_mechanisms` transitions) | ✗ | ✗ | ✗ | ✗ |
| Hypothesis `assumptions / falsifiers / contradictions` | `C_hypotheses` | cited ids | LEDGER | result `contradictions` (collected from outputs) | `changes.assumptions / contradictions` on REVISE silently ignored; falsifiers reach nobody | ✗ | ✗ (falsification target absent) | ✗ | contradictions only |
| Hypothesis `field_evidence_ids[]` | ledger | admissions | LEDGER | — | stays EMPTY: Trail's verdict carries `field_evidence_ids` but the wire `ResearchVerdictV1` drops it (`research_operations.py:239`); run 5: 0 on all four although 8 observations were admitted and linked | — | — | — | ✗ |
| `bridges[]` {source, path, target_mechanism, evidence_boundary, hop_refs, gaps, alternatives, falsifiers, status, grounding} | `C_bridge` | hop_refs | outputs (not the ledger) | `C_bridge_law`; `K_revise` via materials | bridge `gaps[]` never reach `gaps.compile`; `target_mechanism` (the mechanism FAMILY) reaches nobody; never re-validated after admission (`grounding: LIVED`, `lived_anchor_ids`, anchor laws unreachable); not in `X_compile.include`; report hard-codes `"bridges": []` (`report.py:214`) | ✗ | ✗ | ✗ | ✗ |
| Trail `priors[]` | `D_project` | lexical overlap | outputs + `trail_prior` refs | agent: opaque ids with `note = prior_role`; no readable row (run 5: 10 unresolved refs at every step) | `label / overlap / section` computed at `gap_compiler.py:170`, dropped at `research_operations.py:218`. No later Trail operation consumes priors. Agent attached 0 priors in run 5 | — | ✗ | ✗ | ✗ |
| Top-level `knowledge_gaps[]` | `G_mechanisms` | — | outputs (newest pass) | `gaps.compile` → `evidence_gaps` with `hypothesis_id` preserved; `gap_id` re-minted `gap_0…` per round | stable gap identity | ✔ | ✔ (question → 6 keywords) | ✗ | ✗ |
| `K_revise.open_gaps[]` | `K_revise` | — | outputs | NONE: `_newest_output_with(state, "open_gaps")` returns `L_judge`'s (`adapter_step_worker.py:402`) | all (run 5 round 2: neither agent gap compiled; Trail's four gate gaps were) | ✗ | ✗ | ✗ | ✗ |
| `research_directive.search_intents[].template` | Trail `gaps.compile` / `territory.project` | `search_query_templates.csv` | outputs → harness action | harness: the template string with slots UNFILLED (`{activity} {task} annoying`) | the binding slot ↔ ledger field never happens anywhere deterministic | — | ✗ | as-is | ✗ |
| `corpus_questions[]`, `need` | `K_questions` · engine | lived clusters, field records | outputs | NONE: `K_retrieve.config.source = outputs.K_questions.need`, but `evidence_boundary.original_needs` resolves `source` over `{input, options}` only (`evidence_boundary.py:116`) → falls back to the seed (run 5: the seed, 3 / 3 rounds) | all. Also template-mangled upstream ("What mechanism reduces camera shake when photrio.com?") because the governed record mapping puts the host into `community` and the excerpt into `workaround` (`binding.py:259–263`) | ✗ | ✗ | ✗ | ✔ (listed) |
| `physical_jobs[]` {hypothesis_id, job, mechanism} | `N_jobs` | cause refs | outputs | Trail `territory.project` (lexical, with the statement); `N_concepts` materials | — | ✔ | ✗ | ✗ | ✗ (in the result, not rendered) |
| `mechanisms[]` {id, name, hypothesis_id, evidence_refs, `product_terms[]`} | `N_concepts` | admitted field evidence | outputs | `N_concepts_law`, `S_plan`, `T_leads` (`product_terms` only inside the supplier-fit join, `executors.py:657–665`) | `product_terms` — the market vocabulary — is never a query input and is not shown to `P_reality` | ✗ | ✗ | ✗ | ✔ |
| `product_concepts[]` | `N_concepts` | admitted field evidence | outputs | `P_reality` via materials (human-readable context only), `S_plan` (terms = name, form_factor, variation names), `S_supply`, `T_leads`, `W_interpret` | no concept id on a product-reality intent or observation; nothing joins competitors to concepts | ✗ | supply only | shown, not compiled | ✔ |
| Trail `territories[]` | `O_territory` | lexical | outputs | nobody (not in `P_reality` materials) | the territory NAME: `ResearchTerritoryV1(territory=t.prior_role)` sends the constant `"product_territory"` (`research_operations.py:247`); run 5 output: `{"territory": "product_territory", "territory_id": "pt-06"}` | — | ✗ | ✗ | ✗ |
| Receipt observation | harness | live web | `adapter_harness_actions`, outputs | Trail admission | no relation / polarity field exists (`harness_receipt.schema.json` observation `additionalProperties: false`, 8 fields); structure rides in free-text `context` and is regex-read back (`binding.py:214–222`) | ✔ | — | — | ✔ |
| Admission `polarity` | Trail `admission.py:223` | role = `contradiction` OR claim starts with `no / not / never / nobody / none` | outputs, `adapter_admitted_evidence` | judgement, qualification, score (`net = supporting groups − contradicting groups`, `engine.py:255–258`), cards (`contradicts`), report | one value per observation for ALL its hypotheses | ✔ | — | — | ✔ |

## 5. Lossy boundaries — ranked
**P0 — break the thesis or are incorrect state**
| # | Boundary | Exists here → projection here → contract carries → disappears | Label · evidence |
|---|---|---|---|
| L1 | Ledger → every issued step | `adapter_hypotheses.state` (21 fields) → `hypotheses.py:256` `context_view` → `{hypothesis_id, revision, status, statement}` (schema-closed) → mechanism, population, activity, task, context, suspected_friction, knowledge_support, gaps, assumptions, falsifiers, contradictions, priors, field evidence | [BOTH] · READ + STATICALLY VERIFIED + HISTORICAL (67 / 67) |
| L2 | Polymath → Trail wire | `_payload_for` forwards that view untouched → `ResearchHypothesisViewV1` (4 fields, `extra="forbid"`) → `HypothesisView(…, knowledge_support_count=0)` → EVERY hypothesis is `unsupported` and WEAKENED `NO_KNOWLEDGE_SUPPORT` at `E_filter` (`judgement.py:110–112`). Run 5: 4 / 4, each citing 2–3 corpus rows. Side effect: `weakened` is not an eligible status for a mechanism (`binding.py:86`) until something else moves it | [BOTH] · READ + HISTORICAL. Known as D4; its consequence for concept eligibility is new |
| L3 | Registry mapping | structured prior fields → `" ".join(field.value …)` → `len(tokens(statement) & tokens(text))`, ties by record id (`gap_compiler.py:157–168`) → Run 5 H1 ("spare batteries … buried in the pack") matched 11 cycling-commuter `wet_dry_transition` seeds on the tokens **`are` + `spare`**; the correct families (`access_latency`, `occupied_hand`, `small_parts`) overlap that statement on ZERO tokens, so no tuning of the lexical matcher can find them. One archetype × 11 activities consumed the 12-prior budget. 1 of 4 hypotheses got an apt family (`cold_dexterity`), 1 arguable, 2 wrong | [BOTH] · READ + EXECUTED (the `tokens()` rule replicated verbatim in a scratch script over the CSV) + HISTORICAL |
| L4 | Trail → Polymath return | coordinates `label / overlap / section` and the territory name are computed, then dropped by the wire mapping (`research_operations.py:218`, `:247`) → the agent and every later step hold opaque ids (`seed-0344`, `pt-06`) | [BOTH] · READ + HISTORICAL |
| L5 | Grammar slots ↔ ledger fields | templates `{activity} {task} {friction_family} {product_territory}` (`search_query_templates.csv`) and ledger fields `activity`, `task`, `suspected_friction` exist with the same names → `compile_research_directive` cannot fill them (no such fields on `HypothesisView`) and no Polymath-side step fills them → the harness receives raw slot strings and improvises | [BOTH] · READ + HISTORICAL (11 field + 4 product-reality templates, all unfilled) |
| L6 | Product reality has no plan and no join | field = `H_gaps → H_plan → I_research → J_admit → J_cards`; supply = `S_gaps → S_plan → S_supply → T_admit → T_leads`; product reality = `O_territory → P_reality → Q_admit` — no domain planning step, no domain join step → directive has `evidence_gaps: []`, four unfilled templates, no concept, no `product_terms`, no territory name | [EPR] · STATICALLY VERIFIED + HISTORICAL |

**P1 — degrade the research loop**
| # | Boundary | What happens | Label |
|---|---|---|---|
| L7 | Query compilation | `executors.channel_queries` = first 6 non-stop tokens of ONE string (gap question, else statement, else lead name). Trail's governance gate gaps are fed through the same path: run 5 round 2 searched `"reach independent observations far"`, `"admitted yet"`, `"corroborate second independent source"` on every channel — 4 of 8 subjects. A gate gap knows its `hypothesis_id`; the compiler cannot look that hypothesis's vocabulary up. Every channel intent is hosted under the first servable Trail intent → `evidence_goal` flattened to `complaint`; 29 of 84 compiled intents dropped over budget | [EPR] · READ + HISTORICAL |
| L8 | Per-hypothesis gaps | ledger gaps never compiled; `changes.knowledge_gaps / contradictions / assumptions` on REVISE silently ignored (`REVISABLE_FIELDS`, no error); `K_revise.open_gaps` shadowed by `L_judge`'s; `C_bridge.gaps[]` never compiled | [BOTH] (bridge part [EPR]) · READ + HISTORICAL |
| L9 | Polarity | §8. Misclassification feeds the score directly (`net = support − against`) | [BOTH] · READ + HISTORICAL (`obs_09`) |
| L10 | Second and third knowledge passes invisible | §10 | [BOTH] · READ + HISTORICAL |
| L11 | `K_questions → K_retrieve` | computed need discarded; seed re-sent | [EPR] · READ + HISTORICAL |
| L12 | Standalone reasoning inputs not carried into the manifest | standalone `hypothesize` requires `[signal, primitives]`, prefers `cross_domain_analogies`, lived situations / clusters (`graph/control_graph.yaml`); governed `C_hypotheses` is shown lenses, leads, latent structures — NOT `primitives`. Standalone `product_ideation` prefers `primitives`, `cross_domain_analogies`; governed `N_concepts` gets neither. `G_mechanisms` and `N_jobs` have no `show` at all | [EPR] · STATICALLY VERIFIED |
| L13 | First-hypothesis fallback | `research_operations.py:170–173`. Reachable: `K_revise.open_gaps` is `[object]` with no required `hypothesis_id`, and the wire `ResearchKnowledgeGapV1.hypothesis_id` is optional. Not observed in run 5 (every gap carried an id). Contrast: admission already refuses `HYPOTHESIS_LINK_MISSING` instead of guessing (`admission.py:209–211`) | [BOTH] · READ |

**P2 — fidelity / reporting**
| # | Boundary | Label |
|---|---|---|
| L14 | Dossier: hypothesis table read from the 4-field view → mechanism / population / activity / friction / support counts empty; `bridges: []` hard-coded; primitives, latent structures, invariants, physical jobs, territories, qualification gate results not rendered although the journal holds the `C_primitives` / `C_bridge` submissions (`report.py:116–244`) | [EPR] · READ |
| L15 | Host journal stores `step`, `status`, `evidence` — not `materials`; automatic-step outputs are absent → what the agent was shown is not reconstructible from the dossier's only source | [EPR] · READ + HISTORICAL |
| L16 | `X_compile.include` omits `primitives`, `latent_structures`, `bridges`, `territories`, `priors`, research plans | [EPR] · STATICALLY VERIFIED |
| L17 | Evidence cards cluster on generation-time `suspected_friction` (stale after REVISE; SPLIT children `unassigned`) | [EPR] · READ |
| L18 | `gap_id` re-minted per round (`gap_0…`), ledger gap ids unused → no stable gap lineage | [BOTH] · READ + HISTORICAL |
| L19 | Bridges are never revisited after admission; anchor laws (`require_lived_anchor`, `min_lived_anchored`) unreachable in the manifest | [EPR] · READ |

## 6. CSV / Trail behaviour — what each registry family does TODAY
| Family (rows) | In Trail's core | In the engine mirror | Role today |
|---|---|---|---|
| `outdoor_activity_niche_seed.csv` (1380; mirror 1386) | flattened to text, token overlap with the statement → `niche_seed` priors → opaque ids → consumed by NO later operation | `index_by_predicate`, `index_by_friction`, `index_by_predicate_friction` (`registry.py:143–150`) → up to 6 `participant — activity` POPULATION leads, lane REGISTRY | Trail: lexical lookup material that dead-ends. Engine: LITERAL niche priors. Neither uses the row as a transformation example |
| `friction_library.csv` (30) | same lexical path → `friction_primitive` prior (run 5: 1 of 48 priors) | family ids gate the friction index | semantic primitive in name; lexical lookup in practice. `workaround_markers` and `observable_metric` are ONE value across all 30 rows (EXECUTED) — only `friction_family` + `definition` discriminate |
| `product_territories.csv` (20) | lexical vs statement + jobs + mechanisms (`territory`, `definition`, `preferred_first_product`) → id only on the wire | — | routing coordinate whose name never arrives; `preferred_first_product` and `common_risks` are ONE value across all 20 rows (EXECUTED), yet `preferred_first_product` is part of the text Trail matches against |
| `search_query_templates.csv` (18) | selected by stage × evidence role; returned with slots unfilled | standalone only (`registry_query_grammars`) | the only family shaped as a GRAMMAR — and its slots are never bound |
| `source_capabilities.csv` (27) | source routing, stage / role suitability, freshness, independence group | — | source + evidence policy — structured, deterministic, working |
| `scoring_rubric.csv`, `config/evidence_gates.json`, `scoring_weights.json` | hard gates, axes, weights | — | qualification + scoring policy — working |
| `niche_candidates.csv`, `activity_taxonomy.csv`, `seasonal_calendar.csv`, `source_registry.csv` | not on the seven operations' path | candidate priors (standalone) | not exercised |

Seed-table structure (EXECUTED, read-only profile): `shared_predicates` is the SAME 8-value string on 1380 / 1380 rows and `participant` the SAME string on 1380 / 1380 → two of the eight "dimensions" carry zero information. Real variation: 459 activities × ~60
situation archetypes (60 tasks, 60 contexts, 59 body / hand states, 60 territory phrases, 38 friction families). The transformation content of the table IS those ~60 archetype rows (task · context · environment · body state · friction family · friction
hypothesis · workaround · territory); the activity dimension is what makes it read as a market list. 10 of the 38 seed families are absent from Trail's `friction_library` (M-014, confirmed again).
Consequences observed (HISTORICAL): (1) engine registry nomination with free-text frictions degenerates to `index_by_predicate[p]` = every seed → first six by row order → run 5 nominated Neighborhood / Bad-weather / Dog / Commuter / Stroller / Power
walking, all `movement_restriction` — unrelated to the primitives; VOI ranked them last (0.095) and the batch of 4 excluded them, so the bias is low but the lane is noise. (2) Trail's token overlap counts the constant columns too (`carry`, `protect`, `set` matched
in run 5), and breaks ties by seed id.
**Answer to the realignment's open question (§5):** niche-seed rows are used as (3) lexical lookup material in Trail and (2) literal niche priors in the engine — never as (1) a structured transformation grammar. **Answer to Question D:** a structured
deterministic mapper is feasible without an LLM — the engine already indexes seeds by predicate × friction family, and ledger fields `task / context / suspected_friction / mechanism` line up with seed columns `task / context / friction_family /
product_territory` — but it needs (a) a NORMALIZED friction-family candidate per hypothesis (free text never equals an id) and (b) discriminating predicates. Where that mapper lives is decision 1.

## 7. Cross-domain capability — what exists, what is not guaranteed
| Stage | Exists (READ) | Run 5 (HISTORICAL) | Guaranteed? |
|---|---|---|---|
| Invariant extraction | `C_primitives` asks for `transferable_invariants[]` and per-structure `applicability_outside_source` | 3 invariants ("when ONE person must both operate and tend a precision tool … access to consumables and steadiness compete for the same two hands"); 4 structures each with an out-of-source statement ("any task where a precision tool consumes something and the operator cannot leave position") | produced, but `transferable_invariants` has NO consumer and `applicability_outside_source` becomes a `why` string |
| Population candidates | `possible_populations` → NAMED leads; searchable kinds → LATENT leads whose queries use the structure's own language, never a group name (`lived_world.py:196–231`) | all 4 structures named the seed's population (landscape / wildlife / backpacking photographers); 3 LATENT leads compiled | nothing requires a population outside the source or the seed |
| Ranking | `seed_population_discount: 0.5`; LATENT yield 0.6 | the two non-seed LATENT leads ranked FIRST (0.34 vs 0.17); batch = 2 LATENT + 2 CORPUS | ✔ the engine already prefers non-seed populations |
| Field search for the unknown population | lead `channel_queries` ride into `H_plan` | `"replenishing consumable stored away point use"`, `"steadiness comes rigs added mass slow"` — six-keyword fragments of abstract prose | compiled, but the form cannot find a community (L7) |
| Lead → hypothesis | — | hypotheses took the seed population | NO id links a hypothesis to a lead / structure; a population discovered through a LATENT lead has no typed route into a hypothesis except the agent noticing it |
| Bridge | path ≥ 3 hops, `first_inference_at`, hop refs before the boundary, gaps covering speculative hops, alternatives, falsifiers; `WORKING_ANALOGY` + `exploratory` capped at 1 (`policies.yaml portfolio.max_exploratory`) | every bridge started in the source domain ("on a film set, media kept away from the camera…") and crossed at the declared boundary — the transfer hop is explicit and lawful | the cap limits DECLARED analogies only; a transfer written as `WORKING_HYPOTHESIS` is admissible. The law neither blocks nor demands transfer |
| Analogy lookup | standalone `structural_lookup`: invariant-bounded registry + corpus-fact analogies → `cross_domain_analogies`, preferred input of `hypothesize` and `product_ideation` | not in the manifest | the migration mapped it to Trail `registry.project` (`CAPABILITY_MAP.md:27`, `ECOMMERCE-MIGRATION-HARVEST-MAP.md:47,81`) — an operation that runs AFTER hypotheses, matches lexically on the statement, is not invariant-bounded and returns opaque ids. The function was dispositioned, not performed. `signal_gate` likewise: `generative_signal` has no reader |
| Collapse back to the source vocabulary | — | — | yes, at three places: Trail sees only the statement; queries are statement / question keywords; product-reality templates want `{activity}` |

**Answer to Question F:** a source-domain observation CAN become an out-of-domain population lead without the seed naming it (the LATENT lane, ranked first). Whether it becomes a HYPOTHESIS and survives to research is not guaranteed by any contract and was
not tested. Per the directive, an explicit analogy stage is justified only by execution evidence; the evidence today says: bind what exists first (`primitives` + invariants into `C_hypotheses`; decide on `structural_lookup`), then measure with §15.

## 8. Research-loop fidelity
| Link | As built | Verdict |
|---|---|---|
| hypothesis → gaps | top-level `G_mechanisms.knowledge_gaps` carry `hypothesis_id` (schema-required) → preserved through `gaps.compile` (run 5: 2 per hypothesis, 4 / 4) | works ONLY through that one field; L8 for every other gap source |
| gaps → intents | Trail intents are stage × role templates, identical for every hypothesis; engine channel intents are per gap, round-robin so each gap gets its first query before any gets a second; linkage lives in the `intent_id` string (`q-complaint:reddit:gap_0`) | per-gap fairness exists; typed intent → hypothesis linkage does not |
| intents → receipt | `tool_trace.search_intent_id`; observations carry `hypothesis_ids` (run 5: 6 of 20 linked > 1 hypothesis) | works |
| receipt → admission | unknown link → typed rejection `HYPOTHESIS_LINK_MISSING`; single live hypothesis → auto-link | correct pattern — the one to copy for L13 |
| admission → ledger | evidence ↔ hypothesis relation lives ONLY in admission rows; ledger `field_evidence_ids` stays empty; φ CHALLENGE contradictions dropped on the wire (M1-01) | relation not in the hypothesis state |
| revision | REVISE applies 7 fields; everything else in `changes` is dropped without an error; the agent is told `changes: object` | silent loss |
| H1 → H1 program | no per-hypothesis program object exists; preserved de facto via gap ids | H1 / H2 / H3 separation holds for agent-authored top-level gaps only |

**Question I — contradiction today:** an OBSERVATION-GLOBAL property assigned by Trail from the claimed role (`contradiction`) or a leading negation word (`admission.py:28, 223`). The receipt has no field for it. One role per observation, so marking
contradiction erases the friction / behaviour role; one polarity for all linked hypotheses. Run 5 `obs_09` ("owns two strap clips … you never go back"; harness note "COUNTER-evidence: an existing product already solves ready-carry") → role `behavior`,
claim does not start with a negation → admitted `supporting`. Note what it contradicts: not the friction (it confirms it) but the unmet need — a relation to a hypothesis, which a global flag cannot express. Minimum target per the directive:
`{observation_id, hypothesis_id, relation: SUPPORTS | CONTRADICTS | NEUTRAL}`; Polymath's admission contract already allows `neutral`, Trail's `Polarity` does not. The receipt is a cross-repo wire contract (`harness_receipt.schema.json` ⇔ Trail
`ReceiptObservation`, both closed) → it changes in both or in neither.

## 9. Product-reality fidelity (Question G)
`P_reality` receives (HISTORICAL): `harness_action{objective: "map current products, alternatives, reviews, prices, and saturation", hypothesis_ids ×4, evidence_gaps: [], search_intents: q-review "{activity} {product_territory} review problem", q-return
"{product_territory} returned broke leaked", q-price "{product_territory} price buy", q-best "best {product_territory} for {activity}"}` + materials `{product_concepts}` + the 4-field hypotheses. It does NOT receive `mechanisms[].product_terms` (run 5 had the
right vocabulary ready: "backpack strap camera clip", "camera holster for hiking", "arca swiss quick release plate", "neoprene camera wrap"), `physical_jobs`, the projected territories, or any per-concept intent. Why real runs searched registry territory terms: the ONLY
compiled search objects are Trail's four templates keyed on `{product_territory}`; the concepts arrive as reading material beside them. On the way back nothing joins competitors to concepts (no `concept:` convention, no join step), so `R_qualify` counts per
hypothesis and the dossier has no "existing products" section. Stage order is NOT the defect and needs no change. Baseline search (READ): the engine has no competitor / product-reality planner — the standalone graph goes `product_ideation → supplier_search`;
`product_anchored.py` and `market_discovery.py` are other workflows. The reusable pattern is `_op_supply_plan` + `executors.sourcing_plan_compiler` (per-concept jobs, Trail governance fields untouched, Trail intents first, budget respected).

## 10. Side questions from the realignment
- **The 60-row cap — does it change what the agent reasons over? YES.** `context.evidence_refs` (≤ 200, citable) ≠ `evidence.rows` (≤ 60, readable), filled in stable ref order: admitted field evidence first, then knowledge refs in step-acceptance order, graded
  rows first. Run 5: at all 20 agent / harness steps the readable knowledge rows came exclusively from the first pass (`B_plan` / `B_graph`); 0 of the 107 rows `F_plan` retrieved for the hypotheses and 0 rows of any `K_retrieve` were ever readable.
  `G_mechanisms` ("revise its mechanism from the corpus evidence") read the same rows as `C_primitives`; as field evidence arrived, chunk rows shrank 44 → 22. Later rows are citable blind. (HISTORICAL + READ `evidence_boundary.py:58–63, 371–413`.)
  Separate retrieval fact, recorded not diagnosed: every evidence-boundary call in run 5 returned 0 chunk rows (`corpus_explorer_used: false`, `compiled_queries: 0`); `/retrieve/plan` carried the run.
- **`content` axis:** structurally unreachable. `AXIS_ROLES["content"] = ("content",)` (`scoring/domain/engine.py:27`); no row of `source_capabilities.csv` supports a `content` role and the manifest's `evidence_roles` has none → admission can never assign it → the axis is
  always the neutral fill (0.5 at half confidence). (READ + EXECUTED role histogram.) Benchmark only, per the owner.
- **`growth` axis:** `AXIS_ROLES["growth"] = ("seasonality",)` — seasonality stands in for growth by definition; no growth role exists. Run 5 admitted no seasonality evidence → neutral fill. (READ + HISTORICAL.)

## 11. Questions A–I — short answers
A — a MIXTURE: durable typed step outputs (primitives, latent structures, leads, bridges, jobs, mechanisms, concepts) + one durable typed ledger; not one object, and joined only by `hypothesis_id` and `mechanism_id` (the lead / structure → hypothesis link is missing). ·
B — not necessary on this evidence; §12 / §13. · C — §5 (one row per boundary named in the directive). · D — §6 and §13 decision 1. · E — §6. · F — §7. · G — §9. · H — §8. · I — §8.

## 12. Architecture options per correction (reuse · projection · contract extension · Trail change · new state)
| Correction | Reuse / config only | Projection (read view) | Contract extension | Needs the Trail core | New durable state |
|---|---|---|---|---|---|
| Rich hypothesis state to agent steps | — | assemble in `service.advance` next to `context_view` (it already holds the full ledger rows and `outputs`); deliver through `materials` by letting `show` address the ledger | or widen `adapter_step.context.hypotheses` (closed schema) | no | none |
| Rich state to DOMAIN operations (`H_plan`, `J_cards`, `N_concepts_law`, `S_plan`) | — | same view reachable from `exec_domain`'s scope | — | no | none |
| `primitives`, invariants, latent structures into `C_hypotheses` / `N_concepts` / `G_mechanisms` / `N_jobs` | manifest `config.show` entries | — | — | no | none |
| `K_questions.need` reaching `K_retrieve` | — | — | one narrow exception in `original_needs` for a DOMAIN-compiled need (the guard exists to stop reformulations of the seed) | no | none |
| Lead / structure → hypothesis linkage | — | — | optional `lead_ids[]`, `latent_structure_ids[]` on the hypothesis proposal (manifest schema; the ledger may ignore or store them) | no | none |
| REVISE keeps gaps / contradictions / assumptions | — | — | extend `REVISABLE_FIELDS` handling, or refuse unknown `changes` keys loudly | no | none |
| Per-hypothesis gaps compiled | `_payload_for`: harvest ledger gaps + `K_revise.open_gaps` beside Trail's | — | — | no | none |
| Query compilation from semantic state | engine compiler given the view (population, activity, task, friction, workaround, mechanism, falsifier) instead of one string; gate gaps resolved through their `hypothesis_id` | the view | — | no (Trail keeps role, source, freshness, stage, budget) | none |
| Template slots bound | Polymath-side deterministic fill of `{activity} {task} {friction_family} {product_territory}` in `H_plan` / a reality plan | the view | — | OR Trail fills them once it receives the fields | none |
| Product reality plan + join | two DOMAIN operations modelled on `supply.plan` / `supply.leads` | the view | a `concept:` convention in observation `context` (already used for supply) | no | none |
| `knowledge_support_count` | — | — | — | YES (wire field + mapping) | none |
| Prior / territory coordinates returned | Polymath can resolve ids against its own copy of the CSVs as a stop-gap | — | — | YES for the real fix (`ResearchPriorV1`, `ResearchTerritoryV1`) | none |
| Structured registry mapping | — | — | — | decision 1 | none |
| First-hypothesis fallback | Polymath never sends a gap without `hypothesis_id` (typed refusal on its side) | — | — | YES to remove it at source | none |
| Hypothesis-relative relation | — | — | receipt + admission, BOTH repos | YES | none |
| Dossier fidelity | render from the journal submissions + the result; journal stores `materials` | the view in the result | `X_compile.include` | no | none |

TRAP for whichever option widens `context.hypotheses`: `_payload_for` forwards `ctx.hypotheses` to Trail untouched and Trail's wire is `extra="forbid"` — every Trail operation would be refused unless the payload builder projects back to the four wire fields.
(STATICALLY VERIFIED: `adapter_step_worker.py:387–394`, `trail_client.bounded_request`, `kernel/contracts.py:27`.)

## 13. Owner decisions — evidence and options (not decided here)
**Decision 1 — where structured deterministic mapping lives**
| Option | What the evidence says | Ownership consequence |
|---|---|---|
| A — Trail upstream, then re-pin | The only place that can fix L2 (support count), L4 (returned coordinates), L13 (fallback), L9 (relation) at the source; all four sit behind closed wire models. Structured matching would replace one function body (`derive_registry_coordinates`) with field-to-field comparison; the lexical branch can stay as the fallback | Trail's own governance gate + an owner-accepted ADR + a new byte-pin (ADR-0021). Trail stays the single mapping authority. Slowest path |
| B — Polymath-side normalization before Trail | Everything in §12 marked "no" is reachable without touching the core: slot filling, per-hypothesis gaps, semantic queries, product-reality plan, id → CSV resolution. The engine already owns a structured index over the same seeds | Creates a SECOND place that reads the registry semantically (the M-014 two-registries situation gets deeper). L2 / L9 / L13 stay wrong inside Trail; Polymath can only avoid triggering them. Trail's lexical priors stay inert |
| C — staged | B-class fixes are independent of A-class fixes (no ordering conflict found); A-class items are four small wire / mapping changes, separable from a mapper rewrite | Needs an explicit rule that the Polymath-side normalizer is retired or demoted when Trail gains the fields, or the second authority becomes permanent |

Registry DATA is part of the same decision: the constant `shared_predicates` / `participant` columns and the 10 undefined friction families live in the byte-pinned `governance/trail/data` and in the engine mirror; regenerating discriminating predicates from the
~60 archetype rows is deterministic work, but it is a Trail data change (A or C), not a Polymath change.

**Decision 2 — the canonical latent representation**
| Option | Evidence |
|---|---|
| A — replaces the statement at the Trail boundary | impossible without decision 1 = A / C (closed wire); `normalise(statement)` also drives Trail's redundancy / dedupe |
| B — travels beside it | same wire constraint; compatible with keeping the lexical fallback |
| C — derived view from existing state | everything the audit found is already durable and addressable by `run_id + hypothesis_id + mechanism_id`; the two things a view cannot reconstruct are the lead / structure → hypothesis link and post-REVISE gaps / contradictions — both small contract extensions, neither a new store. No finding requires a second source of truth |

**Decision 3 — re-issue `MIGRATION_POLICY.md` / `EXECUTION_PLAN.md` or keep the realignment additive:** no code evidence bears on it. Observed only: `AGENT_OPERATING_DOCTRINE.md` priority 1 ("Working ecommerce E2E") and "generalize only after demonstrated need" now read against the realignment's thesis; `CONTINUATION.md` already treats the realignment + directive as controlling.

## 14. Recommended minimal change set (NOT implemented; ordered by dependency; every item waits for the owner)
Independent of decision 1 (Polymath / manifest / engine only):
1. `OpportunitySemanticViewV1` as a DERIVED read projection per hypothesis — ledger state (latest revision) + its bridge + its linked leads / latent structures + its physical jobs, mechanisms (`product_terms`), concepts + its admitted evidence with relation — built where `context_view` is called; consumers opt in. No new table.
2. Manifest `show` parity with the standalone context contracts: `primitives` (incl. `transferable_invariants`) and `latent_structures` into `C_hypotheses`, `C_bridge`, `G_mechanisms`, `N_jobs`, `N_concepts`; mechanisms + territories + jobs into `P_reality`.
3. Two contract extensions: linkage ids on the hypothesis proposal; REVISE keeps gaps / contradictions / assumptions (or refuses unknown `changes` keys).
4. Gaps: ledger gaps + `K_revise.open_gaps` + bridge gaps reach `gaps.compile` with their `hypothesis_id`; Polymath refuses (typed) any gap without one, so the pinned fallback is never reached.
5. Query compilation consumes the view; governance gate gaps resolve through their hypothesis; template slots bound deterministically from `activity / task / suspected_friction` (+ territory name).
6. Product reality: a plan operation and a join operation modelled on `supply.plan` / `supply.leads`; `concept:` convention in observation context.
7. `K_questions.need` reaches `K_retrieve`; field-record mapping stops putting the host in `community` and the excerpt in `workaround`.
8. Readable-evidence budget: later knowledge passes get a share of the 60 rows (or per-step recency), so a second retrieval can be read.
9. Dossier + journal: render hypothesis fields, bridges, primitives / invariants, jobs, qualification gates, existing products; journal records `materials`.
Dependent on decision 1 (Trail core): 10. `knowledge_support_count` on the wire. 11. return prior `label / section` and the territory name. 12. remove the first-hypothesis fallback (typed refusal). 13. hypothesis-relative `SUPPORTS / CONTRADICTS / NEUTRAL` on receipt + admission (both repos). 14. field-aware registry mapping with the lexical branch kept as fallback; registry data discriminators.
Decide from execution, not now: binding `structural_lookup` / `signal_gate`; any analogy stage; any new durable IR.
Fence note for whoever implements: items 1, 3, 4, 8 touch `shared/` or `workers/` → stale-bundle fence, open runs = 0, bounce after commit. Manifest edits (items 2 and 6) are inert until a bounce.

## 15. Benchmark design — non-presupposing cinema benchmark (DESIGN ONLY; to run AFTER implementation, staged per the testing policy)
**Hypothesis under test:** with a seed that names no market, population, product category or product problem, the system derives latent structure from `cinema`, nominates at least one population not named by the seed, carries it into a typed hypothesis through an earned bridge, researches it with hypothesis-specific queries, and ends in a product opportunity or a governed refusal.
| Element | Design |
|---|---|
| Seeds (input = `{seed, corpus_ids: ["cinema"], geography, freshness_days}` only; `category`, `constraints` unset) | S1 source-situation: "How a camera crew keeps equipment working through a shooting day — who handles what, what is moved between setups, what goes wrong in the hand-offs." · S2 mechanism-level: "Moments in the material where one person has to do with two hands what is normally divided between several people." · S3 open: "Recurring physical handling problems described in this material." Each names the SOURCE domain at most |
| Lint before start (deterministic) | seed contains no token from a deny list built from: registry activity names, territory names, product nouns, consumer-population nouns; reviewer confirms no target market |
| Frozen baseline | run 5 (presupposing seed) — reuse, do not re-run |
| Stage T1 — abstraction (read from `outputs.C_primitives`) | ≥ 1 `transferable_invariant`; ≥ 1 latent structure whose `possible_populations` contains a name with `seed_population == false` AND outside the cinema lexicon; every cited row classified non-IRRELEVANT |
| T2 — nomination | that population (or a LATENT lead) is in the VOI batch |
| T3 — hypothesis | ≥ 1 ledger hypothesis whose `population` is such a population, linked (`lead_ids` / `latent_structure_ids`) to its origin; its bridge starts in corpus evidence, declares the transfer hop as `first_inference_at`, carries gaps covering the speculative hops |
| T4 — Trail normalization | its friction family / territory coordinates are judged apt by a blind reviewer against the archetype table (pre-registered rubric); record lexical-only vs structured if both exist |
| T5 — research fidelity | every compiled query for that hypothesis contains ≥ 1 term from its population / task / friction vocabulary and none of Trail's governance phrases; ≥ 1 admitted observation linked to it, or an honest zero |
| T6 — revision | the hypothesis is revised, split, weakened or killed citing admitted evidence; contradicting observations recorded as CONTRADICTS against the right hypothesis |
| T7 — concepts → reality | product-reality queries derive from concept / mechanism vocabulary, not a territory id; competitors joined per concept |
| T8 — outcome | a Trail score OR a typed refusal; BOTH are passes. A run that stays inside cinema is a valid result only if the transfer was considered and rejected in writing (bridge alternatives) — transfer is never forced |
| Controls | negative control: a corpus slice with no physical-handling content → `generative_signal: false` should end the run (tests the unbound gate). Confound control: same agent model, same budgets as run 5; the WILDCARD 0-row behaviour diagnosed first, or the benchmark measures retrieval, not transduction |
| Size | smoke = S1 once; expand to S2, S3 only if S1 leaves a question open; each run ≈ run 5's spend class; per-action authorization |
| Not a pass criterion | a positive score; an out-of-domain product; agreement with any expected niche |

## 16. Do-not-change list (protect what works)
The adapter runtime, ledger, lineage, budgets, typed gaps and lease model · `DOMAIN_OPERATION` out-of-process binding (the ONE door) · stage ORDER, including `N_concepts` before `P_reality` and hypotheses before field research (M-009) · lineage law, bridge law,
portfolio law, lived-situation law, product-set law · LATENT / NAMED nomination, VOI ranking, the seed-population discount · one evidence id space (M-008) · Trail as the only admission, judgement, qualification and score authority; LAW 1; no LLM in Trail;
snapshot / compiler architecture · Trail's lexical matcher until a replacement is proven compatible · admission's typed `HYPOTHESIS_LINK_MISSING` · source routing, freshness, independence groups · the CSV registry (extend toward domain-invariance;
no per-corpus overlay) · `supply.plan` / `supply.leads` (the template for product reality) · per-friend principals and the hosted surface · the byte-pinned core until decision 1.

## 17. Owner's fourth note (chat, 2026-09-21, received while this audit was being written) — claims confirmed vs corrected
| Claim | Verdict |
|---|---|
| `knowledge_support_count = 0` → wrongly `NO_KNOWLEDGE_SUPPORT`; P0 correctness | CONFIRMED (L2). Addition: the fix cannot be made from Polymath — the wire has no such field |
| Trail computes coordinates and discards them; territory name lost | CONFIRMED (L4) |
| Polarity under-specified | CONFIRMED (L9, §8); the heuristic is now located |
| Standalone engine expects `primitives`, `cross_domain_analogies`; governed path drops them; same for ideation | CONFIRMED (L12) |
| `transferable_invariants` has no meaningful consumer | CONFIRMED (§4) |
| Template slots unfilled although typed values exist | CONFIRMED (L5) |
| `shared_predicates` and `participant` constant on all 1380 seeds; nomination falls back to row order | CONFIRMED (§6) |
| Cycling-commuter seeds matched on shallow words like "wet" and "pack" | CORRECTED: the matched tokens were `are` and `spare` (overlap 2); the point stands, more strongly — the apt families share zero tokens with the statement |
| Product reality lacks a planning stage; look for an existing planner first | CONFIRMED; baseline search done — none exists; `supply.plan` is the pattern (§9). Also missing: the JOIN stage |
| "Semantic parity restoration, not a rebuild" | SUPPORTED by §4 / §12: no finding needs new durable state |
| `signal_gate` / `structural_lookup`: intentional or accidental? | ANSWERED: intentional disposition — mapped to a typed gap and to Trail `registry.project` in the harvest map — but neither mapping performs the function today (§7) |
| The wire SHOULD carry a large structured hypothesis object to Trail | NOT ADOPTED HERE: that is decisions 1 + 2. Evidence to weigh: the wire is closed and byte-pinned; the directive asks for the smallest sufficient projection (candidates with a demonstrated deterministic use today: `knowledge_support_count`, `activity`, `task`, `suspected_friction` / family candidates, `mechanism`, per-hypothesis gaps) |
| Repair the CSV discriminators | Evidence supports the defect; the change is Trail DATA inside the pinned core → decision 1 |
| Benchmark five corpora | The owner's queue names cinema first; §15 stages it. Other corpora are an expansion after the first result, per-action |
| Not in the note, found here | L7 governance gaps compiled into keyword searches · L8 REVISE silently drops gaps / contradictions · L10 second-pass knowledge never readable · L11 `K_questions` never reaches retrieval · ledger `field_evidence_ids` always empty · L14–L16 dossier / journal / result omissions · `content` axis unreachable, `growth` = seasonality |

## 18. Not examined / limits
Question 10 of the realignment (graph as traversal grammar) — not examined beyond noting that `B_graph` / `F_graph` contributed 10 + 9 graph rows and that `_corpus_analogies` (unbound) is the only code that reads graph facts semantically. · Why the evidence-boundary
WILDCARD pass returned 0 rows — recorded, not diagnosed. · Runs 1–4 were not re-read. · No Trail function was executed; the token-overlap figures come from a verbatim re-implementation of `tokens()` over the CSV, not from Trail. · `hypotheses.judge`
REVISION-stage thresholds, qualification and scoring internals beyond the axis ↔ role table were read only as far as polarity and axes required. · The agent's own context between steps (a single LLM session carried memory across steps in run 5) is
outside every contract; all "receives" statements above are about what the CONTRACT delivers.
