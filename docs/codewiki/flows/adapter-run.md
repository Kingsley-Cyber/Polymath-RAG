# flow: adapter-run
A governed Trail adapter run: start, next / submit loop, result and report.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /adapter/start: `require_adapter_start`, then `owner = principal_context.current()` | orchestrator/orchestrator/api/adapter.py:93-100 [DERIVED] | `StartRequest` -> pre-checks or typed refusal | 403 `ADAPTER_NOT_ALLOWED` / `CORPUS_NOT_ALLOWED` / `PRINCIPAL_UNKNOWN` raised before any run exists |
| 2 | Grant gate: `adapter_id` must be in `p.adapter_ids`; every corpus named in `input.corpus_ids` AND `request_options.corpus_ids` must be reachable (naming NONE is allowed through — CORPUS-ACCESS-PARITY) | orchestrator/orchestrator/web_scope.py:168-181 [DERIVED] | principal + named corpus ids -> None | `_refuse("ADAPTER_NOT_ALLOWED", ...)`, `require_corpora` -> `require_corpus` -> `can_see` -> `_refuse("CORPUS_NOT_ALLOWED", ...)` (web_scope.py:103-105, 70-71) |
| 3 | Principal resolved against the registry: mtime+ino+size-cached read, `chmod 600` enforced, unreadable expiry fails closed, profile scopes are a floor never a ceiling, admin scope rejected | orchestrator/orchestrator/web_scope.py:74-82, 46-64; orchestrator/orchestrator/mcp_principals.py:227-239, 206-224 [DERIVED] | principal_id -> `Principal` (or None = trusted local) | `PRINCIPAL_UNKNOWN` "this account is not active" (web_scope.py:80-81) |
| 4 | DB wait moved off the event loop: `run_in_threadpool` + `acting_as(principal)` (B-25: submit/cancel take the run row lock `FOR UPDATE`, which the worker holds for a whole step) | orchestrator/orchestrator/api/adapter.py:57-67; shared/polymath_shared/principal_context.py:29-37 [DERIVED] | closure -> result | without this, every request froze until health probes failed (fixed bug, adapter.py:58-60) |
| 5 | One transaction: pooled connection (`min_size=1`, `max_size=8`, `autocommit=False`), commit on clean exit, rollback on exception | shared/polymath_shared/db.py:44-54, 34-40, 23-31 [DERIVED] | — | exception -> rollback |
| 6 | `service.start`: `manifest_for` (KeyError -> `UnknownAdapter`), `assert_valid("adapter_run_request", ...)`, idempotency replay — key namespaced `f"{key}@{owner_principal_id}"`, lookup `f"{adapter_id}:{key}"` | shared/polymath_shared/adapter/service.py:117-126, 67-71 [DERIVED] | adapter_id + input + options -> existing run's receipt (no new run) | unknown adapter -> 404 (adapter.py:108-109); idempotency key is per owner, never another principal's run (service.py:122) |
| 7 | run_id derived: `"adr_" + hashlib.sha256(seed).hexdigest()[:32]`, seed = `f"{adapter_id}:{key}"` or `f"{adapter_id}:{uuid.uuid4()}"`; `T.start_run` validates the REQUESTER's input before anything is derived | shared/polymath_shared/adapter/service.py:127-129 [DERIVED] | seed string -> run_id | — |
| 8 | Start scope, opt-in via entry step `config` keys `seed_check` / `corpus_scope` / `corpus_seed`; receipt `{"schema_version": START_RECEIPT_VERSION}`; requester's `{field}_origin` popped (only the runtime sets origin) | shared/polymath_shared/adapter/service.py:131-133, 151-179 [DERIVED] | input + opts -> mutated input, opts, receipt | `StartRefused` from seed check or seed derivation |
| 9 | Seed check domain op: verdict `generative` False -> typed refusal with hint; `out["gap"]` -> domain's code; `DomainCrash` recorded `{"ran": False, "error": str(exc)[:500]}` and never blocks the start | shared/polymath_shared/adapter/service.py:182-199 [DERIVED] | seed -> receipt["seed_check"] | `SEED_NOT_GENERATIVE` (or the verdict's `reason_code`) at service.py:196-198 |
| 10 | Corpus default + seed derivation: `scope["origin"] == "default"` -> `opts["corpus_ids"] = list(scope["corpus_ids"])`; no seed and no corpora -> `SEED_UNAVAILABLE`; derived seed sets `inp[field]` and `inp[f"{field}_origin"] = "corpus"` | shared/polymath_shared/adapter/service.py:161-177 [DERIVED] | corpus_ids / seed -> defaulted scope + derived seed | `SEED_UNAVAILABLE` "no seed was given and no corpus is in scope to derive one from" (service.py:173-174) |
| 11 | Run persisted: status `"running"`, `store.insert_run` (idempotency_key, `agent_identity`), `store.set_run_owner` when a principal owns it; reply = run ref + SIBLING `start_receipt` from run options | shared/polymath_shared/adapter/service.py:134-140, 143-148 [DERIVED] | state -> `AdapterRunRefV1` + start_receipt | `assert_valid("adapter_run_ref", ref)` (service.py:209) |
| 12 | GET /adapter/{run_id}/next: `_own` ownership assert, then `next_step` — this path runs on the event loop (no threadpool in its body) | orchestrator/orchestrator/api/adapter.py:117-123, 48-54 [DERIVED]; no-threadpool [INFERRED: body shows a direct `tx()` call] | run_id -> step or status | `NotRunOwner` -> 403 "no such run for this principal" (adapter.py:53-54); `UnknownRun` -> 404 |
| 13 | Ownership rule: no principal = legacy trusted-local unchanged; with a principal only a run whose `owner_principal_id` equals it; NULL owner is legacy state, never "public" | shared/polymath_shared/adapter/service.py:92-99 [DERIVED] | run_id + principal -> None | `NotRunOwner` (service.py:98-99) |
| 14 | `next_step`: status view carries the versions the RUN started under (B-57); if status in `("awaiting_agent", "awaiting_harness")` and the current row `status == "issued"` -> step payload, else `{"kind": "status", ...}` | shared/polymath_shared/adapter/service.py:232-251, 221-229 [DERIVED] | run_id -> step + siblings or status | unknown run -> 404 |
| 15 | Sibling evidence: `EB.hydrate` over `step.context.evidence_refs` joined to stored step outputs; failure returns `{"rows": [], "receipts": [], "error": ...[:500]}` — said, not hidden | shared/polymath_shared/adapter/service.py:373-379 [DERIVED] | evidence_refs + stored outputs -> readable rows | hydration failure never takes adapter_next down (service.py:374, 378) |
| 16 | Sibling materials (ADR-0020): manifest `config.show` name -> dotted path over `outputs` / `input` / `semantics`; `MATERIALS_MAX_BYTES` budget; `missing` / `too_large` listed; authority string `"PRIOR_STEP_OUTPUT — context for reasoning, never citable evidence"` | shared/polymath_shared/adapter/service.py:302-336 [DERIVED] | stored state -> materials or no key | no `config.show` -> NO key at all (service.py:309-316); failure -> error dict (service.py:335-336) |
| 17 | `semantics` built on demand: `OpportunitySemanticViewV1` via `SV.build` + `RG.harvest` research gaps; read-only, never stored | shared/polymath_shared/adapter/service.py:339-348, 319-320 [DERIVED] | hypotheses + outputs -> semantic view | — |
| 18 | Sibling beside (PRODUCT-SEARCH-E2E): `config.beside` name -> path or first-present of a list over `outputs.` / `input.` / `prefetch.`; `BESIDE_MAX_BYTES`; oversize -> `beside_too_large`; failure -> `beside_error` | shared/polymath_shared/adapter/service.py:259-295 [DERIVED] | stored state + row prefetch -> beside keys | no `config.beside` -> `{}` (service.py:270-271); never takes adapter_next down (service.py:293-295) |
| 19 | Last rejection replayed: rejected receipt on the issued row -> `out["last_rejection"] = {"errors": [...][:40], "at": ...}` (F2 — an agent that lost the 422 still sees what to fix) | shared/polymath_shared/adapter/service.py:245-249 [DERIVED] | step row receipt -> last_rejection | — |
| 20 | POST /adapter/{run_id}/submit: submission `{run_id, step_id, payload, submitted_by: {agent_identity, model?}, kind?}`; `_own`; rejection receipts COMMITTED then re-raised (B-48); off-loop via `_off_the_event_loop` | orchestrator/orchestrator/api/adapter.py:127-148, 131-140 [DERIVED] | `SubmitRequest` -> status view | `SubmissionRejected` / `ContractViolation` -> 422 `{"rejected": exc.errors}`; `UnknownRun` -> 404 |
| 21 | `service.submit`: `store.load_run(..., for_update=True)` row lock; no issued row -> `SubmissionRejected(["no step has been issued"])`; `T.accept_submission`; non-invalid `ManifestError` -> `MANIFEST_VERSION_UNAVAILABLE`, run stays parked (B-57) | shared/polymath_shared/adapter/service.py:384-405 [DERIVED] | submission -> new state | 422 "no step has been issued" (service.py:391); 422 `MANIFEST_VERSION_UNAVAILABLE: {_drift(...)}` (service.py:405) |
| 22 | AGENT_REASON: the law that follows the step runs NOW on the submitted payload (F2); a verdict routed back to this step is refused here and counts one repair loop (`branch_loops + 1`); step stays `"issued"` | shared/polymath_shared/adapter/service.py:414-423, 407-411 [DERIVED] | payload -> law verdict or rejection | 422 law errors; step stays issued so the agent may retry (service.py:409) |
| 23 | HARNESS_ACTION: `_receipt_too_large` -> rejected, step stays issued for a smaller receipt; else `store.record_receipt` + `stable_hash`; output gains `_harness_action_id`, `_receipt_hash`, `_host_prefetch` (lineage; never sent to Trail) | shared/polymath_shared/adapter/service.py:424-445 [DERIVED] | `HarnessResearchReceiptV1` -> bound output | 422 too-large errors (service.py:427-432) |
| 24 | Gap + θ ledger: `RG.unowned_gap_errors` (a gap belongs to exactly one LIVE hypothesis, §9.2) + `RG.gap_wire_errors` (B-22 role the gap compiler accepts); `_apply_theta` makes hypotheses/transitions durable in the SAME unit; accepted receipt cites `sorted(_cited(payload))` | shared/polymath_shared/adapter/service.py:446-473 [DERIVED] | payload -> outputs (payload + ledger ids) | 422 gap errors; 422 `"hypotheses: "` errors from `HypothesisRejected` (service.py:460-465) |
| 25 | Loop / finish: submit returns the status view and the run is `"running"` again for the worker; GET /adapter/{run_id}/result (`adapter_result`) is the result entry — its body is past this source excerpt, no behaviour claimed | shared/polymath_shared/adapter/service.py:135, 382-383, 445, 473; orchestrator/orchestrator/api/adapter.py:209 [DERIVED] | — | — |

