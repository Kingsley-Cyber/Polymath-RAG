# HANDOFF — mirror LIVED-WORLD-V2 (v2.0.0) into the standalone TRAIL_AGENT_AUTORESEARCH repo

You are an executor in a fresh session. Your job is to bring the standalone
repo `github.com/Kingsley-Cyber/TRAIL_AGENT_AUTORESEARCH` (last state
**v1.6.0**, commit `7c94e8e`, docs 01–23) up to the reference implementation
that lives inside the Polymath repo at `polymath-v4/research/` (**v2.0.0**,
Polymath main `a7f4f31`, docs 24–25). Same architecture, same laws, same
tests. Nothing here changes the reference; you change the standalone.

Two paths. Take **A** if you can read the reference tree (same machine or a
clone of Polymath main). Take **B** if you only have this document. Both end
with the proof in §8 — a pass is a receipt, never a feeling.

---

## 0. Definition of done (check every line before you report)

1. `python3 tests/run_all.py` → `ALL N CHECKS PASSED` with N ≥ 454 and every
   section-20 label from §8.1 present in the output.
2. `python3 python/controller.py doctor` → `{"ok": true, ...}`.
3. `git grep -l "polymath_shared\|from orchestrator" python/ tests/` → nothing
   (the standalone never imports Polymath; the corpus adapter talks HTTP only).
4. No `people.csv`, no person database anywhere. `registry/research_evidence.csv`
   stays gitignored (it holds Reddit usernames and verbatim quotes).
5. `SKILL.md` frontmatter `version: 2.0.0`; `manifest.yaml`
   `architecture: v2-LIVED-WORLD`; `WORKLOG.md` has v1.7.0 and v2.0.0 entries;
   `docs/24_evidence_channels_and_sourcing.md` and
   `docs/25_population_discovery_and_lived_world.md` exist.
6. Your final message follows §12.

---

## 1. The design in one page

**Measured failure (2026-09-03):** six marketing transcripts hold ~12 product
nouns and 1,369 method terms; the product graph read only corpus rows before
hypothesizing; the observation schema REQUIRED a hypothesis `gap_id`, so the
field could only validate; the 371-row evidence CSV re-clustered into the
three hypotheses it was collected for; three unrelated lives against ten
books shared 18 of 19 documents. Two independent pipelines produced the same
GLP-1 / facial-hair / insole leads. A directional inversion, not a diversity bug.

**Target (owner, 2026-09-04):** real communities generate the lived-world
nouns; the corpus supplies deeper mechanisms and analogies; θ (the model)
bridges them; φ (Python) decides what is allowed to count.

```
understand → corpus (signal-level, isolated) → primitives → signal_gate → lenses → structural_lookup
  → population_nominate (φ)      corpus / registry / signal / prior field rows nominate LEADS
  → population_scout (agent)     open field: where do these people actually talk? (+ the unexpected)
  → population_queue (φ)         VOI-ranked work queue, ONE batch per round, no fan-out
  → community_instantiate (agent) channel tool chains → field_records (real authors, threads)
  → evidence_cards (φ)           ParticipantEvidenceCard + LivedEvidenceCluster (THIN / ANCHOR)
  → population_gate (φ) ⟲        rounds until enough ANCHOR; max_rounds / stagnation / wall clock
  → lived_situations (θ)         FIELD_ANCHORED only on ANCHOR; reconstructions keep unknowns
  → corpus_mechanisms (retrieve)  corpus asked at friction / mechanism level, never per person
  → hypothesize (θ)              each hypothesis names ANCHOR clusters or declares CORPUS_ONLY
  → semantic_review → apply_review → challenge → triage → gaps → web_research → curate ⟲
  → mechanism → product_ideation → supplier_search → normalize_supplier → qualify (provenance) → stop
```

**Laws (unchanged from v1, now enforced by schema + Python):** a lead never
establishes demand; simulation is never evidence; same author or same thread
is ONE voice; a source proves only what it is qualified to prove (docs/04);
the corpus never establishes current demand; lineage decides what counts,
never a category blacklist; the controller runs one action per node.

---

## 2. Data objects and schemas (`schemas/*.json`, validated by `models.validate`)

The validator supports: type (incl. lists), enum, required (present AND not
null/empty), properties, items, additionalProperties, minItems/maxItems,
minimum/maximum. Write schemas within that subset.

### 2.1 `population_lead.json` (used for BOTH `population_leads` and `community_leads`)
required: `id, kind, name, source_lane, nominated_by, authority, status`
- `kind` enum `POPULATION | COMMUNITY`
- `source_lane` enum `CORPUS | REGISTRY | SIGNAL | FIELD_RECORDS | OPEN_FIELD`
- `nominated_by` array minItems 1 (row ids, seed ids, observation ids, or search receipts)
- `authority` enum `LEAD` (only value)
- `status` enum `NOMINATED | INSTANTIATING | INSTANTIATED | EXHAUSTED | DROPPED`
- optional: `platform, community_key, why, expected_frictions[], activities[], contexts[],
  seed_population (bool), channel_queries[], voi (number), rounds_visited (int ≥0),
  record_ids[], evidence_summary {}`

