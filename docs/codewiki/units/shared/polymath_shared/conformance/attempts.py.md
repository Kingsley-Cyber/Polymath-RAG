# unit: shared/polymath_shared/conformance/attempts.py
anchor: shared/polymath_shared/conformance/attempts.py:1-383

## purpose
Records one durable row per LLM provider attempt into Postgres table `llm_provider_attempts`, so failed attempts (e.g. HTTP 429s absorbed by failover) remain visible next to the final batch outcome — the docstring's motivating case is a run at 82% provider rejection with every counter green (shared/polymath_shared/conformance/attempts.py:1-17) [DERIVED]. Writes are fail-soft: accounting must never block an extraction call (shared/polymath_shared/conformance/attempts.py:14-16) [DERIVED]. Readers (`attempt_summary`, `reconcile`) serve the auditor and control plane (shared/polymath_shared/conformance/attempts.py:205) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `enabled` | def | () -> bool | shared/polymath_shared/conformance/attempts.py:42-44 | — |
| `attempt_context` | class | (**fields: Any) context manager -> dict | shared/polymath_shared/conformance/attempts.py:47-91 | module importers (below) |
| `current_context` | def | () -> dict | shared/polymath_shared/conformance/attempts.py:94-95 | — |
| `next_ordinal` | def | () -> int (DEPRECATED) | shared/polymath_shared/conformance/attempts.py:98-113 | — |
| `Attempt` | dataclass | 4 required + 12 optional fields | shared/polymath_shared/conformance/attempts.py:117-135 | `record` |
| `merged_tags` | def | (ctx: dict, *, stage, function) -> dict | shared/polymath_shared/conformance/attempts.py:138-144 | — |
| `fallback_tags` | def | (*, stage, function) context manager | shared/polymath_shared/conformance/attempts.py:148-155 | — |
| `record` | def | (a: Attempt) -> None | shared/polymath_shared/conformance/attempts.py:158-202 | module importers (below) |
| `ledger_available` | def | (conn) -> bool | shared/polymath_shared/conformance/attempts.py:207-212 | — |
| `attempt_summary` | def | (conn, window: str = "24 hours") -> dict | shared/polymath_shared/conformance/attempts.py:215-254 | — |
| `reconcile` | def | (conn, window: str = "24 hours") -> dict | shared/polymath_shared/conformance/attempts.py:257-382 | — |

Module importers (per-symbol mapping unknown): `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/llm_extraction/client.py`, `workers/workers/doc_parent_map_stage_worker.py` [DERIVED].

## contracts

**record(a: Attempt) -> None**
- in: `Attempt(lane, limiter_admitted, http_dispatched, success, limiter_bypassed=False, http_status=None, retry_after_s=None, error_class=None, latency_ms=None, response_hash=None, model=None, provider=None, account_env=None, tokens_in=None, tokens_out=None)` — shared/polymath_shared/conformance/attempts.py:118-135 [DERIVED]
- pre: `enabled()` (env `POLYMATH_ATTEMPT_LEDGER` not in `("0", "false", "no", "off")`) and `POLYMATH_PG_DSN` non-empty; otherwise silent no-op — shared/polymath_shared/conformance/attempts.py:44, 167-171 [DERIVED]
- post: one INSERT into `TABLE` with columns `correlation_id, run_id, ticket_id, function, stage, lane, provider, model, account_env, attempt_ordinal, limiter_admitted, http_dispatched, http_status, retry_after_s, error_class, success, latency_ms, response_hash, tokens_in, tokens_out, limiter_bypassed, started_at`; context keys come from the contextvar, attempt facts from the dataclass — shared/polymath_shared/conformance/attempts.py:177-197 [DERIVED]
- post: `attempt_ordinal` derived in SQL as `(SELECT COALESCE(MAX(attempt_ordinal), 0) + 1 FROM llm_provider_attempts WHERE correlation_id = %s)` — shared/polymath_shared/conformance/attempts.py:183-188 [DERIVED]
- post: `started_at` written as `now() - make_interval(secs => COALESCE(%s,0) / 1000.0)` so the column means start, not finish — shared/polymath_shared/conformance/attempts.py:161-165, 190 [DERIVED]
- never raises — shared/polymath_shared/conformance/attempts.py:159, 198-202 [DERIVED]

**attempt_context(**fields)**
- `__enter__` merges outer context, mints `correlation_id = uuid.uuid4().hex[:24]` only if absent (outermost context), returns merged dict — shared/polymath_shared/conformance/attempts.py:60-74 [DERIVED]
- `__exit__` resets the contextvar token; on `ValueError` restores by value via `_ctx.set(self._prev)` — shared/polymath_shared/conformance/attempts.py:76-91 [DERIVED]

