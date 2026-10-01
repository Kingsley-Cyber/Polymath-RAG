# unit: shared/polymath_shared/summary_compiler.py
anchor: shared/polymath_shared/summary_compiler.py:1-560

## purpose
Deterministic, model-free summary compiler (`COMPILER_CONTRACT = "summary-compiler-v1"`) that builds parent/section and document summaries from verbatim source sentences with offsets, trusted-triple relations, and keywords, then serializes one embed text (module docstring, source 1-22) [DERIVED]. Consumed by `shared/polymath_shared/_small-modules-3` and `shared/polymath_shared/parent_summary.py` (FACTS.importers) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `compile_section` | def | `(children, *, parent_id, background=None, facts=None, max_sentences=6, max_chars=1200) -> CompiledSummary` | summary_compiler.py:483-496 | parent_summary.py, _small-modules-3 (module-level) |
| `compile_document` | def | `(parents, *, doc_id, facts=None, max_sentences=12, max_chars=1600) -> CompiledSummary` | summary_compiler.py:499-511 | parent_summary.py, _small-modules-3 (module-level) |
| `digest_variant` | def | `(digests, deterministic) -> CompiledSummary \| None` | summary_compiler.py:519-551 | — |
| `serialize` | def | `(summary, relations, keywords) -> str` | summary_compiler.py:386-394 | — |
| `render_relation` | def | `(predicate, subject, obj) -> str \| None` | summary_compiler.py:94-99 | — |
| `contract_fingerprint` | def | `() -> dict` | summary_compiler.py:554-559 | — |
| `split_sentences` | def | `(text) -> list[tuple[int, int, str]]` | summary_compiler.py:147-163 | — |
| `structural_quality` | def | `(sentence) -> float` | summary_compiler.py:166-191 | — |
| `tokens` | def | `(text) -> list[str]` | summary_compiler.py:127-128 | — |
| `build_background` | def | `(texts) -> dict[str, int]` | summary_compiler.py:131-139 | — |
| `Sentence` | dataclass | frozen; `child_id, child_index, ordinal, start, end, text` | summary_compiler.py:103-109 | — |
| `CompiledSummary` | dataclass | `summary, sentences, relations, relation_items, keywords, coverage, embed_text, contract, variant` | summary_compiler.py:113-122 | — |

## contracts

**`compile_section`** (483-496)
- in: `children: [{chunk_id, text}]` in source order, noise already removed by caller; `facts: [{predicate, subject, object, chunk_id, start, end, trusted, fact_id}]` (docstring 488-490) [DERIVED]
- pre: `chunk_id` falls back to `c.get("id")` (491) [DERIVED]
- post: level `"section"`, `single_child_overlap = len(units) == 1` (495-496) [DERIVED]
- out: `CompiledSummary` with `coverage`, provenance per sentence, `embed_text` [DERIVED]

**`compile_document`** (499-511)
- in: `parents: [{chunk_id, summary?, text?}]` — each parent's compiled plain summary when available, else its text (docstring 503-504) [DERIVED]
- pre/post: `background=None` → always rebuilt from parent texts via `build_background` (425-426, 508); `single_child_overlap=False` (511) [DERIVED]

**`digest_variant`** (519-551)
- in: extractor digests (`central_claim`, `main_mechanism`, `retrieval_uses`) plus the deterministic card (docstring 520-524) [DERIVED]
- post: returns `None` when joined claims have `< DIGEST_MIN_WORDS` (6) words (537) or fail the garbage gate `common_share < 0.15 and mean_alpha_len < 4.5` (540-541); deterministic card then stays active; never invents relations — relations/relation_items copied verbatim (547) [DERIVED]

**`serialize`** (386-394)
- out: `SUMMARY:` block always; `RELATIONSHIPS:` and `KEY CONCEPTS:` blocks omitted when empty (389-393) [DERIVED]

**`render_relation`** (94-99)
- out: `f"{subject} {phrase} {obj}."` or `None` when predicate unknown or subject/obj empty after strip (95-98) [DERIVED]