### 2.2 `field_record.json` (`field_records`)
required: `id, lead_id, source, quote_ref, community, problem, evidence_roles, freshness, source_identity`
- `evidence_roles` array minItems 1; `freshness {class}`; `source_identity {source_family, platform, author_key?, thread_key?}`
- optional: `workaround, desired_outcome, activity, context, moment, object_state,
  purchase_language (bool), contradicts (bool), friction_family, products_named[],
  knowledge_roles[], origin enum CHANNEL | PRIOR_RUN | FIELD_CORPUS, query_id, query_used, corpus_row_id`
Same evidence contract as `observation` (roles × source suitability × claim-relative
freshness) — validated through `verifiers.admit_observations` at submit.

### 2.3 `participant_evidence_card.json` (`participant_cards`, φ-generated)
required: `id, platform, author_key, record_ids (minItems 1), record_count (≥1), thread_count (≥1), communities, roles_present`
optional: `freshness_classes[], lead_ids[], products_named[], unknowns[]`

### 2.4 `lived_evidence_cluster.json` (`lived_clusters`, φ-generated)
required: `id, community, friction_family, card_ids (≥1), record_ids (≥1), record_count, thread_count, independent_voices (≥1), authority, unknowns`
- `authority` enum `THIN | ANCHOR`
- optional: `lead_id, roles_present[], sample_quotes[], products_named[], seed_population (bool), threshold {}`

### 2.5 `lived_situation.json` (`lived_situations`; also loadout `lived_r1/lived_r2`)
required: `id, authority, unknowns`
- `authority` enum `FIELD_ANCHORED | RECONSTRUCTED | SIMULATED`
- `moment` enum `BEFORE | ARRIVAL | DURING | TRANSITION | AFTER`
- `frictions[]` items object required `text, authority` where authority enum
  `FIELD_OBSERVATION | RECONSTRUCTED`, optional `refs[], friction_family`
- optional: `cluster_id, community, scope, experience_level, situation, activity, environment,
  participants, body_hand_state, object_state, constraints[], inferred_frictions[], workarounds[],
  physical_jobs[], evidence_refs[], preference_cluster`

### 2.6 `community_world_model.json` (loadout `world_model`, singular)
required: `activities (minItems 1), constraints (minItems 1), moments (minItems 1), open_questions`
optional: `experience_profiles[], norms_rituals[], insider_language[], evidence_refs[], authority enum OBSERVED | MIXED | INFERRED`

### 2.7 `product_slot.json` (loadout `slot_candidates`)
required: `id, name, physical_jobs (≥1), moments (≥1), collection_roles (≥1)`
- `collection_roles` items enum `INSIDER_GEM | UTILITY | DISCOVERY | COMPLEMENT | IDENTITY`
- optional: `quality (0..1), mechanism_family, why_this, lived_situation_ids[], evidence_refs[]`

### 2.8 Additions to existing objects (no schema change needed, validated in Python)
- hypothesis: `lived_anchor_ids[]` (ANCHOR cluster ids) or `grounding: "CORPUS_ONLY"`;
  `hop_refs` may cite corpus rows, observations, field records, clusters.
- primitives: `population_leads[]` items `{name, why, evidence_refs[], activities[], contexts[], frictions[], community_key?, platform?}` or plain strings.
- understand: optional output `example_terms[]` (brands/products the signal uses as illustrations).
- product_concept: `evidence_refs` may name field_record ids; optional `origin: "FIELD"`;
  φ writes `provenance` and `field_originated` at qualify.

---

## 3. Graph (`graph/control_graph.yaml`, version 2.0.0)

Node specs (type / executor or prompt / outputs / context contract). Every
model-executed node (reason, retrieve, agent) MUST declare a context contract;
`require` must be resolvable or the controller blocks the action.

| node | type | executor / prompt | outputs | context |
|---|---|---|---|---|
| population_nominate | transform | `python.population_nominate` | — | — |
| population_scout | agent, `fresh_submission_per_visit: true` | `hermes_existing_web_stack`, prompt `population_scout` | `[community_leads]` | require `[run_identity]`; prefer `[population_leads, community_leads, signal, primitives, evidence_authority_rules]`; exclude `[corpus_evidence, hypotheses, mechanisms, supplier_candidates, leads]` |
| population_queue | transform | `python.population_queue` | — | — |
| community_instantiate | agent, fresh per visit | web stack, prompt `community_instantiate` | `[field_records]` | require `[run_identity]`; prefer `[population_queue, population_leads, community_leads, lived_clusters, participant_cards, evidence_authority_rules, signal]`; exclude as above |
| evidence_cards | transform | `python.evidence_cards` | — | — |
| population_gate | gate, `checkpoint: POPULATION_DISCOVERED` | `python.population_gate` | — | — |
| lived_situations | reason | prompt `lived_situation` | `[lived_situations]` | require `[lived_clusters]`; prefer `[participant_cards, field_records, population_leads, community_leads, signal, evidence_authority_rules]`; exclude `[corpus_evidence, hypotheses, mechanisms, supplier_candidates, leads]` |
| corpus_mechanisms | retrieve, `on_enter: python.corpus_question_compiler`, fresh per visit | `corpus_retrieve` | `[corpus_evidence]` + optional `[corpus_answers, corpus_backend]` | require `[run_identity]`; prefer `[corpus_questions, lived_clusters]`; exclude `[hypotheses, mechanisms, supplier_candidates, leads]` |

