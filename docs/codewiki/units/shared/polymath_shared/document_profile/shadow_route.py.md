# unit: shared/polymath_shared/document_profile/shadow_route.py
anchor: shared/polymath_shared/document_profile/shadow_route.py:1-187

## purpose
Shadow-only retrieval route that runs the vNext semantic path (global profile search → one filtered parent-map search → child deepening) and returns a measurement receipt, with **no production rank effect** — shared/polymath_shared/document_profile/shadow_route.py:1-5 [DERIVED]. Built per RETRIEVAL-MIGRATION-DEPENDENCY-V1 §17 (shadow phase) / roadmap S8; the caller (canary / future dual-read lane) computes overlap and gold-hit from the receipt, keeping this module a pure route — shared/polymath_shared/document_profile/shadow_route.py:18-25 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ShadowReceipt` | frozen dataclass | fields `profile_doc_candidates`, `parent_map_candidates`, `resolved_parent_ids`, `shadow_child_candidates`, `latency_ms`, `degraded=()`, `version=SHADOW_ROUTE_VERSION`; `.as_receipt() -> dict` | shared/polymath_shared/document_profile/shadow_route.py:66-89 | — |
| `shadow_route` | def | `(query_vec, *, profile_search, map_search, child_search, k_docs=DEFAULT_K_DOCS, k_parents=DEFAULT_K_PARENTS, k_children=DEFAULT_K_CHILDREN) -> ShadowReceipt` | shared/polymath_shared/document_profile/shadow_route.py:92-160 | — |
| `overlap_with_final` | def | `(shadow_child_ids, final_child_ids) -> float` | shared/polymath_shared/document_profile/shadow_route.py:166-175 | — |
| `gold_hit` | def | `(shadow_child_ids, gold_ids) -> bool` | shared/polymath_shared/document_profile/shadow_route.py:178-181 | — |
| `doc_nomination_hit` | def | `(profile_doc_candidates, gold_doc_ids) -> bool` | shared/polymath_shared/document_profile/shadow_route.py:184-187 | — |

No FACTS importers; docstring names the caller role as "the canary / the future dual-read lane" — shared/polymath_shared/document_profile/shadow_route.py:18-20 [DERIVED]. `_dedupe` is private — shared/polymath_shared/document_profile/shadow_route.py:57 [DERIVED].

## contracts

**`shadow_route`** — shared/polymath_shared/document_profile/shadow_route.py:92-160
- in: `query_vec: list[float]` already embedded; three injected callables typed `ProfileSearch`/`MapSearch`/`ChildSearch` — shared/polymath_shared/document_profile/shadow_route.py:44-46, 92-101 [DERIVED].
- in (callable shapes, each returns descending-by-score dict rows): `profile_search(query_vec, k) -> [{"doc_id", "score", ...}]`; `map_search(query_vec, doc_ids, k) -> [{"doc_id", "parent_id", "alias", "score", ...}]`; `child_search(query_vec, doc_parent_pairs, k) -> [{"chunk_id", "doc_id", "parent_id", "score", ...}]` — shared/polymath_shared/document_profile/shadow_route.py:27-32 [DERIVED].
- pre: `map_search` MUST issue a single store query filtered to `doc_ids` (§17 rule: never one search per doc) — shared/polymath_shared/document_profile/shadow_route.py:34-35 [DERIVED].
- post: a failure or empty result at any stage degrades gracefully (recorded in `degraded`) and short-circuits downstream stages; a shadow never raises into the caller — shared/polymath_shared/document_profile/shadow_route.py:104-105 [DERIVED].
- out: `ShadowReceipt`; id tuples are deduped, order-preserving projections; `parent_map_candidates` keeps raw map rows so misses are attributable — shared/polymath_shared/document_profile/shadow_route.py:68-70, 115, 127, 145 [DERIVED].
- out: `latency_ms` keys `"profile"`, `"map"`, `"child"`, `"total"`, each `round(span * 1000, 2)` ms — shared/polymath_shared/document_profile/shadow_route.py:153-157 [DERIVED].

**`overlap_with_final`** — shared/polymath_shared/document_profile/shadow_route.py:166-175
- in: two id sequences; out: `round(len(set(shadow_child_ids) & final) / len(final), 4)`; returns `0.0` when `final` is empty — shared/polymath_shared/document_profile/shadow_route.py:172-175 [DERIVED].
- Denominator is the current lane's final child set; `1.0` means the routing localized to every final child — shared/polymath_shared/document_profile/shadow_route.py:169-171 [DERIVED].

**`gold_hit`** — shared/polymath_shared/document_profile/shadow_route.py:178-181
- out: `bool(gold) and bool(set(shadow_child_ids) & gold)`; `False` when no gold is given — shared/polymath_shared/document_profile/shadow_route.py:180-181 [DERIVED].

**`doc_nomination_hit`** — shared/polymath_shared/document_profile/shadow_route.py:184-187
- out: `bool(gold) and bool(set(profile_doc_candidates) & gold)`; localization prerequisite at the profile step — shared/polymath_shared/document_profile/shadow_route.py:186-187 [DERIVED].

**`ShadowReceipt.as_receipt`** — shared/polymath_shared/document_profile/shadow_route.py:80-89
- out: plain dict with keys mirroring the fields (`profile_doc_candidates`, `parent_map_candidates`, `resolved_parent_ids`, `shadow_child_candidates`, `latency_ms`, `degraded`, `version`) — shared/polymath_shared/document_profile/shadow_route.py:81-88 [DERIVED].

## effect surface
- Postgres: none — FACTS `tables_read`/`tables_written` empty.
- Qdrant: no direct access; all store I/O sits behind the three injected callables — shared/polymath_shared/document_profile/shadow_route.py:95-97 [DERIVED]. The same module later backs the S9 dual-read lane over the real Qdrant store — shared/polymath_shared/document_profile/shadow_route.py:22-25 [DERIVED].
- Mutates nothing: "never mutates retrieval, ranking, `QUERY_READY`, or any store — additive and reversible by construction" — shared/polymath_shared/document_profile/shadow_route.py:25 [DERIVED].
- Clock: `time.monotonic` ×4 — shared/polymath_shared/document_profile/shadow_route.py:108, 116, 128, 146 [DERIVED].
- Files / network / subprocess / env flags: none visible.

## invariants
INVARIANT: map_search invocations ≤ 1 per `shadow_route` call, gated by `if doc_ids:` — shared/polymath_shared/document_profile/shadow_route.py:118-122 [DERIVED]
  fails-if: per-doc map searches violate the §17 performance rule (shared/polymath_shared/document_profile/shadow_route.py:34).
INVARIANT: `child_search` runs only when `resolved` is non-empty, fed deduped `(doc_id, parent_id)` pairs — shared/polymath_shared/document_profile/shadow_route.py:132-140 [DERIVED]
  fails-if: an unfiltered child lane destroys the localization being measured.
INVARIANT: `latency_ms["total"]` equals profile+map+child spans before per-field `round(..., 2)` — shared/polymath_shared/document_profile/shadow_route.py:153-157 [DERIVED]
  fails-if: adding a stage without a `time.monotonic` read breaks latency accounting.
INVARIANT: `overlap_with_final` denominator is `len(final)`, never `len(shadow)`; `0.0` on empty final — shared/polymath_shared/document_profile/shadow_route.py:172-175 [DERIVED]
  fails-if: swapping the denominator silently redefines coverage.
INVARIANT: `gold_hit` is `False` whenever `gold_ids` is empty — shared/polymath_shared/document_profile/shadow_route.py:180-181 [DERIVED]
  fails-if: empty-gold counted as a hit inflates the canary pass rate.
INVARIANT: `_dedupe` drops falsy ids and preserves first-seen order — shared/polymath_shared/document_profile/shadow_route.py:57-63 [DERIVED]
  fails-if: empty-string doc/parent/chunk ids leak into receipt tuples.
INVARIANT: `ShadowReceipt.version` defaults to `SHADOW_ROUTE_VERSION = "shadow-route-v1"` — shared/polymath_shared/document_profile/shadow_route.py:48, 78 [DERIVED]
  fails-if: receipt consumers can no longer pin the schema version.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock only: `time.monotonic` at shared/polymath_shared/document_profile/shadow_route.py:108, 116, 128, 146 feeds `latency_ms`; candidate sets are pure functions of the injected searches — shared/polymath_shared/document_profile/shadow_route.py:22-25 [DERIVED])
idempotency: SAFE (no store/file writes; "never mutates retrieval, ranking, `QUERY_READY`, or any store" — shared/polymath_shared/document_profile/shadow_route.py:25 [DERIVED])

## failure behaviour
- Three broad `except Exception` handlers (FACTS.fallbacks; source lines shared/polymath_shared/document_profile/shadow_route.py:113, 123, 141) swallow every error from the injected searches — "a shadow must never raise into production" — shared/polymath_shared/document_profile/shadow_route.py:113 [DERIVED].
- Degradation codes emitted: `"profile_search_error"` (:114), `"map_search_error"` (:124), `"child_search_error"` (:142), `"no_nominated_docs"` (:126), `"no_resolved_parents"` (:143-144) — shared/polymath_shared/document_profile/shadow_route.py:114-144 [DERIVED].
- After a `profile_search_error`, `prof_rows` becomes `[]` and all downstream stages short-circuit; `"no_nominated_docs"` fires only when the profile step succeeded but returned nothing (`elif not degraded:`) — shared/polymath_shared/document_profile/shadow_route.py:114-126 [DERIVED].
- `"no_resolved_parents"` fires only when `doc_ids` is non-empty and no `*_error` code is present (`not any(d.endswith("_error") for d in degraded)`) — shared/polymath_shared/document_profile/shadow_route.py:143-144 [DERIVED].
- No exceptions raised on any path; the caller always receives a `ShadowReceipt` with `degraded` filled in — shared/polymath_shared/document_profile/shadow_route.py:104-105, 148-160 [DERIVED].

## dumb-code flags
- Magic widths `DEFAULT_K_DOCS = 8`, `DEFAULT_K_PARENTS = 24`, `DEFAULT_K_CHILDREN = 40`, commented "deliberately generous"; caller tunes per experiment — shared/polymath_shared/document_profile/shadow_route.py:50-54 [DERIVED].
- `except Exception:  # noqa: BLE001` duplicated ×3 — shared/polymath_shared/document_profile/shadow_route.py:113, 123, 141 [DERIVED].
- Pair building synthesizes `""` sentinels via `m.get("doc_id", ""), m.get("parent_id", "")` then filters on `if pr[1]` — overlapping with `_dedupe`'s falsy drop — shared/polymath_shared/document_profile/shadow_route.py:135-136, 57-63 [DERIVED].
- Degradation codes are bare string literals, not an enum/constants — shared/polymath_shared/document_profile/shadow_route.py:114, 124, 126, 142, 144 [DERIVED].

