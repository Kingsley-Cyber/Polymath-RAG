# unit: shared/polymath_shared/document_profile/profile_coverage.py
anchor: shared/polymath_shared/document_profile/profile_coverage.py:1-202

## purpose
FACET-RETRIEVAL-V1 F4 profile-coverage audit scorer: scores every retrieval profile against its document (top-term coverage + section-title coverage) and lists the worst — profile_coverage.py:1-3 [DERIVED]. Pure policy, no I/O; the script `scripts/profile_audit.py` loads a library read-only and calls this — profile_coverage.py:5 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| tokens | def | (text: str) -> list[str] | profile_coverage.py:34-36 | — |
| document_term_counts | def | (parent_texts: Iterable[str]) -> Counter | profile_coverage.py:48-52 | — |
| document_terms | def | (parent_texts, *, doc_freq=None, n_docs=1, top=TOP_TERMS) -> list[tuple[str, float]] | profile_coverage.py:55-69 | — |
| library_doc_freq | def | (docs_parent_texts) -> tuple[Counter, int] | profile_coverage.py:72-79 | — |
| section_titles | def | (parents: Sequence[dict]) -> list[str] | profile_coverage.py:82-95 | — |
| flatten_compiled | def | (compiled: dict \| None) -> str | profile_coverage.py:98-106 | — |
| flatten_retrieval_profile | def | (rp: dict \| None) -> str | profile_coverage.py:109-121 | — |
| CoverageReport | class | dataclass; to_dict() -> dict[str, Any] | profile_coverage.py:125-140 | — |
| coverage | def | (top_terms, titles, profile_text: str) -> CoverageReport | profile_coverage.py:143-176 | — |
| audit_document | def | (parents, *, profile_texts, doc_freq=None, n_docs=1, top=50, threshold=_gp.GIANT_PARENT_THRESHOLD, section_profiles=0) -> dict[str, Any] | profile_coverage.py:179-195 | — |
| worst | def | (rows, *, n=10, key="score") -> list[dict[str, Any]] | profile_coverage.py:198-201 | — |

Only named caller in material: `scripts/profile_audit.py` (module docstring) — profile_coverage.py:5 [DERIVED]. `_stem` (profile_coverage.py:39-45) is private.

## contracts

**document_terms** — profile_coverage.py:55-69
- in: parent text strings; optional library-wide `doc_freq` Counter and `n_docs`.
- pre: `doc_freq=None` ⇒ idf computed over this document's own parents via `_ps.document_frequency` — profile_coverage.py:63-66 [DERIVED].
- out: top `top` terms as `(term, weight)` where weight = tf × `_ps.idf(max(1, n_docs), doc_freq.get(t, 0))`, rounded to 3 — profile_coverage.py:58,69 [DERIVED].
- post: empty tf ⇒ `[]` — profile_coverage.py:61-62 [DERIVED]; order is weight desc, term asc — profile_coverage.py:59,68 [DERIVED].

**coverage** — profile_coverage.py:143-176
- in: `top_terms` as `(term, weight)` tuples or plain strings — profile_coverage.py:150-151 [DERIVED]; `titles`; `profile_text` (empty allowed).
- pre: none.
- out: `CoverageReport`; a term matches on exact or `_stem` membership in the profile token set — profile_coverage.py:149,153-154 [DERIVED]; a title matches when `hit / len(words) >= TITLE_MATCH_SHARE` (0.6) — profile_coverage.py:156-157,31 [DERIVED]; `score = TERM_WEIGHT * term_share + TITLE_WEIGHT * title_share`, or `term_share` alone when there are no titles — profile_coverage.py:168-172 [DERIVED]; shares/score rounded to 4 — profile_coverage.py:173-174 [DERIVED].
- post: empty profile scores 0 — profile_coverage.py:147 [DERIVED].

