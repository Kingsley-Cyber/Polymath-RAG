# unit: shared/polymath_shared/corpus_mapping.py
anchor: shared/polymath_shared/corpus_mapping.py:1-196

## purpose
SUMMARY RUNTIME D4: the corpus mapping worker — builds a corpus-level "navigation map" answering "what does this corpus contain?", never "what is true?" — shared/polymath_shared/corpus_mapping.py:1-4 [DERIVED]. Input contract is `document_summaries` only; rebuilds are batch-triggered by refresh policy, never one per document — shared/polymath_shared/corpus_mapping.py:5-8 [DERIVED]. Weighted composition: concept weight = document spread + occurrences (+ evidence density); entity importance adds `fact_degree`; every field carries `source_document_summary_ids` provenance — shared/polymath_shared/corpus_mapping.py:7-10 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build_corpus_map` | def | (corpus_id: str, document_summaries: list[dict], fact_degrees: dict\|None=None, procedures: list[dict]\|None=None, top_n: int=10) -> dict | shared/polymath_shared/corpus_mapping.py:70-129 | module imported by shared/polymath_shared/vocabulary_mapping.py, workers/workers/summary_worker_impl.py (FACTS.importers; per-symbol use not in FACTS) |
| `run_corpus_mapping_ticket` | def | (conn, ticket_id: str, corpus_id: str, input_hash: str, contract_version: str, worker_id: str, fact_degrees: dict\|None=None) -> dict | shared/polymath_shared/corpus_mapping.py:133-195 | same importers |
| `corpus_refresh_policy` | def | (completed_documents: int, last_run_at, now, threshold: int=100, debounce_minutes: int=30, force: bool=False) -> tuple[bool, str] | shared/polymath_shared/corpus_mapping.py:31-45 | same importers |
| `CORPUS_MAPPING_THRESHOLD_DOCS` / `CORPUS_MAPPING_DEBOUNCE_MINUTES` | constants | 100 / 30 | shared/polymath_shared/corpus_mapping.py:27-28 | same importers |
| `_claim` | def (private) | (conn, ticket_id: str, worker_id: str) -> bool | shared/polymath_shared/corpus_mapping.py:20-25 | internal only (called at shared/polymath_shared/corpus_mapping.py:137) [DERIVED] |
| `_weighted` | def (private) | (per_doc, fact_degrees, top_n) -> list[dict] | shared/polymath_shared/corpus_mapping.py:48-67 | internal only (called at shared/polymath_shared/corpus_mapping.py:83-85) [DERIVED] |

## contracts

**corpus_refresh_policy** — shared/polymath_shared/corpus_mapping.py:31-45
- in: keyword-only; defaults `threshold=100`, `debounce_minutes=30`, `force=False` — shared/polymath_shared/corpus_mapping.py:31-36 [DERIVED]
- out: `(bool, str)`; reason ∈ `{"manual_rebuild", "document_count_threshold", "scheduled_refresh", "policy_deferred"}` — shared/polymath_shared/corpus_mapping.py:37-45 [DERIVED]
- post: `force=True` ⇒ always `(True, "manual_rebuild")` — shared/polymath_shared/corpus_mapping.py:37-38 [DERIVED]
- pre: `now >= last_run_at`, else `elapsed` minutes go negative and `scheduled_refresh` never fires — shared/polymath_shared/corpus_mapping.py:42-44 [INFERRED: subtraction sign]

**build_corpus_map** — shared/polymath_shared/corpus_mapping.py:70-129
- in: keyword-only, `top_n=10` default — shared/polymath_shared/corpus_mapping.py:70-73 [DERIVED]
- reads per-doc keys: `summary_id` (direct index, KeyError if absent), `major_entities`, `major_concepts`, `methods`, `evidence_density` (each `.get` with `or 0.5` fallback) — shared/polymath_shared/corpus_mapping.py:74-81 [DERIVED]
- out keys: `corpus_id`, `concepts`, `entities`, `procedures`, `typed_relations`, `predicates`, `document_clusters` — shared/polymath_shared/corpus_mapping.py:113-129 [DERIVED]
- post: every concepts/entities/predicates/procedures entry carries `source_document_summary_ids` — shared/polymath_shared/corpus_mapping.py:179-181, shared/polymath_shared/corpus_mapping.py:96-101, shared/polymath_shared/corpus_mapping.py:117-125 [DERIVED]
- post: `typed_relations` only contains `PROCEDURE_USES_TOOL` and `PROCEDURE_SUPPORTS_CONCEPT`, never flattened `related_to` — shared/polymath_shared/corpus_mapping.py:93-94, shared/polymath_shared/corpus_mapping.py:105-109 [DERIVED]
- post: cluster labels are `f"{cpts[0]} cluster"` — first major concept only — shared/polymath_shared/corpus_mapping.py:87-91 [DERIVED]

**run_corpus_mapping_ticket** — shared/polymath_shared/corpus_mapping.py:133-195
- in: `conn` (DB-API), rest keyword-only — shared/polymath_shared/corpus_mapping.py:133-136 [DERIVED]
- out: `{"status": "SKIPPED_NOT_CLAIMABLE"}` / `{"status": "EXISTING", "artifact_id"}` / `{"status": "COMPLETE", "artifact_id", "output_hash"}` — shared/polymath_shared/corpus_mapping.py:138, shared/polymath_shared/corpus_mapping.py:145, shared/polymath_shared/corpus_mapping.py:194-195 [DERIVED]
- pre: a `summary_jobs` row for `ticket_id` with state in `('READY','RETRY_WAIT')` — shared/polymath_shared/corpus_mapping.py:22-24 [DERIVED]
- post COMPLETE: rows in `summary_artifacts` (stage `'CORPUS_MAPPING'`) and `corpus_summaries`; `summary_jobs.state='COMPLETE'` — shared/polymath_shared/corpus_mapping.py:170-178, shared/polymath_shared/corpus_mapping.py:179-191, shared/polymath_shared/corpus_mapping.py:192-193 [DERIVED]

## effect surface
- Postgres reads: `summary_artifacts` (`SELECT artifact_id WHERE input_hash=%s`) — shared/polymath_shared/corpus_mapping.py:139-141; `document_summaries` (`summary_id, major_entities, major_concepts, methods WHERE corpus_id=%s`, no ORDER BY) — shared/polymath_shared/corpus_mapping.py:146-150; `procedure_artifacts` (`title, goal, tools_json WHERE corpus_id=%s ORDER BY procedure_id`) — shared/polymath_shared/corpus_mapping.py:156-160 [DERIVED]
- Postgres writes: `summary_jobs` (UPDATE state/worker_id/completed_at) — shared/polymath_shared/corpus_mapping.py:21-24, shared/polymath_shared/corpus_mapping.py:143-144, shared/polymath_shared/corpus_mapping.py:192-193; `summary_artifacts` (INSERT ... `ON CONFLICT (input_hash) DO NOTHING`) — shared/polymath_shared/corpus_mapping.py:169-178; `corpus_summaries` (INSERT with `::text[]` casts) — shared/polymath_shared/corpus_mapping.py:179-191 [DERIVED]
- Qdrant / files / network / subprocess: none in this unit — shared/polymath_shared/corpus_mapping.py:1-195 [DERIVED]
- env flags: none read — shared/polymath_shared/corpus_mapping.py:1-195 [DERIVED]
- imports: `polymath_shared.identity.content_hash` (shared/polymath_shared/corpus_mapping.py:16), `polymath_shared.summary_layer.build_envelope` (shared/polymath_shared/corpus_mapping.py:17, re-imported at 165) [DERIVED]

## invariants
INVARIANT: `CORPUS_MAPPING_THRESHOLD_DOCS = 100` == default `threshold` of `corpus_refresh_policy` — shared/polymath_shared/corpus_mapping.py:27, shared/polymath_shared/corpus_mapping.py:33 [DERIVED]
  fails-if: policy fires at a different document count than the default callers assume.
INVARIANT: `CORPUS_MAPPING_DEBOUNCE_MINUTES = 30` == default `debounce_minutes` — shared/polymath_shared/corpus_mapping.py:28, shared/polymath_shared/corpus_mapping.py:34-35 [DERIVED]
  fails-if: scheduled refresh cadence drifts from 30 min.
INVARIANT: predicates cap `8` < `top_n` default `10` (entities/concepts) — shared/polymath_shared/corpus_mapping.py:83-85, shared/polymath_shared/corpus_mapping.py:73 [DERIVED]
  fails-if: `common_predicates` shape in `corpus_summaries` changes silently relative to entities/concepts.
INVARIANT: `summary_artifacts.artifact_id == "csa_" + content_hash({"in": input_hash})[:32]` — shared/polymath_shared/corpus_mapping.py:168 [DERIVED]
  fails-if: artifact identity changes; lookups by old IDs break.
INVARIANT: `corpus_summaries.summary_id == env["artifact_id"]` ≠ the `"csa_"` artifact_id written to `summary_artifacts` — shared/polymath_shared/corpus_mapping.py:185 vs shared/polymath_shared/corpus_mapping.py:168 [INFERRED: two ID spaces for one build]
  fails-if: consumers joining `corpus_summaries` to `summary_artifacts` by ID get zero rows.
INVARIANT: `env["output_hash"]` stored identically as `summary_artifacts.output_hash` and `corpus_summaries.artifact_hash` — shared/polymath_shared/corpus_mapping.py:175, shared/polymath_shared/corpus_mapping.py:185 [DERIVED]
  fails-if: hash mismatch flags the same build as different content.
INVARIANT: stored entities/concepts sliced `[:10]`; `common_predicates` stored unsliced — shared/polymath_shared/corpus_mapping.py:188-190 [DERIVED]
  fails-if: `corpus_summaries` rows exceed the `top_n=10` used elsewhere (shared/polymath_shared/corpus_mapping.py:73).
INVARIANT: `concept_strength = min(1.0, 0.25 + 0.25 * spread)`; `score = round(spread * dens * concept_strength + fact_degree * 0.01, 3)` — shared/polymath_shared/corpus_mapping.py:61-63 [DERIVED]
  fails-if: ranking changes reorder top-N without any data change.
INVARIANT: density fallback `0.5` at five sites — shared/polymath_shared/corpus_mapping.py:75, shared/polymath_shared/corpus_mapping.py:78, shared/polymath_shared/corpus_mapping.py:80, shared/polymath_shared/corpus_mapping.py:56, shared/polymath_shared/corpus_mapping.py:60 [DERIVED]
  fails-if: editing one site changes weights inconsistently.

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` in SQL — shared/polymath_shared/corpus_mapping.py:143-144, shared/polymath_shared/corpus_mapping.py:192-193 [DERIVED]; `document_summaries` SELECT has no ORDER BY — shared/polymath_shared/corpus_mapping.py:148-149 — so tie order in `Counter.most_common()` (shared/polymath_shared/corpus_mapping.py:58) can reorder equal-weight items across runs, perturbing `output_hash` [INFERRED]). Scoring math itself is pure — shared/polymath_shared/corpus_mapping.py:61-63 [DERIVED].
idempotency: SAFE (re-run of the same ticket → `_claim` fails → `"SKIPPED_NOT_CLAIMABLE"` — shared/polymath_shared/corpus_mapping.py:22-24, shared/polymath_shared/corpus_mapping.py:137-138; new ticket with known `input_hash` → `"EXISTING"` — shared/polymath_shared/corpus_mapping.py:139-145; `ON CONFLICT (input_hash) DO NOTHING` — shared/polymath_shared/corpus_mapping.py:174). Exception: the `corpus_summaries` INSERT (shared/polymath_shared/corpus_mapping.py:179-191) has no conflict clause; two concurrent tickets sharing an `input_hash` can both pass the existing-check and double-insert [INFERRED].

