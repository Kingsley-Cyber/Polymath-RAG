# unit: shared/polymath_shared/parent_summary.py
anchor: shared/polymath_shared/parent_summary.py:1-176

## purpose
Composes the SUMMARY-VOCABULARY-LAYER S2 parent summary for one parent chunk: settled facts + durable entities + scientific concepts folded into a stable envelope; provenance carried as `derived_from` = child chunk ids — shared/polymath_shared/parent_summary.py:1-7 [DERIVED]. Pure composition, "No model, no I/O" — shared/polymath_shared/parent_summary.py:5 [DERIVED]. Sole known importer: `shared/polymath_shared/summary_runtime.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_parent_summary` | def | keyword-only `parent_id: str, parent_text: str, children: list[dict], facts: list[dict], entities: list[dict], compiled: dict | None = None` -> `dict` | shared/polymath_shared/parent_summary.py:31-107 | shared/polymath_shared/summary_runtime.py |
| `re_finditer_candidates` | def | `text: str` -> `list[str]` | shared/polymath_shared/parent_summary.py:110-176 | `build_parent_summary` (shared/polymath_shared/parent_summary.py:88) |
| `_fact_sentence` | def (private) | `fact: dict` -> `str | None` | shared/polymath_shared/parent_summary.py:22-28 | internal only (shared/polymath_shared/parent_summary.py:64) |

## contracts

**build_parent_summary**
- in: `children: [{id, text}]`; `facts: [{predicate, subject_surface, object_surface}]`; `entities: [{surface, core_type}]` durable only — shared/polymath_shared/parent_summary.py:34-35 [DERIVED]
- in: `compiled` (SUMMARY-COMPILER-V1) = `{summary_id, plain_summary, relations[{text,...}], keywords}`; "when present it IS the summary (one compiler, no second head/concept scan)" — shared/polymath_shared/parent_summary.py:36-39 [DERIVED]
- pre: compiled branch taken only if `compiled and (compiled.get("plain_summary") or compiled.get("relations"))` — shared/polymath_shared/parent_summary.py:40 [DERIVED]
- out: envelope from `build_envelope(derived_from=[c["id"] for c in children], payload=payload)` in both branches — shared/polymath_shared/parent_summary.py:59, 105-107 [DERIVED]
- out (compiled payload): `summary_type="parent"`, `parent_id`, `entities`, `concepts` = `compiled["keywords"][:10]`, `summary`, `fact_count=len(rel_texts)`, `fact_sentences=rel_texts`, `compiled_from=summary_id`, `variant = compiled.get("variant") or "deterministic"` — shared/polymath_shared/parent_summary.py:48-58 [DERIVED]
- out (deterministic payload): `summary_type`, `parent_id`, `entities`, `concepts`, `summary`, `fact_count=len(sentences)` only — no `fact_sentences`/`compiled_from`/`variant` — shared/polymath_shared/parent_summary.py:97-104 [DERIVED]
- post: summary fallback chain = deduped fact sentences -> 180-char whitespace-normalized `parent_text` head (with `"…"`) -> `""` — shared/polymath_shared/parent_summary.py:61-77 [DERIVED]

**re_finditer_candidates**
- in: one child text string — shared/polymath_shared/parent_summary.py:110 [DERIVED]
- out: named-concept surfaces; start at capitalized token, extend via capitalized tokens and connectors, 5-word cap, sentence punctuation breaks chains, hyphenated lowercase terms scanned separately — shared/polymath_shared/parent_summary.py:111-115, 137, 139, 168 [DERIVED]
- post: leading articles `"the"/"a"/"an"` stripped from chain starts — shared/polymath_shared/parent_summary.py:152-160 [DERIVED]
- post: emitted only if `len(words) >= 2 or (w.isupper() and len(w) >= 3)` and `named_concept_evidence(surface)` — shared/polymath_shared/parent_summary.py:162-165 [DERIVED]

**_fact_sentence**
- in: fact with `subject_surface`, `object_surface`, `predicate` — shared/polymath_shared/parent_summary.py:23-25 [DERIVED]
- out: `f"{subj} {rel} {obj}."`; `None` if any of subj/obj/rel empty; `rel` looked up in `RELATION_PHRASES` by predicate with default `""` — shared/polymath_shared/parent_summary.py:25-28 [DERIVED]

## effect surface
- Postgres tables: none read, none written (FACTS tables_read/tables_written empty; "No model, no I/O" — shared/polymath_shared/parent_summary.py:5) [DERIVED]
- Qdrant / files / network / subprocess / env flags: none; only function-local `import re` — shared/polymath_shared/parent_summary.py:116 [DERIVED]
- Downstream code touched: `scientific_concept.named_concept_evidence` (:10-12), `summary_layer.build_envelope` (:13), `summary_compiler.RELATION_PHRASES` (:15) — shared/polymath_shared/parent_summary.py:10-15 [DERIVED]

## invariants
INVARIANT: `len(fact_sentences) <= MAX_SUMMARY_FACTS = 4` (slice in compiled branch, break in deterministic branch) — shared/polymath_shared/parent_summary.py:17, 43, 68 [DERIVED]
  fails-if: summary overstates settled facts; joined summary grows past budget
INVARIANT: `len(entities) <= MAX_ENTITIES = 10` and excludes `admission_class == "MENTION_ONLY"` — shared/polymath_shared/parent_summary.py:18, 44-47, 79-82 [DERIVED]
  fails-if: mention-only noise surfaces leak into the routing summary
