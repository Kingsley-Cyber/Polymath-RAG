# unit: shared/polymath_shared/document_profile/map_compiler.py
anchor: shared/polymath_shared/document_profile/map_compiler.py:1-314

## purpose
Deterministic parent-map compiler in `shared/`: parses the LLM parent-map DSL — one line per parent, `MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>` — into frozen `CompiledMap` records keyed to real parents via the S1 `SkeletonManifest`. Tolerant on format, strict on identity: harmless drift accepted, unknown/ambiguous/invented alias rejected. No I/O, no model. — shared/polymath_shared/document_profile/map_compiler.py:1-30,157 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `compile_maps` | function | `(raw_response: str, manifest: SkeletonManifest, *, contract: str = MAP_COMPILER_VERSION) -> MapCompileResult` | map_compiler.py:201-314 | workers/workers/doc_parent_map_stage_worker.py, workers/workers/doc_parent_map_worker.py, shared/polymath_shared/document_profile/parent_map_projection.py |
| `MapCompileResult` | class | frozen dataclass; fields `contract, maps, missing_aliases, unknown_aliases, duplicate_aliases, rejected, raw_response_hash, map_completeness_hash`; props `expected_count`, `complete`; `to_dict() -> dict` | map_compiler.py:125-159 | same importers |
| `CompiledMap` | class | frozen dataclass; fields `alias, parent_id, routing_signature, semantic_hooks, exact_identifiers, map_hash, quality_flags=()`; `to_dict() -> dict` | map_compiler.py:96-114 | same importers |
| `RejectedLine` | class | frozen dataclass; fields `raw, reason, alias=None` | map_compiler.py:118-121 | same importers |
| `normalize_search_text` | function | `(text: str) -> str` | map_compiler.py:71-79 | — |
| `MAP_COMPILER_VERSION` | constant | `"map-compiler-v1"` | map_compiler.py:42 | — |
| `MAX_HOOKS` | constant | `3` | map_compiler.py:44 | — |

Internal helpers (underscore): `_sha256` :67-68, `_alias_key` :82-85, `_is_generic_signature` :88-92, `_resolve_alias` :162-176, `_hooks` :179-198.

## contracts

**`compile_maps`** (map_compiler.py:201-314)
- in: `raw_response` raw model text (empty/None coerced via `raw_response or ""` at :231, :313); `manifest: SkeletonManifest` supplying `manifest.skeletons` (alias + identifiers) and `manifest.alias_to_parent` (:214-218); keyword `contract` defaults to `MAP_COMPILER_VERSION` (:205-206).
- pre: manifest exposes `manifest_hash` used in the completeness hash (:299); expected aliases match `_ALIAS_RE = re.compile(r"^P?0*([0-9]+)$")` (:64, :220-224).
- post: only lines matching `_MAP_LINE_RE = re.compile(r"^\s*MAP\s*\|", re.IGNORECASE)` (:63, :234) with ≥3 `|`-fields (:237-239), an alias resolving to exactly one expected alias (:253-257), and a non-empty normalized signature (:259-261) become maps. First valid record wins per alias; duplicates receipted (:262-265). `missing_aliases = sorted(expected_aliases - set(maps))` (:294). Maps ordered by alias (:293).
- post: deterministic — same `(raw_response, manifest)` ⇒ same result (:209-210).
- `map_hash = _sha256("\x1f".join([contract, alias, parent_id, signature, "\x1e".join(hooks), "\x1e".join(identifiers)]))` (:271-282).
- `map_completeness_hash = _sha256("\x1d".join(["manifest:"+manifest_hash, "expected:"+sorted aliases, "valid:"+`alias\x1cmap_hash` pairs, "missing:"+missing]))` (:295-304) — binds source manifest, expected set, valid pairs AND missing set (:133-137).

**`normalize_search_text`** (map_compiler.py:71-79)
- NFC-normalize, fold `_UNICODE_FOLD` chars, strip `"'\`*_ ` and whitespace-collapse; case preserved; display + embed text only, never an identity key, never applied to exact identifiers (:72-76, :59-61).

**`_hooks`** (map_compiler.py:179-198)
- Split on `";"`, normalize each, drop empties and `_GENERIC` words, dedup preserving order, cap at `MAX_HOOKS` = 3; returns `(hooks, flags)` with `generic_hooks_dropped:N` and/or `hooks_count:N` (:194-198).

**`_resolve_alias`** (map_compiler.py:162-176)
- `(raw_alias, expected_by_number) -> (alias|None, 'ok'|'unknown'|'ambiguous')`; zero-padding cosmetic (`P17` / `p0017`), multiple expected aliases with same number ⇒ `'ambiguous'` (:164-176).

## effect surface
None. `tables_read: []`, `tables_written: []` (FACTS); "no I/O, no model" (:157). Imports only `hashlib`, `re`, `unicodedata`, `dataclasses`, `typing`, and `polymath_shared.document_profile.parent_skeleton.SkeletonManifest` (:33-39). No files, network, subprocess, or env flags.

## invariants

INVARIANT: `len(semantic_hooks) <= MAX_HOOKS (3)` — map_compiler.py:193-197 [DERIVED]
  fails-if: hook lists exceed the 3-slot schema promised to the prompt DSL (:9).
INVARIANT: `expected_count == len(maps) + len(missing_aliases)` — map_compiler.py:140-141 [DERIVED]
  fails-if: 73/90-style partial accounting breaks; repair set size disagrees with persisted maps.
INVARIANT: `map_completeness_hash` includes the missing set, so two different 73/90 partials never collide and neither matches a 90/90 run — map_compiler.py:133-137,295-304 [DERIVED]
  fails-if: partial runs treated as complete/duplicate; repair skips documents.
