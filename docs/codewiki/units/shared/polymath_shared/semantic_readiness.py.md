# unit: shared/polymath_shared/semantic_readiness.py
anchor: shared/polymath_shared/semantic_readiness.py:1-245

## purpose
Computes the SEMANTIC-READINESS-V1 verdict per corpus from durable Postgres state only — a semantic-lane completion view distinct from the frozen `query_ready` control contract (shared/polymath_shared/semantic_readiness.py:1-23) [DERIVED]. Also carries the vNext-substrate verdict (parent-MAP + vNext profile, the §19 floor `unresolved_eligible_parents == 0`) that the S13 QUERY_READY flip and S14 cutover gate on (shared/polymath_shared/semantic_readiness.py:33-40, 44-47) [DERIVED]. Consumed by the orchestrator health API and document_status.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `vnext_readiness` | def | (conn, corpus_id: str, documents: int) -> dict | shared/polymath_shared/semantic_readiness.py:43-92 | orchestrator/orchestrator/api/health.py, shared/polymath_shared/document_status.py (module importers) |
| `semantic_completion` | def | (conn, corpus_id: str) -> dict | shared/polymath_shared/semantic_readiness.py:95-245 | orchestrator/orchestrator/api/health.py, shared/polymath_shared/document_status.py (module importers) |
| `SEMANTIC_READINESS_VERSION` | const | `"semantic-readiness-v1"` | shared/polymath_shared/semantic_readiness.py:27 | — |
| `COMPLETE`/`INCOMPLETE`/`FAILED` | const | `"SEMANTIC_COMPLETE"`/`"SEMANTIC_INCOMPLETE"`/`"SEMANTIC_FAILED"` | shared/polymath_shared/semantic_readiness.py:29-31 | — |
| `VNEXT_COMPLETE`/`VNEXT_INCOMPLETE`/`VNEXT_NOT_STARTED` | const | `"VNEXT_COMPLETE"`/`"VNEXT_INCOMPLETE"`/`"VNEXT_NOT_STARTED"` | shared/polymath_shared/semantic_readiness.py:38-40 | — |

## contracts

**`vnext_readiness(conn, corpus_id, documents)` — shared/polymath_shared/semantic_readiness.py:43-92**
- in: `conn` (DB API connection using `%s` paramstyle), `corpus_id: str`, `documents: int` = corpus document count (caller supplies the count; line 202 uses it as a count) [DERIVED]
- out: dict `{verdict, pending, parents:{eligible, mapped, excluded, unresolved}, vnext_profiles, profiled, documents}` (shared/polymath_shared/semantic_readiness.py:90-92) [DERIVED]
- pre: none — missing `document_parent_maps` schema returns `{"verdict": VNEXT_NOT_STARTED, "reason": "no_parent_map_schema"}` (shared/polymath_shared/semantic_readiness.py:49-50) [DERIVED]
- post: never raises; any read exception returns `{"verdict": VNEXT_NOT_STARTED, "reason": "read_error:{type}"}` (shared/polymath_shared/semantic_readiness.py:47, 68-69) [DERIVED]

