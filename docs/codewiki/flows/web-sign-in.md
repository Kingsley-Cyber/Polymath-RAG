# flow: web-sign-in
Website sign-in and the web boundary: POST /auth/login, the session and CSRF cookies, every later proxied request classified public / user / write / owner, the owner's password set on the server itself.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Proxied request enters `WebBoundaryMiddleware`; non-http/websocket scopes or non-proxied callers pass through untouched, no identity attached | web_boundary.py:104-107 [DERIVED] | ASGI scope -> scope | loopback caller gets no `web_identity` |
| 2 | Any incoming principal header is stripped, then method+path classified first-match via RULES | web_boundary.py:111,113 [DERIVED] | (method, path) -> "public"/"user"/"write"/"owner" or None | unmatched path -> class None |
| 3 | POST /auth/login is class public: forwarded untouched, no session or CSRF required | web_boundary.py:117 [DERIVED] | request -> `login()` | — |
| 4 | `login()` preconditions: `REGISTRY.get()` non-None and `session_secret()` non-None | web_auth.py:99-105 [DERIVED] | registry doc + env secret -> gate | either None -> 503 `LOGIN_NOT_CONFIGURED` |
| 5 | `RegistryCache.get()`: stat key `(str(path), st_mtime_ns, st_ino, st_size)`; `st.st_mode & 0o077` -> ValueError; stat OSError -> empty doc `{"schema": P.SCHEMA, "principals": []}` | web_scope.py:33-51 [DERIVED] | file -> doc, None, or empty doc | parse/permission errors swallowed into doc None + `last_error`; missing file silently becomes an EMPTY doc |
| 6 | `session_secret()` reads env `POLYMATH_WEB_SESSION_SECRET`; `< 32` chars -> None | web_accounts.py:374-376 [DERIVED] | env str -> bytes or None | short/missing secret -> 503 at hop 4 |
| 7 | Throttle gate on keys `[f"user:{username.strip().lower()}", f"addr:{client_address(request)}"]` | web_auth.py:103-105 [DERIVED] | username + client addr -> allow/deny | denied -> 429 `TOO_MANY_ATTEMPTS` "wait 15 minutes" |
| 8 | `client_address`: `cf-connecting-ip` -> first `x-forwarded-for` hop -> socket peer -> `"unknown"` | web_auth.py:61-69 [DERIVED] | request headers -> addr str | no headers -> `"unknown"` |
| 9 | `authenticate_password` -> `_identity`: owner branch when name == `OWNER_USERNAME` and `owner_web.username` matches; else `_friend` lookup + `P._active` (enabled is True, no `revoked_at`, not expired) | web_accounts.py:347-353, 322-337, 135-140 [DERIVED]; mcp_principals.py:160-172 [DERIVED] | (doc, username) -> (WebIdentity, stored hash) or None | inactive/revoked/expired friend -> None |
| 10 | Unknown user: `verify_password(str(password), _DUMMY_HASH)` — identical work, then return None | web_accounts.py:350 [DERIVED] | password -> None | no timing oracle on usernames |
| 11 | `verify_password`: only kind `"scrypt"`; split `"scrypt$n$r$p$salt$digest"`, recompute scrypt, `hmac.compare_digest` | web_accounts.py:75-84 [DERIVED] | (password, stored) -> bool | wrong kind or malformed stored string -> False |
| 12 | Failed login: username == `OWNER_USERNAME` and `not owner_password_set(doc)` (no `owner_web.password_hash`) -> 409 `OWNER_PASSWORD_NOT_SET` with no throttle count; otherwise `THROTTLE.failed(keys)` + 401 `BAD_LOGIN` | web_auth.py:107-112, 37-38 [DERIVED] | — | both throttle keys (user AND addr) incremented |
| 13 | Success: `THROTTLE.succeeded(keys[:1])` — clears only the user key | web_auth.py:113 [DERIVED] | — | addr-key failures from earlier attempts persist [INFERRED: only `keys[:1]` is passed] |
| 14 | Response body built by `me_payload(ident)` | web_auth.py:114, 72-80 [DERIVED] | WebIdentity -> {username, display_name, is_owner, must_change_password, principal_id, web_password_set?} | — |
| 15 | `_with_session` -> `make_session`: `csrf = secrets.token_urlsafe(24)`; payload `{"p": principal_id, "v": session_version, "e": expiry, "c": csrf}`; cookie = `b64(json).b64(HMAC-SHA256(secret, body))` | web_auth.py:87-95; web_accounts.py:379-384, 498-499 [DERIVED] | (secret, ident) -> (cookie value, csrf) | secret None -> 503 (redundant re-check) |
| 16 | Cookies set: `SESSION_COOKIE` httponly=True secure strict, `CSRF_COOKIE` httponly=False (readable by JS), both `max_age=W.SESSION_TTL_S`, plus `cache-control: no-store` | web_auth.py:91-94 [DERIVED] | — | — |
| 17 | Later proxied class-user request (GET /auth/me): boundary requires secret + registry, a valid session, CSRF header when method not in SAFE_METHODS, and `not must_change_password or path in PASSWORD_CHANGE_OK`; class owner additionally requires `ident.is_owner` | web_boundary.py:118-135 [DERIVED] | session cookie -> verified ident | refused at the boundary before the route runs |
| 18 | Non-owner ident gets the principal header appended; `scope["state"]["web_identity"] = ident`; `me()` reads it via `identity(request)` | web_boundary.py:136-139 [DERIVED]; web_auth.py:157-161, 83-84 [DERIVED] | ident -> me payload | — |
| 19 | `me_payload(None)` fallback: a direct loopback caller (ident None) is reported as owner — username `OWNER_USERNAME`, display "King", `is_owner: True` | web_auth.py:72-77 [DERIVED] | None -> owner payload | silent: loopback needs no login |
| 20 | POST /auth/owner-password: refused when `proxied(headers)` (any of x-forwarded-for / forwarded / x-forwarded-host present) or `principal_context.current()` non-None -> 403 `LOCAL_ONLY` | web_auth.py:173-176 [DERIVED]; web_boundary.py:70-71 [DERIVED]; principal_context.py:23-25 [DERIVED] | headers + context -> refuse | even a signed-in owner through the proxy is refused |
| 21 | `registry_path()` None -> 503 `ACCOUNTS_NOT_CONFIGURED`; `password_problem(body.password)` non-empty -> 422 `WEAK_PASSWORD` (only an empty/too-short password is refused) | web_auth.py:177-182 [DERIVED]; web_accounts.py:88-90, 61-65 [DERIVED] | env + password -> gate | — |
| 22 | `W.set_owner_password`: `_new_web` builds {username, `password_hash` (scrypt), `password_changed_at`, `must_change_password: False`}, then `session_version = old + 1`, written to `doc["owner_web"]` | web_accounts.py:160-167, 152-157, 68-72 [DERIVED] | (path, password) -> new owner_web record | `_new_web` raises `AccountError("WEAK_PASSWORD", ...)` on empty |
| 23 | `update_registry`: `flock` on `.{name}.lock`, read_registry, change, `write_registry` — temp file mode 0600 in same dir, `os.replace`, final `os.chmod(path, 0o600)`; records validated by `principal_from_record` first | web_accounts.py:105-110, 94-102 [DERIVED]; mcp_principals.py:291-308 [DERIVED] | doc -> file | a reader sees old or new, never half |
| 24 | Response `{"owner_password": "set", "username": W.OWNER_USERNAME}` | web_auth.py:183-184 [DERIVED] | — | — |

