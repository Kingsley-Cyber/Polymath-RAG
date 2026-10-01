# unit: workers/workers/adapter_step_worker.py
anchor: workers/workers/adapter_step_worker.py:1-795

## purpose
Durable executor of automatic adapter steps (COGNITIVE-ADAPTER-V1, ADR-0018, plan E2): leases ONE running adapter run (`FOR UPDATE SKIP LOCKED`, lease renewed per step) and drives it with `polymath_shared.adapter.service.advance` until it awaits the connected agent, reaches COMPILE_RESULT, hits a typed gap, or spends the per-claim step budget; a crash mid-step leaves the lease to expire and the next claim re-executes the ISSUED step idempotently — workers/workers/adapter_step_worker.py:1-6 [DERIVED]. Knowledge steps reach Polymath only through the orchestrator HTTP seam (`POLYMATH_ORCH_URL`), never by importing orchestrator code; the outbound surface is an allow-list owned by `polymath_shared.adapter.evidence_boundary`; this worker never reaches a synthesis route — workers/workers/adapter_step_worker.py:8-12 [DERIVED]. EXTERNAL_OPERATION steps call TrailSignal's bounded synchronous operations; HARNESS_ACTION steps are never executed here — workers/workers/adapter_step_worker.py:13-15 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| WORKER_TYPE | const | `"adapter_step"` (== supervisor slot name) | workers/workers/adapter_step_worker.py:47 | — |
| OrchUnavailable | class | RuntimeError | workers/workers/adapter_step_worker.py:132-133 | — |
| OrchRejected | class | RuntimeError | workers/workers/adapter_step_worker.py:136-137 | — |
| ScopeNotConfirmed | class | OrchRejected | workers/workers/adapter_step_worker.py:140-143 | — |
| exec_retrieve | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:221-229 | — |
| exec_evidence | def | (step, state, m, corpus_ids, *, legacy, union_legacy=False) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:232-296 | — |
| exec_compile_plan | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:299-307 | — |
| exec_graph_expand | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:320-327 | — |
| exec_validate | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:342-371 | — |
| exec_branch | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:374-375 | — |
| TrailStoreMissing | class | RuntimeError | workers/workers/adapter_step_worker.py:384-385 | — |
| trail | def | () -> TC.TrailMCPClient | workers/workers/adapter_step_worker.py:413-417 | — |
| exec_external | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:504-626 | — |
| exec_domain | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:643-690 | — |
| process_one | def | (owner, lease_s, max_steps, crash_after) -> run_id or None | workers/workers/adapter_step_worker.py:712-753 | — |
| main | def | (argv) -> exit | workers/workers/adapter_step_worker.py:756-790 | — |

## contracts

**_orch_post(path, body, *, user_agent) -> dict** — workers/workers/adapter_step_worker.py:158-190
- pre: path must pass `EB.assert_allowed_path(path)` — workers/workers/adapter_step_worker.py:162 [DERIVED]
- in: POST `{ORCH}{path}` via `httpx.Client(timeout=HTTP_TIMEOUT_S)` — workers/workers/adapter_step_worker.py:166-167 [DERIVED]
- transient (NetworkError/RemoteProtocolError/ConnectTimeout/PoolTimeout, or status in {502, 504}) retried after pauses `(2.0, 8.0, 30.0)` — workers/workers/adapter_step_worker.py:154-155, 169-180 [DERIVED]
- post: status ≥500 → `OrchUnavailable`; ≥400 → `OrchRejected` — workers/workers/adapter_step_worker.py:182-185 [DERIVED]
- post: `EB.scope_violation(body, out)` non-empty → `ScopeNotConfirmed` (fail closed, K1b) — workers/workers/adapter_step_worker.py:187-189 [DERIVED]

**exec_retrieve(step, state, m)** — workers/workers/adapter_step_worker.py:221-229
- pre: `_corpus_ids(state)` non-empty else gap `INPUT_SCOPE_MISSING` — workers/workers/adapter_step_worker.py:223-225 [DERIVED]
- dispatch: `EB.resolve_surface(cfg, os.environ)` == `EB.SURFACE_BOUNDARY` → `exec_evidence(..., legacy=_retrieve_legacy)`; else legacy lane, degraded if forced — workers/workers/adapter_step_worker.py:226-229 [DERIVED]

