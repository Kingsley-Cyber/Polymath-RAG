---
change_id: i0-native-document-materialization
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: new materialization layer (ADR 0010)
---

# I0: native document materialization

## Contract

Convert supported native source files (PDF / EPUB / DOCX / TXT /
Markdown / HTML) into a deterministic normalized-text representation
plus a structural source-location map, then feed that representation
into the EXISTING frozen ingestion/extraction pipeline. Semantic
extraction is untouched (Q1 frozen). Fail loudly on
encrypted/unreadable documents, empty extraction, unsupported
formats, corrupted archives, and suspiciously low text yield.

Acceptance (all required):
- PDF extracts non-empty deterministic text;
- EPUB extracts chapters in deterministic (spine) order;
- DOCX preserves paragraph/heading order;
- TXT/MD remain byte/text stable;
- HTML removes presentation noise deterministically;
- repeated parsing gives identical normalized-text hash;
- source-map entries resolve back to the original source location;
- malformed/native extraction failures are explicit;
- original source bytes/hash remain traceable;
- parsed output enters the existing frozen pipeline unchanged;
- one psychology-book sample and one technical-book sample complete
  the full pipeline (materialize → intake → extraction →
  canonicalization → Neo4j projection → evidence/source lineage).

## Owner and public contract

- Owner: shared owns the deterministic materializer policy; the
  intake worker owns the stage change.
- Public contract: `contracts/ingestion/v1/materialization.schema.json`
  (new). Reverse dependents: R3a source spans consume the source map
  indirectly (no semantic change).

## Design decisions (admitted, ADR 0010)

- Deterministic pure function of bytes → identical output/hashes.
- One new dependency: `pypdf` (pure Python, page-order extraction).
  Footprint-ladder step documented here: PyMuPDF rejected (heavy,
  AGPL), pdfminer.six rejected (complex, slower, no stable page
  ordering guarantee), bs4/lxml/html2text rejected (stdlib
  html.parser suffices for deterministic tag stripping).
- Per-format parsers: TXT/MD = existing byte normalization
  (byte-stable); HTML = stdlib html.parser with block boundaries;
  PDF = pypdf page order; EPUB = stdlib zipfile + OPF spine +
  per-chapter HTML extraction; DOCX = stdlib zipfile +
  word/document.xml paragraphs/headings.
- Source map segments: `{text_start, text_end, kind, location,
  label}` — page for PDF, chapter for EPUB, section/paragraph for
  DOCX, block for HTML, whole-document for TXT/MD.
- Failure modes (typed, loud): UnsupportedFormatError,
  EncryptedDocumentError, CorruptedDocumentError,
  EmptyExtractionError, LowYieldError → StageFailed in intake.
- Persistence: migration 0006 adds documents.source_hash,
  documents.materialization, documents.source_map.

## Inputs, outputs, persistence, failure modes

- Inputs: original bytes + media type + source name.
- Outputs: normalized text + source map + parser identity + hashes.
- Persistence: documents row extensions (migration 0006); chunks
  unchanged.
- Failure modes: typed errors above → stage failure receipt (never a
  silent empty document).

## Dependency edges

- shared → pypdf (new, documented); intake worker → shared
  (existing). No dependency map change.
- New files: materializer.py, contract schema, migration 0006, book
  fixtures, three test files, ADR 0010, work log, refactor.
- Reverse dependents: none beyond intake.

## Verifier and rollback boundary

- Verifier: per-format unit tests, contract schema test, full-pipeline
  book-sample E2E (real GLiNER), `make guards`, full suites.
- Rollback boundary: revert the intake-worker change and drop the
  materializer/tests; migration stays (append-only) with columns
  unused.

## Changes

- `shared/polymath_shared/materializer.py` (new): deterministic
  per-format materialization (TXT/MD/HTML/PDF/EPUB/DOCX) with source
  maps + typed loud failures.
- `workers/workers/intake_worker.py`: materialize inside the stage
  transaction; persist source_hash/materialization/source_map;
  materialization failures commit a FAILURE receipt.
- `workers/workers/extract_worker.py`: consume the authoritative
  Postgres chunks (committed by intake) instead of re-deriving text
  from event bytes — required so native formats and TXT share one
  chunk lineage (I0 defect discovered by the E2E run).
- `stores/postgres/migrations/0006_materialization.sql` (new):
  documents.source_hash / materialization / source_map.
- `contracts/ingestion/v1/materialization.schema.json` (new).
- `shared/pyproject.toml`: + `pypdf` (only new dependency; footprint
  step documented in ADR 0010).
- Fixtures `eval/fixtures/native_docs/` (12 files): public-domain
  psychology (William James) + technical (Darwin) excerpts in all six
  formats.
- Tests: `tests/determinism/test_materializer.py` (14),
  `tests/contracts/test_materialization_contract.py` (4),
  `tests/integration/test_i0_native_docs_e2e.py` (1, live).
- Governance: ADR 0010, refactor 0007, architecture changelog, TREE
  registration, RAG_E2E_CHECKLIST I0 → COMPLETE, state docs.

Dependency edges: shared → pypdf (new); intake/extract workers →
shared (existing). No dependency map change. Semantic extraction
(compiler/rules/ontology/GLiNER/thresholds) untouched.

## Proof

- Unit/contract: 18 new tests green (152 unit total, 22 skipped).
- Integration: 19 passed, 2 skipped — includes the live
  full-pipeline run of BOTH book samples (psychology + technical)
  across PDF/EPUB/DOCX/HTML/MD/TXT with real GLiNER: facts extracted
  with evidence + full provenance, canonicalization converged,
  Neo4j projection intact, and the lineage
  fact → evidence → chunk offsets → source-map segment → page/chapter
  asserted for every sampled fact.
- `make guards` green (preflight, repo guard, wiki worm).
- Contract schema validated by jsonschema in tests.

## Rejected claims

- No extraction change (compiler/rules/ontology/GLiNER/thresholds).
- No silent empty ingestion.
- No semantic R3a/R3b change.

## Open contract gaps

- OCR/scan-PDF handling is out of scope (typed failure, not silent
  degradation).
