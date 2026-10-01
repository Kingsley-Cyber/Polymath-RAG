# unit: shared/polymath_shared/source_region.py
anchor: shared/polymath_shared/source_region.py:1-176

## purpose
Deterministic source-region classifier (REGION-POLICY-V1): labels a text span as one of `BODY_PROSE`, `BIBLIOGRAPHY`, `INDEX`, `TABLE_OF_CONTENTS`, `CAPTION`, `HEADING`, `CODE_OR_CONFIG` using only shape signals (line geometry, punctuation regularity, numeric density) — no model, no corpus-specific phrase lists — shared/polymath_shared/source_region.py:1-14 [DERIVED]. It exists so downstream assertion/extraction can treat body prose as asserting and index/reference/caption furniture as non-asserting while keeping it retrieval-reachable — shared/polymath_shared/source_region.py:3-6 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `classify_chunk` | function (lru_cached) | `(text: str) -> str` | shared/polymath_shared/source_region.py:94-136 | — |
| `region_at` | function | `(chunk_text: str, span_start: int, span_end: int, layout_spans: Optional[list[tuple[str, int, int]]] = None, chunk_char_start: int = 0) -> str` | shared/polymath_shared/source_region.py:145-175 | — |
| `REGION_POLICY_VERSION` | constant | `= "region-policy-v1"` | shared/polymath_shared/source_region.py:25 | — |
| `BODY_PROSE` | constant | `= "BODY_PROSE"` | shared/polymath_shared/source_region.py:27 | — |
| `BIBLIOGRAPHY` | constant | `= "BIBLIOGRAPHY"` | shared/polymath_shared/source_region.py:28 | — |
| `INDEX` | constant | `= "INDEX"` | shared/polymath_shared/source_region.py:29 | — |
| `TABLE_OF_CONTENTS` | constant | `= "TABLE_OF_CONTENTS"` | shared/polymath_shared/source_region.py:30 | — |
| `CAPTION` | constant | `= "CAPTION"` | shared/polymath_shared/source_region.py:31 | — |
| `HEADING` | constant | `= "HEADING"` | shared/polymath_shared/source_region.py:32 | — |
| `CODE_OR_CONFIG` | constant | `= "CODE_OR_CONFIG"` | shared/polymath_shared/source_region.py:33 | — |

## contracts

`classify_chunk(text)`
- in: `text: str`, immutable chunk text — shared/polymath_shared/source_region.py:95 [DERIVED]
- pre: none; empty/whitespace text allowed — shared/polymath_shared/source_region.py:97 [DERIVED]
- out: one of the seven region constants — shared/polymath_shared/source_region.py:110-135 [DERIVED]
- post: computed once per distinct text, cached via `functools.lru_cache(maxsize=4096)` — shared/polymath_shared/source_region.py:94 [DERIVED]

`region_at(chunk_text, span_start, span_end, layout_spans, chunk_char_start)`
- in: span offsets relative to `chunk_text`; `layout_spans` entries `(kind, lo, hi)` in absolute document coordinates, converted via `chunk_char_start + span_start` / `chunk_char_start + span_end` — shared/polymath_shared/source_region.py:156-158 [DERIVED]
- pre: span must be fully contained in a layout span (`lo <= abs_s and abs_e <= hi`) for layout to apply — shared/polymath_shared/source_region.py:159 [DERIVED]
- out: a region constant
- post: authority order is (1) layout evidence (`heading` -> `HEADING`; `caption`/`figure` -> `CAPTION`), (2) whole-chunk `classify_chunk` if not `BODY_PROSE`, (3) span's own line (`_CAPTION_LINE` -> `CAPTION`, `_INDEX_LINE` -> `INDEX`), else `BODY_PROSE` — shared/polymath_shared/source_region.py:148-175 [DERIVED]

## effect surface
No Postgres tables (`tables_read: []`, `tables_written: []` per FACTS), no Qdrant, no files, no network, no subprocess, no env flags; only imports are `functools`, `re`, `typing` — shared/polymath_shared/source_region.py:21-23 [DERIVED].

## invariants
INVARIANT: `_YEAR_CITE` count >= 4 OR `_AUTHOR_INITIAL` count >= 5 OR `_CITATION_FURNITURE` count >= 3 ⇒ `BIBLIOGRAPHY` — shared/polymath_shared/source_region.py:103-110 [DERIVED]
  fails-if: reference list below all three floors falls through to index/TOC tests and can be labelled `INDEX` or `BODY_PROSE`.
INVARIANT: page-ref `INDEX` requires `_PAGE_REF` count >= 4 AND `_page_ref_density(text) >= 6.0` AND word count >= 15 — shared/polymath_shared/source_region.py:117-119 [DERIVED]
  fails-if: prose citing four figures below 6.0/100-words density gets misclassified as `INDEX`.
INVARIANT: line-shape ratio tests run only when `len(non_empty) >= 4` — shared/polymath_shared/source_region.py:124 [DERIVED]
  fails-if: a 1–3 line index/TOC chunk skips `_INDEX_LINE`/`_TOC_LINE`/`_CODE_LINE` ratios entirely.
