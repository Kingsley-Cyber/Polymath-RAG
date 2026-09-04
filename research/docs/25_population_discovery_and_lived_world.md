# 25 — Population discovery and the lived world (LIVED-WORLD-V2)

Owner (2026-09-04): "Accept the stress-test correction and revise the
lived-world architecture before adding further features … Real communities
generate the lived-world nouns; the corpus supplies deeper mechanisms and
analogies; θ bridges them; Python decides what is allowed to count."

What was wrong, measured on the 2026-09-03 runs: six marketing transcripts
hold about twelve product nouns and 1,369 method terms; two independent
pipelines produced the same GLP-1 / facial-hair / insole leads because the
product graph read only the corpus before hypothesizing, every observation
had to belong to a hypothesis gap, and the 371-row CSV re-clustered into the
exact three hypotheses it was collected for. The field was a validator of
corpus nouns. This document makes it a co-generator.

## §1 POPULATION_DISCOVERY before ideation

`structural_lookup → population_nominate → population_scout → population_queue
→ community_instantiate → evidence_cards → population_gate ⟲ → lived_situations
→ corpus_mechanisms → hypothesize`

| node | kind | what it does |
|---|---|---|
| population_nominate | φ | corpus (`primitives.population_leads`), registry situations (predicate / friction overlap with the primitives), the signal's own `communities`, and prior field rows each nominate `PopulationLead` / `CommunityLead` objects — `authority: LEAD`, `status: NOMINATED`; every lead carries compiled channel queries with tool chains (docs/24) |
| population_scout | agent | open field: finds the real communities behind the leads and anything current nobody nominated; submits `community_leads` (source_lane OPEN_FIELD) with search receipts as `nominated_by` |
| population_queue | φ | VOI-ranked work queue: yield(lane) × missing-information × decision impact / cost, discounted for leads that restate the seed population; hands ONE batch (`lived_world.batch_size`) per round — the controller is sequential, there is no fan-out |
| community_instantiate | agent | runs each lead's tool chains, submits `field_records` (schema field_record.json, same evidence contract as observations, keyed by `lead_id`); prior field rows re-enter via `field_evidence.py --leads` (origin PRIOR_RUN) |
| evidence_cards | φ | `ParticipantEvidenceCard` per real (platform, author); `LivedEvidenceCluster` per community × friction family with independent voices, threads, roles, unknowns; authority THIN / ANCHOR |
| population_gate | φ | another round while ANCHOR clusters < `min_anchor_clusters`, bounded by `max_rounds`, stagnation (no new record and no new ANCHOR) and `wall_clock_minutes`; routes to `lived_situations`, or straight to `hypothesize` when no record survived (every hypothesis then CORPUS_ONLY) |

A lead never establishes demand. Only external records instantiate it. The
seed table stays an activity / context / friction prior; it is not a people
database and no people.csv exists.

## §2 Field records, not lives

`registry/research_evidence.csv` and the field-evidence corpus are FIELD
RECORDS: real quotes with author, thread, roles and freshness. They are not
lives. The 2026-09-03 CSV has 177 authors of which 53 left one row and 70 two;
median record 29 words. Treating an author row as a person is fiction with a
citation. Records re-enter runs as `field_records` for the lead whose
community they came from; they count, they are not invented, and they are
THIN until independent records join them.

## §3 Cards, clusters and the anchor threshold

`ParticipantEvidenceCard` = every record one real author left (record_count,
thread_count, roles_present, unknowns = the core roles never recorded).
`LivedEvidenceCluster` = cards sharing community × friction family.
`authority: ANCHOR` when record_count ≥ `min_records` (5), thread_count ≥
`min_threads` (2) and `independent_voices` ≥ `min_independent_voices` (3,
verifiers.independence_groups: same author or same thread = one voice). Below
that the cluster is THIN: it may feed explicit reconstruction only. The
threshold is policy (`lived_world.anchor_threshold`) and a run's settings may
tighten it, never loosen it. Clusters carry their `unknowns` and the exact
threshold they were judged against.

