# flow: web-sign-in
Website sign-in and the web boundary: POST /auth/login, the session and CSRF cookies, every later proxied request classified public / user / write / owner, the owner's password set on the server itself.

## hops
| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Direct loopback requests pass `WebBoundaryMiddleware` untouched; only proxied traffic is gated | orchestrator/orchestrator/web_boundary.py:106-109 [DERIVED] | ASGI scope -> same scope | proxied websocket closed with code 1008 |
| 2 | `classify(method, path)` -> `"public"`/`"user"`/`"write"`/`"owner"` or None; `/auth/login` is public | orchestrator/orchestrator/web_boundary.py:66-70, 115-118 [DERIVED] | method+path -> class | unmatched -> 403 `ROUTE_NOT_ALLOWED` |
| 3 | `login(body, request)`: `REGISTRY.get()` cache; path from env `POLYMATH_MCP_PRINCIPALS_FILE` | orchestrator/orchestrator/api/web_auth.py:99-100; web_scope.py:46-53; web_accounts.py:101-103 [DERIVED] | env -> registry doc or None | path unset -> None; stat `OSError` -> `{"schema": P.SCHEMA, "principals": []}` (empty, not None) |
| 4 | Cache re-read keyed on `(str(path), st_mtime_ns, st_ino, st_size)`; perms `st.st_mode & 0o077` refused; `read_registry` validates `schema == SCHEMA` and `principals` list | orchestrator/orchestrator/web_scope.py:54-64; mcp_principals.py:349-355 [DERIVED] | stat key -> doc | loose perms -> `"{path} must be owner-only (chmod 600)"` ValueError -> doc None; wrong schema -> ValueError |
| 5 | Configured gate: doc non-None and `W.session_secret()` non-None; secret = env `POLYMATH_WEB_SESSION_SECRET`, None when `len(raw) < 32` | orchestrator/orchestrator/api/web_auth.py:101-102; web_accounts.py:458-460 [DERIVED] | doc + env -> pass | either None -> 503 `LOGIN_NOT_CONFIGURED` |
| 6 | Throttle: keys `[f"user:{username.strip().lower()}", f"addr:{client_address(request)}"]`; address = `cf-connecting-ip` -> first `x-forwarded-for` hop -> `request.client.host` -> `"unknown"` | orchestrator/orchestrator/api/web_auth.py:103-105, 61-69 [DERIVED] | username + headers -> keys | `THROTTLE.allowed(keys)` false -> 429 `TOO_MANY_ATTEMPTS` "too many failed sign-ins; wait 15 minutes" |
| 7 | `W.authenticate_password(doc, username, password)` -> `_identity`: owner branch needs `name == OWNER_USERNAME` and `web.get("username") == OWNER_USERNAME`; friend branch scans `doc["principals"]` for `rec["web"]["username"] == name` | orchestrator/orchestrator/web_accounts.py:431-437, 406-421, 160-165, 168-170 [DERIVED] | doc + username -> `(WebIdentity, stored hash)` or None | unknown user: `verify_password(str(password), _DUMMY_HASH)` (same work, no timing oracle) then None |
| 8 | Friend liveness `P._active(rec, now)`: `enabled is True`, no `revoked_at`, `expires_at` in the future | orchestrator/orchestrator/mcp_principals.py:227-239 [DERIVED] | rec + now -> bool | unreadable expiry treated as expired (fail closed) |
| 9 | `verify_password`: stored split on `"$"`, `kind != "scrypt"` -> False, recompute `hashlib.scrypt(password, salt=_unb64(salt), n, r, p, dklen=len(want))`, `hmac.compare_digest` | orchestrator/orchestrator/web_accounts.py:88-97 [DERIVED] | password + `scrypt$...` -> bool | parse errors -> False; mismatch -> False |
| 10 | Failed-login branch: owner name + `not owner_password_set(doc)` (checks `owner_web.password_hash`) -> 409 `OWNER_PASSWORD_NOT_SET` raised BEFORE `THROTTLE.failed`; otherwise `THROTTLE.failed(keys)` -> 401 `BAD_LOGIN` | orchestrator/orchestrator/api/web_auth.py:107-112, 37-38 [DERIVED] | ident None -> error | 409 (no throttle count) or throttle-counted 401 |
| 11 | Success clears only the user key: `THROTTLE.succeeded(keys[:1])` | orchestrator/orchestrator/api/web_auth.py:113 [DERIVED] | keys -> cleared user key | addr-key failure history survives |
| 12 | `W.make_session`: csrf = `secrets.token_urlsafe(24)`; payload `{"p": principal_id, "v": session_version, "e": expiry, "c": csrf}`; cookie = `f"{body}.{_b64(_sign(secret, body))}"`, `_sign` = HMAC-SHA256 | orchestrator/orchestrator/web_accounts.py:463-468, 582-583 [DERIVED] | secret + ident -> (cookie value, csrf token) | — |
| 13 | `_with_session`: `SESSION_COOKIE` httponly=True, `CSRF_COOKIE` httponly=False, both `secure=True, samesite="strict", path="/", max_age=W.SESSION_TTL_S`; body = `me_payload(ident)`; `cache-control: no-store` | orchestrator/orchestrator/api/web_auth.py:87-95, 114, 72-80 [DERIVED] | ident -> 200 JSON + 2 cookies | secret became None -> 503 `LOGIN_NOT_CONFIGURED` |
| 14 | Later proxied request: session resolved, `csrf_ok` on non-safe methods, `must_change_password` and owner-class gates | orchestrator/orchestrator/web_boundary.py:119-137 [DERIVED] | cookie + headers -> identity | 401 `LOGIN_REQUIRED`; 403 `CSRF_FAILED`; 403 `PASSWORD_CHANGE_REQUIRED`; 403 `OWNER_ONLY` |
| 15 | Non-owner forwarded with header `(principal_context.HEADER, ident.principal_id)`; `scope["state"]["web_identity"] = ident`; incoming principal header always stripped | orchestrator/orchestrator/web_boundary.py:113, 138-141 [DERIVED] | ident -> narrowed downstream scope | — |
| 16 | GET /auth/me: `identity(request)` reads `request.state.web_identity`; ident None (direct loopback) -> owner payload `"King"`, `is_owner: True`, `local=True` | orchestrator/orchestrator/api/web_auth.py:157-161, 83-84, 72-77 [DERIVED] | request -> `me_payload`, `cache-control: no-store` | — |
| 17 | POST /auth/owner-password local-only gate: `proxied(headers)` (any of `x-forwarded-for`, `forwarded`, `x-forwarded-host`) or `principal_context.current()` -> refused | orchestrator/orchestrator/api/web_auth.py:169-176; web_boundary.py:73-74; shared/polymath_shared/principal_context.py:23-25 [DERIVED] | headers + contextvar -> allow/refuse | 403 `LOCAL_ONLY` "set the owner password on the server itself" |
| 18 | Registry + password checks: `W.registry_path()` non-None; `W.password_problem` — only emptiness refused (`len(password) < MIN_PASSWORD`) | orchestrator/orchestrator/api/web_auth.py:177-182; web_accounts.py:74-78 [DERIVED] | body.password -> pass | path None -> 503 `ACCOUNTS_NOT_CONFIGURED`; empty -> 422 `WEAK_PASSWORD` "a password cannot be empty" |
| 19 | `W.set_owner_password`: `_new_web` builds `{username, password_hash, password_changed_at, session_version: 1, must_change_password: False}` + `display_name = "King"`; `session_version = int(old or 0) + 1` | orchestrator/orchestrator/web_accounts.py:185-192, 177-182 [DERIVED] | password -> new `doc["owner_web"]` | — |
| 20 | `hash_password` + persist: salt `secrets.token_bytes(16)`, `hashlib.scrypt(..., **_SCRYPT)`, stored `"scrypt${n}${r}${p}${s}${d}"`; `update_registry` under flock `.name.lock`, write via temp `.{name}.{pid}.tmp` mode `0o600`, fsync, `os.replace`, final `chmod 0o600` | orchestrator/orchestrator/web_accounts.py:81-85, 118-123, 107-115; mcp_principals.py:358-375 [DERIVED] | doc -> registry file | a reader sees old or new, never half |
| 21 | Response `{"owner_password": "set", "username": W.OWNER_USERNAME}` | orchestrator/orchestrator/api/web_auth.py:184 [DERIVED] | -> JSON | — |