Patch existing contracts: `hypothesize.prefer` += `lived_situations, lived_clusters, corpus_questions`;
`mechanism.prefer` += `field_records, lived_clusters`; `product_ideation.prefer` += `field_records, lived_situations, lived_clusters`.

Edges (replace `structural_lookup → hypothesize`):
```
structural_lookup → population_nominate → population_scout → population_queue → community_instantiate
  → evidence_cards → population_gate
population_gate → population_queue     when: population_round_needed     (list this edge FIRST)
population_gate → lived_situations     when: lived_world_present
population_gate → hypothesize          when: lived_world_empty
lived_situations → corpus_mechanisms → hypothesize
```

Conditions (`python/transitions.py`, registered in `CONDITIONS`):
- `population_round_needed` = `bool(state["population_loop"]["continue"])`
- `lived_world_present` = not needed and `data.lived_clusters` non-empty
- `lived_world_empty` = not needed and `data.lived_clusters` empty (every hypothesis will be CORPUS_ONLY)

---

## 4. Policies (`graph/policies.yaml`) — add verbatim

```yaml
bridge:
  require_lived_anchor: true     # docs/25 §5
portfolio:
  min_lived_anchored: 2          # when ANCHOR clusters exist
corpus:
  question_forms:
    - "What explains this workaround: {workaround}?"
    - "What mechanism reduces {friction} when {context}?"
    - "What analogous constraint exists elsewhere for {friction}?"
    - "Why do people keep doing {behavior} despite {friction}?"
  max_questions: 12
lived_world:
  anchor_threshold: {min_records: 5, min_threads: 2, min_independent_voices: 3}
  batch_size: 4
  max_rounds: 3
  min_anchor_clusters: 2
  wall_clock_minutes: 45
  stagnation_rounds: 1
  seed_population_discount: 0.5
  nominate_max_registry: 6
  value_of_information:
    default_source_yield: {SIGNAL: 0.8, FIELD_RECORDS: 0.7, OPEN_FIELD: 0.7, CORPUS: 0.6, REGISTRY: 0.5}
provenance:
  min_independent_voices: 3
  min_communities: 2
  echo_verdict: CORPUS_ECHO_UNGROUNDED
```
(v1.7.0 blocks, §10: `evidence_channels`, `sourcing.channels`, `supplier.moq_default_by_channel`.)

---

## 5. Deterministic executors and validators (`python/lived_world.py`, `python/provenance.py`)

No LLM calls. Same state + policies → same output. Ids via `models.stable_id`.

### 5.1 `nominate(state, policies)` — executor `python.population_nominate`
Seed terms = tokens (len ≥ 5) of the first 600 chars of the signal + the
signal's `communities`. A lead is `seed_population` when a distinctive token
of its name/activities/contexts is in the seed terms.
Lanes, in this order, deduped by normalized name (ids are stable on kind+lane+name):
1. **SIGNAL** — each `data.communities` entry → COMMUNITY lead (`community_key` = name without `r/`, platform reddit, nominated_by `["signal"]`).
2. **CORPUS** — `primitives.population_leads` (dict or string) → POPULATION (COMMUNITY if `community_key`), nominated_by its `evidence_refs` or `["primitives"]`.
3. **REGISTRY** — compiled registry seeds whose `shared_predicates × friction_family` (same index `structural_lookup` uses; friction-only match when no predicate hit) → POPULATION lead named `"{participant} — {activity}"`, activities/contexts/expected_frictions from the seed, nominated_by `[seed_id]`, capped at `nominate_max_registry`, deduped on (participant, activity). The seed table stays an activity/context/friction prior.
4. **FIELD_RECORDS** — corpus rows tagged `field_evidence` grouped by frontmatter `community` → COMMUNITY lead, nominated_by up to 5 row ids.
Every lead gets `channel_queries` from the shared builder `executors.channel_queries(lead_id, question, state, policies, id_prefix="pq")` where question = name + first two expected frictions + first activity (underscores/dashes → spaces); each query carries `lead_id`; for COMMUNITY leads the reddit query's `subreddit_hints = [community_key]`. Then `rank_leads`. Note string: counts by lane, total, how many restate the seed population.

