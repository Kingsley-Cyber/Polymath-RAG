# unit: shared/polymath_shared/concept_inventory.py
anchor: shared/polymath_shared/concept_inventory.py:1-482

## purpose
Deterministic concept inventory, contract `concept-inventory-v1`, for the E5B retrieval-representation lane — shared/polymath_shared/concept_inventory.py:1-2,28 [DERIVED]. Extracts multi-token concept candidates from chunk text and admits a ranked, budgeted subset as experimental routing metadata; concepts are explicitly NOT entities (never canonical entities, admission inputs, fact endpoints, Neo4j nodes, graph seeds, or graph facts) — shared/polymath_shared/concept_inventory.py:3-6 [DERIVED]. Zero new NLP/model dependencies: stdlib regex tokenization plus the frozen `GENERIC_HEAD` vocabulary — shared/polymath_shared/concept_inventory.py:8-10 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| normalize_concept_v1 | def | (surface: str) -> str | shared/polymath_shared/concept_inventory.py:117-127 | — |
| ConceptOccurrence | class | frozen dataclass: chunk_id, sentence_index, char_start, char_end, surface | shared/polymath_shared/concept_inventory.py:130-136 | — |
| ConceptCandidate | class | concept_id, normalized, surfaces, occurrences, token_count, generic; occurrence_count(), distinct_chunks() | shared/polymath_shared/concept_inventory.py:139-152 | — |
| concept_id | def | (normalized: str) -> str | shared/polymath_shared/concept_inventory.py:155-160 | — |
| generate_candidates | def | (chunk_id, text, *, sentence_offset=0) -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:167-267 | — |
| apply_overlap_policy | def | (candidates) -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:270-318 | — |
| is_generic | def | (candidate) -> bool | shared/polymath_shared/concept_inventory.py:321-329 | — |
| admit | def | (candidates, *, budget, in_summary_text="") -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:332-362 | — |
| build_inventory | def | (chunk_id, text, *, budget, in_summary_text="") -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:365-376 | — |
| document_inventory | def | (chunks: list[dict], *, budget=DOC_BUDGET_DEFAULT) -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:444-454 | — |
| section_inventory | def | (children: list[dict], *, budget=SECTION_BUDGET_DEFAULT, section_summary="") -> list[ConceptCandidate] | shared/polymath_shared/concept_inventory.py:457-467 | — |
| enriched_representation | def | (summary_text, concepts, max_concept_chars=240) -> str | shared/polymath_shared/concept_inventory.py:470-481 | — |

## contracts

**normalize_concept_v1** — shared/polymath_shared/concept_inventory.py:117-127
- in: any `str` surface.
- out: NFKC, case-fold, whitespace collapse; `re.sub(r"[-_/]", " ", text)` folds `-`, `_`, `/` to space — shared/polymath_shared/concept_inventory.py:123-126.
- post: `'working-memory' == 'working memory'` identity equivalence; original surface/offsets retained by caller-side dataclasses — shared/polymath_shared/concept_inventory.py:120-122,132-136.

**concept_id** — shared/polymath_shared/concept_inventory.py:155-160
- in: normalized string (re-normalized inside, double normalization).
- out: `CONCEPT_NS + content_hash({"normalized": ..., "contract": "concept-inventory-v1"})`, prefix `"concept_"` — shared/polymath_shared/concept_inventory.py:29,157-160.

**generate_candidates** — shared/polymath_shared/concept_inventory.py:167-267
- in: chunk_id, text; `sentence_offset=0` declared but never read — shared/polymath_shared/concept_inventory.py:171.
- out: candidates in first-seen order (`order` list, no set iteration) — shared/polymath_shared/concept_inventory.py:176-177,257.
- post: sentence-local token runs of `MIN_TOKENS..MAX_TOKENS` (2..5) split on `_STOP`/`_BOUNDARY_RE`/gaps; `"of"`/`"per"` bridging joins X-of-Y shapes; occurrences carry sentence-relative `char_start`/`char_end` — shared/polymath_shared/concept_inventory.py:191-231,244,262-265.

**apply_overlap_policy** — shared/polymath_shared/concept_inventory.py:270-318
- in/out: candidate lists.
- pre: same-`concept_id` candidates merged first — shared/polymath_shared/concept_inventory.py:276-283.
- post: shorter candidate that is a strict normalized substring of a kept longer one is dropped unless it has an independent occurrence (not span-contained in any longer occurrence, same chunk) — shared/polymath_shared/concept_inventory.py:286-304.