## state written

- Run row: `store.insert_run(conn, state, m, idempotency_key=..., agent_identity=opts.get("agent_identity"))` — shared/polymath_shared/adapter/service.py:136-137 [DERIVED]
- Run owner: `store.set_run_owner(conn, run_id, owner_principal_id)` (migration 0066 RUN OWNERSHIP) — shared/polymath_shared/adapter/service.py:138-139; orchestrator/orchestrator/api/adapter.py:48-50 [DERIVED]
- Start receipt stored in run request options: `opts["start_receipt"] = receipt` — shared/polymath_shared/adapter/service.py:178 [DERIVED]
- Step rows: `store.finish_step(..., status="issued"|"accepted", receipt=...)` on every submit outcome — shared/polymath_shared/adapter/service.py:411, 421, 430, 443, 452, 463, 471 [DERIVED]
- Run state: `store.save_state` (outputs, `branch_loops`) and `_touch(conn, run_id)` — shared/polymath_shared/adapter/service.py:422, 444, 472; 412, 431, 454, 464 [DERIVED]
- Harness receipts: `store.record_receipt(conn, step["harness_action"]["action_id"], rec, rhash)` — shared/polymath_shared/adapter/service.py:434 [DERIVED]
- θ ledger: hypotheses and transitions become durable state in the same unit — shared/polymath_shared/adapter/service.py:455-459 [DERIVED]
- File (read-only on this path): principals registry at `POLYMATH_MCP_PRINCIPALS_FILE`, owner-only (`chmod 600`) — orchestrator/orchestrator/web_accounts.py:101-103; orchestrator/orchestrator/web_scope.py:58-59 [DERIVED]
- No Qdrant collection appears anywhere on this path [DERIVED: no such call in SOURCE]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| entry `config.seed_check` | None (absent) | start-time domain check of the seed; absent -> no check | shared/polymath_shared/adapter/service.py:132, 154-160 [DERIVED] |
| entry `config.corpus_scope` | None | named corpora validated now; none named -> caller's share of all libraries via `corpus_view` | shared/polymath_shared/adapter/service.py:132, 161-166; orchestrator/orchestrator/api/adapter.py:104-105 [DERIVED] |
| entry `config.corpus_seed` | None | no seed -> one derived from the corpora (`<field>_origin: corpus`) | shared/polymath_shared/adapter/service.py:133, 167-177 [DERIVED] |
| seed `field` | `"seed"` | which input key holds the seed | shared/polymath_shared/adapter/service.py:155 [DERIVED] |
| `request_options.idempotency_key` | absent | present -> replay of the existing run; absent -> run_id from `uuid.uuid4()` | shared/polymath_shared/adapter/service.py:120-128 [DERIVED] |
| named `corpus_ids` (input + request_options) | none named | allowed through; scope narrowed to the grant (wildcard joins libraries added later) | orchestrator/orchestrator/web_scope.py:169-181, 113-119; shared/polymath_shared/query_scope.py:96-103 [DERIVED] |
| manifest `config.show` | absent | no `materials` sibling key at all | shared/polymath_shared/adapter/service.py:312, 315-316 [DERIVED] |
| manifest `config.beside` | absent | no beside keys | shared/polymath_shared/adapter/service.py:267, 270-271 [DERIVED] |
| `request_options.agent_identity` | absent | recorded on the run row | shared/polymath_shared/adapter/service.py:137 [DERIVED] |
| `POLYMATH_MCP_PRINCIPALS_FILE` | unset -> `registry_path()` None | any non-None principal then fails `PRINCIPAL_UNKNOWN`; no principal reads as trusted-local | orchestrator/orchestrator/web_accounts.py:101-103; orchestrator/orchestrator/web_scope.py:47-49, 79-81 [DERIVED] |

