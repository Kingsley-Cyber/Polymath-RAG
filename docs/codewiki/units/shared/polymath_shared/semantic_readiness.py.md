# unit: shared/polymath_shared/semantic_readiness.py
anchor: shared/polymath_shared/semantic_readiness.py:1-237

## purpose
Durable, Postgres-receipt-backed semantic-completion verdict per corpus, deliberately separate from the `query_ready` CONTROL contract, whose semantics are frozen and never redefined here — semantic_readiness.py:1-10 [DERIVED].
Answers: did FACT/PROCEDURE/CONCEPT extraction, the summary hierarchy, the corpus map, and artifact projections all complete, where ZERO yield is completion and FAILED execution is not — semantic_readiness.py:12-21, semantic_readiness.py:234-236 [DERIVED].
Also carries the vNext-substrate verdict (parent-map + doc-profile, §19 floor) as an additive first-class dimension the S13/S14 cutover gates read — semantic_readiness.py:33-40, semantic_readiness.py:216-217 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `vnext_readiness` | def | `(conn, corpus_id: str, documents: int) -> dict` | semantic_readiness.py:43-84 | `semantic_completion` in-file (:218); module importers: `orchestrator/orchestrator/api/health.py`, `shared/polymath_shared/document_status.py` (FACTS.importers) |
| `semantic_completion` | def | `(conn, corpus_id: str) -> dict` | semantic_readiness.py:87-237 | module importers: `orchestrator/orchestrator/api/health.py`, `shared/polymath_shared/document_status.py` (FACTS.importers) |

Exported verdict constants: `SEMANTIC_READINESS_VERSION = "semantic-readiness-v1"` (:27), `COMPLETE = "SEMANTIC_COMPLETE"` (:29), `INCOMPLETE = "SEMANTIC_INCOMPLETE"` (:30), `FAILED = "SEMANTIC_FAILED"` (:31), `VNEXT_COMPLETE` (:38), `VNEXT_INCOMPLETE` (:39), `VNEXT_NOT_STARTED` (:40) — semantic_readiness.py:27-40 [DERIVED].

## contracts

### vnext_readiness — semantic_readiness.py:43-84
- in: `conn` (DB execute), `corpus_id`, `documents` = document count used as the profile floor — semantic_readiness.py:43 [DERIVED]
- pre: none; missing schema `public.document_parent_maps` short-circuits to `{"verdict": VNEXT_NOT_STARTED, "reason": "no_parent_map_schema"}` — semantic_readiness.py:49-50 [DERIVED]
- out: `{verdict, pending, parents: {eligible, mapped, excluded, unresolved}, vnext_profiles, documents}` (+`reason` on early exits) — semantic_readiness.py:82-84 [DERIVED]
- post: never raises; any `Exception` → verdict `VNEXT_NOT_STARTED`, reason `f"read_error:{type(exc).__name__}"` — semantic_readiness.py:68-69 [DERIVED]
- rule: `unresolved = max(0, eligible - mapped - excluded)` (:70); reasons `unresolved_eligible_parents_{u}_of_{e}` (:73) and `vnext_profiles_{p}_of_{d}` when `documents` truthy and `vnext_profiles < documents` (:74-75); NOT_STARTED iff all three of eligible/mapped/vnext_profiles are 0 (:76-77); COMPLETE iff no reasons (:78-79); else INCOMPLETE (:80-81)

### semantic_completion — semantic_readiness.py:87-237
- in: `conn`, `corpus_id` — semantic_readiness.py:87 [DERIVED]
- out keys: `contract, corpus_id, verdict, vnext, pending, artifact_lane_failures, extraction, extraction_failures, warnings, runs, counts, zero_yield_is_completion` with `zero_yield_is_completion: True` — semantic_readiness.py:212-237 [DERIVED]
- verdict order: `FAILED` if `artifact_lane_failures or extraction_failures` (:205-206); `INCOMPLETE` if `pending` (:207-208); else `COMPLETE` (:209-210)
- pending literals: `no_ingested_documents` (:191), `no_query_ready_run` (:193), `document_summaries_{x}_of_{y}` (:195), `no_parent_summaries` (:197), `no_corpus_map` (:199), `unprojected_procedures_{n}` (:201), `unprojected_concepts_{n}` (:203)
- per-run extraction verdict = `coverage_verdict(stats, floor=float(get_settings().control.extraction_coverage_floor))` over latest extract artifact with `llm_extraction` — semantic_readiness.py:113-131 [DERIVED]
- `vnext` key is additive; it never changes `verdict`, which stays the legacy-lane contract — semantic_readiness.py:216-218 [DERIVED]

