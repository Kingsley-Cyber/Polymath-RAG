# unit: shared/polymath_shared/document_profile/compiler.py
anchor: shared/polymath_shared/document_profile/compiler.py:1-1046

## purpose
Tolerant 4-stage compiler for tagged-line LLM document profiles: `normalize` (fence/alias/colon repair) → `parse` (tolerant tag parser) → `validate` (dedupe, repair, grounding, caps) → score/emit (payload for embedding) — shared/polymath_shared/document_profile/compiler.py:299, 476, 689, 894 [DERIVED]. Design rule: content correctness beats formatting; cardinality targets are soft, "Only a missing semantic core causes compilation failure" — shared/polymath_shared/document_profile/compiler.py:23-27 [DERIVED]. Only known importer: `workers/workers/doc_profile_worker.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| compile_llm_output | def | (raw, doc_id="", source_text="", grounding_mode="warn") -> CompileResult | shared/polymath_shared/document_profile/compiler.py:961-995 | doc_profile_worker (module import) |
| index_document | def | (raw, doc_id, source_text="", min_quality=0.70, grounding_mode="warn") -> dict \| None | shared/polymath_shared/document_profile/compiler.py:998-1020 | doc_profile_worker (module import) |
| index_document_with_result | def | (raw, doc_id, source_text="", min_quality=0.70, grounding_mode="warn") -> tuple[dict \| None, CompileResult] | shared/polymath_shared/document_profile/compiler.py:1023-1045 | doc_profile_worker (module import) |
| CompileResult | class | fields: record, issues, truncated, ok, quality, format_quality, coverage_quality; method report() -> str | shared/polymath_shared/document_profile/compiler.py:185-215 | retry logic per :1031-1033 |
| Record | class | 3 text fields + 14 list fields (slots dataclass) | shared/polymath_shared/document_profile/compiler.py:162-181 | — |
| Issue | class | (severity, code, message, line_no=-1) | shared/polymath_shared/document_profile/compiler.py:154-158 | — |
| emit | def | (rec, doc_id) -> dict | shared/polymath_shared/document_profile/compiler.py:894-954 | — |
| profile_valid | def | (rec) -> tuple[bool, list[str]] | shared/polymath_shared/document_profile/compiler.py:881-891 | — |
| semantic_artifact | def | (rec) -> dict | shared/polymath_shared/document_profile/compiler.py:865-878 | — |
| validate | def | (rec, issues, source_text="", grounding_mode="warn") -> None | shared/polymath_shared/document_profile/compiler.py:689-813 | — |

FACTS.importers lists only the worker file; which symbols it calls is not itemized.

## contracts

**compile_llm_output** — shared/polymath_shared/document_profile/compiler.py:961-995
- pre: `grounding_mode in {"off","warn","drop"}` else `ValueError` — :975-976 [DERIVED]
- in: raw tagged-line text (ONE/SUMMARY/TOPIC/TERM/Q/SEARCH/THEORY/CONCEPT/SEEALSO/END, alias table :65-147) [DERIVED]
- out: `ok = not any(issue.severity == "error")` — :983 [DERIVED]; `quality = 0.75*format + 0.25*coverage` clamped [0.0,1.0] — :858-862 [DERIVED]
- post: Record deduped, capped at HARD_MAX, questions suffixed "?", searches stripped trailing "?" — :698-751 [DERIVED]

**index_document / index_document_with_result** — shared/polymath_shared/document_profile/compiler.py:998-1020, 1023-1045
- post: payload = `emit(record, doc_id)` iff `result.ok and result.quality >= min_quality` (default `0.70`), else None — :1018-1020, 1042-1044 [DERIVED]

**emit** — shared/polymath_shared/document_profile/compiler.py:894-954
- out keys: `doc_id`, `schema_version`, legacy pooled `embed_topic`/`embed_theme`/`embed_questions`, `metadata{topics,terms,theories,concepts,seealso}`, atomic `representations{identity,theme,questions,searches,theories,concepts,seealso}`, `artifact` — :920-946 [DERIVED]
- post: `embed_search`/`embed_seealso` present only when lists non-empty — :948-952 [DERIVED]

**profile_valid** — shared/polymath_shared/document_profile/compiler.py:881-891
- valid iff semantic core (`one_liner or summary`) AND query hook (`questions or searches`); missing list returns codes `semantic_core`, `query_hook` — :887-891 [DERIVED]

**validate** — shared/polymath_shared/document_profile/compiler.py:689-813
- fatal only: `NO_SEMANTIC_CORE` (error) when both `one_liner` and `summary` empty after `_repair_core` fallbacks (DETAIL→SUMMARY, first SUMMARY sentence→ONE) — :665-686, 805-813 [DERIVED]
- grounding: skipped when `source_text` empty or mode "off"; "warn" keeps ungrounded terms with `UNGROUNDED_TERM` warn; "drop" removes them — :753-774 [DERIVED]

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty) [DERIVED]
- Qdrant/files/network/subprocess/env: none; imports only `re`, `dataclasses`, `typing` — shared/polymath_shared/document_profile/compiler.py:31-33 [DERIVED]

## invariants
- INVARIANT: quality == 0.75 * format_quality + 0.25 * coverage_quality — compiler.py:861 [DERIVED]; fails-if: acceptance gate (`min_quality=0.70`) flips at ~10 warn-severity issues (each warn costs 0.04 format, :829-831)
- INVARIANT: every TARGET_COUNTS key has a HARD_MAX entry (7 tags both dicts) — compiler.py:43-51, 55-63 [DERIVED]; fails-if: KeyError at `HARD_MAX[tag]` in :781
- INVARIANT: HARD_MAX == aim+headroom (16 or 22) > TARGET_COUNTS aim (10 or 15) for all tags — compiler.py:44-50, 56-62 [DERIVED]; fails-if: cap could bite below the prompt's requested count
- INVARIANT: vNext attrs (latent_pattern, anchor, recallq, tension, bridge, inversion, boundary) absent from TARGET_COUNTS/HARD_MAX/emit metadata+representations — compiler.py:43-51, 55-63, 920-944 [DERIVED]; fails-if: none — they are deduped (:698-699) and surfaced only in `artifact` when non-empty (:874-877)
- INVARIANT: v3.x artifact is byte-identical (vNext keys added only when present) — compiler.py:874-877 [DERIVED]; fails-if: contract drift for existing profiles
- INVARIANT: `min_quality` default 0.70 identical in both index functions — compiler.py:1003, 1027 [DERIVED]; fails-if: worker retry policy diverges from legacy one-liner
- INVARIANT: compile `ok` ignores query_hook; profile_valid requires it — compiler.py:983, 805-813 vs 887-891 [INFERRED] (validate never errors on empty Q/SEARCH) — a payload with zero questions/searches can still be emitted with `embed_questions: ""`
- INVARIANT: semantic-core coverage component = 1.0 iff both one_liner and summary, else 0.5 — compiler.py:853 [DERIVED]; fails-if: coverage score halves for DETAIL-only profiles

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env; only `re`, `dataclasses`, `typing` imported — compiler.py:31-33) [DERIVED]
idempotency: SAFE (pure text→struct transform, no writes or external state) [DERIVED]

## failure behaviour
- No try/except anywhere; failures are issue-coded, not raised. Only raised error: `ValueError("grounding_mode must be 'off', 'warn', or 'drop'")` — compiler.py:975-976 [DERIVED]
- `NO_SEMANTIC_CORE` (error) → `ok=False` → index_* return payload None — compiler.py:805-813, 1018-1020 [DERIVED]
- Unparseable lines dropped as `GARBAGE_LINE` (warn) — compiler.py:514-521; unknown tags dropped as `UNKNOWN_TAG` (warn) — compiler.py:528-537 [DERIVED]
- Missing END → `truncated=True` + `NO_END_SENTINEL` warn, content retained — compiler.py:584-593, 478 [DERIVED]
- FACTS define no `fallbacks` list; FACTS.fallbacks absent for this unit.

## dumb-code flags
- Module docstring targets are stale vs code: docstring says `TOPIC # target 4-6`, `TERM # target 4-7`, `Q # target 3-5`, `SEARCH # target 4-6`, `SEEALSO # target 1-2` — compiler.py:11-15 — but TARGET_COUNTS is TOPIC (5,10), TERM (5,10), Q (8,15), SEARCH (8,15), SEEALSO (5,10) — compiler.py:44-50; comment :40-42 records the owner 2026-09-07 change that the docstring missed [DERIVED]
- Dead value: `_target_hi` unpacked and discarded in both consumers — compiler.py:780, 845 [DERIVED]
- Duplicated severity logic: `SEVERITY` map used only for report() sort — compiler.py:149, 198 — while `_format_quality` re-branches on severity strings — compiler.py:829-832 [DERIVED]
- Magic weights `0.75`/`0.25` unnamed — compiler.py:861; penalty `0.40`/`0.04` unnamed — compiler.py:830-831 [DERIVED]
- `grounding_mode="drop"` silently behaves like "off" when `source_text` is empty (gate `if source_text and grounding_mode != "off"`) — compiler.py:755 [INFERRED] from the conjunctive gate
- Legacy `embed_*` pooled keys kept with contract only in a comment ("the projector must NOT embed these") — compiler.py:923 [DERIVED]