**attempt_summary(conn, window)**
- out: dict with keys `available, window, attempts, logical_calls, limiter_refused, limiter_bypassed, dispatched, http_429, succeeded, attempts_per_success, rejection_rate, failover_attempts, uncorrelated_attempts, per_lane` — shared/polymath_shared/conformance/attempts.py:238-254 [DERIVED]
- error path: `{"available": False, "error": str(exc)[:200]}` — shared/polymath_shared/conformance/attempts.py:230-231 [DERIVED]

**reconcile(conn, window)**
- out: `{"available": True, "summary": s, "batch_outcomes": outcomes, "findings": findings}` — shared/polymath_shared/conformance/attempts.py:382 [DERIVED]
- findings codes emitted: `PROVIDER_PRESSURE` (:268), `FAILOVER_ATTEMPTS` (:272), `HIDDEN_429` (:283-287), `LIMITER_BYPASS` (:302), `DARK_ENABLED_LANE` (:340), `CONFIG/LIVE_MISMATCH` (:381) — shared/polymath_shared/conformance/attempts.py:267-381 [DERIVED]
- reads `document_parent_map_batches` grouped by `COALESCE(last_error,'SUCCESS')` — shared/polymath_shared/conformance/attempts.py:276-279 [DERIVED]

## effect surface
- Postgres written: `llm_provider_attempts` (INSERT per attempt) — shared/polymath_shared/conformance/attempts.py:32, 177 [DERIVED]
- Postgres read: `llm_provider_attempts` (summary, per-lane, bypass-lanes, live-model queries) — shared/polymath_shared/conformance/attempts.py:218-227, 233-237, 295-298, 360-364; `document_parent_map_batches` — shared/polymath_shared/conformance/attempts.py:276-279 [DERIVED]
- Network: `psycopg.connect(dsn, connect_timeout=3, autocommit=True)` opened per `record()` call — shared/polymath_shared/conformance/attempts.py:175 [DERIVED]
- Env: `POLYMATH_PG_DSN = ''`, `POLYMATH_ATTEMPT_LEDGER = '1'` — shared/polymath_shared/conformance/attempts.py:169, 44 [DERIVED]
- Lazy import: `polymath_shared.llm_extraction.lane_registry` inside `reconcile` — shared/polymath_shared/conformance/attempts.py:317, 355 [DERIVED]
- No files, no subprocess, no Qdrant [DERIVED — absent from SOURCE].

## invariants
INVARIANT: failover_attempts == max(0, (attempts - uncorrelated) - logical_calls) — shared/polymath_shared/conformance/attempts.py:250 [DERIVED]
  fails-if: rows without `correlation_id` get counted as provider failover (comment :246-249)
INVARIANT: correlation_id minted only when the merged context lacks one — shared/polymath_shared/conformance/attempts.py:70-71 [DERIVED]
  fails-if: nested contexts (e.g. Ollama `think` retry) split one logical call; `failover_attempts` reads 0 (comment :64-69)
INVARIANT: attempt_ordinal == COALESCE(MAX(attempt_ordinal), 0) + 1 scoped to correlation_id — shared/polymath_shared/conformance/attempts.py:187-188 [DERIVED]
  fails-if: in-process counter records every attempt of sibling contexts as ordinal 1 (comment :183-186)
INVARIANT: rejection_rate > 0.25 AND dispatched > 0 => PROVIDER_PRESSURE finding — shared/polymath_shared/conformance/attempts.py:267 [DERIVED]
  fails-if: sustained provider pressure under the threshold stays unreported
INVARIANT: started_at == now() - latency_ms/1000.0 — shared/polymath_shared/conformance/attempts.py:190 [DERIVED]
  fails-if: column silently holds finish time; latency/overlap analysis inverts (comment :161-165)
INVARIANT: limiter_admitted=false => zero HTTP/quota holds only when limiter_bypassed is false — shared/polymath_shared/conformance/attempts.py:122-125 [DERIVED]
  fails-if: a bypassing seam (probe, chat synthesis) recorded as `limiter_admitted=false` looks like a limiter violation
INVARIANT: http_429 in ledger > 0 AND 0 batch outcomes with HTTP_429 => HIDDEN_429 finding — shared/polymath_shared/conformance/attempts.py:282-287 [DERIVED]
  fails-if: failover-absorbed 429s invisible in outcome counters
INVARIANT: DARK_ENABLED_LANE fires only when the lane's function had live siblings; fully idle functions are context, not findings — shared/polymath_shared/conformance/attempts.py:306-330 [DERIVED]
  fails-if: detector fires on pipeline idle (first implementation reported 31 dark lanes, comment :310-314)

