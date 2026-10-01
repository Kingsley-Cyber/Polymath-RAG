# unit: shared/polymath_shared/document_profile/fingerprint.py
anchor: shared/polymath_shared/document_profile/fingerprint.py:1-417

## purpose
Builds the vNext deterministic global-profile INPUT (`DocumentFingerprint`) that the global-profile LLM sees — successor to `context.py`'s `lean-context-v1` ~500-token block (fingerprint.py:8-9). Six surfaces (identity, structure, framing, coverage, synthesis, vocabulary) with `coverage` the largest; adaptive 500–2,000 tokens, 2,000 a ceiling never padding (fingerprint.py:11, 24-25). Pure deterministic policy, no I/O/model/network (fingerprint.py:27). Module imported by `giant_profile.py`, `workers/workers/doc_profile_worker.py`, `document_profile/_small-modules` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_fingerprint` | def | (document: dict, parents: Sequence[dict], *, budget_tokens=500, allocation=None, extra_terms=()) -> DocumentFingerprint | fingerprint.py:321-417 | giant_profile.py; doc_profile_worker.py; _small-modules (module importers) |
| `DocumentFingerprint` | dataclass | fields: title, identity, structure, framing, coverage, synthesis, vocabulary, budget_tokens, allocation, used_tokens, sources, builder_version | fingerprint.py:236-252 | same importers |
| `DocumentFingerprint.used_total` | property | () -> int (sum of used_tokens) | fingerprint.py:254-256 | — |
| `DocumentFingerprint.structure_block` | property | () -> str ("\n".join(structure)) | fingerprint.py:258-260 | — |
| `DocumentFingerprint.render_block` | property | () -> str (DOCUMENT block for the profile prompt) | fingerprint.py:262-281 | — |
| `DocumentFingerprint.to_dict` | method | () -> dict[str, Any] | fingerprint.py:283-297 | — |
| `DocumentFingerprint.input_hash` | method | (content_hash: str = "") -> str (sha256 hex) | fingerprint.py:299-318 | — |
| `FINGERPRINT_BUILDER_VERSION` | const | `"fingerprint-v1"` | fingerprint.py:60 | — |
| `PROFILE_CONTEXT_BUDGET_MIN` / `_MAX` | const | `500` / `2000` | fingerprint.py:63-64 | — |
| `DEFAULT_BUDGET_TOKENS` | const | `500` | fingerprint.py:70 | — |
| `DEFAULT_ALLOCATION` | const | identity 0.08, structure 0.20, framing 0.12, coverage 0.36, synthesis 0.12, vocabulary 0.12 | fingerprint.py:77-84 | — |
| `COVERAGE_EXCERPT_TOKENS` | const | `56` | fingerprint.py:89 | — |
| `SOURCE_ANCHORED_FIELDS` | const | `("ONE", "SUMMARY", "TOPIC", "TERM", "Q")` | fingerprint.py:96 | future prompt/compiler change (fingerprint.py:38-41) |
| `RESEARCH_INDEX_TAGS` | const | `("LATENT-PATTERN", "ANCHOR", "RECALLQ", "TENSION", "BRIDGE", "INVERSION", "BOUNDARY")` | fingerprint.py:100-102 | future prompt/compiler change (fingerprint.py:38-41) |
| `ROUTING_INFERRED_FIELDS` | const | `("SEARCH", "THEORY", "CONCEPT", "SEEALSO") + RESEARCH_INDEX_TAGS` | fingerprint.py:105-107 | future prompt/compiler change |

## contracts

### build_fingerprint (fingerprint.py:321-417)
- in: `document` = {source_name, media_type, frontmatter?, doc_id?, content_hash?} — fingerprint.py:331 [DERIVED]
- in: `parents` = rows {heading_path, text, region_role, chunk_index/char_start} in ANY order; `chunk_id` NOT required — fingerprint.py:332-334; ordering fixed by sort on (source position, text) in `_eligible_body` — fingerprint.py:138 [DERIVED]
- pre: `budget = max(PROFILE_CONTEXT_BUDGET_MIN, min(int(budget_tokens), PROFILE_CONTEXT_BUDGET_MAX))` — fingerprint.py:337 [DERIVED]
- pre: allocation merged over `DEFAULT_ALLOCATION`, normalized: `sub[k] = max(4, int(round(budget * v / total_frac)))` — fingerprint.py:338-342 [DERIVED]
- pre: noisy/empty parents filtered by `document_region.is_noisy` (single furniture authority) — fingerprint.py:131-133 [DERIVED]
- post: title = `frontmatter.title` else `_ctx.clean_title(source_name)`; identity joins title + subtitle/author/authors/organization/publisher/type/document_type + `format: <media_type suffix>` with `" · "`, trimmed to `sub["identity"]` — fingerprint.py:344-354 [DERIVED]
- post: coverage computed LAST with `coverage_budget = max(0, budget - used_others)` — fingerprint.py:377-387 [DERIVED]
- post: `used_tokens` per surface; `est+1` per structure line and vocab term, `est+3` per coverage excerpt — fingerprint.py:389-396 [DERIVED]
- post: `sources` = {parents, body_parents, heading_paths, structure_mode ("headings" if >2 heading lines else "positions"), coverage_samples, media_type, title_source} — fingerprint.py:408-416 [DERIVED]
- out: `DocumentFingerprint` — fingerprint.py:397 [DERIVED]

