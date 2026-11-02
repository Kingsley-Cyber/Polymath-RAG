# unit: orchestrator/orchestrator/main.py
anchor: orchestrator/orchestrator/main.py:1-221
## purpose
FastAPI entrypoint for the orchestrator service: "Stateless. Dumb on purpose" per ADR-0004 (orchestrator/orchestrator/main.py:1-4). Composes 20 API routers (109-142), a principal/web-boundary/CORS middleware stack (59-70), a startup-validation gate (41-45), and static mounts for the two web UIs and a generated-files dir (147-160, 218-220). Serves API clients and the browser UI from one port.

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `lifespan` | async context manager (def) | `(app: FastAPI) -> AsyncContextManager` | orchestrator/orchestrator/main.py:31-48 | `FastAPI(lifespan=lifespan)` at 51 |
| `app` | module attr | `FastAPI(title="Polymath Orchestrator")` | orchestrator/orchestrator/main.py:51 | ASGI server (external; no importer facts present) |
| `_query_activity_signal` | http middleware (def) | `(request, call_next) -> Response` | orchestrator/orchestrator/main.py:88-106 | registered via `@app.middleware("http")` at 87 |
| `_SPAStaticFilesV2` | class (extends `StaticFiles`) | `(directory, html=True)` | orchestrator/orchestrator/main.py:166-210 | `app.mount("/v2", ...)` at 220 |
| `_SPAStaticFilesV2._uncache_html` | method | `(self, response) -> Response` | orchestrator/orchestrator/main.py:196-202 | `get_response` at 206, 209 |
| `_SPAStaticFilesV2.get_response` | method | `(self, path: str, scope) -> Response` | orchestrator/orchestrator/main.py:204-210 | StaticFiles serving machinery ( superclass contract) |

No FACTS.importers data exists for this file; external users unknown.

## contracts

### lifespan(app) — 31-48
- in: `app: FastAPI` (31)
- pre: `validate_startup` / `StartupContractError` importable from `polymath_shared.startup_contract` (37-38)
- out: `app.state.startup_contract = validate_startup()` (41); `app.state.sidecars = load_sidecar_registry()` (47); single `yield` (48)
- post/exn: on `StartupContractError` → `logger.critical("STARTUP BLOCKED", extra={"error_code": exc.code, "detail": exc.detail})` then `raise` (42-45); serving must not start on bad config (32-36)

### _query_activity_signal(request, call_next) — 88-106
- in: fires only on the 9 literal paths `("/chat", "/chat/stream", "/retrieve", "/ask", "/fast", "/hybrid", "/graph", "/product/search", "/product/report/start")` (89-91)
- pre: none; DB imported lazily as `from polymath_shared.db import tx` (93)
- effect: `CREATE TABLE IF NOT EXISTS runtime_signals (key text PRIMARY KEY, updated_at timestamptz NOT NULL)` (96-98) then upsert `('last_query', now())` `ON CONFLICT (key) DO UPDATE SET updated_at = now()` (100-103)
- post: always `return await call_next(request)` (106); the signal write completes BEFORE the handler runs (92-103 precede 106; rationale at 78-83 — first query on a parked embedder must trigger the wake)
- exn: any `Exception` swallowed (104-105)

### _SPAStaticFilesV2.get_response(path, scope) — 204-210
- in: `path: str`
- normal: serve file; HTML responses pass through `_uncache_html` (206)
- 404 branch: iff `exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]` → serve `index.html` (207-209); otherwise `raise` (210)
- post: `text/html` responses get `cache-control: no-cache, no-store, must-revalidate`, `pragma: no-cache`, `expires: 0` (194, 199-201); non-HTML (hashed assets) stay cacheable (190-193)

## effect surface
| kind | target | detail | anchor |
|---|---|---|---|
| Postgres DDL | `runtime_signals` | `CREATE TABLE IF NOT EXISTS`, columns `key text PRIMARY KEY`, `updated_at timestamptz NOT NULL` | orchestrator/orchestrator/main.py:96-98 |
| Postgres write | `runtime_signals` | upsert key `'last_query'` with `now()` | orchestrator/orchestrator/main.py:100-103 |
| Postgres read | none | FACTS.tables_read = [] | orchestrator/orchestrator/main.py:96-103 |
| env | `POLYMATH_GENERATED_DIR` | default `str(_P.home() / "PolymathRuntime" / "polymath-v4" / "generated")` | orchestrator/orchestrator/main.py:153-155 |
| fs write | `_GEN_DIR` | `mkdir(parents=True, exist_ok=True)` | orchestrator/orchestrator/main.py:156 |
| fs mount | `frontend/dist` → `/ui`; `_GEN_DIR` → `/generated` | only if `_UI_DIST.exists()` | orchestrator/orchestrator/main.py:147-160 |
| fs mount | `frontend-v2/dist` → `/v2` | only if `_V2_DIST.exists()` | orchestrator/orchestrator/main.py:218-220 |
| inbound HTTP | CORS | `allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"]`, `allow_methods=["*"]`, `allow_headers=["*"]` | orchestrator/orchestrator/main.py:67-69 |

No Qdrant or subprocess use appears in the 220-line source or FACTS.imports.

