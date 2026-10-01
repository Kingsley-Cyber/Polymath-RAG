# unit: shared/polymath_shared/document_region.py
anchor: shared/polymath_shared/document_region.py:1-239

## purpose
Deterministic document-role classifier: labels a chunk `body` / `front_matter` / `marketing` / `toc` / `index` / `bibliography` / `ocr_noise` / `unknown` from its TEXT ALONE, so default retrieval can demote boilerplate that beats real answers on cosine similarity (author bio 0.5955 vs correct objectives map 0.4894 on cysa-study-v1) — shared/polymath_shared/document_region.py:1-48. Classification is metadata only: it never alters child text, never deletes a chunk, never removes anything from the index — shared/polymath_shared/document_region.py:50-54. Consumed by 9 modules (FACTS.importers), including candidate_engine.py, hybrid.py, pass1.py, semantic_readiness.py.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `classify_region` | def | `(text: str) -> tuple[str, str]` (role, reason) | shared/polymath_shared/document_region.py:171-228 | 9 importers (FACTS.importers; per-symbol mapping not in FACTS) |
| `is_noisy` | def | `(role: str \| None) -> bool` | shared/polymath_shared/document_region.py:231-238 | 9 importers (FACTS.importers) |
| `CONTRACT` | const | `"document-region-v1"` | shared/polymath_shared/document_region.py:60 | 9 importers (FACTS.importers) |
| `NOISY_ROLES` | const | 7-tuple of demoted role strings | shared/polymath_shared/document_region.py:79-80 | 9 importers (FACTS.importers) |
| `RETRIEVABLE_ROLES` | const | `(ROLE_BODY, ROLE_UNKNOWN)` | shared/polymath_shared/document_region.py:85 | 9 importers (FACTS.importers) |
| `_has_answer_bearing_structure` | def (private) | `(text: str) -> bool` | shared/polymath_shared/document_region.py:163-164 | — (internal) |
| `_lines` | def (private) | `(text: str) -> list[str]` | shared/polymath_shared/document_region.py:167-168 | — (internal) |

Importers (FACTS): `shared/polymath_shared/_small-modules-1`, `candidate_engine.py`, `document_profile/fingerprint.py`, `document_profile/giant_profile.py`, `document_profile/parent_skeleton.py`, `document_status.py`, `hybrid.py`, `pass1.py`, `semantic_readiness.py`.

## contracts

**`classify_region(text)`** — shared/polymath_shared/document_region.py:171-228
- in: raw chunk text; `None`/empty tolerated via `raw = text or ""` (line 177).
- out: `(role, reason)`; role is one of the 8 `ROLE_*` strings (lines 63-70); reason is a literal tag, e.g. `"empty"`, `"ocr_fallback_placeholder"`, `"answer_bearing_structure_override"`, `"about_the_author_heading"`, `"credentials_plus_biographical_predicate"`, `"imprint_or_copyright_block"`, `"front_matter_section_opener"`, `"publisher_promotion_phrase"`, `"index_page_list_lines {h}/{n}"`, `"dot_leader_or_chapter_page_lines {h}/{n}"`, `"reference_entry_signals {k}"`, `"contents_heading_with_list_shape"`, `"default_body"` (lines 179-228).
- pre: none.
- post: unproven content returns `(ROLE_BODY, "default_body")` (line 228); empty text returns `(ROLE_UNKNOWN, "empty")` (lines 178-179); evaluation order fixed: OCR placeholder → structured-content override → bio → imprint → front heading → marketing → index → toc → bibliography → toc heading (lines 182-226).

**`is_noisy(role)`** — shared/polymath_shared/document_region.py:231-238
- in: role string or `None`.
- out: `role in NOISY_ROLES` (line 238).
- pre: none.
- post: `None` and `ROLE_UNKNOWN` are never noisy — legacy chunks ingested before this contract keep competing (lines 233-237).

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant / files / network / subprocess / env flags: none — only `import re` and `from __future__ import annotations` — shared/polymath_shared/document_region.py:56-58. Pure function module; demotion is applied elsewhere, not here — shared/polymath_shared/document_region.py:50-54.

## invariants
INVARIANT: structured-content hits >= `_MIN_STRUCTURED_HITS` = 2 forces ROLE_BODY before any boilerplate rule — shared/polymath_shared/document_region.py:159-160, 186-188 [DERIVED]
  fails-if: enumerated objectives-map chunks opening with marketing phrasing get demoted by `_MARKETING` (the exact failure the override exists to prevent, lines 150-158).
INVARIANT: index/TOC line ratio >= 0.45 and n >= 5 required — shared/polymath_shared/document_region.py:209, 214, 217 [DERIVED]
  fails-if: prose with incidental trailing numbers is mislabelled TOC/INDEX and demoted.
INVARIANT: bibliography requires ref_signals >= 4 — shared/polymath_shared/document_region.py:222 [DERIVED]
  fails-if: body prose citing one arXiv/DOI reference is demoted as bibliography.