INVARIANT: `raw_response_hash != map_completeness_hash` by design (raw text hashed first, normalization applied after) — map_compiler.py:26-28,313 [DERIVED]
  fails-if: re-normalizing before hashing would make completeness hash depend on fold policy, invalidating stored hashes.
INVARIANT: `exact_identifiers == skeleton identifiers verbatim`, independent of model hooks — map_compiler.py:21-23,270 [DERIVED]
  fails-if: identifiers routed through `_UNICODE_FOLD` would corrupt identity keys (:59-61).
INVARIANT: separator tolerance applies only when `len(tail) > 1 and ";" not in raw_hooks` — map_compiler.py:250-251 [DERIVED]
  fails-if: a ';'-separated tail byte-identical to before would silently change; hook count schema drifts.
INVARIANT: unknown/ambiguous alias never yields a map (rejected, not attached) — map_compiler.py:165-176,253-257 [DERIVED]
  fails-if: a map attaches to the wrong parent.
INVARIANT: `complete == (not missing_aliases)` — map_compiler.py:144-145 [DERIVED]
  fails-if: completeness gate passes with unrepaired aliases.

## determinism & idempotency
determinism: DETERMINISTIC (pure computation: `hashlib`/`re`/`unicodedata` only, map_compiler.py:33-39; same inputs ⇒ same result, :209-210)
idempotency: SAFE (no side effects, no I/O — :157; errors returned as data, never swallowed state)

## failure behaviour
No `raise` in the module; only `assert alias is not None` (:258), unreachable when `status == "ok"` (:253-258). All failures are returned as data:

| reason / flag | trigger | anchor |
|---|---|---|
| `not_a_map_line` | line fails `_MAP_LINE_RE` | :234 |
| `malformed_too_few_fields` | `len(parts) < 3` | :237-239 |
| `alias_unknown` / `alias_ambiguous` | `_resolve_alias` status | :253-257 |
| `empty_signature` | normalized signature empty | :259-261 |
| `duplicate_alias` | alias already in `maps`; first valid wins | :262-265 |
| `generic_hooks_dropped:N` | hooks in `_GENERIC` dropped | :189-196 |
| `hooks_count:N` | fewer than 3 hooks survive | :197-198 |
| `generic_signature` | `_GENERIC_SIGNATURE_RE` or all-`_GENERIC` words | :88-92,267-269 |

Caller sees a partial `MapCompileResult` with `missing_aliases` as the exact repair set; valid lines are never re-run (:19-20, :294). `RejectedLine.raw` truncated to 200 chars (:234).

## dumb-code flags
- Comment names only U+2011 and U+00A0; `_UNICODE_FOLD = {"\u00a0": " ", "\u2010": "-", "\u2011": "-"}` has three keys — comment under-documents U+2010. map_compiler.py:58-61 [DERIVED]
- Tail round-trip: `raw_hooks = "|".join(tail)` then conditionally `";".join(tail)` — join then rejoin. map_compiler.py:243-252 [DERIVED]
- Magic separators unlabeled: `"\x1f"` :272, `"\x1e"` :429-430, `"\x1d"` :446-452, `"\x1c"` :301. [DERIVED]
- Repeated truncation literal `200` in every `RejectedLine(raw=line.strip()[:200], ...)`. map_compiler.py:234,239,256,261,265 [DERIVED]
- `MAX_HOOKS = 3` duplicated as DSL shape `hook1;hook2;hook3` (:9) and prose "THREE hooks" (:247). [DERIVED]
- `assert alias is not None` used for type narrowing — stripped under `python -O`. map_compiler.py:258 [DERIVED]
- `_alias_key` mirrors the profile compiler's tag normalization in a second copy. map_compiler.py:82-85 [INFERRED: docstring says "Mirror the profile compiler's tag normalization", so the policy exists in two modules]

## refactor notes
- Three importers (`parent_map_projection.py`, `doc_parent_map_stage_worker.py`, `doc_parent_map_worker.py`, FACTS.importers) consume `compile_maps`/`MapCompileResult`; changing `to_dict` keys (:147-159) is a cross-worker schema break.
- `map_hash` and `map_completeness_hash` recipes include the `contract` string; version via `MAP_COMPILER_VERSION` bump, not by editing the join recipe (:41-42, :271-282, :295-304).
- `normalize_search_text` must stay in sync with the `canonicalizer`/`identity` NFC contract (:24-26); `_alias_key` must stay in sync with the profile compiler (:82-85).
- `MAX_HOOKS` is tied to the MAP DSL prompt shape (3 hooks, :9) and the `hooks_count:N` flag semantics (:196-198).
- `RejectedLine` receipts and `missing_aliases` implement the partial-output-is-useful rule (§18.4) — successful lines must remain never-re-run (:19-20).

## VERIFY
```verify
grep -Fq 'MAP_COMPILER_VERSION = "map-compiler-v1"' shared/polymath_shared/document_profile/map_compiler.py
grep -Fq 'MAX_HOOKS = 3' shared/polymath_shared/document_profile/map_compiler.py
grep -Fq 'r"^P?0*([0-9]+)$"' shared/polymath_shared/document_profile/map_compiler.py
grep -Fq 'if len(tail) > 1 and ";" not in raw_hooks:' shared/polymath_shared/document_profile/map_compiler.py
grep -Fq '"\x1f".join(' shared/polymath_shared/document_profile/map_compiler.py
test "$(grep -c -F 'map_completeness_hash' shared/polymath_shared/document_profile/map_compiler.py)" -ge 4
! grep -Fq 'open(' shared/polymath_shared/document_profile/map_compiler.py
```
