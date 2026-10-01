# unit: orchestrator/orchestrator/api/web_auth.py
anchor: orchestrator/orchestrator/api/web_auth.py:1-202

## purpose
FastAPI router for the web login surface (FRIENDS-ACCESS-V1 F2): sign in, sign out, who-am-I, change my password, and INVITE-SIGNUP account creation. Identity for proxied callers is decided upstream in `web_boundary.py` via `request.state.web_identity`; a direct loopback caller is the owner without a login. ONE-PROFILE policy: new accounts only when `POLYMATH_WEB_SIGNUPS` is truthy (default off). — web_auth.py:1-11 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | module APIRouter | 6 routes below | web_auth.py:24 | orchestrator/orchestrator/main.py |
| login | def POST /auth/login | (body: LoginBody, request: Request) -> JSONResponse | web_auth.py:98-114 | main.py (router) |
| register | def POST /auth/register | (body: RegisterBody, request: Request) -> JSONResponse | web_auth.py:117-145 | main.py (router) |
| logout | def POST /auth/logout | () -> JSONResponse | web_auth.py:148-153 | main.py (router) |
| me | def GET /auth/me | (request: Request) -> JSONResponse | web_auth.py:156-161 | main.py (router) |
| set_owner_password | def POST /auth/owner-password | (body: OwnerPasswordBody, request: Request) -> JSONResponse | web_auth.py:168-184 | main.py (router) |
| change_password | def POST /auth/password | (body: PasswordBody, request: Request) -> JSONResponse | web_auth.py:187-201 | main.py (router) |
| signups_open | def | (env=None) -> bool | web_auth.py:31-34 | — |
| owner_password_set | def | (doc: dict \| None) -> bool | web_auth.py:37-38 | — |
| client_address | def | (request: Request) -> str | web_auth.py:61-69 | — |
| me_payload | def | (ident: W.WebIdentity \| None, \*, local: bool = False) -> dict | web_auth.py:72-80 | — |
| identity | def | (request: Request) -> W.WebIdentity \| None | web_auth.py:83-84 | — |
| _with_session | def | (response: JSONResponse, ident: W.WebIdentity) -> JSONResponse | web_auth.py:87-95 | — (internal) |
| _refuse | def | (status: int, code: str, message: str) -> HTTPException | web_auth.py:57-58 | — (internal) |
| LoginBody / RegisterBody / PasswordBody / OwnerPasswordBody | class (BaseModel) | request bodies | web_auth.py:41-43, 46-49, 52-54, 164-165 | — |

## contracts

**login** — web_auth.py:98-114
- in: `LoginBody{username 1..64, password 1..256}` (41-43).
- pre: `REGISTRY.get()` non-None and `W.session_secret()` non-None, else 503 `LOGIN_NOT_CONFIGURED` (100-102).
- pre: throttle keys `[f"user:{body.username.strip().lower()}", f"addr:{client_address(request)}"]` allowed, else 429 `TOO_MANY_ATTEMPTS` (103-105).
- out: 200, `me_payload(ident)` + session/CSRF cookies via `_with_session` (114, 396→114).
- failure: `W.authenticate_password` None + username == `W.OWNER_USERNAME` + `not owner_password_set(doc)` → 409 `OWNER_PASSWORD_NOT_SET`, no throttle count (107-110); otherwise `THROTTLE.failed(keys)` + 401 `BAD_LOGIN` (111-112).
- post: on success `THROTTLE.succeeded(keys[:1])` clears only the user key (113).

**register** — web_auth.py:117-145
- in: `RegisterBody{username ≤64, password ≤256 (no min), invite_code ≤128}` (46-49).
- pre: `signups_open()` true, else 403 `SIGNUPS_CLOSED` (126-127); registry doc + `W.registry_path()` + session secret present, else 503 `LOGIN_NOT_CONFIGURED` (128-130).
- pre: throttle keys `[INVITE_KEY, f"addr:{client_address(request)}"]` allowed, else 429 `TOO_MANY_ATTEMPTS` (131-133).
- effect: `W.register_friend(path, username, password, invite_code, corpus_ids=web_settings.friend_defaults() libraries, adapter_ids=adapters)` (134-136).
- failure: `W.AccountError` → status from `REGISTER_STATUS.get(exc.code, 400)`; only `INVITE_INVALID` calls `THROTTLE.failed(keys)` (137-140).
- out: 201 + `me_payload` + cookies; identity re-read failure → 500 `SESSION_REFRESH_FAILED` (142-145).

**logout** — web_auth.py:148-153: deletes `W.SESSION_COOKIE` and `W.CSRF_COOKIE` (`path="/"`, `secure=True`, `samesite="strict"`), body `{"signed_out": True}`.

**me** — web_auth.py:156-161: returns `me_payload(ident, local=ident is None)`, `cache-control: no-store`.