## determinism & idempotency
determinism: NONDETERMINISTIC (uuid `uuid.uuid4().hex[:24]` — shared/polymath_shared/conformance/attempts.py:71; SQL `now()` — :190; per-call DB connect — :175; env `POLYMATH_PG_DSN`/`POLYMATH_ATTEMPT_LEDGER` — :169, :44; concurrency via contextvars + `threading.Event` — :36, :38)
idempotency: UNSAFE — `record()` INSERTs unconditionally; no natural key, ordinal is derived from existing rows, so replaying the same `Attempt` duplicates rows (shared/polymath_shared/conformance/attempts.py:177-197) [DERIVED]

## failure behaviour

| site | handler | caller sees |
|---|---|---|
| record, any Exception — :198-202 | one log warning `attempt ledger unavailable` gated by `_warned` Event, then silent | nothing; call proceeds |
| ledger_available, Exception — :211-212 | swallowed | `False` |
| attempt_summary first query, Exception — :230-231 | swallowed | `{"available": False, "error": str(exc)[:200]}` |
| reconcile outcomes query, Exception — :280-281 | handled | `outcomes = {}` |
| reconcile bypass-lanes query, Exception — :299-300 | handled | `lanes = []` |
| reconcile dark-lane registry, Exception — :331-332 | handled | `dark, idle_functions = [], []` |
| reconcile configured registry, Exception — :357-358 | handled | `configured = {}` |
| `__exit__` ValueError on token reset — :81-89 | handled | context restored by value `_ctx.set(self._prev)`; stream never errors |

No error codes raised; the module raises nothing by design (shared/polymath_shared/conformance/attempts.py:14-16, 159) [DERIVED].

## dumb-code flags
- `reconcile`'s `window` parameter is ignored in the outcomes query: hardcoded `interval '24 hours'` at :279 while every other query interpolates `interval '{window}'` (:227, :236, :297, :363) [DERIVED]
- `window` is f-string-interpolated directly into SQL (`interval '{window}'`) at four sites — shared/polymath_shared/conformance/attempts.py:227, 236, 297, 363 [DERIVED]
- `TABLE` f-string-interpolated into SQL at :177, :227, :236, :297, :363 [DERIVED]
- `next_ordinal` is deprecated and unused by the ledger, but still ships — shared/polymath_shared/conformance/attempts.py:98-106 [DERIVED]
- `merged["_ordinal"]` is copied in `__enter__` (:92) but never incremented there; only `next_ordinal` increments it — shared/polymath_shared/conformance/attempts.py:92, 111 [DERIVED]
- Magic literals: `hex[:24]` (:71), `str(exc)[:200]` (:231), `connect_timeout=3` (:175), threshold `0.25` (:267), lane prefix `"chat_synth"` (:371) [DERIVED]

## refactor notes
- Signature/behaviour changes to `record`, `Attempt`, or `attempt_context` ripple into all three importers: `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/llm_extraction/client.py`, `workers/workers/doc_parent_map_stage_worker.py` [DERIVED — FACTS.importers]
- The INSERT column list (:178-181) must stay in sync with the `llm_provider_attempts` schema (introduced by migration 0059, comment :288-289); adding an `Attempt` field requires touching the column list, VALUES, and params tuple (:177-197) [DERIVED]
- Context key contract: `record` reads `correlation_id, run_id, ticket_id, function, stage` from the contextvar (:191-193); `attempt_context`/`fallback_tags` callers must use these exact key names [DERIVED]
- The lazy imports of `lane_registry` (:317, :355) must stay lazy — "a registry read must never break reconciliation" (:351) [DERIVED]
- Readers take an open `conn` argument while `record` opens its own connection per call (:175); unifying these changes the fail-soft semantics of each path [INFERRED — visible asymmetry, blast radius is failure behaviour]

## VERIFY
```verify
grep -Fq 'TABLE = "llm_provider_attempts"' shared/polymath_shared/conformance/attempts.py
grep -Fq 'COALESCE(MAX(attempt_ordinal), 0) + 1' shared/polymath_shared/conformance/attempts.py
grep -Eq 'now\(\) - make_interval' shared/polymath_shared/conformance/attempts.py
grep -Fq 'POLYMATH_ATTEMPT_LEDGER' shared/polymath_shared/conformance/attempts.py
grep -Fq 'CONFIG/LIVE_MISMATCH' shared/polymath_shared/conformance/attempts.py
test "$(grep -c -F 'document_parent_map_batches' shared/polymath_shared/conformance/attempts.py)" -ge 1
```