## §4 Lived situations keep their unknowns

`lived_situation.json`: FIELD_ANCHORED requires an ANCHOR `cluster_id` and at
least one friction with `authority: FIELD_OBSERVATION` and known `refs`;
RECONSTRUCTED sits on a cluster (or cited observations) and MUST list
`unknowns` — "a reconstruction with no unknowns is a biography" is a
validator message, not advice; SIMULATED has no records behind it (loadout
round 1) and simulation is never evidence. `CommunityWorldModel` and
`ProductSlot` gained schemas for the same reason: authority labels were
prompt text before; they are enforced by schema + Python now.

## §5 The bridge names its lane

`bridge.require_lived_anchor: true`: a hypothesis carries `lived_anchor_ids`
(ANCHOR clusters only) or declares `grounding: CORPUS_ONLY`. THIN clusters
cannot anchor. Whenever anchors exist, `portfolio.min_lived_anchored` (2)
hypotheses must anchor in lived clusters. Hop refs may cite corpus rows,
observations, field records and clusters. Corpus-only hypotheses are legal to
write and to research — their products simply cannot qualify on corpus
lineage alone (§7).

## §6 The corpus is asked at friction / mechanism level

`corpus_mechanisms` (`on_enter: python.corpus_question_compiler`) compiles
`corpus.question_forms` per cluster — "What explains this workaround: …?",
"What mechanism reduces {friction} when {context}?", "What analogous
constraint exists elsewhere for {friction}?" — never per person (measured:
three unrelated lives against ten books shared 18 of 19 documents; asking
per life discriminates nothing). `corpus_polymath.py --questions` (automatic
at that node) asks them through the full RAG; rows come back stamped
`question_id` + `cluster_id`, tagged `question_level`. Corpus diversity is
measured by CITED reasoning contributions (`corpus_contribution`: rows cited,
documents cited of retrieved, mechanism-only contributions, example rows
cited) — the shelf returning whole proves nothing. The corpus may supply
mechanisms, analogies, populations, activities and contexts as leads; never
current demand by itself.

## §7 Provenance replaces category echo refusal

Rows naming a document's proper-noun entity (or the signal's `example_terms`)
are tagged `CORPUS_EXAMPLE` — never dropped. At qualify, `provenance.enforce`
computes each concept's lineage: independent voices and communities behind
its refs (observations + field records + its hypothesis' anchor clusters),
overlap with example terms, field-record vs gap-observation refs, whether the
noun is field-originated (present in records, absent from every corpus row).
Verdicts: GROUNDED (≥ `provenance.min_independent_voices` voices from ≥
`min_communities` communities — legal even when it overlaps a corpus example);
`CORPUS_ECHO_UNGROUNDED` (example overlap, no lived anchor, no field record:
lineage is corpus example → same noun → same-noun search); otherwise
ECHO_WEAKLY_GROUNDED / UNGROUNDED. Echo leads are excluded with the reason;
a run whose every lead was an echo ends `CORPUS_ECHO_UNGROUNDED`.

## §8 Calibration proves semantics, not execution

`tests/calibration_acceptance.py --state run.json` exits non-zero unless: ≥ 2
concepts (and half of those kept) anchor outside the seed population; every
kept concept has ≥ 3 independent voices; cited corpus share of the shelf ≥
0.5; ≥ 1 field-originated product absent from corpus nouns; ≥ 1
mechanism-only corpus contribution; ≥ 1 hypothesis killed or reframed by
field evidence. Thresholds live in policies (`calibration`, defaults in the
script) and are printed with the verdict. The first calibration run is the
same six transcripts; the pass condition is a product they never name.

## §9 What did not change

Extraction in Polymath (owner rule). The evidence authority table (docs/04).
The independence law. Registry mutation only through maintenance with human
approval (an ANCHOR cluster emits a `COMMUNITY_CANDIDATE`, nothing more). The
controller: one action per node, rounds instead of fan-out, drift blocks.
