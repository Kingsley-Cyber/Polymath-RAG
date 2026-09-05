---
title: "WORK LOG — HTML-STRUCTURE-V1 + TIER-CHUNKER-V3.1: HTML lists/tables/pre kept as structure; small heading sections merge to the parent floor; lead-ins travel with their block"
change_id: HTML-STRUCTURE-V1
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.82
package: shared/polymath_shared/materializer.py, workers/workers/tier_chunker.py, eval/fixtures/native_docs/structured.html
architecture_impact: "Materializer 1.0.0 → 1.1.0: the HTML extractor emits Markdown-shaped structure (list blocks of '- item' lines, tables as '| a | b |' rows, <pre> as fenced code, headings as '#' lines, <br> as a line break, <nav> dropped). Chunk contract chunk-structure-v3 → v3.1: consecutive sections whose body is between parent_stub_words and parent_min_words merge forward under their shared ancestry until the floor (sub-stub and heading-only sections still drop as layout evidence); a prose fragment under child_fragment_floor_words joins the next child (lead-in + list/code) else the previous; structured blocks stay atomic. Existing documents are unchanged until re-ingested; new ingests of every format get v3.1 parents/children. Chunk ids for re-ingested documents change (content-addressed)."
---

# WORK LOG — HTML-STRUCTURE-V1 + TIER-CHUNKER-V3.1

Owner (2026-09-05): "I just uploaded handbook.html … it can't index html junk, verify it's actually being extracted" → "fix the html list chunking and reingest handbook.html".

## Contract

- **Materializer (HTML).** `_TextExtractor` builds blocks: `<ul>/<ol>/<dl>` → one block of `- item` / `n. item` lines (nested levels indented two spaces, `<li><p>` is a line break); `<table>` → one block of `| c1 | c2 |` rows; `<pre>` → one fenced block with lines and indentation preserved; `<h1..h6>` → `#…# Title` block; `<br>` → line break inside the block; `<blockquote>` → `> ` lines; `script/style/head/noscript/template/svg/nav` dropped; entities unescaped. Paragraph = blank-line-separated block, exactly what the Markdown path feeds the chunker. `MATERIALIZER_VERSION = "1.1.0"` (recorded per document in `materialization.parser_version`). EPUB chapters share the HTML path and inherit the change.
- **Tier chunker v3.1.** (1) `_merge_small_sections`: a section with `parent_stub_words ≤ body < parent_min_words` absorbs following sections that carry real body while a heading-path prefix is shared and the sum stays ≤ `parent_max_words`; heading_path becomes the shared ancestry; dropped sub-stubs between them remain layout evidence. Sub-stub (< 15 words) and heading-only sections still drop — a title page never leaks into chapter one. (2) `_coalesce_fragments` across region kinds inside a parent: a PROSE fragment (< 25 words) joins the next child when the pair fits `child_max_words`, else the previous; code/table/list children never move; a span that absorbed a lead-in is settled. (3) `_prose_child_spans` leaves a fragment ending with `:` for the cross-region pass instead of gluing it backward. Contract stamp `chunk-structure-v3.1`. TIER_FROZEN_PARAMS unchanged.

## Why (measured, handbook.html = 3.2 MB, 316k words, 6,926 `<li>`, 2,825 `<tr>`, 1,819 `<pre>`, 3,773 headings)

| | v1.0.0 extractor | v1.1.0 only | v1.1.0 + chunker v3.1 | Markdown control (VES Handbook) before → after |
|---|---|---|---|---|
| parents | 303 | 3,167 (avg 98 w; 3,051 under the 280-word floor) | 802 (avg 392 w; 30 under) | 1,322 (857 under) → 704 (10 under) |
| children | 4,758 | 8,268 | 5,538 | 4,636 → 4,520 |
| `stub` children (noise role: extraction and enrichment skip them) | 1,747 (37 %) | 3,080 (37 %) | 400 (7 %) | 101 (2 %) → 5 (0 %) |
| children under 60 chars | 1,395 (29 %) | 1,711 | 94 | 75 → 2 |