**exec_evidence(step, state, m, corpus_ids, *, legacy, union_legacy=False)** — workers/workers/adapter_step_worker.py:232-296
- in: needs = `EB.original_needs(...)` incl. `_compiled_need`; plan = `EB.plan_calls(needs, corpus_ids, max_calls=cfg.max_calls or EB.DEFAULT_MAX_CALLS)` — workers/workers/adapter_step_worker.py:246-247 [DERIVED]
- per call: POST `EB.EVIDENCE_PATH`; `EB.check_response` errors → terminal gap `EB.GAP_CONTRACT_MISMATCH`, never a fallback — workers/workers/adapter_step_worker.py:254-261 [DERIVED]
- all calls failed: `cfg.get("fallback") == EB.SURFACE_LEGACY` → legacy lane marked `degraded` with reason `evidence_boundary_unavailable`; legacy also unreachable → `EB.unavailable_outcome(on_unavailable or "gap")` — workers/workers/adapter_step_worker.py:265-274 [DERIVED]
- post: rows merged via `EB.merge_rows(..., max_rows=cfg.max_rows or EB.DEFAULT_MAX_ROWS)`; empty evidence is SUCCESS (`retrieval_completed: true`) — workers/workers/adapter_step_worker.py:275-278 [DERIVED]
- `union_legacy=True` (graph steps): legacy graph rows unioned, refs deduped by id; legacy `OrchUnavailable` → `graph_rows=[]`, `graph_failure`, reason `graph_facts_unavailable` — workers/workers/adapter_step_worker.py:286-295 [DERIVED]

**exec_validate(step, state, m)** — workers/workers/adapter_step_worker.py:342-371
- pre: `cfg.require_corpus` and no corpus_ids → gap `INPUT_SCOPE_MISSING` — workers/workers/adapter_step_worker.py:347-350 [DERIVED]
- in: `require` paths (`a.b`, `list[].field`) checked with `_present` over accepted outputs — workers/workers/adapter_step_worker.py:330-339, 352-355 [DERIVED]
- post: missing → gap `VALIDATION_FAILED`; `phi == "deduplicate"` emits MERGE verdicts into `ids[0]`, reason `DUPLICATE_STATEMENT` — workers/workers/adapter_step_worker.py:356-370 [DERIVED]

**exec_external(step, state, m)** — workers/workers/adapter_step_worker.py:504-626
- pre: `availability == "planned"` → gap `TRAIL_CAPABILITY_PLANNED`; kind not in `TC.BOUNDED_OPERATIONS` → `TRAIL_OPERATION_UNSUPPORTED` — workers/workers/adapter_step_worker.py:512-516 [DERIVED]
- pre: `TrailStoreMissing` → `TRAIL_STORE_MISSING`; `not client.configured` → `TRAIL_PRINCIPAL_MISSING` — workers/workers/adapter_step_worker.py:518-522 [DERIVED]
- `evidence.admit` request over Trail's ceiling → gap `RECEIPT_TOO_LARGE`; nothing trimmed or sent — workers/workers/adapter_step_worker.py:529-534 [DERIVED]
- `TC.TrailToolError` → gap `TRAIL_REFUSED`; transient transport retried with the SAME request (idempotency key safe), exhausted → `RuntimeError` (typed STEP_EXECUTOR_ERROR, retryable by re-run) — workers/workers/adapter_step_worker.py:541-552 [DERIVED]
- post: response identity checked before relabelling: `operation_kind` mismatch or empty `operation_id` → `TRAIL_RESPONSE_MISMATCH` — workers/workers/adapter_step_worker.py:557-560 [DERIVED]

