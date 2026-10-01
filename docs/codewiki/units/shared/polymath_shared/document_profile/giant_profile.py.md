# unit: shared/polymath_shared/document_profile/giant_profile.py
anchor: shared/polymath_shared/document_profile/giant_profile.py:1-515

## purpose
Deterministic, pure policy (no I/O, no model, no store — giant_profile.py:9) for profiling "giant" documents (>300 parents). Fixes the measured failure where `handbook.html` (802 parents) got a profile built from 5 samples that named nothing past the front matter (giant_profile.py:3-7). Produces: a section plan (`section_groups`), one LLM fingerprint per section (`build_section_fingerprint`), and a stratified document-level fingerprint (`build_giant_fingerprint`). The worker (`workers/workers/doc_profile_worker.py`) turns these into LLM calls and stored points; the audit scorer lives in `profile_coverage.py` (giant_profile.py:26-30).

## public surface
Importers (FACTS): `shared/polymath_shared/document_profile/profile_coverage.py`, `workers/workers/doc_profile_worker.py` — per-symbol use not distinguished.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `SectionGroup` | frozen dataclass | (ordinal, key, title, heading_path, parents, parent_ids, chars) -> SectionGroup; props `parent_count`, `content_hash()` | giant_profile.py:86-108 | — |
| `is_giant` | def | (parent_count: int, *, threshold: int = GIANT_PARENT_THRESHOLD) -> bool | giant_profile.py:111-113 | — |
| `clean_heading_segment` | def | (segment: Any) -> str | giant_profile.py:118-131 | — |
| `heading_key_path` | def | (heading_path: Any) -> tuple[str, ...] | giant_profile.py:134-149 | — |
| `section_key` | def | (path: Sequence[str]) -> str | giant_profile.py:152-156 | — |
| `parent_id_of` | def | (parent: dict, position: int) -> str | giant_profile.py:159-167 | — |
| `section_groups` | def | (parents, *, threshold=300, split_at=150, min_parents=3, max_profiles=72) -> list[SectionGroup] | giant_profile.py:264-319 | — |
| `plan_sections` | def | (parents, **kw) -> dict[str, Any] | giant_profile.py:322-336 | — |
| `document_title` | def | (document: dict) -> str | giant_profile.py:341-343 | — |
| `build_section_fingerprint` | def | (document, group, *, ordinal=None, total=None, budget_tokens=1000) -> _fp.DocumentFingerprint | giant_profile.py:346-364 | — |
| `stratified_samples` | def | (groups, signals, budget, *, max_passes=5, sample_tokens=45) -> list[tuple[int, str]] | giant_profile.py:377-422 | — |
| `build_giant_fingerprint` | def | (document, parents, groups, *, budget_tokens=2000) -> _fp.DocumentFingerprint | giant_profile.py:425-496 | — |
| `base_prompt_blocks` | def | (fp: _fp.DocumentFingerprint) -> tuple[str, str] | giant_profile.py:499-514 | — |

## contracts

**`section_groups`** (giant_profile.py:264-319)
- in: parent dicts; reads `heading_path`, `text`, `region_role`, `chunk_id`/`parent_id`/`chunk_index` (giant_profile.py:277, 172-183, 159-167)
- out: `list[SectionGroup]`, `ordinal` starts at 1 (giant_profile.py:319)
- pre: `[]` unless `len(parents) > threshold` (giant_profile.py:272-273); `[]` if no eligible parents (giant_profile.py:275-276)
- post: every eligible (non-noisy, non-empty) parent in exactly one group (giant_profile.py:270-271, 15-16); group order = first appearance (giant_profile.py:188-190)
- rules: group > `split_at` splits at next heading level up to `MAX_SPLIT_DEPTH = 3`, else positional parts `"<title> (part i of n)"` (giant_profile.py:236-247, 221-233); groups with `< min_parents` fold into predecessor, leading ones into the first real group (giant_profile.py:284-303); count capped at `max_profiles` by merging the smallest group into its smaller neighbour (giant_profile.py:304-318)

**`build_section_fingerprint`** (giant_profile.py:346-364)
- in: document dict + one `SectionGroup`
- out: `_fp.DocumentFingerprint` from `_fp.build_fingerprint(doc_like, list(group.parents), budget_tokens=1000)`, titled `"<doc> › <section>"`, subtitle `"section i of n of “<doc>”"` (giant_profile.py:353-361)
- post: `fp.sources` gains `scope="section"`, `section_key`, `section_title`, `section_parents`, `giant_profile="giant-profile-v1"` (giant_profile.py:362-363)

