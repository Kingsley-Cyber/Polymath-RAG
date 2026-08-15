---
owner: worker
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: accepted
---

# ADR 0010: Native document materialization (gate I0)

## Context

Q1 qualified the semantic extraction layer (frozen GLiNER/compiler,
P/R ≈ 0.943) on text. But the intake worker only decodes UTF-8 bytes;
a binary PDF/EPUB/DOCX book silently becomes an empty document. Real
corpus books are native files, not plain text. Semantic extraction is
qualified and locked; native-document parsing is a SEPARATE concern
and must be qualified separately.

## Decision

Introduce a deterministic materialization layer (I0) between intake
and extraction:

```text
native file (PDF/EPUB/DOCX/TXT/MD/HTML)
    -> materializer (deterministic, per-format parser)
    -> normalized text + structural source map
    -> EXISTING frozen intake/extraction pipeline (unchanged)
```

- `shared/polymath_shared/materializer.py` owns the pure, deterministic
  policy: given original bytes + media type, produce
  `{text, source_map, parser, parser_version, original_sha256,
  normalized_text_sha256}`. Source-map segments map normalized
  character ranges to native locations (page for PDF, chapter for
  EPUB, heading/paragraph context for DOCX, block for HTML).
- Format parsers: TXT/MD via the existing byte normalization (byte-
  stable — Q1 corpus behavior unchanged); HTML via stdlib
  `html.parser` (scripts/styles removed, block boundaries kept);
  PDF via `pypdf` (page-order extraction); EPUB via stdlib zipfile +
  OPF spine (chapter order, per-chapter HTML extraction); DOCX via
  stdlib zipfile + `word/document.xml` (paragraph/heading order).
  ONE new dependency (`pypdf`) — the footprint-ladder step is
  documented in the I0 work log (alternatives rejected: PyMuPDF/
  pdfminer/bs4/lxml — heavier or non-deterministic ordering).
- Fail loudly: unsupported format, encrypted or corrupted document,
  empty extraction, suspiciously low text yield → typed
  `MaterializationError` → stage failure receipt. An empty document is
  NEVER ingested silently.
- Persistence (migration 0006): `documents.source_hash` (original
  bytes), `documents.materialization` (parser/version/hashes/stats),
  `documents.source_map` (segments). Chunks keep their document-level
  char offsets, so the citation chain becomes
  evidence → chunk offsets → source-map segment → page/chapter.
- Semantic extraction is untouched: no compiler, predicate, GLiNER,
  ontology, or threshold change.

## Consequences

- Intake gains a hard dependency on the materializer; TXT behavior is
  byte-identical to the pre-I0 path (guarded by tests).
- The citation chain gains native-location provenance without changing
  R3a/R3b semantics.
- New formats are a new parser + parser_version, never a change to
  extraction.
