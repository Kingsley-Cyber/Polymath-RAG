# unit: shared/polymath_shared/knowledge_objects/concept.py
anchor: shared/polymath_shared/knowledge_objects/concept.py:1-429

## purpose
Compiles definitional sentences ("X is defined as Y", copula/gerund/appositive definitions) into CONCEPT `KnowledgeArtifact` rows. Two contracts: frozen v1 (`compile_concepts`, capped at 10) and v2 durable inventory (`compile_concept_inventory`, no cap, admission-governed). Also owns the shared object-name admission gates used by the concept and procedure compilers and the /ask read path — concept.py:1-10, 317-321 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `compile_concepts` | def | (document_id, corpus_id, sentences, domain="general", admitted_entities=None, source_chunk_ids=None, max_concepts=10) -> list[dict] | concept.py:143-209 | — |
| `compile_concept_inventory` | def | (document_id, corpus_id, sentences, domain="general", admitted_entities=None, source_chunk_ids=None, summary_top_n=SUMMARY_TOP_N) -> list[dict] | concept.py:397-429 | — |
| `object_name_admissible` | def | (name) -> tuple[bool, str] | concept.py:317-344 | procedure compiler + /ask serve path (docstring, concept.py:318-321) |
| `concept_name_admissible` | def | (name) -> tuple[bool, str] | concept.py:347-394 | — |
| `count_opportunities` | def | (sentences) -> int | concept.py:126-140 | — |
| `CONCEPT_CONTRACT_V1` / `CONCEPT_CONTRACT_V2` / `SUMMARY_TOP_N` | const | "concept-artifact-v1" / "concept-inventory-v2" / 10 | concept.py:258-263 | — |

Module-level importers (FACTS): orchestrator/orchestrator/api/ask.py, shared/polymath_shared/knowledge_objects/procedure.py, workers/workers/knowledge_artifacts.py. Private helpers: `_bad_name`, `_nominal_head`, `_clean_name`.

## contracts

**compile_concepts** — concept.py:143-209
- in: keyword-only `document_id`, `corpus_id`, `sentences: list[str]`, `domain="general"`, `admitted_entities=None`, `source_chunk_ids=None`, `max_concepts=10` (concept.py:143-148).
- out: `KnowledgeArtifact(...).model_dump()` merged with body `{name, description, domain, related_entities, source_sentence}`; `artifact_type="CONCEPT"`, `confidence=0.9` (concept.py:184-201).
- post: when `max_concepts > 0`, scanning stops the moment `len(out) >= max_concepts`; `max_concepts <= 0` means no ceiling (concept.py:204-208).
- post: candidate name cleaned (`_clean_name`), leading `"the"/"a"/"an"` stripped, rejected if empty or `> _MAX_NAME` (8) words (concept.py:158-169).
- post: rejected by `_bad_name` (pronoun/demonstrative/enumeration/clause subject), by `object_name_admissible`, and gerund-copula matches require `_nominal_head` (concept.py:171-177).
- post: names deduped case-insensitively (`key = name.lower()`) (concept.py:178-181).
- post: `desc` falls back to the whole sentence when the pattern has no `desc` group (refers-to pattern) (concept.py:164-168).
- post: `description` truncated `[:400]`, `source_sentence` `[:300]`, `related_entities` = admitted entities substring-matched in sentence, longest first, `[:6]` (concept.py:182-183, 194-197).

**object_name_admissible** — concept.py:317-344
- out reasons in order: `"empty"`, `"not_a_term_surface"` (via lazy `from polymath_shared.llm_extraction.gate import is_term_surface`), `"repeated_content_token"`, else `"admitted"` (concept.py:330-344).
- post: repeated-token check skips `_REPEATABLE_TOKENS` = `of the a an and or for in on to with` (concept.py:313-314, 338-343).

**concept_name_admissible** — concept.py:347-394
- out: delegates first to `object_name_admissible`, then closed-class checks in order: `"punctuation_fragment"`, `"opens_with_function_word"`, `"ends_with_function_word"`, `"contains_finite_verb"`, `"contains_subordinate_clause"` (interior tokens only, `low[1:-1]`), `"no_letters"` (concept.py:361-375).
- post: single-token names: reject `"bare_participle"` (`^\w+(?:ing|ed)$`), reject `"bare_generic_noun"` against `_GENERIC_NAME`; multi-token: reject `"generic_head_no_modifier"` when the head is generic and no discriminative modifier survives filtering by `_EDGE_FUNCTION`/`_GENERIC_NAME`/`WEAK_MODIFIERS`/`DEICTIC_MODIFIERS` (concept.py:377-394).

**compile_concept_inventory** — concept.py:397-429
- pre: calls `compile_concepts(..., max_concepts=0)` — 0 = no ceiling, reads every sentence (concept.py:410-414).
- post: every row's name passes `concept_name_admissible` or is dropped (concept.py:418-420).
- post: each admitted row gains `provenance = {contract: CONCEPT_CONTRACT_V2, summary_rank: len(out), in_summary: len(out) < summary_top_n, admission: reason}`; `summary_rank` in document order (concept.py:422-427).

**count_opportunities** — concept.py:126-140
- out: number of sentences matching any `_DEFINE_PATTERNS`, before the cap; diagnostic only, same patterns as `compile_concepts` (concept.py:127-139).

## effect surface
- Postgres tables: none read, none written (FACTS `tables_read: []`, `tables_written: []`).
- No Qdrant, files, network, subprocess, or env flags anywhere in SOURCE.
- Only external calls: `finalize(artifact, body)` from `knowledge_objects.knowledge_artifact` (concept.py:199) and `is_term_surface` from `llm_extraction.gate` (concept.py:330).