**`build_giant_fingerprint`** (giant_profile.py:425-496)
- pre: budget clamped to `[_fp.PROFILE_CONTEXT_BUDGET_MIN, _fp.PROFILE_CONTEXT_BUDGET_MAX]` (giant_profile.py:432)
- out: `DocumentFingerprint` with structure lines `"i. <title> (<count>)"` (giant_profile.py:420-421), coverage = stratified samples labelled `"[<ordinal>]"` (giant_profile.py:440-441, 413), framing = first signalled group's lead, synthesis = last group's last salient (tail-trimmed) (giant_profile.py:453-462), coverage budget = `budget - used_others` remainder (giant_profile.py:466-470)
- post: `sources` includes `structure_mode: "sections"`, `sections`, `sections_sampled`, `coverage_by_section` map; `builder_version="fingerprint-giant-v1"` (giant_profile.py:487-495)

**`stratified_samples`** (giant_profile.py:377-422)
- out: `(group_index, "[<ordinal>] <excerpt>")` in sampling order (giant_profile.py:413, 417)
- pass map: 0 → `sig[0]["lead"]`; 1 → `m // 2`; 2 → `m - 1`; 3 → `m // 4`; 4 → `(3 * m) // 4` (giant_profile.py:401-404)
- post: pass 0 cap `per_first = max(12, min(45, budget // n - label_cost))`; stops when `spent + cost > budget` (giant_profile.py:393, 415-416)

**`plan_sections`** (giant_profile.py:322-336)
- out: keys `version`, `threshold`, `parents`, `giant`, `sections` (rows: `ordinal`, `key`, `title`, `heading_path`, `parents`, `chars`) (giant_profile.py:326-335)

**`is_giant`** (giant_profile.py:111-113): strict `int(parent_count or 0) > int(threshold)`; 300 itself is not a giant.
**`section_key`** (giant_profile.py:155-156): `sha256("›".join(lower-cased path)).hexdigest()[:16]`.
**`parent_id_of`** (giant_profile.py:162-167): `chunk_id` → `parent_id` → `f"idx:{chunk_index or position}"` fallback.
**`base_prompt_blocks`** (giant_profile.py:499-514): renders `IDENTITY` / `OPENING` / `SAMPLE i` / `ENDING` / `KNOWN TERMS` blocks identical to the lean-context rendering so base and vNext paths see the same evidence (giant_profile.py:500-502).

## effect surface
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty) [DERIVED]
- Qdrant / store: none in this unit; per-section and document points are written by `doc_profile_worker.py` via `projection.project_profile(section=…)` and `profile_atom.source_tag("section", …)` (giant_profile.py:26-29) [DERIVED]
- Files / network / subprocess / env flags: none; module declares "pure: no I/O, no model, no store" (giant_profile.py:9) [DERIVED]
- Local stdlib import: `json` inside `heading_key_path` (giant_profile.py:140) [DERIVED]

## invariants
INVARIANT: GIANT_PARENT_THRESHOLD (300) > SECTION_SPLIT_PARENTS (150) > MIN_SECTION_PARENTS (3) — giant_profile.py:49-53 [DERIVED]
  fails-if: split/fold thresholds stop being nested; fold could dissolve all groups or split could never fire before the giant check.
INVARIANT: is_giant(300) == false (strict >) — giant_profile.py:113, 112 [DERIVED]
  fails-if: boundary documents at exactly 300 parents flip between profile modes.
INVARIANT: len(section_groups(...)) <= MAX_SECTION_PROFILES (72) — giant_profile.py:55, 305-318 [DERIVED]
  fails-if: more section profile points (and LLM calls) per document than the budget assumes (giant_profile.py:58-60).
INVARIANT: len(section_key(path)) == 16 hex chars — giant_profile.py:155-156 [DERIVED]
  fails-if: rebuilt sections duplicate their points instead of replacing them (giant_profile.py:152-154).
INVARIANT: sum(GIANT_ALLOCATION.values()) == 1.00 (0.06+0.22+0.06+0.46+0.06+0.14) — giant_profile.py:69-76 [DERIVED]
  fails-if: drift is hidden because `total_frac` normalization rescales silently (giant_profile.py:433-434).