**trail() -> TC.TrailMCPClient** — workers/workers/adapter_step_worker.py:413-417
- caches `_TRAIL`; rebuilds when `TC.token_expires_within(_TRAIL.token, 300)` — workers/workers/adapter_step_worker.py:410, 413-417 [DERIVED]
- embedded mode (`POLYMATH_TRAIL_MODE=embedded`) requires `POLYMATH_TRAIL_STORE` else `TrailStoreMissing`; loads `parents[2]/governance/trail/embedded.py` by file path, client base `"http://trail.embedded/mcp"` — workers/workers/adapter_step_worker.py:394-397, 399-406 [DERIVED]

**exec_domain(step, state, m)** — workers/workers/adapter_step_worker.py:643-690
- DOMAIN_OPERATION = bounded stateless computation by domain code running OUT OF PROCESS via `subprocess.run` — workers/workers/adapter_step_worker.py:664 [DERIVED]
- request version `"domain_operation_request.v1"`, timeout `POLYMATH_DOMAIN_OPERATION_TIMEOUT_S` default `120`, output cap `DOMAIN_OUTPUT_MAX_BYTES = 1000000` — workers/workers/adapter_step_worker.py:633-635 [DERIVED]

**process_one(owner, lease_s, max_steps, crash_after)** — workers/workers/adapter_step_worker.py:712-753
- claim + drive one run; returns run_id worked on, `None` = nothing claimable; a step unit that raises is rolled back — workers/workers/adapter_step_worker.py:712 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| env | `POLYMATH_ORCH_URL = 'http://127.0.0.1:7200'` | workers/workers/adapter_step_worker.py:44 |
| env | `POLYMATH_ADAPTER_HTTP_TIMEOUT_S = '120'` | workers/workers/adapter_step_worker.py:45 |
| env | `POLYMATH_TRAIL_MODE = 'daemon'` (embedded \| daemon) | workers/workers/adapter_step_worker.py:416 |
| env | `POLYMATH_TRAIL_STORE` (no default; file path, required in embedded mode) | workers/workers/adapter_step_worker.py:394 |
| env | `POLYMATH_TRAIL_PRINCIPAL = 'polymath'` | workers/workers/adapter_step_worker.py:524 |
| env | `POLYMATH_DOMAIN_OPERATION_TIMEOUT_S = '120'` | workers/workers/adapter_step_worker.py:634 |
| env | `POLYMATH_ADAPTER_LEASE_S = '120'` | workers/workers/adapter_step_worker.py:760 |
| env (subprocess) | `PATH = ''`, `LANG = 'en_US.UTF-8'` | workers/workers/adapter_step_worker.py:662 |
| network | httpx POST `{ORCH}/retrieve` | workers/workers/adapter_step_worker.py:215, 312 |
| network | httpx POST `{ORCH}/retrieve/plan` | workers/workers/adapter_step_worker.py:303 |
| network | httpx POST `{ORCH}/{EB.EVIDENCE_PATH}` | workers/workers/adapter_step_worker.py:254 |
| network | Trail MCP client: `TC.TrailMCPClient.from_env()` (daemon) or in-process transport | workers/workers/adapter_step_worker.py:406, 416 |
| subprocess | `subprocess.run` (domain module, out of process) | workers/workers/adapter_step_worker.py:664 |
| file | embedded Trail core loaded from `governance/trail/embedded.py` by path; audit store at `POLYMATH_TRAIL_STORE` | workers/workers/adapter_step_worker.py:390-399 |
| postgres | no direct table reads/writes in this file (static analysis empty); DB via `polymath_shared.db.tx`; lease claim uses `FOR UPDATE SKIP LOCKED` | workers/workers/adapter_step_worker.py:3, 40 |

## invariants
INVARIANT: len(TRANSIENT_BACKOFF_S) == 3 == max transient retries (guard `attempt < len(TRANSIENT_BACKOFF_S)`) — workers/workers/adapter_step_worker.py:154, 169, 176 [DERIVED]
  fails-if: unbounded retry loop or IndexError past the tuple.
INVARIANT: TRANSIENT_STATUS == frozenset({502, 504}); 500 and 503 are NOT retried (503 answers via the boundary fallback / `on_unavailable`) — workers/workers/adapter_step_worker.py:152-155, 182 [DERIVED]
  fails-if: treating 503 as transient doubles a server-declared unavailability instead of falling back.
