# unit: shared/polymath_shared/evidence_utility.py
anchor: shared/polymath_shared/evidence_utility.py:1-217

## purpose
Deterministic marginal-utility selection of the HYBRID evidence set; sole importer is `shared/polymath_shared/hybrid.py` (FACTS.importers). Intervenes at two points fixed by the module docstring: `utility_cut` at the pre-rerank truncation and `latent_competition` after G3 — HYBRID cuts BEFORE the reranker — shared/polymath_shared/evidence_utility.py:16-32 [DERIVED]. Treats two measured diseases: parent saturation (mean max-from-one-parent 3.6, worst 8/10) and latent displacement; the redundancy veto ships as a cheap guard only, fact/entity novelty deferred — shared/polymath_shared/evidence_utility.py:7-14 [DERIVED]. Never re-scores relevance and never reorders by its own score; the cross-encoder stays sole relevance authority — shared/polymath_shared/evidence_utility.py:34-39 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `derive_requirements` | def | (query: str) -> list[set[str]] | shared/polymath_shared/evidence_utility.py:66-78 | shared/polymath_shared/hybrid.py |
| `utility_cut` | def | (candidates: list[dict], limit: int, *, reserved: int, rescue_arrivals: tuple[str, ...], requirements: list[set[str]] \| None = None, parent_saturation: int = 2, redundancy_veto: float = 0.6, lookahead: int = 12, annotations=None) -> tuple[list[dict], dict] | shared/polymath_shared/evidence_utility.py:87-95 | shared/polymath_shared/hybrid.py |
| `latent_competition` | def | (candidates: list[dict], *, latent_arrival: str, margin: float = 0.05) -> tuple[list[dict], dict] | shared/polymath_shared/evidence_utility.py:181-183 | shared/polymath_shared/hybrid.py |
| `_content_tokens` | def | (text: str) -> set[str] | shared/polymath_shared/evidence_utility.py:61-63 | — (private) |
| `_jaccard` | def | (a: set[str], b: set[str]) -> float | shared/polymath_shared/evidence_utility.py:81-84 | — (private) |

## contracts

### derive_requirements — shared/polymath_shared/evidence_utility.py:66-78
- in: one query string.
- out: list of content-token sets, one per qualifying clause; `[]` when fewer than 2 clauses qualify — shared/polymath_shared/evidence_utility.py:78 [DERIVED].
- pre: none (pure string work).
- post: every token matches `[a-z0-9][a-z0-9_-]+`, is not in `_STOPWORDS`, and has `len(t) > 2` — shared/polymath_shared/evidence_utility.py:61-63 [DERIVED]; a clause qualifies with ≥2 content tokens OR a `_REQ_CUE_RE` hit plus ≥1 token — shared/polymath_shared/evidence_utility.py:76 [DERIVED].

### utility_cut — shared/polymath_shared/evidence_utility.py:87-178
- in: relevance-ordered candidate dicts (keys read: `arrival`, `text`, `parent_id`, `chunk_id`), `limit`, seat policy.
- out: `(out, diag)`; `out` is a subset of `candidates` truncated to `limit` — shared/polymath_shared/evidence_utility.py:173 [DERIVED]; `diag` keys: `enabled`, `requirements`, `covered`, `parent_deferrals`, `redundancy_deferrals`, `promotions` — shared/polymath_shared/evidence_utility.py:113-115 [DERIVED].
- pre: candidates in relevance order — original index is the tiebreak tier — shared/polymath_shared/evidence_utility.py:101-104 [DERIVED]; if `len(candidates) <= limit` the function no-ops — shared/polymath_shared/evidence_utility.py:116-117 [DERIVED].
- post: rescue arrivals keep exactly `min(reserved, len(rescue), limit)` seats — shared/polymath_shared/evidence_utility.py:119-123 [DERIVED]; non-reserved seats filled by greedy key `(not covers, not fresh_parent, not non_redundant, i)` within a `lookahead` window — shared/polymath_shared/evidence_utility.py:137-150 [DERIVED]; output preserves input order (filter, no sort) — shared/polymath_shared/evidence_utility.py:173 [DERIVED]; `_eu_tokens` cache removed from all candidates before return — shared/polymath_shared/evidence_utility.py:174-177 [DERIVED].