## effect surface
- Postgres READ-ONLY; `tables_written` = [] (FACTS.tables_written) — semantic_readiness.py:43-237 [DERIVED]
- tables read: `runs` (:89-91, :117-127), `artifacts` (:64-67, :100-105, :121-125), `chunks` (:54), `documents` (:54, :142, :164), `document_parent_maps` (:49, :58-59), `document_parent_exclusions` (:62), `document_summaries` (:145), `parent_summaries` (:148-149), `corpus_summaries` (:152), `procedure_artifacts` (:156, :171), `concept_artifacts` (:159, :180), `facts` (:162), `evidence` (:163), `projection_receipts` (:173, :182) [DERIVED]
- FACTS.tables_read lists a table named `lateral` — that is the `LEFT JOIN LATERAL` clause at semantic_readiness.py:121, not a table — [INFERRED]
- Qdrant: no client/call; referenced only as the literal `projection = 'qdrant'` in `projection_receipts` — semantic_readiness.py:174, semantic_readiness.py:183 [DERIVED]
- settings/env: `get_settings().control.extraction_coverage_floor` (default not visible in this file) — semantic_readiness.py:114-115 [DERIVED]
- lazy imports at call time: `polymath_shared.document_region` (:51), `polymath_shared.extraction_coverage.coverage_verdict` (:113), `polymath_shared.settings.get_settings` (:114)
- no files, no subprocess, no network

## invariants
INVARIANT: unresolved == max(0, eligible - mapped - excluded) — semantic_readiness.py:70 [DERIVED]
  fails-if: over-counted mapped/excluded hides unresolved parents and flips the verdict to VNEXT_COMPLETE.
INVARIANT: verdict == VNEXT_COMPLETE ⇒ unresolved == 0 and (documents == 0 or vnext_profiles >= documents) — semantic_readiness.py:72-79 [DERIVED]
  fails-if: cutover (S13/S14) proceeds on a partial generation, breaking the §16 no-legacy/vNext-mixture rule (:33-37).
INVARIANT: semantic verdict == FAILED ⇔ artifact_lane_failures or extraction_failures non-empty — semantic_readiness.py:205-206 [DERIVED]
  fails-if: swallowed extract-stage exceptions (`artifacts_error` payload) get reported as completion.
INVARIANT: facts count includes only `f.decision = 'ACCEPT'` facts joined through `evidence` — semantic_readiness.py:162-165 [DERIVED]
  fails-if: rejected facts inflate the reported count (informational; counts do not drive the verdict).
INVARIANT: parent_summaries counts only rows with `superseded_at IS NULL` — semantic_readiness.py:148-149 [DERIVED]
  fails-if: superseded summaries satisfy the `no_parent_summaries` pending check.
INVARIANT: the `vnext` sub-verdict never mutates legacy `verdict` — semantic_readiness.py:216-217 [DERIVED]
  fails-if: legacy-verdict consumers flap on vNext substrate state.
INVARIANT: `zero_yield_is_completion` is always the literal `True` — semantic_readiness.py:236 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (pure SELECTs over durable state, docstring "One deterministic read" :88; variability only from DB contents and the settings floor `control.extraction_coverage_floor` :114-115) — semantic_readiness.py:88-115 [DERIVED]
idempotency: SAFE (read-only; no writes in SOURCE, `tables_written` empty per FACTS) — semantic_readiness.py:43-237 [DERIVED]