### 5.2 `rank_leads` / `eligible_leads` / `queue` — executor `python.population_queue`
VOI per lead = `yield[source_lane] × missing × impact / cost × (seed_population_discount if seed_population)`
- missing: 1.0 NOMINATED; 0.2 EXHAUSTED; 0.1 DROPPED or already has an ANCHOR cluster; INSTANTIATED-but-thin: `0.4 + 0.5·max(0, 1 − records/min_records)`
- impact: `0.5 + 0.5·min(1, |lead tokens ∩ primitives vocab| / 3)` (vocab from frictions, physical_jobs, behaviors, shared_predicates, drivers, constraints)
- cost: `max(0.5, len(channel_queries)/4)`
Eligible = NOMINATED, or INSTANTIATED without an ANCHOR cluster and `rounds_visited < 2`.
`queue`: take the first `batch_size` eligible ids; set status INSTANTIATING and `rounds_visited += 1`;
write `state["population_queue"] = {round (+1), batch, started_at (kept from first round), batch_queries, remaining_eligible}`.

### 5.3 `cards(state, policies)` — executor `python.evidence_cards`
Input: non-contradicting `field_records`. Identity of a record = (platform, author_key or source or id, thread_key or source or id).
- Cards: one per (platform, author): record_ids, record_count, thread_count, communities (normalized), roles_present, freshness_classes, lead_ids, products_named, unknowns = `"no {ROLE} recorded"` for each of FRICTION_EVIDENCE, WORKAROUND_EVIDENCE, BEHAVIOR_SUPPORT, PURCHASE_INTENT absent.
- Clusters: one per (normalized community, `friction_family` or `"unassigned"`): card_ids, record_ids, record_count, thread_count, `independent_voices = verifiers.independence_groups(records)["independent_groups"]`, roles_present, up to 3 sample_quotes, products_named, `lead_id` = most common lead among records, `seed_population` from that lead, `threshold` = the threshold used.
- `authority = ANCHOR` iff record_count ≥ min_records AND thread_count ≥ min_threads AND independent_voices ≥ min_independent_voices; else THIN.
- Cluster unknowns: missing core roles; `"moment (before/during/transition/after) unknown"` when no record has `moment`; `"workaround unknown"` when no workaround text; `"only N thread(s) — independence unproven"` when threads < min_threads.
- Threshold = policy `lived_world.anchor_threshold`, and a run's settings may only RAISE it (`settings.effective(state, "lived_world.anchor_<key>", None)` → `max(policy, setting)`).
- Lead statuses: recompute `record_ids` per lead; INSTANTIATING → INSTANTIATED if it has records else EXHAUSTED.
Replace `participant_cards` and `lived_clusters` wholesale (deterministic recompute).

### 5.4 `gate(state, policies)` — executor `python.population_gate`
anchors = ANCHOR clusters; records = len(field_records); rounds = queue round; elapsed = minutes since `population_queue.started_at`;
progressed = records or anchors grew since the previous gate; stagnant = not progressed and rounds > `stagnation_rounds`;
need = anchors < `min_anchor_clusters`; remaining = eligible leads.
`continue = need and not (rounds ≥ max_rounds or stagnant or elapsed ≥ wall_clock_minutes or not remaining)`.
Write `state["population_loop"] = {continue, rounds, anchors, records, elapsed_min, remaining_eligible, reason}` where reason names every ceiling that fired.