## state written
- File: principals registry at `POLYMATH_MCP_PRINCIPALS_FILE` — `doc["owner_web"]` replaced (username, scrypt password_hash, password_changed_at, session_version = old+1, must_change_password False, display_name "King") — orchestrator/orchestrator/web_accounts.py:185-192, 177-182 [DERIVED]; atomic write + `chmod 0o600` — orchestrator/orchestrator/mcp_principals.py:358-375 [DERIVED]; lock file `.{name}.lock` — orchestrator/orchestrator/web_accounts.py:107-115 [DERIVED].
- Client cookies: `W.SESSION_COOKIE` (signed session) and `W.CSRF_COOKIE` (readable token) — orchestrator/orchestrator/api/web_auth.py:91-93 [DERIVED].
- In-memory: `RegistryCache._doc` replaced whenever `(path, mtime_ns, ino, size)` changes — orchestrator/orchestrator/web_scope.py:54-64 [DERIVED].
- Postgres/Qdrant: none on this path (FACTS tables_read/tables_written empty for these modules) — units/orchestrator/orchestrator/mcp_principals.py.md [DERIVED].

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PRINCIPALS_FILE` | unset (`""`) | registry location; unset -> `registry_path()` None -> `REGISTRY.get()` None -> login 503 `LOGIN_NOT_CONFIGURED`, owner-password 503 `ACCOUNTS_NOT_CONFIGURED` | orchestrator/orchestrator/web_accounts.py:101-103 [DERIVED] |
| `POLYMATH_WEB_SESSION_SECRET` | unset (`""`) | `len(raw) < 32` -> `session_secret()` None -> 503 `LOGIN_NOT_CONFIGURED` at login and again in `_with_session` | orchestrator/orchestrator/web_accounts.py:458-460; web_auth.py:101-102, 88-90 [DERIVED] |

## failure modes
1. Login always 503 `LOGIN_NOT_CONFIGURED` -> registry env unset, cached read failed (loose perms / bad schema), or secret env shorter than 32 chars -> look orchestrator/orchestrator/api/web_auth.py:101-102, orchestrator/orchestrator/web_scope.py:47-62, orchestrator/orchestrator/web_accounts.py:458-460.
2. Registry file exists but perms have group/other bits -> `ValueError` "must be owner-only (chmod 600)" -> `REGISTRY.get()` returns None with `last_error` set -> every login 503 -> orchestrator/orchestrator/web_scope.py:58-62.
3. Registry file missing (stat `OSError`) -> doc is the EMPTY `{"schema": P.SCHEMA, "principals": []}`, not None -> gate passes, `_identity` finds nothing -> owner name gets 409 `OWNER_PASSWORD_NOT_SET`, others get 401 `BAD_LOGIN` -> orchestrator/orchestrator/web_scope.py:51-53, orchestrator/orchestrator/api/web_auth.py:107-112.
4. 429 `TOO_MANY_ATTEMPTS` -> `THROTTLE.failed` accumulated on `user:` and `addr:` keys; window message "wait 15 minutes" (LoginThrottle limit=5, window_s=900) -> orchestrator/orchestrator/api/web_auth.py:103-105, 111; orchestrator/orchestrator/web_accounts.py:504-532.
5. Owner name + 409 never opens the throttle counter -> raise precedes `THROTTLE.failed` -> orchestrator/orchestrator/api/web_auth.py:108-111.
6. Owner locked out of the website -> `owner_web.password_hash` missing -> set it server-local at `http://127.0.0.1:7200` POST /auth/owner-password -> orchestrator/orchestrator/api/web_auth.py:108-110, 169-176.
7. Owner signed out right after password set -> `session_version` bumped to old+1; cookies carry the old `"v"` -> orchestrator/orchestrator/web_accounts.py:190, 465-466 [INFERRED: payload `"v"` changes, so previously issued cookies no longer match].
8. `set_owner_password` returns 403 `LOCAL_ONLY` -> request arrived proxied (a `PROXY_HEADERS` header present) or inside a principal context -> orchestrator/orchestrator/api/web_auth.py:173-176, orchestrator/orchestrator/web_boundary.py:73-74.
9. Silent fallback: GET /auth/me with no `web_identity` returns the OWNER payload ("King", `is_owner: True`) — loopback is trusted as the owner, not a bug -> orchestrator/orchestrator/api/web_auth.py:72-77, 83-84.
10. Silent fallback: unknown usernames burn full scrypt work against `_DUMMY_HASH` before returning None — do not read it as a near-miss password match -> orchestrator/orchestrator/web_accounts.py:434.
11. Proxied request dies before any handler -> boundary gates: 403 `ROUTE_NOT_ALLOWED`, 401 `LOGIN_REQUIRED`, 403 `CSRF_FAILED`, 403 `PASSWORD_CHANGE_REQUIRED`, 403 `OWNER_ONLY` -> orchestrator/orchestrator/web_boundary.py:115-137.

