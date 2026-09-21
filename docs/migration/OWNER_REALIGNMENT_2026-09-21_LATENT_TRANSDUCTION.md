# Owner Realignment — 2026-09-21 — Arbitrary corpus → latent structure → universal grammar → reality

> OWNER INTENT. Structured by the agent from the owner's two analysis notes and chat turn of 2026-09-21 (the two attached text files themselves were NOT received — only the chat text). Where this file and the owner's
> words differ, the owner's words win; the owner confirms or corrects it. Owner-controlled like the files in `README_OWNER_CONTROL.md`: the agent records facts against it, never rewrites its intent.
> STATUS: admitted, NOT executed. The session that wrote it executed nothing. It REORDERS the work; it does not authorize spend, merges or a Trail change by itself (see "Decisions the owner still has to make").

## 1. The thesis (the one sentence to align to)
**Use arbitrary knowledge as a hypothesis-generating substrate, abstract reusable causal / behavioural structures from it, and force those abstractions to survive contact with real-world commercial evidence.**
This is not "ecommerce RAG with good governance". The knowledge source and the resulting market do NOT have to be the same domain.

## 2. What is corrected
- RETRACTED: "arbitrary corpus → choose / build a matching Trail domain overlay" (the `universal-v1 + cinema-v1` registry idea). It would anchor the system back to source-domain labels.
- LOCKED instead: arbitrary corpus → Polymath / LLM extracts generalizable latent structure → Trail's DOMAIN-INVARIANT transformation vocabulary normalizes and constrains it → real-world research tests whether the abstraction
  manifests commercially. The corpus can be cinema, fiction, military logistics, gardening, psychology — anything — and must not require a matching Trail ontology.

## 3. The architecture to lock
```
ARBITRARY CORPUS
  → POLYMATH RETRIEVAL
  → LLM SEMANTIC TRANSDUCTION            (understand the specific situation, then abstract it)
  → UNIVERSAL LATENT REPRESENTATION      population / activity pattern · task / job · constraints / context · body / hand state ·
                                         friction candidates · workaround pattern · shared predicates · mechanism
  → TRAIL UNIVERSAL TRANSFORMATION GRAMMAR   friction primitives · mechanism / product territories · predicates · evidence roles ·
                                             source policy · research policy · scoring / gates
  → LATENT OPPORTUNITY HYPOTHESES
  → REAL-WORLD RESEARCH
  → SUPPORT / CONTRADICTION / COMPETITORS / SUPPLY
  → RE-REASON
  → PRODUCT OPPORTUNITY OR REFUSAL
```

## 4. Ownership split (use this wording everywhere)
| Who | The question it answers |
|---|---|
| POLYMATH / LLM | "What does the source knowledge mean, and what reusable latent structure is inside it?" — interprets, abstracts, analogizes, cross-maps, abducts. It is the SEMANTIC TRANSDUCER, not merely "writes a hypothesis". |
| TRAIL | "What universal opportunity primitives does that map to, what evidence would make it credible, and what evidence is admissible?" — normalizes, supplies transformation primitives, specifies evidence requirements, admits, qualifies, scores. Deterministic. |
| HARNESS | "Go interrogate reality." |
| POLYMATH / LLM | "Given what reality returned, revise the hypothesis." |

## 5. What the CSV registry IS
A **latent-opportunity transformation vocabulary**, not a domain taxonomy and not a list of markets: friction primitives (`access_latency`, `occupied_hand`, `small_parts`, `object_retention`, `setup_complexity`, `carry_load`,
`tangle_management`, `visibility`, `field_repair`, `repetition_burden`, `checklist_failure`, `multi_person_coordination` …), mechanism / product territories (`body_mounted_access`, `modular_carry`, `tangle_control`, `field_labeling`,
`task_lighting`, `environmental_protection` …), source capabilities, query templates, evidence gates, scoring laws. It should become INCREASINGLY domain-invariant.
`outdoor_activity_niche_seed.csv`: its value is the SCHEMA — WHO / WHAT / CONDITIONS / BODY STATE / FAILURE / WORKAROUND / PHYSICAL JOB / PRODUCT MECHANISM — i.e. worked examples of situation → constraints → friction → workaround → mechanism,
not the fact that the rows are dog walking or fishing. OPEN QUESTION FOR THE AUDIT: does the implementation treat those rows as transformation examples / priors, or as literal candidate-market coordinates? The second is bias.

## 6. The gap (a product-architecture gap, not a failed migration)
The migration reused working behaviour (`REUSE > WRAP > MOVE > ADAPT > REWRITE`) — correct for consolidation — and the 78-step real run proved the system works AS BUILT. One old bridging assumption was never replaced:

