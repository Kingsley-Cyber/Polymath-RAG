# unit: shared/polymath_shared/document_profile/grounding.py
anchor: shared/polymath_shared/document_profile/grounding.py:1-243

## purpose
Builds `DocumentGroundingContextV1`: a deterministic, CPU-only ~50-100 token document orientation (title / byline / type / top-level outline anchors) injected AHEAD of the ParentSkeleton data in the pMAP (parent-map) prompt — grounding.py:3-6,171-172 [DERIVED]. Source-derived only: frontmatter + filename + parents' heading paths; no model called, no store touched — grounding.py:11-13 [DERIVED]. Reuses `context.py` helpers so grounding and profile context share one title/structure derivation — grounding.py:24-26 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_grounding_context` | function | (document: dict, parents: Sequence[dict], *, budget_tokens: int = 90) -> DocumentGroundingContextV1 | grounding.py:194-242 | workers/workers/doc_parent_map_stage_worker.py, workers/workers/doc_parent_map_worker.py, shared/polymath_shared/document_profile/_small-modules (module-level importers; per-symbol use unknown) |
| `DocumentGroundingContextV1` | frozen dataclass | fields: title: str, byline: str, doc_type: str, anchors: tuple[str, ...], budget_tokens: int, version: str = "grounding-context-v1", context_hash: str = ""; methods render() -> str, to_dict() -> dict | grounding.py:159-186 | same importers (per-symbol unknown) |
| `GROUNDING_CONTEXT_VERSION` | constant | "grounding-context-v1" | grounding.py:43 | — |
| `DEFAULT_BUDGET_TOKENS` | constant | 90 | grounding.py:45 | — |

## contracts

`build_grounding_context` — grounding.py:194-242
- in: `document` = {source_name, media_type, frontmatter?}; `parents` = rows {heading_path, text, chunk_index, char_start, region_role?} in any order — grounding.py:200-204 [DERIVED]
- out: frozen `DocumentGroundingContextV1`; `context_hash` = sha256 of `"\x1f".join([GROUNDING_CONTEXT_VERSION, title, byline, doc_type, "\x1e".join(anchors)])` — grounding.py:189-191,237-241 [DERIVED]
- pre: none enforced; every input field optional (missing → fallback or omission) — grounding.py:205-218 [DERIVED]
- post: same (document, parents) ⇒ identical context and same `context_hash` — grounding.py:14-15,203-204 [DERIVED]
- post: `est_tokens(render()) <= budget_tokens`, enforced by trimming anchors first (pop trailing), then byline (drop), then doc_type (drop); title trimmed last with floor `_TITLE_MIN_TOKENS = 6` — grounding.py:17-18,227-235 [DERIVED]

`DocumentGroundingContextV1.render` — grounding.py:171-181
- out: line 1 always `DOCUMENT: {title}`; `BY: {byline}`, `TYPE: {doc_type}`, `OUTLINE: {a · b · ...}` emitted only when non-empty — grounding.py:174-180 [DERIVED]

`DocumentGroundingContextV1.to_dict` — grounding.py:183-186
- out: keys `version, title, byline, doc_type, anchors (list), budget_tokens, context_hash` — grounding.py:184-185 [DERIVED]

## effect surface
None. `tables_read = []`, `tables_written = []` (FACTS); "no summary is invented, no model is called, no store is touched" — grounding.py:13 [DERIVED]. Imports only `hashlib`, `re`, `collections.abc`, `dataclasses`, `typing` — grounding.py:30-34 [DERIVED]. No files, network, subprocess, or env flags.

## invariants

INVARIANT: DEFAULT_BUDGET_TOKENS = 90, comment "target band 50-100; hard ceiling enforced at build" — grounding.py:45 [DERIVED]
  fails-if: budget drifts outside ~50-100 → block stops being the compact pMAP orientation (grounding.py:4).
INVARIANT: len(anchors) <= _MAX_ANCHORS = 12 — grounding.py:49,154-155 [DERIVED]
  fails-if: outline floods the prompt / budget.
INVARIANT: byline <= _BYLINE_MAX_TOKENS = 16 tokens; doc_type <= _TYPE_MAX_TOKENS = 4 tokens — grounding.py:47-48,216-217 [DERIVED]
  fails-if: byline/type crowd out title/outline inside the budget.
INVARIANT: title never empty — fm.title → `_title_like_first_line(parents)` → `clean_title(source_name)` → "untitled"; noise title re-falls back to filename/"untitled" — grounding.py:206-213 [DERIVED]
  fails-if: render() emits `DOCUMENT: ` with nothing after it.
INVARIANT: title-like first line <= _TITLE_LINE_MAX_WORDS = 14 words, no sentence-terminal ending — grounding.py:54,113-116 [DERIVED]
  fails-if: a full first sentence becomes the document title.