## invariants
INVARIANT: an unknown username costs the same scrypt work as a known one — `verify_password(str(password), _DUMMY_HASH)` runs before returning None — orchestrator/orchestrator/web_accounts.py:434 [DERIVED].
INVARIANT: the session cookie is always `b64(json payload).b64(HMAC-SHA256(secret, body))`, and the CSRF token rides INSIDE the signed payload (`"c"`) so the header can be checked against it — orchestrator/orchestrator/web_accounts.py:463-468, 582-583 [DERIVED].
INVARIANT: `SESSION_COOKIE` is `httponly=True, secure=True, samesite="strict", path="/"`; `CSRF_COOKIE` is identical except `httponly=False` — orchestrator/orchestrator/api/web_auth.py:91-93 [DERIVED].
INVARIANT: login success clears only the user throttle key — `THROTTLE.succeeded(keys[:1])` — orchestrator/orchestrator/api/web_auth.py:113 [DERIVED].
INVARIANT: registry writes are all-or-nothing — exclusive flock, temp file mode `0o600`, fsync, `os.replace`, final `chmod 0o600`; readers see old or new, never half — orchestrator/orchestrator/web_accounts.py:107-123; orchestrator/orchestrator/mcp_principals.py:358-375 [DERIVED].
INVARIANT: the registry cache serves a doc only while `(path, mtime_ns, ino, size)` is unchanged — orchestrator/orchestrator/web_scope.py:54-64 [DERIVED].
INVARIANT: friend sign-in requires an `_active` record — `enabled is True`, no `revoked_at`, expiry in the future; an unreadable expiry is an expired one — orchestrator/orchestrator/mcp_principals.py:227-239 [DERIVED].
INVARIANT: setting the owner password always increments `session_version` (`int(old or 0) + 1`) — orchestrator/orchestrator/web_accounts.py:190 [DERIVED].

## VERIFY
```verify
grep -Fq 'POLYMATH_WEB_SESSION_SECRET' orchestrator/orchestrator/web_accounts.py
grep -Fq 'too many failed sign-ins; wait 15 minutes' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'samesite="strict"' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'must be owner-only (chmod 600)' orchestrator/orchestrator/web_scope.py
grep -Fq 'set the owner password on the server itself' orchestrator/orchestrator/api/web_auth.py
test "$(grep -c -F 'hashlib.scrypt' orchestrator/orchestrator/web_accounts.py)" -ge 2
! grep -Fq 'POLYMATH_WEB_SESSION_SECRET' orchestrator/orchestrator/api/web_auth.py
```
