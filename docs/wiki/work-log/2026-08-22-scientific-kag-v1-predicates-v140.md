---
change_id: scientific-kag-v1-predicates-v140
owner: worker
date: 2026-08-22
status: complete
architecture_impact: rule-pack-supersede-v140-research-relations
last_reviewed: 2026-08-22
---

# SCIENTIFIC-KAG-V1 SLICE D (phase 4): research predicates v1.4.0

## Contract

Owner mission phase 4: the ten research relations that turn the entity
KG into a KAG. Pack superseded deliberately (never edited in place):
core-predicates-v1.4.0.yaml — 35 predicates over the 35-type backbone,
signature families resolving through type-ontology-v1.

## Predicate decisions (collision-aware authoring)

| owner name | landed as | why |
|---|---|---|
| introduced | NEW `introduced` (introduce) | lemma unclaimed |
| proposed | NEW `proposed` (propose, present) | unclaimed |
| uses_method | `uses` signatures widened to scientific subjects/objects | lemma 'use' already owned by uses; splitting would force AMBIGUOUS abstains |
| contains_component | NEW `contains_component` placed BEFORE part_of; claims include/comprise/consist/compose/contain/constitute/incorporate + nouns component/element/subcomponent | re-homed from part_of, which keeps part/member/section nouns + all multiword phrases ("component of" still routes to part_of) |
| trained_on | NEW `trained_on` (train) | unclaimed |
| evaluated_on | NEW `evaluated_on` (evaluate) | unclaimed |
| outperforms | NEW `outperforms` (outperform, surpass, exceed) | unclaimed |
| implemented_by | `implemented_with` signatures widened (Model/Framework/Algorithm → Software/Library/Tool); 'implement' also removed from developed so implemented_with owns it | duplicate claim would mis-route |
| released_on | NEW `released_on` (release) | unclaimed |
| occurred_on | `occurred_at` signatures widened (Experiment/Release/TrainingRun subjects; Date/TimePeriod objects) | temporal event predicate already existed |

Signatures accept BOTH vocabularies where GLiNER register decides:
Document alongside Paper; TimeReference alongside Date/TimePeriod.

## Collateral fixes the new predicates forced

1. Scope analyzer substring bug: attribution cue "per" matched inside
   "paper"/"period" and falsely QUALIFY'd sentences
   (`negation.py` now matches cue token sequences). Same disease class
   as the trigger substring fix.
2. Control-framed infinitives take prep>pobj objects when the subject
   arrived via control ("enables B to train on D" → trained_on(B, D)).
3. fact_admission_policy.yaml: orientation entries for all seven new
   asymmetric predicates (F7 would REJECT without them).
4. Deliberate supersede chain: SEMANTIC_CONTRACTS.md declares 1.4.0;
   settings default 1.4.0; boot env default 1.4.0; compiled tables
   compiled_lexical-v1.4.0.json; bundle re-frozen v5-production-005
   (bdfec5d02b7f1b06).

## Proof

- Direction tests green: trained_on(BERT, BooksCorpus) ACCEPT;
  reverse rejected by signature; introduced/released_on/
  contains_component fire on owner examples; object-control trio shape
  yields trained_on(Bertie, WikiText) with OpenAI excluded.
- Full suite: 876 passed, 68 skipped.
- Boot gate READY --strict under declared==loaded 1.4.0.

## Open gaps

P6 live validation on real text; acceptance harness; 4-doc suite.
