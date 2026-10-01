# unit: shared/polymath_shared/materializer.py
anchor: shared/polymath_shared/materializer.py:1-675

## purpose
I0 deterministic native document materialization (ADR 0010): turns native source files (PDF / EPUB / DOCX / TXT / Markdown / HTML) into a deterministic normalized-text representation plus a structural source map for the existing frozen ingestion/extraction pipeline — shared/polymath_shared/materializer.py:1-22 [DERIVED]. Sole known consumer: `workers/workers/intake_worker.py` (FACTS.importers). Owns materialization only; never touches entities, facts, compiler, GLiNER, ontology, thresholds — shared/polymath_shared/materializer.py:20-22 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `materialize` | function | `(original_bytes: bytes, media_type: str, source_name: str = "") -> Materialization` | shared/polymath_shared/materializer.py:143-189 | workers/workers/intake_worker.py (module-level importer) |
| `detect_format` | function | `(media_type: str, source_name: str) -> Optional[str]` | shared/polymath_shared/materializer.py:133-140 | — |
| `Materialization` | dataclass | fields text/source_map/parser/parser_version/format/media_type/original_sha256/normalized_text_sha256/original_byte_length/warnings; `to_record() -> dict` | shared/polymath_shared/materializer.py:98-122 | workers/workers/intake_worker.py |
| `MaterializationError` + `UnsupportedFormatError`, `EncryptedDocumentError`, `CorruptedDocumentError`, `EmptyExtractionError`, `LowYieldError` | exceptions | subclasses of `RuntimeError` | shared/polymath_shared/materializer.py:73-94 | — |
| `MATERIALIZER_NAME`, `MATERIALIZER_VERSION` | constants | `"polymath-materializer"`, `"1.1.0"` | shared/polymath_shared/materializer.py:35-36 | — |

## contracts

### materialize — shared/polymath_shared/materializer.py:143-189
- in: `original_bytes: bytes`, `media_type: str`, `source_name: str = ""` — :143
- pre: `detect_format(media_type, source_name)` must resolve a format, else `UnsupportedFormatError` — :145-149
- out: `Materialization` with `original_sha256 = hashlib.sha256(original_bytes).hexdigest()` — :150, :185 and `normalized_text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()` — :186
- post: `text.strip()` non-empty else `EmptyExtractionError` — :170-171
- post: for `fmt in ("pdf", "epub", "docx")`: `len(text) >= 20` and `len(text) / max(len(original_bytes), 1) >= 0.001` else `LowYieldError` — :172-178
- dispatch: text/markdown -> `_materialize_text` (parser `f"{fmt}-codec"`), html -> `_materialize_html` (`"stdlib-html"`), pdf -> `_materialize_pdf` (`"pypdf"`), epub -> `_materialize_epub` (`"stdlib-zip-epub"`), docx -> `_materialize_docx` (`"stdlib-zip-docx"`) — :152-168 (see dumb-code flags: parser local never used)

### detect_format — shared/polymath_shared/materializer.py:133-140
- in: `media_type: str`, `source_name: str`
- out: `TEXT_MEDIA_TYPES` hit wins; else longest-suffix match from `EXTENSION_FALLBACK` against lowercased name (sorted by `-len(kv[0])`); else `None` — :134-140

### Materialization.to_record — shared/polymath_shared/materializer.py:110-122
- out: dict with exactly the keys `text, source_map, parser, parser_version, format, media_type, original_sha256, normalized_text_sha256, original_byte_length, warnings` — :111-122