## failure modes

1. Start refused 422 with `{error_code, message, hint}` -> seed judged non-generative, a domain gap, or nothing to derive from -> shared/polymath_shared/adapter/service.py:192-198, 173-174 [DERIVED]
2. 403 at start before any run exists -> adapter not in grant, corpus outside grant, or inactive/unknown principal -> orchestrator/orchestrator/web_scope.py:177, 105, 81 [DERIVED]
3. 404 "unknown adapter ..." -> `manifest_for` KeyError -> shared/polymath_shared/adapter/service.py:67-71; orchestrator/orchestrator/api/adapter.py:108-109 [DERIVED]
4. 404 "unknown adapter run ..." on next/submit -> `store.load_run` empty -> orchestrator/orchestrator/api/adapter.py:122-123, 143-144; shared/polymath_shared/adapter/service.py:385-386 [DERIVED]
5. 403 "no such run for this principal" -> owner mismatch; NULL owner never public -> orchestrator/orchestrator/api/adapter.py:53-54; shared/polymath_shared/adapter/service.py:97-99 [DERIVED]
6. 422 `MANIFEST_VERSION_UNAVAILABLE` -> redeploy renamed/removed the awaited step; run parked until deploy rollback or cancel -> shared/polymath_shared/adapter/service.py:403-405 [DERIVED]
7. 422 law errors at submit (not 1024 s later) -> F2 law runs on the submitted payload; counts one repair loop -> shared/polymath_shared/adapter/service.py:415-423 [DERIVED]
8. 422 "no step has been issued" -> no current step row -> shared/polymath_shared/adapter/service.py:390-391 [DERIVED]
9. 422 harness receipt too large -> `_receipt_too_large`; step stays issued for a smaller receipt -> shared/polymath_shared/adapter/service.py:427-432 [DERIVED]
10. 422 gap / hypotheses errors -> unowned gap (§9.2), bad gap wire role (B-22), or `HypothesisRejected` -> shared/polymath_shared/adapter/service.py:448-454, 460-465 [DERIVED]
11. Silent fallback: seed-check crash -> start proceeds, `{"ran": False, "error": ...[:500]}` recorded -> shared/polymath_shared/adapter/service.py:190-191 [DERIVED]
12. Silent fallback: evidence hydration failure -> `{"rows": [], "receipts": [], "error": ...}` beside the step -> shared/polymath_shared/adapter/service.py:373-379 [DERIVED]
13. Silent fallback: materials/beside failure -> `error` / `beside_error` dicts; step still returned -> shared/polymath_shared/adapter/service.py:335-336, 293-295 [DERIVED]
14. Replay instead of new run -> idempotency key hit returns the existing run's receipt -> shared/polymath_shared/adapter/service.py:124-126 [DERIVED]
15. Rejection receipt survives -> B-48: the refusal is receipted on the step row and the transaction commits it before the 422 -> orchestrator/orchestrator/api/adapter.py:136-140 [DERIVED]

