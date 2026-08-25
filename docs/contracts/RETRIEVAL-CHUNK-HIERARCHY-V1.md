# RETRIEVAL-CHUNK-HIERARCHY-V1

Status: **ACTUAL BEHAVIOR** (audited from production code 2026-08-25,
HEAD `9331f9a`). This document describes what the pipeline DOES, not
aspirations. Any change to a frozen field below is a new contract
version.

Owners: `workers/workers/intake_worker.py` (intake stage),
`workers/workers/chunker.py` (legacy_v1 chunker),
`workers/workers/summarizer.py` (deterministic extractive summaries).

## Pipeline position

```
intake.v1 → normalize → materialize (per-format, typed failures)
          → route_document(profile) → chunk (provider-selected)
          → chunks rows + document_layout + retrieval_summaries seeds
```

Production provider: **legacy_v1** (`POLYMATH_CHUNKER=legacy_v1`,
boot-script default). `semantic_v2`
(`workers/workers/semantic_chunker.py`) exists behind the same setting;
its activation is a deliberate cutover, not a default.

## Normalization (before any byte is seen by the chunker)

strip BOM · CRLF→LF · NFC. Applied identically to txt/markdown and to
materializer output for binary formats. `doc_id = document_id(normalized)`
— content-addressed, globally unique; re-ingesting changed bytes yields
a new doc_id by construction.

## Materialization (ADR-0010)

| format | parser | notes |
|---|---|---|
| md / txt | codec | same normalization path as pre-I0 |
| pdf | pypdf | |
| epub / docx | stdlib zip | typed CorruptedDocumentError on bad zips (measured live: corrupt epubs fail intake with failure receipts, never silent empty docs) |
| html | stdlib-html | |

Durable record: `documents.materialization` JSON (parser,
parser_version, normalized_text_sha256, original_byte_length, warnings)
+ `documents.source_map`; layout evidence in `document_layout`
(doc_id, kind, char_start, char_end) — the ONLY place heading status is
DETECTED.

## Sentences

`summarizer.split_sentences`: regex split on `_SENTENCE_RE`, stripped,
empties dropped. Never splits mid-sentence. Offsets recovered by
sequential `text.find(sentence, cursor)` — deterministic given text.

## CHILD chunks (tier='child')

- **Segmentation**: greedy sentence packing. A sentence joins the open
  buffer iff `buf_len + 1 + len(sentence) <= child_target_chars`.
  Frozen param: `child_target_chars = 1200`.
- **Oversized sentence** (> target alone): becomes its own single-
  sentence chunk; it is never split.
- **No overlap** between children. None configured, none emitted.
- **Headings**: heading regions from `layout_evidence.heading_regions`
  are projected into each chunk's `layout_map` as chunk-relative
  [start,end) pairs. Headings are NOT excluded from legacy_v1 body
  text (they are part of the packed sentences); only semantic_v2
  excludes them from body. `layout_map=[]` means "detected, none
  here"; NULL means "never detected".
- **Tables/transcripts**: no special-casing in legacy_v1 — they pack as
  sentences like any prose.
- **Offsets**: char_start/char_end = document-level offsets of the
  spanned sentences (start of first, end of last).
- **Summary**: extractive, ≤2 sentences / 420 chars, original order.
- **Identity**: `chunk_id = chunk_id(doc_id, i, spec.text)` —
  content-addressed; identical text ⇒ identical ids.

## PARENT chunks (tier='parent')

- **Grouping**: FIXED fanout over consecutive children — frozen param
  `parent_fanout = 4`. NOT section-aware; headings do not reset groups.
- **Parent TEXT is a SUMMARY**, not verbatim concatenation:
  `summarize_children(child_texts)` = summarize( join(
  summarize(child, 1 sentence/220) ), ≤3 sentences / 600 chars ) — a
  two-level centroid, stable under child reorder.
- **Span**: char_start..char_end covers first..last grouped child.
- **Ordering/indexing**: children occupy chunk_index 0..n−1 in document
  order; parents are appended at n..n+m−1 in group order. Children's
  parent_id set to their group's parent chunk_id.
- **Reconstruction invariant** (long-procedure sequence regression):
  `" ".join(children ordered by chunk_index within a parent)` reproduces
  source order because packing never reorders sentences and offsets are
  monotonic. Retrieval MUST NOT reorder procedural evidence across
  parents.

## DOCUMENT summary

Extractive ≤6 sentences / 1600 chars (deterministic TF scoring,
original order, word-boundary truncation).

## Corpus map

Produced downstream by the summaries worker into
`retrieval_summaries` (kind=`document_retrieval_summary` /
`section_retrieval_summary`) and projected to Qdrant routing lanes —
see RETRIEVAL-STORAGE-CONTRACT-V1. Not part of the chunker itself.

## Semantic roles (do not collapse)

| role | producer | consumer meaning |
|---|---|---|
| CHILD | chunker (verbatim sentences) | evidence / proof |
| PARENT | chunker (centroid summary of ≤4 children) | local context |
| PARENT SUMMARY row | summaries worker | local semantic navigation |
| DOCUMENT SUMMARY row | summaries worker | document intelligence |
| CORPUS MAP | summaries worker | corpus-level navigation |

Known tension, documented deliberately: tier='parent' CHUNK text is
already a summary, while retrieval_summaries ALSO carries section
summaries. Consumers must treat them as distinct artifacts with
distinct ids; they are not interchangeable.

## Regression obligations

Any change here must keep green:
- the existing long-procedure sequence regression (child order);
- tests pinning CHUNK_FROZEN_PARAMS via the intake contract hash;
- projection/reconstruction gates that assume chunk_id stability.
