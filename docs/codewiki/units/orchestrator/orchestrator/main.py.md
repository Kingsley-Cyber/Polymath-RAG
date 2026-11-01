# unit: orchestrator/orchestrator/main.py
anchor: orchestrator/orchestrator/main.py:1-214

## purpose
FastAPI entrypoint for the Polymath Orchestrator — "Role: orchestrator. Stateless. Dumb on purpose. See ADR-0004." (orchestrator/orchestrator/main.py:1-4) [DERIVED].
Validates startup config before serving, loads the sidecar registry, registers 19 API routers, layers principal/web-boundary/CORS middleware, records query-activity signals for the fleet autopilot's demand policy, and serves the built UIs (`/ui`, `/v2`, `/generated`) from one port (orchestrator/orchestrator/main.py:31-48, 59-70, 84-102, 105-135, 137-153, 206-213) [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `lifespan` | async context manager (def) | `(app: FastAPI)` -> yields after validation | orchestrator/orchestrator/main.py:31-48 | `FastAPI(title="Polymath Orchestrator", lifespan=lifespan)` orchestrator/orchestrator/main.py:51 [DERIVED] |
| `app` | FastAPI instance | — | orchestrator/orchestrator/main.py:51 | ASGI entrypoint (no importer in FACTS) — |
| `_query_activity_signal` | HTTP middleware (def) | `(request, call_next)` -> `await call_next(request)` | orchestrator/orchestrator/main.py:85-102 | `@app.middleware("http")` orchestrator/orchestrator/main.py:84 [DERIVED] |
| `_SPAStaticFilesV2` | class (StaticFiles subclass) | `get_response(path: str, scope)`, `_uncache_html(response)` | orchestrator/orchestrator/main.py:159-203 | `app.mount("/v2", _SPAStaticFilesV2(...))` orchestrator/orchestrator/main.py:213 [DERIVED] |

No FACTS.importers present — external consumers unknown.

## contracts
`lifespan(app)` — orchestrator/orchestrator/main.py:31-48
- in: none; config read via `validate_startup()` from `polymath_shared.startup_contract` (orchestrator/orchestrator/main.py:37-38, 41).
- out: `app.state.startup_contract = validate_startup()` (orchestrator/orchestrator/main.py:41); `app.state.sidecars = load_sidecar_registry()` (orchestrator/orchestrator/main.py:47).
- post: on `StartupContractError` -> `logger.critical("STARTUP BLOCKED", extra={"error_code": exc.code, "detail": exc.detail})` then `raise` — fail loud before serving (orchestrator/orchestrator/main.py:42-45, 32-36).

`_query_activity_signal(request, call_next)` — orchestrator/orchestrator/main.py:85-102
- pre: fires only when `request.url.path` is one of `("/chat", "/chat/stream", "/retrieve", "/ask", "/fast", "/hybrid", "/graph", "/product/search")` (orchestrator/orchestrator/main.py:86-87).
- in/out: upserts `runtime_signals` row `('last_query', now())` BEFORE the handler runs, then `return await call_next(request)` (orchestrator/orchestrator/main.py:90-102, write-first rationale 78-83).
- post: any `Exception` in the write is swallowed — "a signal write must never fail a query" (orchestrator/orchestrator/main.py:100-101, 75-76).

`_SPAStaticFilesV2.get_response(path, scope)` — orchestrator/orchestrator/main.py:197-203
- in: `path: str`, `scope`.
- out: normal StaticFiles response with HTML un-cached; on 404 with extension-less last segment -> serves `index.html`; other 404s re-raised (orchestrator/orchestrator/main.py:199-203).
- post: HTML responses get `cache-control`/`pragma`/`expires` no-store headers (orchestrator/orchestrator/main.py:189-195, 187).

## effect surface
| kind | detail | anchor |
|---|---|---|
| Postgres write | table `runtime_signals`: `CREATE TABLE IF NOT EXISTS` + upsert `('last_query', now()) ON CONFLICT (key) DO UPDATE` | orchestrator/orchestrator/main.py:91-99 |
| Postgres read | none (`tables_read: []` per FACTS) | FACTS |
| Files | `frontend/dist` mounted at `/ui` if it exists | orchestrator/orchestrator/main.py:140-153 |
| Files | `frontend-v2/dist` mounted at `/v2` via `_SPAStaticFilesV2` if it exists | orchestrator/orchestrator/main.py:211-213 |
| Files | env dir created with `mkdir(parents=True, exist_ok=True)`, mounted at `/generated` | orchestrator/orchestrator/main.py:149-151 |
| env | `POLYMATH_GENERATED_DIR` = `str(_P.home() / "PolymathRuntime" / "polymath-v4" / "generated")` | orchestrator/orchestrator/main.py:146-148 |
| network | CORS `allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"]`, `allow_methods=["*"]`, `allow_headers=["*"]` — dev-server origins only | orchestrator/orchestrator/main.py:65-70 |
| subprocess | none visible | — |
| import side effect | `from . import json_logging` "configures on import" | orchestrator/orchestrator/main.py:12 |

## invariants
INVARIANT: signal-path set == {"/chat", "/chat/stream", "/retrieve", "/ask", "/fast", "/hybrid", "/graph", "/product/search"} — orchestrator/orchestrator/main.py:86-87 [DERIVED]
  fails-if: a query route outside the tuple never wakes parked sidecars (`embedder_unavailable`, orchestrator/orchestrator/main.py:79-81)
INVARIANT: signal write strictly before `await call_next(request)` — orchestrator/orchestrator/main.py:90-102 [DERIVED]
  fails-if: the wake-trigger request itself fails `embedder_unavailable` while waiting for the embedder (orchestrator/orchestrator/main.py:78-83)