### 5.5 Validators (called from `controller.cmd_submit`)
- `validate_leads(items, state)`: COMMUNITY lead needs `community_key` or `platform`; submitted status must be NOMINATED (or absent); authority must be LEAD.
- `validate_records(items, state, policies)`: `verifiers.admit_observations` errors + `lead_id` must be a nominated lead in this run + non-empty `quote_ref`.
- `validate_situations(items, state, policies)`: unknown `cluster_id` → error; any friction with authority FIELD_OBSERVATION must cite non-empty refs that exist among field_records ∪ observations; FIELD_ANCHORED requires a cluster_id whose authority is ANCHOR and ≥1 FIELD_OBSERVATION friction (message names the cluster's records/threads/voices when THIN); RECONSTRUCTED requires a cluster_id or known evidence_refs AND non-empty unknowns (message: "a reconstruction with no unknowns is a biography"); SIMULATED may not sit on a cluster.
- `validate_hypothesis_anchors(hypotheses, state, policies)` (only when `bridge.require_lived_anchor`): each hypothesis names `lived_anchor_ids` (every id must exist and be ANCHOR; sets `grounding: LIVED`) or declares `grounding: CORPUS_ONLY`; otherwise error "silence is not a lane".
- `validate_portfolio_anchors`: when any ANCHOR cluster exists, at least `portfolio.min_lived_anchored` hypotheses carry anchors.
- Anchor validation runs ONLY at node `hypothesize` (status updates at `challenge` never re-litigate lanes). Keep the docs/20 rule at challenge: `allocation.starved_rejections` inside the hypotheses block.

### 5.6 `compile_corpus_questions` — executor `python.corpus_question_compiler` (on_enter of `corpus_mechanisms`)
Clusters ordered ANCHOR first, then by independent_voices desc. Per cluster fill the
`corpus.question_forms` slots: `friction` = friction_family with underscores → spaces
(or the three most common problem tokens when "unassigned"), `workaround` = first
non-empty workaround (≤90 chars), `context` = community, `behavior` = first
BEHAVIOR_SUPPORT record's problem (≤90). Skip a form whose slots are empty; dedupe text;
cap at `max_questions`. Each question: `{id stable("cq", cluster_id, i), cluster_id, community,
kind (workaround | mechanism | analogy | behavior), question, authority_of_answer: CORPUS_SYNTHESIS,
cluster_authority}` → `data.corpus_questions`. Never mention a person.

### 5.7 `summary(state)` — used by `status` and `utilization.lived_world`
leads, leads_by_lane, leads_by_status, seed_population_leads, field_records, records_by_origin,
participant_cards, clusters_by_authority, clusters_outside_seed, situations_by_authority,
unknowns_preserved, corpus_questions, rounds, loop.

### 5.8 `provenance.py`
- Token rule: lowercase words ≥4 letters minus stop words, with light plural folding:
  `ies→y`; `sses|shes|ches|xes|zes → strip "es"`; trailing `s` (not `ss`) → strip; all for len > 4.
- `tag_corpus_examples(rows, example_terms)`: build doc → major entities from rows carrying
  `document_summary.major_entities` (len ≥ 4, not generic); a row is tagged `CORPUS_EXAMPLE`
  (tag appended, `example_terms` = matched names) when its text contains such an entity as a
  whole word that appears capitalized in the text, or contains a given example term. Never drops a row.
- `example_overlap(concept, state)` = concept tokens (name + form_factor) ∩ brand tokens of
  tagged rows, ∪ content tokens of tagged rows of length ≥ 6 (minus a generic list: women, people,
  market, products, specific, proven, segment, brands, business, customers, company, selling, sells,
  money, example, things, something), ∪ all row-token hits when there are ≥ 2 of them.
- `lineage(concept, state, policies)`: cited = concept.evidence_refs resolved against
  field_records ∪ observations, plus the records of its hypothesis' ANCHOR clusters (hypothesis
  found via mechanism.hypothesis_id); `independent_voices = independence_groups(cited)`;
  communities = distinct normalized communities; `field_originated` = concept content tokens
  absent from every non-field corpus row AND present in some record's `products_named`/workaround.
  Verdict: GROUNDED if voices ≥ min_independent_voices and communities ≥ min_communities (legal
  even with example overlap); else `echo_verdict` if overlap AND no ANCHOR anchor AND no
  field-record ref; else ECHO_WEAKLY_GROUNDED if overlap; else UNGROUNDED.
- `enforce(state, policies)`: writes `data.provenance` (one row per concept), stamps
  `concept.provenance` and `concept.field_originated`, moves leads whose concept verdict is the
  echo verdict into `data.excluded_leads` (with `excluded_reason`), keeps the rest with `provenance`.
- `corpus_contribution(state)`: cited row ids from primitives.evidence_refs, hypotheses.hop_refs,
  admitted corpus_answers citations, lived_situations friction refs, mechanisms.corpus_refs →
  `{rows_retrieved, rows_cited, documents_retrieved, documents_cited, cited_share_of_shelf,
  cited_by_document, example_rows_retrieved, example_rows_cited, mechanism_only_contributions
  (cited, not CORPUS_EXAMPLE, sharing no token with any concept name), question_level_rows}`.

### 5.9 Integration points
- `executors.scoring` (qualify): after leads are capped call `provenance.enforce`; verdict
  QUALIFIED_LEADS / PROVISIONAL_LEADS as before; if leads existed and all were excluded →
  verdict = `provenance.echo_verdict`; else MECHANISM_WITHOUT_SUPPLY. Append the provenance summary to the note.
- `qualify.KNOWN_VERDICTS["opportunity_research"]` += `CORPUS_ECHO_UNGROUNDED`.
- `ideation.validate_concepts`: `evidence_refs` may name field_record ids.
- `satisfaction._roles_present` and its independence count include non-contradicting field_records.
- `candidates.emit_communities(state)`: each ANCHOR cluster → `COMMUNITY_CANDIDATE` (payload
  community, friction_family, records, threads, independent_voices, seed_population; refs = record ids);
  called at the end of `auto_emit`.
- `utilization.compute` += `lived_world` (5.7), `corpus_contribution`, `provenance {verdicts,
  field_originated_concepts, excluded_leads, concepts_outside_seed}`; `to_markdown` renders them.
- `report`: model carries `provenance` and `excluded_leads`; render a Provenance table before Qualified Leads.
- `field_evidence.py --leads`: FIELD_OBS rows → `field_records` for the lead whose `community_key`
  matches the row's community (origin PRIOR_RUN, original author/thread, freshness recomputed by the
  existing decay rule). Output `{"field_records": [...]}`.
- `corpus_polymath.py`: `--questions` flag, automatic when `state.node == "corpus_mechanisms"`:
  queries = `data.corpus_questions` (`asked_as` = the question; chat lane asks it verbatim; the plan
  lane is replaced by per-question retrieve); rows whose `query_ids` hit a question get `question_id`,
  `question_ids`, `cluster_id`, tag `question_level`; empty questions → `capability_failure
  corpus_questions`. Always run `provenance.tag_corpus_examples(rows, data.example_terms)` before
  writing the payload; report `corpus_example_rows` and `question_level_rows` in the stderr note.

