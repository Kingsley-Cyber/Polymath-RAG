# SCIENTIFIC-KAG-V1 — Summary Intelligence & Vocabulary Layer (design of record)

> Owner-issued 2026-08-23. This document is the work order for the
> summary waterfall. Implementation slices must conform to it; deviations
> require an owner decision recorded here.

## Position in the architecture

                    CONTROL PLANE
                         |
                         v
                 Evidence Ledger (L0-L4)
                         |
                         v
              Entity / Fact / Event Settlement
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
 Parent Summary    Document Summary   Corpus Summary
      Worker            Worker            Worker
        |                |                |
        +----------------+----------------+
                         |
                         v
                Vocabulary / Concept Layer
                         |
                         v
              Retrieval + Query Routing

The summary layer CONSUMES settlement outputs; it never competes with
Entity Admission or Fact Admission. Waterfall:

    Evidence -> Knowledge -> Summaries -> Concepts -> Retrieval

## The three layers

### 1. Parent Summary (retrieval bridge)

Input: parent chunk + child chunks + accepted facts + accepted entities
+ accepted events.
Output artifact fields: `summary_type: parent`, `parent_id`,
`derived_from: [child_001, ...]`, `entities: [...]`, `concepts: [...]`,
`summary`.
Purpose: queries hit parent summaries first, then relevant children,
then evidence — never raw chunks cold.

### 2. Document Summary

Input: ALL parent summaries (never raw text).
Output fields: `document`, `summary`, `major_entities`,
`major_concepts`, `methods`, `questions_answered`.
Purpose: "What is this document about?"

### 3. Corpus Summary (research assistant / router)

Input: document summaries only.
Output fields: `domains`, `dominant_concepts`, `important_entities`,
`common_predicates`, `research_questions`.
Purpose: query routing.

## Vocabulary layer (consumes summaries, not raw chunks)

Wrong: raw chunks -> keywords -> concepts (junk).
Correct: accepted facts/events -> parent summaries -> document summaries
-> concept candidates -> VOCABULARY ADMISSION.

Vocabulary entry shape:

    concept: transformer_model
    aliases: ["transformer architecture", "transformer model",
              "attention-based model"]
    supported_by: [fact_001, fact_002, summary_001]

Alias evidence accumulates; no forced merge.

## Control-plane additions

New stages after event_admission, each own ticket/status:
`parent_summary`, `document_summary`, `corpus_summary`, `vocabulary`
(status pending until implemented).

Every artifact envelope MUST carry: `artifact_id`, `input_hash`,
`output_hash`, `version`, `model`, `prompt_version`, `derived_from`,
`created_at`.

## Production rules

- Summaries run as BACKGROUND workers; ingestion path stays
  Document → Extract → Facts → Events → Projection → READY.
- Summary failure ⇒ knowledge=READY, summaries=DEGRADED. Never
  "ingestion failed".

## Final query shape

QUERY → Corpus Summary Router → Vocabulary Resolver →
{Evidence Retrieval (Qdrant/BM25) | Graph Retrieval (Neo4j)} →
Answer Composer → Evidence + Provenance.

Separation of concerns: extraction creates KNOWLEDGE; summaries create
UNDERSTANDING of where knowledge lives; vocabulary creates TRANSLATION
between human language and that knowledge. All deterministic layers.

## Implementation slice order (agreed)

1. Control-plane stage declarations + artifact envelope schema.
2. Parent summary worker (deterministic composition from settled
   facts/entities/events over child chunks).
3. Document summary worker.
4. Corpus summary worker.
5. Vocabulary admission + concept candidates.
6. Query routing integration (Corpus Router → Vocabulary Resolver →
   Evidence/Graph lanes).

NOTE on generation: deterministic composition from settled structures
first; if a generative model renders summary PROSE later, its prompt +
version live in the artifact envelope and admission-style checks apply
to anything that could mutate meaning. No LLM may create facts,
entities, or events — summaries describe where knowledge lives.
