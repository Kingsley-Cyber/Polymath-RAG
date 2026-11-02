# flow: web-sign-in
Website sign-in and the web boundary: POST /auth/login, the session and CSRF cookies, every later proxied request classified public / user / write / owner, the owner's password set on the server itself.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Proxied browser request hits `WebBoundaryMiddleware`; `classify(method, path)` returns the class (`"public"` for /auth/login); PUBLIC/CAPABILITY classes skip session+CSRF | orchestrator/orchestrator/web_boundary.py:90-94, 174 [DERIVED] | method+path -> class or None | proxied path with no RULES match -> 403 ROUTE_NOT_ALLOWED (fail closed) |
| 2 | Direct (non-proxied) request with non-loopback Host is refused before any route (DNS-rebinding block) | orchestrator/orchestrator/web_boundary.py:155-162 [DERIVED] | Host header -> 403 | 403 NON_LOOPBACK_HOST / websocket close 1008 |
| 3 | `login()` calls `REGISTRY.get()`; `RegistryCache` stats the file at `POLYMATH_MCP_PRINCIPALS_FILE`, re-reads only when `(str(path), st_mtime_ns, st_ino, st_size)` changed | orchestrator/orchestrator/web_scope.py:46-64; orchestrator/orchestrator/web_accounts.py:101-103 [DERIVED] | env path -> registry doc or None | mode `st.st_mode & 0o077` -> ValueError "must be owner-only (chmod 600)" -> doc None |
| 4 | `P.read_registry(path)` parses JSON, requires `schema == SCHEMA` and `principals` list | orchestrator/orchestrator/mcp_principals.py:360-366 [DERIVED] | file bytes -> dict | OSError/ValueError -> `self._doc = None`, `last_error` set (web_scope.py:61-62) |
| 5 | `login()` preconditions: doc non-None and `W.session_secret()` non-None | orchestrator/orchestrator/api/web_auth.py:100-102; orchestrator/orchestrator/web_accounts.py:458-460 [DERIVED] | — -> continue | 503 LOGIN_NOT_CONFIGURED ("web logins are not configured on this server") |
| 6 | Throttle gate: keys `[f"user:{body.username.strip().lower()}", f"addr:{client_address(request)}"]` | orchestrator/orchestrator/api/web_auth.py:103-105 [DERIVED] | username + client IP -> allowed bool | 429 TOO_MANY_ATTEMPTS ("too many failed sign-ins; wait 15 minutes") |
| 7 | `client_address` picks the throttling IP: `cf-connecting-ip` header, then first `x-forwarded-for` hop, then `request.client.host`, else `"unknown"` | orchestrator/orchestrator/api/web_auth.py:61-69 [DERIVED] | headers -> IP string | spoofable `x-forwarded-for` when no Cloudflare edge (first hop wins) |
| 8 | `W.authenticate_password(doc, username, password)` -> `_identity(doc, username)`: owner branch when `name == OWNER_USERNAME` and `owner_web.username` matches; else friend found by `rec["web"]["username"]` via `_friend` | orchestrator/orchestrator/web_accounts.py:406-421, 160-165 [DERIVED] | doc + username -> (WebIdentity, stored hash) or None | AccountError in `_friend` or no match -> None |
| 9 | Friend records must be ACTIVE: `_active` requires `enabled is True`, no `revoked_at`, `now < expires_at`; unreadable expiry = expired (fail closed) | orchestrator/orchestrator/mcp_principals.py:238-250 [DERIVED] | record + now -> bool | inactive/expired friend -> None -> BAD_LOGIN |
| 10 | Unknown user: `verify_password(str(password), _DUMMY_HASH)` burns the same scrypt work — no timing oracle | orchestrator/orchestrator/web_accounts.py:431-435 [DERIVED] | password -> None | always None; throttle still counts the failure |
| 11 | `verify_password` parses `scrypt$n$r$p$salt$digest`, recomputes scrypt with the stored params, `hmac.compare_digest` | orchestrator/orchestrator/web_accounts.py:88-97, 578-579 [DERIVED] | password + stored hash -> bool | wrong kind/malformed hash -> False (ValueError caught) |
| 12 | Failure branch: username == `W.OWNER_USERNAME` and `not owner_password_set(doc)` (no `owner_web.password_hash`) -> 409 OWNER_PASSWORD_NOT_SET, no throttle count; otherwise `THROTTLE.failed(keys)` + 401 BAD_LOGIN | orchestrator/orchestrator/api/web_auth.py:107-112, 37-38 [DERIVED] | — -> 409 or 401 | 409 tells the owner to set the password in Polymath on the Mac |
| 13 | Success: `THROTTLE.succeeded(keys[:1])` clears only the user key, not the addr key | orchestrator/orchestrator/api/web_auth.py:113 [DERIVED] | keys -> reset | [INFERRED] the address failure count from `keys[1]` is never reset on success |
| 14 | `W.make_session(secret, ident)`: `csrf = secrets.token_urlsafe(24)`; payload `{"p": principal_id, "v": session_version, "e": now+ttl, "c": csrf}`; cookie = `b64(payload).b64(HMAC-SHA256)` | orchestrator/orchestrator/web_accounts.py:463-468, 582-583, 574-575 [DERIVED] | secret + ident -> (cookie, csrf) | secret None -> 503 LOGIN_NOT_CONFIGURED in `_with_session` (web_auth.py:88-90) |
| 15 | `_with_session` sets `SESSION_COOKIE` (httponly=True, secure=True, samesite="strict", path="/", max_age=SESSION_TTL_S) and `CSRF_COOKIE` (httponly=False, readable by JS for the header), `cache-control: no-store` | orchestrator/orchestrator/api/web_auth.py:87-95 [DERIVED] | response -> response + 2 cookies | — |
| 16 | 200 body `me_payload(ident)`: username, display_name, is_owner, must_change_password, principal_id, `local: False` | orchestrator/orchestrator/api/web_auth.py:114, 72-80 [DERIVED] | ident -> JSON payload | — |
| 17 | Later proxied request (GET /auth/me): boundary sees proxy headers (`x-forwarded-for`, `forwarded`, `x-forwarded-host`), classifies (e.g. "user"), reads the session cookie, `read_session` + `resolve_session`, and for non-safe methods requires `csrf_ok` | orchestrator/orchestrator/web_boundary.py:30, 97-98, 175-189; orchestrator/orchestrator/web_accounts.py:471-500 [DERIVED] | cookies + headers -> WebIdentity or refusal | no/invalid session -> 302 sign-in or 401/403; bad CSRF header -> 403 CSRF_FAILED |
| 18 | Boundary stores `scope["state"]["web_identity"] = ident` and appends the principal header ONLY when `not ident.is_owner`; scope copied, never mutated in place; incoming principal header always dropped | orchestrator/orchestrator/web_boundary.py:168, 196-200 [DERIVED] | scope -> narrowed scope | a browser-supplied principal header can never impersonate |
| 19 | Identity with `must_change_password` may touch only the 3 paths in `PASSWORD_CHANGE_OK` | orchestrator/orchestrator/web_boundary.py:42, 190-192 [DERIVED] | path -> allow/refuse | anything else -> refused until password changed |
| 20 | `me()` reads `identity(request)` = `request.state.web_identity`; a direct loopback caller has ident None -> `me_payload(None, local=True)` returns the owner payload (username OWNER_USERNAME, display_name "King", is_owner True) | orchestrator/orchestrator/api/web_auth.py:157-161, 83-84, 72-77 [DERIVED] | request -> JSON, no-store | — |
| 21 | POST /auth/owner-password (server itself, http://127.0.0.1:7200): refused when `proxied(headers)` or `principal_context.current()` | orchestrator/orchestrator/api/web_auth.py:169-176; orchestrator/orchestrator/web_boundary.py:97-98; shared/polymath_shared/principal_context.py:23-25 [DERIVED] | headers + context -> 403 or continue | 403 LOCAL_ONLY ("set the owner password on the server itself") |
| 22 | `W.registry_path()` None -> 503; `password_problem(body.password)` -> 422 WEAK_PASSWORD (only an empty/too-short password is refused, owner's rule 2026-09-27) | orchestrator/orchestrator/api/web_auth.py:177-182; orchestrator/orchestrator/web_accounts.py:74-78, 101-103 [DERIVED] | — | 503 ACCOUNTS_NOT_CONFIGURED ("POLYMATH_MCP_PRINCIPALS_FILE is not set on this server") / 422 |
| 23 | `W.set_owner_password(path, password)`: `_new_web` hashes with scrypt (salt 16 bytes, `session_version` 1, must_change False), sets display_name "King", bumps `session_version = old + 1` | orchestrator/orchestrator/web_accounts.py:185-192, 177-182, 81-85 [DERIVED] | path + password -> new owner_web | AccountError("WEAK_PASSWORD") from `_new_web` |
| 24 | `update_registry`: under `flock` on `.{name}.lock` (0o600) -> `read_registry` -> change -> `P.write_registry` (validates every record via `principal_from_record`, temp `.{name}.{pid}.tmp` 0o600 O_EXCL, fsync, `os.replace`, chmod 0600) | orchestrator/orchestrator/web_accounts.py:118-123, 107-115; orchestrator/orchestrator/mcp_principals.py:369-386 [DERIVED] | doc -> file on disk | a reader sees old or new, never half; bad record -> validation error aborts the write |

## state written
- principals registry JSON (path from `POLYMATH_MCP_PRINCIPALS_FILE`): `owner_web` = `{username: OWNER_USERNAME, password_hash: "scrypt$...", password_changed_at, session_version: old+1, must_change_password: False, display_name: "King"}` — orchestrator/orchestrator/web_accounts.py:185-192, 181 [DERIVED]
- lock file `.{name}.lock`, created 0o600, exclusive flock held during the update — orchestrator/orchestrator/web_accounts.py:107-115 [DERIVED]
- temp file `.{name}.{pid}.tmp` 0o600, fsynced then `os.replace`d onto the registry, unlinked if it survives — orchestrator/orchestrator/mcp_principals.py:374-385 [DERIVED]
- client cookies `W.SESSION_COOKIE` (httponly) and `W.CSRF_COOKIE` (readable), `max_age=W.SESSION_TTL_S` — orchestrator/orchestrator/api/web_auth.py:92-93; deleted by logout at 148-153 [DERIVED]
- Postgres tables: none; Qdrant collections: none — orchestrator/orchestrator/mcp_principals.py:1-31 ("no network, no database") [DERIVED]

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_WEB_SESSION_SECRET` | `""` | shorter than 32 chars -> `session_secret()` returns None -> 503 LOGIN_NOT_CONFIGURED at login and in `_with_session` | orchestrator/orchestrator/web_accounts.py:458-460 |
| `POLYMATH_MCP_PRINCIPALS_FILE` | `""` | unset -> `registry_path()` None -> `REGISTRY.get()` None -> 503 at login; 503 ACCOUNTS_NOT_CONFIGURED at /auth/owner-password | orchestrator/orchestrator/web_accounts.py:101-103; orchestrator/orchestrator/web_scope.py:47-49 |
| `POLYMATH_WEB_SIGNUPS` | `"0"` | no effect on this flow — gates POST /auth/register only (truthy set `("1", "true", "yes", "on")`) | orchestrator/orchestrator/api/web_auth.py:31-34 |

## failure modes
1. Every login returns 503 LOGIN_NOT_CONFIGURED -> `session_secret()` None (secret unset or < 32 chars) or registry doc None -> check `POLYMATH_WEB_SESSION_SECRET` length and `REGISTRY.last_error` — orchestrator/orchestrator/api/web_auth.py:100-102; orchestrator/orchestrator/web_accounts.py:458-460; orchestrator/orchestrator/web_scope.py:61-62.
2. Silent fallback: registry file missing (`stat` OSError) returns `{"schema": P.SCHEMA, "principals": []}`, NOT an error — every credential then fails as 401 BAD_LOGIN with no 503 — orchestrator/orchestrator/web_scope.py:51-53.
3. All logins 503 after a registry copy -> file mode has group/other bits (`st.st_mode & 0o077`) -> treated as invalid, doc None; fix with chmod 600 — orchestrator/orchestrator/web_scope.py:58-59.
4. 429 TOO_MANY_ATTEMPTS for a correct password -> throttle (LoginThrottle limit=5, window_s=900) counted failures on the `addr:` key; success resets only the `user:` key (`keys[:1]`) — orchestrator/orchestrator/api/web_auth.py:103-105, 113; orchestrator/orchestrator/web_accounts.py:504-532.
5. Owner sign-in fails with 409 OWNER_PASSWORD_NOT_SET and no throttle count -> `owner_web.password_hash` absent -> set it via POST /auth/owner-password on the server itself (loopback only) — orchestrator/orchestrator/api/web_auth.py:107-110, 169-184.
6. Correct friend password still 401 -> record inactive: `enabled` not True, `revoked_at` set, or expired; an unreadable `expires_at` counts as expired (fail closed) — orchestrator/orchestrator/mcp_principals.py:238-250.
7. 403 LOCAL_ONLY setting the owner password -> request arrived with a proxy header (`proxied()`) or inside a principal context; must come from http://127.0.0.1:7200 directly — orchestrator/orchestrator/api/web_auth.py:173-176; orchestrator/orchestrator/web_boundary.py:97-98.
8. 422 WEAK_PASSWORD -> password below `MIN_PASSWORD`/empty; any non-empty password of sufficient length is accepted (owner's rule, 2026-09-27) — orchestrator/orchestrator/web_accounts.py:74-78.
9. Proxied POST rejected 403 CSRF_FAILED -> non-safe method without a CSRF header matching the `c` token inside the signed session — orchestrator/orchestrator/web_boundary.py:31, 187-189.
10. New route unreachable through the proxy (403 ROUTE_NOT_ALLOWED) -> `classify` returns None (no RULES match); fail closed by design — orchestrator/orchestrator/web_boundary.py:90-94, 170-173.
11. Friend locked out of everything but password change -> identity has `must_change_password` and the path is outside `PASSWORD_CHANGE_OK` — orchestrator/orchestrator/web_boundary.py:42, 190-192.
12. Old sessions stop working after an owner-password set -> `session_version` bumped to `old + 1`, and the session payload carries `"v"` — orchestrator/orchestrator/web_accounts.py:190, 195, 465-466.

## invariants
INVARIANT: `session_secret()` returns bytes only when the env value is >= 32 chars — orchestrator/orchestrator/web_accounts.py:458-460 [DERIVED]
  fails-if: every login and session issue refuses 503 LOGIN_NOT_CONFIGURED.
INVARIANT: session cookie is `httponly=True, secure=True, samesite="strict", path="/"`; CSRF cookie is readable (`httponly=False`) and its token rides INSIDE the signed session — orchestrator/orchestrator/api/web_auth.py:91-93; orchestrator/orchestrator/web_accounts.py:463-464 [DERIVED]
  fails-if: a script-readable session cookie or a CSRF token not bound to the session.
INVARIANT: unknown usernames cost the same scrypt work (`verify_password(str(password), _DUMMY_HASH)`) — orchestrator/orchestrator/web_accounts.py:434 [DERIVED]
  fails-if: username enumeration via response timing.
INVARIANT: registry file must have `st.st_mode & 0o077 == 0` (chmod 600) or the whole registry is treated as absent — orchestrator/orchestrator/web_scope.py:58-59 [DERIVED]
  fails-if: fail closed — no principal authenticates.
INVARIANT: registry writes are atomic: temp file 0o600 O_EXCL, fsync, `os.replace`, then `os.chmod(path, 0o600)`; every record re-validated first — orchestrator/orchestrator/mcp_principals.py:369-386 [DERIVED]
  fails-if: a reader could see a half-written registry.
INVARIANT: principal header appended iff `not ident.is_owner`; an incoming one is always dropped — orchestrator/orchestrator/web_boundary.py:168, 196-197 [DERIVED]
  fails-if: a browser-supplied header could impersonate any principal.
INVARIANT: an unreadable `expires_at` is an expired one (fail closed) — orchestrator/orchestrator/mcp_principals.py:245-246 [DERIVED]
INVARIANT: password hashes are self-describing `scrypt$n$r$p$salt$digest` and verified with `hmac.compare_digest` — orchestrator/orchestrator/web_accounts.py:88-97 [DERIVED]

## VERIFY
```verify
grep -Fq 'POLYMATH_WEB_SESSION_SECRET' orchestrator/orchestrator/web_accounts.py
grep -Fq 'too many failed sign-ins; wait 15 minutes' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'must be owner-only (chmod 600)' orchestrator/orchestrator/web_scope.py
grep -Fq 'the same work for an unknown user: no timing oracle' orchestrator/orchestrator/web_accounts.py
grep -Fq 'os.replace(tmp, path)' orchestrator/orchestrator/mcp_principals.py
grep -Fq 'cf-connecting-ip' orchestrator/orchestrator/api/web_auth.py
grep -Fq 'OWNER_PASSWORD_NOT_SET' orchestrator/orchestrator/api/web_auth.py
test "$(grep -c -F 'set_cookie' orchestrator/orchestrator/api/web_auth.py)" -ge 2
```