---

## 6. Controller and data-model hooks

- `controller.SCHEMA_BY_KEY` += `population_leads, community_leads → population_lead;
  field_records → field_record; participant_cards → participant_evidence_card;
  lived_clusters → lived_evidence_cluster; lived_situations → lived_situation;
  slot_candidates → product_slot; world_model → community_world_model`.
- `cmd_submit` hooks: hypotheses → known ids include field_records and lived_clusters; at
  `hypothesize` run `validate_hypothesis_anchors`, `validate_portfolio` (existing),
  `validate_portfolio_anchors`; at `challenge` keep `starved_rejections`;
  `population_leads`/`community_leads` → `validate_leads`; `field_records` → `validate_records`;
  `lived_situations` → `validate_situations`.
- `cmd_status` adds `lived_world: lived_world.summary(state)` for the product graph.
- `models.new_state` data keys += `population_leads, community_leads, field_records,
  participant_cards, lived_clusters, lived_situations, corpus_questions, example_terms, provenance` (lists).
- `memory._NODE_TYPES` += `population_leads: POPULATION_LEAD, community_leads: COMMUNITY_LEAD,
  field_records: FIELD_RECORD, participant_cards: PARTICIPANT_EVIDENCE_CARD,
  lived_clusters: LIVED_EVIDENCE_CLUSTER, corpus_questions: CORPUS_QUESTION`.
- `context._PRIORITY` += P1 `lived_clusters, lived_situations, provenance`; P2 `field_records,
  population_leads, community_leads`; P3 `participant_cards, corpus_questions, example_terms`.
- `doctor._known_data_keys` extras += `population_queue, population_loop, excluded_leads`.
- `executors.EXECUTORS.update(lived_world.EXECUTORS)` — the five executors of §5.

---

## 7. Prompts

New: `prompts/population_scout.md` (find real communities behind the leads, submit CommunityLeads
with search receipts, open-field rule, never invent a community, prefer communities outside the
seed population) and `prompts/community_instantiate.md` (run the batch's channel_queries, submit
field_records with author/thread identity, products_named, friction_family when it fits; run
`field_evidence.py --leads` first; stop a lead once past the anchor threshold; what people did not
say stays unknown).
Rewrite `prompts/lived_situation.md` around the three authorities and the biography rule.
Append to `bridge_hypothesis.md` (lived anchors / CORPUS_ONLY / CORPUS_EXAMPLE rows may back a
mechanism hop only), `opportunity_primitives.md` (`population_leads` output — places to look, never
demand), `latent_interpretation.md` (`example_terms`), `product_ideation.md` (lineage; prefer records
outside the seed population; one field-originated concept with `origin: FIELD`).

---

## 8. Proof — the tests you must add and pass

### 8.1 Harness section 20 (labels to reproduce in `tests/run_all.py`)
1. population_lead schema accepts a well-formed lead; refuses any authority but LEAD
2. lived_situation schema requires unknowns; lived_evidence_cluster authority is THIN or ANCHOR only; product_slot roles are the five loadout roles
3. all four nomination lanes produce leads, every one authority LEAD
4. leads restating the signal's own population are marked seed_population; a book-named population is not
5. VOI ranking is monotone and discounts the seed population — non-seed leads are visited first
6. lead channel queries carry tool chains and the community key as the reddit scope
7. queue hands exactly batch_size leads and marks them INSTANTIATING
8. a visited lead with no records is EXHAUSTED, never padded
9. no ANCHOR yet and budget left: one more round
10. stagnation / round ceiling stops the loop honestly
11. wall-clock ceiling is enforced
12. 5 authors in 2 threads = 2 voices = THIN (same thread is one voice)
13. 5 records / 3 threads / 3 voices = ANCHOR at the default threshold
14. raising the threshold flips the same cluster to THIN — configurable, recorded on the cluster
15. six records from one author in one thread = ONE voice = THIN
16. questions ask about the friction and the workaround, never about a person; count honours corpus.max_questions
17. rows naming a document's proper-noun entity are tagged CORPUS_EXAMPLE; the mechanism row is not; nothing is dropped
18. lineage corpus example → same noun → same-noun search only = CORPUS_ECHO_UNGROUNDED
19. the SAME category stays legal when independent participants across communities ground it
20. a noun that lives only in field records is field-originated; the echoed noun is not
21. echo leads are excluded with the reason; grounded leads survive
22. contribution counts CITED rows (retrieved shelf with nothing cited = 0); a cited mechanism row sharing no noun with a concept is a mechanism-only contribution
23. prior field rows map to their community's lead with the original author and recomputed freshness, and pass the record contract
24. calibration acceptance reports six receipts and exits non-zero unless all pass
25. doctor green over the lived-world surface

