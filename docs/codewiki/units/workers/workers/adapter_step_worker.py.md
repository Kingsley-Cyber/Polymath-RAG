# unit: workers/workers/adapter_step_worker.py
anchor: workers/workers/adapter_step_worker.py:1-967

## purpose
Durable executor of automatic adapter steps (COGNITIVE-ADAPTER-V1, ADR-0018, plan E2). Loop: lease ONE running adapter run (`FOR UPDATE SKIP LOCKED`, lease renewed per step) → drive it with `polymath_shared.adapter.service.advance` until it awaits the connected agent, reaches COMPILE_RESULT, hits a typed gap, or spends the step budget → release the lease. workers/workers/adapter_step_worker.py:1-6 [DERIVED]
Knowledge steps reach Polymath only via the orchestrator HTTP API (`POLYMATH_ORCH_URL`); workers never import orchestrator code; outbound paths are allow-listed by `polymath_shared.adapter.evidence_boundary`; this worker never reaches a Polymath synthesis route. workers/workers/adapter_step_worker.py:8-12 [DERIVED]
HARNESS_ACTION steps are never executed here (the host harness answers them through `adapter_submit`). workers/workers/adapter_step_worker.py:14-15 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| process_one | def | (owner, lease_s, max_steps, crash_after) -> run_id \| None | workers/workers/adapter_step_worker.py:845-906 | — |
| sweep_idle | def | (last) -> never raises | workers/workers/adapter_step_worker.py:909-923 | — |
| main | def | (argv) -> exit | workers/workers/adapter_step_worker.py:926-962 | `python -m workers.adapter_step_worker` (workers/workers/adapter_step_worker.py:17) |
| lease_seconds | def | (lease_s) -> seconds | workers/workers/adapter_step_worker.py:835-842 | — |
| trail | def | () -> TC.TrailMCPClient | workers/workers/adapter_step_worker.py:521-525 | — |
| exec_retrieve | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:261-269 | — |
| exec_evidence | def | (step, state, m, corpus_ids, *, legacy, union_legacy=False) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:303-400 | — |
| exec_compile_plan | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:403-413 | — |
| exec_graph_expand | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:426-433 | — |
| exec_validate | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:448-479 | — |
| exec_branch | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:482-483 | — |
| exec_external | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:612-735 | — |
| exec_domain | def | (step, state, m) -> service.ExecOutcome | workers/workers/adapter_step_worker.py:748-759 | — |
| exec_prefetch | def | (unit, lookups, cfg) -> ... | workers/workers/adapter_step_worker.py:781-812 | — |
| OrchUnavailable | class | RuntimeError | workers/workers/adapter_step_worker.py:162-163 | — |
| OrchRejected | class | RuntimeError | workers/workers/adapter_step_worker.py:166-167 | — |
| ScopeNotConfirmed | class | OrchRejected | workers/workers/adapter_step_worker.py:170-173 | — |
| TrailStoreMissing | class | RuntimeError | workers/workers/adapter_step_worker.py:492-493 | — |

No FACTS.importers given; callers unknown.

## contracts

**_orch_post(path, body, *, user_agent=None) -> dict** workers/workers/adapter_step_worker.py:188-221
- pre: `path` must pass `EB.assert_allowed_path(path)` — only evidence-boundary allow-list paths. workers/workers/adapter_step_worker.py:192 [DERIVED]
- pre: `_renew_lease()` before every attempt; lost lease raises `service.LeaseLost`. workers/workers/adapter_step_worker.py:195, 70-71 [DERIVED]
- in: POST `{ORCH}{path}` via `httpx.Client(timeout=HTTP_TIMEOUT_S)`. workers/workers/adapter_step_worker.py:197-198 [DERIVED]
- retry: transient transport errors (`httpx.NetworkError`, `RemoteProtocolError`, `ConnectTimeout`, `PoolTimeout`) and status `502`/`504` retried after `TRANSIENT_BACKOFF_S = (2.0, 8.0, 30.0)`. workers/workers/adapter_step_worker.py:200-212, 184-185 [DERIVED]
- out/error: `>= 500` → `OrchUnavailable`; `>= 400` → `OrchRejected` (never a fallback); `EB.scope_violation(body, out)` → `ScopeNotConfirmed` (fail closed, K1b). workers/workers/adapter_step_worker.py:213-220, 166-173 [DERIVED]