INVARIANT: anchor rejected when letters < _MIN_ANCHOR_LETTERS = 3 or letters < len/2 — grounding.py:50,66-69 [DERIVED]
  fails-if: page numbers / rule lines surface as outline sections.
INVARIANT: anchors deduped case-insensitively on first heading-path segment; title-echo segments skipped via `_alpha` signature — grounding.py:133,140-153 [DERIVED]
  fails-if: running header repeats as every anchor.
INVARIANT: est_tokens(render()) <= budget_tokens holds only while budget_tokens >= ~8 (floor 6 + `DOCUMENT: ` prefix ≈ 2) — grounding.py:17,46,227-228 [INFERRED: `max(_TITLE_MIN_TOKENS, budget_tokens - 2)` cannot go below 6]
  fails-if: a tiny budget_tokens breaks the "NEVER exceeded" claim.

## determinism & idempotency
determinism: DETERMINISTIC — pure function of inputs; fixed sha256 (grounding.py:57-58), fixed sort key `(chunk_index is None, chunk_index or 0, char_start or 0)` (grounding.py:101-104), fixed byline key order "author, authors, organization, publisher" (grounding.py:75); no clock/random/uuid/network/db/env — grounding.py:30-34 [DERIVED]
idempotency: SAFE — nothing written, no store touched — grounding.py:13 [DERIVED]

## failure behaviour
No try/except anywhere in the unit (SOURCE 1-243) [DERIVED]. Missing data degrades silently: absent byline/type/anchors are omitted from render — grounding.py:174-180 [DERIVED]; noise title replaced by cleaned filename or "untitled" — grounding.py:212-213 [DERIVED]; flat/transcript documents yield no anchors — grounding.py:130-131 [DERIVED]. Exceptions from imported helpers (`clean_title`, `est_tokens`, `_trim_tokens`, `structure_lines` — grounding.py:36-41) propagate uncaught to the pMAP caller [DERIVED].

## dumb-code flags
- Docstring drift: module docstring claims "missing title falls back to the cleaned filename then a short title-like first line" — grounding.py:19-20 — but code order is first-line THEN filename, and the inline comment says the first line "beats the filename" — grounding.py:209-211 [DERIVED]
- Magic `3` duplicated: `max(3, len(s) // 2)` and `max(3, len(head) // 2)` re-hardcode the value of `_MIN_ANCHOR_LETTERS = 3` without referencing the constant — grounding.py:50,68,118 [DERIVED]
- "NEVER exceeded" budget claim vs title floor: with budget_tokens < 8 the protected title + `DOCUMENT: ` prefix can still exceed budget — grounding.py:17,46,227-228 [INFERRED]

## refactor notes
- Renaming `build_grounding_context` or `DocumentGroundingContextV1` breaks all three module importers: workers/workers/doc_parent_map_stage_worker.py, workers/workers/doc_parent_map_worker.py, shared/polymath_shared/document_profile/_small-modules (FACTS.importers) [DERIVED]
- `context_hash` feeds pMAP generation/batch identity: changing `_hash_fields` payload or `GROUNDING_CONTEXT_VERSION` intentionally invalidates old skeleton-only maps — grounding.py:15-16,189-191 [DERIVED]
- Private cross-module import `_trim_tokens` from `polymath_shared.document_profile.context` (with `clean_title`, `est_tokens`, `structure_lines`): renaming any in context.py breaks this module and forks the shared title/structure derivation — grounding.py:24-26,36-41 [DERIVED]
- `render()` literals (`DOCUMENT: `, `BY: `, `TYPE: `, `OUTLINE: `, ` · ` joiner) enter the pMAP prompt verbatim and drive `est_tokens` budget math — grounding.py:174-180,221-224 [DERIVED]
- Heading-path separator `" › "` parsed in `_outline_anchors` must match what `structure_lines` emits — grounding.py:136,140 [DERIVED]

## VERIFY
```verify
grep -Fq 'GROUNDING_CONTEXT_VERSION = "grounding-context-v1"' shared/polymath_shared/document_profile/grounding.py
grep -Fq 'DEFAULT_BUDGET_TOKENS = 90' shared/polymath_shared/document_profile/grounding.py
grep -Fq '_MAX_ANCHORS = 12' shared/polymath_shared/document_profile/grounding.py
grep -Fq 'def build_grounding_context(' shared/polymath_shared/document_profile/grounding.py
grep -Eq 'class DocumentGroundingContextV1' shared/polymath_shared/document_profile/grounding.py
test "$(grep -c -F 'untitled' shared/polymath_shared/document_profile/grounding.py)" -ge 2
! grep -Fq 'os.environ' shared/polymath_shared/document_profile/grounding.py
```