### 8.2 The positive E2E walk (section 4) must traverse the new nodes and assert
registry leads nominated with authority LEAD; open-field CommunityLeads admitted; a DEMAND lead
rejected; the queue's first batch is non-seed open-field leads; a record for an unknown lead is
rejected; cards/clusters authorities (ANCHOR needs 3 threads); the gate proceeds at 2 anchors;
FIELD_ANCHORED on THIN rejected; biography rejected; anchored + reconstructed admitted; corpus
questions compiled; a hypothesis without a lane rejected; a THIN anchor rejected; a concept cited
across communities is GROUNDED; a field-only noun is field-originated; utilization carries the three
new sections. Loadout fixtures (section 11d) must now include `moments`/`open_questions` in the world
model and `authority`/`unknowns` in lived situations (SIMULATED in R1, RECONSTRUCTED with
`evidence_refs` in R2).

### 8.3 `tests/calibration_acceptance.py --state run.json [--seed-communities r/x,r/y]`
Exit 1 unless all six pass; print thresholds with the verdict:
- concepts_outside_seed ≥ 2 and ≥ 50 % of kept concepts (kept = not the echo verdict; outside =
  cited communities not a subset of seed communities = `--seed-communities` ∪ seed_population leads ∪ `data.communities`)
- independent_voices_per_concept: every kept concept ≥ 3
- cited_share_of_shelf ≥ 0.5
- field_originated_products ≥ 1
- mechanism_only_corpus_contributions ≥ 1
- hypotheses_killed_or_reframed_by_field ≥ 1 (REJECTED with a contradicting observation on its gaps, or CHALLENGED with a REVISE evaluation)
Defaults live in the script; a `calibration` policy block may override them.

### 8.4 Commands
```
python3 python/controller.py doctor
RUN_ALL_CONTINUE=1 python3 tests/run_all.py
```
Never pipe the harness through `tail`/`grep` inside an `&&` chain when deciding to commit; read the
exit code. Commit only after both are green.

---

## 9. Path A — sync by copy from the reference tree

Reference tree: `polymath-v4/research/` at Polymath main `a7f4f31` (or later). The delta since the
standalone's v1.6.0 is 44 files (v1.7.0 + v2.0.0):

```
SKILL.md  WORKLOG.md  manifest.yaml
docs/23_registry_maintenance.md  docs/24_evidence_channels_and_sourcing.md  docs/25_population_discovery_and_lived_world.md
graph/control_graph.yaml  graph/policies.yaml
prompts/bridge_hypothesis.md  prompts/community_instantiate.md  prompts/latent_interpretation.md
prompts/lived_situation.md  prompts/opportunity_primitives.md  prompts/population_scout.md  prompts/product_ideation.md
python/candidates.py  python/context.py  python/controller.py  python/corpus_polymath.py  python/doctor.py
python/executors.py  python/field_evidence.py  python/ideation.py  python/lived_world.py  python/market_discovery.py
python/memory.py  python/models.py  python/product_anchored.py  python/provenance.py  python/qualify.py
python/report.py  python/satisfaction.py  python/sourcing_exa.py  python/transitions.py  python/utilization.py
schemas/community_world_model.json  schemas/field_record.json  schemas/lived_evidence_cluster.json
schemas/lived_situation.json  schemas/participant_evidence_card.json  schemas/population_lead.json  schemas/product_slot.json
tests/run_all.py  tests/calibration_acceptance.py
```

Procedure:
1. `git clone https://github.com/Kingsley-Cyber/TRAIL_AGENT_AUTORESEARCH.git && cd TRAIL_AGENT_AUTORESEARCH && git checkout -b v2-lived-world`
2. Copy the 44 files from the reference tree over the standalone (same relative paths). Do NOT copy
   `state/`, `registry/compiled/`, `registry/patches/`, `candidates/`, `registry/research_evidence.csv`,
   or any `*.sqlite3`.
3. Diff for standalone-only differences and keep them: the standalone's `README.md`, `.gitignore`
   (must still ignore `registry/research_evidence.csv`, `registry/patches/`, `state/`), docs 01–18 (.txt).
4. Run §8.4. Fix anything path-specific (the reference assumes it is a sibling of Polymath only in
   docs prose; the code resolves paths from its own tree).
5. Commit `v2.0.0: LIVED-WORLD-V2 mirrored from polymath-v4/research (docs/24-25)`, push, open a PR
   or merge to main per the repo's convention.

## 10. If the standalone is still at v1.6.0, also mirror v1.7.0 (docs/24)
- `executors._CHANNEL_TEMPLATES`: 7 channels `(channel, template "{q}"-form, family, why,
  expected_roles, {tools[], identity, freshness, law?, limits?})` — reddit (community), amazon_reviews
  (review: PRODUCT_COMPLAINT/WORKAROUND/COMPARISON/REQUEST/CURRENT_PRODUCT_REFERENCE, never
  FRICTION_EVIDENCE), youtube, tiktok (captions only), xiaohongshu, twitter, forum (Exa + reader).