### latent_competition — shared/polymath_shared/evidence_utility.py:181-216
- in: post-rerank candidate dicts (keys read: `arrival`, `rerank_score`, `parent_id`, `chunk_id`).
- out: `(filtered, diag)` with `latent_considered`, `latent_dropped` — shared/polymath_shared/evidence_utility.py:190 [DERIVED]; no latent candidates → input list returned unchanged — shared/polymath_shared/evidence_utility.py:194-195 [DERIVED].
- post: a latent candidate is kept iff its `rerank_score >= min(numeric non-latent scores) - margin` OR its `parent_id` is absent from non-latent parents — shared/polymath_shared/evidence_utility.py:198-208 [DERIVED]; missing/non-numeric scores never drop a latent survivor — shared/polymath_shared/evidence_utility.py:205-206 [DERIVED].

## effect surface
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty); only stdlib import is `re` — shared/polymath_shared/evidence_utility.py:46 [DERIVED].
- Qdrant / files / network / subprocess: none visible; no env flags read.
- In-place mutation of caller dicts: writes `c["_eu_tokens"]` — shared/polymath_shared/evidence_utility.py:132-135 [DERIVED] — and pops it before return — shared/polymath_shared/evidence_utility.py:174-177 [DERIVED].
- `enabled=False` gating lives in the caller; such paths never call into this module — shared/polymath_shared/evidence_utility.py:41-42 [DERIVED].

## invariants
INVARIANT: rescue seat count == min(reserved, len(rescue), limit) — shared/polymath_shared/evidence_utility.py:122 [DERIVED]
  fails-if: seat floors diverge from `_truncate_reserving_rescue` semantics the docstring promises — shared/polymath_shared/evidence_utility.py:96-97
INVARIANT: len(out) <= limit — shared/polymath_shared/evidence_utility.py:173 [DERIVED]
  fails-if: the post-G3 stage receives more rows than its contract allows.
INVARIANT: output order == input candidate order — shared/polymath_shared/evidence_utility.py:173 and shared/polymath_shared/evidence_utility.py:215-216 [DERIVED]
  fails-if: breaks the never-reorder law; cross-encoder is sole ordering authority — shared/polymath_shared/evidence_utility.py:35-37
INVARIANT: len(derive_requirements result) is 0 or >= 2 — shared/polymath_shared/evidence_utility.py:78 [DERIVED]
  fails-if: single-clause queries enter coverage accounting that can never close a second requirement — shared/polymath_shared/evidence_utility.py:69-71
INVARIANT: _jaccard(a, b) == 0.0 when either set is empty — shared/polymath_shared/evidence_utility.py:82-83 [DERIVED]
  fails-if: two empty token sets hit division by zero at `len(a & b) / len(a | b)` — shared/polymath_shared/evidence_utility.py:84
INVARIANT: latent floor == min(numeric non-latent rerank_score) - margin; no numeric scores ⇒ floor is None ⇒ all latent kept — shared/polymath_shared/evidence_utility.py:196-198 [DERIVED]
  fails-if: with rerank disabled/degraded, dropping latent survivors would break "guaranteed access to the competition" — shared/polymath_shared/evidence_utility.py:26-32

## determinism & idempotency
determinism: DETERMINISTIC — docstring asserts no RNG, no models, no clock; same inputs → same set — shared/polymath_shared/evidence_utility.py:41-42 [DERIVED]; only `re` imported — shared/polymath_shared/evidence_utility.py:46 [DERIVED].
idempotency: SAFE — the only mutation is the `_eu_tokens` cache, popped from every candidate on the normal path — shared/polymath_shared/evidence_utility.py:174-177 [DERIVED]; the early-return path never writes it — shared/polymath_shared/evidence_utility.py:116-117 [DERIVED].

## failure behaviour
- No try/except handlers exist; nothing is swallowed, no error codes raised by this module. [DERIVED — visible absence in shared/polymath_shared/evidence_utility.py:61-216]
- `latent_competition` fails open: `floor is None` (no numeric non-latent scores) or a non-numeric latent score ⇒ `clears` is True ⇒ survivor kept; "the filter never invents a score" — shared/polymath_shared/evidence_utility.py:186-189 and shared/polymath_shared/evidence_utility.py:205-206 [DERIVED].
- `utility_cut` with `limit == 0` returns `[]`; with `len(candidates) <= limit` returns candidates untouched — shared/polymath_shared/evidence_utility.py:116-117 [DERIVED].
- Direct indexing `c["chunk_id"]` at shared/polymath_shared/evidence_utility.py:171-172, shared/polymath_shared/evidence_utility.py:211, shared/polymath_shared/evidence_utility.py:215-216 raises KeyError on malformed candidate dicts [INFERRED: Python dict semantics; the bare indexing is visible].

