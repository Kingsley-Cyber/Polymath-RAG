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

---

# INTELLIGENCE BRIEF 2 (2026-08-23): baseline run under 1.4.0/v3

Source run `run_a5b1c4…` (all stages ok). Doc `doc_5db710…` (TEST.md,
5 chunks, DOC_001–004 designed fixture).

## 1 Entity Intelligence — HEALTHY

49 mentions → 26 admitted (16 GLOBAL · 10 CORPUS_SCOPED) · 23
MENTION_ONLY (correct for generic noun phrases).

Key scientific entities discovered and admitted: BERT (Architecture),
GLUE + SQuAD (Benchmark), Tree of Thoughts (Framework), GPT (Model),
Google/Google Research/Microsoft/OpenAI (Org), Princeton University,
Game of 24 / creative writing / crossword solving (Task), 2018 + 2023
(Date mentions). Cross-domain homonyms correctly separated
(BERT-style architectures vs threat-model concepts vs biological
models — no cross-corpus merge).

Entity-layer MISS: BooksCorpus and English Wikipedia never proposed
(pretraining corpora absent from GLiNER label space or threshold).
Classification: entity DISCOVERY gap (feeds fix arc after replay).

## 2 Predicate Intelligence — ZERO CANDIDATES GENERATED

raw_predicate_evidence=0 · relation_candidates=0 · facts=0.
NOT an admission failure — candidate generation is trigger-scoped and
TEST.md matches only 3 of 203 pack trigger surfaces (like/rate/
require). The document's actual relational vocabulary — introduce(d),
pretrain(ed), evaluate(d), generate, rely on, enable, use, compare —
is absent from core-predicates-v1.4.0.

Expected-fact inventory blocked at generation (subject/predicate/
object all present as entities):
  BERT --introduced_by--> Google Research (2018)
  BERT --pretrained_on--> BooksCorpus ; English Wikipedia
  BERT --evaluated_on--> GLUE ; SQuAD
  Tree of Thoughts --introduced_by--> Princeton researchers (2023)
  ToT --evaluated_on--> Game of 24 etc.
  neural models --rely_on--> optimization procedures/datasets

## 3 Event Intelligence — BLOCKED UPSTREAM

2018/2023 detected as Date MENTION_ONLY; date promotion and event
creation require predicates first. No independent event defect.

## 4 Scientific Knowledge Assessment

Extracted knowledge: entity graph only. Missed: every relational fact
above. Miss attribution: predicate VOCABULARY (generation gate), not
admission/evidence gates — they never received a candidate.

## 5 Retrieval Readiness

Qdrant: 14 chunk receipts (vectors live). Document summary: pending
(non-blocking stage queued behind drain). Vocabulary/concept layers:
pending same. Graph usefulness currently = entity retrieval only.

## Phase-3 classification (owner taxonomy)

- CATEGORY A (missing deterministic rule): compound-NP head binding —
  "The BERT model was introduced" must bind BERT not "model".
  Quarantined red test already marks this spot.
- CATEGORY B (missing ontology/predicate vocabulary): trigger surfaces
  above; map introduced/pretrained/evaluated ONLY where semantic
  signatures prove equivalence (owner directive).
- CATEGORY C (expected rejection): once B lands, DOC_003 negatives
  ("may appear similar", "does not imply influenced") must REJECT via
  existing speculative/negation constraints — regression fixtures to
  assert rejection, not silence.
- CATEGORY D (architecture deficiency): none new. Pipeline mechanically
  sound end-to-end (evidence survives regardless of admission).

## Order of work (per owner lock)

Replay successor extraction → harness gap-sizing → then B-vocabulary
authored updates + A-binding fix together, fixtures first, replay,
harness again.

---

# FAILURE MATRIX (2026-08-24): every expected TEST.md fact traced

Stages traced: frame resolution -> role binding -> type checking ->
admission projection. v2 shadow semantics; NO rules modified.
Legend: A=entity_discovery · B=semantic_frame · C=role_binding ·
D=type_ontology · E=expected_rejection.

| # | Expected fact | Frame | Binding | Types | Class |
|---|---|---|---|---|---|
| 1 | BERT introduced_by Google Research | creation_event OK | passive-by binds; BERT nearest-left ✓ | Architecture+ResearchGroup→introduced_by ✓ | **PROJECTED PASS** |
| 2 | BERT pretrained_on BooksCorpus | training_event OK | object never proposed | unreachable | **A** |
| 3 | BERT pretrained_on English Wikipedia | training_event OK | object never proposed | unreachable | **A** |
| 4 | BERT evaluated_on GLUE | evaluation_event OK | ACTIVE voice; no left-entity subject; role orientation missing in legacy_v1 | Architecture+Benchmark ✓ once oriented | **C** |
| 5 | BERT evaluated_on SQuAD | evaluation_event OK | same as #4 | ✓ | **C** |
| 6 | ToT introduced_by Princeton researchers | creation_event OK | ToT >4 tokens left of trigger (intervening generic head chain) | ✓ | **C** |
| 7 | ToT evaluated_on Game of 24 | evaluation_event OK | pronominal subject "It" — durable-identity ban | ✓ | **C** |
| 8 | ToT evaluated_on creative writing | evaluation_event OK | endpoint only MENTION_ONLY (non-referential) | Task type exists ✓ | **A*** (admission-class) |
| 9 | ToT evaluated_on crossword solving | evaluation_event OK | same | ✓ | **A*** (admission-class) |
| 10 | NEG speculative similarity | zero frames fire ✓ | n/a | n/a | **E — correctly rejected TODAY** |

## Matrix totals (10 expected facts)

```yaml
projected_pass_v2:      1
entity_discovery_A:     2   # BooksCorpus, English Wikipedia
endpoint_nonref_A2:     2   # MENTION_ONLY endpoints (taxonomy split proposed)
role_binding_C:         4   # active-voice orientation x2,
                            # head-chain distance x1, pronoun x1
semantic_frame_B:       0   # v2 ontology covers every trigger present
type_mapping_D:         0   # signatures correct where reached
expected_rejection_E:   1   # speculative similarity — already safe
```

## Reading

- v2 eliminated CATEGORY_B entirely for TEST.md: every relational verb
  now resolves to a frame.
- The residual is dominated by BINDING (C): active/passive orientation
  and head-chain/pronoun subjects — exactly what PropBank role
  assignment (already present in kimi_v1 path) addresses; cutover
  replay must run kimi_v1+v2 lanes, not legacy_v1 positional binding.
- A* proposes a taxonomy refinement for owner ratification: split
  entity_discovery into A1 (never proposed: BooksCorpus) vs
  A2 (proposed but admission_class=MENTION_ONLY: creative writing).
  Fixes differ: registries vs referential-eligibility policy.

NO RULES MODIFIED — classification complete; awaiting fix authorization
per measured gaps.