- One shared builder `executors.channel_queries(gid, question, state, policies, id_prefix)` used by
  `gap_compiler`, `market_discovery.market_gaps` (prefix `mq`) and `product_anchored.bridge_gaps`
  (prefix `bq`); emits one query per channel in `policies.evidence_channels` order with `tools`
  (the `{q}` placeholder replaced by the short keyword form), `identity`, `freshness_hint`, `law`,
  `limits`, `source_family`, `expected_evidence_roles`, `cannot_satisfy`.
- `sourcing_plan_compiler`: one job per concept PER channel in `policies.sourcing.channels`
  (`[alibaba, cjdropshipping]`) with tool text; `supplier()` sets `moq_units` from
  `supplier.moq_default_by_channel` (cjdropshipping: 1, with `moq_note`); leads carry `channel`.
- `python/sourcing_exa.py`: per-concept per-channel Exa sourcing; listing regexes for
  `alibaba…/product-detail/<slug>_<id>.html` and `cjdropshipping…/product/<slug>-p-<id>.html`;
  keep price/MOQ text verbatim, `NOT_SHOWN = "not shown in listing snippet"`; blank prices > 100 as
  non-unit; output `supplier_candidates` with `concept_id`, `mechanism_id`, `channel`.
- utilization `leads.by_channel`, `observations.by_platform`; report lead line prefixed with channel.
- Harness section 19 (7 checks): every enabled channel compiled per gap in policy order; tool chain,
  identity, family on each; amazon_reviews may not establish FRICTION_EVIDENCE; disabling a channel
  removes its queries; a review record admitted for complaint/workaround and refused for friction;
  CJ row without MOQ defaults to 1 and an Alibaba row does not; the sourcing helper parses both URLs
  and never invents a missing value.

## 11. Do-not list (each line is a law someone already paid for)
- Do not treat the evidence CSV or one-comment author rows as lives; do not add a people database.
- Do not let a lead, a corpus row, a trend or a supplier listing establish current demand.
- Do not fan out per life; the controller is one action per node with bounded rounds.
- Do not refuse a product because a corpus example mentioned its category; refuse only lineage that is
  corpus example → same noun → same-noun search with no independent field grounding.
- Do not measure corpus contribution by documents returned; count cited rows.
- Do not put authority labels in prompt text without a schema and a validator behind them.
- Do not change the evidence-authority table (docs/04), the independence law, or registry mutation
  rules (candidates → maintenance → human approval).
- Do not commit `registry/research_evidence.csv` (usernames, verbatim quotes) to the public repo.
- Do not add third-party dependencies beyond PyYAML; Python ≥ 3.9.

## 12. Your final report (plain text)
1. Commit hash(es) and branch in the standalone; whether pushed.
2. `tests/run_all.py` total and the exit code; `doctor` result.
3. Every section-20 label from §8.1 you could not reproduce, with the reason.
4. Files you changed that are NOT in the §9 manifest, and why.
5. What you did not do.

---

## 13. v2.1.0 addendum — source-agnostic interpretation (docs/26) — mirror this too

Reference: Polymath main after 2026-09-04 evening (`research/` v2.1.0). Add to the manifest of §9:
`docs/26_source_agnostic_interpretation.md`, `schemas/latent_structure.json`, `schemas/corpus_observation.json`,
and the v2.1.0 versions of `python/{lived_world,provenance,controller,executors,utilization,corpus_polymath}.py`,
`prompts/{opportunity_primitives,population_scout,bridge_hypothesis,latent_interpretation}.md`,
`graph/policies.yaml` (`corpus.relevance_classes`, `corpus.interpretation_kinds`, `lived_world.nominate_max_latent`,
`LATENT` source yield, `calibration` block), `tests/calibration_acceptance.py`, `tests/run_all.py` (section 21).
Spec in one paragraph: primitives carry `latent_structures[]` (24 kinds, authority LATENT_HYPOTHESIS),
`corpus_observations[]` (OBSERVED_PRODUCT | EXAMPLE | NAMED_POPULATION, authority NONE_FOR_CURRENT_DEMAND) and
`row_relevance {row_id: LEXICAL_MATCH | SEMANTIC_MATCH | STRUCTURAL_ANALOGY | IRRELEVANT}`; the controller validates
them, mirrors them into `data.latent_structures / corpus_observations / row_relevance`, stamps `relevance` on rows,
and rejects hop_refs citing IRRELEVANT rows; `structural_lookup` skips IRRELEVANT rows; `population_nominate` adds
NAMED leads from `possible_populations` and `search_mode: LATENT` leads (source_lane LATENT, queries from the
structure text) from searchable kinds, capped by `nominate_max_latent`; provenance gains `observation_terms`,
`corpus_named(concept)` (bigram in corpus text, or ≥2 tokens / a brand token shared with observations) and
`hop_cites_corpus`; the acceptance script evaluates the eight canaries of docs/26 §6 and reports shelf share as a
diagnostic only. Harness section 21 must cover: both schemas, primitives mirror + rejection of an unknown relevance
class, LATENT lead nomination with structure-language queries, IRRELEVANT rows refused in hop_refs and skipped by
analogies, `corpus_named` true/false cases, and the canary statuses (PASS / NOT_TRIGGERED / FAIL) on synthetic states.
