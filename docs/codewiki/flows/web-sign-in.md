# flow: web-sign-in
Website sign-in and the web boundary: POST /auth/login, the session and CSRF cookies, every later proxied request classified public / user / write / owner, the owner's password set on the server itself.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /auth/login (boundary class: public, forwarded untouched) reaches `login`; it reads `REGISTRY.get()` | orchestrator/orchestrator/api/web_auth.py:99-100 | `LoginBody{username, password}` + Request -> registry doc or None | doc None handled at hop 4 |
| 2 | `RegistryCache.get()` resolves the registry path from env `POLYMATH_MCP_PRINCIPALS_FILE` | orchestrator/orchestrator/web_accounts.py:88-90 | env str -> `Path \| None` | env unset -> None |
| 3 | stat + cache key `(str(path), st_mtime_ns, st_ino, st_size)`; perms `st_mode & 0o077` -> ValueError -> doc None + `last_error`; else `read_registry` parses and checks schema | orchestrator/orchestrator/web_scope.py:33-51, orchestrator/orchestrator/mcp_principals.py:287-293 | Path -> doc dict or None | stat OSError -> silent empty `{"schema": P.SCHEMA, "principals": []}`; bad schema -> ValueError |
| 4 | gate: `doc is None or W.session_secret() is None` -> 503 `LOGIN_NOT_CONFIGURED` | orchestrator/orchestrator/api/web_auth.py:101-102, orchestrator/orchestrator/web_accounts.py:374-376 | — | 503 (secret env < 32 chars also triggers) |
| 5 | throttle keys `["user:{name}", "addr:{ip}"]`; `client_address`: `cf-connecting-ip` -> first `x-forwarded-for` hop -> `request.client.host` -> `"unknown"` | orchestrator/orchestrator/api/web_auth.py:103-105, 61-69 | headers -> str | 429 `TOO_MANY_ATTEMPTS` "too many failed sign-ins; wait 15 minutes" |
| 6 | `authenticate_password` -> `_identity`: `name == OWNER_USERNAME and web.get("username") == OWNER_USERNAME` -> owner `WebIdentity` + stored hash | orchestrator/orchestrator/web_accounts.py:347-353, 322-328, 143-145 | (doc, username) -> (WebIdentity, hash) or None | no owner_web -> falls to friend branch |
| 7 | friend branch: `_friend` scans `doc["principals"]` for `web.username` match; record must pass `P._active` (`enabled is True`, no `revoked_at`, `expires_at` in future; unreadable expiry = expired) | orchestrator/orchestrator/web_accounts.py:330-334, 135-140, orchestrator/orchestrator/mcp_principals.py:165-177 | doc + name -> record or None | inactive/expired -> None |
| 8 | unknown/inactive name: `verify_password(str(password), _DUMMY_HASH)` — "the same work for an unknown user: no timing oracle" — then None | orchestrator/orchestrator/web_accounts.py:349-351 | password -> None | returns None, cost paid |
| 9 | known name: `verify_password` — format `scrypt$n$r$p$salt$digest`, recomputed via `hashlib.scrypt`, compared with `hmac.compare_digest` | orchestrator/orchestrator/web_accounts.py:75-84, 129-139 | password + stored -> bool | parse error or mismatch -> False -> None |
| 10 | `ident is None` + username == `W.OWNER_USERNAME` + `not owner_password_set(doc)` -> 409 `OWNER_PASSWORD_NOT_SET` (no throttle count) | orchestrator/orchestrator/api/web_auth.py:107-110, 37-38 | — | 409 |
| 11 | otherwise `THROTTLE.failed(keys)` + 401 `BAD_LOGIN` | orchestrator/orchestrator/api/web_auth.py:111-117 | — | 401; counters incremented |
| 12 | success: `THROTTLE.succeeded(keys[:1])` clears only the user key; body = `me_payload(ident)` | orchestrator/orchestrator/api/web_auth.py:113-114, 72-80 | ident -> JSON payload | — |
| 13 | `_with_session` -> `make_session`: `csrf = secrets.token_urlsafe(24)`; payload `{"p": principal_id, "v": session_version, "e": expiry, "c": csrf}`; cookie = `_b64(json) + "." + _b64(HMAC-SHA256(secret, body))` | orchestrator/orchestrator/api/web_auth.py:87-95, orchestrator/orchestrator/web_accounts.py:379-384, 498-499, 490-491 | secret + ident -> (cookie, csrf) | secret None -> 503 `LOGIN_NOT_CONFIGURED` |
| 14 | cookies set: `SESSION_COOKIE` `httponly=True, secure=True, samesite="strict", path="/"`, `max_age=W.SESSION_TTL_S`; `CSRF_COOKIE` `httponly=False`; `cache-control: no-store` | orchestrator/orchestrator/api/web_auth.py:91-94 | — | — |
| 15 | later proxied request: `WebBoundaryMiddleware` strips any incoming principal header; `proxied(headers)` true iff any of `x-forwarded-for` / `forwarded` / `x-forwarded-host` present | orchestrator/orchestrator/web_boundary.py:104-141, 70-71, 21 | ASGI scope -> gate decision | non-http/websocket or not proxied: pass-through |
| 16 | `classify(method, path)` first-match table -> one of `"public"`, `"user"`, `"write"`, `"owner"` or None; public -> forwarded | orchestrator/orchestrator/web_boundary.py:63-67, 23, 117 | method+path -> class | unmatched -> None |
| 17 | non-public gates: `W.session_secret()` and `REGISTRY.get()` non-None; valid session; CSRF header when method not in SAFE_METHODS; `not ident.must_change_password or path in PASSWORD_CHANGE_OK`; class `OWNER` requires `ident.is_owner` | orchestrator/orchestrator/web_boundary.py:118-135 | scope -> allow/refuse | refused at boundary (503 when unconfigured, session/CSRF/owner failures) |
| 18 | pass-through: non-owner gets `principal_context.HEADER` appended with `ident.principal_id`; `scope["state"]["web_identity"] = ident`; headers replaced | orchestrator/orchestrator/web_boundary.py:136-140 | ident -> downstream state | — |
| 19 | GET /auth/me (class: user): `identity(request)` = `request.state.web_identity`; `me_payload(ident, local=ident is None)`; no identity (direct loopback caller) -> owner payload `"display_name": "King"`, `is_owner: True`, `web_password_set` from registry; `cache-control: no-store` | orchestrator/orchestrator/api/web_auth.py:157-161, 83-84, 72-80 | request -> JSON | — |
| 20 | POST /auth/owner-password (class: owner): refused when `proxied(request.scope headers)` or `principal_context.current()` -> 403 `LOCAL_ONLY` "set the owner password on the server itself" | orchestrator/orchestrator/api/web_auth.py:169-176, orchestrator/orchestrator/web_boundary.py:70-71, shared/polymath_shared/principal_context.py:23-25 | headers + context -> gate | 403 |
| 21 | `W.registry_path()` None -> 503 `ACCOUNTS_NOT_CONFIGURED`; `W.password_problem(body.password)` -> 422 `WEAK_PASSWORD` ("a password cannot be empty"; only emptiness refused — owner's rule 2026-09-27) | orchestrator/orchestrator/api/web_auth.py:177-182, orchestrator/orchestrator/web_accounts.py:61-65 | — | 503 / 422 |
| 22 | `W.set_owner_password(path, password)`: `_new_web` builds `{username, password_hash, password_changed_at, session_version: 1, must_change_password: False}` via `hash_password` (scrypt, salt `token_bytes(16)`); `display_name` kept; `session_version = old + 1` | orchestrator/orchestrator/web_accounts.py:160-167, 152-157, 68-72 | path + password -> doc["owner_web"] | — |
| 23 | `update_registry`: under `_locked` (flock on `.{name}.lock`, mode 0o600) read -> change -> `write_registry` (records validated, temp file 0o600 + `os.replace` + `chmod(path, 0o600)`) | orchestrator/orchestrator/web_accounts.py:105-110, 94-102, orchestrator/orchestrator/mcp_principals.py:296-313 | doc -> file | invalid record -> ValueError |
| 24 | response `{"owner_password": "set", "username": W.OWNER_USERNAME}` | orchestrator/orchestrator/api/web_auth.py:184 | — | — |

## state written
- principals registry JSON file (`POLYMATH_MCP_PRINCIPALS_FILE`): `owner_web` = `{username, password_hash (scrypt), password_changed_at, session_version = old + 1, must_change_password: False, display_name}` — orchestrator/orchestrator/web_accounts.py:152-157, 160-167.
- written atomically: temp file mode `0o600`, `os.replace`, `os.chmod(path, 0o600)` — orchestrator/orchestrator/mcp_principals.py:296-313.
- lock file `.{path.name}.lock` created mode `0o600`, flock held during update — orchestrator/orchestrator/web_accounts.py:94-102.
- client cookies `SESSION_COOKIE` (httponly) and `CSRF_COOKIE` (readable) on the login response — orchestrator/orchestrator/api/web_auth.py:91-93.
- no Postgres/Qdrant on this path (policy + file store only) — orchestrator/orchestrator/mcp_principals.py:15.

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_MCP_PRINCIPALS_FILE` | `''` | path of the principals registry; unset -> `registry_path()` None -> login 503 `LOGIN_NOT_CONFIGURED`, owner-password 503 `ACCOUNTS_NOT_CONFIGURED` | orchestrator/orchestrator/web_accounts.py:88-90, orchestrator/orchestrator/api/web_auth.py:101-102, 177-179 |
| `POLYMATH_WEB_SESSION_SECRET` | `''` | `raw.encode()` only when `len(raw) >= 32`, else None -> login and session minting refuse 503 | orchestrator/orchestrator/web_accounts.py:374-376, orchestrator/orchestrator/api/web_auth.py:88-90 |

## failure modes
1. Login always 503 `LOGIN_NOT_CONFIGURED` despite file existing -> registry has group/other bits (`st_mode & 0o077` -> ValueError -> doc None) or secret env shorter than 32 chars -> web_scope.py:44-48, web_accounts.py:374-376, web_auth.py:101-102.
2. 429 `TOO_MANY_ATTEMPTS` -> more than 5 failures on the `user:` or `addr:` key inside the 900 s window ("wait 15 minutes"); success clears only the user key (`keys[:1]`) -> web_auth.py:103-105, 113; throttle params web_accounts.py:420-448.
3. 409 `OWNER_PASSWORD_NOT_SET` -> owner username typed but `owner_web.password_hash` absent; fix is POST /auth/owner-password on the server itself -> web_auth.py:108-110, 37-38.
4. 401 `BAD_LOGIN` for a real friend -> account not active: `enabled is not True`, `revoked_at` set, or `expires_at` passed/unreadable (fail closed) -> web_accounts.py:322-337, mcp_principals.py:163-176.
5. Silent fallback: registry stat `OSError` -> `REGISTRY.get()` returns `{"schema": P.SCHEMA, "principals": []}` — every login fails 401, no error surfaced -> web_scope.py:37-40.
6. Silent fallback: a failed read is cached until `(st_mtime_ns, st_ino, st_size)` changes; an atomic `os.replace` (new inode) always refreshes -> web_scope.py:41-50, mcp_principals.py:309.
7. Proxied non-public request refused at the boundary -> missing/invalid session, missing CSRF header on a non-safe method, `must_change_password` outside `PASSWORD_CHANGE_OK`, or non-owner hitting an OWNER-class path -> web_boundary.py:118-135.
8. `set_owner_password` 403 `LOCAL_ONLY` -> request arrived through the proxy (any of `x-forwarded-for`/`forwarded`/`x-forwarded-host` present) or a principal context is active -> web_auth.py:173-176, web_boundary.py:70-71.
9. `set_owner_password` 503 `ACCOUNTS_NOT_CONFIGURED` -> `POLYMATH_MCP_PRINCIPALS_FILE` unset on the server -> web_auth.py:177-179.
10. 422 `WEAK_PASSWORD` -> body.password below `MIN_PASSWORD` (empty); "Any password the person chooses is accepted; only nothing at all is refused" -> web_auth.py:180-182, web_accounts.py:61-65.

## invariants
- INVARIANT: an unknown username pays identical scrypt work against `_DUMMY_HASH` — no timing oracle — web_accounts.py:350 [DERIVED]; fails-if: username enumeration by response latency.
- INVARIANT: the CSRF token rides INSIDE the signed session payload key `"c"`, so the header can be checked against it — web_accounts.py:380-382 [DERIVED]; fails-if: CSRF check becomes forgeable.
- INVARIANT: session cookie `httponly=True, secure=True, samesite="strict", path="/"`, CSRF cookie `httponly=False` — web_auth.py:91-92 [DERIVED].
- INVARIANT: `session_secret()` returns None when the env value is shorter than 32 chars — web_accounts.py:375-376 [DERIVED]; fails-if: short-key HMAC signing.
- INVARIANT: digest comparison uses `hmac.compare_digest` — web_accounts.py:139 [DERIVED].
- INVARIANT: registry writes are atomic (temp 0o600 + `os.replace` + chmod 0600); "A reader sees old or new, never half" — mcp_principals.py:297-313 [DERIVED].
- INVARIANT: a registry file with any group/other permission bit is rejected — web_scope.py:34-35 [DERIVED].
- INVARIANT: "an unreadable expiry is an expired one (fail closed)" — mcp_principals.py:171 [DERIVED].
- INVARIANT: setting the owner password bumps `session_version = old + 1` — web_accounts.py:165 [DERIVED]; effect: previously issued cookies carry a stale `"v"` (payload key at web_accounts.py:382), so they stop matching the registry [INFERRED].

## VERIFY
```verify
grep -Fq 'LOGIN_NOT_CONFIGURED' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'cf-connecting-ip' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'POLYMATH_WEB_SESSION_SECRET' orchestrator/orchestrator/web_accounts.py
grep -Fq 'must be owner-only (chmod 600)' orchestrator/orchestrator/web_scope.py
grep -Fq 'token_urlsafe(24)' orchestrator/orchestrator/web_accounts.py
grep -Eq 'hmac[.]compare_digest' orchestrator/orchestrator/web_accounts.py
test "$(grep -c -F 'raise _refuse' orchestrator/orchestrator/api/web_auth.py)" -ge 7
```