- v1.0.0 made every block tag a paragraph: one child per list item / table cell / code line. v1.1.0 fixed the shape but exposed the chunker: every `####`/`#####` label (3,125 of them, ~83 words per heading) became its own sub-floor section, and 2,297 of the remaining stubs were lead-in lines ("The same applies to:", "Prompt field:") separated from the list or code block they introduce because regions never share a child.
- The remaining 7 % on the handbook are tiny fenced snippets and one-line tables that stay atomic by doctrine (`test_structured_blocks_are_atomic_children`), each carrying its lead-in.
- HTML residue check on the first ingest: 0 entities, the 39 "tagged" chunks were the document's own `<placeholder>` text.

## Changes

- `shared/polymath_shared/materializer.py`: `_TextExtractor` rewritten (block builder), `_materialize_html` builds the block source_map directly, `_SKIP_TAGS` += nav, version 1.1.0.
- `workers/workers/tier_chunker.py`: `_merge_small_sections`, `_common_prefix`, `_section_body_words`, `_coalesce_fragments` (kinds-aware), lead-in exception in `_prose_child_spans`, `CHUNK_CONTRACT_V3 = "chunk-structure-v3.1"`.
- `eval/fixtures/native_docs/structured.html` (new fixture: nested lists, `<li><p>`, table, pre, headings, br, blockquote, nav/script/style).
- Tests: `test_materializer.py` +5 (list block, table block, fenced pre, headings/br/quote/noise/version/determinism, end-to-end through the tier chunker with zero stub children); `test_tier_chunker.py` +4 (label sections merge to the floor under shared ancestry, sub-stub/title sections still drop, lead-in joins its block, contract v3.1) and the heading-bounded exit gate restated for v3.1 (a sub-floor intro merges forward; siblings past the floor and H1 boundaries never merge).

## Proof

- `test_materializer.py` 19 passed, `test_tier_chunker.py` + `test_tier_chunk_gap_accounting.py` + `test_chunk_structure_v2.py` green; full determinism suite green apart from the three pre-existing data/DiskFull-dependent files (deselected, tracked in 11.79/11.81).
- Live re-ingest receipts: see the addendum below (filled from the database after the third ingest).

## Rejected claims

- "Demote h4–h6 to plain text in the materializer." Rejected: it hides the author's structure from heading_path and only helps HTML; the sub-floor problem is the chunker's and shows on Markdown too (857 of 1,322 parents under the floor on the control book).
- "Merge sub-stub sections too" (measured: dropped text 48 KB → 227 chars on the handbook). Rejected: it moves title pages and part dividers into the next chapter's first child; the v3.3 drop doctrine and `test_stub_and_heading_only_sections_drop` stand. The remaining drops on the handbook are 606 label-only sections (21.8 KB of heading lines, 23.7 KB of sub-15-word bodies), all recorded as `dropped_stub`.
- "Let a lead-in + tiny code span keep merging forward." Rejected: it chains code into the next paragraph; structured children stay atomic.

## Open contract gaps

- Sub-15-word bodies under label headings (e.g. "#### Verification" + two test names) still drop; a future rule could attach them to the following real section as layout-anchored context.
- Region role `code` is assigned to pipe tables (symbol share), which excludes them from summaries; extraction and retrieval still see them.
- Re-ingesting an existing document requires delete + upload: intake is a replay-exempt no-op on the same content-addressed doc_id (`ON CONFLICT (doc_id) DO NOTHING`), so a materializer or chunker change never rewrites chunks by itself.

## Addendum — live re-ingest receipts (16:0xZ, third ingest of handbook.html)

The second ingest (materializer 1.1.0, chunker v3) ran before the intake worker had restarted onto v3.1; its extraction held a stage transaction so the delete answered 409 `runs_in_flight` until the ticket was superseded (`DELETE-WINS` quiesce), then took 115 s to remove 11,435 chunks. Third ingest, verified in the database:

| receipt | value |
|---|---|
| `materialization.parser_version` / format | 1.1.0 / html |
| `chunk_contract_version` | chunk-structure-v3.1 |
| parents | 802, avg 392 words, 30 under the 280-word floor |
| children | 5,538, avg 54 words; 94 under 60 chars |
| child roles | body 4,802 · stub 400 (7 %) · code 302 · question_bank 20 · noise_ocr 14 |
| list-bearing children | 996 (avg 47 words); table-bearing 280; fenced code 1,738 |
| layout `dropped_stub` | 606 spans, 48,059 chars (label-only sections, doctrine) |
| extraction at write time | extraction calls=16 accepted_items=442 tickets=[('extract', 'leased'), ('intake', 'done')] |

Identical to the offline measurement on the same bytes (deterministic chunker).