## failure behaviour
- `vnext_readiness` swallows every `Exception` (`# noqa: BLE001 — availability-neutral; never blocks the legacy verdict`) and returns `{"verdict": VNEXT_NOT_STARTED, "reason": f"read_error:{type(exc).__name__}"}` — semantic_readiness.py:68-69 (FACTS.fallbacks line 68) [DERIVED]. Caller sees a normal dict, never an exception, even on DB failure.
- Missing substrate schema → `{"verdict": VNEXT_NOT_STARTED, "reason": "no_parent_map_schema"}` — semantic_readiness.py:49-50 [DERIVED]
- `semantic_completion` has no try/except; a DB error in any of its queries propagates to the caller — semantic_readiness.py:87-237 [DERIVED]
- no error codes raised by this module

## dumb-code flags
- Literal `'qdrant'` duplicated in two queries with no shared constant (plus a comment mention at :169) — semantic_readiness.py:174, semantic_readiness.py:183 [DERIVED]
- Near-duplicate NOT EXISTS projection queries for procedures vs concepts (copy-paste pair) — semantic_readiness.py:170-187 [DERIVED]
- Lazy imports inside function bodies hide import failures until call time — semantic_readiness.py:51, semantic_readiness.py:113-114 [DERIVED]
- Edge branch: with `eligible == 0`, `mapped == 0`, `vnext_profiles > 0`, `documents == 0`, reasons stay empty and the NOT_STARTED test fails ⇒ `VNEXT_COMPLETE` for a zero-document corpus — semantic_readiness.py:70-81 [INFERRED] (branch order makes this reachable)
- `documents` is a caller-supplied count, not recomputed; `semantic_completion` passes its own `docs` count — semantic_readiness.py:43, semantic_readiness.py:141-143, semantic_readiness.py:218 [DERIVED]; a stale count silently shifts the profile-floor check [INFERRED]
- Pending/status strings embed counts via f-strings (`unresolved_eligible_parents_{u}_of_{e}`, `document_summaries_{x}_of_{y}`, `unprojected_procedures_{n}`) — semantic_readiness.py:73, semantic_readiness.py:195, semantic_readiness.py:201-203 [DERIVED]

## refactor notes
- Verdict strings are wire constants; importers `orchestrator/orchestrator/api/health.py` and `shared/polymath_shared/document_status.py` (FACTS.importers) break if `SEMANTIC_*`/`VNEXT_*` values change — semantic_readiness.py:29-31, semantic_readiness.py:38-40 [DERIVED]
- Output key `vnext` feeds the S13 QUERY_READY flip and S14 cutover gates; reshaping it has repo-wide blast radius — semantic_readiness.py:46-47, semantic_readiness.py:216-218 [DERIVED]
- `query_ready` semantics are frozen; this module must not redefine them — semantic_readiness.py:4-10 [DERIVED]
- Coupled to external payload shapes owned by producers: `artifacts.payload` key `artifacts_error` (:100-105), `llm_extraction`->`stats` (:119-124), `doc_profile`->>`vnext` == `'true'` (:65-67)
- Depends on `coverage_verdict(stats, floor=...)` from `polymath_shared.extraction_coverage` and on `document_region.NOISY_ROLES` driving parent eligibility — semantic_readiness.py:51-56, semantic_readiness.py:113, semantic_readiness.py:131 [DERIVED]
- Pending reason literals (:191-203) are string codes consumers may match; renaming them is a contract change

## VERIFY
```verify
grep -Fq 'semantic-readiness-v1' shared/polymath_shared/semantic_readiness.py
grep -Fq 'zero_yield_is_completion' shared/polymath_shared/semantic_readiness.py
grep -Fq 'unresolved_eligible_parents' shared/polymath_shared/semantic_readiness.py
grep -Fq 'extraction_coverage_floor' shared/polymath_shared/semantic_readiness.py
grep -Eq 'read_error:' shared/polymath_shared/semantic_readiness.py
test "$(grep -c -F 'qdrant' shared/polymath_shared/semantic_readiness.py)" -ge 3
! grep -Fq 'INSERT INTO' shared/polymath_shared/semantic_readiness.py
```
