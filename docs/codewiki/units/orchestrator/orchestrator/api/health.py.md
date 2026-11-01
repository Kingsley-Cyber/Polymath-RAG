# unit: orchestrator/orchestrator/api/health.py
anchor: orchestrator/orchestrator/api/health.py:1-190

## purpose
FastAPI router exposing fleet health: `/health` liveness, `/ready` traffic verdict (bounded Postgres probe + informational sidecar status), `/semantic_readiness` semantic-completion verdict, `/sidecars` registry dump, `/health/semantic` per-lane semantic health, `/health/pipeline` BLOCKED-vs-IDLE. [DERIVED orchestrator/orchestrator/api/health.py:1-14, 28-190]
Consumers: the supervisor (liveness = `/health`), `scripts/bounce_fleet.sh` (greps `"ready":true` from `/ready` body), operators. [DERIVED orchestrator/orchestrator/api/health.py:11-14]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| health | async def, route GET /health | () -> dict | orchestrator/orchestrator/api/health.py:29-30 | router; orchestrator/orchestrator/main.py (FACTS.importers) |
| postgres_ready | def | (timeout_s: float = POSTGRES_READY_TIMEOUT_S) -> dict | orchestrator/orchestrator/api/health.py:33-45 | ready (:57) |
| ready | async def, route GET /ready | (request: Request) -> dict | orchestrator/orchestrator/api/health.py:49-58 | router; main.py |
| semantic_readiness | async def, route GET /semantic_readiness | (corpus_id: str) -> dict | orchestrator/orchestrator/api/health.py:62-95 | router; main.py |
| sidecars | async def, route GET /sidecars | (request: Request) -> dict | orchestrator/orchestrator/api/health.py:99-112 | router; main.py |
| semantic_health | def (sync), route GET /health/semantic | (corpus_id: str \| None = None) -> dict | orchestrator/orchestrator/api/health.py:116-175 | router; main.py |
| pipeline | def (sync), route GET /health/pipeline | () -> dict | orchestrator/orchestrator/api/health.py:179-190 | router; main.py |

## contracts

**postgres_ready(timeout_s)** — orchestrator/orchestrator/api/health.py:33-45
- in: `timeout_s: float = POSTGRES_READY_TIMEOUT_S` (= `2.0`, :25) [DERIVED :25,33]
- out: `{"ok": True, "latency_ms": <ms, 1 decimal>}` :42, or `{"ok": False, "latency_ms": ..., "error_code": "POSTGRES_UNAVAILABLE", "error": <type(exc).__name__>}` :44-45 [DERIVED]
- pre: `polymath_shared.db.get_pool` importable :38 [DERIVED]
- post: never raises; leaks no DSN or server message, only the exception type name [DERIVED :34-35,43-45]; exactly one `SELECT 1` through the shared pool with `connection(timeout=timeout_s)` :40-41 [DERIVED]

**ready(request)** — orchestrator/orchestrator/api/health.py:49-58
- in: reads `request.app.state.sidecars`; missing attribute → `{}` :53-55 [DERIVED]
- out: `{"ready": bool(postgres.get("ok")), "postgres": <postgres_ready()>, "sidecars": {name: s.is_ready()}}` :56-58 [DERIVED]
- post: probe off the event loop via `run_in_threadpool` :57; always HTTP 200 with the verdict in the body — a DB outage must not restart-loop the app [DERIVED :11-14]

**semantic_readiness(corpus_id)** — orchestrator/orchestrator/api/health.py:62-95
- pre: `require_corpus(corpus_id)` (FRIENDS-ACCESS-V1 D5) :73; corpus row must exist in `corpora`, else `HTTPException` 404 with `error_code: "QUERY_SCOPE_UNKNOWN"` :76-85 [DERIVED]
- out: `semantic_completion(conn, corpus_id)` dict :86; if `out["vnext"]` is a dict and `served_profiles(corpus_id)` returns non-None, sets `vnext["vnext_served"] = min(int(vnext.documents or 0), count of served cards with writer == "vnext")` :92-94 [DERIVED]
- post: `served_profiles` computed off the event loop :91 [DERIVED]