## invariants

- INVARIANT naming no corpus never means a server default outside the caller's grant — orchestrator/orchestrator/web_scope.py:170-173 [DERIVED]
- INVARIANT an idempotency key is per owner: `f"{key}@{owner_principal_id}"`, never another principal's run — shared/polymath_shared/adapter/service.py:121-122 [DERIVED]
- INVARIANT the requester's input is validated before anything is derived — shared/polymath_shared/adapter/service.py:119, 129 [DERIVED]
- INVARIANT `{field}_origin` is set only by the runtime; a requester-supplied one is popped — shared/polymath_shared/adapter/service.py:157, 176 [DERIVED]
- INVARIANT a principal reaches only its own runs; a NULL owner is legacy state, never "public" — shared/polymath_shared/adapter/service.py:93-99 [DERIVED]
- INVARIANT evidence / materials / beside travel as SIBLING keys; the AdapterStepV1 contract and its ids stay the citation contract — shared/polymath_shared/adapter/service.py:234-235, 303-305, 518-519 [DERIVED]
- INVARIANT materials are context for reasoning, never citable evidence — shared/polymath_shared/adapter/service.py:334 [DERIVED]
- INVARIANT a broken readable view never takes adapter_next down; the failure is SAID, not hidden — shared/polymath_shared/adapter/service.py:373-379, 335-336, 293-295 [DERIVED]
- INVARIANT a rejected submission leaves the step `"issued"` so the agent may retry — shared/polymath_shared/adapter/service.py:409, 411, 421, 430, 452, 463 [DERIVED]
- INVARIANT a read wildcard reaches every non-private library; a write grant is explicit — the wildcard never opens a library for writing — shared/polymath_shared/query_scope.py:96-103; orchestrator/orchestrator/web_scope.py:98-99 [DERIVED]
- INVARIANT an unreadable principal expiry is an expired one (fail closed) — orchestrator/orchestrator/mcp_principals.py:233-235 [DERIVED]
- INVARIANT the status view reports the versions the RUN started under, not the current manifest — shared/polymath_shared/adapter/service.py:229 [DERIVED]

## VERIFY

```verify
grep -Fq 'def adapter_start' orchestrator/orchestrator/api/adapter.py
grep -Fq 'SEED_NOT_GENERATIVE' shared/polymath_shared/adapter/service.py
grep -Fq 'MANIFEST_VERSION_UNAVAILABLE' shared/polymath_shared/adapter/service.py
grep -Fq 'CORPUS_NOT_ALLOWED' orchestrator/orchestrator/web_scope.py
grep -Eq 'awaiting_(agent|harness)' shared/polymath_shared/adapter/service.py
grep -Fq 'no such run for this principal' orchestrator/orchestrator/api/adapter.py
grep -Fq 'start_receipt' shared/polymath_shared/adapter/service.py
test "$(grep -c -F 'store.finish_step' shared/polymath_shared/adapter/service.py)" -ge 6
```