**audit_document** — profile_coverage.py:179-195
- in: parent dicts read via `p.get("text")` and `p.get("heading_path")` — profile_coverage.py:184,87 [DERIVED].
- out: dict with keys `parents`, `giant` (`_gp.is_giant(len(parents), threshold=threshold)`), `section_profiles`, `giant_without_sections` (`giant and section_profiles <= 0`), `top_terms`, `titles`, `reports` (one `to_dict()` per named profile text), `score` = max report score or 0.0 — profile_coverage.py:184-195 [DERIVED].

**worst** — profile_coverage.py:198-201
- out: `n` rows sorted by `(score asc, -parents, source_name)` — profile_coverage.py:200-201 [DERIVED].
- pre: rows may lack `source_name`; `.get(...) or ""` tolerates it — profile_coverage.py:200-201 [DERIVED].

**section_titles** — profile_coverage.py:82-95: distinct top-level titles (first element of `_gp.heading_key_path`) in document order, deduped case-insensitively — profile_coverage.py:84-94 [DERIVED].

**flatten_compiled / flatten_retrieval_profile** — profile_coverage.py:98-121: `None` ⇒ `""`; string values and list/tuple items joined with `\n` — profile_coverage.py:99,101-106,111-112 [DERIVED]. `flatten_retrieval_profile` reads exactly the 8 keys `semantic_summary`, `primary_domains`, `secondary_domains`, `core_concepts`, `methods`, `problems_addressed`, `use_for_questions_about`, `connects_to_domains` — profile_coverage.py:114-115 [DERIVED].

**CoverageReport.to_dict** — profile_coverage.py:136-140: stamps `"version": COVERAGE_VERSION` (`"profile-coverage-v1"`) — profile_coverage.py:137,26 [DERIVED].

## effect surface
None. Pure policy, no I/O — profile_coverage.py:5 [DERIVED]. FACTS report `tables_read: []`, `tables_written: []`; no file, network, subprocess, or env access appears in SOURCE. Only imports are stdlib (`Counter`, `Iterable`/`Sequence`, `dataclass`/`field`, `Any`) and siblings `giant_profile`/`parent_skeleton` — profile_coverage.py:17-24 [DERIVED].

## invariants
INVARIANT: TERM_WEIGHT + TITLE_WEIGHT == 1.0 (0.6 + 0.4), keeping `score` in [0, 1] — profile_coverage.py:12-13,28-29 [DERIVED]
  fails-if: weights no longer sum to 1 ⇒ score range leaves [0,1] and cross-document comparisons break.