**exec_evidence(...)** workers/workers/adapter_step_worker.py:303-400
- in: needs from `EB.original_needs(cfg, state.input, state.options, hypotheses, compiled_need=step.get("_compiled_need"))`; calls planned by `EB.plan_calls` bounded by `max_calls`/row budget. workers/workers/adapter_step_worker.py:320-323 [DERIVED]
- parallel: width = `max(1, min(cfg.get("parallel_calls", EB.DEFAULT_PARALLEL_CALLS), len(plan["calls"]) or 1))` via ThreadPoolExecutor. workers/workers/adapter_step_worker.py:351-356 [DERIVED]
- post: packet failing contract → terminal gap `EB.GAP_CONTRACT_MISMATCH`, never fallback. workers/workers/adapter_step_worker.py:357-359, 307-308 [DERIVED]
- post: all calls failed and `fallback == EB.SURFACE_LEGACY` → legacy lane output marked `degraded` + `fallback`; else `EB.unavailable_outcome(on_unavailable or "gap")`. workers/workers/adapter_step_worker.py:363-372 [DERIVED]
- post: empty evidence is SUCCESS (`"retrieval_completed": not failures`). workers/workers/adapter_step_worker.py:379, 311-312 [DERIVED]
- cache: key = `EB.cache_key(need, corpus_id, mode, explorer, generation)`; hit marked `"cache": "hit"`; per-run bucket bounded to `EVIDENCE_CACHE_ENTRIES`. workers/workers/adapter_step_worker.py:329-348 [DERIVED]

**exec_validate(step, state, m)** workers/workers/adapter_step_worker.py:448-479
- pre: `require_corpus` and no `_corpus_ids(state)` → gap `INPUT_SCOPE_MISSING`. workers/workers/adapter_step_worker.py:453-457 [DERIVED]
- in: `require` paths checked with `_present` over every accepted output (`a.b`, `list[].field` = every element non-empty). workers/workers/adapter_step_worker.py:436-445, 458-462 [DERIVED]
- post: missing → gap `VALIDATION_FAILED`; `phi == "deduplicate"` merges identical normalised statements into the earliest hypothesis (`MERGE`, `DUPLICATE_STATEMENT`). workers/workers/adapter_step_worker.py:463-478 [DERIVED]

**_need(step, state, m) -> (need, source)** workers/workers/adapter_step_worker.py:85-106
- order: `query_from == "hypotheses"` (statements joined `"; "`, `[:2000]`, source `"context.hypotheses"`) → `config.source` path → `EB.NEED_FIELDS` in `state.input`. workers/workers/adapter_step_worker.py:91-104 [DERIVED]
- error: nothing usable raises `ValueError("NEED_MISSING: ...")`; a limit (category/language/geography) is never searched in the seed's place. workers/workers/adapter_step_worker.py:105-106, 88-90 [DERIVED]

**trail() / _embedded_trail()** workers/workers/adapter_step_worker.py:496-525
- pre (embedded): `POLYMATH_TRAIL_STORE` set, else `TrailStoreMissing` (bug hunt B-66); `:memory:` only when asked explicitly. workers/workers/adapter_step_worker.py:502-505 [DERIVED]
- embedded client: `TrailMCPClient("http://trail.embedded/mcp", "in-process", transport=mod.transport(mod.build_service(store=SqliteResearchStore(store_path))))` loaded from `governance/trail/embedded.py` by file path. workers/workers/adapter_step_worker.py:507-514 [DERIVED]
- rebuild: when token expires within `TOKEN_REFRESH_S = 300` (token lifetime 1 h, bug hunt B-67). workers/workers/adapter_step_worker.py:517-524 [DERIVED]

**exec_prefetch(unit, lookups, cfg)** workers/workers/adapter_step_worker.py:781-812 (FACTS doc)
- HOST_PREFETCH: lookups through HOST_TOOLS with the run owner's principal, outside any transaction; bounded by `PREFETCH_MAX_LOOKUPS = 24`. workers/workers/adapter_step_worker.py:772, 781-812 [DERIVED]

## effect surface
| effect | detail | anchor |
|---|---|---|
| network | `httpx.Client` POST to `{ORCH}{path}`, timeout `HTTP_TIMEOUT_S` | workers/workers/adapter_step_worker.py:197-198 |
| network | allow-list enforced by `EB.assert_allowed_path` | workers/workers/adapter_step_worker.py:192 |
| network | embedded Trail endpoint literal `"http://trail.embedded/mcp"`; daemon mode `TC.TrailMCPClient.from_env()` | workers/workers/adapter_step_worker.py:513-514, 524 |
| postgres | `tx()` + `service.store.renew_lease(conn, run_id, owner, lease_s)`; claim uses FOR UPDATE SKIP LOCKED | workers/workers/adapter_step_worker.py:69-71, 3 |
| postgres | FACTS `tables_read`/`tables_written` both `[]` — table names not visible here | FACTS |
| file | sqlite audit store at `POLYMATH_TRAIL_STORE` via `SqliteResearchStore` | workers/workers/adapter_step_worker.py:502, 513 |
| file | loads `governance/trail/embedded.py` by path as module `polymath_governance_trail_embedded` | workers/workers/adapter_step_worker.py:507-509 |
| subprocess | `import subprocess` unused here; domain runner (`polymath_shared.adapter.domain`) spawns through it, tests patch it | workers/workers/adapter_step_worker.py:28 |
| collections | `polymath_transition` (FACTS, exec_external region); `polymath_governance_trail_embedded` (module name, FACTS) | workers/workers/adapter_step_worker.py:705, 708, 508 |