### DocumentFingerprint.render_block (fingerprint.py:262-281)
- out: non-empty surfaces in order IDENTITY, STRUCTURE, FRAMING, COVERAGE (numbered `COVERAGE {i}:`, 1-based), SYNTHESIS, VOCABULARY; joined `"\n\n"` — fingerprint.py:265-281 [DERIVED]

### DocumentFingerprint.input_hash (fingerprint.py:299-318)
- in: `content_hash` (document's content hash), default `""` — fingerprint.py:299 [DERIVED]
- out: sha256 hex of JSON {builder, content_hash, identity, structure, framing, coverage, synthesis, vocabulary, allocation} with `sort_keys=True, ensure_ascii=False`; mirrors `context.DocumentContext.input_hash` — fingerprint.py:301-318 [DERIVED]

### _select_vocabulary (fingerprint.py:191-232)
- out order: exact identifiers (first-seen, capped at `budget // 2`) → key terms ranked `(-cross-parent freq, term)` → deduped `extra_terms`; dedup is case-insensitive against terms+identifiers — fingerprint.py:194-231 [DERIVED]

## effect surface
- Postgres: none (FACTS `tables_read`/`tables_written` empty).
- Qdrant / files / network / subprocess / env flags: none — "no I/O, no model, no network" — fingerprint.py:27; imports are stdlib (`hashlib`, `json`, `collections`, `dataclasses`, `typing`) plus `polymath_shared` modules only — fingerprint.py:45-54 [DERIVED]

## invariants
INVARIANT: clamped budget ∈ [500, 2000] — fingerprint.py:337, 63-64 [DERIVED]
  fails-if: caller budgets (e.g. 10000 or 100) are silently clamped; tests asserting raw pass-through break.
INVARIANT: DEFAULT_ALLOCATION["coverage"] = 0.36 > next-largest DEFAULT_ALLOCATION["structure"] = 0.20 — fingerprint.py:77-84 [DERIVED]
  fails-if: coverage stops being the largest surface; whole-document sampling shrinks below the heading stride.
INVARIANT: sum(DEFAULT_ALLOCATION.values()) = 1.00 (0.08+0.20+0.12+0.36+0.12+0.12) — fingerprint.py:77-84 [INFERRED — arithmetic on the six literals]
  fails-if: caller passing absolute-token intuitions gets silently rescaled by `total_frac` at fingerprint.py:341.
INVARIANT: coverage sample count ≤ max(1, min(n_parents, budget // 56)) — fingerprint.py:176 [DERIVED]
  fails-if: per-excerpt real cost exceeds the 56-token estimate and `render_block` overruns the profile budget.
INVARIANT: `_even_indices(n, k)` always contains 0 and n−1 for n ≥ 2, k ≥ 2 — fingerprint.py:111-113, 120 [DERIVED]
  fails-if: first/last eligible parents never sampled — the no-first-400-bias guarantee (fingerprint.py:111-113, 13-16) is lost at the tail.
INVARIANT: identifier spend ≤ vocabulary budget // 2 — fingerprint.py:219-225 [DERIVED]
  fails-if: exact identifiers crowd key terms out of VOCABULARY.
INVARIANT: `used_tokens["coverage"]` counts est_tokens(x)+3 per excerpt, matching the "COVERAGE N:" label rendered at fingerprint.py:275 — fingerprint.py:393 [DERIVED]
  fails-if: accounting drifts from the rendered block's true token cost.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of inputs; no clock/random/uuid/network/db/env (fingerprint.py:27, 45-54); `input_hash` sorts keys (fingerprint.py:315).
idempotency: SAFE — no state or side effects; identical inputs yield identical `to_dict()` and `input_hash`.

## failure behaviour
- No `try`/`except` anywhere in the unit; nothing swallowed; raw exceptions propagate to the caller. [DERIVED — full SOURCE scan]
- Degenerate inputs yield empties, not errors: `_even_indices` → `[]` when n ≤ 0, `[0]` when k ≤ 1 — fingerprint.py:114-119; `_select_coverage` → `[]` when `per` empty or budget ≤ 0 — fingerprint.py:173-174; `_select_vocabulary` → `[]` when budget ≤ 0 — fingerprint.py:198-199; empty eligible body → `framing = ""` and `synthesis = ""` — fingerprint.py:365-372 [DERIVED]
- No error codes raised. [DERIVED]

## dumb-code flags
- Magic calibration: `COVERAGE_EXCERPT_TOKENS = 56` ≈ 45 tokens + label, "Deliberately a touch high" — fingerprint.py:86-89 [DERIVED]
- Three ad-hoc per-item overheads: `+3` coverage label (fingerprint.py:183, 393), `+1` structure line (fingerprint.py:381, 391), `+1` vocab term (fingerprint.py:227, 231, 384, 395) [DERIVED]
- First coverage excerpt bypasses the budget check: `if out and spent + cost > budget: break` — with empty `out` it appends even when `cost > budget` — fingerprint.py:184-186 [DERIVED]
- `DEFAULT_BUDGET_TOKENS = 500` equals `PROFILE_CONTEXT_BUDGET_MIN = 500`; the lower clamp is a no-op at default — fingerprint.py:63, 70, 337 [DERIVED]
- `sub` floor `max(4, ...)` never binds under `DEFAULT_ALLOCATION` at min budget (smallest surface = round(500×0.08) = 40); only relevant for caller fractions < 0.008 — fingerprint.py:342 [INFERRED — floor vs 500-budget arithmetic]
- `_even_indices` can return fewer than k indices on round collisions (set union) — k is an upper bound — fingerprint.py:120 [DERIVED]
- `SOURCE_ANCHORED_FIELDS` / `RESEARCH_INDEX_TAGS` / `ROUTING_INFERRED_FIELDS` declared but unused inside this module — exported for a future owner-gated prompt/compiler change — fingerprint.py:36-41, 91-107 [DERIVED]
- "COVERAGE" label spelling duplicated between the `+3` cost assumption (fingerprint.py:183) and the render f-string `f"COVERAGE {i}: {c}"` (fingerprint.py:275) [DERIVED]

## refactor notes
- Importers: `document_profile/giant_profile.py`, `workers/workers/doc_profile_worker.py`, `document_profile/_small-modules` (FACTS.importers) — signature or return-type changes to `build_fingerprint`/`DocumentFingerprint` blast to all three.
- Private cross-module dependencies: `_ctx.est_tokens/_trim_tokens/_stride_select/structure_lines/clean_title` (fingerprint.py:56, 345, 354, 360-361, 367, 372); `_ps.normalize_whitespace/_normalize_heading/_source_position/_word_tokens/_heading_tokens/document_frequency/select_key_terms/select_salient_excerpt/select_lead_excerpt/extract_identifiers` (fingerprint.py:132-162); `document_region.is_noisy/ROLE_UNKNOWN` (fingerprint.py:131, 133). Renaming any of these breaks this file. [DERIVED]
- `FINGERPRINT_BUILDER_VERSION` feeds `input_hash` (fingerprint.py:305); bumping it changes every fingerprint hash — versions tracked separately so effects do not couple into unrelated rebuilds (fingerprint.py:58-60). [DERIVED]
- `RESEARCH_INDEX_TAGS` is the version-pinned single source of truth for the upcoming `prompt.py` + `compiler.py` change — moving it requires updating that consumer (fingerprint.py:38-41, 100-102). [DERIVED]
- Dropping the legacy `document_summaries.major_concepts` reader in `workers/workers/doc_profile_worker.py` is repo S8 and is NOT done here — this slice only makes it safe (fingerprint.py:20-22). [DERIVED]

## VERIFY
```verify
grep -Fq 'FINGERPRINT_BUILDER_VERSION = "fingerprint-v1"' shared/polymath_shared/document_profile/fingerprint.py
grep -Fq 'DEFAULT_BUDGET_TOKENS = 500' shared/polymath_shared/document_profile/fingerprint.py
grep -Fq 'COVERAGE_EXCERPT_TOKENS = 56' shared/polymath_shared/document_profile/fingerprint.py
grep -Fq 'ident_budget = budget // 2' shared/polymath_shared/document_profile/fingerprint.py
grep -Fq '"coverage": 0.36,' shared/polymath_shared/document_profile/fingerprint.py
! grep -Fq 'import random' shared/polymath_shared/document_profile/fingerprint.py
test "$(grep -c -F 'est_tokens' shared/polymath_shared/document_profile/fingerprint.py)" -ge 8
```
