# unit: shared/polymath_shared/document_profile/parent_skeleton.py
anchor: shared/polymath_shared/document_profile/parent_skeleton.py:1-482

## purpose
Deterministic, CPU-only skeleton builder for the parent-map LLM: one `ParentSkeleton` per retrieval-eligible parent (alias, heading_path, lead_excerpt, salient_excerpt, key_terms, identifiers, hashes), plus accounted exclusions for noisy parents (shared/polymath_shared/document_profile/parent_skeleton.py:1-26 [DERIVED]). Pure policy module in `shared/`: "no I/O, no model, no network" — only `re`, `collections.Counter`, `math.log` (shared/polymath_shared/document_profile/parent_skeleton.py:6-8 [DERIVED]). Consumed by the document_profile map pipeline and both parent-map workers (see importers note).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| build_parent_skeletons | def | (parents: Sequence[Mapping[str, Any]]) -> SkeletonManifest | shared/polymath_shared/document_profile/parent_skeleton.py:401-481 | file-level importers (note below) |
| ParentSkeleton | class | frozen dataclass; fields incl. alias, heading_path, lead_excerpt, salient_excerpt, key_terms, identifiers, text_hash, skeleton_hash; `to_dict()` | shared/polymath_shared/document_profile/parent_skeleton.py:271-304 | file-level importers |
| SkeletonManifest | class | frozen dataclass; builder_version, skeletons, excluded, alias_to_parent, manifest_hash; `eligible_count`, `to_dict()` | shared/polymath_shared/document_profile/parent_skeleton.py:317-338 | file-level importers |
| ExcludedParent | class | frozen dataclass; parent_id, region_role, reason | shared/polymath_shared/document_profile/parent_skeleton.py:308-313 | file-level importers |
| extract_identifiers | def | (text: str) -> list[str] | shared/polymath_shared/document_profile/parent_skeleton.py:109-131 | — |
| select_key_terms | def | (tokens, heading_tokens, identifier_tokens, df: Counter, n_docs) -> list[str] | shared/polymath_shared/document_profile/parent_skeleton.py:165-188 | — |
| select_salient_excerpt | def | (text, heading_tokens, key_terms, identifiers) -> str | shared/polymath_shared/document_profile/parent_skeleton.py:218-250 | — |
| select_lead_excerpt | def | (text: str) -> str | shared/polymath_shared/document_profile/parent_skeleton.py:253-267 | — |
| document_frequency | def | (parent_token_sets) -> Counter | shared/polymath_shared/document_profile/parent_skeleton.py:151-156 | — |
| idf | def | (n_docs: int, df: int) -> float | shared/polymath_shared/document_profile/parent_skeleton.py:159-162 | — |
| normalize_whitespace | def | (text: str) -> str | shared/polymath_shared/document_profile/parent_skeleton.py:94-98 | — |
| SKELETON_BUILDER_VERSION | const | `"parent-skeleton-v2"` | shared/polymath_shared/document_profile/parent_skeleton.py:42 | — |
| STOP_TERMS | const | frozenset of split words | shared/polymath_shared/document_profile/parent_skeleton.py:59-72 | — |

File-level importers (FACTS.importers; per-symbol use unknown): `document_profile/{_small-modules, fingerprint.py, giant_profile.py, map_batches.py, map_compiler.py, parent_map_projection.py, profile_coverage.py}`, `workers/workers/doc_parent_map_stage_worker.py`, `workers/workers/doc_parent_map_worker.py` [DERIVED].

## contracts

**build_parent_skeletons(parents) -> SkeletonManifest** — shared/polymath_shared/document_profile/parent_skeleton.py:401-481
- in: parent mappings with `text`, `heading_path`, `region_role`, an identity field (`chunk_id`/`parent_id`), optional `char_start`/`source_position`/`chunk_index`; any order :404-409 [DERIVED]
- pre: every parent has non-empty `chunk_id` or `parent_id`, else `ValueError` :355-362 [DERIVED]
- post: noisy-role parents -> `excluded` with `reason=role`; empty-text -> `reason="empty"` :422-427 [DERIVED]
- post: eligible sorted by `(source_position, parent_id)` before aliasing, so caller order cannot shift aliases :414-430 [DERIVED]
- post: `alias = f"P{ordinal + 1:0{width}d}"` with `width = max(ALIAS_MIN_WIDTH, len(str(n_docs)))` = `max(4, len(str(n_docs)))` :439,443 [DERIVED]
- post: `alias_to_parent[alias] = parent_id` for every skeleton :470 [DERIVED]
- post: `manifest_hash` = sha256 over `alias \x1c parent_id \x1c skeleton_hash` triples joined with `\x1d` :472-474 [DERIVED]