| Intended | As built (to be PROVEN by the audit) |
|---|---|
| retrieved evidence → LLM extracts structured latent semantics → deterministic mapping against Trail primitives → registry coordinates | LLM writes hypothesis prose → Trail takes the TEXT → lexical matching against friction / territory / niche-seed CSV text → registry coordinates |

The semantic intelligence exists (mechanism reasoning, physical-job derivation, lived situations, bridge / portfolio laws, revision) but is SCATTERED across steps and collapses back into prose before Trail sees it. What is missing is ONE canonical typed object.

### `LatentOpportunityRepresentationV1` (target shape — conceptual, not a schema yet)
`source_evidence_refs` · `population_pattern` / `actor_pattern` · `activity_pattern` · `task` · `context_constraints[]` · `body_state[]` · `observed_failure` · `friction_candidates[]` · `workaround_pattern` · `shared_predicates[]` ·
`physical_job` · `mechanism_candidate` · `transferability_hypothesis` · `knowledge_gaps[]` · `contradictions[]`.
Example of the abstraction wanted (from cinema material: one hand occupied + fast transitions + temporary retention + clean-surface scarcity + access latency): NOT "sell camera gear" but `population_pattern: mobile worker` ·
`activity_pattern: repeated equipment transition` · `task: temporary staging during component exchange` · `friction_candidates: small_parts, object_retention, access_latency` · `mechanism: temporary retained staging interface` —
then ask: where does this pattern exist in the real world, and does anyone suffer enough from it to create a product opportunity?
Flow: POLYMATH / LLM produces it → TRAIL validates / normalizes / maps it deterministically → TRAIL compiles evidence requirements → HARNESS researches reality.

### The real-run defects are symptoms of this one missing boundary
| Symptom seen in the real runs | Same root cause |
|---|---|
| Product-reality searches used ontology coordinates (`body_mounted_access`) as search vocabulary | A Trail coordinate CLASSIFIES a concept; market vocabulary must be generated from concept + job + mechanism + population (e.g. "lens cap quick access holder", "camera tool pouch") |
| Query compilation flattened rich reasoning into keyword / template fragments | Templates must consume population, activity, task, mechanism, friction, workaround terms, candidate product form and the domain vocabulary recovered from Polymath |
| Per-hypothesis knowledge gaps collapsed into one top-level gap set | Hypothesis-specific intelligence is not preserved across the boundary; it weakens the portfolio architecture |
| Admitted counter-evidence recorded as "supporting" | The receipt carries no polarity |
| The same first 60 evidence rows shown at every step | Unknown whether it affects the agent's actual context — to be determined |

## 7. Why the cinema run matters MORE now
Cinema is a strong canonical test precisely BECAUSE it is not ecommerce knowledge. `cinema` is a valid real benchmark corpus. (This reverses the older standing rule that a run on `cinema` is a mechanical smoke only.)

## 8. Do NOT
Build `cinema-v1` · build one Trail overlay per corpus · make `commerce-v1` the acceptance blocker · create separate ontologies for fiction / military / gardening · throw away the CSV registry · redesign Trail's deterministic
snapshot / compiler architecture · change LAW-1 before a defect is proven live · expand IAM, build UI, add speculative adapters, optimise performance.

## 9. Kept from the first note — benchmark, do not redesign
Two questions added to the acceptance audit; LAW-1 is not changed unless they prove a live defect:
1. Does real product-discovery evidence ever populate the `content` axis meaningfully?
2. Is `growth` inferred from growth evidence, or is seasonality standing in for it?

## 10. The queue the owner set
```
NOW     audit the semantic transduction path  (arbitrary evidence → latent representation → Trail coordinates)
        fix evidence polarity
        preserve per-hypothesis gaps
        fix semantic query compilation
        fix product-reality search semantics
        determine whether the 60-row reuse affects the agent's actual context
THEN    CINEMA REAL BENCHMARK AGAIN  →  NEGATIVE CONTROL  →  OFF-HOST MCP  →  ACCEPTANCE
REMOVED from the critical path:  repair commerce-v1 as a prerequisite · build a cinema registry overlay
```
Commerce may still be useful later as another corpus; it is not required for the arbitrary-corpus thesis.

