# TEST.md EXTRACTION QUALITY ANALYSIS — STEP 5 (first scored run)
**Corpus:** test-validation-v1 · **Pipeline:** kimi_v2 + policy v3 + pack v1.4.0

## Verdict: EXTRACTION INCOMPLETE — predicate capture FAILED (0 candidates)
Entity layer: **STRONG PASS**. Relation layer: **FAIL — zero candidates
from text dense with licensed triggers.**

## Entity layer (human eyes vs system)
Human-expected scientific entities vs system output:

| expected | system | verdict |
|---|---|---|
| Tree of Thoughts (FRAMEWORK) | ✅ DURABLE Framework ×2 | PASS |
| BERT / BERT-style architectures | ✅ DURABLE Architecture | PASS |
| GLUE, SQuAD (BENCHMARK) | ✅ DURABLE Benchmark | PASS |
| Google, Microsoft, OpenAI, Princeton | ✅ DURABLE Organization/RG | PASS |
| GPT (MODEL) | ✅ DURABLE Model | PASS |
| Game of 24 (TASK) | ✅ DURABLE Task | PASS |
| March 2023 / 2018 (DATE endpoints) | ⚠️ mention-only Date | PARTIAL — date_expression gate passes qualification but production promotion path didn't fire |
| thought generators, state evaluators | ❌ absent (doc lacks those phrases) | n/a |

No cross-domain bleed (biomedical/cyber terms stayed mention-level);
adversarial DOC_003 terminology correctly never became durable facts.
**Entity recall ≈ high; contamination 0.**

## Relation layer: ZERO candidates — root cause open
Text contains licensed triggers (`introduces`, `evaluated`, `trained`
via "pretrained", `enables`) plus durable endpoint pairs. Expected ≥:
introduced(Google Research → BERT-style architectures) ·
evaluated_on(BERT → GLUE/SQuAD). System emitted none.

Two suspect layers, both queued:
1. This document may have extracted during the `_admitted_facts`
   regression window (`af5f94b` fixed it); re-run required before
   grading is valid.
2. Lemma gaps: "was **pretrained** using BooksCorpus" — `pretrain`
   ∉ trained_on verb list ([train]); "was **evaluated**" ✓ licensed.
   Registry vocabulary audit needed (mission phase-4 list vs pack).

## What must happen before a fair grade
1. Re-extract test-validation-v1 post-regression-fix (one manifest replay).
2. Add `pretrain/pretrained` to trained_on authored verbs if owner agrees
   (registry vocabulary decision, not code).
3. Re-score with acceptance harness against the labels below (frozen).

## Human label fixtures (drafted from reading; owner review requested)
entities: BERT · BooksCorpus · English Wikipedia · GLUE · SQuAD ·
Tree of Thoughts · Game of 24 · Google Research · Princeton University ·
GPT · Microsoft · OpenAI
facts: introduced(Tree of Thoughts, framework) ·
introduced(BERT-style architectures ← Google Research, 2018) ·
pretrained/trained_on(BERT, BooksCorpus+Wikipedia) ·
evaluated_on(BERT, GLUE) · evaluated_on(BERT, SQuAD) ·
evaluated_on(ToT, Game of 24 / creative writing / crosswords)
events: release/evaluation events with 2018 / 2023 anchors
adversarial expectations: DOC_003 similar_to count = 0 · DOC_004
cyber/biomed "model" separation preserved