**extract_identifiers(text) -> list[str]** — shared/polymath_shared/document_profile/parent_skeleton.py:109-131
- out: canonical source form preserved, first-seen order, deduplicated :110-112 [DERIVED]
- pre: patterns applied most-specific-first; each match blanked to same-length spaces before the next pattern runs, so substrings of claimed ids are never re-extracted :113-117, :78-87 [DERIVED]
- all-caps common words rejected: `token.isalpha() and token.lower() in STOP_TERMS` :126-128 [DERIVED]

**select_key_terms(...) -> list[str]** — shared/polymath_shared/document_profile/parent_skeleton.py:165-188
- out: `ranked[:KEY_TERMS_MAX]` (at most 5); score = `count * idf` + `2.0 * weight` heading overlap + `3.0 * weight` identifier bonus; tie-break `(-score, term asc)` :179-188 [DERIVED]
- note: `KEY_TERMS_MIN` is never applied here — see dumb-code flags [DERIVED]

**select_salient_excerpt(...) -> str** — shared/polymath_shared/document_profile/parent_skeleton.py:218-250
- out: best sentence by `len(tokens & key_set) + 0.5 * len(tokens & heading_tokens)` + `1.0` if any identifier substring present; min `MIN_SENTENCE_WORDS` (4) words, boilerplate rejected; earliest position wins ties; truncated to `SALIENT_EXCERPT_MAX_WORDS` (30) :233-250 [DERIVED]
- fallback: no qualifying sentence -> leading slice of normalized text, still truncated :246-250 [DERIVED]

**select_lead_excerpt(text) -> str** — shared/polymath_shared/document_profile/parent_skeleton.py:253-267
- out: first `LEAD_EXCERPT_SENTENCES` (2) substantive sentences joined, truncated to `LEAD_EXCERPT_MAX_WORDS` (50); fallback `lead or normalized` :262-267 [DERIVED]
- invoked only when `heading_path` is empty: `lead = select_lead_excerpt(text) if not heading_path else ""` :453 [DERIVED]

**idf(n_docs, df) -> float** — shared/polymath_shared/document_profile/parent_skeleton.py:159-162
- out: `math.log((n_docs + 1) / (df + 1)) + 1.0`; never divides by 0, never negative :160-162 [DERIVED]

**_identity(parent) -> str** (private but caller-facing contract) — shared/polymath_shared/document_profile/parent_skeleton.py:349-362
- tries `"chunk_id"` then `"parent_id"`; raises `ValueError` if both absent; `chunk_index` explicitly rejected as identity :355-362 [DERIVED]

## effect surface
- Postgres: none — `tables_read: []`, `tables_written: []` (FACTS) [DERIVED]
- Qdrant / files / network / subprocess: none — module asserts "no I/O, no model, no network" :6-8; imports limited to `hashlib`, `math`, `re`, `collections.Counter`, `dataclasses`, `typing`, `polymath_shared.document_region` :30-37 [DERIVED]
- Env flags: none read [DERIVED, no `os`/`environ` anywhere in SOURCE]
- Input shape consumed: in-memory parent mappings (keys above) :404-409 [DERIVED]

## invariants
INVARIANT: idf(n_docs, df) == math.log((n_docs + 1) / (df + 1)) + 1.0 for all df >= 0 — shared/polymath_shared/document_profile/parent_skeleton.py:162 [DERIVED]
  fails-if: a zero or negative idf would invert key-term ranking (promise at :160-161 broken)
INVARIANT: len(key_terms) <= KEY_TERMS_MAX (5) — shared/polymath_shared/document_profile/parent_skeleton.py:187-188 [DERIVED]
  fails-if: prompt density per parent grows without bound; skeleton_hash churns
INVARIANT: word_count(salient_excerpt) <= SALIENT_EXCERPT_MAX_WORDS (30) — shared/polymath_shared/document_profile/parent_skeleton.py:250,45 [DERIVED]
  fails-if: per-parent prompt cost blows past the measured density budget
INVARIANT: word_count(lead_excerpt) <= LEAD_EXCERPT_MAX_WORDS (50) — shared/polymath_shared/document_profile/parent_skeleton.py:267,50 [DERIVED]
  fails-if: headingless parents add unbounded opening text (the ~30-50 word budget at :47-48)
INVARIANT: lead_excerpt != "" only when heading_path == () — shared/polymath_shared/document_profile/parent_skeleton.py:453 [DERIVED]
  fails-if: structured parents pay double framing (heading + lead) in every prompt
INVARIANT: alias digit width == max(ALIAS_MIN_WIDTH, len(str(n_docs))) — shared/polymath_shared/document_profile/parent_skeleton.py:439,443 [DERIVED]
  fails-if: alias collisions or width churn across documents of different sizes
INVARIANT: eligible sort key == (source_position, parent_id) — shared/polymath_shared/document_profile/parent_skeleton.py:430 [DERIVED]
  fails-if: alias assignment becomes caller-order-dependent; manifest_hash unstable across calls
INVARIANT: skeleton_hash payload excludes alias/ordinal/source_position and always includes SKELETON_BUILDER_VERSION — shared/polymath_shared/document_profile/parent_skeleton.py:383-398 [DERIVED]
  fails-if: re-aliasing or reordering churns hashes and triggers spurious rebuilds
