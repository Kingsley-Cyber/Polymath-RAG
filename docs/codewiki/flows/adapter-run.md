# flow: adapter-run
A governed Trail adapter run: start, next / submit loop, result and report.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /adapter/start: adapter gate — `adapter_id` must be in the principal's `adapter_ids`; naming no corpus is allowed through | orchestrator/orchestrator/api/adapter.py:93-99; orchestrator/orchestrator/web_scope.py:168-181 | adapter_id, input, request_options -> None | 403 `ADAPTER_NOT_ALLOWED` |
| 2 | Principal resolved from registry (stat-cached, owner-only file mode enforced) and active-checked; record -> `Principal` | orchestrator/orchestrator/web_scope.py:46-64, 74-82; orchestrator/orchestrator/mcp_principals.py:238-250, 217-235, 360-366 | principal_id -> Principal or None | 403 `PRINCIPAL_UNKNOWN`; unreadable expiry = expired (fail closed) |
| 3 | Named corpora authorized: ids gathered from `input.corpus_ids` and `request_options.corpus_ids`, each checked against the grant (wildcard honored, private libraries excluded) | orchestrator/orchestrator/web_scope.py:108-110, 103-105, 94-100; shared/polymath_shared/query_scope.py:96-103; orchestrator/orchestrator/mcp_principals.py:213-214 | corpus id lists -> None | 403 `CORPUS_NOT_ALLOWED` |
| 4 | Start offloaded to a worker thread; the request's principal re-attached via `acting_as` (B-25 row-lock fix) | orchestrator/orchestrator/api/adapter.py:57-67, 102-107; shared/polymath_shared/principal_context.py:29-37 | `_start` closure -> dict | event-loop freeze if run on the loop (historical) |
| 5 | One transaction on the workflow authority (pool min 1 / max 8, commit on clean exit, rollback on exception) | shared/polymath_shared/db.py:44-54, 34-40, 23-31 | — -> Connection | any exception rolls back |
| 6 | Manifest resolved by `adapter_id` from the registry | shared/polymath_shared/adapter/service.py:67-71, 59-60 | adapter_id -> Manifest | `UnknownAdapter` -> 404 |
| 7 | Idempotency: key scoped per owner (`f"{key}@{owner_principal_id}"`); an existing run is replayed with its start receipt | shared/polymath_shared/adapter/service.py:120-126, 143-148 | idempotency_key -> prior run dict | none |
| 8 | `run_id` derived (`"adr_" + sha256[:32]`); the requester's raw input validated by `T.start_run` before anything is derived | shared/polymath_shared/adapter/service.py:127-133 | seed -> run_id | `ContractViolation` -> 422 |
| 9 | Start-time scope, only when the entry step config names `seed_check` / `corpus_scope` / `corpus_seed` | shared/polymath_shared/adapter/service.py:131-133, 151-179 | input, opts -> input, opts, receipt | `StartRefused` 422 typed |
| 10 | Seed domain check on a given seed; requester-supplied `{field}_origin` popped first | shared/polymath_shared/adapter/service.py:154-160, 182-199 | seed -> verdict | `SEED_NOT_GENERATIVE` / domain gap code; a `DomainCrash` is only recorded |
| 11 | Corpus scope resolved; `origin == "default"` writes `opts["corpus_ids"]`; "all libraries" narrowed by `all_libraries_view` (owner: all but friends' private; friend: its grant incl. wildcard) | shared/polymath_shared/adapter/service.py:161-166; orchestrator/orchestrator/web_scope.py:113-119, 85-91 | corpus_view -> scope | none |
| 12 | Corpus-derived seed when none given; runtime stamps `inp[f"{field}_origin"] = "corpus"` with lineage | shared/polymath_shared/adapter/service.py:167-177 | corpora -> seed + lineage | `SEED_UNAVAILABLE` when no corpora in scope |
| 13 | Run persisted: status `running`, `store.insert_run` (+ `idempotency_key`, `agent_identity`), `store.set_run_owner` | shared/polymath_shared/adapter/service.py:134-139 | state -> run row | none |
| 14 | Response = validated AdapterRunRefV1 plus sibling `start_receipt`; refusals mapped (404 / 422 typed / 422 errors) | shared/polymath_shared/adapter/service.py:143-148, 202-210; orchestrator/orchestrator/api/adapter.py:107-113 | run_id -> {ref, start_receipt} | 404 unknown adapter; 422 `StartRefused` |
| 15 | GET /adapter/{id}/next: run ownership asserted — one answer for "not yours" and "no such run"; NULL owner = legacy caller, unchanged | orchestrator/orchestrator/api/adapter.py:48-54, 117-123; shared/polymath_shared/adapter/service.py:92-99 | run_id -> None | 403 "no such run for this principal"; 404 unknown run |
| 16 | Status view built under the versions the run started with (B-57), not the current manifest | shared/polymath_shared/adapter/service.py:221-229 | run_id -> status dict | `UnknownRun` -> 404 |
| 17 | Issued step returned (`awaiting_agent` / `awaiting_harness` + row status `issued`) with hydrated `evidence` sibling (TG2a: `evidence_refs` ids stay the citation contract) | shared/polymath_shared/adapter/service.py:232-244, 373-379 | evidence_refs -> readable rows | hydration failure -> `{"rows": [], "receipts": [], "error": ...}`; step still returned |
| 18 | Optional siblings added: `materials` (manifest `config.show` over outputs/input/semantics, byte-budgeted) and `beside` keys (`config.beside` over outputs/input/prefetch) — opt-in first, no config = no key | shared/polymath_shared/adapter/service.py:302-348, 259-295 | scope paths -> values, missing, too_large | failure SAID (`error` / `beside_error` dicts), never raised |
| 19 | Last rejection surfaced beside an open step (F2): errors capped at 40 | shared/polymath_shared/adapter/service.py:245-249 | row receipt -> `last_rejection` | none |
| 20 | POST /adapter/{id}/submit: ownership + `FOR UPDATE` row lock, wait off the event loop; a `SubmissionRejected` is caught inside the tx so the refusal receipt COMMITS (B-48) | orchestrator/orchestrator/api/adapter.py:127-148; shared/polymath_shared/adapter/service.py:384-390 | submission -> state | 404; 403 ownership; 422 `{"rejected": [...]}` |
| 21 | Submission judged: manifest drift (B-57), law-at-submit for AGENT_REASON (F2, `branch_loops + 1`), harness receipt size, gap ownership + wire (§9.2, B-22), θ ledger apply | shared/polymath_shared/adapter/service.py:392-465 | payload -> output (+ ledger ids) | each refusal receipts the row, step stays `issued`, raises `SubmissionRejected` |
| 22 | Accept path: receipt (hashes, `hypothesis_transition_ids`) written, state saved, run status returned to the worker | shared/polymath_shared/adapter/service.py:466-473, 406-410 | output -> status dict | none |

`GET /adapter/{run_id}/result` (orchestrator/orchestrator/api/adapter.py:209) is named as an entry but is not present in the captured chain; no hop is claimed for it.

## state written

| what | where (anchor) |
|---|---|
| Run row: `store.insert_run(conn, state, m, idempotency_key=(f"{adapter_id}:{key}" ...), agent_identity=opts.get("agent_identity"))` | shared/polymath_shared/adapter/service.py:136-137 |
| Run owner: `store.set_run_owner(conn, run_id, owner_principal_id)` | shared/polymath_shared/adapter/service.py:138-139 |
| Run request options mutated at start: `opts["corpus_ids"]`, `opts["start_receipt"]` (receipt kept beside the ref, in run options, and in the entry step output) | shared/polymath_shared/adapter/service.py:165, 223, 114-115 |
| Step rows + receipts: `store.finish_step(..., status="issued"/"accepted", receipt=receipt, output=..., submission=...)`; a rejected receipt survives the raised exception (B-48 commit) | shared/polymath_shared/adapter/service.py:410, 443, 471; orchestrator/orchestrator/api/adapter.py:135-140 |
| Run state: `store.save_state` (outputs incl. harness receipt bindings and θ ledger ids; `branch_loops` incremented on law refusal) | shared/polymath_shared/adapter/service.py:421-422, 439-444, 466-472 |
| Harness receipts: `store.record_receipt(conn, step["harness_action"]["action_id"], rec, rhash)` | shared/polymath_shared/adapter/service.py:434 |
| Run liveness: `_touch(conn, run_id)` after each refusal | shared/polymath_shared/adapter/service.py:411, 431, 453, 464 |
| Backing store: Postgres "workflow authority" via pooled `tx()` (min_size=1, max_size=8, autocommit False) | shared/polymath_shared/db.py:44-54, 23-31 |
| No Qdrant or file write on this path [INFERRED — no such call appears anywhere in the chain] | shared/polymath_shared/db.py:44-54 |

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| entry config `seed_check` | None | a given seed runs a domain check at start; non-generative refuses with hint | shared/polymath_shared/adapter/service.py:154, 159-160, 182-199 |
| entry config `corpus_scope` | None | named corpora validated now; none named = caller's share of all libraries | shared/polymath_shared/adapter/service.py:161-166 |
| entry config `corpus_seed` | None | no seed -> one derived from the corpora, `<field>_origin: corpus` | shared/polymath_shared/adapter/service.py:167-177 |
| request_options `idempotency_key` | None | per-owner dedupe (`key@owner`); replay returns the existing run + receipt | shared/polymath_shared/adapter/service.py:120-126 |
| `corpus_ids` in input / request_options | none named | allowed through; runtime defaults to the caller's searchable libraries within its grant | orchestrator/orchestrator/web_scope.py:168-181 |
| request_options `agent_identity` | absent | stored on the run row | shared/polymath_shared/adapter/service.py:136-137 |
| submission `submitted_by.model` / `agent_identity` | absent | receipt `model` falls back to agent_identity | orchestrator/orchestrator/api/adapter.py:128-129; shared/polymath_shared/adapter/service.py:413 |
| submission `kind` | absent | included in the submission only if given | orchestrator/orchestrator/api/adapter.py:130 |
| principal context | None = owner / trusted-local caller | None: every library, no ownership filter; a principal: grant-filtered corpora + owned runs only | shared/polymath_shared/principal_context.py:23-25; orchestrator/orchestrator/web_scope.py:85-91; shared/polymath_shared/adapter/service.py:92-99 |
| env `POLYMATH_MCP_PRINCIPALS_FILE` | unset -> None | location of the principal registry; unset disables it | orchestrator/orchestrator/web_accounts.py:101-103 |
| manifest `config.show` | absent | no `materials` sibling key at all | shared/polymath_shared/adapter/service.py:312-316 |
| manifest `config.beside` | absent | no beside sibling keys | shared/polymath_shared/adapter/service.py:266-271 |

## failure modes

1. 403 `{"error_code": "ADAPTER_NOT_ALLOWED"}` -> adapter_id not in the principal's `adapter_ids` -> orchestrator/orchestrator/web_scope.py:176-178
2. 403 `{"error_code": "CORPUS_NOT_ALLOWED"}` -> named library outside the grant; wildcard never reaches a private library; a write grant is explicit membership only -> orchestrator/orchestrator/web_scope.py:103-105, 94-100; shared/polymath_shared/query_scope.py:96-103
3. 403 `PRINCIPAL_UNKNOWN` -> record missing, `enabled` not True, `revoked_at` set, or expired; an unreadable expiry is an expired one (fail closed) -> orchestrator/orchestrator/web_scope.py:79-81; orchestrator/orchestrator/mcp_principals.py:238-250
4. Registry silently unusable -> file mode has 0o077 bits ("must be owner-only (chmod 600)") or schema mismatch; cache holds None with `last_error` -> orchestrator/orchestrator/web_scope.py:58-62; orchestrator/orchestrator/mcp_principals.py:360-366
5. 404 unknown adapter -> manifest registry KeyError -> shared/polymath_shared/adapter/service.py:67-71; orchestrator/orchestrator/api/adapter.py:108-109
6. 422 typed refusal `{error_code, message, hint}` -> `SEED_NOT_GENERATIVE`, a domain gap code, or `SEED_UNAVAILABLE` (no seed, no corpus in scope to derive one) -> shared/polymath_shared/adapter/service.py:173-174, 192-198; orchestrator/orchestrator/api/adapter.py:110-111
7. Seed check silently skipped -> `DomainCrash` recorded as `{"ran": False, "error": ...}`; a broken check never blocks a start -> shared/polymath_shared/adapter/service.py:189-191
8. Whole-server freeze on start/submit/cancel (B-25) -> `FOR UPDATE` row lock held by the step worker for a whole step; waiting on the event loop froze every request until health probes failed; now a threadpool wait with the principal carried explicitly -> orchestrator/orchestrator/api/adapter.py:57-67
9. 403 "no such run for this principal" -> owner mismatch or nonexistent run — deliberately one answer -> orchestrator/orchestrator/api/adapter.py:48-54; shared/polymath_shared/adapter/service.py:92-99
10. 422 rejected "no step has been issued" -> no issued current step at submit time -> shared/polymath_shared/adapter/service.py:389-390
11. 422 `MANIFEST_VERSION_UNAVAILABLE`, run parked -> a redeploy renamed or removed the awaited step (B-57); rollback of the deploy resumes it, cancel ends it -> shared/polymath_shared/adapter/service.py:400-405
12. 422 law errors at submit (F2) -> the law now runs on the submitted payload; a verdict routing back to this step refuses inline and counts one repair loop (previously a 1024 s wait for the worker) -> shared/polymath_shared/adapter/service.py:414-423
13. 422 harness receipt too large -> receipt over budget; the step stays open for a smaller receipt -> shared/polymath_shared/adapter/service.py:427-432
14. 422 gap errors -> a research gap not owned by exactly one LIVE hypothesis, or a role Trail's gap compiler rejects (B-22) -> shared/polymath_shared/adapter/service.py:446-454
15. 422 `"hypotheses: ..."` -> θ ledger rejects generated hypotheses/transitions -> shared/polymath_shared/adapter/service.py:459-465
16. Silent fallbacks on GET next -> evidence hydration, materials and beside failures return error dicts; the agent still gets its step — failures are SAID, never raised -> shared/polymath_shared/adapter/service.py:373-379, 309-316, 335-336, 268-271, 293-295
17. Rejection receipt believed lost -> it is not: B-48 catches `SubmissionRejected` inside the transaction so the receipt commits before the re-raise -> orchestrator/orchestrator/api/adapter.py:135-140

## invariants

- INVARIANT naming no corpus never resolves outside the caller's grant — "no corpus" defaults to the caller's searchable libraries within its grant, the same default for the owner and a friend (orchestrator/orchestrator/web_scope.py:168-173; orchestrator/orchestrator/api/adapter.py:94-97) [DERIVED]
- INVARIANT an idempotency key is per owner — `f"{key}@{owner_principal_id}"` — a replay can never return another principal's run (shared/polymath_shared/adapter/service.py:121-122) [DERIVED]
- INVARIANT the requester's input is schema-valid before anything is derived from it — `T.start_run` precedes `_start_scope` (shared/polymath_shared/adapter/service.py:129-133) [DERIVED]
- INVARIANT the runtime says where the seed came from — `{field}_origin` is popped from requester input and stamped only by derivation (shared/polymath_shared/adapter/service.py:157, 176) [DERIVED]
- INVARIANT the AdapterStepV1 is unchanged on this path: `evidence`, `materials` and `beside` travel as SIBLING keys, `evidence_refs` ids stay the citation contract, and materials are `PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence` (shared/polymath_shared/adapter/service.py:233-235, 304-307, 334) [DERIVED]
- INVARIANT a refused submission leaves the step `issued` so the agent may retry, with the refusal receipted on the step row (shared/polymath_shared/adapter/service.py:406-410) [DERIVED]
- INVARIANT no readable view can take adapter_next down — evidence, materials and beside failures are SAID, not hidden or raised (shared/polymath_shared/adapter/service.py:374, 307-308, 263-264) [DERIVED]
- INVARIANT `acting_as` carries only the request's own principal and never widens anything; without it a missing principal would read as the trusted-local caller (shared/polymath_shared/principal_context.py:29-37) [DERIVED]
- INVARIANT with a principal, only a run whose `owner_principal_id` equals it is reachable; a NULL owner is legacy state, never "public" (shared/polymath_shared/adapter/service.py:92-99) [DERIVED]
- INVARIANT the read wildcard never opens a library for writing and never reaches a private library (orchestrator/orchestrator/web_scope.py:98-99; shared/polymath_shared/query_scope.py:100-103) [DERIVED]
- INVARIANT status and run_ref report the versions the run started under, not the current manifest (B-57) (shared/polymath_shared/adapter/service.py:226-229, 207-208) [DERIVED]

## VERIFY

```verify
grep -Fq 'async def adapter_start' orchestrator/orchestrator/api/adapter.py
grep -Fq 'run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]' shared/polymath_shared/adapter/service.py
grep -Fq 'key = f"{key}@{owner_principal_id}"' shared/polymath_shared/adapter/service.py
grep -Fq 'SEED_UNAVAILABLE' shared/polymath_shared/adapter/service.py
grep -Fq 'the wildcard never opens a library for writing' orchestrator/orchestrator/web_scope.py
grep -Fq 'no such run for this principal' orchestrator/orchestrator/api/adapter.py
test "$(grep -c -F 'raise SubmissionRejected' shared/polymath_shared/adapter/service.py)" -ge 5
```