**set_owner_password** — web_auth.py:168-184
- pre: `not proxied(headers)` and `not principal_context.current()`, else 403 `LOCAL_ONLY` (173-176).
- pre: `W.registry_path()` non-None, else 503 `ACCOUNTS_NOT_CONFIGURED` ("POLYMATH_MCP_PRINCIPALS_FILE is not set on this server") (177-179).
- pre: `W.password_problem(body.password)` empty, else 422 `WEAK_PASSWORD` (180-182).
- out: `{"owner_password": "set", "username": W.OWNER_USERNAME}` after `W.set_owner_password(path, body.password)` (183-184).

**change_password** — web_auth.py:187-201
- pre: `identity(request)` non-None and `W.registry_path()` non-None, else 409 `NO_WEB_ACCOUNT` (189-192).
- effect: `W.change_password(path, ident.principal_id, current_password, new_password)`; `W.AccountError` → 400 with `exc.code` (193-196).
- post: re-issue session at `{"p": ident.principal_id, "v": ident.session_version + 1}`; resolve failure → 500 `SESSION_REFRESH_FAILED` (197-200).

**signups_open** — web_auth.py:31-34: truthy set is exactly `("1", "true", "yes", "on")`; default `"0"`.

**client_address** — web_auth.py:61-69: `cf-connecting-ip` → first `x-forwarded-for` hop → `request.client.host` → `"unknown"`.

## effect surface
- env: `POLYMATH_WEB_SIGNUPS` = `'0'` (read via `os.environ.get(SIGNUPS_FLAG, "0")`) — web_auth.py:33, 28 [DERIVED]
- env referenced in error text: `POLYMATH_MCP_PRINCIPALS_FILE` — web_auth.py:179 [DERIVED]
- files: principals registry — read (`REGISTRY.get()` 100, 128; `W.read_registry(path)` 142, 197) and written indirectly (`W.register_friend` 136, `W.set_owner_password` 183, `W.change_password` 194) [DERIVED]
- cookies: `W.SESSION_COOKIE` (httponly) and `W.CSRF_COOKIE` (readable) set at 92-93, deleted at 151-152; `max_age=W.SESSION_TTL_S` [DERIVED]
- headers read: `cf-connecting-ip` (63), `x-forwarded-for` (66); header set: `cache-control: no-store` (94, 160) [DERIVED]
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty); Qdrant: none [DERIVED]
- in-process state: `THROTTLE = W.LoginThrottle()` module singleton (25) [DERIVED]

## invariants
INVARIANT: SESSION_COOKIE `httponly=True` AND CSRF_COOKIE `httponly=False` — web_auth.py:92-93 [DERIVED]
  fails-if: page can no longer read the CSRF cookie to echo in `X-Polymath-CSRF` (docstring, 4-5), or the session leaks to JS.
INVARIANT: both cookies `secure=True, samesite="strict", path="/"` — web_auth.py:92-93, 152 [DERIVED]
  fails-if: cookie sent over plain HTTP or cross-site, breaking the boundary model.
INVARIANT: register success status == 201, login success status == 200 — web_auth.py:145, 114 [DERIVED]
  fails-if: clients treating signup responses as errors.
INVARIANT: change_password session version == ident.session_version + 1 — web_auth.py:197-198 [DERIVED]
  fails-if: `W.resolve_session` returns None → 500 SESSION_REFRESH_FAILED despite the write succeeding.
INVARIANT: register throttle keys[0] == INVITE_KEY == `"invite"` (shared by every caller) — web_auth.py:26, 131 [DERIVED]
  fails-if: one attacker's wrong codes lock signup for everyone, since the key is global.
INVARIANT: `THROTTLE.succeeded(keys[:1])` clears only the first key (user key on login, invite key on register) — web_auth.py:113, 141 [DERIVED]
  fails-if: the `addr:` key stays hot; a later attempt from that address is throttled after a success.
INVARIANT: 409 OWNER_PASSWORD_NOT_SET only when username == W.OWNER_USERNAME AND owner_password_set(doc) == False, with no throttle count — web_auth.py:108-110 [DERIVED]
  fails-if: owner-without-password gets 401 BAD_LOGIN and burns throttle budget on a password that cannot exist.
INVARIANT: signups_open truthy values == {"1","true","yes","on"}, default "0" — web_auth.py:33-34 [DERIVED]
  fails-if: an env value like "2" silently keeps signups closed.
INVARIANT: set_owner_password reachable only when proxied(headers) == False AND principal_context.current() falsy — web_auth.py:175-176 [DERIVED]
  fails-if: owner password becomes settable through the proxy by any signed-in principal.
INVARIANT: change_password has no THROTTLE check (contrast login 104) — web_auth.py:187-201 [INFERRED: no THROTTLE call in the function body]
  fails-if: current_password can be brute-forced unthrottled on this route.