## failure behaviour
- No try/except anywhere in the unit; `conn.execute` exceptions propagate to the caller — shared/polymath_shared/corpus_mapping.py:1-195 [DERIVED]
- If any statement raises after a successful claim, `summary_jobs` stays `state='RUNNING'`; no reset path exists in this file, so the ticket can never re-match `('READY','RETRY_WAIT')` — shared/polymath_shared/corpus_mapping.py:22-24 [INFERRED]
- Statuses returned instead of raised: `"SKIPPED_NOT_CLAIMABLE"`, `"EXISTING"`, `"COMPLETE"` — shared/polymath_shared/corpus_mapping.py:138, shared/polymath_shared/corpus_mapping.py:145, shared/polymath_shared/corpus_mapping.py:194 [DERIVED]
- `ON CONFLICT (input_hash) DO NOTHING` silently drops a racing duplicate insert while the function still returns `"COMPLETE"` — shared/polymath_shared/corpus_mapping.py:174, shared/polymath_shared/corpus_mapping.py:194 [DERIVED]

## dumb-code flags
- Duplicate import: `from polymath_shared.summary_layer import build_envelope` at top (shared/polymath_shared/corpus_mapping.py:17) and again inside the worker (shared/polymath_shared/corpus_mapping.py:165) [DERIVED]
- `__import__("json").dumps(...)` inline at shared/polymath_shared/corpus_mapping.py:178 and shared/polymath_shared/corpus_mapping.py:191; no top-level `import json` [DERIVED]
- `tools_json` column zipped into key `"tools"` with no `json.loads` (shared/polymath_shared/corpus_mapping.py:156-158); `build_corpus_map` iterates `p.get("tools", [])` (shared/polymath_shared/corpus_mapping.py:104) — if the column stores JSON text, the tool loop walks characters [INFERRED]
- Redundant nested comprehension `[ds for ds in [d.get("summary_id") for d in document_summaries]]` — shared/polymath_shared/corpus_mapping.py:98-100 [DERIVED]
- Magic cap `8` for predicates (shared/polymath_shared/corpus_mapping.py:85) vs `top_n=10` default (shared/polymath_shared/corpus_mapping.py:73); `[:10]` re-slices duplicate that default — shared/polymath_shared/corpus_mapping.py:188-189 [DERIVED]
- Module docstring claims "Input contract: document_summaries ONLY" (shared/polymath_shared/corpus_mapping.py:6) but the worker also reads `procedure_artifacts` (shared/polymath_shared/corpus_mapping.py:156-160); the comment at shared/polymath_shared/corpus_mapping.py:151-155 says procedures were always accepted by the builder [DERIVED]
- Cluster label uses only `cpts[0]`; a document with several concepts appears in exactly one cluster — shared/polymath_shared/corpus_mapping.py:89-91 [DERIVED]
- Item label truncates only the fallback: `p.get("title") or p.get("goal", "")[:60]` — shared/polymath_shared/corpus_mapping.py:96 [DERIVED]

