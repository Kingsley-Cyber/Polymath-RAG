# unit: shared/polymath_shared/document_profile/context.py
anchor: shared/polymath_shared/document_profile/context.py:1-262

## purpose
DOCUMENT-PROFILE-V1 step 2 — the lean context builder (owner spec 2026-09-07). Turns what intake knows about a document (name, heading paths, first/last sections, sampled positions, known terms) into the ~500-token DOCUMENT block the profile prompt receives. Pure module: the caller loads rows; it never touches a store. The rendered block is hashed (`input_hash`) as the second link of the profile receipt chain (content hash → INPUT HASH → raw response hash → compiled hash → projection hash). — context.py:1-13 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| est_tokens | def | (text: str) -> int | context.py:41-44 | — |
| clean_title | def | (source_name: str) -> str | context.py:47-54 | — |
| structure_lines | def | (parents: Sequence[dict], *, max_lines: int = 400) -> list[str] | context.py:78-106 | — |
| DocumentContext | class | dataclass; methods structure_block, excerpts_block (properties), to_dict, input_hash | context.py:152-196 | — |
| build_context | def | (document: dict, parents: Sequence[dict], *, terms=(), budget_tokens=DEFAULT_BUDGET_TOKENS, allocation=None) -> DocumentContext | context.py:199-262 | — |

Module imported by: `document_profile/fingerprint.py`, `document_profile/giant_profile.py`, `document_profile/grounding.py`, `workers/workers/doc_profile_worker.py` (FACTS.importers). Private helpers: `_trim_tokens`, `_clean_segment`, `_stride_select`, `_body_parents`, `_is_furniture_parent` (context.py:57-149).

## contracts
**build_context** — context.py:199-262
- in: `document` = {source_name, media_type, frontmatter?, doc_id?}; `parents` rows = {heading_path, text, chunk_index, char_start, char_end, region_role?} in any order — context.py:201-202 [DERIVED]
- pre: caller has already loaded parent rows; module performs no store access — context.py:6 [DERIVED]
- out: `DocumentContext` with title, identity, structure, opening, ending, middle, terms, budget_tokens, allocation, used_tokens, sources — context.py:256-261 [DERIVED]
- post: if `budget_tokens < sum(allocation)`, every surface is scaled by `scale` with floor 4 tokens (`max(4, int(v * scale))`) — context.py:206-208 [DERIVED]
- post: `sources` reports `parents`/`body_parents`/`heading_paths` counts, `structure_mode` = "headings" iff `len(structure) > 2` else "positions", `title_source` = "frontmatter" iff `fm.get("title")` else "source_name" — context.py:259-261 [DERIVED]

**structure_lines** — context.py:78-106
- in: parent rows in any order; heading_path may be a list or a JSON/stray string
- out: distinct heading paths in document order rendered `A › B › C`, furniture/file/page segments removed, capped at `max_lines=400` — context.py:78-80, 104-105 [DERIVED]
- pre: sorts by `(chunk_index is None, chunk_index or 0, char_start or 0)` — context.py:83 [DERIVED]

**DocumentContext.input_hash(content_hash: str = "")** — context.py:190-196
- out: sha256 hex of `json.dumps({builder, content_hash, identity, structure_block, excerpts_block, allocation}, sort_keys=True, ensure_ascii=False)` — context.py:193-196 [DERIVED]
- post: pure function of rendered block + builder version + allocation + content hash — context.py:191-192 [DERIVED]

**est_tokens** — context.py:41-44
- out: `0` for empty/whitespace text, else `max(1, len(t) // 4)` — context.py:43-44 [DERIVED]

**clean_title** — context.py:47-54
- out: extension/suffix/markdown-link/bracket-noise stripped, whitespace collapsed, trimmed of ` #›-–—:|,.`, hard-capped at `[:120]` — context.py:49-54 [DERIVED]

## effect surface
- Postgres tables read: none (FACTS.tables_read = []) / written: none (FACTS.tables_written = [])
- Qdrant, files, network, subprocess: none; module docstring: "this module never touches a store" — context.py:6 [DERIVED]
- Env flags read: none. Imports are stdlib only (hashlib, json, re, collections.abc, dataclasses, typing) — context.py:16-21 [DERIVED]

## invariants
INVARIANT: sum(DEFAULT_ALLOCATION) = 40+150+80+60+100+20 = 450 ≤ DEFAULT_BUDGET_TOKENS = 500 — context.py:24,26 [DERIVED]
  fails-if: if the allocation sum exceeded the budget, `scale < 1.0` and every surface shrinks to `max(4, int(v*scale))` — context.py:206-208
