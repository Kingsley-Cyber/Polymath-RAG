# flow: adapter-run
A governed Trail adapter run: start, next / submit loop, result and report.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | ENTRY POST /adapter/start -> `adapter_start` calls `require_adapter_start` (FRIENDS-ACCESS-V1 D5; same rule Server A applies, resource START) | orchestrator/orchestrator/api/adapter.py:85-91 [DERIVED]; orchestrator/orchestrator/web_scope.py:126-129 [DERIVED] | StartRequest{adapter_id, input, request_options} -> pass or refuse | 403 `ADAPTER_NOT_ALLOWED`; 422 `CORPUS_IDS_REQUIRED`; 403 `CORPUS_NOT_ALLOWED` (web_scope.py:132-137, 85-92) |
| 2 | Principal resolution: `principal_context.current()` (None = legacy/trusted-local, gate returns) -> registry record -> `P._active` -> `principal_from_record` | orchestrator/orchestrator/web_scope.py:61-69, 129-131 [DERIVED]; orchestrator/orchestrator/mcp_principals.py:165-177, 147-162 [DERIVED] | contextvar pid -> Principal | 403 `PRINCIPAL_UNKNOWN`; disabled / revoked / expired refused; unreadable `expires_at` counts as expired (fail closed) (mcp_principals.py:166-173) |
| 3 | Registry file read, stat-keyed cache `(path, st_mtime_ns, st_ino, st_size)`; mode must be owner-only | orchestrator/orchestrator/web_scope.py:33-51 [DERIVED]; orchestrator/orchestrator/web_accounts.py:88-90 [DERIVED] | file -> principals doc | not chmod 600 -> ValueError, doc None, cause stored in `last_error` — caller only sees `PRINCIPAL_UNKNOWN` (web_scope.py:45-49) |
| 4 | Transaction: `tx()` yields pooled connection, commit on clean exit, rollback on exception; pool `min_size=1`, `max_size=8`, `autocommit=False` | shared/polymath_shared/db.py:44-54, 34-40, 23-31 [DERIVED] | — | exception anywhere rolls the unit back |
| 5 | start: manifest lookup + schema validation `assert_valid("adapter_run_request", ...)` | shared/polymath_shared/adapter/service.py:103, 105, 65-69 [DERIVED] | adapter_id + payload -> Manifest | UnknownAdapter -> 404; ContractViolation -> 422 (adapter.py:92-94) |
| 6 | start: idempotency — key becomes `f"{key}@{owner_principal_id}"`; `find_run_by_idempotency(conn, f"{adapter_id}:{key}")` returns the existing run | shared/polymath_shared/adapter/service.py:106-112 [DERIVED] | idempotency_key -> replayed run_ref | replay short-circuits creation |
| 7 | start: create run — `run_id = "adr_" + sha256(seed)[:32]` (seed = `adapter:key` or `adapter:uuid4`); `T.start_run`, status -> `running`; `insert_run` (+idempotency_key, agent_identity); `set_run_owner`; `run_ref` asserts `adapter_run_ref` | shared/polymath_shared/adapter/service.py:113-121, 124-132 [DERIVED] | payload -> run row + owner + ref {run_id, adapter_id, adapter_version, workflow_version, created_at, status} | `run_ref` raises UnknownRun if the row vanished (service.py:126-128) |
| 8 | ENTRY GET next -> `_own`: `assert_owner` vs `principal_context.current()` | orchestrator/orchestrator/api/adapter.py:99-105, 47-53 [DERIVED]; shared/polymath_shared/adapter/service.py:90-97 [DERIVED] | run_id -> ownership ok | 403 "no such run for this principal" (one answer for not-yours and no-such-run); UnknownRun -> 404 |
| 9 | `next_step` -> `status`: load_run, manifest, `run_status_view` with `identity` = the versions the RUN started under (B-57) | shared/polymath_shared/adapter/service.py:154-158, 143-151 [DERIVED] | run_id -> status view | UnknownRun -> 404 |
| 10 | Issued-step branch: status in `("awaiting_agent", "awaiting_harness")` and current step `status == "issued"` -> `{"kind": "step", step, status, evidence}`; else `{"kind": "status"}` | shared/polymath_shared/adapter/service.py:159-167 [DERIVED] | run -> step envelope | — |
| 11 | Evidence hydration: `EB.hydrate(evidence_refs, stored step outputs)` — ids stay the citation contract (GOVERNGED-CONVERGENCE-V1 TG2a) | shared/polymath_shared/adapter/service.py:245-251 [DERIVED] | refs -> readable rows | any Exception -> `{"rows": [], "receipts": [], "error": ...}` capped at 500 chars; never takes adapter_next down |
| 12 | Materials (opt-in): manifest `config.show` name -> dotted path over `outputs` / `input` / `semantics` under a `MATERIALS_MAX_BYTES` budget; authority string `PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence` | shared/polymath_shared/adapter/service.py:174-208 [DERIVED] | scope -> {values, missing, too_large} | no `config.show` (or undeterminable) -> no `materials` key at all; failure -> error dict, never raised (service.py:181-187, 207-208) |
| 13 | Semantics build: any `semantics.*` show-path triggers `_semantics` — `SV.build`/`SV.scope` + `RG.harvest` -> `research_gaps`; never stored | shared/polymath_shared/adapter/service.py:191-192, 211-220 [DERIVED] | ledger + outputs -> OpportunitySemanticViewV1 | — |
| 14 | ENTRY POST submit -> `adapter_submit` builds submission {run_id, step_id, payload, submitted_by{agent_identity, model?}, kind?} | orchestrator/orchestrator/api/adapter.py:109-112 [DERIVED] | SubmitRequest -> submission | — |
| 15 | Off the event loop (B-25): submit/cancel take the run's FOR UPDATE row lock, which the worker holds for a whole step; the wait runs in `run_in_threadpool`, principal carried by `acting_as` | orchestrator/orchestrator/api/adapter.py:56-66 [DERIVED]; shared/polymath_shared/principal_context.py:29-37 [DERIVED] | closure -> result | waiting on the event loop froze every other request until health probes failed (docstring, B-25) |
| 16 | submit core: `load_run(for_update=True)`, manifest, current step, sub defaults (`submitted_at`, `submission_hash`), `T.accept_submission` | shared/polymath_shared/adapter/service.py:254-271 [DERIVED] | submission -> new_state | no issued step -> SubmissionRejected `["no step has been issued"]`; ManifestError (not ManifestInvalid) -> 422 `MANIFEST_VERSION_UNAVAILABLE` + `_drift`, run parked (service.py:262-263, 272-277, 511-513) |
| 17 | Rejection receipt (B-48): `finish_step(status="issued", receipt=rejected)` then re-raise; the route COMMITS that receipt and answers 422 `{"rejected": exc.errors}` | shared/polymath_shared/adapter/service.py:278-283 [DERIVED]; orchestrator/orchestrator/api/adapter.py:113-128 [DERIVED] | errors -> receipted step row | step stays ISSUED — the agent may retry (service.py:281) |
| 18 | HARNESS_ACTION branch: `_receipt_too_large` preflight builds the `evidence.admit` envelope and measures it by TrailSignal's rule (B-05: keep refusal, no trimming); fits -> `record_receipt`, output gains `_harness_action_id` + `_receipt_hash`, accepted receipt | shared/polymath_shared/adapter/service.py:285-302, 331-355 [DERIVED] | HarnessResearchReceiptV1 -> stored receipt + bound output | 422 `RECEIPT_TOO_LARGE` naming bytes, limit, and how many observations must go; step stays open for a smaller receipt (service.py:350-355) |
| 19 | Gap + theta gates: `RG.unowned_gap_errors` (§9.2: a gap belongs to exactly one LIVE hypothesis) + `RG.gap_wire_errors` (B-22); then `_apply_theta` — `H.generate` / `H.apply`, `max_hypotheses` default 8, all-or-nothing writes (B-48); payload gains `hypothesis_ids` / `hypothesis_transition_ids` | shared/polymath_shared/adapter/service.py:303-320, 358-390, 393-399 [DERIVED] | payload -> output + revisions/transitions | gap errors or HypothesisRejected -> 422, receipted, step stays issued (service.py:307-310, 316-320) |
| 20 | Accept + persist: outputs merged, accepted receipt (`evidence_ids=sorted(_cited(payload))`, `receipt_hash = stable_hash`), `finish_step(accepted)`, `save_state`, return `status` | shared/polymath_shared/adapter/service.py:321-328, 774-790 [DERIVED] | new_state -> persisted run + step | receipt reason copies are bounded (B-02/B-04, `RECEIPT_ERROR_MAX` / `FAILURE_MESSAGE_MAX`) (service.py:776-781) |
| 21 | ENTRY GET result -> `_own` then `service.result` (loads the run); route maps UnknownRun -> 404, NotTerminal -> 409 `run is not terminal (status ...)` | orchestrator/orchestrator/api/adapter.py:191-199 [DERIVED]; shared/polymath_shared/adapter/service.py:475-477 [DERIVED] | run_id -> terminal result | 404; 409 while non-terminal |

