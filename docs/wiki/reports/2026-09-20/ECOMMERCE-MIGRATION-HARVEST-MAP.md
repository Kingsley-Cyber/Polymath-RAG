---
title: "Ecommerce migration — harvest map (what the original controller already does, what the governed path duplicated, what was lost, what still needs connecting)"
date: 2026-09-20
status: measured
method: "READ-ONLY. Four sub-agent code-reading passes over TRAIL_AGENT_AUTORESEARCH, Trail A41 and the polymath-v4 adapter + direct checks by the primary agent of every claim that decides what is retained, replaced or reconnected. Nothing was run: no tests, services, database, controller command or web call. Run artifacts were read as files."
controller_head: "a7baa66 (GitHub main = a7dbc52; the engine files cited here are unchanged from GitHub except 2 lines in lived_world.py and 6 in the graph file)"
polymath_head: faedb20
trail_tree: "A41 de64d84 (untouched)"
feeds: "docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md (migration / recovery reframe)"
last_reviewed: 2026-09-20
---

# Principle: harvest behaviour, not architecture
Owner direction 2026-09-20: this is a MIGRATION / RECOVERY project, not "finish TG5". The goal is niche-informed product
ideation for ecommerce. Keep the original controller's proven ecommerce intelligence, Polymath's evidence-only knowledge
boundary, Trail's deterministic authority and the existing renderer; throw away duplicate glue only after the unified path
proves itself. **No code until the owner has reviewed this map.**

Evidence classes used throughout: **REAL** executed on real input · **FIX** executed with fixtures only · **CODE**
implemented, never executed for this purpose · **DOC** documented only. "Verified" = checked by the primary agent against
current code or a run artifact; everything else is reader-reported with file:line.

## 0. What the two systems have actually demonstrated
| | Original controller | Governed path |
|---|---|---|
| Complete real run | ONE: `calib_books_01` (2026-09-04) → `QUALIFIED_LEADS`. Verified in the state file: 5 concepts × 2 variations, 135 supplier candidates (96 Alibaba / 39 CJ), 8 leads with price + MOQ, 146 observations — ALL Reddit, 78 field records, 62 population leads, 3 SUPPORTED / 2 REJECTED hypotheses | none. R0 / R1 complete with FIXTURE receipts and hard-coded answers; R2a (real) died at `L_judge` |
| Honest negative run | `calib_novel_02`: all 4 hypotheses rejected on field evidence, 0 concepts (a correct refusal) | R2a typed gap was a DEFECT (D1), not a refusal |
| Caveats | that run used the since-deleted `ecom-meta-v1` corpus and the since-retired answer lane; 0 / 146 observations carry a harvest date (none could enter a receipt today); supplier name hard-coded `unresolved` (`sourcing_exa.py:49`, verified); CJ produced 0 leads (price empty, MOQ = policy constant); competing-product research never ran; no rendered HTML exists for it; canary 2 of 9 FAILED on it. The SQLite loop memory was not opened | product / supply / qualify / score stages never ran on real input; 7 run defects (D1–D7) + 12 reviewer findings (M1-01..12) |

## 1. One owner per authority (target)
| Responsibility | Owner |
|---|---|
| Corpus retrieval, Corpus Explore, graph retrieval, EvidencePacket, knowledge provenance | Polymath |
| Run state, durable hypothesis ledger, budgets, cross-system lineage, the ONLY caller of Trail | governed adapter |
| Niche interpretation, population discovery, research / channel planning, hypothesis STRUCTURE checks, product concepts + variations, product-reality and sourcing procedures, parsers, the mechanism × supplier join | harvested controller library (+ the agent for the reasoning itself) |
| Live-world execution, tool and browser choice | host harness |
| Evidence admissibility, freshness, independence, hypothesis judgement, qualification, score / refusal, registry data | Trail |
| HTML dossier | the controller's existing renderer |
| Advisory red team (independent reviewer, triage priority, anchor / thin arithmetic) | controller library — ADVISORY, never a ledger transition |