## refactor notes
- Injected callable signatures (`ProfileSearch`/`MapSearch`/`ChildSearch`) are the store-abstraction contract; the same module must later back the S9 dual-read lane over the real Qdrant store, so arity/type changes break both the unit-test fakes and that lane — shared/polymath_shared/document_profile/shadow_route.py:22-25, 44-46 [DERIVED].
- `ShadowReceipt` field names and `as_receipt()` keys are the §17 receipt schema the canary / dual-read caller measures against; renames break receipt consumers — shared/polymath_shared/document_profile/shadow_route.py:18-20, 80-89 [DERIVED].
- Degradation code strings are the only failure signal the caller receives; treat them as API — shared/polymath_shared/document_profile/shadow_route.py:114-144 [INFERRED: caller can only branch on these literals, nothing else is emitted].
- Keep the single filtered `map_search` (§17 rule) and the never-raise guarantee; both are stated contract points — shared/polymath_shared/document_profile/shadow_route.py:34-35, 104-105 [DERIVED].
- `SHADOW_ROUTE_VERSION` is stamped into every receipt; bump it whenever the receipt schema changes — shared/polymath_shared/document_profile/shadow_route.py:48, 78 [DERIVED].

## VERIFY
```verify
grep -Fq 'SHADOW_ROUTE_VERSION = "shadow-route-v1"' shared/polymath_shared/document_profile/shadow_route.py
grep -Fq 'DEFAULT_K_DOCS = 8' shared/polymath_shared/document_profile/shadow_route.py
grep -Fq 't0 = time.monotonic()' shared/polymath_shared/document_profile/shadow_route.py
grep -Fq 'degraded.append("no_resolved_parents")' shared/polymath_shared/document_profile/shadow_route.py
grep -Fq 'return round(len(set(shadow_child_ids) & final) / len(final), 4)' shared/polymath_shared/document_profile/shadow_route.py
! grep -Fq 'import random' shared/polymath_shared/document_profile/shadow_route.py
```