INVARIANT: TOKEN_REFRESH_S == 300 < token lifetime "an hour" — workers/workers/adapter_step_worker.py:409-410, 415 [DERIVED for 300; INFERRED hour from comment]
  fails-if: cached client is rebuilt after expiry; calls fail auth.
INVARIANT: hypotheses query text ≤ 2000 chars (`[:2000]`) — workers/workers/adapter_step_worker.py:67 [DERIVED]
INVARIANT: `_refs_from_rows` emits only kind ∈ {"chunk", "document", "graph_fact", "graph_hop"} — workers/workers/adapter_step_worker.py:93 [DERIVED]
  fails-if: other kinds silently dropped from evidence_refs.
INVARIANT: gap wire caps — `gaps[-100:]`, `open_gaps[:100]`, `physical_jobs[:100]`; `boundary_failures[:6]` — workers/workers/adapter_step_worker.py:474-475, 488, 272, 284 [DERIVED]
INVARIANT: row text truncated to 700 chars default (`text`, `text_clean`, `summary`) — workers/workers/adapter_step_worker.py:124-127 [DERIVED]
INVARIANT: every legacy retrieve/plan/graph call carries `scope: dict(EB.TRAIL_SCOPE)` (K1 reference-material-only) — workers/workers/adapter_step_worker.py:210, 304, 313 [DERIVED]
  fails-if: Trail ideation reads non-reference knowledge roles.
INVARIANT: step-output selection must use acceptance order (`state.output_order`), never dict order — workers/workers/adapter_step_worker.py:423, 430-434 [DERIVED]
  fails-if: JSONB-reordered outputs corrupt `latest`/chronological gap accumulation.
INVARIANT: WORKER_TYPE == "adapter_step" == supervisor slot name — workers/workers/adapter_step_worker.py:47 [DERIVED]
INVARIANT: DOMAIN_OUTPUT_MAX_BYTES == 1000000; ERROR_BACKOFF_S == 10.0 — workers/workers/adapter_step_worker.py:635, 701 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network — httpx.Client workers/workers/adapter_step_worker.py:166; subprocess — workers/workers/adapter_step_worker.py:664; clock — time.sleep backoff workers/workers/adapter_step_worker.py:171, 178, 549; env — ORCH URL/trail mode workers/workers/adapter_step_worker.py:44, 416; db lease via tx workers/workers/adapter_step_worker.py:3, 40)
idempotency: SAFE (every step is a single committed unit; the next claim re-executes the ISSUED step idempotently — workers/workers/adapter_step_worker.py:5-6; Trail retries replay the SAME request whose idempotency key makes it safe — workers/workers/adapter_step_worker.py:544-545) [DERIVED]

## failure behaviour
- `main` loop catches `Exception` (if, log, expr, continue): a failed cycle does not kill the daemon — workers/workers/adapter_step_worker.py:777 [DERIVED]
- `process_one` catches `Exception` (if, log, with, return run_id): the failing run is surfaced, loop continues — workers/workers/adapter_step_worker.py:732 [DERIVED]
- `_transient(exc)`: DB unreachable/busy (connection lost, pool exhausted, lock/deadlock) says nothing about the run — workers/workers/adapter_step_worker.py:704-709 [DERIVED]
- typed gap codes (step ends typed, never invention): `INPUT_SCOPE_MISSING` 225/302/323/350; `VALIDATION_FAILED` 357; `EB.GAP_CONTRACT_MISMATCH` 261; `TRAIL_CAPABILITY_PLANNED` 513; `TRAIL_OPERATION_UNSUPPORTED` 516; `TRAIL_STORE_MISSING` 520; `TRAIL_PRINCIPAL_MISSING` 522; `RECEIPT_TOO_LARGE` 533; `TRAIL_REFUSED` 542; `TRAIL_RESPONSE_MISMATCH` 558/560; exhausted transport → `RuntimeError` typed STEP_EXECUTOR_ERROR, retryable by re-run — workers/workers/adapter_step_worker.py:552 [DERIVED]
- `OrchRejected` (4xx) is a caller defect and never a fallback; `OrchUnavailable` (transport/timeout/5xx) may fall back — workers/workers/adapter_step_worker.py:132-137 [DERIVED]