INVARIANT: `NOISY_ROLES` has 7 entries including BOTH `"ocr_noise"` and alias `"noise_ocr"` — shared/polymath_shared/document_region.py:78-80 [DERIVED]
  fails-if: chunker-spelled `noise_ocr` chunks (121 cinema children, measured 2026-09-07, lines 75-77) stop being demoted.
INVARIANT: `RETRIEVABLE_ROLES` == `(ROLE_BODY, ROLE_UNKNOWN)` — shared/polymath_shared/document_region.py:85 [DERIVED]
  fails-if: an empty/failed classifier suppresses a corpus (lines 82-84).
INVARIANT: `is_noisy(None)` == False — shared/polymath_shared/document_region.py:238 [DERIVED] (`None` not in the tuple)
INVARIANT: empty text -> `(ROLE_UNKNOWN, "empty")` — shared/polymath_shared/document_region.py:178-179 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — pure regex/text functions; no clock, random, uuid, network, db, or env reads (only `import re`, shared/polymath_shared/document_region.py:58).
idempotency: SAFE — no writes; classification "never alters child text, never deletes a chunk, and never removes anything from the index" — shared/polymath_shared/document_region.py:50-54.

## failure behaviour
No try/except handlers exist in the module; no error codes raised. All degenerate inputs resolve to returned values, not exceptions: empty/None text -> `(ROLE_UNKNOWN, "empty")` — shared/polymath_shared/document_region.py:177-179; OCR placeholder -> `(ROLE_OCR_NOISE, "ocr_fallback_placeholder")` — shared/polymath_shared/document_region.py:182-183; everything unproven -> `(ROLE_BODY, "default_body")` — shared/polymath_shared/document_region.py:228. Callers always receive a 2-tuple.

## dumb-code flags
- Threshold `0.45` duplicated as bare literals at lines 214 and 217 — no named constant.
- Line-count gate `n >= 5` duplicated at lines 209 and 225.
- Magic number `4` for bibliography ref_signals — shared/polymath_shared/document_region.py:222.
- Dual spelling of the OCR-noise role: `ROLE_OCR_NOISE = "ocr_noise"` (line 69) vs `ROLE_NOISE_OCR_ALIAS = "noise_ocr"` (line 78); comment attributes the alias to the chunker's `region_role.ROLE_NOISE_OCR` spelling — shared/polymath_shared/document_region.py:75-78.
- Magic window `{0,60}` in `_BIO_PREDICATE` — shared/polymath_shared/document_region.py:95.
- Markdown-heading assumptions baked into heading regexes (`#{0,6}`, `\s{0,3}`) — shared/polymath_shared/document_region.py:98-99, 123-125, 133-134.

## refactor notes
- Role string values (`"body"`, `"front_matter"`, `"marketing"`, `"toc"`, `"index"`, `"bibliography"`, `"ocr_noise"`, `"unknown"`, `"noise_ocr"`) are contract values consumed by 9 importers (FACTS.importers); renaming any breaks them — shared/polymath_shared/document_region.py:63-70, 78.
- `classify_region` returns a 2-tuple; arity or ordering change breaks unpacking callers — shared/polymath_shared/document_region.py:171.
- Rule ORDER is behaviour: the structured-content override must run before boilerplate rules ("Runs before them, never after", lines 185-188) and INDEX must run before TOC (index entries shadowed by the looser TOC rule, lines 210-212). Reordering changes labels.
- Do not drop `ROLE_NOISE_OCR_ALIAS` from `NOISY_ROLES` — chunker-spelled `"noise_ocr"` chunks would stop being demoted — shared/polymath_shared/document_region.py:75-80.
- APPENDIX is deliberately not a suppressed role; technical appendices carry objectives maps, port tables, command references — adding suppression would remove answers — shared/polymath_shared/document_region.py:45-48.
- End-anchors in `_FRONT_HEADING` are adversarial-suite-tested ("Preface attacks manipulate the leading bytes..." must NOT match) — loosening them reintroduces false suppression — shared/polymath_shared/document_region.py:118-125.

## VERIFY
```verify
grep -Fq 'CONTRACT = "document-region-v1"' shared/polymath_shared/document_region.py
grep -Fq '_MIN_STRUCTURED_HITS = 2' shared/polymath_shared/document_region.py
grep -Fq 'ROLE_NOISE_OCR_ALIAS = "noise_ocr"' shared/polymath_shared/document_region.py
grep -Eq 'idx_hits / n >= 0\.45' shared/polymath_shared/document_region.py
grep -Fq 'RETRIEVABLE_ROLES = (ROLE_BODY, ROLE_UNKNOWN)' shared/polymath_shared/document_region.py
! grep -Fq 'ROLE_APPENDIX' shared/polymath_shared/document_region.py
test "$(grep -c -F 'ROLE_FRONT_MATTER' shared/polymath_shared/document_region.py)" -ge 3
```