INVARIANT: TITLE_MATCH_SHARE == 0.6 (share of a title's content words required) — profile_coverage.py:31,157 [DERIVED]
  fails-if: raising it marks partially-covered titles missing; lowering it inflates title_share.
INVARIANT: audit row `score` == max over `reports[*].score` (0.0 when no reports) — profile_coverage.py:194 [DERIVED]
  fails-if: switching to min/mean changes which documents `worst` surfaces.
INVARIANT: `_stem` strips a suffix only when `len(t) > len(suf) + 3`; suffix order is `("ing", "ies", "es", "s")` — profile_coverage.py:42-44 [DERIVED]
  fails-if: reordering suffixes or relaxing the length guard changes stem matches (e.g. "cats", len 4, fails `4 > 1+3` and stays unstemmed, so it will not stem-match "cat") — profile_coverage.py:43 [INFERRED: length arithmetic applied to a concrete word].
INVARIANT: `document_terms` order is weight desc then term asc — profile_coverage.py:59,68 [DERIVED]
  fails-if: nondeterministic tie order breaks diffable audit output.
INVARIANT: `worst` tie-break is `-parents` then `source_name` string — profile_coverage.py:200-201 [DERIVED]
  fails-if: bigger documents stop surfacing first among equal scores.

## determinism & idempotency
determinism: DETERMINISTIC (no clock/random/uuid/network/db/env constructs anywhere in SOURCE; docstrings assert determinism at profile_coverage.py:60 and :147)
idempotency: SAFE (pure functions over their arguments; no state written — profile_coverage.py:5 [DERIVED])

## failure behaviour
No try/except or raised error codes anywhere in SOURCE. None/missing-key tolerance instead: `flatten_compiled(None)` ⇒ `""` (`compiled or {}`) — profile_coverage.py:99; `flatten_retrieval_profile(None)` ⇒ `""` — profile_coverage.py:111-112; parent dicts read with `.get("text")` / `.get("heading_path")` — profile_coverage.py:184,87; `worst` reads `r.get(key) or 0.0` and `r.get("source_name") or ""` — profile_coverage.py:200-201 [all DERIVED].

## dumb-code flags
- Literal `0.6` plays two unrelated roles: `TERM_WEIGHT` (line 28) and `TITLE_MATCH_SHARE` (line 31) — profile_coverage.py:28,31 [DERIVED]. Editing one "0.6" wrongly changes the other policy.
- Mixed rounding granularity: term weights round to 3 (line 69), coverage shares/score round to 4 (lines 173-174) — profile_coverage.py:69,173-174 [DERIVED].
- `coverage` accepts dual input shapes for `top_terms` (tuples or strings) — profile_coverage.py:150-151 [DERIVED].
- `audit_document` output has no `source_name` key, but `worst` sorts on `r.get("source_name")` — profile_coverage.py:189-194,200-201 [DERIVED]; the caller must attach it [INFERRED: no other source of that key exists in this file].
- `title_share` is `float | None` and `to_dict` emits the `None` verbatim for title-less documents — profile_coverage.py:127,138,168-169 [DERIVED].
- `_stem` special case `+"y"` only for the `"ies"` suffix — profile_coverage.py:44 [DERIVED].

## refactor notes
- Private cross-module dependencies; renaming any of these in siblings breaks this file: `_ps._word_tokens` (line 36), `_ps.document_frequency` (line 66), `_ps.idf` (line 67), `_gp.heading_key_path` (line 87), `_gp.GIANT_PARENT_THRESHOLD` (line 180), `_gp.is_giant` (line 189) — profile_coverage.py:36,66-67,87,180,189 [DERIVED].
- `COVERAGE_VERSION = "profile-coverage-v1"` is stamped into every `to_dict()` output; consumers may gate on it — profile_coverage.py:26,137 [DERIVED].
- The 8-key list in `flatten_retrieval_profile` mirrors the `documents.retrieval_profile` (document-summary-v1) schema; a schema change requires updating that list — profile_coverage.py:110,114-115 [DERIVED].
- Named caller `scripts/profile_audit.py` loads the library and drives `audit_document`/`worst`; changing the audit-row dict shape (e.g. renaming `score` or `parents`) changes what that script prints — profile_coverage.py:5,189-195 [INFERRED: docstring names the script as the driver].
- `TOP_TERMS = 50` is the default for both `document_terms` and `audit_document`; changing the constant shifts every audit score — profile_coverage.py:27,56,181 [DERIVED].

## VERIFY
```verify
grep -Fq 'COVERAGE_VERSION = "profile-coverage-v1"' shared/polymath_shared/document_profile/profile_coverage.py
grep -Fq 'TITLE_MATCH_SHARE = 0.6' shared/polymath_shared/document_profile/profile_coverage.py
grep -Fq 'score = TERM_WEIGHT * term_share + TITLE_WEIGHT * title_share' shared/polymath_shared/document_profile/profile_coverage.py
grep -Fq 'scripts/profile_audit.py' shared/polymath_shared/document_profile/profile_coverage.py
grep -Fq 'semantic_summary' shared/polymath_shared/document_profile/profile_coverage.py
! grep -Fq 'import random' shared/polymath_shared/document_profile/profile_coverage.py
test "$(grep -c -F 'def ' shared/polymath_shared/document_profile/profile_coverage.py)" -ge 10
```