INVARIANT: est_tokens(t) ≥ 1 for any non-empty t; == 0 only when empty — context.py:43-44 [DERIVED]
INVARIANT: `_trim_tokens` char limit = `tokens * 4`, matching est_tokens' 4 chars/token — context.py:60 vs context.py:44 [DERIVED]
INVARIANT: `_stride_select` always keeps index 0 and `len(lines)-1` — context.py:122 [DERIVED]
INVARIANT: structure dedupe key is `line.lower()`; first occurrence in document order wins — context.py:99-102 [DERIVED]
INVARIANT: middle samples taken only when `len(structure) <= 2 or len(body) >= 40`, at `int(n*0.25/0.5/0.75)` minus `{0, n-1}` — context.py:230-236 [DERIVED]
INVARIANT: structure budget = `alloc["structure"]` + spare from unused opening/ending/middle/terms tokens — context.py:248-252 [DERIVED]
INVARIANT: `used_tokens` is filled for all six surfaces (structure, opening, ending, middle, terms, identity) — context.py:226,235,245,253-254 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — pure string/hash computation; `sha256` over `json.dumps(..., sort_keys=True)`; no clock/random/uuid/network/db/env inputs — context.py:190-196 [DERIVED]
idempotency: SAFE — no writes, no store access; same inputs yield the same `DocumentContext` and `input_hash` — context.py:6 [DERIVED]

## failure behaviour
- `except Exception` at context.py:88 (fallback "handled: assign", FACTS.fallbacks): a heading_path string that fails `json.loads` is reassigned `hp = [hp]` — the raw string becomes a single-element path. Caller sees that parent's structure line as one segment instead of a parsed hierarchy — context.py:85-89 [DERIVED]
- No error codes raised anywhere; `None`/blank inputs are coerced via `(text or "")` / `str(...)` (e.g. context.py:43,48,59,73) rather than rejected — [DERIVED]

## dumb-code flags
- Magic 4 chars/token duplicated in two places: `len(t) // 4` (context.py:44) and `limit = max(0, tokens) * 4` (context.py:60).
- Budget headroom never spent: DEFAULT_BUDGET_TOKENS 500 vs allocation sum 450; the 50-token surplus is not allocated to any surface — spare only flows from unused excerpt tokens, not from budget − sum — context.py:24,26,249-252 [DERIVED]
- Furniture word lists diverge: `_FURNITURE_RE` (context.py:35-37) matches `index`, `notes`, `also by`; `_FURNITURE_WORD_RE` (context.py:136-138) omits all three. A heading "Index" is stripped from structure lines but its body parent survives `_is_furniture_parent` unless `region_role == "index"` — context.py:141-149 [DERIVED]
- Hard title cap `[:120]` with no ellipsis marker — context.py:54.
- Magic thresholds: `max_lines=400` (context.py:78), `keep = max(2, ...)` (context.py:119), safety `cap = max(12, tokens // ...)` (context.py:125), floor `max(4, ...)` per surface (context.py:208), `per = max(8, ...)` per middle sample (context.py:233).
- `_FURNITURE_RE` allows `copyright page` while `_FURNITURE_WORD_RE` handles it via `copyright` — overlapping but not identical regexes maintained separately — context.py:35-37,136-138 [DERIVED]

## refactor notes
- Four importers depend on this module (FACTS.importers): `fingerprint.py`, `giant_profile.py`, `grounding.py`, `workers/workers/doc_profile_worker.py` — signature changes to `build_context`, `DocumentContext`, `est_tokens`, `clean_title`, `structure_lines` ripple into all four.
- `input_hash` is receipt-chain link 2 (content hash → INPUT HASH → raw response hash → compiled hash → projection hash); any change to `BUILDER_VERSION`, rendering in `structure_block`/`excerpts_block`, or the hash payload invalidates stored hashes — context.py:8,190-196 [DERIVED]
- `DEFAULT_ALLOCATION` keys are indexed positionally by string throughout (`alloc["identity"]`, `alloc["opening"]`, `alloc["ending"]`, `alloc["middle"]`, `alloc["terms"]`, `alloc["structure"]`) — renaming a key raises KeyError at context.py:219,224-225,233,242,249-251 [DERIVED]
- `sources` dict keys (context.py:259-261) and `used_tokens` (context.py:226-254) are emitted into `to_dict` output that downstream consumers may read — keep key names stable.

## VERIFY
```verify
grep -Fq 'DEFAULT_BUDGET_TOKENS = 500' shared/polymath_shared/document_profile/context.py
grep -Fq 'BUILDER_VERSION = "lean-context-v1"' shared/polymath_shared/document_profile/context.py
grep -Eq '^def (est_tokens|clean_title|structure_lines)\(' shared/polymath_shared/document_profile/context.py
grep -Fq 'return hashlib.sha256(payload.encode("utf-8")).hexdigest()' shared/polymath_shared/document_profile/context.py
grep -Eq 'scale < 1\.0' shared/polymath_shared/document_profile/context.py
test "$(grep -c -F 'BUILDER_VERSION' shared/polymath_shared/document_profile/context.py)" -ge 2
! grep -Fq 'DEFAULT_BUDGET_TOKENS = 600' shared/polymath_shared/document_profile/context.py
```