env flags (name = default):
| flag | default | anchor |
|---|---|---|
| POLYMATH_ORCH_URL | `'http://127.0.0.1:7200'` | workers/workers/adapter_step_worker.py:44 |
| POLYMATH_ADAPTER_HTTP_TIMEOUT_S | `'180'` | workers/workers/adapter_step_worker.py:48 |
| POLYMATH_ADAPTER_LEASE_S | `'300'` | workers/workers/adapter_step_worker.py:49 |
| POLYMATH_ADAPTER_IDLE_SWEEP_S | `'60'` | workers/workers/adapter_step_worker.py:52 |
| POLYMATH_TRAIL_MODE | `'daemon'` | workers/workers/adapter_step_worker.py:524 |
| POLYMATH_TRAIL_STORE | `null` (unset refused in embedded mode) | workers/workers/adapter_step_worker.py:502 |
| POLYMATH_TRAIL_PRINCIPAL | `'polymath'` | FACTS workers/workers/adapter_step_worker.py:632 |

## invariants
INVARIANT: HTTP_TIMEOUT_S (default 180) > 149 s worst observed call (74 s evidence + 75 s provider breaker wait) — workers/workers/adapter_step_worker.py:45-48 [DERIVED]
  fails-if: evidence calls time out and the surface flaps to OrchUnavailable.
INVARIANT: LEASE_MARGIN_S (60) >= max(TRANSIENT_BACKOFF_S) (30.0) + a renewal round trip — workers/workers/adapter_step_worker.py:50, 184 [DERIVED]
  fails-if: lease expires mid-backoff; a second worker claims the run mid-step.
INVARIANT: TRANSIENT_STATUS == frozenset({502, 504}); 500 and 503 are NOT retried — workers/workers/adapter_step_worker.py:183-185 [DERIVED]
  fails-if: a server-declared 503 would be pointlessly retried before `on_unavailable` runs.
INVARIANT: retry attempts <= len(TRANSIENT_BACKOFF_S) == 3 — workers/workers/adapter_step_worker.py:200, 207 [DERIVED]
  fails-if: unbounded retry loops on a bouncing peer.
INVARIANT: EVIDENCE_CACHE_RUNS == 32 runs and EVIDENCE_CACHE_ENTRIES == 64 entries per run — workers/workers/adapter_step_worker.py:275-276, 284-285, 347-348 [DERIVED]
  fails-if: unbounded process memory growth across runs.
INVARIANT: TOKEN_REFRESH_S (300) < token lifetime (1 h) — workers/workers/adapter_step_worker.py:517-518 [DERIVED]
  fails-if: expired daemon token used; Trail calls rejected.
INVARIANT: hit rows carry `corpus_id` only when `len(corpus_ids) == 1`, else `None` — workers/workers/adapter_step_worker.py:143 [DERIVED]
  fails-if: multi-corpus rows silently lose corpus attribution.