## state written

| what | anchor |
|---|---|
| Postgres run row: state, `idempotency_key`, `agent_identity` — `store.insert_run` | shared/polymath_shared/adapter/service.py:117-118 [DERIVED] |
| Run ownership (`owner_principal_id`, migration 0066) — `store.set_run_owner` | shared/polymath_shared/adapter/service.py:119-120 [DERIVED]; orchestrator/orchestrator/api/adapter.py:48 [DERIVED] |
| Run state on accepted submissions / harness receipts — `store.save_state` | shared/polymath_shared/adapter/service.py:301, 327 [DERIVED] |
| Step rows: status `issued`/`accepted`, receipt, output, submission — `store.finish_step` | shared/polymath_shared/adapter/service.py:282, 291, 300, 309, 319, 326 [DERIVED] |
| Step receipts, schema-validated `adapter_step_receipt`, `receipt_hash = stable_hash(r)` | shared/polymath_shared/adapter/service.py:783-789 [DERIVED] |
| Harness receipt + `stable_hash` — `store.record_receipt` | shared/polymath_shared/adapter/service.py:293-294 [DERIVED] |
| θ ledger: immutable hypothesis revisions + transitions — `store.insert_hypothesis_revisions` / `store.insert_transitions` | shared/polymath_shared/adapter/service.py:387-389 [DERIVED] |
| File (read-only here): principals registry, owner-only mode enforced | orchestrator/orchestrator/web_scope.py:45-47 [DERIVED] |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PRINCIPALS_FILE` | unset -> `registry_path()` returns None | with a principal context, `REGISTRY.get()` returns None and the request refuses `PRINCIPAL_UNKNOWN` [INFERRED: get returns None on a None path, refuse follows] | orchestrator/orchestrator/web_accounts.py:88-90; orchestrator/orchestrator/web_scope.py:34-36, 67-68 |
| `request_options.idempotency_key` | absent | with an owner becomes `f"{key}@{owner_principal_id}"`; a repeat returns the earlier run | shared/polymath_shared/adapter/service.py:106-112 |
| `input.corpus_ids` / `request_options.corpus_ids` | absent | both absent -> 422 `CORPUS_IDS_REQUIRED` | orchestrator/orchestrator/web_scope.py:134-137 |
| manifest step `config.show` | absent | absent -> no `materials` key in the next response | shared/polymath_shared/adapter/service.py:181-187 |
| show-path prefix `semantics` | — | any `semantics.*` path triggers the `_semantics` build | shared/polymath_shared/adapter/service.py:191-192 |
| `m.budgets.max_hypotheses` | `8` | generate budget = 8 minus live (non-absorbed) hypotheses | shared/polymath_shared/adapter/service.py:363, 373 |
| admit `config.hypotheses_from` | — | `== "context.semantics.trail"` -> size preflight uses the closed extended wire | shared/polymath_shared/adapter/service.py:342-343 |
| `request_options.agent_identity` | absent | stored on the run row at insert | shared/polymath_shared/adapter/service.py:117-118 |
| registry cache key `(path, mtime_ns, ino, size)` | — | file swap detected by stat; reload under lock | orchestrator/orchestrator/web_scope.py:41-43 |

## failure modes

1. 404 `unknown adapter ...` -> adapter_id absent from the registry -> `manifest_for` KeyError -> UnknownAdapter (shared/polymath_shared/adapter/service.py:65-69; orchestrator/orchestrator/api/adapter.py:92-93).
2. 403 `ADAPTER_NOT_ALLOWED` / 422 `CORPUS_IDS_REQUIRED` / 403 `CORPUS_NOT_ALLOWED` -> scope gate refuses (orchestrator/orchestrator/web_scope.py:132-137, 85-92).
3. 403 `PRINCIPAL_UNKNOWN` -> record missing, `enabled` not True, `revoked_at` set, or expired; an unreadable `expires_at` is treated as expired (orchestrator/orchestrator/mcp_principals.py:166-173).
4. Silent registry failure -> file mode not owner-only raises ValueError inside `get()`; `_doc` becomes None and `last_error` holds the cause — the request surfaces only as `PRINCIPAL_UNKNOWN` (orchestrator/orchestrator/web_scope.py:45-49).
5. 403 "no such run for this principal" -> owner mismatch or absent run; a NULL owner is legacy state, never public (shared/polymath_shared/adapter/service.py:90-97; orchestrator/orchestrator/api/adapter.py:52-53).
6. 422 `MANIFEST_VERSION_UNAVAILABLE` -> a redeploy renamed/removed the awaited step; run stays parked — deploy rollback resumes it, cancel ends it (shared/polymath_shared/adapter/service.py:272-277).
7. 422 `{"rejected": [...]}` with a committed receipt -> validation / gap / hypothesis refusal; the step stays ISSUED for retry (shared/polymath_shared/adapter/service.py:278-283, 303-310, 316-320; orchestrator/orchestrator/api/adapter.py:117-128).
8. 422 `RECEIPT_TOO_LARGE` -> admission preflight over TrailSignal's limit; names bytes, limit, and how many observations to drop; nothing is trimmed (shared/polymath_shared/adapter/service.py:331-355).
9. Silent evidence fallback -> hydration exception returns `{"rows": [], "receipts": [], "error": ...}`; the agent still gets its step (shared/polymath_shared/adapter/service.py:250-251).
10. Silent materials fallback -> `config.show` missing or unreadable yields no key; a later failure yields an error dict, never an exception (shared/polymath_shared/adapter/service.py:181-187, 207-208).
11. 409 `run is not terminal (status ...)` -> result requested before a terminal status (orchestrator/orchestrator/api/adapter.py:198-199).
12. Event-loop freeze (B-25, historical) -> submit/cancel waited on the FOR UPDATE row lock the worker holds for a whole step, freezing all requests until restart; fixed by threadpool + `acting_as` (orchestrator/orchestrator/api/adapter.py:57-66).

## invariants

- INVARIANT a principal starts only its adapters, on only its libraries, and must name them via corpus_ids (orchestrator/orchestrator/web_scope.py:127-129) [DERIVED]
- INVARIANT an idempotency key is per owner: `f"{key}@{owner_principal_id}"` — never another principal's run (shared/polymath_shared/adapter/service.py:107-108) [DERIVED]
- INVARIANT `run_id = "adr_" + sha256(f"{adapter_id}:{key or uuid.uuid4()}").hexdigest()[:32]` (shared/polymath_shared/adapter/service.py:113-114) [DERIVED]
- INVARIANT one answer for "not yours" and "no such run"; no principal context = the legacy / trusted-local caller, unchanged (orchestrator/orchestrator/api/adapter.py:48-49) [DERIVED]
- INVARIANT with a principal, only a run whose `owner_principal_id` equals it is reachable; a NULL owner is legacy state, never "public" (shared/polymath_shared/adapter/service.py:91-93) [DERIVED]
- INVARIANT a rejected submission leaves the step ISSUED — the agent may retry (shared/polymath_shared/adapter/service.py:281) [DERIVED]
- INVARIANT θ writes are all or nothing: both halves validated before anything is written (shared/polymath_shared/adapter/service.py:366-367) [DERIVED]
- INVARIANT materials authority is `PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence`; nothing in materials is evidence (shared/polymath_shared/adapter/service.py:206, 179) [DERIVED]
- INVARIANT evidence ids stay the citation contract; hydrated rows are the readable sibling key (shared/polymath_shared/adapter/service.py:155-157) [DERIVED]
- INVARIANT an unreadable expiry is an expired one — fail closed (orchestrator/orchestrator/mcp_principals.py:173) [DERIVED]
- INVARIANT receipts keep a bounded copy (head + tail, elision counted) of oversized reasons; the full reason stays on the run's gap / failure and in the rejection's errors (shared/polymath_shared/adapter/service.py:776-778) [DERIVED]
- INVARIANT status views report the versions the RUN started under, not the currently loaded manifest (B-57) (shared/polymath_shared/adapter/service.py:151) [DERIVED]

## VERIFY

```verify
grep -Fq 'FRIENDS-ACCESS-V1 D5' orchestrator/orchestrator/api/adapter.py
grep -Fq 'CORPUS_IDS_REQUIRED' orchestrator/orchestrator/web_scope.py
grep -Fq 'must be owner-only (chmod 600)' orchestrator/orchestrator/web_scope.py
grep -Fq 'no such run for this principal' orchestrator/orchestrator/api/adapter.py
grep -Fq 'MANIFEST_VERSION_UNAVAILABLE' shared/polymath_shared/adapter/service.py
grep -Fq 'RECEIPT_TOO_LARGE' shared/polymath_shared/adapter/service.py
test "$(grep -c -F 'store.finish_step' shared/polymath_shared/adapter/service.py)" -ge 5
```