## invariants
INVARIANT: signal write (92-103) executes before `call_next` (106) — orchestrator/orchestrator/main.py:92-106 [DERIVED]
  fails-if: first query against a parked embedder fails `embedder_unavailable` on its own wake trigger (78-83)
INVARIANT: every trigger-path request reaches `call_next` regardless of DB outcome (`except Exception` → `pass`, 104-105) — orchestrator/orchestrator/main.py:104-106 [DERIVED]
  fails-if: telemetry outage turns into query failures, violating "a signal write must never fail a query" (75-76)
INVARIANT: SPA fallback fires iff `exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]` — orchestrator/orchestrator/main.py:208 [DERIVED]
  fails-if: missing hashed asset returns HTML and masks a broken deploy (171-172, 190)
INVARIANT: every `text/html` response from the /v2 mount carries `_NO_STORE = "no-cache, no-store, must-revalidate"` — orchestrator/orchestrator/main.py:194,198-199 [DERIVED]
  fails-if: browser replays old index.html with old asset hashes; deploys invisible until hard refresh (observed live 2026-09-12, 186-193)
INVARIANT: `validate_startup()` (41) runs before `yield` (48) — orchestrator/orchestrator/main.py:41-48 [DERIVED]
  fails-if: server serves traffic on bad Postgres creds; every /retrieve burns a 30s pool timeout as HTTP 500 (32-36)
INVARIANT: `app.include_router` call count = 20 — orchestrator/orchestrator/main.py:109-142 [DERIVED]
  fails-if: a router's endpoints silently vanish (404)
INVARIANT: `WebBoundaryMiddleware` added after `PrincipalContextMiddleware` (64 after 59) so the boundary wraps the principal context — orchestrator/orchestrator/main.py:59-64 [DERIVED]
  fails-if: routes see the wrong principal for a signed-in friend (60-61)

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` 101/103; filesystem existence checks `_UI_DIST.exists()` 148, `_V2_DIST.exists()` 219; env `POLYMATH_GENERATED_DIR` 153-155)
idempotency: SAFE (`CREATE TABLE IF NOT EXISTS` 96; upsert `ON CONFLICT (key) DO UPDATE` 100-103; `mkdir(parents=True, exist_ok=True)` 156)

## failure behaviour
- `except Exception: pass` in `_query_activity_signal` — all signal-write failures (DB down, bad creds, DDL denied) swallowed; caller sees the wrapped handler's normal response (104-105; stated intent 75-76).
- `StartupContractError` — logged `critical` `"STARTUP BLOCKED"` with `error_code`/`detail` extras, then re-raised; process refuses to serve (42-45). Error codes originate in `polymath_shared.startup_contract`, not here.
- `_StarletteHTTPExceptionV2` — only the 404 + extension-less case is converted to `index.html`; all others re-raised (207-210).

## dumb-code flags
- Duplicate import: `from pathlib import Path` (145) then `from pathlib import Path as _P` (151).
- Per-request DDL: `CREATE TABLE IF NOT EXISTS runtime_signals` runs inside the request path on every trigger hit, not once at startup (92-98).
- Hardcoded 9-entry path tuple (89-91) duplicates route paths owned by other routers (chat 115, ask 116, retrieve 111, product 139, product_report 142) — no shared constant in this file [INFERRED: sync risk, nothing links them].
- FACTS.tables_written lists `"set"` — that is the SQL `SET updated_at` clause at 103, not a table [INFERRED: analyzer parse artifact].
- CORS: two hardcoded dev origins with wildcard methods/headers (67-69).
- Split include style: 10 grouped `app.include_router` calls (109-118), then 10 more interleaved with imports (119-142).

## refactor notes
- The trigger tuple (89-91) plus write-before-handler ordering (78-83, 106) are the fleet-autopilot wake contract; renaming any of the 9 paths or adding an embedding route without editing 89-11 silently drops wake signals.
- Middleware add order 59 → 64 must keep the boundary outside the principal context (60-61); reordering changes the principal routes see.
- Do not swallow `StartupContractError` (45) — reintroduces the clean-start-then-500-per-request failure mode (33-36).
- `_NO_STORE` must stay scoped to `text/html` (198); extending it to hashed assets forfeits the one-revalidation-per-load property (190-193).
- `_SPAStaticFilesV2` must remain module-level so it is unit-testable without a frontend-v2 build (181-183).
- URL contract: `/ui` (159, rollback reference per 213-217), `/v2` (220), `/generated` (157) — renaming breaks the frontend and the owner's bookmarked URLs.
- `from . import json_logging` at 12 is side-effect-only (O-07 log config on import); removing it silently drops JSON logging.

## VERIFY
```verify
grep -Fq 'app = FastAPI(title="Polymath Orchestrator", lifespan=lifespan)' orchestrator/orchestrator/main.py
grep -Fq 'no-cache, no-store, must-revalidate' orchestrator/orchestrator/main.py
grep -Fq 'POLYMATH_GENERATED_DIR' orchestrator/orchestrator/main.py
grep -Fq 'http://localhost:5173' orchestrator/orchestrator/main.py
test "$(grep -c -F 'app.include_router' orchestrator/orchestrator/main.py)" -ge 20
test "$(grep -c -F 'runtime_signals' orchestrator/orchestrator/main.py)" -ge 2
! grep -Fq 'allow_credentials' orchestrator/orchestrator/main.py
```