INVARIANT: WORKER_TYPE `"adapter_step"` == the supervisor slot name — workers/workers/adapter_step_worker.py:54 [DERIVED]
  fails-if: supervisor cannot match/register this worker.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` workers/workers/adapter_step_worker.py:911; network `httpx.Client` workers/workers/adapter_step_worker.py:197; env-driven config workers/workers/adapter_step_worker.py:44-52; concurrency ThreadPoolExecutor workers/workers/adapter_step_worker.py:353-354 and `threading.Lock` `_CACHE_LOCK` workers/workers/adapter_step_worker.py:277)
idempotency: SAFE — a crash mid-step leaves the lease to expire; the next claim re-executes the ISSUED step idempotently (every step is a single committed unit) workers/workers/adapter_step_worker.py:5-6 [DERIVED]; the evidence cache is rebuilt from the run's own stored outputs after a restart workers/workers/adapter_step_worker.py:272-274, 289-300 [DERIVED]

## failure behaviour
| handler | behaviour | anchor |
|---|---|---|
| sweep_idle `Exception` | SWALLOWED: log, return `[]` — never raises | workers/workers/adapter_step_worker.py:909-923 (FACTS fallback line 921) |
| main loop `Exception` | handled: log, continue | FACTS workers/workers/adapter_step_worker.py:949 |
| process_one `Exception` | handled: log, return run_id | FACTS workers/workers/adapter_step_worker.py:885 |
| exec_prefetch `Exception` | handled: assign (per-lookup) | FACTS workers/workers/adapter_step_worker.py:795 |
| lost lease | `service.LeaseLost` raised; the unit is dropped, never applied | workers/workers/adapter_step_worker.py:70-71, 64-65 |

Error/gap codes raised: `OrchUnavailable` (162-163), `OrchRejected` — "a caller defect... never a fallback" (166-167), `ScopeNotConfirmed` — step fails STEP_EXECUTOR_ERROR rather than reason over unscoped evidence (170-173), `TrailStoreMissing` (492-493), `ValueError("NEED_MISSING: ...")` (105-106), gaps `INPUT_SCOPE_MISSING` (265, 406, 429, 456-457), `VALIDATION_FAILED` (463-464), `EB.GAP_CONTRACT_MISMATCH` (358-359).

## dumb-code flags
- `"EXPLORE"` default literal duplicated in `_legacy_mode` (`legacy_mode` and `mode` branches) — workers/workers/adapter_step_worker.py:227 [DERIVED]
- `subprocess` imported and unused here (`# noqa: F401`), kept only so tests can patch it — workers/workers/adapter_step_worker.py:28 [DERIVED]
- `corpus_ids[0] if len(corpus_ids) == 1 else None` silently nulls `corpus_id` for multi-corpus calls — workers/workers/adapter_step_worker.py:143 [DERIVED]
- hardcoded `limit: 24` in the `/retrieve/plan` body — workers/workers/adapter_step_worker.py:408 [DERIVED]
- default `top_k` fallback `16` inside `_retrieve_legacy` — workers/workers/adapter_step_worker.py:241 [DERIVED]
- trim limits scattered: need `[:2000]`, row text `max_text=700` — workers/workers/adapter_step_worker.py:95, 154 [DERIVED]
- FACTS `collections` lists `polymath_transition` three times (lines 705, 705, 708) — duplicated references in the unseen exec_external region — FACTS [DERIVED]
- same number, two meanings: `LEASE_S_DEFAULT` 300 (s) and `TOKEN_REFRESH_S` 300 (s) — workers/workers/adapter_step_worker.py:49, 518 [INFERRED: coincidence, easy to conflate when tuning]

## refactor notes
- Any new orchestrator path must be added to the `polymath_shared.adapter.evidence_boundary` allow-list first; `_orch_post` hard-fails otherwise — workers/workers/adapter_step_worker.py:192, 9-12 [DERIVED]
- `service.ExecOutcome` dict shape (`{"output", "evidence_refs"}` or `{"gap"}`) is the contract consumed by `service.advance`; changing it breaks every executor — workers/workers/adapter_step_worker.py:249-251, 359, 479 [DERIVED]
- `state.output_order` reliance: JSONB drops dict order, so `_cached_from_outputs` and `_newest_output_with` select by acceptance order — workers/workers/adapter_step_worker.py:291, 529-531 [DERIVED]
- `WORKER_TYPE` string must keep matching the supervisor slot name — workers/workers/adapter_step_worker.py:54 [DERIVED]
- Keep the `subprocess` import: the domain runner and tests patch it in this module — workers/workers/adapter_step_worker.py:28 [DERIVED]
- Embedded Trail couples to `governance/trail/embedded.py` by relative path and module name `polymath_governance_trail_embedded`; moving that file breaks `_embedded_trail` — workers/workers/adapter_step_worker.py:507-511 [DERIVED]
- Cross-module EB constants in play: `EB.NEED_FIELDS`, `EB.SURFACE_BOUNDARY`, `EB.SURFACE_LEGACY`, `EB.EVIDENCE_PATH`, `EB.TRAIL_SCOPE`, `EB.DEFAULT_MAX_ROWS`, `EB.DEFAULT_MAX_CALLS`, `EB.DEFAULT_PARALLEL_CALLS`, `EB.PACKET_SCHEMA_VERSION` — workers/workers/adapter_step_worker.py:101, 227, 242, 305, 321-324, 335, 377-378 [DERIVED]

## VERIFY
```verify
grep -Fq 'TRANSIENT_BACKOFF_S = (2.0, 8.0, 30.0)' workers/workers/adapter_step_worker.py
grep -Fq 'WORKER_TYPE = "adapter_step"' workers/workers/adapter_step_worker.py
grep -Fq 'EVIDENCE_CACHE_ENTRIES = 64' workers/workers/adapter_step_worker.py
grep -Fq 'TOKEN_REFRESH_S = 300' workers/workers/adapter_step_worker.py
test "$(grep -c -F 'OrchUnavailable' workers/workers/adapter_step_worker.py)" -ge 5
! grep -Fq 'import requests' workers/workers/adapter_step_worker.py
```