**sidecars(request)** — orchestrator/orchestrator/api/health.py:99-112
- in: `request.app.state.sidecars`; missing → `{}` :100-103 [DERIVED]
- out: per sidecar `{"release", "model", "base_url", "ready"}` from `s.manifest["identity"]` and `s.is_ready()` :104-111 [DERIVED]

**semantic_health(corpus_id)** — orchestrator/orchestrator/api/health.py:116-175
- in: `corpus_id: str | None = None`; None → no WHERE filter, whole-store aggregates :129-130 [DERIVED]
- out: `{"contract": "polymath-health-surface-v1", "lanes": {...}}` :148; per lane from `knowledge_lane_attempts` GROUP BY lane: status, opportunities, accepted, capture_ratio (`round(acc/opps, 4)`), documents, capped_documents, last_attempt_at :131-160; `out["lanes"]["fact"]` overwritten from the durable funnel (relation_candidates / fact_admission_decisions / facts / evidence counts) :141-146,163-172; `suspect` = lanes whose status == `"SUSPECT"` :173-174 [DERIVED]

**pipeline()** — orchestrator/orchestrator/api/health.py:179-190
- out: `pipeline_health(conn)` verbatim :190; contract PIPELINE-BLOCKED-HEALTH-V1: BLOCKED with cause vs IDLE [DERIVED :180-184]

## effect surface
- Postgres read (direct SQL in this unit): `corpora` :77, `knowledge_lane_attempts` :138, `relation_candidates` :143, `fact_admission_decisions` :144, `facts` :145, `evidence` :146; plus reads inside helpers `semantic_completion` :86, `served_profiles` :91, `pipeline_health` :190 (FACTS.tables_read lists all six tables above) [DERIVED]
- Postgres written: none (FACTS.tables_written is empty) [DERIVED]
- Network: Postgres via shared pool :40; sidecar `is_ready()` probes :56,109 [INFERRED — is_ready is a sidecar reachability check]
- Env flags, Qdrant, files, subprocesses: none visible in this unit

## invariants
INVARIANT: POSTGRES_READY_TIMEOUT_S == 2.0 — orchestrator/orchestrator/api/health.py:25 [DERIVED]
  fails-if: /ready waits unbounded on a dead Postgres and hangs pollers (:24 comment).
INVARIANT: response["ready"] == postgres.get("ok") — sidecar status never flips it — orchestrator/orchestrator/api/health.py:58 [DERIVED]
  fails-if: a parked model being woken makes the fleet look down (:10-11).
INVARIANT: vnext_served <= int(vnext.documents or 0) — enforced by min() — orchestrator/orchestrator/api/health.py:94 [DERIVED]
  fails-if: a refused vNext card paints the library green (:87-88).
INVARIANT: postgres_ready error field == type(exc).__name__ only, error_code == "POSTGRES_UNAVAILABLE" — orchestrator/orchestrator/api/health.py:44-45 [DERIVED]
  fails-if: DSN or server message leaks into /ready body (:34-35).
INVARIANT: /health body == {"status": "ok"} unconditionally — orchestrator/orchestrator/api/health.py:29-30 [DERIVED]
  fails-if: supervisor restart-loops on a DB outage (:13-14).
INVARIANT: capture_ratio == round(accepted/opportunities, 4) in both lane paths — orchestrator/orchestrator/api/health.py:156,171 [DERIVED]
  fails-if: lane health and fact-funnel health report different precision/semantics.