## 2. Governed step → harvest map (all 28 steps)
Evidence key: **REAL** = executed on real input · **FIX** = executed with fixtures only · **CODE** = implemented, never executed for this purpose · **—** = nothing to harvest.
Controller evidence comes from run `calib_books_01` (2026-09-04) unless noted; governed evidence from R0 / R1 (fixtures) and R2a (real, to `L_judge`).

| # | Governed step | Capability the step needs | Existing controller implementation | Controller proof | Direct reuse? | Glue required | Duplicate now in the adapter / Trail? | Final owner |
|---|---|---|---|---|---|---|---|---|
| 1 | `A_understand` VALIDATE | understand the niche: latent interpretation, lenses, structural analogies | `prompts/latent_interpretation.md` · `executors.lens_gate` · `executors.structural_lookup` | REAL | yes (functions over dicts + a prompt) | run them on the agent side before / at `C_hypotheses`; the adapter step itself stays input validation | no — the adapter has none of it (LOST) | ecommerce library + agent |
| 2 | `B_plan` | corpus query formulation | `corpus_queries.compile_queries` (3–5 typed reformulations) | REAL | not needed | none — Polymath's own plan lane does this (`/retrieve/plan`) | YES: controller compiler vs Polymath corpus-plan | **Polymath** (retire the controller's compiler in governed mode) |
| 3 | `B_retrieve` | evidence-only corpus knowledge | `corpus_polymath.explore_corpus` (same `/chat/evidence`) | REAL (TG3) | not needed | none | YES: two clients of one backend | **Polymath + adapter** |
| 4 | `B_graph` | graph knowledge | controller reads graph facts from plan rows (`_corpus_analogies`) | REAL | — | none | same backend | **Polymath + adapter** |
| 5 | `C_hypotheses` θ | bridge hypotheses with admissible hops, portfolio breadth, lived anchors | `prompts/bridge_hypothesis.md` · `bridge.validate_bridge / validate_hop_refs / validate_portfolio` · `lived_world.validate_hypothesis_anchors` | REAL (5 and 4 hypotheses; 2 died on field evidence) | yes as an agent-side quality gate BEFORE `adapter_submit` | map controller hypothesis fields ↔ adapter hypothesis fields; ids come from the adapter | PARTLY: adapter validates citations + schema only | agent + ecommerce library (structure) · **adapter** (durable ledger) |
| 6 | `D_project` T `registry.project` | registry priors | controller's `structural_lookup` over its registry MIRROR | REAL | no | none | YES: mirror of Trail data | **Trail** |
| 7 | `E_filter` T `hypotheses.judge` | kill / weaken unsupported or redundant hypotheses | `evaluator.build_dossier` + separate reviewer subagent + `apply_evaluations`; `executors.triage` | REAL (4 verdicts per run) | advisory only | reviewer verdicts become ADVISORY input to the agent's next revision, never a ledger transition | YES: two judges | **Trail** (authority) · controller reviewer = advisory red team |
| 8–10 | `F_plan` `F_retrieve` `F_graph` | mechanism-level corpus questions | `lived_world.compile_corpus_questions` (questions from field clusters) | REAL (12 questions per run) | candidate | the adapter derives needs from hypothesis STATEMENTS (hit by D2); the controller derives QUESTIONS from clusters — decide which need the boundary receives | YES: two need-builders | **Polymath** retrieval · need wording = open design point |
| 11 | `G_mechanisms` θ | mechanisms + what only the field can close | `prompts` for mechanism / gaps; `executors.gap_compiler` (gap objects) | REAL | yes (agent side) | gaps must be emitted in the adapter's `knowledge_gaps` shape | PARTLY | agent + library · **adapter** ledger |
| 12 | `H_gaps` T `gaps.compile` | WHAT evidence is required, roles, freshness, budget | — (Trail's job) | — | — | — | the controller's gap compiler also sets roles / freshness | **Trail** |
| 13 | `I_research` HARNESS | HOW to research: populations, communities, per-channel queries, extraction, curation | `lived_world.nominate / rank_leads / queue / cards / gate` · `executors.channel_queries` + `_CHANNEL_TEMPLATES` · prompts population_scout / community_instantiate · `executors.comments` | REAL (62 leads → 78 field records → 15 clusters; 146 observations; Reddit only) | yes, as the harness procedure | directive + hypotheses + gaps IN → controller planning; observations + harvest dates OUT → `adapter_receipt.py` (exists) | YES: in R2a the queries were improvised by hand; Trail's templates are generic | **ecommerce library + host harness** |
| 14 | `J_admit` T `evidence.admit` | what counts as evidence | `verifiers.admit_observations`, `independence_groups` | REAL | no | none | YES: two admission systems | **Trail** (controller's = standalone only) |
| 15 | `K_revise` θ | revise on admitted evidence; contradictions | `prompts/contradiction.md` (challenge), `allocation.starved_rejections` | REAL (13 challenges) | yes (agent side) | admitted ids come from the adapter view | PARTLY | agent + library · **adapter** ledger |
| 16 | `L_judge` T | deterministic revision judgement | `apply_evaluations`, status lattice | REAL | advisory only | — | YES | **Trail** |
| 17 | `M_loop` | loop / stop control | `transitions.py` round caps, forced-verdict laws, `population_gate` | REAL | no | none | YES: two loop controllers | **adapter** |
| 18 | `N_jobs` θ | physical jobs, mechanisms, PRODUCT CONCEPTS + VARIATIONS | `prompts/product_ideation.md` · `ideation.validate_concepts` · `schemas/product_concept.json` (≥ 2 variations) | REAL (5 concepts × 2 variations) | yes (agent side) | the adapter contract has `physical_jobs` only; concepts + variations need a carrier (`product_opportunity` is free-form today) | no — LOST in the governed contract | agent + ecommerce library · adapter carries it |
| 19 | `O_territory` T `territory.project` | product territories | controller registry mirror (`product_territories.csv`) | REAL (mirror) | no | none | YES: mirror | **Trail** |
| 20 | `P_reality` HARNESS | existing products, alternatives, reviews, prices, complaints | `executors` channel table: `opencli amazon search / discussion`, retailers via Exa + reader | **CODE** — never executed by either system on real input | yes, as the harness procedure | per-concept product-reality plan does not exist in the controller; only channel commands do | no | **ecommerce library + host harness** (governed stage KEPT) |
| 21 | `Q_admit` T | admission | as 14 | — | no | — | YES | **Trail** |
| 22 | `R_qualify` T | market-delta gates | — | — | — | — | controller has no equivalent | **Trail** |
| 23 | `S_supply` HARNESS | supplier research per concept / variation | `executors.sourcing_plan_compiler` · `sourcing_exa.py` · `executors.supplier` · `_parse_price` · `_parse_moq` | REAL (135 candidates; 8 Alibaba leads with price + MOQ; CJ 0 leads; supplier name unresolved) | yes, as the harness procedure | concepts IN → sourcing plan; supplier rows + harvest dates OUT → `adapter_receipt._supplier_items` (exists) | directive side broken (M1-07) | **ecommerce library + host harness** |
| 24 | `T_admit` T | admission | as 14 | — | no | — | YES | **Trail** |
| 25 | `U_qualify` T | supply gates | — | — | — | — | — | **Trail** |
| 26 | `V_score` T | the only score / refusal | `executors.scoring` evidence_score | REAL | no | none | YES: two scores | **Trail** (controller score = standalone only) |
| 27 | `W_interpret` θ | explain the outcome; concept ↔ evidence ↔ supplier join | the JOIN half of `executors.scoring` (mechanism × supplier, needs price + MOQ) · `interleave_leads` · `provenance.enforce` | REAL (8 leads) | yes — the join without its score | Trail's records must be readable here first (M1-08) | the score half is a duplicate | agent + ecommerce library |
| 28 | `X_compile` | result + dossier | `report.build_model` / `render` (+ `build_model_from_governed`, TG4) | renderer CODE; governed bridge REAL (R2a gap dossier) | yes (already wired) | report model must receive concepts, variations, existing products, suppliers, Trail records | no | **adapter** result · **controller renderer** dossier |

## 3. Controller node → future owner (all 28 nodes)
| Controller node | Keep as library | Wrap for the harness | Replaced by Trail | Replaced by Polymath / adapter | Standalone only | Retire |
|---|---|---|---|---|---|---|
| understand | ✔ prompt | | | | | |
| corpus | | | | ✔ evidence boundary via the adapter | ✔ `corpus_polymath.py` | |
| primitives | ✔ prompt + lineage law | | | | | |
| signal_gate | | | | ✔ adapter typed gap | ✔ | |
| structural_lookup | ✔ analogies from corpus facts | | ✔ registry priors (`registry.project`) | | | mirror data |
| lenses | ✔ | | | | | |
| population_nominate | ✔ | ✔ `I_research` | | | | |
| population_scout | | ✔ `I_research` | | | | |
| population_queue | ✔ | ✔ | | | | |
| community_instantiate | | ✔ `I_research` (+ harvest dates) | | | | |
| evidence_cards | ✔ anchor / thin arithmetic (advisory) | | independence = Trail | | | |
| population_gate | | | | ✔ adapter loop control | ✔ | |
| lived_situations | ✔ prompt + validator | | | | | |
| corpus_mechanisms | ✔ question compiler (open design point) | | | ✔ retrieval | | |
| hypothesize | ✔ prompt + bridge / portfolio validators | | | ✔ durable ledger | | |
| semantic_review | ✔ ADVISORY reviewer | | ✔ authority | | | |
| apply_review | | | ✔ | ✔ ledger transitions | ✔ | |
| triage | ✔ advisory priority | | | | ✔ | |
| challenge | ✔ prompt | | ✔ judgement | | | |
| gaps | ✔ gap objects → `knowledge_gaps` | | ✔ roles / freshness / budget | | | |
| web_research | | ✔ `I_research`, `P_reality` | | | | |
| curate | ✔ | ✔ | ✔ what is admitted | | | |
| mechanism | ✔ prompt | | | | | |
| product_ideation | ✔ prompt + `validate_concepts` + variations | | | | | |
| supplier_search | | ✔ `S_supply` | | | | |
| normalize_supplier | ✔ parsers | ✔ | | | | |
| qualify (`executors.scoring`) | ✔ the mechanism × supplier JOIN | | ✔ qualification + score | | ✔ evidence_score | score as authority |
| stop | | | | ✔ adapter terminal states | ✔ | |

## 4. Dependency facts for each harvest target (decides: call directly, wrap thinly, or leave behind)
| Capability | Entry points | Reads → writes (run-state keys) | Needs | Prompt · schema · validator that travel with it | Coupling / side effects | Verdict |
|---|---|---|---|---|---|---|
| Corpus question compiler | `lived_world.compile_corpus_questions` :618 (`corpus_queries.compile_queries` :61 is superseded by Polymath's plan lane) | `lived_clusters`, `field_records` → `corpus_questions` | `policies.corpus.*` | none (no LLM) | pure | DIRECT |
| Lenses · structural analogies | `executors.lens_gate` :52 · `structural_lookup` :80 · `_corpus_analogies` :131 | `signal`, `corpus_evidence`, `primitives`, `row_relevance` → `lenses`, `cross_domain_analogies` | `registry/lenses.yaml`; compiled registry snapshot | none | `registry.load_snapshot` WRITES a compiled file when missing; hard key indexing | DIRECT (lenses) · THIN WRAPPER (analogies: supply or stub the snapshot) |
| Population discovery | `lived_world.nominate` :234 · `rank_leads` :279 · `queue` :337 · `cards` :363 · `gate` :432 · `validate_leads / records / situations` :515 / :529 / :542 | `signal`, `communities`, `primitives`, `corpus_evidence`, `latent_structures`, `field_records` → `population_leads`, `community_leads`, `participant_cards`, `lived_clusters` (+ top-level `population_queue`, `population_loop`) | `policies.lived_world.*`, `evidence_channels`; `executors.channel_queries`; `verifiers.independence_groups` | prompts `population_scout`, `community_instantiate`, `lived_situation` · schemas `population_lead`, `field_record`, `lived_situation` · the three validators (today only `controller.cmd_submit` calls them) | pure over dicts apart from the snapshot write | THIN WRAPPER (build the dict, call the validators, keep queue / loop keys) |
| Hypothesis structure checks | `bridge.validate_bridge` :20 · `validate_hop_refs` :66 · `validate_portfolio` :100 · `lived_world.validate_hypothesis_anchors` :580 · `lineage_ref_errors` :471 | hypothesis list (+ `lived_clusters` for anchors) → annotates `grounding` | `policies.bridge.*`, `policies.portfolio.*` | prompt `bridge_hypothesis` (+ `registry/reasoning_motifs.yaml`) · schema `hypothesis.json` | `bridge.py` has zero imports and zero side effects | DIRECT |
| Advisory reviewer · triage | `evaluator.build_dossier` :52 · `apply_evaluations` :74 · `executors.triage` :168 | hypotheses + evidence → `evaluations`, status, gaps | `policies.triage.*` | prompt `semantic_evaluation` · schema `evaluation.json` · a FRESH subagent | `apply_evaluations` writes SQLite (`memory.write_check`) and mutates statuses | DIRECT for dossier + triage · `apply_evaluations` stays STANDALONE (its status changes are Trail's job) |
| Research planning | `executors.channel_queries` :258 · `_CHANNEL_TEMPLATES` :198 · `gap_compiler` :282 | `hypotheses`, `gaps`, `queries`, `communities` → `gaps`, `queries`, `research_allocation` | `policies.evidence_channels`; snapshot `query_templates`; `allocation` | none | `channel_queries` is the cleanest harvest in the repo (gap id + question + policies) | DIRECT (`channel_queries`) · THIN WRAPPER (`gap_compiler`) |
| Curation | `executors.comments` :326 | `observations`, `gaps` → closes gaps, `rounds`, `satisfaction` | `satisfaction`, `verifiers`, `allocation`, role / freshness policy tables | — | ENTANGLED with the controller's own admission + coverage stack | LEAVE BEHIND (Trail admission replaces it); keep only de-duplication |
| Product concepts + variations | `ideation.validate_concepts` :17 | `mechanisms` (SUPPORTED), `observations`, `field_records` | `policies.ideation.*` | prompt `product_ideation` · schema `product_concept.json` (≥ 2 variations, ≥ 1 evidence ref) | pure | DIRECT. **No Python producer of `mechanisms` / `supporting_observation_ids` exists** — they are agent output (`prompts/mechanism_mapping`, `schemas/mechanism.json`) |
| Sourcing | `executors.sourcing_plan_compiler` :446 · `sourcing_exa.parse_listing` :40 · `executors.supplier` :508 · `_parse_price` :404 · `_parse_moq` :416 · `_supplier_fits` :643 | `product_concepts`, `mechanisms`, `product_candidates` → `sourcing_plan`; `supplier_candidates` → normalised rows, `sourcing_coverage` | `policies.sourcing.*`, `policies.supplier.moq_default_by_channel` | none | parsers pure; `sourcing_exa.main` shells out to `mcporter` and writes a file | DIRECT (parsers, `parse_listing`) · THIN WRAPPER (plan + normalise) · the Exa call sits behind the harness |
| Lead assembly | the JOIN half of `executors.scoring` :552-576 · `interleave_leads` :609 | `mechanisms` × `supplier_candidates` × `product_concepts` → `leads` | three `policies.supplier.require_*` booleans | none | the OTHER half (score arithmetic, coverage pre-gate, verdict write-back, `satisfaction`, `settings`, `candidates`, `utilization`) is the duplicate authority | THIN WRAPPER: lift the ~25-line join · LEAVE the score half behind |
| Report | `report.render` :514 (pure dict → HTML) · `report.build_model` :37 · `build_model_from_governed` (TG4) | reads the run state / the governed journal | none | none | `build_model` opens SQLite inside a bare try / except | DIRECT (`render`); extend the GOVERNED model, not the renderer |

Mid-graph entry: **none.** `controller.py init` takes only `--signal --graph --settings --preset --corpus --document-id`, always
starts at the graph entry and refuses out-of-order submissions. For a harvest this does not matter: almost every target is
`(state, policies) → state["data"]`, so state is built as plain dicts. The controller's 28-node state machine is NOT needed.

## 5. Acquisition tools each harvested capability needs
| Capability | Tools (as the controller emits them) | Evidence |
|---|---|---|
| Field research | `opencli reddit search / read` | REAL (146 observations; also R2a) |
| | `opencli youtube search / comments` | CODE in the controller; ran once in R2a after one rejected navigation |
| | `opencli amazon search / discussion` · `tiktok` · `xiaohongshu` · `twitter` · forums via `mcporter exa.web_search_exa` + `curl r.jina.ai` | CODE — no run artifact in either system (Exa search + fetch ran in R2a) |
| Product reality (`P_reality`) | the amazon / retailer / forum rows of the same channel table | CODE — no per-concept product-reality PLAN exists anywhere; only channel commands |
| Sourcing | `python/sourcing_exa.py` → `mcporter exa.web_search_exa "<term> site:alibaba.com …"` / `site:cjdropshipping.com` | REAL for Alibaba (8 leads); CJ 39 rows, 0 leads; `opencli 1688` exists, unused |
| All of them | `opencli` needs a RUNNING Chrome for its bridge | measured in R2a |

## 6. Fixtures and invariants for behavioural parity (no exact-output matching)
| Fixture | Use |
|---|---|
| `state/calib_books_01.json` (deployed copy, 2.4 MB) | golden POSITIVE: populations outside the seed, anchored clusters, 5 concepts × 2 variations, supplier candidates, leads with price + MOQ |
| `state/calib_novel_02.json` | golden NEGATIVE: every hypothesis dies on field evidence → no concepts. The migrated path must still be able to refuse |
| `state/calib2_*.json` (~35 files) | node-level inputs / outputs for the harvested functions |
| `candidates/r2a_cinema_smoke/` | the same inputs already recorded on the governed path (11 `adapter_next` payloads, 3 receipts, harvest ledger, result) |
| `tests/calibration_acceptance.py` — nine canaries (docs/26 §6) | the ONLY named structural invariants either system has. Recorded baseline: books-01 **FAILS** canary 2 (heterogeneous source reasoning), novel-02 passes — parity is measured against a known-failing baseline, not a green one |
| `tests/run_all.py` sections 20 / 23a (population), 2b / 13 / 14 (bridge, portfolio), 13 / 19 (gap + channel), 13 (ideation), 12d / 14 / 19 (parsers, sourcing), 6 / 13 (report) | reusable as parity checks: they test functions over dicts. Sections 1, 2d, 5, 10, 11, 12k, 12l, 18, 23c are bound to the controller CLI / state machine |

Parity acceptance (structural): populations are nominated from latent structures and ranked · field records cluster into
anchored groups by independent voices · hypotheses pass the bridge and portfolio laws BEFORE they enter the ledger · every
product concept has ≥ 2 variations and ≥ 1 evidence ref · a sourcing plan exists per concept and yields supplier rows with
parsed price and MOQ · leads join a Trail-admitted mechanism to an admitted supplier observation · `NO_DEFENSIBLE_BRIDGE` /
a typed refusal remains reachable · every observation carries harvest dates · no `score|rank|weight` from the controller
appears anywhere in a governed artifact · the nine canaries are evaluated and reported.

## 7. Duplicates — and what becomes deletable ONLY after parity
| Responsibility | Controller | Governed | Retain | Precondition before deleting the other |
|---|---|---|---|---|
| Workflow state machine | `transitions.py` (29 conditions) + `controller.py step / submit` | adapter `transitions.py` / `service.py` | adapter | standalone mode is still wanted until the governed path reaches parity |
| Hypothesis lifecycle | statuses + `apply_evaluations`, `triage`, `run_triage` | adapter ledger + Trail `judgement.py` | adapter + Trail | reviewer kept as ADVISORY |
| Research planning | `gap_compiler`, `channel_queries`, `_CHANNEL_TEMPLATES` | Trail `gap_compiler.py` → directive (WHAT: roles, freshness, budget) | BOTH, split: Trail = WHAT · controller = HOW | none — they are complementary once split |
| Admission · independence · freshness | `verifiers.py` + policy tables | Trail `admission.py` + `data/source_capabilities.csv` | Trail | never invoked in governed mode (already fenced by docs/27) |
| Qualification · score | `executors.scoring` score half, `satisfaction`, `qualify.py` | Trail `qualification.py` + scoring engine | Trail | as above |
| Registry data | `registry/trailsignal/*.csv` mirror + compiled snapshot | Trail `data/` | Trail | **verified DRIFT: the mirror carries +6 seeds, +10 friction families (`friction_library.upstream.patch`, never upstreamed), +6 niche candidates — upstream or consciously drop them first, or they die silently.** 7 other files are byte-identical. `source_capabilities.csv` has no mirror: the controller re-implements it as hand-written policy |
| Corpus client | `corpus_polymath.py` (cap 12 evidence calls) | adapter `evidence_boundary.py` (cap 3) | adapter | reconcile the call cap first — the governed cap is untested at the controller's working volume |
| Must SURVIVE (controller-only) | `lived_world.py`, `bridge.py`, `ideation.py`, `registry/lenses.yaml`, `reasoning_motifs.yaml`, `niche_scopes.yaml`, channel templates, supplier parsers, `interleave_leads`, `provenance.py`, `report.py`, `tests/calibration_acceptance.py` | — | controller | — |

## 8. Migration order that never leaves two AUTHORITATIVE implementations live
The authority question is settled by MODE from day one: in a governed run only Trail admits, judges, qualifies and scores, and
only the adapter holds state — the controller's authority code is simply not called (docs/27 already fences it). Nothing is
deleted until parity.

| Layer | Content | Code? |
|---|---|---|
| A — capability extraction | this document | no |
| B — library boundary | only where §4 says THIN WRAPPER: build the state dict, call the validators, stub the registry snapshot, lift the mechanism × supplier join. No new framework: the targets are already functions over dicts | skill repo only |
| C — governed connection | `I_research` ← population discovery + channel planning (Trail's directive supplies WHAT) · agent steps ← the controller's prompts + bridge / ideation validators as a pre-submit gate · `P_reality` ← amazon / retailer channels (first real exercise by either system) · `S_supply` ← sourcing plan + parsers · harvest dates stamped at capture · concepts + variations carried in the free-form `product_opportunity` (no contract change for a first run) · governed report model extended | skill repo; the adapter only needs the run-survival fixes (D1, M1-04, M1-06, M1-07, M1-08, M1-11) — one bounce |
| D — retirement | mirrors (after the drift is upstreamed), `verifiers.py`, the authority half of `policies.yaml`, `evaluator.apply_evaluations`, the score half of `executors.scoring`, `qualify.py`, `corpus_polymath.py`, then the controller state machine | only after parity on the fixtures in §6 |

Trail-side findings (M1-01, M1-02, M1-03, D4) go through Trail's own governance (TG7) and are independent of layers B–C.

## 9. Open points that the evidence does not settle
1. **Corpus.** The only useful run used `ecom-meta-v1`, which the owner dropped from the plan; v4 holds only `cinema`; a second corpus needs Item 2D first.
2. **What the mechanism-level retrieval asks.** The adapter sends hypothesis STATEMENTS (hit by D2); the controller sends QUESTIONS compiled from field clusters. One of them should feed `F_retrieve`.
3. **Where concepts and variations live.** `product_opportunity` is an untyped object today: good enough to carry them for a first run, not a contract.
4. **Mechanisms** have no deterministic producer in either system; they remain agent output with a 5-field schema.
5. **The reviewer.** Advisory input to the agent's revision is lawful; whether its verdicts are shown in the dossier is a product choice.
6. **Product reality** has never run in either system: its plan is new work, not a harvest.