INVARIANT: every input parent lands in exactly one of skeletons or excluded — shared/polymath_shared/document_profile/parent_skeleton.py:417-429 [INFERRED — single pass with continue; both branches append exclusively]
  fails-if: silent parent loss breaks the §20.3 accounting guarantee (exclusions counted, none dropped)

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of input text; no clock/random/uuid/network/db/env anywhere in SOURCE (imports at :30-37; policy statement :6-8) [DERIVED]
idempotency: SAFE — no side effects (`tables_written: []` in FACTS); same `parents` input reproduces identical `manifest_hash` :472-474 [DERIVED]

## failure behaviour
- No try/except in SOURCE; nothing is swallowed [DERIVED].
- `ValueError` from `_identity` when a parent lacks `chunk_id`/`parent_id` — "raised loudly rather than mis-keyed" :359-362, :353-354 [DERIVED]. Caller (workers) sees an exception, not a mis-keyed skeleton.
- Soft fallbacks the caller sees as values, not errors: salient excerpt falls back to the leading bounded slice when no sentence qualifies :246-249; lead excerpt falls back to whole normalized text when no substantive sentence exists :267 [DERIVED].

## dumb-code flags
- `KEY_TERMS_MIN = 3` defined at :51 but never referenced; only `KEY_TERMS_MAX` is enforced (:187-188) while both the module docstring (:16, "key_terms[] 3-5") and `select_key_terms` docstring (:172, "3-5 high-information terms") promise a minimum of 3 [DERIVED].
- `STOP_TERMS` duplicates: `upon` (:62, :68), `above` (:62, :67), `below` (:62, :67), `also` (:67, :68) — harmless in a frozenset but a copy-paste smell :61-70 [DERIVED].
- Unnamed scoring magic numbers: `2.0` heading bonus and `3.0` identifier bonus (:183-185), `0.5` heading overlap and `1.0` identifier hit in salient selection (:239-241) — no named constants unlike every other bound :44-55 [DERIVED].
- `_source_position` accepts digit-string values via `val.isdigit()` (:370-371) while `_identity` requires non-empty strings — two different coercion policies in adjacent helpers :365-372 vs :355-358 [DERIVED].

## refactor notes
- Bumping `SKELETON_BUILDER_VERSION` (`"parent-skeleton-v2"`, :42) invalidates every `skeleton_hash` (:388) and `manifest_hash` (:472-474); blast radius = all 9 file-level importers (FACTS.importers), including `map_compiler.py` and both `doc_parent_map` workers — plan §32 tracks it independently of prompt/compiler versions (:39-41) [DERIVED].
- The alias scheme `f"P{ordinal + 1:0{width}d}"` + `alias_to_parent` (:443, :470) is the only prompt↔Postgres bridge (real `parent_id` never enters the prompt, :272-275); changing format or width breaks every consumer that resolves aliases [DERIVED].
- `skeleton_hash` deliberately excludes alias/ordinal/source_position (:383-386); adding positional fields reintroduces re-aliasing churn [DERIVED].
- `_IDENTIFIER_PATTERNS` order (most-specific first, :78-87) plus same-length blanking (:113-117) is what prevents substring re-extraction (`0217` inside `CVE-2026-0217`); reordering patterns changes extraction output [DERIVED].
- `_identity` key precedence `"chunk_id"` then `"parent_id"` (:355-358) and the loud `ValueError` are caller contracts; workers must keep sending those keys [DERIVED].
- `STOP_TERMS` is "Intentionally small and frozen" (:57-58); growing it shifts `key_terms` and therefore every `skeleton_hash` [DERIVED].
- `lead_excerpt` emission tied to empty `heading_path` (:453) is the v2 change (:41); consumers read `lead_excerpt` only for headingless parents (:273-274, :46-48) [DERIVED].

## VERIFY
```verify
grep -Fq 'SKELETON_BUILDER_VERSION = "parent-skeleton-v2"' shared/polymath_shared/document_profile/parent_skeleton.py
grep -Fq 'return math.log((n_docs + 1) / (df + 1)) + 1.0' shared/polymath_shared/document_profile/parent_skeleton.py
grep -Fq 'alias = f"P{ordinal + 1:0{width}d}"' shared/polymath_shared/document_profile/parent_skeleton.py
grep -Fq 'lead = select_lead_excerpt(text) if not heading_path else ""' shared/polymath_shared/document_profile/parent_skeleton.py
grep -Fq 'raise ValueError(' shared/polymath_shared/document_profile/parent_skeleton.py
test "$(grep -c -F 'KEY_TERMS_MAX' shared/polymath_shared/document_profile/parent_skeleton.py)" -ge 2
! grep -Eq 'import (requests|urllib|socket|subprocess)' shared/polymath_shared/document_profile/parent_skeleton.py
```