## determinism & idempotency
determinism: NONDETERMINISTIC (env flag web_auth.py:33; request headers `cf-connecting-ip`/`x-forwarded-for` 63-68; shared in-process `THROTTLE` 25, 104; registry file contents 100, 128)
idempotency: login/me/logout SAFE (no registry write; login mutates only throttle counters 111-113); register UNSAFE (creates account, writes registry, 136); set_owner_password UNSAFE (overwrites `owner_web.password_hash`, 183); change_password UNSAFE (writes registry, bumps session_version, 194-198)

## failure behaviour
- All refusals are `HTTPException(detail={"error_code", "message"})` built by `_refuse` — web_auth.py:57-58 [DERIVED]
- `W.AccountError` is caught and converted: register maps via `REGISTER_STATUS.get(exc.code, 400)` (137-140); change_password always returns 400 with `exc.code` (195-196) [DERIVED]
- No broad try/except: any non-AccountError exception propagates to FastAPI [INFERRED: only the two targeted `except W.AccountError` blocks exist, 137 and 195]
- Error codes raised: `LOGIN_NOT_CONFIGURED` 503 (90, 102, 130), `TOO_MANY_ATTEMPTS` 429 (105, 133), `OWNER_PASSWORD_NOT_SET` 409 (109), `BAD_LOGIN` 401 (112), `SIGNUPS_CLOSED` 403 (127), `INVITE_INVALID` 403 / `USERNAME_TAKEN` 409 / `USERNAME_INVALID` 422 / `WEAK_PASSWORD` 422 / `INVITES_OFF` 503 (REGISTER_STATUS, 27), `SESSION_REFRESH_FAILED` 500 (144, 200), `LOCAL_ONLY` 403 (176), `ACCOUNTS_NOT_CONFIGURED` 503 (179), `NO_WEB_ACCOUNT` 409 (192) [DERIVED]

## dumb-code flags
- Dead mapping: `REGISTER_STATUS["INVITES_OFF"]=503` can never be hit — closed signups exit earlier with 403 `SIGNUPS_CLOSED` (126-127 vs 27) [INFERRED]
- Two different "closed" codes for the same condition: route says `SIGNUPS_CLOSED` 403, registry map says `INVITES_OFF` 503 — web_auth.py:27, 127 [DERIVED]
- Literal `"web logins are not configured on this server"` duplicated 3× — web_auth.py:90, 102, 130 [DERIVED]
- Literal `"wait 15 minutes"` duplicated with the real window/count living in `W.LoginThrottle` (docstring claims "after five", 121-122) — web_auth.py:105, 133 [DERIVED]
- Throttle key normalizes username (`body.username.strip().lower()`, 103) but `W.authenticate_password` receives raw `body.username` (106) — mismatch if the registry stores normalized names [INFERRED]
- Magic strings: `INVITE_KEY = "invite"` (26), client-address fallback `"unknown"` (69) [DERIVED]
- RegisterBody password has no `min_length`, deferring the rule to the registry's `WEAK_PASSWORD` — comment at 48 [DERIVED]

## refactor notes
- Router is mounted by `orchestrator/orchestrator/main.py` (FACTS.importers); route paths and methods (`/auth/login`, `/auth/register`, `/auth/logout`, `/auth/me`, `/auth/owner-password`, `/auth/password`) are client contract — web_auth.py:98, 117, 148, 156, 168, 187 [DERIVED]
- `me_payload` keys (`username, display_name, is_owner, must_change_password, principal_id, local, web_password_set`) are returned by login, register, me, and change_password — changing the shape breaks all four — web_auth.py:72-80 [DERIVED]
- Cookie names/flags/TTL come from `orchestrator.web_accounts` (`W.SESSION_COOKIE`, `W.CSRF_COOKIE`, `W.SESSION_TTL_S`); `_with_session` and `logout` must stay in sync — web_auth.py:92-93, 151-152 [DERIVED]
- `INVITE_KEY` is a shared global throttle bucket by design ("whoever sent it", 26); renaming or per-caller keys changes lockout semantics — web_auth.py:26, 131 [DERIVED]
- `signups_open` truthy set and default-off are ops contract via `POLYMATH_WEB_SIGNUPS` — web_auth.py:28, 31-34 [DERIVED]
- Identity is set upstream (`request.state.web_identity`, 83-84); this module must not re-derive it — web_auth.py:3-4 [DERIVED]

## VERIFY
```verify
grep -Fq 'INVITE_KEY = "invite"' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'POLYMATH_WEB_SIGNUPS' orchestrator/orchestrator/api/web_auth.py
grep -Eq 'OWNER_PASSWORD_NOT_SET|SIGNUPS_CLOSED|TOO_MANY_ATTEMPTS' orchestrator/orchestrator/api/web_auth.py
test "$(grep -c -F 'LOGIN_NOT_CONFIGURED' orchestrator/orchestrator/api/web_auth.py)" -ge 3
test "$(grep -c -F 'samesite="strict"' orchestrator/orchestrator/api/web_auth.py)" -ge 3
grep -Fq 'cf-connecting-ip' orchestrator/orchestrator/api/web_auth.py
```