**admit** — shared/polymath_shared/concept_inventory.py:332-362
- rejects: `is_generic`, any `_verb_like` token, `_WEAK_MODIFIERS` lead — shared/polymath_shared/concept_inventory.py:343-350.
- rank tuple: `(occurrence_count, distinct_chunks, round(density,3), -(1 if token_count>3 else 0), token_count, in-summary hit, -weak-modifier count)` — shared/polymath_shared/concept_inventory.py:351-359.
- post: `scored.sort(key=(score, concept_id), reverse=True)`; returns `scored[:budget]` — tie-break on `concept_id` is therefore descending — shared/polymath_shared/concept_inventory.py:361-362.

**build_inventory** — shared/polymath_shared/concept_inventory.py:365-376
- pipeline: `generate_candidates` → `apply_overlap_policy` → `admit`; `_pre_filter` NOT applied — shared/polymath_shared/concept_inventory.py:372-375.

**document_inventory** — shared/polymath_shared/concept_inventory.py:444-454
- pre: chunks sorted by chunk_id upstream, dicts with `chunk_id`, `text`, optional `summary` (`ch.get("summary") or ""`).
- pipeline: per-chunk generate → `_pre_filter` → overlap → admit with `in_summary_text` = joined summaries — shared/polymath_shared/concept_inventory.py:449-454.

**section_inventory** — shared/polymath_shared/concept_inventory.py:457-467
- same pipeline as document_inventory, `section_summary` passed straight through — shared/polymath_shared/concept_inventory.py:463-467.

**enriched_representation** — shared/polymath_shared/concept_inventory.py:470-481
- out: `"[DOCUMENT SUMMARY]"` + stripped summary + `"[KEY CONCEPTS]"` + `"- {first surface}"` lines, truncated to `len(summary_text) + max_concept_chars` then `rstrip()` — shared/polymath_shared/concept_inventory.py:474-481.

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant collections / files / network / subprocess / env flags: none — pure in-process computation; only imports `re`, `unicodedata` — shared/polymath_shared/concept_inventory.py:20-21 — and `polymath_shared.entity_admission.GENERIC_HEAD` (:25), `polymath_shared.identity.content_hash` (:26), `polymath_shared.verb_inventory.VERBS` (:60).

## invariants
INVARIANT: MAX_TOKENS = 5 and MIN_TOKENS = 2 bound every candidate span window — shared/polymath_shared/concept_inventory.py:31-32,235-236 [DERIVED]
  fails-if: spans outside 2..5 tokens are generated or expected.
INVARIANT: DOC_BUDGET_DEFAULT = 8, SECTION_BUDGET_DEFAULT = 6; grids (4, 8, 12) / (3, 6, 8) — shared/polymath_shared/concept_inventory.py:34-38 [DERIVED]
  fails-if: admitted counts exceed caller expectations after budget retune.
INVARIANT: concept_id = "concept_" + hash(normalized, "concept-inventory-v1") — shared/polymath_shared/concept_inventory.py:29,155-160 [DERIVED]
  fails-if: contract-string bump silently re-keys every stored concept id.
INVARIANT: '-', '_', '/' all normalize to ' ' — shared/polymath_shared/concept_inventory.py:125 [DERIVED]
  fails-if: 'working-memory' and 'working memory' become two identities.
INVARIANT: frequency is ranking signal only, never admission authority (singletons admissible) — shared/polymath_shared/concept_inventory.py:15,338-340,352 [DERIVED]
  fails-if: rare-but-specific concepts silently dropped.
INVARIANT: per-document output depends ONLY on (sorted chunk identities, document text, contract version); PROCESS(A,B,C) == PROCESS(C,A,B) — shared/polymath_shared/concept_inventory.py:12-16 [DERIVED]
  fails-if: any set/dict iteration or ingestion-order ID leaks into output.
INVARIANT: concepts never become entities, Neo4j nodes, graph seeds, or graph facts — shared/polymath_shared/concept_inventory.py:3-6 [DERIVED]
  fails-if: sink escapes experimental routing metadata.

## determinism & idempotency
determinism: DETERMINISTIC — pure text functions; first-seen `order` list instead of set iteration (shared/polymath_shared/concept_inventory.py:176-177,257), explicit sort in overlap policy (:286); no clock/random/uuid/network/db/env/concurrency anywhere in the file.
idempotency: SAFE — no writes, no mutable module state; repeated calls with same chunks return equal output.

## failure behaviour
No try/except in the file; nothing is swallowed. Malformed chunk dicts raise `KeyError` at `ch["chunk_id"]` / `ch["text"]` — shared/polymath_shared/concept_inventory.py:450-452,464-466. Summary access is defaulted, not guarded: `ch.get("summary") or ""` — shared/polymath_shared/concept_inventory.py:453.

