# unit: orchestrator/orchestrator/main.py
anchor: orchestrator/orchestrator/main.py:1-209

## purpose
FastAPI entrypoint for the Polymath orchestrator: wires 18 API routers, three middleware layers, and static mounts for `/ui`, `/v2`, `/generated`. Self-described as "orchestrator. Stateless. Dumb on purpose." per ADR-0004. main.py:1-3 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `lifespan` | async def (asynccontextmanager) | `app` -> yields (sets `app.state`) | main.py:30-47 | `FastAPI(title="Polymath Orchestrator", lifespan=lifespan)` main.py:50 |
| `_query_activity_signal` | http middleware | `(request, call_next)` -> Response | main.py:84-101 | `@app.middleware("http")` main.py:83 |
| `_SPAStaticFilesV2` | class (StaticFiles subclass) | methods `_uncache_html(response)`, `get_response(path, scope)` | main.py:155-199 | `/v2` mount main.py:209 |
| `app` | FastAPI instance | module-level, `title="Polymath Orchestrator"` | main.py:50 | all routers included main.py:104-131 |

No external importers of these symbols appear in FACTS.

## contracts

**`lifespan(app)`** main.py:30-47
- in: none beyond the app instance.
- pre: none.
- does: `validate_startup()` from `polymath_shared.startup_contract`; result stored as `app.state.startup_contract` (main.py:40); `load_sidecar_registry()` stored as `app.state.sidecars` (main.py:46).
- post: on `StartupContractError`, logs `logger.critical("STARTUP BLOCKED", extra={"error_code": exc.code, "detail": exc.detail})` and re-raises — process fails loud, does not serve (main.py:31-44).

**`_query_activity_signal(request, call_next)`** main.py:84-101
- trigger set (exact): `request.url.path in ("/chat", "/chat/stream", "/retrieve", "/ask", "/fast", "/hybrid", "/graph")` main.py:85-86.
- does, BEFORE the handler runs: create table if missing, upsert `('last_query', now())` (main.py:87-98). Write ordering is deliberate: WAKE-ON-QUERY 2026-08-27, first query against a parked embedder used to fail `embedder_unavailable` when the signal landed after the response (main.py:77-82).
- post: `return await call_next(request)` always reached on non-exception paths (main.py:101).

**`_SPAStaticFilesV2.get_response(path, scope)`** main.py:193-199
- in: SPA path + ASGI scope.
- post: on 404 AND `"." not in path.rsplit("/", 1)[-1]`, serve `index.html` instead (main.py:197-198); a missing fingerprinted asset (has extension) still 404s.
- post: any `text/html` response gets `cache-control: no-cache, no-store, must-revalidate`, `pragma: no-cache`, `expires: 0` (main.py:183, 185-191). Reason: Vite fingerprints assets (`index-<hash>.js`), so only `index.html` URL is stable across deploys; cached index = invisible deploys, observed live 2026-09-12 (main.py:174-182).

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres write | table `runtime_signals` (`key text PRIMARY KEY, updated_at timestamptz NOT NULL`), upsert `ON CONFLICT (key) DO UPDATE SET updated_at = now()` | main.py:91-98 |
| Postgres read | none in this file | FACTS.tables_read = [] |
| filesystem read/mount | `frontend/dist` at `/ui`; `frontend-v2/dist` at `/v2`; both mounted only `if _DIST.exists()` | main.py:136-149, 207-209 |
| filesystem write | `_GEN_DIR.mkdir(parents=True, exist_ok=True)` then mounted at `/generated` | main.py:142-147 |
| env | `POLYMATH_GENERATED_DIR` = default `str(_P.home() / 'PolymathRuntime' / 'polymath-v4' / 'generated')` | main.py:142-144 |
| CORS | `allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"]`, methods/headers `["*"]` | main.py:64-69 |
| network/subprocess/Qdrant | none visible in this file | — |

## invariants

INVARIANT: middleware ordering — `WebBoundaryMiddleware` added AFTER `PrincipalContextMiddleware` (main.py:58, 63), so the boundary wraps the principal context for signed-in friends — main.py:59-63 [DERIVED]
  fails-if: swapping add order makes the principal the routes see come from the wrong layer for friend traffic.
INVARIANT: signal write executes before `call_next` — main.py:98-101 [DERIVED]
  fails-if: moving it after reintroduces `embedder_unavailable` on the wake-trigger query (main.py:77-82).
