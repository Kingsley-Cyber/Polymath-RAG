# unit: shared/polymath_shared/scientific_concept.py
anchor: shared/polymath_shared/scientific_concept.py:1-185

## purpose
Deterministic named-concept identity gate (SCIENTIFIC-KAG-V1 phase 2): decides whether a surface string names a scientific concept using surface-pattern evidence only — no model, no I/O. Exists so multi-token research compounds ("Tree of Thoughts", "thought generator") survive the admission chain instead of dying as non-durable. — shared/polymath_shared/scientific_concept.py:1-24 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| named_concept_evidence | def | (surface: str, tokens: list[dict] \| None = None) -> dict \| None | shared/polymath_shared/scientific_concept.py:70-137 | shared/polymath_shared/admission_interpreter.py, shared/polymath_shared/parent_summary.py (module importers, FACTS) |
| is_temporal_surface | def | (surface: str) -> bool | shared/polymath_shared/scientific_concept.py:147-160 | same module importers |
| normalize_temporal | def | (surface: str) -> dict \| None | shared/polymath_shared/scientific_concept.py:163-184 | same module importers |
| _is_date_expression | def | (words: list[str]) -> bool | shared/polymath_shared/scientific_concept.py:45-52 | — (private) |
| _is_version_identity | def | (words: list[str]) -> bool | shared/polymath_shared/scientific_concept.py:55-59 | — (private) |
| _is_acronym | def | (token: str) -> bool | shared/polymath_shared/scientific_concept.py:62-63 | — (private) |
| _has_digit | def | (token: str) -> bool | shared/polymath_shared/scientific_concept.py:66-67 | — (private) |

Module constants: `SCIENTIFIC_HEAD_LEMMAS = frozenset({...28 lemmas...})` at shared/polymath_shared/scientific_concept.py:31-37; `_MONTHS` tuple of 12 month names at shared/polymath_shared/scientific_concept.py:41-42.

## contracts

**named_concept_evidence** — shared/polymath_shared/scientific_concept.py:70-137
- in: `surface: str`; optional `tokens: list[dict]` whose dicts carry `"text"` and `"lemma"` keys (matched case-insensitively against the head word) — shared/polymath_shared/scientific_concept.py:129-132 [DERIVED]
- out: dict `{"contract": "scientific-concept-evidence-v1", "pattern": <p>, "surface": text}`; `technical_head_compound` adds `"head": head_lemma` — shared/polymath_shared/scientific_concept.py:89-136 [DERIVED]
- pattern value is one of: `acronym`, `versioned_compound`, `short_acronym` (single token); `date_expression`, `version_identity`, `acronym_token`, `versioned_compound`, `capitalized_compound`, `technical_head_compound` (multi token) — shared/polymath_shared/scientific_concept.py:86-136 [DERIVED]
- pre: empty/whitespace surface returns `None` — shared/polymath_shared/scientific_concept.py:79-81 [DERIVED]
- post: `None` means decline, never refusal — later admission authorities still run — shared/polymath_shared/scientific_concept.py:72-73 [DERIVED]

**is_temporal_surface** — shared/polymath_shared/scientific_concept.py:147-160
- in: `surface: str`
- out: `True` iff month-name date expression, bare year matching `_YEAR_RE = \b(1[89]\d{2}|20\d{2})\b` fullmatch, or ISO `\d{4}-\d{2}(-\d{2})?` fullmatch — shared/polymath_shared/scientific_concept.py:144,154-159 [DERIVED]

**normalize_temporal** — shared/polymath_shared/scientific_concept.py:163-184
- in: `surface: str`
- out: `None` when not temporal; `{"valid_from": YYYY}` for bare year or ISO; `{"valid_from": "YYYY-MM"}` (+"-DD" when a 1–2 digit day token exists) for month-name forms — shared/polymath_shared/scientific_concept.py:167-181 [DERIVED]
- pre: delegates gating to `is_temporal_surface` — shared/polymath_shared/scientific_concept.py:167-168 [DERIVED]

## effect surface
- None. `tables_read` and `tables_written` are empty in FACTS; imports are only `from __future__ import annotations` and `import re` — shared/polymath_shared/scientific_concept.py:26-27 [DERIVED]
- Module docstring commits to "no model, no I/O" — shared/polymath_shared/scientific_concept.py:8 [DERIVED]

## invariants
INVARIANT: `_is_acronym` accepts only tokens with `len(token) >= 2`, `token.isupper()`, `token.isalpha()` — shared/polymath_shared/scientific_concept.py:63 [DERIVED]
  fails-if: single letters ("A", "I") get admitted as `acronym` evidence.
INVARIANT: `short_acronym` requires `len(w) <= 6` AND `sum(ch.isupper() for ch in w) >= 2` AND `not w.istitle()` — shared/polymath_shared/scientific_concept.py:95-97 [DERIVED]
  fails-if: CamelCase words ("Dataset") or long names leak in as acronyms.
INVARIANT: inflected plural guard — `w[-1].islower() and w[-2].isupper()` returns `None` ("LMs") — shared/polymath_shared/scientific_concept.py:100-101 [DERIVED]
  fails-if: plural inflections of acronyms admitted as distinct concepts.
