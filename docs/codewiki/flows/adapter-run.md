# flow: adapter-run
A governed Trail adapter run: start, next / submit loop, result and report.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | ENTRY `POST /adapter/start` — `adapter_start` calls the principal gate (`require_adapter_start`, marked FRIENDS-ACCESS-V1 D5), then one `tx()` [DERIVED] | orchestrator/orchestrator/api/adapter.py:85-91 | `StartRequest{adapter_id, input, request_options}` -> run ref dict | 404 unknown adapter; 422 ContractViolation/SubmissionRejected (adapter.py:92-95) |
| 2 | `current_principal`: contextvar id -> registry record lookup; missing/inactive record refused [DERIVED] | orchestrator/orchestrator/web_scope.py:61-69 | principal id -> `Principal` | 403 PRINCIPAL_UNKNOWN "this account is not active" |
| 3 | `REGISTRY.get`: cached read of the principals file keyed by `(path, mtime_ns, ino, size)`; file must be owner-only (`chmod 600`) [DERIVED] | orchestrator/orchestrator/web_scope.py:33-51; orchestrator/orchestrator/web_accounts.py:88-90 | `POLYMATH_MCP_PRINCIPALS_FILE` -> principals doc | silent: OSError/ValueError -> doc `None`, error only in `last_error` |
| 4 | record validation: `enabled`/`revoked_at`/`expires_at` (unreadable expiry = expired, fail closed); scopes, rate, `principal_id` checked [DERIVED] | orchestrator/orchestrator/mcp_principals.py:160-172, 142-157 | record -> `Principal{adapter_ids, corpus_ids, writable_corpus_ids, ...}` | ValueError on invalid record; inactive -> 403 at hop 2 |
| 5 | scope gate: `adapter_id in p.adapter_ids`; corpus_ids collected from `input` + `request_options` via `P._ids`; `require_corpora` [DERIVED] | orchestrator/orchestrator/web_scope.py:126-138, 85-87; orchestrator/orchestrator/mcp_principals.py:138-139 | adapter_id, corpus_ids -> None | 403 ADAPTER_NOT_ALLOWED; 422 CORPUS_IDS_REQUIRED; 403 CORPUS_NOT_ALLOWED |
| 6 | `tx()` — pooled connection (dsn `get_settings().postgres.dsn`, min_size=1, max_size=8, autocommit False); commit on clean exit, rollback on exception [DERIVED] | shared/polymath_shared/db.py:44-54, 34-40, 23-31 | -> `Connection` | any later exception rolls the whole unit back |
| 7 | `manifest_for` registry lookup for the adapter [DERIVED] | shared/polymath_shared/adapter/service.py:103, 65-69 | adapter_id -> `Manifest` | `UnknownAdapter` -> 404 (adapter.py:92-93) |
| 8 | request validated (`assert_valid("adapter_run_request", ...)`); idempotency key namespaced per owner `f"{key}@{owner_principal_id}"`; existing run returned untouched [DERIVED] | shared/polymath_shared/adapter/service.py:105-112 | `request_options.idempotency_key` -> existing run_ref | none — silent dedupe |
| 9 | durable run created: `run_id = "adr_" + sha256(seed)[:32]` (seed `f"{adapter_id}:{key}"` or `f"{adapter_id}:{uuid4}"`); status set `running`; `insert_run` + `set_run_owner` [DERIVED] | shared/polymath_shared/adapter/service.py:113-120 | seed -> run row | - |
| 10 | `run_ref` built and validated (`assert_valid("adapter_run_ref", ref)`) [DERIVED] | shared/polymath_shared/adapter/service.py:124-132 | run_id -> `{run_id, adapter_id, adapter_version, workflow_version, created_at, status}` | `UnknownRun` |
| 11 | ENTRY `GET /adapter/{run_id}/next` — `adapter_next` -> `_own` -> `next_step` [DERIVED] | orchestrator/orchestrator/api/adapter.py:99-105 | run_id -> step view or status | 404 UnknownRun (adapter.py:104-105) |
| 12 | RUN OWNERSHIP (migration 0066): with a principal, only a run whose `owner_principal_id` equals it is reachable; NULL owner is legacy, never public; no principal = trusted-local, unchanged [DERIVED] | orchestrator/orchestrator/api/adapter.py:47-53; shared/polymath_shared/adapter/service.py:90-97 | principal id -> None | 403 "no such run for this principal" — one answer for not-yours and no-such-run |
| 13 | `next_step`: `status()`; if status in `("awaiting_agent", "awaiting_harness")` and current step row `issued` -> `{"kind": "step", step, status, evidence}`; else `{"kind": "status", ...}` [DERIVED] | shared/polymath_shared/adapter/service.py:154-167 | run -> step payload | falls to status view when nothing awaits |
| 14 | `_readable_evidence`: stored step outputs hydrated (`EB.hydrate`) for exactly `step.context.evidence_refs` [DERIVED] | shared/polymath_shared/adapter/service.py:245-251 | evidence_refs + stored steps -> `{rows, receipts}` | silent: `{"rows": [], "receipts": [], "error": ...}` — step still delivered |
| 15 | `_materials` (ADR-0020 addendum): opt-in via manifest `config.show` (dotted paths over `outputs` / `input` / `semantics`); byte budget `MATERIALS_MAX_BYTES`; returns `{values, missing, too_large, authority}` [DERIVED] | shared/polymath_shared/adapter/service.py:174-208 | show paths -> materials dict | silent: no `show` -> no key at all; failure -> error dict |
| 16 | `_semantics` (only when a show path starts `semantics`): `SV.build`/`SV.scope` + `RG.harvest` research_gaps; a read of ledger + outputs + steps, never stored [DERIVED] | shared/polymath_shared/adapter/service.py:211-220, 190-192 | hypotheses + outputs -> semantic scope | - |
| 17 | ENTRY `POST /adapter/{run_id}/submit` — submission dict built (`run_id, step_id, payload, submitted_by{agent_identity, model}, kind`); run off the event loop in a threadpool (B-25: the FOR UPDATE row wait froze the loop), principal carried via `acting_as` [DERIVED] | orchestrator/orchestrator/api/adapter.py:109-130, 56-66; shared/polymath_shared/principal_context.py:29-37 | `SubmitRequest` -> submission | 404; 422 `{"rejected": errors}`; ContractViolation -> 422 |
| 18 | `submit`: `load_run(for_update=True)` row lock; `current_step`; defaults `submitted_at`, `submission_hash` [DERIVED] | shared/polymath_shared/adapter/service.py:254-267 | submission -> state + step | SubmissionRejected "no step has been issued" |
| 19 | `T.accept_submission`; on manifest drift (redeploy renamed/removed the awaited step, B-57) -> `MANIFEST_VERSION_UNAVAILABLE` with `_drift`; any rejection receipted on the step row and COMMITTED (B-48), step stays `issued` [DERIVED] | shared/polymath_shared/adapter/service.py:269-283, 511-513; orchestrator/orchestrator/api/adapter.py:118-121 | step + sub -> new_state | SubmissionRejected; run stays parked (deploy rollback resumes, cancel ends) |
| 20 | HARNESS_ACTION branch: `_receipt_too_large` pre-builds the `evidence.admit` envelope and measures it via `trail_client.admission_overflow`; over limit -> refusal naming bytes, limit, observations-that-fit; fits -> `record_receipt`, output gains `_harness_action_id` + `_receipt_hash`, accepted receipt [DERIVED] | shared/polymath_shared/adapter/service.py:285-302, 331-355 | HarnessResearchReceiptV1 -> bound output | `RECEIPT_TOO_LARGE`; step stays issued for a smaller receipt — nothing trimmed |
| 21 | gap gates: `RG.unowned_gap_errors` (a gap belongs to exactly one LIVE hypothesis) + `RG.gap_wire_errors` (B-22 role must be one Trail accepts) [DERIVED] | shared/polymath_shared/adapter/service.py:303-305 | payload gaps -> errors | SubmissionRejected; step stays issued |
| 22 | `_apply_theta` (θ ledger): `hypotheses` (GENERATE, theta_op allow-list incl. `generate_hypotheses`, `split_hypotheses`, `derive_mechanisms`, `cross_map_frictions`, `derive_physical_jobs`, `derive_analogies`, `generate_product_mechanisms`; budget `max_hypotheses` default 8) and/or `transitions` (REVISE/SPLIT) validated then persisted; payload gains the ids; all-or-nothing (B-48) [DERIVED] | shared/polymath_shared/adapter/service.py:311-320, 358-390 | payload -> output + hypothesis/transition ids | `HypothesisRejected` -> errors prefixed `"hypotheses: "` |
| 23 | accept: output merged into state; receipt `accepted` with `evidence_ids = sorted(_cited(payload))`, `receipt_hash = stable_hash(...)`; `finish_step(accepted, receipt, output, submission)` + `save_state`; returns `status` view [DERIVED] | shared/polymath_shared/adapter/service.py:316-328, 774-790 | output -> status view | `assert_valid("adapter_step_receipt", r)` |
| 24 | ENTRY `GET /adapter/{run_id}/result` — `adapter_result` -> `_own` -> `service.result` [DERIVED] | orchestrator/orchestrator/api/adapter.py:191-199; shared/polymath_shared/adapter/service.py:475-477 | run_id -> result | 404 UnknownRun; 409 NotTerminal `run is not terminal (status ...)` |