INVARIANT: a signal-write exception never fails the query — `except Exception: pass` — main.py:99-100 [DERIVED]
  fails-if: removing the swallow turns a DB outage into a hard failure of `/chat`, `/retrieve`, `/ask`, `/fast`, `/hybrid`, `/graph`.
INVARIANT: SPA fallback fires only when `"." not in path.rsplit("/", 1)[-1]` — main.py:197 [DERIVED]
  fails-if: dropping the extension check silently serves HTML in place of 404'd assets after a stale deploy (main.py:161, 173-174).
INVARIANT: `index.html` served with `_NO_STORE = "no-cache, no-store, must-revalidate"` — main.py:183, 188 [DERIVED]
  fails-if: cached index pins old asset hashes; app stays on the previous build until hard refresh (main.py:175-182).
INVARIANT: `/v2` and `/ui` mounts conditional on their dist directories existing — main.py:137, 208 [DERIVED]
  fails-if: mounting unconditionally crashes boot on a machine without a frontend build; `/ui` is the documented rollback reference (FRONTEND-V2-PLAN §0.1, main.py:205).

## determinism & idempotency
determinism: NONDETERMINISTIC (db `now()` timestamps main.py:97; filesystem existence checks for mounts main.py:137, 208; env `POLYMATH_GENERATED_DIR` main.py:142)
idempotency: SAFE (the only write is an upsert `ON CONFLICT (key) DO UPDATE` on `runtime_signals` main.py:95-98; DDL is `CREATE TABLE IF NOT EXISTS` main.py:91-93)

## failure behaviour
- `StartupContractError` from `validate_startup()` — logged critical with `error_code`/`detail`, then re-raised; app refuses to start (main.py:41-44). Rationale: wrong Postgres credential used to start clean then 500 every `/retrieve` with a 30s pool timeout per request (main.py:31-35).
- `Exception` in the signal write is swallowed (`pass`), FACTS fallback line 99 — caller sees the normal handler response, signal loss is invisible (no log) (main.py:99-100). [DERIVED]

## dumb-code flags
- Bare `except Exception: pass` with no logging at main.py:99-100 — silent signal loss; contradicts the fail-loud philosophy at main.py:31-35.
- `CREATE TABLE IF NOT EXISTS` DDL on the hot path of every matching request (main.py:91-93) — runs per query, not once at startup.
- Hardcoded 7-path literal list duplicated between the middleware trigger (main.py:85-86) and router mounts (main.py:104-112); adding a query route requires editing both.
- FACTS.tables_written contains a stray `"set"` entry (FACTS:106-109) — an artifact of parsing the SQL `SET updated_at`, not a table. [INFERRED]
- Docstring carries a correction log: an earlier version wrongly claimed React Router/BrowserRouter owns `/v2/*` paths; the app actually uses plain `useState<ScreenId>` with no router (main.py:163-168).
- CORS origins hardcode dev ports `5173` for dev-server-only use; production serves from the same process (main.py:52-53, 66).

## refactor notes
- `_SPAStaticFilesV2` is defined at module level deliberately, outside the `if _V2_DIST.exists()` guard, so it stays importable/unit-testable where no frontend-v2 build exists (dist is git-ignored) — main.py:170-172. Moving it inside the guard breaks those tests.
- Moving the signal write after `call_next` reintroduces the 2026-08-27 wake-ordering bug; `fast._await_embedder` depends on write-first (main.py:77-82).
- Middleware add order is contract, not style: boundary-after-principal (main.py:58-63); CORSMiddleware added last makes it the outermost layer. [INFERRED — Starlette wraps in reverse add order]
- `app.state.startup_contract` and `app.state.sidecars` (main.py:40, 46) are consumed downstream; renaming either breaks readers not visible in this file.
- All 18 `app.include_router` calls live here (main.py:104-131); a new route module must be added in this file, and query-serving ones likely also need their path added at main.py:85-86.

## VERIFY
```verify
grep -Fq 'runtime_signals' orchestrator/orchestrator/main.py
grep -Fq 'no-cache, no-store, must-revalidate' orchestrator/orchestrator/main.py
grep -Fq 'POLYMATH_GENERATED_DIR' orchestrator/orchestrator/main.py
grep -Fq 'http://localhost:5173' orchestrator/orchestrator/main.py
grep -Eq 'except Exception:\s*$' orchestrator/orchestrator/main.py
test "$(grep -c -F 'app.include_router' orchestrator/orchestrator/main.py)" -ge 17
! grep -Fq 'from react_router' orchestrator/orchestrator/main.py
```