INVARIANT: `len(concepts) <= MAX_CONCEPTS = 10` in both branches — shared/polymath_shared/parent_summary.py:19, 52, 93-95 [DERIVED]
  fails-if: concept list unbounded downstream of this unit
INVARIANT: `derived_from == [c["id"] for c in children]` in both branches — shared/polymath_shared/parent_summary.py:59, 106 [DERIVED]
  fails-if: parent-summary -> child-chunk provenance link breaks
INVARIANT: entity surfaces deduped and ordered via `sorted({...})` in both branches — shared/polymath_shared/parent_summary.py:44, 79 [DERIVED]
  fails-if: duplicate entities / unstable ordering between runs
INVARIANT: fact sentences deduped case-insensitively before the cap — shared/polymath_shared/parent_summary.py:65-66 [DERIVED]
  fails-if: duplicate sentences consume the 4-fact budget
INVARIANT: compiled branch reads concepts only from `compiled["keywords"]`, never scans child text — shared/polymath_shared/parent_summary.py:36-39, 52 [DERIVED]
  fails-if: two competing concept heads yield different summaries for the same compiled card

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env; "No model, no I/O" — shared/polymath_shared/parent_summary.py:5; sorted entity ordering — shared/polymath_shared/parent_summary.py:44, 79) [DERIVED]
idempotency: SAFE (pure function building and returning a dict; no writes anywhere in 31-176) — shared/polymath_shared/parent_summary.py:31-107 [DERIVED]

## failure behaviour
- No exception handlers in the module (entire source 1-176); nothing is swallowed — shared/polymath_shared/parent_summary.py:1-176 [DERIVED]
- `_fact_sentence` returns `None` on missing subject/object/relation; caller silently skips that fact — shared/polymath_shared/parent_summary.py:26-27, 63-67 [DERIVED]
- Graceful degradation: no usable facts -> 180-char parent-text head -> empty string `""` — shared/polymath_shared/parent_summary.py:71-77 [DERIVED]
- `compiled` lacking both `plain_summary` and `relations` falls through to the deterministic branch — shared/polymath_shared/parent_summary.py:40 [DERIVED]
- Child dicts indexed with `c["id"]` (not `.get`): a child missing `"id"` raises KeyError to the caller — shared/polymath_shared/parent_summary.py:59, 106 [INFERRED: direct subscript is visible; KeyError is Python semantics]

## dumb-code flags
- Docstring lists connectors `of/in/the/for/and` but `connectors = {"of", "in", "the", "for"}` omits `"and"` — shared/polymath_shared/parent_summary.py:113 vs 121 [DERIVED]
- Dead local: `is_acronym = w.isupper() and len(w) >= 2 and w[-1].isdigit() is False` computed, never read — shared/polymath_shared/parent_summary.py:161 [DERIVED]
- Duplicated durable-entity filter (identical `MENTION_ONLY` logic) in both branches — shared/polymath_shared/parent_summary.py:44-47 vs 79-82 [DERIVED]
- Magic word list `("attention", "search", "training", "learning")` admits any lowercase hyphen compound containing one part — shared/polymath_shared/parent_summary.py:170-172 [DERIVED]
- Magic numbers: word caps `5` (:139) and `4` (:143), acronym lengths `2` (:161) and `3` (:162), head truncation `180` (:74), lookahead `j + 2 < n` (:143) — shared/polymath_shared/parent_summary.py:139, 143, 161-162, 174 [DERIVED]
- Payload schema diverges between branches: deterministic payload lacks `fact_sentences`, `compiled_from`, `variant` — shared/polymath_shared/parent_summary.py:48-58 vs 97-104 [DERIVED]
- Function-local `import re` although the module already has top-level imports — shared/polymath_shared/parent_summary.py:116 [DERIVED]
- Redundant guard `len(words) > 0` in the article-strip while: `words` starts non-empty and the body breaks on empty — shared/polymath_shared/parent_summary.py:154, 158-159 [INFERRED: control flow makes the clause unreachable-false]

## refactor notes
- Sole known importer is `shared/polymath_shared/summary_runtime.py` (FACTS.importers); renaming/removing payload keys at :48-58 or :97-104 breaks it.
- Compiled-branch contract "one compiler, no second head/concept scan" (:36-39): reintroducing a concept scan there creates two competing summary heads.
- Predicate vocabulary lives in `polymath_shared.summary_compiler.RELATION_PHRASES` (:15, :25): an unknown predicate yields rel `""` and the fact is silently dropped.
- Every candidate is gated by `named_concept_evidence` from `polymath_shared.scientific_concept` (:10-12, :164, :170): changing that function changes concept extraction with zero diff here.
- Envelope shape and `derived_from` ordering come from `summary_layer.build_envelope` and the children list order (:13, :59, :105-107).
- `re_finditer_candidates` is public and called at :88; moving/renaming requires updating that call site and any external caller.

## VERIFY
```verify
grep -Fq 'MAX_SUMMARY_FACTS = 4' shared/polymath_shared/parent_summary.py
grep -Fq 'connectors = {"of", "in", "the", "for"}' shared/polymath_shared/parent_summary.py
grep -Fq 'is_acronym = w.isupper() and len(w) >= 2 and w[-1].isdigit() is False' shared/polymath_shared/parent_summary.py
grep -Fq 'compiled.get("variant") or "deterministic"' shared/polymath_shared/parent_summary.py
grep -Fq '[:180]' shared/polymath_shared/parent_summary.py
! grep -Fq 'import random' shared/polymath_shared/parent_summary.py
test "$(grep -c -F 'MENTION_ONLY' shared/polymath_shared/parent_summary.py)" -ge 2
```