INVARIANT: every eligible parent belongs to exactly one SectionGroup — giant_profile.py:271, 15-16 [DERIVED]
  fails-if: a parent in no group loses routing coverage; a parent in two groups double-counts `chars` and `parent_ids`.
INVARIANT: per_first >= STRATIFIED_MIN_SAMPLE_TOKENS (12) — giant_profile.py:393, 66 [DERIVED]
  fails-if: a section's only sample is trimmed below a usable signal.

## determinism & idempotency
determinism: DETERMINISTIC — no clock/random/uuid/network/db/env; only `hashlib.sha256` (giant_profile.py:34, 104-107, 155-156) [DERIVED]
idempotency: SAFE — pure functions; same parents → same groups, keys, fingerprints. Documented exception: positional part keys are NOT stable across a re-chunk, so a re-cut document must purge its orphan section points (giant_profile.py:223-224) [DERIVED]

## failure behaviour
- `heading_key_path`: `except Exception` around `json.loads` of a string heading → the string is treated as a one-element path `[hp]`; caller never sees the parse error (giant_profile.py:141-143) [DERIVED]
- No other handlers; no error codes raised in this unit (FACTS `fallbacks` has the single entry) [DERIVED]

## dumb-code flags
- Hard `5` in `range(min(max_passes, 5))` duplicates `STRATIFIED_MAX_PASSES = 5`; a caller passing `max_passes=7` silently gets 5 — giant_profile.py:406, 64 [DERIVED]
- `label_cost` is estimated from `f"[{n}] "` (n = section count) but actual labels are `f"[{g.ordinal}]"` — slight estimation drift — giant_profile.py:392 vs 413 [DERIVED]
- `+ 3` token padding duplicated at three sites — giant_profile.py:392, 414, 480 [DERIVED]
- Magic floor `max(4, ...)` per allocation sub-budget — giant_profile.py:434 [DERIVED]
- Magic truncation `[:16]` — giant_profile.py:156 [DERIVED]
- Two file-detection patterns: local `_FILE_LIKE_RE` (ext list) plus `_ctx._FILE_SEGMENT_RE` — duplicated concept — giant_profile.py:82, 127 [DERIVED]
- `n = total if total is not None else ordinal` then `n or '?'` — when both are None the identity prints `of ?` — giant_profile.py:353-354 [DERIVED]

## refactor notes
- `section_key` format (lower-case, `"›"` join, 16 hex) is the replace-on-rebuild contract for section points — changing it duplicates points instead of replacing them (giant_profile.py:152-156).
- Constants (300/150/3/72/3, budgets 1000/2000) are the tuning contract shared with `doc_profile_worker.py` and audited by `profile_coverage.py`; changing any of them changes the section plan and stored point count (giant_profile.py:26-30, 45-66).
- `sources` dict keys (`scope`, `section_key`, `section_title`, `giant_profile`, `coverage_by_section`, `builder_version`) feed the receipt chain / projection; renaming breaks receipts and stored-point scope tagging (giant_profile.py:362-363, 487-495, 26-29).
- `base_prompt_blocks` must keep rendering identical to the lean context's blocks — base path and vNext path must see the SAME sampled evidence (giant_profile.py:500-502).
- `GIANT_ALLOCATION` re-weighting shifts the coverage remainder: coverage = `budget - used_others` (giant_profile.py:466-470).
- Positional-part keys (`part i of n`) must never be treated as stable across re-chunks; orphan purge depends on this (giant_profile.py:221-224).

## VERIFY
```verify
grep -Fq 'GIANT_PARENT_THRESHOLD = 300' shared/polymath_shared/document_profile/giant_profile.py
grep -Fq 'MAX_SECTION_PROFILES = 72' shared/polymath_shared/document_profile/giant_profile.py
grep -Fq 'hexdigest()[:16]' shared/polymath_shared/document_profile/giant_profile.py
grep -Fq 'range(min(max_passes, 5))' shared/polymath_shared/document_profile/giant_profile.py
grep -Eq '"coverage": 0\.46' shared/polymath_shared/document_profile/giant_profile.py
test "$(grep -c -F 'STRATIFIED_MIN_SAMPLE_TOKENS' shared/polymath_shared/document_profile/giant_profile.py)" -ge 3
```