INVARIANT: missing app.state.sidecars yields {} in both /ready and /sidecars — orchestrator/orchestrator/api/health.py:53-55,101-103 [DERIVED]
  fails-if: AttributeError → 500 on apps that never mounted sidecars.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.perf_counter` :36,42,44 feeds latency_ms; DB reads :76-78,131-146,190 return current state) [DERIVED]
idempotency: SAFE (GET-only handlers, zero table writes — FACTS.tables_written empty; each call is a fresh probe/read) [DERIVED]

## failure behaviour
- `except Exception` at :43 (noqa BLE001) is swallowed: caller of postgres_ready sees `{"ok": False, "latency_ms": ..., "error_code": "POSTGRES_UNAVAILABLE", "error": <type name>}` — FACTS.fallbacks line 43; never raises [DERIVED :43-45]
- `AttributeError` on `request.app.state.sidecars` swallowed → `{}` :53-55,101-103 [DERIVED]
- Unknown corpus in /semantic_readiness → HTTPException 404, `error_code: "QUERY_SCOPE_UNKNOWN"`, message `f"corpus {corpus_id!r} not found"` :82-85 [DERIVED]
- No handlers in semantic_health/pipeline: `tx()` failures propagate to FastAPI :128,189 [DERIVED]

## dumb-code flags
- Docstring says autoheal acts on `/live` failures (:4) but the liveness route is `/health` (:28) — stale name in doc [DERIVED :4 vs :28]
- `run_in_threadpool` imported locally twice :50 and :90 [DERIVED]
- Latency expression `round((time.perf_counter() - t0) * 1000, 1)` duplicated :42,44 [DERIVED]
- `out["lanes"]["fact"]` assignment :164 unconditionally overwrites any `fact` lane row coming from the knowledge_lane_attempts GROUP BY loop :149-160 — intentional per :161-162, but the attempts row is silently discarded [DERIVED]
- SQL assembled via f-string `{where}` splice :132,138 — safe here (only "" or `"WHERE corpus_id = %s"` spliced; value stays a %s param) but a string-built-SQL pattern [INFERRED — where literal is fixed at :130]
- Mixed handler styles: async handlers offload blocking work (:57,:91) while semantic_health :116 and pipeline :179 are sync and block on `tx()` :128,189 [DERIVED]
- Route naming inconsistent: underscore `/semantic_readiness` :61 vs slash `/health/semantic` :115 [DERIVED]

## refactor notes
- orchestrator/orchestrator/main.py imports this module (FACTS.importers); the six paths /health, /ready, /semantic_readiness, /sidecars, /health/semantic, /health/pipeline are the fleet-facing API [DERIVED FACTS.routes]
- `scripts/bounce_fleet.sh` greps `"ready":true` from /ready (:12-13) — renaming the key or changing always-200 behavior breaks the bounce script [DERIVED]
- Supervisor liveness is /health (:13) — /health must stay dependency-free [DERIVED]
- External contract literals: SEMANTIC-READINESS-V1 :63, `polymath-health-surface-v1` :148, PIPELINE-BLOCKED-HEALTH-V1 :180; the UI badge reads `vnext_served` :87-88 [DERIVED]
- `require_corpus(corpus_id)` must stay first in any corpus-scoped handler (FRIENDS-ACCESS-V1 D5) :73 [DERIVED]
- `vnext_served` mutates the dict returned by `semantic_completion` in place :92-94 — blast radius if that helper ever caches/reuses result dicts [INFERRED — in-place mutation of a returned dict]

## VERIFY
```verify
grep -Fq 'POSTGRES_READY_TIMEOUT_S = 2.0' orchestrator/orchestrator/api/health.py
grep -Fq '"error_code": "POSTGRES_UNAVAILABLE", "error": type(exc).__name__' orchestrator/orchestrator/api/health.py
grep -Fq 'QUERY_SCOPE_UNKNOWN' orchestrator/orchestrator/api/health.py
grep -Fq 'polymath-health-surface-v1' orchestrator/orchestrator/api/health.py
grep -Fq '"ready": bool(postgres.get("ok"))' orchestrator/orchestrator/api/health.py
grep -Eq 'router\.get\("/(health|ready|sidecars|semantic_readiness|health/semantic|health/pipeline)"\)' orchestrator/orchestrator/api/health.py
! grep -Fq 'INSERT INTO' orchestrator/orchestrator/api/health.py
test "$(grep -c -F 'run_in_threadpool' orchestrator/orchestrator/api/health.py)" -ge 4
```
