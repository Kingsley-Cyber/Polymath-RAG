---
change_id: semantic-chunking-v2
owner: worker
date: 2026-08-16
status: in-progress
architecture_impact: adds-versioned-chunking-provider-contract
last_reviewed: 2026-08-16
---

# SEMANTIC-CHUNKING-V2: qualify Chonkie SemanticChunker (structure-constrained)

## Contract

SEMANTIC-CHUNKING-V2 qualification gate (directive 2026-08-16):
qualify Chonkie 1.7.0 SemanticChunker as a structure-constrained
replacement chunker IF AND ONLY IF superior; keep legacy_v1 default;
fix the heading bug generally; freeze the qualification set before
comparison; zero hard-boundary violations; exact offsets; 5-run
determinism; STOP before promotion or I5. QUALITY-PROBE-001
(single-document full-stack diagnostic) rode the same configuration.

## §0 Inspection map (pre-implementation, per directive)

1. **Materialization** (shared/materializer.py): per-format extractors
   (MD/TXT keep text verbatim; HTML parser; PDF/EPUB/DOCX) produce
   normalized text + source_map (char ranges → native pages/chapters).
   Normalization = BOM strip + CRLF + NFC only — **newlines are
   preserved** in materialized text. Polymath stays the document
   authority; Chonkie never sees fetchers/persistence.
2. **Chunker** (workers/chunker.py): `plan_document(text, doc_id,
   child_target_chars=1200, parent_fanout=4)` — `split_sentences`
   → greedy sentence packing (`_pack_sentences`, never splits a
   sentence, no overlap, chars-based; NO token counting exists today)
   → parents = deterministic extractive summaries over 4-child
   groups. `materialize_chunks` renders rows; chunk identity =
   content_hash(doc_id, index, text); intake pins CHUNK_FROZEN_PARAMS
   in the intake contract.
3. **Sentence splitter** (workers/summarizer.split_sentences): regex
   `(?<=[.!?])\s+(?=[A-Z0-9"'(\[])|\n+` — splits on punctuation or
   NEWLINES.
4. **THE HEADER BUG mechanism**: materialized text keeps the heading
   newline, so `split_sentences` DOES separate the heading — but
   `_pack_sentences` space-joins sentences into chunk text, destroying
   that boundary; extraction re-splits the JOINED chunk text
   (`_sentences_of` → split_sentences) where no newline survives and
   the unpunctuated heading fuses with the first body sentence
   ("…Operations Review Northvale Health Network uses…"). This is the
   I4 4-FN class and the I4R-A "### Brightpath Learning" NP residue.
5. **Chunk identity**: chunk_id = content hash (doc_id, chunk_index,
   text); char_start/char_end into the source document; re-chunking
   unchanged text is a no-op (frozen test).
6. **Provenance on offsets**: exact-evidence-v1 evidence/subject/object
   offsets are CHUNK-RELATIVE; chunk char_start/end locate the chunk in
   the document; source_map maps document ranges to pages/chapters.
7. **Extraction dependencies**: extract reads chunk text from Postgres
   (authoritative), re-splits sentences, GLiNER over chunk text,
   syntax over sentence slices. Depends on chunk text + sentence
   integrity only — not on chunk boundaries directly.
8. **Summary/profile dependencies**: retrieval_summaries
   (document/section) built by profile_worker from chunk rows;
   retrieval-summary-v2 contract; routing points in Qdrant keyed by
   chunk/summary ids.
9. **Qdrant payloads**: chunk points (child tier) + routing points
   (routing_child / section / document summaries) keyed by entity ids;
   collections per corpus+embedding contract. Semantic_v2 keeps the
   same payload shape with new chunk ids + chunk_contract_version.
10. **Postgres schema**: chunks(chunk_id, doc_id, parent_id,
    chunk_index, tier, text, summary, char_start, char_end). No
    heading_path/contract columns yet → migration 0013 adds
    chunk_contract_version, heading_path, token_count (nullable —
    legacy rows NULL).
11. **Frozen tests assuming current boundaries**:
    tests/determinism/test_chunker_summarizer.py (sentence alignment,
    parent summarization, re-chunk no-op, purity, normalization→one
    id) — all keep passing because legacy_v1 functions are UNTOUCHED.
12. **Embedding sidecar API**: POST /infer {texts (≤32!),
    representation_kind} → {vectors, contract_id, dimension,
    model_release}; /manifest carries the pinned model identity. The
    adapter must batch in ≤32-text groups.

Design decisions from the map: legacy_v1 stays byte-identical
(historical reproducibility); semantic_v2 owns the general heading fix
(headings become structural metadata + heading_path, never chunk-body
text); sentence identity remains Polymath's split_sentences within
semantic chunks (sentence-contract-v1 semantics preserved on heading-
free text); the ChunkingProvider contract carries chunk-contract-v2
with every parameter versioned; CP2 worker contracts gain the chunker
field.

## Changes

- workers/workers/semantic_chunker.py (provider, region splitter,
  adapter+cache, contract identity); settings POLYMATH_CHUNKER;
  intake worker provider wiring + new chunk columns (migration 0013);
  CP2 contracts carry chunker.
- eval/chunking_v2: qualification corpus + dev/sealed boundary gold +
  FROZEN.json + harness (qualify.py); artifacts dev_matrix +
  sealed_score.
- eval/quality_probe_001: REPORT + bundle + harvest.
- CP2 fixes during probe: claim starvation, payload reuse, intake
  binding, uniform env, per-corpus barrier.

## Proof

- Qualification: see report. I4 extraction regression: NOT completed
  (interrupted; separate completion required before any promotion).
- Suite 286 passed / 53 skipped; guards green.

## Verdict: SEMANTIC_V2 QUALIFIED ON CHUNKING CRITERIA; PROMOTION
PENDING the I4 regression + explicit authorization. Default remains
legacy_v1.

## Rejected claims

- No claim that semantic chunking improves extraction quality: the I4
  regression was interrupted and remains unmeasured; chunking
  qualification covers structure/boundary/provenance/determinism only.
- No promotion: legacy_v1 remains the default; semantic_v2 params
  (t0.65/w3) were selected on dev before sealing and never retuned.

## Open contract gaps

- I4 extraction regression (frozen, isolate chunking) still to run.
- Retrieval A/B (legacy vs semantic on frozen questions) not run.
- Auto-restart (V2.1) unresolved: five processes died silently during
  the probe session and required manual restart.
