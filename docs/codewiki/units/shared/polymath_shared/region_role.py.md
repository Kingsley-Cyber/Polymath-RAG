# unit: shared/polymath_shared/region_role.py
anchor: shared/polymath_shared/region_role.py:1-216

## purpose
Chunker-independent region classification: assigns every chunk a durable `region_role` so extraction, summaries and routing agree on prose vs structural noise — shared/polymath_shared/region_role.py:1-9 [DERIVED]. Pure, deterministic, cheap: heading-kind rules from `chunk_kind` (TOC/index/bibliography/front & back matter) plus text-shape rules headings cannot see (OCR garbage, index page-lists, legal boilerplate, log/packet dumps, question banks) — shared/polymath_shared/region_role.py:5-9 [DERIVED]. Built after measured waste on corpus cysa-study-v1: OCR-garbage pages and book-index pages were sent to the LLM and became routing summaries while `chunks.region_role` (migration 0037) stayed NULL — shared/polymath_shared/region_role.py:11-16 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `signals` | def | `(text: str) -> dict` | region_role.py:120-147 | — |
| `classify_region` | def | `(text: str \| None, heading_kind: str \| None = None) -> tuple[str, str]` | region_role.py:150-180 | — |
| `is_noise` | def | `(role: str \| None) -> bool` | region_role.py:183-184 | — |
| `is_summarizable` | def | `(role: str \| None) -> bool` | region_role.py:187-189 | — |
| `parent_role` | def | `(child_roles: list[str \| None]) -> tuple[str, str]` | region_role.py:192-208 | — |
| `contract_fingerprint` | def | `() -> dict` | region_role.py:211-216 | — |
| `REGION_CONTRACT` | const | `"region-role-v1"` | region_role.py:36 | — |
| `NOISE_ROLES` | const | frozenset of 10 role strings | region_role.py:53-57 | — |
| `NON_SUMMARY_ROLES` | const | `NOISE_ROLES \| frozenset({ROLE_OUTPUT, ROLE_CODE})` | region_role.py:61 | — |
| `THRESHOLDS` | const | dict of 11 thresholds | region_role.py:73-91 | — |

Module imported by: shared/polymath_shared/summary_compiler.py, workers/workers/intake_worker.py, workers/workers/llm_provider.py, workers/workers/profile_worker.py, workers/workers/summary_worker_impl.py, workers/workers/verify_worker.py (FACTS.importers). Per-symbol usage not in FACTS.

## contracts

**classify_region** — region_role.py:150-180
- in: `text` (None coerced to `""`), optional `heading_kind` from `workers.chunk_kind` — :154
- out: `(role, reason)`; role is one of the 14 `ROLE_*` strings — :38-51, :180
- post: decision order, first match wins: `words < MIN_WORDS` → stub; `heading_kind in _HEADING_NOISE_KINDS` → that kind; `heading_kind == ROLE_CODE` → code; `index_line_share >= 0.40` → index; `toc_line_share >= 0.30` → toc; `legal_markers >= 2 and words <= 250` → legal; `digit_share >= 0.35` → output; `symbol_share >= 0.06` → code; `common_share < 0.15 and mean_alpha_len < 4.5` → noise_ocr; `question_stems >= 2 or (question_marks_per_kchar >= 3.0 and question_stems >= 1)` → question_bank; else body — :157-180
- post: a stub check runs BEFORE heading checks — a <15-word chunk with `heading_kind="toc"` returns `("stub", ...)` — :157-160 [DERIVED]

**signals** — region_role.py:120-147
- in: any `str`; out: dict with keys `words, alpha_tokens, common_share, mean_alpha_len, symbol_share, digit_share, top_token_share, index_line_share, toc_line_share, legal_markers, question_stems, question_marks_per_kchar`; all ratios in [0, 1] — :121, :134-146
- post: never divides by zero — guards `or 1` (:125, :130), `if alpha_tokens else 0.0` (:128, :137-138), `max(1.0, ...)` (:133), `max(1, len(text))` (:139) — :125-139
- post: legal markers counted only over `text[:1500]` — :144

**is_noise** — region_role.py:183-184
- in: role or None; out: `bool(role) and role in NOISE_ROLES`; None and `""` both → False — :184

**is_summarizable** — region_role.py:187-189
- out: True when role is None (pre-hardening rows count as prose) or not in `NON_SUMMARY_ROLES` — :188-189

**parent_role** — region_role.py:192-208
- in: list of child roles (None → `ROLE_BODY`); out: `(role, reason)`
- post: empty list → `("stub", "no_children")` — :197-198; all children noise → most common child noise role, `"all_children_noise"` — :199-201; no summarizable children → most common non-noise role, `"no_summarizable_children"` — :202-204; strictly more than half of live children are question_bank → `("question_bank", "majority_question_bank")` — :205-207; else `("body", "has_prose_children")` — :208

**contract_fingerprint** — region_role.py:211-216
- out: `{"contract": REGION_CONTRACT, "min_words": MIN_WORDS, "thresholds": dict(sorted(...)), "noise_roles": sorted(NOISE_ROLES)}` — :214-215; hashed into extract contract identity so a threshold change forces re-extraction — :71-72, :212-213

