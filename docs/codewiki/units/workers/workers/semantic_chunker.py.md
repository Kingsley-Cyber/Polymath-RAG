# unit: workers/workers/semantic_chunker.py
anchor: workers/workers/semantic_chunker.py:1-448

## purpose
Implements SEMANTIC-CHUNKING-V2 (chunk-contract-v2): markdown-derived hard structural regions (heading/prose/code/table/list), then Chonkie SemanticChunker (pinned "1.7.0") splits only inside prose regions using Polymath's pinned Qwen embedder via a batching adapter with a Postgres content-addressed cache. Produces offset-validated child chunk rows plus deterministic parent rows for the intake worker. — workers/workers/semantic_chunker.py:1-13 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Region` | class (frozen dataclass) | fields: `kind, text, start, heading_path` | workers/workers/semantic_chunker.py:51-56 | — |
| `split_structural_regions` | def | `(text: str) -> list[Region]` | workers/workers/semantic_chunker.py:59-138 | — |
| `PolymathEmbeddingsAdapter` | class | `__init__(cache)`, `embed(text)->ndarray`, `embed_batch(texts)->list[ndarray]`, `similarity(u,v)->float64`, `dimension->int`, `get_tokenizer()` | workers/workers/semantic_chunker.py:147-192 | — |
| `SemanticEmbeddingCache` | class | `__init__(dsn=None)`, `get(text)->list[float]|None`, `put(text, vector)`, `embed_texts(texts)` | workers/workers/semantic_chunker.py:195-256 | — |
| `chunk_contract_identity` | def | `(params: dict|None) -> dict` | workers/workers/semantic_chunker.py:265-288 | — |
| `semantic_chunk_rows` | def | `(text: str, doc_id: str, *, cache: SemanticEmbeddingCache, params: dict|None) -> list[dict]` | workers/workers/semantic_chunker.py:307-380 | workers/workers/intake_worker.py (module importer, per FACTS.importers) |
| constants | module | `CHUNK_CONTRACT_V2`, `CHONKIE_VERSION`, `HARD_BOUNDARY_POLICY`, `SENTENCE_CONTRACT`, `TOKENIZER_CONTRACT`, `SEMANTIC_V2_DEFAULTS` | workers/workers/semantic_chunker.py:26-43 | — |

## contracts

**`semantic_chunk_rows` — workers/workers/semantic_chunker.py:307-380**
- in: `text` (authoritative source), `doc_id`, keyword-only `cache`, optional `params` overriding `SEMANTIC_V2_DEFAULTS` (321-323).
- out: list of child row dicts (keys `doc_id, tier="child", text, summary, char_start, char_end, heading_path, token_count, chunk_contract_version, provider, chunk_index, chunk_id, parent_id`) followed by parent rows (383-413).
- pre: `chonkie` installed (`SemanticChunker` imported at 319; adapter raises `RuntimeError("chonkie is not installed")` at 154 if base import failed).
- post: every child satisfies `_validate_contiguous` (378); each child `text` equals `source[char_start:char_end]` (447); heading regions skipped, never chunk-body text (329-330); whitespace-trim of Chonkie's span is the one documented normalization (354-361, docstring 315-318).

**`chunk_contract_identity` — workers/workers/semantic_chunker.py:265-288**
- in: optional `params` merged over `SEMANTIC_V2_DEFAULTS`.
- out: dict with `contract="chunk-contract-v2"`, `provider="semantic_v2"`, `provider_version="2.0.0"`, `chonkie_version="1.7.0"`, `hard_boundary_policy="hard-boundary-v1"`, `sentence_contract="sentence-contract-v1"`, `tokenizer_contract="chonkie-word-v1"`, plus embedding identity and all chunking params. Any change = new interpretation (§21, 266-267).
- pre: `EmbedderClient` reachable — calls `client.manifest()` (292-304).