### _TextExtractor — shared/polymath_shared/materializer.py:225-440
- in: HTML via `feed()`; entities unescaped via `convert_charrefs=True` — :252
- out: blocks joined `"\n\n"`; list = one block of `- item` / `n. item` lines, nested indent `"  " * depth` — :344-352, :440; table row = `"| " + " | ".join(cells) + " |"` — :410; `<pre>` = fenced block with ```` ``` ```` at :288 and :291

## effect surface
- Postgres: none (FACTS `tables_read: []`, `tables_written: []`)
- Qdrant / network / subprocess / env flags: none in SOURCE
- Files: none; all parsing is in-memory over bytes (`io.BytesIO` at :506, zip over BytesIO at :543-544, :626-627)
- Lazy imports: `pypdf.PdfReader` — shared/polymath_shared/materializer.py:502 (pinned dependency, error at :504); `polymath_shared.identity.normalize_document_bytes` — shared/polymath_shared/materializer.py:128
- Consumer: workers/workers/intake_worker.py (FACTS.importers)

## invariants
INVARIANT: `Materialization.parser_version` default == `MATERIALIZER_VERSION` == `"1.1.0"` — shared/polymath_shared/materializer.py:36,102 [DERIVED]
  fails-if: records from different extractor generations become indistinguishable.
INVARIANT: for pdf/epub/docx, `len(text) >= MIN_BINARY_CHARS` (`20`) — shared/polymath_shared/materializer.py:62,172-175 [DERIVED]
  fails-if: image-only PDF with stray glyphs ingests as a text document.
INVARIANT: for pdf/epub/docx, `len(text)/max(len(original_bytes),1) >= MIN_TEXT_YIELD` (`0.001`) — shared/polymath_shared/materializer.py:61,173-178 [DERIVED]
  fails-if: near-empty extraction silently enters the pipeline.
INVARIANT: source_map cursor advance `len(segment) + 2` equals the `"\n\n"` join separator — shared/polymath_shared/materializer.py:529-530 (pdf), :592-595 (epub) [DERIVED]
  fails-if: char ranges drift; evidence spans point at wrong native locations.
INVARIANT: media_type match precedes extension fallback — shared/polymath_shared/materializer.py:134-139 [DERIVED]
  fails-if: a file named `.html` served as `text/plain` is parsed as plain text.
INVARIANT: nested list indent = `"  " * depth` (two spaces per level) — shared/polymath_shared/materializer.py:344-352 [DERIVED]
  fails-if: chunker hard-line markers (`"- "`, `"1. "`) stop being recognized (contract at :236-238).
INVARIANT: identical input yields byte-identical text, source map, and hashes — shared/polymath_shared/materializer.py:8-9 [DERIVED]
  fails-if: re-ingestion of the same file forks/duplicates children.

## determinism & idempotency
determinism: DETERMINISTIC (pure function of (bytes, media_type) — shared/polymath_shared/materializer.py:8-9; no clock/random/uuid/network/db/env usage in SOURCE :25-33)
idempotency: SAFE (no writes; FACTS tables_read/tables_written empty)

## failure behaviour
All four broad handlers from FACTS.fallbacks convert, never swallow — the caller sees a typed `MaterializationError` subclass:

| site | trigger | caller sees |
|---|---|---|
| shared/polymath_shared/materializer.py:446-447 | html decode `except Exception` | `CorruptedDocumentError("html bytes are not decodable")` (unreachable in practice, see flags) |
| shared/polymath_shared/materializer.py:452-453 | html parse failure | `CorruptedDocumentError(f"html parse failed: {exc}")` |
| shared/polymath_shared/materializer.py:507-508 | pdf open failure | `CorruptedDocumentError(f"pdf open failed: {exc}")` |
| shared/polymath_shared/materializer.py:517-518 | pdf page extraction failure | `CorruptedDocumentError(f"pdf page {page_index} extraction failed: {exc}")` |

Other typed raises: `UnsupportedFormatError` :147-149, :168; `EmptyExtractionError` :170-171; `LowYieldError` :175-178; `EncryptedDocumentError("pdf is encrypted and cannot be materialized")` :509-510; `MaterializationError("pypdf is not installed (pinned dependency)")` :503-504; `CorruptedDocumentError` for non-UTF-8 text :200-201, epub container/spine/zip :547-548, :553-554, :577-578, :593-594, docx structure :627-628, :630-631, :634-635.

## dumb-code flags
- Dead local `parser`: assigned `f"{fmt}-codec"` / `"stdlib-html"` / `"pypdf"` / `"stdlib-zip-epub"` / `"stdlib-zip-docx"` at :154,157,160,163,166 but never passed to `Materialization(...)` at :180-189; every record reports the default `parser = "polymath-materializer"` (:101) — per-format parser identity is lost — shared/polymath_shared/materializer.py:154-166,180-189 [DERIVED assignment absent from constructor; INFERRED effect on records]
- Unreachable handler: `raw.decode("utf-8", errors="replace")` (:445) does not raise on bad bytes, so the `except` at :446-447 is dead in practice — shared/polymath_shared/materializer.py:445-447 [INFERRED: errors="replace" substitutes instead of raising]
- `_BLOCK_TAGS` (:64-68) has no reference anywhere in this file after the HTML-STRUCTURE-V1 rework — shared/polymath_shared/materializer.py:64-68 [INFERRED: no call/read site in SOURCE]
- `_collapse_blocks` (:469-493) has no call site in this unit — shared/polymath_shared/materializer.py:469-493 [INFERRED]
- `import html as html_lib` (:26) occurs exactly once (the import); unused — shared/polymath_shared/materializer.py:26 [INFERRED]
- Doc drift: `_SKIP_TAGS` includes `"nav"` (:69) but the extractor docstring drop-list at :248 omits it — shared/polymath_shared/materializer.py:69,248 [DERIVED]
- Literal `"\n\n"` duplicated across five builders: :210, :455-456, :477, :530, :595, :658 — shared/polymath_shared/materializer.py [DERIVED]
- DOCX heading gate is `style.lower().startswith("heading")` (:646); style ids not starting with `"heading"` silently become plain paragraphs — shared/polymath_shared/materializer.py:646 [DERIVED]

## refactor notes
- `workers/workers/intake_worker.py` is the only known importer (FACTS.importers); signature or `to_record` key changes to `materialize`/`Materialization` propagate there — shared/polymath_shared/materializer.py:110-122,143
- TXT/MD path must keep delegating to `polymath_shared.identity.normalize_document_bytes` (BOM strip + CRLF normalize + NFC) to stay byte-stable with the pre-I0 Q1-qualified behavior — shared/polymath_shared/materializer.py:17-18,125-130
- `_TextExtractor` output shapes are coupled to the chunker's blank-line split and hard-line markers (`"- "`, `"1. "`, `"#"`, `"|"`, `">"`, 4-space code) — shared/polymath_shared/materializer.py:236-238; changing block shapes moves chunk boundaries
- `source_map` key contract (`text_start/text_end/kind/location/label`) feeds the frozen ingestion/extraction pipeline — shared/polymath_shared/materializer.py:4-5,10-13
- Fixing the dead `parser` local changes the `parser` key in every emitted record for downstream consumers — shared/polymath_shared/materializer.py:110-122,154-166,180-189
- Bumping `MATERIALIZER_VERSION` (`"1.1.0"`) re-tags `parser_version` on every record — shared/polymath_shared/materializer.py:36,102

## VERIFY
```verify
grep -Fq 'MATERIALIZER_VERSION = "1.1.0"' shared/polymath_shared/materializer.py
grep -Fq 'MIN_TEXT_YIELD = 0.001' shared/polymath_shared/materializer.py
grep -Fq 'MIN_BINARY_CHARS = 20' shared/polymath_shared/materializer.py
grep -Fq 'def materialize(original_bytes: bytes, media_type: str, source_name: str = "") -> Materialization:' shared/polymath_shared/materializer.py
! grep -Fq 'parser=parser' shared/polymath_shared/materializer.py
test "$(grep -c -F 'raise CorruptedDocumentError(' shared/polymath_shared/materializer.py)" -ge 10
test "$(grep -c -F 'html_lib' shared/polymath_shared/materializer.py)" -eq 1
```