## 11. What this changes in the existing documents (the agent does not resolve these silently)
| Document | Says | Now |
|---|---|---|
| `MIGRATION_POLICY.md` mission / "Ecommerce first" / "do not generalize before ecommerce proves the need" | the immediate objective is ecommerce research end to end | Ecommerce stays the first ADAPTER and the commercial test; the GOAL is the arbitrary-corpus thesis. The consolidation it governed is done and live; this file governs what comes next. The owner may want to re-issue the policy. |
| `MIGRATION_POLICY.md` "Old ecommerce indexes … reingest" + `EXECUTION_PLAN.md` Phase 10 + the 09-21 owner decision (order step 3) | commerce corpus is a phase on the path | Off the critical path. Not deleted: 4 / 10 documents are query-ready; the ingestion diagnosis stays recorded. |
| `/polymath-bootstrap` skill + earlier `CONTINUATION.md` | "a run on `cinema` is a mechanical smoke only" | Reversed: `cinema` is the canonical real benchmark. |
| `CONTINUATION.md` queue | NOW = dossier product-artifact gaps | Moved behind the audit and the five fixes; still owed before ACCEPTANCE (owner's dossier requirements of 09-21 stand). |
| `MIGRATION_POLICY.md` stop condition 5 + ADR-0021 | "Trail policy semantic change without documented intent" is a stop; the embedded Trail core is byte-identical to A41 | The lexical bridge lives INSIDE the pinned core. This file is the documented intent; WHERE the deterministic mapping lives is an owner decision (below). |
| Doctrine "generalize only after demonstrated need" / "no speculative abstractions" | — | The need is now demonstrated by real runs; ONE typed contract is authorized in principle, conditional on the audit proving the gap. |

## 12. Claims to VERIFY in the audit (evidence classes — nothing here is proven by this file)
- READ, confirmed 2026-09-21: `governance/trail/src/trail_signal/contexts/planning/domain/gap_compiler.py:149` `derive_registry_coordinates` — "lexical overlap with niche seeds, friction primitives, and territories": `words = tokens(hypothesis.statement)`,
  `overlap = len(words & tokens(text))`; `map_product_territories` (`:179`) maps physical jobs / mechanisms "by lexical overlap". Both inside the byte-pinned core.
- EXECUTED in the real runs: `registry.project` was called with hypothesis STATEMENTS and returned `niche_seed` priors; territories projected for the camera-carry hypothesis were `body_mounted_access`, `one_hand_controls`, `articulated_apparel`.
- UNVERIFIED: whether niche seeds act as literal market coordinates downstream; how much of the engine's structured output (primitives, latent structures, physical jobs, mechanisms) already exists in typed form and is simply not handed to Trail;
  whether the hypothesis ledger's fields (`population`, `activity`, `task`, `mechanism`, `suspected_friction`) reach Trail at all; the two scoring questions of §9; the 60-row question.

## 12b. Third note (owner, same day) — the sharpened diagnosis, and what the repository confirms or corrects
**Diagnosis the owner adopts:** *the EXECUTION architecture was completed; the SEMANTIC TRANSFORMATION architecture was only partially carried across.* The machine that executes, governs, researches, revises and scores latent
opportunities is built and working. The part that converts arbitrary knowledge into a rich, reusable latent-opportunity representation is still mostly prompt behaviour plus lexical matching, not a first-class typed reasoning layer.
The older design's chain — Pressure → Human Mechanism → Behaviour → Adaptation → Current Solution → Latent Need → Opportunity → Product Mechanism → Product, with a bridge that must be EARNED (storytelling → performative delivery →
physical presence → mobile audio capture → handheld microphone) — was compressed into a few AGENT_REASON prompts during the ADR-0019 migration, which solved a different, necessary problem (ownership boundaries). Fix this next — not another migration.
Do NOT: rebuild Polymath · replace Trail · create cinema tables · put an LLM inside Trail's deterministic scorer · create a second graph database · undo the migration.

