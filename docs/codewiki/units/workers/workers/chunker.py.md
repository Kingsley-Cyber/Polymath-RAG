# unit: workers/workers/chunker.py
anchor: workers/workers/chunker.py:1-570

## purpose
Deterministic, no-LLM child/parent chunker: splits a document into sentence-aligned child chunks, groups children into extractive parent summaries (fanout grouping), and emits chunk rows with source char offsets. Serves the top-down retrieval shape: document routing card -> parent (summary) -> child (evidence). Imported by `workers/workers/intake_worker.py` (FACTS.importers). workers/workers/chunker.py:1-14 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ChunkSpec` | class | (text, char_start, char_end, sentences: tuple[int, ...], layout_headings=()) -> frozen dataclass | workers/workers/chunker.py:25-33 | — |
| `ChunkPlan` | class | (doc_id, children, parents, document_summary, fanout, layout=[], contract="chunk-structure-v1") | workers/workers/chunker.py:37-46 | — |
| `plan_document` | def | (text, doc_id, *, child_target_chars=1200, parent_fanout=4, separator_mode=SEPARATOR_LEGACY) -> ChunkPlan | workers/workers/chunker.py:427-507 | — |
| `materialize_chunks` | def | (plan) -> list[dict] | workers/workers/chunker.py:510-570 | — |
| `SEPARATOR_LEGACY` / `SEPARATOR_SOURCE` | const | `"legacy_space"` / `"source_structure"` | workers/workers/chunker.py:72-73 | — |
| `CHUNK_CONTRACT_V1` / `CHUNK_CONTRACT_V2` | const | `"chunk-structure-v1"` / `"chunk-structure-v2"` | workers/workers/chunker.py:75-76 | — |
| `CHUNK_CONTRACT` | const | {SEPARATOR_LEGACY: V1, SEPARATOR_SOURCE: V2} | workers/workers/chunker.py:83-86 | — |

Module-level importer per FACTS: `workers/workers/intake_worker.py` — per-symbol callers not in FACTS.

## contracts
`plan_document` (workers/workers/chunker.py:427-507)
- in: `doc_id` must already be the content-hashed document identity (`identity.document_id`); pure function, no randomness, no model. workers/workers/chunker.py:436-438
- in: `separator_mode` selects contract; `SEPARATOR_LEGACY` (space join, frozen v1) is the DEFAULT "so nothing re-identifies by accident"; `SEPARATOR_SOURCE` rejoins with source separators. workers/workers/chunker.py:440-445
- pre: unknown `separator_mode` -> `ValueError` ("a chunk generation must name its contract"). workers/workers/chunker.py:457-461
- out: `ChunkPlan` with `children`, `parents` (parent i summarizes `children[fanout*i : fanout*(i+1)]`), `document_summary = summarize(text, max_sentences=6, max_chars=1600)`, `layout` heading regions, `contract` stamp. workers/workers/chunker.py:487-506
- out: no sentences -> `ChunkPlan(children=[], parents=[], document_summary="")`. workers/workers/chunker.py:463-466

`materialize_chunks` (workers/workers/chunker.py:510-570)
- in: a `ChunkPlan`.
- out: rows children-first (`chunk_index` = document order), parents appended after the last child (`base + j`). workers/workers/chunker.py:513-515, 540, 547
- out: child row keys `chunk_id, doc_id, parent_id, chunk_index, tier="child", chunk_contract_version, text, summary, char_start, char_end, layout_map`; `chunk_id = chunk_id(doc_id, i, spec.text)`; `summary = summarize(spec.text, max_sentences=2, max_chars=420)`. workers/workers/chunker.py:521-536
- post: every child in a parent's group gets `parent_id` set to that parent's `chunk_id`; parent row has `tier="parent"`, `summary == spec.text`. workers/workers/chunker.py:548-560, 564-568

## effect surface
- Postgres tables: none (`tables_read: []`, `tables_written: []`, FACTS).
- Qdrant / network / subprocess / env flags: none in source; imports are `re`, `dataclasses`, `polymath_shared.identity.chunk_id`, `workers.summarizer` (split_sentences, summarize, summarize_children), `polymath_shared.layout_evidence` (heading_regions, project_regions). workers/workers/chunker.py:17-21, 323, 386, 479

## invariants
INVARIANT: a sentence is never split mid-way — packer flushes on `buf_len + 1 + len(sentence) > target_chars` — workers/workers/chunker.py:4, 319-320, 351-352, 379-380, 404-405 [DERIVED]
  fails-if: mid-sentence chunks break sentence-aligned offsets and downstream anchors.
INVARIANT: `_soften_wraps` output length == input length (one `"\n"` -> one `" "`) — workers/workers/chunker.py:97-99, 111-122 [DERIVED]
  fails-if: every char offset into the source stops being valid.
INVARIANT: `_break_pathological_lines` swaps a single space for a newline, inserts nothing — workers/workers/chunker.py:236-238, 243-253 [DERIVED]
  fails-if: same — offsets no longer index the source.
INVARIANT: `CHUNK_CONTRACT[SEPARATOR_LEGACY] == CHUNK_CONTRACT_V1` and `CHUNK_CONTRACT[SEPARATOR_SOURCE] == CHUNK_CONTRACT_V2` — workers/workers/chunker.py:83-86 [DERIVED]
  fails-if: a half-old/half-new corpus becomes untellable apart (the failure mode P13 targets). workers/workers/chunker.py:78-82
INVARIANT: v1 `buf_len` excludes separators, so packing decisions (chunk text, ids, embeddings) are bit-for-bit unchanged from pre-layout code — workers/workers/chunker.py:410-413 [DERIVED]
  fails-if: chunk ids silently re-identify across generations.
INVARIANT: `_is_list_block` iff markers >= 3 and markers * 2 >= len(lines) — workers/workers/chunker.py:198-201 [DERIVED]
  fails-if: prose blocks get split into bogus list items.
INVARIANT: `_is_low_punct_multiline` iff len(lines) >= 5 and sentence_finals * 3 < len(lines) — workers/workers/chunker.py:227-230 [DERIVED]
  fails-if: unpunctuated transcripts get sentence-split into fragments.
INVARIANT: child `layout_map` `[]` means "detected, none here", distinct from NULL "never detected" — workers/workers/chunker.py:533-534 [DERIVED]
  fails-if: downstream conflates "no headings" with "layout detection never ran".

## determinism & idempotency
determinism: DETERMINISTIC ("Pure function: no randomness, no model", workers/workers/chunker.py:436-438; embedder-based `_semantic_deviation_split` and wtpsplit `_sat_split` deliberately NOT ported to keep chunking a pure function, workers/workers/chunker.py:167-173)
idempotency: SAFE (chunk identity is a content hash — "re-chunking unchanged text is a no-op and shifted text only shifts the chunks it touches", workers/workers/chunker.py:7-8)

## failure behaviour
- Only explicit raise in the module: `ValueError` for unknown `separator_mode`. workers/workers/chunker.py:457-461
- No try/except handlers anywhere in the source; nothing is swallowed. [DERIVED]
- Defensive path, not an exception: `_reconstruct_separator` returns a non-whitespace gap verbatim ("literal fidelity outranks normalisation") when sentence offsets misalign with the source. workers/workers/chunker.py:141-146

## dumb-code flags
- Magic numbers: `child_target_chars=1200`, `parent_fanout=4` (workers/workers/chunker.py:431-432); `_PATHOLOGICAL_LINE_CHARS = 5_000`, `_PATHOLOGICAL_SLICE_CHARS = 2_000` (workers/workers/chunker.py:187-188); summary budgets `max_sentences=6, max_chars=1600` (workers/workers/chunker.py:502) and `max_sentences=2, max_chars=420` (workers/workers/chunker.py:530); 200-char lookback window in `_break_pathological_lines` (workers/workers/chunker.py:248).
- Default `separator_mode=SEPARATOR_LEGACY` keeps the known-broken v1 space join as the default (0 of 7,085 production chunks contain a newline, 74% carry a glued heading) — intentional freeze, but a live foot-gun for new callers. workers/workers/chunker.py:51-55, 433, 440-443 [DERIVED]
- Duplicated packer logic: `_joined()`/separator tracking in v2 (workers/workers/chunker.py:334-359) vs `" ".join(buf)` in v1 (workers/workers/chunker.py:399); two near-identical `_flush` closures (workers/workers/chunker.py:342-346, 397-401).
- Parent-link pass is a triple-nested scan (`for parent_row / for child_id / for row in rows`) — O(parents × children × rows). workers/workers/chunker.py:564-568 [INFERRED: no index from chunk_id to row is kept, unlike `child_by_spec`].
- `_document_units` rewrites the local `text` when a block is softened and returns it (workers/workers/chunker.py:293-297, 532, 542); `plan_document` then runs `heading_regions(text)` on that softened copy, not the raw input (workers/workers/chunker.py:451-453, 481) [INFERRED: the returned text is the one bound at line 453].
- Legacy fallback recomputes `starts` via sequential `text.find` (workers/workers/chunker.py:468-473) — duplicate offset logic only used on the v1 path.

## refactor notes
- `workers/workers/intake_worker.py` imports this module (FACTS.importers); signature or row-schema changes to `plan_document`/`materialize_chunks` ripple there. Row keys (`chunk_id`, `parent_id`, `chunk_index`, `tier`, `chunk_contract_version`, `layout_map`) are the persisted shape. workers/workers/chunker.py:521-536, 548-560
- Changing the join or packing decisions changes chunk text -> `chunk_id` -> embeddings; v1 decisions are pinned bit-for-bit. workers/workers/chunker.py:7-8, 410-413
- The `contract` stamp is the only thing making the two generations tellable apart without re-deriving them; removing it reopens the half-old/half-new corpus failure. workers/workers/chunker.py:78-86
- Order of operations is load-bearing: soft-wrap repair must run AFTER routing and only on prose, or unpunctuated speech is collapsed. workers/workers/chunker.py:283-286
- Heading detection must stay on the materialized source text with line structure; downstream may not re-derive it from chunk text. workers/workers/chunker.py:475-478
- Both repairs (`_soften_wraps`, `_break_pathological_lines`) must stay length-preserving or all source offsets break. workers/workers/chunker.py:97-99, 236-238, 448-450

## VERIFY
```verify
grep -Fq 'child_target_chars: int = 1200' workers/workers/chunker.py
grep -Fq 'parent_fanout: int = 4' workers/workers/chunker.py
grep -Fq 'SEPARATOR_LEGACY = "legacy_space"' workers/workers/chunker.py
grep -Fq '_PATHOLOGICAL_LINE_CHARS = 5_000' workers/workers/chunker.py
grep -Fq 'unknown separator_mode' workers/workers/chunker.py
! grep -Fq 'import random' workers/workers/chunker.py
test "$(grep -c -F 'ChunkSpec(' workers/workers/chunker.py)" -ge 3
```