## dumb-code flags
- Magic literals: `[:2000]` 67; `700` trim 124; `24` plan limit 303; `16` top_k default 209; `20` max_facts 313; `100` gap caps 474-475, 488; `[:6]` failure cap 272, 284 — workers/workers/adapter_step_worker.py:67, 124, 303, 209, 313 [DERIVED]
- `"EXPLORE"` default duplicated in both branches of `_legacy_mode` — workers/workers/adapter_step_worker.py:196 [DERIVED]
- string `"polymath_transition"` appears at 596 (twice) and 599 — workers/workers/adapter_step_worker.py:596, 599 [DERIVED]
- `_rows_from_hits` sets `corpus_id` only when `len(corpus_ids) == 1`, else None — multi-corpus hits lose corpus attribution — workers/workers/adapter_step_worker.py:113 [INFERRED: single-value ternary drops it otherwise]
- fallback config compared against constant `EB.SURFACE_LEGACY` while the docstring spells the value `"retrieve"` — doc/value coupling — workers/workers/adapter_step_worker.py:239, 267 [DERIVED]
- `degraded` marker written as two keys (`degraded`, `degraded_reasons`) appended in place — workers/workers/adapter_step_worker.py:200-202 [DERIVED]

## refactor notes
- `exec_evidence` takes the legacy lane as a callable; `exec_retrieve` passes `_retrieve_legacy`, `exec_graph_expand` passes `_graph_legacy` with `union_legacy=True` — changing either legacy signature breaks both call sites — workers/workers/adapter_step_worker.py:228, 326, 287-295 [DERIVED]
- Trail payloads are CLOSED (`extra="forbid"`, bug hunts B-21/B-26): never forward a raw agent dict; physical jobs reduced to `("hypothesis_id", "job", "mechanism")` — workers/workers/adapter_step_worker.py:473-474, 486-488 [DERIVED]
- output-order discipline: any new selection over `state.outputs` must go through `_ordered_outputs` / `_newest_output_with` (JSONB drops dict order) — workers/workers/adapter_step_worker.py:420-434 [DERIVED]
- the outbound seam is the EB allow-list; this worker must never reach a Polymath synthesis route — workers/workers/adapter_step_worker.py:11-12, 162 [DERIVED]
- K1b stays fail-closed: a scoped call whose response does not confirm scope raises `ScopeNotConfirmed` instead of reasoning over unscoped evidence — workers/workers/adapter_step_worker.py:140-143, 187-189 [DERIVED]
- embedded loader resolves `governance/trail/embedded.py` via `parents[2]` — moving this module or the trail core breaks the loader — workers/workers/adapter_step_worker.py:399 [DERIVED]
- oversized `evidence.admit` receipts are refused, never trimmed (B-05, owner decision 2026-09-26) — workers/workers/adapter_step_worker.py:529-531 [DERIVED]

## VERIFY
```verify
grep -Fq 'WORKER_TYPE = "adapter_step"' workers/workers/adapter_step_worker.py
grep -Fq 'TRANSIENT_BACKOFF_S = (2.0, 8.0, 30.0)' workers/workers/adapter_step_worker.py
grep -Fq 'TRANSIENT_STATUS = frozenset({502, 504})' workers/workers/adapter_step_worker.py
grep -Fq 'TOKEN_REFRESH_S = 300' workers/workers/adapter_step_worker.py
grep -Fq 'raise ScopeNotConfirmed(' workers/workers/adapter_step_worker.py
grep -Fq 'gaps[-100:]' workers/workers/adapter_step_worker.py
test "$(grep -c -F 'TRAIL_RESPONSE_MISMATCH' workers/workers/adapter_step_worker.py)" -ge 2
grep -Fq 'retrieval_completed' workers/workers/adapter_step_worker.py
```