**`contract_fingerprint`** (554-559)
- out: `{"contract", "weights": [W_TRIPLE, W_SALIENCE, W_CENTRALITY, W_QUALITY], "caps": [SECTION_MAX_SENTENCES, SECTION_MAX_CHARS, DOC_MAX_SENTENCES, DOC_MAX_CHARS, MAX_RELATIONS_SECTION, MAX_RELATIONS_DOCUMENT, MAX_KEYWORDS], "dedupe_jaccard", "digest_min_words"}` [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`) [DERIVED]
- Qdrant / files / network / subprocess / env flags: none in source or FACTS [DERIVED]
- Lazy imports inside functions: `polymath_shared.region_role.signals` at 168 and 525 (FACTS.imports; source 168, 525) [DERIVED]

## invariants
INVARIANT: SECTION_MAX_SENTENCES (6) < DOC_MAX_SENTENCES (12) — summary_compiler.py:32-34 [DERIVED]
  fails-if: document summaries stop being strictly larger-budget than sections; `contract_fingerprint().caps` order breaks.
INVARIANT: SECTION_MAX_CHARS (1200) < DOC_MAX_CHARS (1600) — summary_compiler.py:33-35 [DERIVED]
  fails-if: document card exceeds section budget semantics; embed length assumptions drift.
INVARIANT: enforced char bound is `max_chars + 1`, checked as `total <= max_chars + 1` — summary_compiler.py:304, 318, 322 [DERIVED]
  fails-if: summaries one char over `max_chars` pass `_fit` silently; `coverage.chars` disagrees with the declared cap.
INVARIANT: duplicate dropped when `_jaccard(st, kept_tokens) >= DEDUPE_JACCARD` (0.8), stronger representative survives — summary_compiler.py:292, 39 [DERIVED]
  fails-if: near-identical sentences both survive; summary budget wasted.
INVARIANT: triple score term = `min(2, trusted) * 1.0 + min(2, untrusted) * 0.5` with weights `W_TRIPLE, W_SALIENCE, W_CENTRALITY, W_QUALITY = 1.0, 1.0, 0.5, 0.5` — summary_compiler.py:228, 45 [DERIVED]
  fails-if: ranking order changes; any weight/cap edit re-profiles per comment at 44 and flips `contract_fingerprint`.
INVARIANT: relations serialized are trusted triples only — `sorted((t for t in triples if t.get("trusted")))`, section scope filters `chunk_id in unit_ids`, document passes `None` — summary_compiler.py:402, 441 [DERIVED]
  fails-if: untrusted facts leak into embed text; document card carries section-local relations.
INVARIANT: region count = sentence budget — `regions = _regions(len(units), max_sentences)`; one region per unit while `n_units <= max_regions` — summary_compiler.py:266, 245-246 [DERIVED]
  fails-if: coverage-first selection stops representing every unit (e.g., 181-parent doc per comment 245).
INVARIANT: structural_quality gate sequence: `< 4 words`, `len < 20` or `len > 600`, `alpha_ratio < 0.4`, heading `#` prefix, digit words `> n/2`, `common_share < 0.15 and mean_alpha_len < 4.5`, `mean_alpha_len < 3.2 or symbol_share >= 0.05 or digit_share >= 0.2` → all yield `0.0` — summary_compiler.py:171-183 [DERIVED]
  fails-if: OCR debris/headings/dumps score as prose and enter summaries or keywords.
INVARIANT: keyword `min_df = 1 if n < 3 else (2 if n < 50 else 3)`; keywords capped at `MAX_KEYWORDS` (8), digest adapter at `MAX_KEYWORDS + 3` (11) — summary_compiler.py:351, 38, 544 [DERIVED]
  fails-if: hapax/OCR tokens become routing keywords, or digest variant exceeds its implicit 11-keyword cap.
INVARIANT: `_debris` = `len(token) <= 5 and len(set(token)) <= 2` — summary_compiler.py:383 [DERIVED]
  fails-if: real short keywords ("add", "css") filtered as debris alongside "ee"/"rere".

## determinism & idempotency
determinism: DETERMINISTIC (stdlib `math`, `re`, `collections.Counter`, `dataclasses` only; lazy `region_role` import; no clock/random/uuid/network/db/env — source 25-28, 168, 525) [DERIVED]
idempotency: SAFE (pure functions, no writes of any kind per FACTS empty table lists) [DERIVED]

## failure behaviour
- No try/except handlers exist in the source; nothing is swallowed [DERIVED].
- Soft failures via `None` returns: `render_relation` on unknown predicate/empty endpoint (97-98); `digest_variant` on short or garbage claims (537, 540-541) — caller keeps the deterministic card [DERIVED].
- Truncation is reported, not raised: `_fit` sets `truncated = True` when a reserved (coverage) sentence must be dropped weakest-first (322-326); surfaces in `coverage["truncated"]` (473) [DERIVED].
- Starved units (prose existed but nothing selected) are listed in `coverage["uncovered"]`; units with no usable prose go to `coverage["no_prose_units"]` and are a source property, not a compiler failure — verifier gates on starvation only (455-469) [DERIVED].

## dumb-code flags
- `parent_id` (483) and `doc_id` (499) keyword parameters are never referenced in their function bodies [DERIVED].
- `RELATION_PHRASES` carries both ontology ids and legacy rule-pack ids with identical renderings: `"USES"`/`"uses"`, `"CAUSES"`/`"causes"`, `"PART_OF"`/`"part_of"`, `"LOCATED_IN"`/`"located_in"` — and the upper-case fallback at 95 makes several lowercase keys redundant — summary_compiler.py:65-91, 95 [DERIVED].
- Magic numbers: garbage-gate literals `0.15`/`4.5` duplicated in `structural_quality` (180) and `digest_variant` (540); thresholds `3.2`, `0.05`, `0.2` (182); `min_df` cutoffs `3`/`50` (351); `PREFERRED_SENTENCE_CHARS = 220` (42) [DERIVED].
- Off-by-one budget: the "HARD bound" actually enforced is `max_chars + 1` (304, 318, 322), not `max_chars` [DERIVED].
- Two keyword caps: `MAX_KEYWORDS = 8` (38) vs digest-adapter `MAX_KEYWORDS + 3` (544) — a default that disagrees with the constant's declared role [DERIVED].
- `Sentence.ordinal` is populated (429) but never read downstream; provenance dicts omit it (447-453) [INFERRED — set, never referenced elsewhere in file].

## refactor notes
- Importers `shared/polymath_shared/_small-modules-3` and `shared/polymath_shared/parent_summary.py` must be updated with any signature change (FACTS.importers) [DERIVED].
- Any change to weights (45), caps (32-38), `DEDUPE_JACCARD` (39), or `DIGEST_MIN_WORDS` (516) alters `contract_fingerprint()` output (554-559) — the contract-check consumers see a different fingerprint [INFERRED — fingerprint lists exactly these values].
- `serialize` block headers `"SUMMARY:"`, `"RELATIONSHIPS:"`, `"KEY CONCEPTS:"` (389-393) are the embedded representation; changing them re-embeds every parent/document vector [INFERRED — docstring calls it "The ONE deterministic text representation that is embedded"].
- `RELATION_PHRASES` must keep the 17 ontology ids + `RELATED_TO` because `workers/llm_direct.py` writes those predicates (comment 66) [DERIVED].
- `CompiledSummary` field set (113-122) and `coverage` keys (464-477) are the interchange format consumed by the verifier that gates on `uncovered` (455-458) [DERIVED].
- `region_role.signals` output keys `common_share`, `mean_alpha_len`, `symbol_share`, `digit_share` are a hard dependency (168, 179-183, 525, 539-541) [DERIVED].

## VERIFY
```verify
grep -Fq 'COMPILER_CONTRACT = "summary-compiler-v1"' shared/polymath_shared/summary_compiler.py
grep -Fq 'SECTION_MAX_SENTENCES = 6' shared/polymath_shared/summary_compiler.py
grep -Fq 'DOC_MAX_CHARS = 1600' shared/polymath_shared/summary_compiler.py
grep -Fq 'if total <= max_chars + 1:' shared/polymath_shared/summary_compiler.py
grep -Fq 'len(keywords) < MAX_KEYWORDS + 3' shared/polymath_shared/summary_compiler.py
test "$(grep -c -F 'is part of' shared/polymath_shared/summary_compiler.py)" -ge 2
! grep -Fq 'import random' shared/polymath_shared/summary_compiler.py
```