## dumb-code flags
- Negative `limit` returns the FULL list, not an empty one: `(candidates[:limit] if limit >= 0 else candidates)` — shared/polymath_shared/evidence_utility.py:116-117 [DERIVED].
- Magic number `0.12` (requirement-coverage Jaccard threshold) appears twice, unnamed — shared/polymath_shared/evidence_utility.py:142 and shared/polymath_shared/evidence_utility.py:163 [DERIVED].
- `diag["enabled"]` hardcoded `True`, even on the early-return path where no cut happened — shared/polymath_shared/evidence_utility.py:113-117 [DERIVED].
- `annotations` parameter accepted and never read — commented "deferred seam: entity/fact novelty" — shared/polymath_shared/evidence_utility.py:94 and shared/polymath_shared/evidence_utility.py:12-14 [DERIVED].
- Local `kept` list is appended but never used; the drop decision runs through `dropped_ids` — shared/polymath_shared/evidence_utility.py:200-216 [DERIVED].
- `_eu_tokens` cleanup runs twice: once over `out`, then over all `candidates` (superset) — shared/polymath_shared/evidence_utility.py:174-177 [DERIVED].
- Promotion diagnostics attribute the skip only to `window[0]` (`skipped`), even when `best_i > 1` — shared/polymath_shared/evidence_utility.py:152-160 [DERIVED].

## refactor notes
- Sole importer is `shared/polymath_shared/hybrid.py` (FACTS.importers) — renaming or resigning `utility_cut`, `latent_competition`, `derive_requirements` ripples only there, at the two intervention points — shared/polymath_shared/evidence_utility.py:20-32 [DERIVED].
- Seat-floor semantics are contracted identical to `_truncate_reserving_rescue`; changing seat math here desyncs that helper — shared/polymath_shared/evidence_utility.py:96-97 [DERIVED].
- Sole-scoring-authority law: adding any relevance score or reorder breaks the register entry "set composition, not score fusion" — shared/polymath_shared/evidence_utility.py:34-39 [DERIVED].
- Dict keys `arrival`, `text`, `parent_id`, `chunk_id`, `rerank_score` are the implicit wire format consumed from pipeline dicts — shared/polymath_shared/evidence_utility.py:119, shared/polymath_shared/evidence_utility.py:171, shared/polymath_shared/evidence_utility.py:199, shared/polymath_shared/evidence_utility.py:204 [INFERRED: keys are read from caller-supplied dicts, so renaming breaks hybrid.py].
- `annotations` is the reserved extension point for entity/fact novelty — wire it before adding a new parameter — shared/polymath_shared/evidence_utility.py:94 and shared/polymath_shared/evidence_utility.py:12-14 [DERIVED].
- Degenerate identity (no requirements, fresh parents, no redundancy ⇒ exactly original order / plain reserved-seat cut) is a documented behavioural contract — preserve it — shared/polymath_shared/evidence_utility.py:108-111 [DERIVED].

## VERIFY
```verify
grep -Fq 'EVIDENCE-UTILITY-V1' shared/polymath_shared/evidence_utility.py
grep -Fq 'def utility_cut(candidates: list[dict], limit: int, *,' shared/polymath_shared/evidence_utility.py
grep -Fq 'redundancy_veto: float = 0.6,' shared/polymath_shared/evidence_utility.py
grep -Fq 'lookahead: int = 12,' shared/polymath_shared/evidence_utility.py
grep -Fq 'margin: float = 0.05' shared/polymath_shared/evidence_utility.py
grep -Fq '_jaccard(toks, reqs[j]) > 0.12' shared/polymath_shared/evidence_utility.py
! grep -Fq 'import random' shared/polymath_shared/evidence_utility.py
test "$(grep -c -F '0.12' shared/polymath_shared/evidence_utility.py)" -ge 2
```