| # | Claimed gap (severity per the note) | Repository evidence, 2026-09-21 |
|---|---|---|
| 1 | No durable Opportunity Transformation IR — mostly `HypothesisStateV1` (P0) | PARTLY CORRECTED. The note read `trail.product_discovery` (28 steps). The manifest that ran is `ecommerce.product_research` (54 steps), which DOES produce typed structure before hypotheses: `C_primitives` (drivers, behaviours, adaptations, constraints, frictions, workarounds, physical interactions / jobs, latent values, transferable invariants, shared predicates, `latent_structures[]` of 24 kinds incl. `TRANSFERABLE_INVARIANT`, `CAUSAL_MECHANISM`, with `possible_populations` and `applicability_outside_source`) and `C_bridge` (≥ 3 hops, an explicit evidence boundary, "never seed → product in one jump", distinct mechanism families). TRUE PART: it is scattered over step outputs and engine state, is not ONE canonical object, is not in the hypothesis ledger, and never reaches Trail. |
| 2 | CSV used as priors / routing, not as a transformation grammar (P0) | CONFIRMED for Trail's CSVs (READ). In both manifests `D_project` runs AFTER `C_hypotheses`: Trail's vocabulary is not the lens of the first abstraction. In `ecommerce.product_research` the ENGINE's registry mirror does enter earlier (`B_lenses`, `C_population`) — two registries, one early and one late (see M-014). |
| 3 | Trail does lexical word overlap on flattened rows (P0) | CONFIRMED (READ): `gap_compiler.py:149` joins a prior's fields into text and scores `len(tokens(statement) & tokens(text))`; `:179` likewise. Niche-seed columns (participant, task, context, body_or_hand_state, friction_family, workaround, territory, shared_predicates) lose their distinct semantics. Inside the byte-pinned core. |
| 4 | Rich hypothesis state is stripped between steps; Trail gets only the statement (P0) | CONFIRMED (READ + EXECUTED): `shared/polymath_shared/adapter/hypotheses.py:256` `context_view` = `{hypothesis_id, revision, status, statement}`; every real step's `context.hypotheses` showed exactly that. Trail: `research_operations.py:166` builds `HypothesisView(…, statement, knowledge_support_count=0)`. The ledger itself stores mechanism / population / activity / task / context / suspected_friction / assumptions / contradictions / falsifiers / gaps. |
| 5 | No analogical / cross-domain stage in production (P0 / P1) | PARTLY CONFIRMED. No dedicated analogy step in either manifest. The engine has the hooks (`possible_populations`, `applicability_outside_source`, LATENT population leads "population unknown — search by the friction language"), but nothing FORCES a cross-domain projection. In the real runs the SEED already named the population and the problem (outdoor photographers), so transduction from arbitrary knowledge into another market was NOT tested. The next cinema benchmark must use a seed that does not presuppose the market. |
| 6 | Product hypotheses come after market search (P0) | CORRECTED for the manifest that ran: `N_concepts` (typed concepts + variations, each on admitted evidence, product-set law) precedes `P_reality`. THE REAL DEFECT: the `P_reality` directive ignores those concepts — 4 Trail templates keyed on the registry TERRITORY name; the engine compiles concept-derived queries for SUPPLY only. True as written for `trail.product_discovery`. |
| 7 | A gap without a hypothesis id is attached to the FIRST hypothesis (P1) | CONFIRMED (READ): `research_operations.py:170–173` `fallback = hypotheses[0].hypothesis_id … gap.hypothesis_id or fallback`. The owner's rule: no first-hypothesis fallback; a missing linkage is a typed refusal. Inside the pinned core. Separately (EXECUTED): per-hypothesis gaps stored in the ledger never reach `gaps.compile`; only a step's top-level `knowledge_gaps` do. |
| 8 | Query compilation lacks semantic material (P1) | CONFIRMED (EXECUTED): 13 / 13 compiled channel queries useless with verbose inputs; usable only when the agent hand-shaped names and gaps. The compiler receives a lead name or a gap question, not population aliases, behaviour, adaptation, friction / workaround language, product form, mechanism synonyms, analogous populations, corpus vocabulary or falsification terms. Ownership stays: Polymath = vocabulary + interpretation · Trail = what evidence is required and from where · Harness = execute. |
| 9 | Counter-evidence is structurally weak (P1) | CONFIRMED (EXECUTED): the receipt has no polarity; an admitted "never go back" observation was recorded `supporting`. The exact text heuristic inside Trail was NOT located — UNVERIFIED. Target: a RELATION — observation X CONTRADICTS hypothesis H3 — not a guessed global polarity. |
| 10 | The graph is retrieval breadth, not a traversal grammar (Driver → Behaviour → Adaptation → Friction → Latent Value → Mechanism → Product) | NOT EXAMINED. For the audit. |

**What the audit must therefore establish:** not "is there an IR?" but — which typed structure already exists in `ecommerce.product_research`, where each field dies (ledger → `context_view` → Trail payload → directive → query), and what is the SMALLEST
contract that carries it across: most likely a canonical object assembled from what `C_primitives` / `C_bridge` / `N_jobs` / `N_concepts` already emit, persisted with the hypothesis, shown to later steps, and handed to a deterministic mapper.

## 13. Decisions the owner still has to make (after the audit, not before)
1. WHERE the deterministic mapping lives: (a) change TrailSignal upstream (its own governance; owner-accepted ADR) and re-pin the embedded copy, or (b) a deterministic Polymath-side normalizer that turns the typed representation into what Trail
   already consumes, leaving the pinned core untouched, or (c) both in sequence.
2. Whether `LatentOpportunityRepresentationV1` replaces the hypothesis prose at the Trail boundary or travels beside it.
3. Whether `MIGRATION_POLICY.md` / `EXECUTION_PLAN.md` are re-issued for this phase or this file stands beside them.
