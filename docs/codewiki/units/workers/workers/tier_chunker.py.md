# unit: workers/workers/tier_chunker.py
anchor: workers/workers/tier_chunker.py:1-725

## purpose
TIER-CHUNKER-V3: splits one document into heading-bounded parent chunks (the author's own sections) with byte-exact source offsets, plus exact-substring children, under contract `chunk-structure-v3` (latent plan D15, Phase 0) — workers/workers/tier_chunker.py:1-26 [DERIVED].
Producer for the ingestion pipeline; sole importer is `workers/workers/intake_worker.py` (FACTS.importers) — workers/workers/intake_worker.py [DERIVED].
Deterministic by design: "same text → same regions → same spans → same content-addressed ids. No models, no embedder, no RNG" — workers/workers/tier_chunker.py:24-26 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `CHUNK_CONTRACT_V3` | constant | `= "chunk-structure-v3.1"` | workers/workers/tier_chunker.py:35 | — |
| `PROVIDER` | constant | `= "tier_v3"` | workers/workers/tier_chunker.py:36 | — |
| `TIER_FROZEN_PARAMS` | dict | 9 frozen budget keys (see invariants) | workers/workers/tier_chunker.py:40-50 | — |
| `TierRegion` | dataclass | `(kind, text, start, heading_path, level=0)`; property `end = start + len(text)` | workers/workers/tier_chunker.py:61-70 | — |
| `walk_regions` | def | `(text: str) -> list[TierRegion]` | workers/workers/tier_chunker.py:77-164 | — |
| `tier_chunk_rows` | def | `(text, doc_id, params=None) -> list[dict]` | workers/workers/tier_chunker.py:599-603 | workers/workers/intake_worker.py [INFERRED: only importer named in FACTS] |
| `tier_chunk_layout` | def | `(text, doc_id, params=None) -> tuple[list[dict], list[dict]]` | workers/workers/tier_chunker.py:606-706 | workers/workers/intake_worker.py [INFERRED: only importer named in FACTS] |

## contracts

**tier_chunk_layout(text, doc_id, params=None)** — workers/workers/tier_chunker.py:606-706
- in: `p = dict(TIER_FROZEN_PARAMS)`, then `p.update(params)` if params given — workers/workers/tier_chunker.py:623-625 [DERIVED]
- out rows: children in document order, parents appended after; ids content-addressed via `make_chunk_id(doc_id, i, child["text"])` / `make_chunk_id(doc_id, base + j, parent_text)` — workers/workers/tier_chunker.py:618-622, workers/workers/tier_chunker.py:676, workers/workers/tier_chunker.py:686 [DERIVED]
- out layout: dicts `{kind, char_start, char_end}`; kinds `heading`, `dropped_stub` (section body < `parent_stub_words`), `dropped_empty` (parent with no child span); deduped on `(kind, char_start, char_end)` and sorted — workers/workers/tier_chunker.py:628-629, workers/workers/tier_chunker.py:637-640, workers/workers/tier_chunker.py:644-648, workers/workers/tier_chunker.py:704-706 [DERIVED]
- pipeline: `walk_regions` → `_sections` → `_merge_page_sections` → `_merge_small_sections` → per-section `_parent_spans` → `_child_spans_for_parent` — workers/workers/tier_chunker.py:630-631, workers/workers/tier_chunker.py:642-648 [DERIVED]
- post: `_validate` must pass (see invariants) — workers/workers/tier_chunker.py:703 [DERIVED]

**tier_chunk_rows(text, doc_id, params=None)** — workers/workers/tier_chunker.py:599-603
- returns `rows` only from `tier_chunk_layout`; "Rows only (the historical surface)" — workers/workers/tier_chunker.py:601-603 [DERIVED]

**walk_regions(text)** — workers/workers/tier_chunker.py:77-164
- out: regions of kind `heading | prose | code | table | list` — workers/workers/tier_chunker.py:62 [DERIVED]
- heading stack pops on same-or-shallower level, so `heading_path` is the section's true ancestry — workers/workers/tier_chunker.py:78-81, workers/workers/tier_chunker.py:107-110 [DERIVED]

**Row schema** (both tiers): keys `chunk_id, doc_id, parent_id, chunk_index, tier, text, summary, char_start, char_end, heading_path, token_count, chunk_contract_version, provider` — workers/workers/tier_chunker.py:659-670, workers/workers/tier_chunker.py:684-698 [DERIVED]
- child summary: `summarize(chunk_text, max_sentences=2, max_chars=420)`; parent summary: `summarize(parent_text, max_sentences=3, max_chars=600)` — workers/workers/tier_chunker.py:663, workers/workers/tier_chunker.py:691 [DERIVED]
- `parent_id` is `None` until backfilled to the parent's `chunk_id` — workers/workers/tier_chunker.py:677, workers/workers/tier_chunker.py:700-701 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`); imports are only `re`, `dataclasses`, `polymath_shared.identity.chunk_id`, `workers.summarizer.summarize` — workers/workers/tier_chunker.py:29-33 [INFERRED: no db/network/env module imported]
- External calls: `summarize(...)` once per child and per parent row — workers/workers/tier_chunker.py:33, workers/workers/tier_chunker.py:663, workers/workers/tier_chunker.py:691 [DERIVED]
- Files / subprocesses / env flags: none read — workers/workers/tier_chunker.py:29-33 [INFERRED: no such imports]

## invariants
INVARIANT: `parent_target_words` (850) < `parent_max_words` (1400) — workers/workers/tier_chunker.py:42-43 [DERIVED]
  fails-if: `_pack_spans`/`_parent_spans` merge logic (caps at `cap`, targets at `target`) inverts and produces oversize parents — workers/workers/tier_chunker.py:249-255, workers/workers/tier_chunker.py:546-549
INVARIANT: `source[s:e] == row["text"]` for every row — workers/workers/tier_chunker.py:719 [DERIVED]
  fails-if: AssertionError "offset roundtrip failed"
INVARIANT: child offsets monotonic non-overlapping (`s >= last_end`) — workers/workers/tier_chunker.py:720-722 [DERIVED]
  fails-if: AssertionError "child overlap"
INVARIANT: every child span inside its parent span (`ps <= s and e <= pe`) — workers/workers/tier_chunker.py:723-724 [DERIVED]
  fails-if: AssertionError "child escapes parent span"
INVARIANT: word measure is `len(text.split())` everywhere, including `token_count` — workers/workers/tier_chunker.py:38-39, workers/workers/tier_chunker.py:73-74 [DERIVED]
  fails-if: any consumer treats `token_count` as model tokens; budgets silently shift
INVARIANT: section body < `parent_stub_words` (15) yields zero rows, only a `dropped_stub` layout region — workers/workers/tier_chunker.py:44, workers/workers/tier_chunker.py:634-640 [DERIVED]
  fails-if: title pages / part dividers leak into the next parent's text
INVARIANT: heading regions never become child spans (children come only from non-heading regions) — workers/workers/tier_chunker.py:516, workers/workers/tier_chunker.py:556-557, workers/workers/tier_chunker.py:582-595 [DERIVED]
  fails-if: heading text duplicated into child bodies, violating the v2 header rule — workers/workers/tier_chunker.py:10-12
INVARIANT: atomic child (code/table/list) ≤ `atomic_child_max_words` (700), split at line boundaries above that — workers/workers/tier_chunker.py:49, workers/workers/tier_chunker.py:588-592 [DERIVED]
  fails-if: oversize atomic block either exceeds embed budget or loses atomicity
INVARIANT: fragment coalescing never merges past `child_max_words` (250) — workers/workers/tier_chunker.py:47, workers/workers/tier_chunker.py:494, workers/workers/tier_chunker.py:500 [DERIVED]
  fails-if: lead-in + list/code child exceeds child budget

## determinism & idempotency
determinism: DETERMINISTIC — no RNG/clock/db/env; ids content-addressed (`make_chunk_id(doc_id, index, text)`) — workers/workers/tier_chunker.py:24-26, workers/workers/tier_chunker.py:676, workers/workers/tier_chunker.py:686 [DERIVED]; caveat: `row["summary"]` comes from `workers.summarizer.summarize` — workers/workers/tier_chunker.py:663, workers/workers/tier_chunker.py:691 [INFERRED: summary determinism is that module's responsibility]
idempotency: SAFE — pure function of `(text, doc_id, params)`; same inputs recompute identical rows and layout — workers/workers/tier_chunker.py:24-26, workers/workers/tier_chunker.py:623-625 [INFERRED: no mutation of inputs or external state visible in source]

## failure behaviour
No try/except and no fallback handlers exist in this unit — workers/workers/tier_chunker.py:709-724 [INFERRED: full source has only the assert-based gate]. All failures surface as `AssertionError` from `_validate`: "chunk offsets out of range" — workers/workers/tier_chunker.py:718; "offset roundtrip failed" — workers/workers/tier_chunker.py:719; "child overlap" — workers/workers/tier_chunker.py:721; "child escapes parent span" — workers/workers/tier_chunker.py:724 [DERIVED].

## dumb-code flags
- `token_count` is a whitespace word count, not tokens — workers/workers/tier_chunker.py:38-39, workers/workers/tier_chunker.py:73-74 [DERIVED]
- Constant named `CHUNK_CONTRACT_V3` carries value `"chunk-structure-v3.1"`; name lags version — workers/workers/tier_chunker.py:35 [DERIVED]
- Version tag `TIER-CHUNKER-V3.1` hardcoded in 4 places (comment at 35, lead-in comment at 317, docstrings at 439 and 479) — must be edited together — workers/workers/tier_chunker.py:35, workers/workers/tier_chunker.py:317, workers/workers/tier_chunker.py:439, workers/workers/tier_chunker.py:479 [DERIVED]
- Dead bookkeeping: `_coalesce_fragments` maintains a `kind` list and assigns `"mixed"` but returns only the spans; kind mutations are discarded — workers/workers/tier_chunker.py:485-508 [DERIVED]
- Duplicated absorption logic: `_merge_small_sections` (section-level, 458-473) and `_parent_spans`'s closing merge (parent-level, 562-574) both implement "absorb small neighbour under cap" — workers/workers/tier_chunker.py:458-473, workers/workers/tier_chunker.py:562-574 [DERIVED]
- Summary budgets (`2/420` children, `3/600` parents) are call-site literals, not in `TIER_FROZEN_PARAMS` — workers/workers/tier_chunker.py:663, workers/workers/tier_chunker.py:691 [DERIVED]
- `_PAGE_NUM_RE` grabs any digit run inside scaffold segments to build "Page N–M" labels — workers/workers/tier_chunker.py:358, workers/workers/tier_chunker.py:388-390, workers/workers/tier_chunker.py:402-404 [DERIVED]

## refactor notes
- Row schema consumers: `intake_worker.py` imports this module (FACTS.importers); any key/id/ordering change in the row dicts breaks intake persistence — workers/workers/tier_chunker.py:659-670, workers/workers/tier_chunker.py:684-698 [DERIVED]
- Chunk ids are content-addressed over `(doc_id, index, text)`: any change to spans, budgets in `TIER_FROZEN_PARAMS`, or merge rules re-ids every chunk — reingest required — workers/workers/tier_chunker.py:40-50, workers/workers/tier_chunker.py:676, workers/workers/tier_chunker.py:686 [DERIVED]
- `_validate` enforces the §8 offset contract that "UI provenance and the projection verifiers rely on" — do not weaken or remove asserts — workers/workers/tier_chunker.py:15-18, workers/workers/tier_chunker.py:709-724 [DERIVED]
- Layout kind strings `"heading"`, `"dropped_stub"`, `"dropped_empty"` are persisted by intake in `document_layout` (per CHUNK-GAP-ACCOUNTING-V1 comment) — renaming them is a schema break — workers/workers/tier_chunker.py:608-617, workers/workers/tier_chunker.py:628, workers/workers/tier_chunker.py:638, workers/workers/tier_chunker.py:645 [DERIVED]
- `CHUNK_CONTRACT_V3` / `PROVIDER` land on every row; bumping either orphans rows filtered on `chunk_contract_version`/`provider` — workers/workers/tier_chunker.py:35-36, workers/workers/tier_chunker.py:668, workers/workers/tier_chunker.py:697 [DERIVED]

## VERIFY
```verify
grep -Fq 'CHUNK_CONTRACT_V3 = "chunk-structure-v3.1"' workers/workers/tier_chunker.py
grep -Fq 'PROVIDER = "tier_v3"' workers/workers/tier_chunker.py
grep -Fq '"parent_target_words": 850,' workers/workers/tier_chunker.py
grep -Fq '"atomic_child_max_words": 700,' workers/workers/tier_chunker.py
grep -Fq 'assert source[s:e] == row["text"], "offset roundtrip failed"' workers/workers/tier_chunker.py
grep -Eq 'def (tier_chunk_rows|tier_chunk_layout)\(' workers/workers/tier_chunker.py
test "$(grep -c -F 'TIER-CHUNKER-V3.1' workers/workers/tier_chunker.py)" -ge 3
! grep -Fq 'import random' workers/workers/tier_chunker.py
```