## refactor notes
- `workers/workers/doc_profile_worker.py` imports this module (FACTS); the two `index_*` entry points and the `CompileResult` fields driving retry (`ok`, `quality`) must not change shape — compiler.py:1031-1033 [DERIVED]
- `emit` payload keys are the downstream contract: legacy `embed_topic`/`embed_theme`/`embed_questions` (:924-926), atomic `representations` (:936-944), `artifact` (:945) — renaming breaks embedding consumers [DERIVED]
- TAG_ALIASES must stay additive: "existing profiles compile byte-identically" — compiler.py:132-135 [DERIVED]
- `_TAG_LINE` separator class includes `-`, so `LATENT-PATTERN:` would mis-split; `_LATENT_PATTERN_LABEL` pre-collapse (:246, applied :306) is coupled to that regex — changing `_TAG_LINE` (:227-229) or the alias without the other breaks vNext parsing — compiler.py:242-246 [DERIVED]
- TARGET_COUNTS, HARD_MAX, and `_LIST_ATTR` key sets must stay aligned (loops do `_LIST_ATTR[tag]`, `HARD_MAX[tag]`) — compiler.py:778-781 [DERIVED]

## VERIFY
```verify
grep -Fq 'SCHEMA_VERSION = "rag-profile-v3"' shared/polymath_shared/document_profile/compiler.py
grep -Fq 'COMPILER_VERSION = "rag-compiler-v3.1"' shared/polymath_shared/document_profile/compiler.py
test "$(grep -c -F 'min_quality: float = 0.70' shared/polymath_shared/document_profile/compiler.py)" -ge 2
grep -Eq 'score = 0\.75 \* format_quality \+ 0\.25 \* coverage_quality' shared/polymath_shared/document_profile/compiler.py
grep -Eq '"Q":\s+\(8, 15\)' shared/polymath_shared/document_profile/compiler.py
grep -Fq 'NO_SEMANTIC_CORE' shared/polymath_shared/document_profile/compiler.py
grep -Fq 'target_lo, _target_hi = target' shared/polymath_shared/document_profile/compiler.py
! grep -Fq 'import random' shared/polymath_shared/document_profile/compiler.py
```