## invariants
INVARIANT: `_MAX_NAME = 8` words == "<=8 words" term law in the object gate docstring — concept.py:96, concept.py:324 [DERIVED]
  fails-if: one gate accepts >8-word names the other rejects → silent concept loss.
INVARIANT: `max_concepts=0` passed by v2 == sentinel meaning "no ceiling" in v1 loop — concept.py:414, concept.py:204-207 [DERIVED]
  fails-if: inventory re-truncated at 10; measured effect of the cap is x8.1 (975 vs 121 concepts, concept.py:226-228).
INVARIANT: `summary_rank < summary_top_n` ⇔ `in_summary == True` — concept.py:424-425 [DERIVED]
  fails-if: routing-card top-N slice disagrees with the stored `in_summary` flags.
INVARIANT: every v2 row name passed `concept_name_admissible` — concept.py:418-420 [DERIVED]
  fails-if: noun-phrase junk re-enters the inventory (~28% of uncapped candidates were junk, concept.py:235-241).
INVARIANT: `len(description) <= 400` chars, `len(source_sentence) <= 300` chars, `len(related_entities) <= 6` — concept.py:183, 194-197 [DERIVED]
  fails-if: oversized artifact bodies.
INVARIANT: emitted names unique per run, compared as `name.lower()` — concept.py:178-181 [DERIVED]
  fails-if: duplicate concept rows for one document.
INVARIANT: default `max_concepts = 10` == `SUMMARY_TOP_N = 10` — concept.py:148, concept.py:263 [DERIVED]
  fails-if: v1 storage cap and v2 presentation top-N drift apart in size (values only, meanings differ).

## determinism & idempotency
determinism: DETERMINISTIC — all logic is regex/frozenset/token comparisons over the input sentences; no clock, random, uuid, db, env, or network reads in SOURCE (whole file).
idempotency: SAFE — pure functions of inputs; the only externally assigned value is `artifact_id="pending"` handed to `finalize` (concept.py:185, 199), so final row identity depends on `finalize` outside this unit [INFERRED].

## failure behaviour
- No try/except in this unit; exceptions from `finalize`/`is_term_surface` propagate to the caller.
- Rejected candidates are swallowed by `continue` — the caller sees fewer rows, never an error (concept.py:170, 172, 174, 176, 180, 420).
- Documented historical bug: the refers-to pattern has no `desc` group, a latent `IndexError` from real transcript text; guarded by `m.groupdict().get("desc") or s` (concept.py:164-168).
- No error codes raised.

## dumb-code flags
- Dead constant: `_MAX_DESC = 40` is never referenced; `description` is truncated with the literal `[:400]` instead — concept.py:97, 194 [DERIVED].
- Redundant flag: refers-to pattern uses inline `(?i)` AND the `re.I` compile flag — concept.py:27-28 [DERIVED].
- Magic numbers: `confidence=0.9`, related cap `[:6]`, `[:400]`, `[:300]` — concept.py:183, 190, 194, 197 [DERIVED].
- Duplicate literal 10 with different meanings: `max_concepts: int = 10` (storage cap) vs `SUMMARY_TOP_N = 10` (presentation cap) — concept.py:148, 263 [DERIVED].
- Docstring hardcodes the cap value: "the cap is 10/document" — concept.py:131 [DERIVED].
- Overlapping closed classes: `_REPEATABLE_TOKENS` words ("a an the and or for in on to with") all also appear in `_EDGE_FUNCTION` — concept.py:268-275, 313-314 [DERIVED].

## refactor notes
- `object_name_admissible` is the shared naming gate for the procedure compiler and the /ask serve path (stale rows filtered at read time) — concept.py:318-321; module importers include ask.py, procedure.py, workers/knowledge_artifacts.py (FACTS). Semantics/reason-string changes alter read-time filtering across those units.
- Reason strings are persisted: `provenance.admission` stores the literal returned by `concept_name_admissible` — concept.py:426. Renaming reasons breaks stored-data consumers.
- v1 is frozen: "compile_concepts still caps at 10" — concept.py:253. Do not change the default without versioning; v2 depends on the `max_concepts=0` sentinel — concept.py:204-205, 414.
- `_GENERIC_NAME = GENERIC_HEAD | _GENERIC_EXTRA` couples admission to the `entity_admission` vocabulary (deliberate reuse, concept.py:243-246, 255-256, 286) — edits there change concept admission here.
- `is_term_surface` is imported inside the function so both contracts share ONE definition of "term" — concept.py:323-326, 330. Moving/duplicating that check forks the term law.

## VERIFY
```verify
grep -Fq 'max_concepts: int = 10' shared/polymath_shared/knowledge_objects/concept.py
grep -Fq 'max_concepts=0)' shared/polymath_shared/knowledge_objects/concept.py
grep -Fq 'SUMMARY_TOP_N = 10' shared/polymath_shared/knowledge_objects/concept.py
grep -Fq '_MAX_DESC = 40' shared/polymath_shared/knowledge_objects/concept.py
! grep -Fq 'desc[:_MAX_DESC]' shared/polymath_shared/knowledge_objects/concept.py
test "$(grep -c -F 'CONCEPT_CONTRACT_V2' shared/polymath_shared/knowledge_objects/concept.py)" -ge 3
grep -Eq 'if max_concepts > 0 and len\(out\) >= max_concepts:' shared/polymath_shared/knowledge_objects/concept.py
```