## state written
- Principals registry JSON at `POLYMATH_MCP_PRINCIPALS_FILE`: `owner_web` = {username: `OWNER_USERNAME`, password_hash `"scrypt$n$r$p$s$d"` (salt `token_bytes(16)`), `password_changed_at` (`_now_iso`), `session_version`: old+1, `must_change_password`: False, `display_name`: "King"} — web_accounts.py:160-167, 152-157, 68-72, 148-149 [DERIVED].
- Same file written atomically (temp 0600 -> `os.replace` -> chmod 0600) under an exclusive `flock` on `.{name}.lock` — web_accounts.py:94-110; mcp_principals.py:291-308 [DERIVED].
- Client-side cookies on the login response: `SESSION_COOKIE` + `CSRF_COOKIE`, `max_age=W.SESSION_TTL_S`; the session itself is a signed payload, no server-side store — web_auth.py:91-93; web_accounts.py:379-384 [DERIVED].
- No Postgres or Qdrant writes on this flow — [INFERRED: no DB call appears anywhere in the traced chain].

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_WEB_SESSION_SECRET` | unset (`""`) | value `< 32` chars -> `session_secret()` None -> 503 `LOGIN_NOT_CONFIGURED` at login (web_auth.py:101-102), no session cookie ever issued, and the boundary refuses every non-public proxied class (web_boundary.py:118-120) | web_accounts.py:375 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | unset | unset -> `registry_path()` None -> `REGISTRY.get()` None -> 503 at login; 503 `ACCOUNTS_NOT_CONFIGURED` at owner-password (web_auth.py:177-179) | web_accounts.py:89 |

## failure modes
1. 503 `LOGIN_NOT_CONFIGURED` on POST /auth/login -> registry doc None (unreadable file, schema mismatch `read_registry` raises, or mode has group/other bits) or secret missing/short -> web_auth.py:101-102; real file error sits in `REGISTRY.last_error` (web_scope.py:48); secret at web_accounts.py:374-376.
2. Silent fallback: `RegistryCache` converts OSError/ValueError into doc None + `last_error`; the route surfaces only the 503 — web_scope.py:47-49.
3. Silent fallback: a MISSING registry file (stat OSError) yields an empty principals doc, not None, so login proceeds and fails as 401 `BAD_LOGIN` (owner name -> 409) instead of 503 — web_scope.py:38-40.
4. 409 `OWNER_PASSWORD_NOT_SET` -> owner username with no `owner_web.password_hash`; fix is POST /auth/owner-password on the server itself — web_auth.py:108-110, 37-38, 169-184.
5. 401 `BAD_LOGIN` -> wrong password or unknown username; unknown username still burns one scrypt verify against `_DUMMY_HASH` (expect uniform latency) — web_accounts.py:347-353, 350.
6. 429 `TOO_MANY_ATTEMPTS` -> throttle (limit=5, window_s=900 per unit page) per user key and per addr key; failures increment BOTH keys, success clears only `keys[:1]`, so an address ban outlives a later successful user login — web_auth.py:103-113; web_accounts.py:420-448.
7. 403 `LOCAL_ONLY` on /auth/owner-password -> proxy header present (x-forwarded-for / forwarded / x-forwarded-host) or a principal context is active — web_auth.py:175-176; web_boundary.py:70-71.
8. 422 `WEAK_PASSWORD` -> empty/short password only; any non-empty password accepted (owner rule dated 2026-09-27) — web_accounts.py:61-65.
9. Old owner web sessions stop validating after a password set -> `session_version` bumped to old+1 and the cookie payload carries `"v"` — web_accounts.py:165, 382 [INFERRED].
10. GET /auth/me returns "King"/`is_owner: True` with no login -> direct loopback caller has ident None — web_auth.py:72-77.

## invariants
- INVARIANT POST /auth/login is web class public: the boundary forwards it untouched, no session or CSRF required — web_boundary.py:117 [DERIVED].
- INVARIANT unknown username and wrong password cost the same verify work (`verify_password(str(password), _DUMMY_HASH)`) — no timing oracle — web_accounts.py:350 [DERIVED].
- INVARIANT password comparison is constant time: `hmac.compare_digest(got, want)` — web_accounts.py:139 [DERIVED].
- INVARIANT only kind `"scrypt"` stored hashes verify; anything else returns False — web_accounts.py:133-134 [DERIVED].
- INVARIANT the CSRF token rides INSIDE the signed session (`"c"` in the payload); the CSRF cookie is readable (httponly=False), the session cookie is not — web_accounts.py:380-382; web_auth.py:91-93 [DERIVED].
- INVARIANT the principals file must be owner-only: `st.st_mode & 0o077` -> refused — web_scope.py:44-46 [DERIVED].
- INVARIANT registry writes are atomic (temp file 0600 + `os.replace`, chmod 0600): a reader sees old or new, never half — mcp_principals.py:291-308 [DERIVED].
- INVARIANT friend login requires an ACTIVE principal: `enabled is not True` or `revoked_at` -> refused; unreadable `expires_at` counts as expired (fail closed) — mcp_principals.py:160-172, 171 [DERIVED].
- INVARIANT non-owner proxied identities travel onward as the principal header, never a client-supplied one (incoming principal header stripped first) — web_boundary.py:111, 136-137 [DERIVED].

## VERIFY
```verify
grep -Fq 'def login(body: LoginBody, request: Request) -> JSONResponse:' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'return raw.encode() if len(raw) >= 32 else None' orchestrator/orchestrator/web_accounts.py
grep -Fq 'verify_password(str(password), _DUMMY_HASH)' orchestrator/orchestrator/web_accounts.py
grep -Fq 'OWNER_PASSWORD_NOT_SET' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'st.st_mode & 0o077' orchestrator/orchestrator/web_scope.py
grep -Fq 'csrf = secrets.token_urlsafe(24)' orchestrator/orchestrator/web_accounts.py
grep -Fq 'web["session_version"] = int(old.get("session_version") or 0) + 1' orchestrator/orchestrator/web_accounts.py
grep -Fq 'os.replace(tmp, path)' orchestrator/orchestrator/mcp_principals.py
```