INVARIANT: multi-token evaluation order is `_is_date_expression` → `_is_version_identity` → acronym → versioned → capitalized → head lemma — shared/polymath_shared/scientific_concept.py:109-136 [DERIVED]
  fails-if: "Version 3.8" would be classified `capitalized_compound` or declined before reaching the right pattern.
INVARIANT: head check strips `".,;:!?'\""` from `words[-1].lower()` and optionally swaps in the token `lemma` before matching `SCIENTIFIC_HEAD_LEMMAS` — shared/polymath_shared/scientific_concept.py:126-133 [DERIVED]
  fails-if: "tree searches" (plural head) declines because "searches" not in the lemma set and no lemma token supplied.
INVARIANT: `len(_MONTHS) == len(_MONTH_NUM) == 12` (both hardcode the same 12 names) — shared/polymath_shared/scientific_concept.py:41-42,140-142 [DERIVED]
  fails-if: a month added to one list only — `is_temporal_surface` true but `normalize_temporal` degrades to year-only or `None`.

## determinism & idempotency
determinism: DETERMINISTIC (pure string/regex functions of arguments; only stdlib `re`, no clock/random/network/db/env) — shared/polymath_shared/scientific_concept.py:26-27 [DERIVED]
idempotency: SAFE (no mutation, no side effects, return values only) — shared/polymath_shared/scientific_concept.py:45-184 [DERIVED]

## failure behaviour
- No try/except handlers and no raised error codes in SOURCE; decline is expressed as `None` (evidence/normalize) or `False` (temporal test) — shared/polymath_shared/scientific_concept.py:81,104,137,160,169,184 [DERIVED]
- `normalize_temporal` can return `None` for input where `is_temporal_surface` is `False`, and returns `out or None` so a month-name match with no resolvable month/year yields `None` — shared/polymath_shared/scientific_concept.py:167-169,184 [DERIVED]

## dumb-code flags
- `_ACRONYM_RE = None` — dead constant, assigned once, never read anywhere in the file — shared/polymath_shared/scientific_concept.py:39 [DERIVED]
- Month names duplicated: `_MONTHS` tuple vs `_MONTH_NUM` dict keys — shared/polymath_shared/scientific_concept.py:41-42,140-142 [DERIVED]
- Literal `"scientific-concept-evidence-v1"` repeated at all 9 return sites instead of a module constant — shared/polymath_shared/scientific_concept.py:89-134 [DERIVED]
- Dead branch: `if len(words) < 2: return None` — empty `text` already returned at :81 and `text.split()` of non-empty text yields ≥1 word, so `len(words) == 0` is unreachable here — shared/polymath_shared/scientific_concept.py:106-107 [INFERRED]
- Magic numbers: `len(tail[-1]) == 4` (:51), `len(w) <= 6` (:95), `sum(...) >= 2` (:96), `len(w) == 4` / `len(w) <= 2` (:175-176) — shared/polymath_shared/scientific_concept.py:51,95-96,175-176 [DERIVED]
- Asymmetric default: single-token `versioned_compound` requires `w[0].isupper()` (:92) but the multi-token `versioned_compound` test has no case condition (:119) — shared/polymath_shared/scientific_concept.py:92,119 [DERIVED]
- `capitalized_compound` scans `words[1:]` only — first-token capitalization alone never matches — shared/polymath_shared/scientific_concept.py:122 [DERIVED]

## refactor notes
- Contract literal `scientific-concept-evidence-v1` and all 8 `pattern` strings are the API consumed by `shared/polymath_shared/admission_interpreter.py` and `shared/polymath_shared/parent_summary.py` (FACTS.importers); renaming any of them breaks both callers — shared/polymath_shared/scientific_concept.py:89-136 [DERIVED]
- Evidence dict shape is load-bearing: keys `"contract"`, `"pattern"`, `"surface"`, plus optional `"head"` only on `technical_head_compound` — shared/polymath_shared/scientific_concept.py:134-136 [DERIVED]
- Documented placement contract: gate runs in `_interpret_v2` AFTER document-definition concept evidence and BEFORE generic classification — moving it changes which authority wins plurals and document-defined terms — shared/polymath_shared/scientific_concept.py:21-23 [DERIVED]
- `SCIENTIFIC_HEAD_LEMMAS` is an authored list to extend through policy only, never silently — shared/polymath_shared/scientific_concept.py:29-30 [DERIVED]
- Adding a month requires touching both `_MONTHS` and `_MONTH_NUM` — shared/polymath_shared/scientific_concept.py:41-42,140-142 [DERIVED]

## VERIFY
```verify
grep -Fq 'scientific-concept-evidence-v1' shared/polymath_shared/scientific_concept.py
grep -Fq 'SCIENTIFIC_HEAD_LEMMAS = frozenset({' shared/polymath_shared/scientific_concept.py
grep -Fq '_ACRONYM_RE = None' shared/polymath_shared/scientific_concept.py
test "$(grep -c -F 'scientific-concept-evidence-v1' shared/polymath_shared/scientific_concept.py)" -ge 8
grep -Eq 'def (named_concept_evidence|is_temporal_surface|normalize_temporal)\(' shared/polymath_shared/scientific_concept.py
! grep -Fq 'import requests' shared/polymath_shared/scientific_concept.py
```