**`split_structural_regions` — workers/workers/semantic_chunker.py:59-138**
- in: full document text.
- out: `Region` list; headings push onto `heading_path` (87, 88); code fences consumed to closing ``` or EOF (89-104); tables (106-115) and contiguous list blocks (117-132) are hard boundaries.
- post: heading text lives in `heading_path` metadata only (docstring 61-64).

**`SemanticEmbeddingCache` — workers/workers/semantic_chunker.py:195-256**
- key: `sha256(f"{contract}|{text}")` where contract = `active_contract().contract_id` (206-210).
- `put`: `INSERT INTO semantic_embedding_cache ... ON CONFLICT (cache_key) DO NOTHING` (223-225).
- `embed_texts`: `EmbedderClient` with `verify_pin()`, batches of 32, `representation_kind="child_chunk"` (227-239).

## effect surface
- Postgres table `semantic_embedding_cache`: read (`SELECT vector ... WHERE cache_key=%s`, 214) and written (`INSERT ... ON CONFLICT DO NOTHING`, 223-225). DSN = `get_settings().postgres.dsn` or `dsn` arg (259-262, 470-481 source lines 244/254).
- Network: `EmbedderClient.embed(...)` (235), `verify_pin()` (232), `manifest()` (296) — Qwen sidecar, batch ≤ 32.
- Third-party import: `chonkie` (BaseEmbeddings 142, SemanticChunker 319, WordTokenizer 190); ImportError swallowed → base becomes `object` (143-144).
- No files, subprocesses, or env flags read directly in this unit.

## invariants
- INVARIANT: `text[abs_start:abs_end] == chunk_text` for every Chonkie-derived child — workers/workers/semantic_chunker.py:364 [DERIVED]; fails-if: `AssertionError` at ingestion, document rejected.
- INVARIANT: `source[char_start:char_end] == row["text"]` and `char_start >= last_end` for all children — workers/workers/semantic_chunker.py:445-447 [DERIVED]; fails-if: overlapping or phantom chunks reach `_validate_contiguous`.
- INVARIANT: `skip_window == 0` (contiguous spans only) — default `"skip_window": 0` (40) and hardcoded `skip_window=0` (348) [DERIVED]; fails-if: any nonzero value produces non-contiguous chunks violating §8.
- INVARIANT: embedding batch size ≤ 32 — workers/workers/semantic_chunker.py:178, 234 [DERIVED]; fails-if: /infer contract violation on the embedder sidecar.
- INVARIANT: cache key = sha256 of `embedding_contract_id + "|" + text` — workers/workers/semantic_chunker.py:210 [DERIVED]; fails-if: cross-contract vector reuse corrupts similarity scores.
- INVARIANT: `parent_fanout = 4` children per parent, parent `chunk_index = len(children) + j` — workers/workers/semantic_chunker.py:392-399 [DERIVED]; fails-if: hierarchy shape diverges from legacy parent/child layout.
- INVARIANT: every row carries `chunk_contract_version = "chunk-contract-v2"` and `provider = "semantic_v2"` — workers/workers/semantic_chunker.py:374-375, 407-408, 427-428 [DERIVED]; fails-if: mixed-contract rows in one document.
- INVARIANT: parent `char_start/char_end` span `group[0].char_start` → `group[-1].char_end` but parent `text` is a summary, not a source substring — workers/workers/semantic_chunker.py:399-405 [DERIVED]; fails-if: nothing in-file — parents are added after `_validate_contiguous` (378-379), so §8 never checks them.

## determinism & idempotency
determinism: NONDETERMINISTIC (db: cache reads 214/writes 223; network: embedder calls 235, manifest 296). Structural scan and id assignment are pure/deterministic (59-138, 386-388); no clock/random/uuid in this file. Offset exactness is enforced by assertion regardless of embedder output (361-364).
idempotency: SAFE — cache write is `ON CONFLICT (cache_key) DO NOTHING` (223-225); re-running the same doc re-hits the cache and rebuilds identical rows; this function writes no document tables itself.

## failure behaviour
- `ImportError` on `chonkie` swallowed at import time → base class becomes `object`; later `RuntimeError("chonkie is not installed")` in `PolymathEmbeddingsAdapter.__init__` (143-144, 153-154). Caller sees RuntimeError only when the adapter is constructed.
- `AssertionError` raised, never caught: `"prose anchoring mismatch"` (341), exactness proof (361), `"document offset roundtrip failed"` (364), `"chunk offsets out of range"` (445), `"chunk overlap"` (446), `"offset roundtrip failed"` (447). Callers get hard failures, no partial output.
- `EmbedderClient`/`psycopg` errors propagate unhandled (227-239, 467-256-source 241-256); `client.close()` guaranteed via `finally` (238-239, 303-304).

## dumb-code flags
- Dead assignment: `prose_offset = len(region.text) - len(region.text.lstrip())` computed then never used; duplicates `lead_ws` on the next line, with an in-line comment admitting the confusion ("already rstripped? no — compute both") — workers/workers/semantic_chunker.py:337-339.
- Dead function: `_exact_span` defined, never called anywhere in the unit — workers/workers/semantic_chunker.py:432-433.
- Dead import: `split_sentences` imported with `summarize, summarize_children` but never called (docstring 10-12 says extraction keeps `summarizer.split_sentences`, i.e. deliberately elsewhere) — workers/workers/semantic_chunker.py:24.
- `in_fence` guard is obfuscated and effectively unreachable: `any(k == "code" for k in (regions[-1].kind if regions else "",))` and not `regions[-1].text.endswith("```")` — code regions are always closed or at EOF when re-evaluated, so `not in_fence` is always True at the heading check — workers/workers/semantic_chunker.py:82-84 [INFERRED: fence branch consumes to closing fence or EOF (96-104) before any heading can be re-checked].
- Duplicated literal: batch size `32` appears in both the adapter (178) and `embed_texts` (234), tied to the /infer contract but not a named constant.
- Param not threaded: `SEMANTIC_V2_DEFAULTS["skip_window"]` (40) and contract identity report it (284), but the `SemanticChunker` call hardcodes `skip_window=0` instead of `p["skip_window"]` — workers/workers/semantic_chunker.py:348.
- Contract/tokenizer mismatch: identity declares `tokenizer_contract: "chonkie-word-v1"` (30, 287) and the adapter returns `WordTokenizer()` (189-192), but `token_count` is plain `len(text.split())` (436-437) — stored `token_count` values are not WordTokenizer counts.
- Magic numbers inline: `summarize(chunk_text, max_sentences=2, max_chars=420)` repeated at 369 and 422.

## refactor notes
- `workers/workers/intake_worker.py` imports this module (FACTS.importers); changing `semantic_chunk_rows`'s signature or the row-dict key set (chunk_id, parent_id, tier, char_start/char_end, heading_path, token_count, chunk_contract_version, provider) breaks it — workers/workers/semantic_chunker.py:365-376, 395-409.
- Any change to `SEMANTIC_V2_DEFAULTS` values or `chunk_contract_identity` output creates a new interpretation (§21) and must be reflected in stored `chunk_contract_version` consumers — workers/workers/semantic_chunker.py:265-288.
- Cache keys embed the active embedding contract id (207-210): rotating the embedding contract silently orphans old `semantic_embedding_cache` rows (no deletion path in this unit).
- `make_chunk_id` (doc_id, index, text) and `summarize`/`summarize_children` come from `polymath_shared.identity` / `workers.summarizer` (23-24); their signatures are part of this unit's stability.
- `_validate_contiguous` runs before parents are appended (378-379); moving parent construction ahead of validation would assert on parent summary text, which is not a source substring.

## VERIFY
```verify
grep -Fq 'CHUNK_CONTRACT_V2 = "chunk-contract-v2"' workers/workers/semantic_chunker.py
grep -Fq 'ON CONFLICT (cache_key) DO NOTHING' workers/workers/semantic_chunker.py
grep -Fq 'representation_kind="child_chunk"' workers/workers/semantic_chunker.py
grep -Eq 'skip_window=0' workers/workers/semantic_chunker.py
! grep -Fq 'split_sentences(' workers/workers/semantic_chunker.py
test "$(grep -c -F 'assert' workers/workers/semantic_chunker.py)" -ge 6
grep -Fq 'return len(text.split())' workers/workers/semantic_chunker.py
```