## state written
All writes below share one `tx()` unit — commit on clean exit, rollback on exception (shared/polymath_shared/db.py:44-54).

- Postgres run row: `store.insert_run(conn, state, m, idempotency_key=f"{adapter_id}:{key}", agent_identity=...)` — shared/polymath_shared/adapter/service.py:117-118 [DERIVED]
- Run ownership: `store.set_run_owner(conn, run_id, owner_principal_id)` — shared/polymath_shared/adapter/service.py:119-120 [DERIVED]
- Run state snapshots: `store.save_state(conn, new_state)` — shared/polymath_shared/adapter/service.py:296, 322 [DERIVED]
- Step rows: `store.finish_step(..., status="issued"|"accepted", receipt, output, submission)` — shared/polymath_shared/adapter/service.py:277, 295, 309, 321 [DERIVED]
- Harness receipts: `store.record_receipt(conn, action_id, rec, rhash)`; output carries `_receipt_hash` — shared/polymath_shared/adapter/service.py:293-295 [DERIVED]
- Hypothesis revisions + transitions: `store.insert_hypothesis_revisions` / `store.insert_transitions` — shared/polymath_shared/adapter/service.py:388-389 [DERIVED]
- Receipts are validated dicts (`assert_valid("adapter_step_receipt", r)`) hashed via `stable_hash` — shared/polymath_shared/adapter/service.py:788-789 [DERIVED]
- Pool: dsn from `get_settings().postgres.dsn`, `min_size=1`, `max_size=8`, `kwargs={"autocommit": False}` — shared/polymath_shared/db.py:23-31 [DERIVED]
- Table names are not shown in SOURCE; access is via `store.*` calls only. [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PRINCIPALS_FILE` | unset (`""` -> `registry_path()` None) | no registry: `REGISTRY.get()` returns None, so any principal-context request reaches the `PRINCIPAL_UNKNOWN` refusal | orchestrator/orchestrator/web_accounts.py:88-90; orchestrator/orchestrator/web_scope.py:33-36 [DERIVED] |
| registry file mode | must be owner-only | `st.st_mode & 0o077` non-zero -> ValueError "must be owner-only (chmod 600)"; doc becomes None, error only in `last_error` | orchestrator/orchestrator/web_scope.py:45-49 [DERIVED] |
| `request_options.idempotency_key` | absent | present + owner -> namespaced `f"{key}@{owner_principal_id}"`; a repeat start returns the existing run instead of creating one | shared/polymath_shared/adapter/service.py:106-112 [DERIVED] |
| manifest `config.show` | absent | no `materials` key at all in the next payload; only `semantics.*` paths trigger the semantic view build | shared/polymath_shared/adapter/service.py:184-192 [DERIVED] |

## failure modes
1. 404 `unknown adapter ...` -> adapter_id absent from the manifest registry (KeyError) -> shared/polymath_shared/adapter/service.py:65-69; orchestrator/orchestrator/api/adapter.py:92-93.
2. 403 ADAPTER_NOT_ALLOWED / 422 CORPUS_IDS_REQUIRED / 403 CORPUS_NOT_ALLOWED -> principal may start only its adapters on named, visible libraries -> orchestrator/orchestrator/web_scope.py:132-138, 85-87.
3. 403 PRINCIPAL_UNKNOWN "this account is not active" -> no active record, or the registry file is missing/unreadable/wrongly permissioned. Silent fallback: `REGISTRY.get` swallows OSError/ValueError into `last_error` and returns None. An unreadable `expires_at` reads as expired (fail closed) -> orchestrator/orchestrator/web_scope.py:61-69, 33-51; orchestrator/orchestrator/mcp_principals.py:168.
4. 403 `no such run for this principal` on next/submit/result -> `NotRunOwner`: run missing, owner mismatch, or NULL owner under a principal context (NULL is legacy, never public) -> orchestrator/orchestrator/api/adapter.py:47-53; shared/polymath_shared/adapter/service.py:90-97.
5. 422 rejected with `MANIFEST_VERSION_UNAVAILABLE: ...` -> a redeploy renamed/removed the step this run awaits; run stays parked (deploy rollback resumes it, cancel ends it) -> shared/polymath_shared/adapter/service.py:275-277, 511-513.
6. 422 `RECEIPT_TOO_LARGE: ...` -> the `evidence.admit` envelope for this harness receipt would exceed TrailSignal's byte limit; step stays `issued` for a smaller receipt, nothing is trimmed for the agent -> shared/polymath_shared/adapter/service.py:331-355, 288-292.
7. 422 gap errors -> a research gap not owned by exactly one LIVE hypothesis, or a gap role Trail's compiler rejects (B-22) -> shared/polymath_shared/adapter/service.py:303-305.
8. 422 errors prefixed `"hypotheses: "` -> `HypothesisRejected` from the θ ledger; step stays `issued` -> shared/polymath_shared/adapter/service.py:311-320.
9. Whole-server freeze during submit (historical, B-25) -> `submit`/`cancel` wait on the FOR UPDATE row lock the step worker holds for an entire step; waiting on the event loop froze every other request until health probes restarted the orchestrator. The wait now runs in a threadpool with the principal carried by `acting_as` -> orchestrator/orchestrator/api/adapter.py:56-66; shared/polymath_shared/principal_context.py:29-37.
10. Silent fallbacks on the read path: evidence hydration failure -> `{"rows": [], "receipts": [], "error": ...}` with the step still delivered (shared/polymath_shared/adapter/service.py:250-251); materials failure -> error dict (shared/polymath_shared/adapter/service.py:207-208) or no key at all when `config.show` cannot be determined (shared/polymath_shared/adapter/service.py:184-188).
11. A rejected submission leaves a durable trace anyway (B-48) -> the refusal is receipted on the step row and the transaction COMMITS that receipt instead of rolling it back -> shared/polymath_shared/adapter/service.py:278-283; orchestrator/orchestrator/api/adapter.py:118-121.

## invariants
- INVARIANT a principal starts only its own adapters, on only its libraries, and must name them (corpus_ids required) — orchestrator/orchestrator/web_scope.py:126-138 [DERIVED]
- INVARIANT an idempotency key is per owner: `f"{key}@{owner_principal_id}"` — never another principal's run — shared/polymath_shared/adapter/service.py:107-108 [DERIVED]
- INVARIANT a NULL `owner_principal_id` is legacy state, never "public" — shared/polymath_shared/adapter/service.py:92 [DERIVED]
- INVARIANT a rejected submission leaves the step ISSUED — the agent may retry — shared/polymath_shared/adapter/service.py:281 [DERIVED]
- INVARIANT evidence ids stay the citation contract; hydrated evidence and materials travel as SIBLING keys of the step, AdapterStepV1 unchanged — shared/polymath_shared/adapter/service.py:255-256, 176-177 [DERIVED]
- INVARIANT materials authority is `PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence` — shared/polymath_shared/adapter/service.py:348 [DERIVED]
- INVARIANT θ writes are all-or-nothing: hypotheses and transitions are both validated before anything is inserted — shared/polymath_shared/adapter/service.py:366-370 [DERIVED]
- INVARIANT the readable view never takes adapter_next down — failures are SAID, never raised — shared/polymath_shared/adapter/service.py:246, 349 [DERIVED]
- INVARIANT the status view reports the versions the RUN started under, not the current manifest (B-57) — shared/polymath_shared/adapter/service.py:151 [DERIVED]
- INVARIANT an unreadable expiry is an expired one — fail closed — orchestrator/orchestrator/mcp_principals.py:168 [DERIVED]
- INVARIANT one transaction per request: commit on clean exit, rollback on exception — shared/polymath_shared/db.py:44-54 [DERIVED]

## VERIFY
```verify
grep -Fq 'FRIENDS-ACCESS-V1 D5' orchestrator/orchestrator/api/adapter.py
grep -Fq 'never another principal' shared/polymath_shared/adapter/service.py
grep -Fq 'MANIFEST_VERSION_UNAVAILABLE' shared/polymath_shared/adapter/service.py
grep -Fq 'RECEIPT_TOO_LARGE' shared/polymath_shared/adapter/service.py
grep -Fq 'POLYMATH_MCP_PRINCIPALS_FILE' orchestrator/orchestrator/web_accounts.py
grep -Fq 'no such run for this principal' orchestrator/orchestrator/api/adapter.py
grep -Fq 'chmod 600' orchestrator/orchestrator/web_scope.py
test "$(grep -c -F 'def tx' shared/polymath_shared/db.py)" -ge 1
```