## refactor notes
- Renaming/moving public symbols or the two constants requires updating importers `shared/polymath_shared/vocabulary_mapping.py` and `workers/workers/summary_worker_impl.py` (FACTS.importers).
- `summary_jobs` state literals `'READY'`, `'RETRY_WAIT'`, `'RUNNING'`, `'COMPLETE'` — shared/polymath_shared/corpus_mapping.py:22-23, shared/polymath_shared/corpus_mapping.py:143, shared/polymath_shared/corpus_mapping.py:192 — are a shared contract with the ticket enqueuer; changing them orphans in-flight tickets.
- `ON CONFLICT (input_hash) DO NOTHING` (shared/polymath_shared/corpus_mapping.py:174) assumes a uniqueness constraint on `summary_artifacts.input_hash`; schema changes break idempotency.
- The `"csa_" + content_hash(...)[:32]` derivation (shared/polymath_shared/corpus_mapping.py:168) is a stable external ID; altering it orphans existing artifacts.
- `corpus_summaries.summary_id = env["artifact_id"]` (shared/polymath_shared/corpus_mapping.py:185) couples this unit to `build_envelope` ID semantics from `polymath_shared.summary_layer` (shared/polymath_shared/corpus_mapping.py:16-17).
- `contract_version` is persisted in both tables (shared/polymath_shared/corpus_mapping.py:171, shared/polymath_shared/corpus_mapping.py:181) but does not enter `input_hash`; bumping it alone reuses old artifacts via the `"EXISTING"` path — shared/polymath_shared/corpus_mapping.py:139-145 [INFERRED]
- All SQL uses `%s` paramstyle — shared/polymath_shared/corpus_mapping.py:22-24, shared/polymath_shared/corpus_mapping.py:140, shared/polymath_shared/corpus_mapping.py:149, shared/polymath_shared/corpus_mapping.py:160, shared/polymath_shared/corpus_mapping.py:173-178, shared/polymath_shared/corpus_mapping.py:184 [DERIVED]

## VERIFY
```verify
grep -Fq 'CORPUS_MAPPING_THRESHOLD_DOCS = 100' shared/polymath_shared/corpus_mapping.py
grep -Fq 'CORPUS_MAPPING_DEBOUNCE_MINUTES = 30' shared/polymath_shared/corpus_mapping.py
grep -Fq 'concept_strength = min(1.0, 0.25 + 0.25 * spread)' shared/polymath_shared/corpus_mapping.py
grep -Fq 'artifact_id = "csa_" + content_hash({"in": input_hash})[:32]' shared/polymath_shared/corpus_mapping.py
grep -Eq 'PROCEDURE_USES_TOOL|PROCEDURE_SUPPORTS_CONCEPT' shared/polymath_shared/corpus_mapping.py
test "$(grep -c -F 'from polymath_shared.summary_layer import build_envelope' shared/polymath_shared/corpus_mapping.py)" -ge 2
! grep -Fq 'import json' shared/polymath_shared/corpus_mapping.py
```