**`semantic_completion(conn, corpus_id)` — shared/polymath_shared/semantic_readiness.py:95-245**
- in: `conn`, `corpus_id: str` [DERIVED]
- out: dict `{contract, corpus_id, verdict, vnext, pending, artifact_lane_failures, extraction, extraction_failures, warnings, runs, counts:{documents, document_summaries, parent_summaries, corpus_map_rows, facts_accepted, procedures, concepts}, zero_yield_is_completion}` (shared/polymath_shared/semantic_readiness.py:220-245) [DERIVED]
- pre: no try/except in body — any DB error propagates to the caller [INFERRED] (no handler exists between 95-245)
- post: verdict = `FAILED` if `artifact_lane_failures or extraction_failures`, else `INCOMPLETE` if `pending`, else `COMPLETE` (shared/polymath_shared/semantic_readiness.py:213-218) [DERIVED]

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | `runs`, `artifacts` | shared/polymath_shared/semantic_readiness.py:97-100, 107-114, 124-136, 64-67, 73-75 |
| Postgres read | `chunks`, `documents` | shared/polymath_shared/semantic_readiness.py:53-56, 149-151 |
| Postgres read | `document_parent_maps`, `document_parent_exclusions` | shared/polymath_shared/semantic_readiness.py:49, 57-63 |
| Postgres read | `document_summaries`, `parent_summaries`, `corpus_summaries` | shared/polymath_shared/semantic_readiness.py:152-161 |
| Postgres read | `facts`, `evidence` | shared/polymath_shared/semantic_readiness.py:169-174 |
| Postgres read | `procedure_artifacts`, `concept_artifacts`, `projection_receipts` | shared/polymath_shared/semantic_readiness.py:163-168, 178-195 |
| Postgres write | none — `tables_written: []` (FACTS), module docstring says durable read view | shared/polymath_shared/semantic_readiness.py:12, 45 |
| env/settings | `settings.control.extraction_coverage_floor` via `get_settings()` (default not visible in this file) | shared/polymath_shared/semantic_readiness.py:123 |
| Qdrant/network/subprocess/files | none — Qdrant projection state read via `projection_receipts` table only | shared/polymath_shared/semantic_readiness.py:180-195 [INFERRED] |

## invariants

- INVARIANT: unresolved == max(0, eligible − mapped − excluded) — shared/polymath_shared/semantic_readiness.py:78 [DERIVED]
  fails-if: over-counting `mapped`/`excluded` hides unresolved parents and flips VNEXT_INCOMPLETE → VNEXT_COMPLETE, wrongly clearing the §19 cutover gate.
- INVARIANT: verdict == VNEXT_NOT_STARTED iff eligible == 0 AND mapped == 0 AND vnext_profiles == 0 — shared/polymath_shared/semantic_readiness.py:84-85 [DERIVED]
  fails-if: a corpus with zero eligible parents but some vnext profiles reads INCOMPLETE/COMPLETE instead of NOT_STARTED.
- INVARIANT: documents > 0 AND vnext_profiles < documents ⇒ reasons non-empty ⇒ verdict != VNEXT_COMPLETE — shared/polymath_shared/semantic_readiness.py:82-83, 86-89 [DERIVED]
  fails-if: partial vNext generation is labelled complete, violating the "no legacy/vNext mixture" generation invariant (§16, shared/polymath_shared/semantic_readiness.py:36-37).
- INVARIANT: (len(artifact_lane_failures) + len(extraction_failures)) > 0 ⇒ verdict == FAILED — shared/polymath_shared/semantic_readiness.py:213-214 [DERIVED]
  fails-if: a failed artifact lane is silently reported as COMPLETE, the exact gap this module exists to close.
- INVARIANT: parent_summaries counts only rows with `superseded_at IS NULL` — shared/polymath_shared/semantic_readiness.py:157 [DERIVED]
  fails-if: counting superseded rows masks a missing active summary layer, wrongly reporting `no_parent_summaries` absent.
- INVARIANT: facts counted only where `f.decision = 'ACCEPT'` and joined through `evidence` + `documents` — shared/polymath_shared/semantic_readiness.py:169-174 [DERIVED]
  fails-if: counting REJECT/undecided facts inflates `facts_accepted`.
- INVARIANT: `zero_yield_is_completion` == True on every return — shared/polymath_shared/semantic_readiness.py:242-244 [DERIVED]
  fails-if: zero artifact counts start blocking COMPLETE, inverting the module's stated contract.
- INVARIANT: `profiled` read failure sets profiled = None and leaves `verdict` untouched (display-only) — shared/polymath_shared/semantic_readiness.py:70-77 [DERIVED]
  fails-if: a display-count failure leaks into the verdict and blocks readiness.

## determinism & idempotency
determinism: NONDETERMINISTIC (db — all verdicts derive from table state, shared/polymath_shared/semantic_readiness.py:97-195; env — floor from `get_settings().control.extraction_coverage_floor`, shared/polymath_shared/semantic_readiness.py:123)
idempotency: SAFE (read-only; FACTS `tables_written: []`; docstring "Read-only" at shared/polymath_shared/semantic_readiness.py:45)