## dumb-code flags
- `sentence_offset: int = 0` parameter is never read; occurrences use raw `s_idx` — shared/polymath_shared/concept_inventory.py:171,262 [DERIVED].
- Dead branch `if pos < 0: continue` — `pos = first_pos` comes from a regex match span, always ≥ 0 — shared/polymath_shared/concept_inventory.py:243-248 [DERIVED].
- `is_generic` final return re-checks `head in GENERIC_HEAD`, which already returned `True` at shared/polymath_shared/concept_inventory.py:326-327; the effective predicate is head-noun membership alone — shared/polymath_shared/concept_inventory.py:321-329 [DERIVED].
- Context-noise suppression loop shared/polymath_shared/concept_inventory.py:305-315 can never fire: candidates are processed longest-first (:286), so `kept_ids` never holds a strictly shorter kept candidate when a longer one is evaluated [INFERRED — sort order at :286 precedes all appends at :315-317].
- Verb-final compound exemption ("session replay") in `_pre_filter` is nullified in every pipeline: `document_inventory`/`section_inventory` end in `admit`, and `admit` drops any candidate containing a `_verb_like` token with no exemption — shared/polymath_shared/concept_inventory.py:428-431 vs :346-348 [INFERRED — all three pipelines terminate in `admit` (:372-375, :452-454, :466-467)].
- Pipeline asymmetry: `build_inventory` skips `_pre_filter`, so 4-5-token candidates (allowed by `MAX_TOKENS = 5`, only rank-penalized at :355) can be admitted there but are hard-rejected (`token_count > 3`) in document/section pipelines — shared/polymath_shared/concept_inventory.py:372-374 vs :410-411 [DERIVED].
- Duplicated literals inside `_STOP`: `"welcome"` twice (:48), `"than"` at :44 and :50, `"instead"` twice (:56) — no behavioral effect (frozenset) but signals hand-edited vocabulary — shared/polymath_shared/concept_inventory.py:44,48,50,56 [DERIVED].
- Unused import `Optional` — shared/polymath_shared/concept_inventory.py:23 [DERIVED].
- `normalize_concept_v1` docstring documents only `-`/space equivalence; the regex also folds `_` and `/` — shared/polymath_shared/concept_inventory.py:119-125 [DERIVED].
- `admit` docstring says "tie-break by concept_id" but `reverse=True` over the whole key makes it descending — shared/polymath_shared/concept_inventory.py:340-341,361 [DERIVED].
- `enriched_representation` truncation budget counts raw `len(summary_text)`, but the emitted `"[DOCUMENT SUMMARY]\n...\n\n[KEY CONCEPTS]\n"` header adds ~35 chars, so concepts actually get `max_concept_chars` minus header overhead — shared/polymath_shared/concept_inventory.py:474-481 [INFERRED — arithmetic on :474-479 vs :479-480].

## refactor notes
- Changing `CONCEPT_CONTRACT = "concept-inventory-v1"` re-hashes every `concept_id` — shared/polymath_shared/concept_inventory.py:28,157-160.
- `VERBS` import is frozen 2026-09-03 (ADR-0017); verb-inventory edits shift `_verb_like`/`_verb_base`/`_ing_stem` and admission outcomes — shared/polymath_shared/concept_inventory.py:60,83-103,391-398.
- `GENERIC_HEAD` is shared with `entity_admission`; edits there change `is_generic` here — shared/polymath_shared/concept_inventory.py:25,326.
- The `-`/`_`/`/` folding in `normalize_concept_v1` is identity-level; altering it merges/splits stored concept ids — shared/polymath_shared/concept_inventory.py:125.
- Unifying `build_inventory` with the `_pre_filter` pipeline changes chunk-level inventories — shared/polymath_shared/concept_inventory.py:372-374 vs :452,:466.
- Any introduced set/dict iteration or cross-call state breaks the PROCESS(A,B,C)==PROCESS(C,A,B) contract — shared/polymath_shared/concept_inventory.py:12-16,286.

## VERIFY
```verify
grep -Fq 'CONCEPT_CONTRACT = "concept-inventory-v1"' shared/polymath_shared/concept_inventory.py
grep -Fq 'DOC_BUDGET_GRID = (4, 8, 12)' shared/polymath_shared/concept_inventory.py
grep -Fq 'max_concept_chars: int = 240' shared/polymath_shared/concept_inventory.py
grep -Fq 'from polymath_shared.verb_inventory import VERBS as _VERBS' shared/polymath_shared/concept_inventory.py
grep -Eq 'def (generate_candidates|apply_overlap_policy|admit|_pre_filter)\(' shared/polymath_shared/concept_inventory.py
test "$(grep -c -F 'concept-inventory-v1' shared/polymath_shared/concept_inventory.py)" -ge 2
```
