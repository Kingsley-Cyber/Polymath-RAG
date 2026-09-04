---
title: "WORK LOG — LIVED-WORLD-V2: population discovery before ideation"
change_id: LIVED-WORLD-V2
date: 2026-09-04
owner: governance
status: shipped
register: 11.72
package: research/
architecture_impact: "research/ product graph v2.0.0 — population discovery precedes hypotheses; seven new schemas; provenance verdicts at qualify; Polymath API and extraction untouched"
---

# WORK LOG — LIVED-WORLD-V2: population discovery before ideation

Owner directive (2026-09-04): accept the stress-test correction and revise the
lived-world architecture before adding further features. Real communities
generate the lived-world nouns; the corpus supplies deeper mechanisms and
analogies; θ bridges them; Python decides what is allowed to count.

## Why now

Measured 2026-09-03: six transcripts hold ~12 product nouns against 1,369
method terms; the product graph read only corpus rows before hypothesizing;
`observation.gap_id` was required, so the field could only validate; the
371-row CSV re-clusters into the three hypotheses it was collected for; three
unrelated lives against ten books shared 18 of 19 documents. Two independent
pipelines produced the same GLP-1 / facial-hair / insole leads. Directional
inversion, not a diversity bug.

## Contract

- **POPULATION-DISCOVERY-V1** — `population_nominate → population_scout →
  population_queue → community_instantiate → evidence_cards → population_gate ⟲`
  precedes `hypothesize` in `research/graph/control_graph.yaml` (v2.0.0).
  Leads (`schemas/population_lead.json`) carry `authority: LEAD` only; corpus,
  registry, signal, prior field rows and the open field may nominate; only
  external `field_records` (`schemas/field_record.json`, the observation
  evidence contract keyed by `lead_id`) instantiate.
- **EVIDENCE-CARDS-V1** — `participant_evidence_card` (per real author) and
  `lived_evidence_cluster` (community × friction family) with `authority`
  THIN / ANCHOR from `policies.lived_world.anchor_threshold` (5 records, 2
  threads, 3 independent voices; settings may tighten only). `lived_situation`
  FIELD_ANCHORED only on ANCHOR clusters with FIELD_OBSERVATION refs;
  RECONSTRUCTED must list unknowns; SIMULATED never evidence.
  `community_world_model` and `product_slot` gained schemas (loadout).
- **LIVED-ANCHORS-V1** — `bridge.require_lived_anchor`: a hypothesis names
  `lived_anchor_ids` or `grounding: CORPUS_ONLY`; `portfolio.min_lived_anchored`
  when anchors exist; validated at `hypothesize` only.
- **CORPUS-QUESTIONS-V1** — `corpus_mechanisms` node (`on_enter
  python.corpus_question_compiler`, `corpus.question_forms`) asks Polymath at
  friction / mechanism level; `corpus_polymath.py --questions` automatic at
  that node; rows stamped `question_id` / `cluster_id`, CORPUS_EXAMPLE rows
  tagged deterministically from document major entities.
- **PROVENANCE-V1** — `provenance.enforce` at qualify: GROUNDED (≥3 voices,
  ≥2 communities, legal even with example overlap) / `CORPUS_ECHO_UNGROUNDED`
  (example overlap, no lived anchor, no field record) / ECHO_WEAKLY_GROUNDED /
  UNGROUNDED; echo leads → `excluded_leads`; verdict `CORPUS_ECHO_UNGROUNDED`
  when every lead was an echo. `corpus_contribution` receipt counts CITED
  rows and documents, never documents returned.
- **CALIBRATION-ACCEPTANCE-V1** — `research/tests/calibration_acceptance.py`
  exits non-zero unless six semantic receipts pass (§8 of docs/25).
- Controller law kept: one action per node; population rounds bounded by
  `max_rounds`, stagnation and `wall_clock_minutes`; no fan-out.

## Changes

`research/`: `python/lived_world.py` (new), `python/provenance.py` (new),
`schemas/{population_lead,field_record,participant_evidence_card,
lived_evidence_cluster,lived_situation,community_world_model,product_slot}.json`
(new), `prompts/{population_scout,community_instantiate}.md` (new),
`prompts/{lived_situation,bridge_hypothesis,opportunity_primitives,
latent_interpretation,product_ideation}.md`, `graph/control_graph.yaml`,
`graph/policies.yaml` (`lived_world`, `provenance`, `corpus.question_forms`,
`bridge.require_lived_anchor`, `portfolio.min_lived_anchored`),
`python/{controller,transitions,executors,models,memory,context,doctor,
qualify,ideation,satisfaction,candidates,utilization,report,field_evidence,
corpus_polymath}.py`, `tests/run_all.py` (walk rewritten through population
discovery; section 20), `tests/calibration_acceptance.py` (new),
`docs/25_population_discovery_and_lived_world.md` (new), `SKILL.md` (v2.0.0),
`WORKLOG.md`, `manifest.yaml` (architecture v2-LIVED-WORLD).
`scripts/scaffold_polymath_v4.py`: TREE rows for the 13 new files.
Polymath extraction: untouched.

## Proof

- `RUN_ALL_CONTINUE=1 python3 research/tests/run_all.py` → **ALL 454 CHECKS
  PASSED** (403 before this slice). New assertions include: lead authority
  refusal, record-to-lead binding, THIN vs ANCHOR at the threshold and after
  tightening it, the independence law inside clusters (6 records / 1 author =
  1 voice), stagnation and wall-clock ceilings, FIELD_ANCHORED-on-THIN
  refusal, biography refusal, hypothesis lane refusal, CORPUS_EXAMPLE tagging,
  echo vs legal-overlap verdicts, field-originated detection, cited-vs-retrieved
  contribution, the acceptance script's six receipts, doctor green.
- `python3 research/python/controller.py doctor` → ok (from the Hermes symlink too).
- `.venv/bin/python scripts/repo_guard.py` → ok.
- Merged to main `dcd762e`.

## Rejected claims

- "Per-life corpus retrieval differentiates books" — measured false (18/19
  documents shared); the corpus is asked at question level instead.
- "The CSV is many lives" — 53 of 177 authors left one row; it is field records.
- "Category blacklists stop echoing" — over-refuse and miss paraphrases;
  replaced by lineage.
- "Fan out one agent per life" — the controller is one action per node; a
  VOI work queue with bounded rounds replaces it.

## Open contract gaps

- The first calibration run has not been executed. Pass condition: the same
  six transcripts must qualify a product they never name, with all six
  acceptance receipts green. Needs an agent (Hermes or the executor) driving
  channels for population instantiation; roughly one hour.
- Document-scoped retrieve (`document_ids` on `/retrieve` and `/retrieve/plan`)
  is in flight on a separate branch; not required by this contract.
- `calibration` policy block: thresholds currently live as script defaults.
- Design docs 01–18 exist only in the retired TRAIL clone as text files; the
  skill cites them. Copying them in is housekeeping, not this contract.
