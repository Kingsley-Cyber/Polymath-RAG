# EXTRACTION REPORT — TEST copy.md (corpus test-copy-v1)

Ingested through the production path with the v2 intelligence stack
(kimi_v1 + Predicate Compiler v2 frame lane + syntax spacy).
Persisted: 5 admitted facts, 1 parent summary, document summary,
corpus map, vocabulary evaluated.

## Entities (70 discovered)

| Admission class | Count | Meaning |
|---|---|---|
| GLOBAL | 27 | cross-corpus named objects (Atlas, Sentinel, GLUE…) |
| CORPUS_SCOPED | 10 | corpus-local durable entities |
| DOCUMENT_SCOPED | 3 | single-document durable |
| MENTION_ONLY | 33 | evidence-only, correctly non-referential |

## Admitted facts — all with full provenance
(frame id · lexical source · role mapping · evidence span)

| Subject | Predicate | Object |
|---|---|---|
| Atlas Language Model | introduced_by | Quantum Research Group |
| Transformer Architecture | introduced_by | Advanced Neural Systems Laboratory * |
| Atlas | trained_on | GlobalText Dataset |
| Atlas | compared_against | previous language models |
| Sentinel | uses | MITRE ATT&CK Framework |

*head-chain resolved through "The Orion Transformer architecture" —
granularity note below.

## Rejections — every one correct

- **Adversarial section (Nova): 5 scope-gate rejections** —
  "may outperform", "appears similar", "not demonstrated" all refused
  by negation/speculative gates. ZERO false positives from Doc 4. ✓
- type_violation ×3: legacy trigger-lane candidates on wrong subjects
  (Document 2 / evaluation process) — fail-closed ✓
- frame_unmapped: temporal/agent-typed endpoints (2021, 2023,
  Researchers→OpenText Corpus) correctly unsupported until event layer
  and definite-description resolution land.

## Missing expected facts (classified)

- Orion trained_on OpenText Corpus — **C** (definite description "the
  model" not resolved to Orion)
- Orion evaluated_on GLUE — **C** (object inside prep phrase not bound)
- Sentinel created_by Secure Horizon Labs — **D→B**: `created` maps to
  creation_event but `created_by` mapping absent from ontology
- Nova section — **E** (all correctly rejected)

## Summaries & map

Parent summary composes the four admitted facts verbatim.
Document summary: entities Atlas/Sentinel/Transformer architecture;
methods introduced_by · trained_on · compared_against · uses.
Corpus map: entities + predicates with document-spread weights.
Vocabulary: 0 families (single document — support-overlap guard holds).

## Follow-ups for next slice

1. Ontology: add created_by / developed_by mappings (D-classification)
2. Definite-description binding ("the model" → Orion)
3. Head-chain through capitalized modifiers ("Orion Transformer…")
