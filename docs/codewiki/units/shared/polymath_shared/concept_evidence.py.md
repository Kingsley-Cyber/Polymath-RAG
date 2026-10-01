# unit: shared/polymath_shared/concept_evidence.py
anchor: shared/polymath_shared/concept_evidence.py:1-270

## purpose
Implements `CONCEPT-EVIDENCE-V1` (Phase 2D): cross-domain concept admission in two separated layers — 2D.1 `concept_candidate()` (candidacy only, no graph authority) and 2D.2 `admit_concept()` (auditable evidence or ABSTAIN). shared/polymath_shared/concept_evidence.py:1-36 [DERIVED]
Admission requires one of four authorities (DOCUMENT_DEFINED, GLOSSARY_DECLARED, EXISTING_CANONICAL, CURATED_LEXICON); frequency, capitalization, embeddings etc. are supporting evidence only, never sufficient. shared/polymath_shared/concept_evidence.py:24-33 [DERIVED]
No domain is named; abstention never blocks text retrieval. shared/polymath_shared/concept_evidence.py:12-15, shared/polymath_shared/concept_evidence.py:8 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ConceptEvidenceKind` | class (`str, Enum`) | members: `DOCUMENT_DEFINED`, `GLOSSARY_DECLARED`, `EXISTING_CANONICAL`, `CURATED_LEXICON` | shared/polymath_shared/concept_evidence.py:48-52 | see note |
| `ConceptEvidence` | frozen dataclass | (kind, term, quote="", source_document_id=None, source_offsets=None, external_source_id=None, external_source_version=None, contract=CONCEPT_CONTRACT) | shared/polymath_shared/concept_evidence.py:55-64 | see note |
| `ConceptRecord` | frozen dataclass | (concept_id, canonical_term, normalized_term, evidence_kind, source_document_id=None, source_offsets=None, external_source_id=None, external_source_version=None, concept_contract=CONCEPT_CONTRACT) | shared/polymath_shared/concept_evidence.py:67-77 | see note |
| `concept_candidate` | function | (surface: str, *, is_identity=False, is_generic=False) -> bool | shared/polymath_shared/concept_evidence.py:137-146 | see note |
| `find_document_definition` | function | (term, text, doc_id=None) -> ConceptEvidence \| None | shared/polymath_shared/concept_evidence.py:192-195 | see note |
| `find_glossary_declaration` | function | (term, text, doc_id=None) -> ConceptEvidence \| None | shared/polymath_shared/concept_evidence.py:198-215 | see note |
| `find_registry_entry` | function | (term, registry: dict[str, ConceptRecord] \| None) -> ConceptEvidence \| None | shared/polymath_shared/concept_evidence.py:218-229 | see note |
| `find_lexicon_entry` | function | (term, lexicon: dict \| None) -> ConceptEvidence \| None | shared/polymath_shared/concept_evidence.py:232-248 | see note |
| `admit_concept` | function | (term, *, document_text="", doc_id=None, registry=None, lexicon=None) -> ConceptEvidence \| None | shared/polymath_shared/concept_evidence.py:251-269 | see note |

Note: module is imported by `shared/polymath_shared/admission_interpreter.py` and `shared/polymath_shared/execution.py` (FACTS.importers); per-symbol usage is not in FACTS.

## contracts

**`admit_concept`** shared/polymath_shared/concept_evidence.py:251-269
- in: `term: str`; keyword-only `document_text: str = ""`, `doc_id: str | None = None`, `registry: dict[str, ConceptRecord] | None = None`, `lexicon: dict | None = None` [DERIVED]
- out: first non-None `ConceptEvidence`, else `None` = ABSTAIN (254, 268-269) [DERIVED]
- pre: document/glossary finders run only when `document_text` is truthy (261-262) [DERIVED]
- post: fixed authority order `find_document_definition` → `find_glossary_declaration` → `find_registry_entry` → `find_lexicon_entry`; at most one authority's evidence returned (260-268) [DERIVED]

**`concept_candidate`** shared/polymath_shared/concept_evidence.py:137-146
- in: `surface: str`, flags `is_identity`, `is_generic` (default `False`) [DERIVED]
- out: `False` if `is_identity or is_generic`; else truthy iff `_norm(_strip_det(surface))` is non-empty (144-146) [DERIVED]
- pre/post: no graph authority, no admission — candidacy only (139-143) [DERIVED]

**`find_document_definition`** shared/polymath_shared/concept_evidence.py:192-195
- in: `term`, `text`, `doc_id=None`; out: DOCUMENT_DEFINED evidence or `None` [DERIVED]
- post: delegates to `_definition_scan(_strip_det(term), ...)` — first-sentence-then-first-template precedence over the 13 `_DEFINITIONAL` templates; `quote=sent[:200]`, `source_offsets=(off, off+len(sent))` only when `text.find(sent) >= 0` (155-190) [DERIVED]

**`find_glossary_declaration`** shared/polymath_shared/concept_evidence.py:198-215
- in: `term`, `text`, `doc_id=None`; out: GLOSSARY_DECLARED evidence or `None` [DERIVED]
- post: matches `_DEF_LIST` (`^\s*(?:[-*]\s*)?{term}\s*(?:[—–:-])\s+\S`) inside the section after a `_GLOSSARY_HEADING` heading, trimmed at the next heading; `source_offsets=(off, off+len(bare))` only when `off >= 0` (203-216) [DERIVED]

**`find_registry_entry`** shared/polymath_shared/concept_evidence.py:218-229
- in: `term`, `registry: dict[str, ConceptRecord] | None`; out: EXISTING_CANONICAL evidence with `quote=f"concept_id={rec.concept_id}"` or `None` [DERIVED]
- post: lookup key is `_norm(_strip_det(term))` (225) [DERIVED]

**`find_lexicon_entry`** shared/polymath_shared/concept_evidence.py:232-248
- in: `term`, `lexicon: dict | None`; out: CURATED_LEXICON evidence or `None` [DERIVED]
- pre: exact match only on `lexicon["entries"][_norm(_strip_det(term))]`; fuzzy/similarity matching is forbidden as truth evidence (235-244) [DERIVED]
- post: `quote=rec.get("gloss", "")[:200]`, carries `lexicon["source_id"]`/`["source_version"]` (246-250) [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS.tables_read and tables_written are empty) [DERIVED]
- Qdrant / files / network / subprocess / env flags: none visible in SOURCE (imports are only `re`, `dataclasses`, `functools.lru_cache`, `enum`, shared/polymath_shared/concept_evidence.py:40-43) [DERIVED]
- In-process memory: `lru_cache` on `_sentences` (maxsize=8, shared/polymath_shared/concept_evidence.py:149-151) and on `_definition_scan` (maxsize=65536, shared/polymath_shared/concept_evidence.py:154-155) [DERIVED]

## invariants
INVARIANT: admit_concept authority order == DOCUMENT_DEFINED → GLOSSARY_DECLARED → EXISTING_CANONICAL → CURATED_LEXICON — shared/polymath_shared/concept_evidence.py:260-268 [DERIVED]
  fails-if: a term matching multiple authorities gets a different `evidence_kind`.
INVARIANT: registry lookup key == lexicon lookup key == `_norm(_strip_det(term))` — shared/polymath_shared/concept_evidence.py:225, shared/polymath_shared/concept_evidence.py:241 [DERIVED]
  fails-if: one term surface hits the registry, another misses, duplicating or dropping concepts.
INVARIANT: len(quote) <= 200 (`sent[:200]`, `rec.get("gloss", "")[:200]`) — shared/polymath_shared/concept_evidence.py:186, shared/polymath_shared/concept_evidence.py:248 [DERIVED]
  fails-if: unbounded quotes in evidence records.
INVARIANT: `concept_candidate(_, is_identity=True) == False` and `concept_candidate(_, is_generic=True) == False` — shared/polymath_shared/concept_evidence.py:144-145 [DERIVED]
  fails-if: spans owned by other Harbor branches leak into concept admission.
INVARIANT: `ConceptEvidence.contract == ConceptRecord.concept_contract == CONCEPT_CONTRACT == "concept-evidence-v1"` (defaults) — shared/polymath_shared/concept_evidence.py:45, shared/polymath_shared/concept_evidence.py:64, shared/polymath_shared/concept_evidence.py:77 [DERIVED]
  fails-if: contract-keyed consumers reject records.
INVARIANT: `source_offsets` is set only when `off >= 0`, else `None` — shared/polymath_shared/concept_evidence.py:188-190, shared/polymath_shared/concept_evidence.py:212-216 [DERIVED]
  fails-if: negative offsets corrupt evidence spans.
INVARIANT: sentence prefilter (`term_rx.search`) cannot drop a match because every one of the 13 templates embeds the escaped term — shared/polymath_shared/concept_evidence.py:166-171, shared/polymath_shared/concept_evidence.py:167 [DERIVED]
  fails-if: a template added without the term subpattern silently skips matching sentences.

## determinism & idempotency
determinism: DETERMINISTIC — pure regex/dataclass logic; no clock/random/uuid/network/db/env input (imports at shared/polymath_shared/concept_evidence.py:40-43; no other I/O in file) [DERIVED]
idempotency: SAFE — pure functions over inputs; caches keyed on `(bare, text, doc_id)` / `text` only, and mutable `registry`/`lexicon` dicts are never cached, so they are re-read each call (shared/polymath_shared/concept_evidence.py:154-155, shared/polymath_shared/concept_evidence.py:260-266) [DERIVED]

## failure behaviour
No try/except handlers exist anywhere in the file; FACTS list no fallbacks. [DERIVED] shared/polymath_shared/concept_evidence.py:38-270
Every finder returns `None` on miss (shared/polymath_shared/concept_evidence.py:203-204, 222-225, 239-244, 189); `admit_concept` propagates that as `None` = ABSTAIN (shared/polymath_shared/concept_evidence.py:268-269). Unsupported semantic knowledge causes abstention, never guessed truth (shared/polymath_shared/concept_evidence.py:8). No error codes raised by this module. [DERIVED]

## dumb-code flags
- Magic cache sizes: `maxsize=8` vs `maxsize=65536` with no shared constant — shared/polymath_shared/concept_evidence.py:149-150, shared/polymath_shared/concept_evidence.py:154 [DERIVED]
- Duplicated truncation literal `200` in two unrelated quote sites — shared/polymath_shared/concept_evidence.py:186, shared/polymath_shared/concept_evidence.py:248 [DERIVED]
- `_DEFINITIONAL` templates duplicated as article-initial variants (pairs at 101/102, 106/107, 118/119) — shared/polymath_shared/concept_evidence.py:98-120 [DERIVED]
- `"{term}"` string-replace templating used in two places (`tmpl.replace("{term}", pat)` and `_DEF_LIST.replace(...)`) — shared/polymath_shared/concept_evidence.py:177, shared/polymath_shared/concept_evidence.py (line out of range) [DERIVED]
- Glossary offsets can point outside the glossary section: the `_DEF_LIST` match runs on `section` trimmed at the next heading (205-208), but `off = text.find(bare, m.end())` searches past that boundary — shared/polymath_shared/concept_evidence.py:212 [INFERRED] (trim boundary not applied to the find range)
- `_definition_scan` offsets use `text.find(sent)`; if the same sentence text occurs twice, offsets point at the first occurrence, not necessarily the matched one — shared/polymath_shared/concept_evidence.py:185-190 [INFERRED]

## refactor notes
- `CONCEPT_CONTRACT = "concept-evidence-v1"` is a wire-format default on both dataclasses (64, 77); the docstring pins it to behavior identity (172-174). Changing it requires updating consumers in `admission_interpreter.py` and `execution.py` (FACTS.importers). shared/polymath_shared/concept_evidence.py:45 [DERIVED]
- The `_norm`/`_strip_det` join key (225, 241, also used in `concept_candidate` at 146) is the registry/lexicon addressing scheme; changing normalization orphans existing registries and lexicons. shared/polymath_shared/concept_evidence.py:129-134 [DERIVED]
- `_definition_scan` must remain behavior-identical to the naive scan; equivalence is asserted by `tests/determinism/test_concept_evidence_equivalence.py` against a verbatim reference copy (docstring reference only, not in FACTS). shared/polymath_shared/concept_evidence.py:159-163 [DERIVED]
- Finder order in `admit_concept` (260-268) is externally visible — which authority's evidence wins for multi-match terms. shared/polymath_shared/concept_evidence.py:260-268 [DERIVED]
- The template count is documented as "the 13 definitional templates" (167); adding/removing `_DEFINITIONAL` entries changes DOCUMENT_DEFINED coverage and that count. shared/polymath_shared/concept_evidence.py:98-120 [DERIVED]
- `_GLOSSARY_HEADING` word list (`glossary|terminology|definitions|key terms|nomenclature`) gates all GLOSSARY_DECLARED hits. shared/polymath_shared/concept_evidence.py:122-124 [DERIVED]

## VERIFY
```verify
grep -Fq 'CONCEPT_CONTRACT = "concept-evidence-v1"' shared/polymath_shared/concept_evidence.py
grep -Fq 'lru_cache(maxsize=65536)' shared/polymath_shared/concept_evidence.py
grep -Fq 'lru_cache(maxsize=8)' shared/polymath_shared/concept_evidence.py
grep -Fq 'sent[:200]' shared/polymath_shared/concept_evidence.py
grep -Fq 'if is_identity or is_generic:' shared/polymath_shared/concept_evidence.py
test "$(grep -c -F 'find_document_definition' shared/polymath_shared/concept_evidence.py)" -ge 2
```