## effect surface
No side effects. `tables_read`/`tables_written` empty in FACTS. No Qdrant, files, network, subprocess, or env flags. Imports only `re` and `collections.Counter` — region_role.py:33-34 [DERIVED].

## invariants

INVARIANT: `MIN_WORDS` = 15 (comment: same floor as `LLM_MIN_CHUNK_WORDS`) — region_role.py:69 [DERIVED]
  fails-if: chunks under 15 words become `ROLE_STUB` even when a heading says otherwise.
INVARIANT: `NON_SUMMARY_ROLES` = `NOISE_ROLES` ∪ {`output`, `code`} (exactly two additions) — region_role.py:61 [DERIVED]
  fails-if: log dumps and code listings would become routing-summary material.
INVARIANT: `common_share_noise` (0.15) < measured prose p10 (0.34); OCR garbage sits at 0.04–0.14 — region_role.py:74-78 [DERIVED]
  fails-if: raising the threshold misclassifies real prose as `noise_ocr`.
INVARIANT: `body` max observed `symbol_share` = 0.051 < `symbol_share_code` = 0.06 — region_role.py:83 [DERIVED]
  fails-if: tightening below 0.051 flags prose as code.
INVARIANT: question_bank majority test is strict — `2 * question_bank_count > len(live)` — region_role.py:206 [DERIVED]
  fails-if: at exactly 50% the parent falls through to `body`.
INVARIANT: fingerprint sorts `THRESHOLDS` and `NOISE_ROLES` before hashing — region_role.py:214-215 [DERIVED]
  fails-if: dict iteration order changes the hash and triggers spurious re-extraction.
INVARIANT: `is_summarizable(None)` = True — region_role.py:188-189 [DERIVED]
  fails-if: all pre-hardening NULL rows would be dropped from summaries.

## determinism & idempotency
determinism: DETERMINISTIC — pure string/regex computation, no clock/random/uuid/db/env/network (imports at region_role.py:33-34) [DERIVED]
idempotency: SAFE — no state, no I/O; same inputs give identical `(role, reason)` every call — region_role.py:120-216 [DERIVED]

## failure behaviour
No try/except anywhere in the unit; nothing is swallowed, no error codes raised. All division-by-zero paths are guarded in `signals` (`or 1`, `max(...)`, `if alpha_tokens else`) — region_role.py:125-139. Callers see only returned values, never exceptions, for any `str | None` input — region_role.py:154.

## dumb-code flags
- `THRESHOLDS: dict[str, float]` but holds int values `"legal_markers": 2`, `"legal_max_words": 250`, `"question_stems": 2` — annotation mismatch — region_role.py:73, :87-89.
- `signals` computes `top_token_share` (:128, :141) but `classify_region` never reads it — unused within this unit — region_role.py:150-180 [DERIVED].
- Magic slice `text[:1500]` limits legal-marker scan — region_role.py:144.
- `_TOC_LINE_RE` bundles two unrelated line formats in one pattern: dot-leader pages `\.{3,}\s*\d+\s*$` and markdown anchors `\[[^\]]{1,100}\]\(#[\w\-]+\)` — region_role.py:116.
- `is_noise("")` returns False because of the `bool(role)` guard — empty-string role silently treated as non-noise — region_role.py:184.
- Role strings double as `chunk_kind` heading strings; membership test `heading_kind in _HEADING_NOISE_KINDS` relies on exact string equality across modules — region_role.py:63-67, :159.

## refactor notes
- Renaming any `ROLE_*` string breaks stored `chunks.region_role` data (column since migration 0037) and all six importers — region_role.py:15-16, :38-51; FACTS.importers.
- Any change to `THRESHOLDS` or `MIN_WORDS` changes `contract_fingerprint` and must trigger re-extraction — region_role.py:71-72, :211-216.
- `_HEADING_NOISE_KINDS` and `heading_kind == ROLE_CODE` depend on `workers.chunk_kind` emitting identical strings — region_role.py:63-67, :159-162.
- `MIN_WORDS = 15` is coupled to `LLM_MIN_CHUNK_WORDS` elsewhere — region_role.py:69.
- `is_summarizable` NULL-as-prose semantics are load-bearing for pre-hardening rows; changing them alters summary coverage of the whole corpus — region_role.py:188-189.

## VERIFY

```verify
grep -Fq 'REGION_CONTRACT = "region-role-v1"' shared/polymath_shared/region_role.py
grep -Fq 'MIN_WORDS = 15' shared/polymath_shared/region_role.py
grep -Fq 'def classify_region(text: str | None, heading_kind: str | None = None) -> tuple[str, str]:' shared/polymath_shared/region_role.py
grep -Fq 'text[:1500]' shared/polymath_shared/region_role.py
test "$(grep -c -F 'NOISE_ROLES' shared/polymath_shared/region_role.py)" -ge 4
! grep -Fq 'import random' shared/polymath_shared/region_role.py
```