## failure behaviour
- Broad `except Exception` in `vnext_readiness` SWALLOWED → caller sees `{"verdict": VNEXT_NOT_STARTED, "reason": "read_error:{ExceptionType}"}` — availability-neutral, never blocks the legacy verdict (shared/polymath_shared/semantic_readiness.py:68-69) [DERIVED]
- Missing substrate table → `{"verdict": VNEXT_NOT_STARTED, "reason": "no_parent_map_schema"}` (shared/polymath_shared/semantic_readiness.py:49-50) [DERIVED]
- Display-only `profiled` count: `except Exception` → `profiled = None` (shared/polymath_shared/semantic_readiness.py:76-77) [DERIVED]
- `semantic_completion` has no handlers — any DB error propagates; no error codes raised in-module [INFERRED] (no try/except between 95-245)

## dumb-code flags
- Param named `documents: int` is a count, not documents — callers must pass `COUNT(documents)`; `docs` local repeats the same misleading naming (shared/polymath_shared/semantic_readiness.py:43, 149-151) [DERIVED]
- `VNEXT_NOT_STARTED` overloaded three ways — "no schema", "read error", "nothing done" — distinguishable only via the `reason` string (shared/polymath_shared/semantic_readiness.py:50, 69, 84-85) [DERIVED]
- Duplicated literal payload path `payload->'doc_profile'->>'doc_id'` + `stage='doc_profile'` in the vnext_profiles and profiled queries (shared/polymath_shared/semantic_readiness.py:65-66, 73-75) [DERIVED]
- Magic truncation `run_id[:20]` in warning labels (shared/polymath_shared/semantic_readiness.py:146) [DERIVED]
- FACTS `tables_read` lists a table named `lateral` — no such table; artifact of `LEFT JOIN LATERAL` at shared/polymath_shared/semantic_readiness.py:129 [INFERRED]

## refactor notes
- Returned dict keys (`verdict`, `vnext`, `pending`, `counts`, `zero_yield_is_completion`) are consumed by orchestrator/orchestrator/api/health.py and shared/polymath_shared/document_status.py (FACTS.importers; shared/polymath_shared/semantic_readiness.py:220-245) — renaming any key breaks both importers.
- `verdict` must stay the legacy-lane contract; `vnext` rides additively and must not be merged into it (shared/polymath_shared/semantic_readiness.py:224-225) [DERIVED]
- `vnext_readiness` must never raise — the health path depends on the swallowed-exception contract (shared/polymath_shared/semantic_readiness.py:47, 68) [DERIVED]
- Function-local imports `document_region` (line 51) and `coverage_verdict`/`get_settings` (lines 121-122) likely avoid import cycles within polymath_shared — hoisting to module scope may create one (shared/polymath_shared/semantic_readiness.py:51, 121-122) [INFERRED]
- The `max(0, ...)` clamp and triple-zero NOT_STARTED condition implement the §19 floor gating S13/S14; changing the arithmetic changes the cutover gate (shared/polymath_shared/semantic_readiness.py:44-47, 78, 84-89) [DERIVED]

## VERIFY
```verify
grep -Fq 'SEMANTIC_READINESS_VERSION = "semantic-readiness-v1"' shared/polymath_shared/semantic_readiness.py
grep -Fq 'unresolved = max(0, eligible - mapped - excluded)' shared/polymath_shared/semantic_readiness.py
grep -Fq 'no_parent_map_schema' shared/polymath_shared/semantic_readiness.py
grep -Fq 'superseded_at IS NULL' shared/polymath_shared/semantic_readiness.py
grep -Fq '"zero_yield_is_completion": True,' shared/polymath_shared/semantic_readiness.py
test "$(grep -c -F 'VNEXT_NOT_STARTED' shared/polymath_shared/semantic_readiness.py)" -ge 4
! grep -Fq 'INSERT INTO' shared/polymath_shared/semantic_readiness.py
```