INVARIANT: ratio floors are `_INDEX_LINE` >= 0.4, `_TOC_LINE` >= 0.4 OR `_CHAPTER_LINE` >= 0.5, `_CODE_LINE` >= 0.5 — shared/polymath_shared/source_region.py:125-131 [DERIVED]
  fails-if: mixed chunks below floor default to `BODY_PROSE` and their entries become asserting text downstream.
INVARIANT: `HEADING` requires `len(non_empty) == 1` AND `len(non_empty[0]) <= 80` AND line does not end with `"."` — shared/polymath_shared/source_region.py:134 [DERIVED]
  fails-if: any short single line without a trailing period (e.g. a question ending `"?"`) is labelled `HEADING`.
INVARIANT: layout span applies only when `lo <= abs_s and abs_e <= hi` (full containment) — shared/polymath_shared/source_region.py:159 [DERIVED]
  fails-if: partial overlap falls through to chunk/line classification.
INVARIANT: `classify_chunk` cache capacity = 4096 distinct texts — shared/polymath_shared/source_region.py:94 [DERIVED]
  fails-if: beyond 4096 live chunk texts, entries evict and regex work recomputes (correctness unaffected, cost returns).

## determinism & idempotency
determinism: DETERMINISTIC — pure regex/counting over input text; no clock/random/uuid/network/db/env inputs; imports limited to `functools`/`re`/`typing` — shared/polymath_shared/source_region.py:21-23 [DERIVED]
idempotency: SAFE — pure functions; only side effect is the `lru_cache` on `classify_chunk` — shared/polymath_shared/source_region.py:94 [DERIVED]

## failure behaviour
No `raise`/`try` anywhere in the unit; degradation is by default, not error — shared/polymath_shared/source_region.py:1-176 [DERIVED].
- Empty/whitespace text → returns `BODY_PROSE` instead of failing — shared/polymath_shared/source_region.py:97-98 [DERIVED]
- `_ratio` on zero non-blank items → `0.0` (ratio tests then don't fire) — shared/polymath_shared/source_region.py:89-90 [DERIVED]
- `_page_ref_density` floors word count at `max(len(text.split()), 1)` to avoid division by zero — shared/polymath_shared/source_region.py:79 [DERIVED]

## dumb-code flags
- Magic thresholds with no named constants: `4`, `5`, `3`, `6.0`, `15`, `0.4`, `0.5`, `80`, `4096` — shared/polymath_shared/source_region.py:103-134, 94 [DERIVED]
- `REGION_POLICY_VERSION = "region-policy-v1"` (line 25) is defined but never referenced elsewhere in this file, and the docstring spells it uppercase `REGION-POLICY-V1` (line 1) — value and docstring disagree on case — shared/polymath_shared/source_region.py:1, 25 [DERIVED]
- `_INDEX_LINE` is applied two ways: as a >= 0.4 line-ratio inside `classify_chunk` (line 126) but as a single-line match with no ratio/line-count guard in `region_at` (lines 173-174) — asymmetric strictness — shared/polymath_shared/source_region.py:126, 173-174 [DERIVED]
- `_CODE_LINE` deliberately excludes plain `"- "` bullets (comment at lines 53-54); the regex only matches bullets that also look like `key: value` — shared/polymath_shared/source_region.py:54-55 [DERIVED]
- `HEADING` trailing-punctuation check tests only `"."`, so a one-line question ending `"?"` still reads as a heading — shared/polymath_shared/source_region.py:134 [INFERRED: `endswith(".")` is the sole punctuation filter]

## refactor notes
- The seven region label strings (lines 27-33) are the public comparison vocabulary; renaming any requires updating every downstream consumer of `classify_chunk`/`region_at` results.
- Layout kind literals `"heading"`, `"caption"`, `"figure"` (lines 161-163) must stay in sync with the LAYOUT-EVIDENCE-V1 `document_layout` producer; other kinds are silently ignored here.
- Authority order in `region_at` (layout > chunk > line) is a published contract in its docstring (lines 148-153); reordering changes which evidence wins on overlap.
- `region_at` offset arithmetic assumes `layout_spans` are absolute while span offsets are chunk-relative plus `chunk_char_start`; callers passing inconsistent coordinates break containment silently.
- Test ordering inside `classify_chunk` (bibliography → page-ref index → table cells → line ratios → heading) is precedence-sensitive; swapping checks changes labels on mixed chunks — shared/polymath_shared/source_region.py:102-135 [DERIVED]

## VERIFY
```verify
grep -Fq 'REGION_POLICY_VERSION = "region-policy-v1"' shared/polymath_shared/source_region.py
grep -Fq '@functools.lru_cache(maxsize=4096)' shared/polymath_shared/source_region.py
grep -Fq 'if kind == "heading":' shared/polymath_shared/source_region.py
grep -Eq 'def (classify_chunk|region_at)\(' shared/polymath_shared/source_region.py
test "$(grep -c -F 'return CODE_OR_CONFIG' shared/polymath_shared/source_region.py)" -ge 2
! grep -Fq 'import random' shared/polymath_shared/source_region.py
```