INVARIANT: rows with key='last_query' == 1 (upsert `ON CONFLICT (key) DO UPDATE`) — orchestrator/orchestrator/main.py:95-99 [DERIVED]
  fails-if: plain INSERT would grow the table and stale/ambiguous wake timestamps
INVARIANT: SPA fallback fires iff `exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]` — orchestrator/orchestrator/main.py:201 [DERIVED]
  fails-if: a genuinely missing hashed asset (e.g. `/v2/assets/app-xyz.js` after a stale deploy) would silently return HTML (orchestrator/orchestrator/main.py:181-182)
INVARIANT: `cache-control == "no-cache, no-store, must-revalidate"` applied only when `media.startswith("text/html")` — orchestrator/orchestrator/main.py:187, 190-192 [DERIVED]
  fails-if: cached index.html replays old asset hashes — app stays on the previous build until hard refresh (orchestrator/orchestrator/main.py:179-183)
INVARIANT: add-middleware order == PrincipalContextMiddleware, then WebBoundaryMiddleware, then CORSMiddleware — orchestrator/orchestrator/main.py:59, 64, 65-70 [DERIVED]
  fails-if: boundary inside principal context forwards the wrong principal for signed-in friends ("added after = wraps it", orchestrator/orchestrator/main.py:60-61)

## determinism & idempotency
determinism: NONDETERMINISTIC (db `now()` in the upsert orchestrator/orchestrator/main.py:98; env default `POLYMATH_GENERATED_DIR` orchestrator/orchestrator/main.py:146-148; mounts gated on dist-directory existence orchestrator/orchestrator/main.py:141, 212; import-time logging config orchestrator/orchestrator/main.py:12)
idempotency: SAFE (`CREATE TABLE IF NOT EXISTS` orchestrator/orchestrator/main.py:91-94; `ON CONFLICT (key) DO UPDATE` 95-99; `mkdir(parents=True, exist_ok=True)` 149)

## failure behaviour
- `except Exception: pass` — swallowed (FACTS.fallbacks: Exception -> "SWALLOWED: pass") at orchestrator/orchestrator/main.py:100-101; caller sees the normal handler response, autopilot silently loses the wake signal.
- `StartupContractError` -> `logger.critical("STARTUP BLOCKED", ...)` then re-raise; startup must abort instead of serving HTTP 500s with 30s pool timeouts per request (orchestrator/orchestrator/main.py:42-45, 32-36).
- SPA mount: extension-less 404 becomes an index.html response; extension 404 re-raised to the client (orchestrator/orchestrator/main.py:200-203).

## dumb-code flags
- Per-request DDL: `CREATE TABLE IF NOT EXISTS runtime_signals` executes inside the HTTP middleware on every matched request — orchestrator/orchestrator/main.py:91-94.
- Route knowledge duplicated: the 8-path literal tuple in main.py must mirror routes defined in other modules — orchestrator/orchestrator/main.py:86-87.
- `allow_methods=["*"]`, `allow_headers=["*"]` beside a fixed 2-origin allowlist — orchestrator/orchestrator/main.py:65-70.
- Module import == full app assembly (middleware, 19 `app.include_router` calls, mounts, mkdir are import side effects) — orchestrator/orchestrator/main.py:51-153.
- Late inline imports interleaved with router registration — orchestrator/orchestrator/main.py:115-135.
- FACTS artifact: `tables_written` lists a bogus table `"set"` — mis-parse of `DO UPDATE SET` (orchestrator/orchestrator/main.py:98); the only real table is `runtime_signals`.

## refactor notes
- Any new API router must be wired here: 19 `app.include_router` calls — orchestrator/orchestrator/main.py:105-135.
- Do not reorder `add_middleware` calls; boundary-wraps-principal is the FRIENDS-ACCESS-V1 D3 contract — orchestrator/orchestrator/main.py:59-64.
- Keep the signal write before `call_next` (WAKE-ON-QUERY); the embed path waits via `fast._await_embedder` per the comment — orchestrator/orchestrator/main.py:78-83, 90-102.
- Keep `_SPAStaticFilesV2` at module level so it is importable/unit-testable without a frontend-v2 build (dist is git-ignored) — orchestrator/orchestrator/main.py:174-176.
- Do not make index.html cacheable; hashed assets stay cacheable, index must not — orchestrator/orchestrator/main.py:178-187.
- `_UI_DIST`/`_V2_DIST` both use `Path(__file__).resolve().parents[2]` — moving this file breaks both mounts — orchestrator/orchestrator/main.py:140, 211.
- `/ui` is deliberately kept as the rollback reference beside `/v2` (FRONTEND-V2-PLAN §0.1); mounts are independent — orchestrator/orchestrator/main.py:206-213.

## VERIFY
```verify
grep -Fq 'title="Polymath Orchestrator", lifespan=lifespan' orchestrator/orchestrator/main.py
grep -Fq 'STARTUP BLOCKED' orchestrator/orchestrator/main.py
grep -Eq 'last_query' orchestrator/orchestrator/main.py
grep -Fq 'no-cache, no-store, must-revalidate' orchestrator/orchestrator/main.py
grep -Fq 'POLYMATH_GENERATED_DIR' orchestrator/orchestrator/main.py
grep -Fq 'embedder_unavailable' orchestrator/orchestrator/main.py
! grep -Fq 'allow_origins=["*"]' orchestrator/orchestrator/main.py
test "$(grep -c -F 'app.include_router' orchestrator/orchestrator/main.py)" -ge 19
```
