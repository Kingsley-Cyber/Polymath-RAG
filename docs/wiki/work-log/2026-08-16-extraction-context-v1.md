---
change_id: extraction-context-v1
owner: worker
date: 2026-08-16
status: complete
architecture_impact: adds-context-envelope-no-storage-change
last_reviewed: 2026-08-16
---

# EXTRACTION-CONTEXT-V1: bounded context envelope for GLiNER

## §0 Inference-contract map (from repository reality)

1. **Chunk creation**: intake_worker → semantic_chunk_rows (or legacy
   plan_document). Child chunks carry chunk_id (content hash of doc,
   index, text), char_start/char_end (document-relative exact offsets),
   heading_path (JSONB), tier=child.
2. **GLiNER input**: extract_worker._entity_spans receives
   `row["text"]` (focal chunk text only) and calls
   `gliner.entity_pass(chunk_text, labels, threshold=0.5)`. The model
   NEVER sees beyond the focal chunk today.
3. **Offset mapping**: GLiNER returns chunk-relative offsets; they are
   stored directly as EntitySpan.start/end (chunk-relative), used
   verbatim by candidates/evidence. Document coordinates are
   chunk.char_start + span.start.
4. **heading_path**: stored on chunk rows (semantic_v2 only); legacy
   rows NULL. Never used during inference today.
5. **Sibling identification**: chunks have chunk_index + doc_id +
   parent_id. Previous/next child = same doc, tier=child, adjacent
   chunk_index ordered by char_start. semantic_v2 children within one
   structural region are contiguous; across regions, char_start gaps
   exist (headings excluded from child text).
6. **Hard-boundary metadata**: semantic_v2 heading_path identifies the
   section; siblings sharing the same heading_path tail are same-
   section. heading_path difference = hard section boundary.
7. **Extraction contract hash**: stage_contract_hash includes
   query_policy identity (which includes active_policy_version +
   aliases), syntax contract, rescue policy, rule pack, admission
   policy, GLiNER pin. Context policy version will be added.
8. **Observability**: discovery events recorded per chunk with detail
   (proposals count); rescue events carry query text + labels.

## Contract

Authorized 2026-08-16 after GLINER-TYPE-ARBITRATION-V1 NOT QUALIFIED
(the production failure is context-dependent scoring, not merge
logic). ONE question: does a deterministic bounded context envelope
around a focal semantic_v2 chunk improve GLiNER semantic interpretation
while preserving the focal chunk as the authoritative storage/
provenance unit? STORAGE UNIT != MODEL CONTEXT WINDOW.

## Changes

- shared/polymath_shared/extraction_context.py — extraction-context-v1
  contract: envelope construction (pure deterministic function of focal
  chunk + document structure + sibling ordering + policy), hard-
  boundary enforcement, offset ownership classification (focal/
  outside/crossing), context policy version.
- extract_worker._entity_spans: receives the envelope; maps envelope-
  relative GLiNER predictions to source coordinates; classifies
  ownership; only focal-owned predictions become EntitySpans.
- Observability: CONTEXT_PREDICTION_FOCAL / CONTEXT_PREDICTION_OUTSIDE_FOCAL /
  CONTEXT_PREDICTION_CROSSES_FOCAL_BOUNDARY / CONTEXT_UNAVAILABLE_HARD_BOUNDARY.
- No changes to: chunk identity, offsets, retrieval, rescue, admission,
  candidates, compiler, predicates, query vocabulary, threshold, model.

## Proof

- Dev matrix C0 (focal-only) vs C1 (heading+focal) vs C2 (previous+
  focal) vs C3 (heading+previous+focal) on dev sentences.
- QUALITY-PROBE before/after with FULL trace (key sentence + 8 surfaces
  + anaphor/generic-endpoint FPs).
- Frozen I4: semantic_v2 focal-only vs semantic_v2 + selected context.
- Determinism: envelope construction + ownership filtering byte-identical.
- Unexplained outcomes = 0.

## Rejected claims

- No coreference: "the company" is NOT resolved to "Brightpath
  Learning"; context only improves upstream span/type evidence.
- No automatic semantic_v2 promotion even if context qualifies.

## Open contract gaps

- I5, predicate signatures, CP2.1: not started.
