# unit: orchestrator/orchestrator/web_boundary.py
anchor: orchestrator/orchestrator/web_boundary.py:1-201

## purpose
ASGI middleware that is the public web door's authorization point (proxy path rag.kingsleylab.xyz → Caddy → :7200), parallel to Server A's MCP door — orchestrator/orchestrator/web_boundary.py:1-9 [DERIVED].
For proxied requests it enforces session, CSRF, owner-only routes, password-change lock, and forwards a friend as a principal header so routes narrow to that friend's libraries; direct loopback callers (Server A, Hermes, workers, owner) pass through unchanged — orchestrator/orchestrator/web_boundary.py:4-9 [DERIVED].
Also blocks DNS rebinding: a direct request whose Host is not loopback is refused 403 before any route runs — orchestrator/orchestrator/web_boundary.py:11-17 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| classify | def | (method: str, path: str) -> str \| None | orchestrator/orchestrator/web_boundary.py:90-94 | file-level importers: orchestrator/orchestrator/main.py, orchestrator/orchestrator/api/web_auth.py |
| proxied | def | (headers) -> bool | orchestrator/orchestrator/web_boundary.py:97-98 | same file-level importers |
| cookie | def | (headers, name: str) -> str \| None | orchestrator/orchestrator/web_boundary.py:108-114 | same file-level importers |
| wants_html | def | (headers) -> bool | orchestrator/orchestrator/web_boundary.py:117-118 | same file-level importers |
| WebBoundaryMiddleware | class | \_\_init\_\_(app); \_\_call\_\_(scope, receive, send) | orchestrator/orchestrator/web_boundary.py:144-201 | same file-level importers |

## contracts

**classify(method, path)** — orchestrator/orchestrator/web_boundary.py:90-94
- in: `method` string (e.g. "GET"), `path` string (e.g. "/auth/me")
- out: one of "public" / "user" / "write" / "owner" / "capability", or None
- pre: RULES regexes compiled once at import — orchestrator/orchestrator/web_boundary.py:51
- post: FIRST matching rule wins; unmatched returns None — orchestrator/orchestrator/web_boundary.py:50, 92-94

**proxied(headers)** — orchestrator/orchestrator/web_boundary.py:97-98
- in: ASGI header list
- out: True iff any of `x-forwarded-for`, `forwarded`, `x-forwarded-host` present (case-insensitive via k.lower()) — orchestrator/orchestrator/web_boundary.py:30, 98

**cookie(headers, name)** — orchestrator/orchestrator/web_boundary.py:108-114
- out: cookie value or None; splits raw Cookie on ";" then first "=" — orchestrator/orchestrator/web_boundary.py:109-113

**WebBoundaryMiddleware.\_\_call\_\_(scope, receive, send)** — orchestrator/orchestrator/web_boundary.py:150-201
- in: ASGI scope/receive/send; non-http/websocket scopes pass through untouched — orchestrator/orchestrator/web_boundary.py:151-153
- pre: must sit OUTSIDE PrincipalContextMiddleware (the forwarded principal is what routes see) — orchestrator/orchestrator/web_boundary.py:145
- post (proxied, class not PUBLIC/CAPABILITY): `scope["state"]["web_identity"] = ident` — orchestrator/orchestrator/web_boundary.py:199; principal header appended iff `not ident.is_owner` — orchestrator/orchestrator/web_boundary.py:196-197; scope copied, never mutated in place — orchestrator/orchestrator/web_boundary.py:198, 200

## effect surface
- Postgres tables read/written: none (FACTS `tables_read` / `tables_written` empty)
- Qdrant / files / subprocess / env flags: none in this file (imports are json, re, urllib.parse.quote, polymath_shared.principal_context, orchestrator.web_accounts, orchestrator.web_scope) — orchestrator/orchestrator/web_boundary.py:21-28
- Calls into orchestrator.web_accounts (`session_secret`, `read_session`, `resolve_session`, `csrf_ok`, `SESSION_COOKIE`, `CSRF_HEADER`) — orchestrator/orchestrator/web_boundary.py:27, 175-187
- Calls `REGISTRY.get()` from orchestrator.web_scope — orchestrator/orchestrator/web_boundary.py:28, 175
- Lazy request-time import of `orchestrator.api.acquisition.loopback_host` — orchestrator/orchestrator/web_boundary.py:132
- Emits ASGI responses itself: 302 sign-in, 401/403/503 JSON, websocket.close 1008 — orchestrator/orchestrator/web_boundary.py:121-126, 136-141, 157, 166

## invariants
INVARIANT: proxied path with no RULES match → 403 ROUTE_NOT_ALLOWED (fail closed, classify returns None) — orchestrator/orchestrator/web_boundary.py:90-94, 170-173 [DERIVED]
  fails-if: an unlisted route becomes reachable through the proxy by any session holder.
INVARIANT: count of proxy-detection header names == 3 (`x-forwarded-for`, `forwarded`, `x-forwarded-host`) — orchestrator/orchestrator/web_boundary.py:30 [DERIVED]
  fails-if: a proxy variant outside the set is treated as DIRECT and must then pass the loopback Host check.
INVARIANT: occurrences of the principal header in forwarded headers == 0 for the owner, == 1 (`ident.principal_id`) for a friend; incoming one always dropped — orchestrator/orchestrator/web_boundary.py:168, 196-197 [DERIVED]
  fails-if: a browser-supplied principal header would impersonate any principal.
INVARIANT: direct request with non-loopback Host never reaches a route (403 NON_LOOPBACK_HOST or ws close 1008) — orchestrator/orchestrator/web_boundary.py:155-162 [DERIVED]
  fails-if: DNS-rebinding page could reach GET /keys/owner or POST /auth/owner-password — orchestrator/orchestrator/web_boundary.py:13-15 [DERIVED]
INVARIANT: CAPABILITY class routes skip session and CSRF and are never forwarded a principal — orchestrator/orchestrator/web_boundary.py:33-37, 174 [DERIVED]
  fails-if: token-in-path uploads (report upload route) would demand a session cookie.
INVARIANT: proxied method not in SAFE_METHODS requires `W.csrf_ok(...)`, else 403 CSRF_FAILED — orchestrator/orchestrator/web_boundary.py:31, 187-189 [DERIVED]
INVARIANT: identity with `must_change_password` may touch only the 3 paths in PASSWORD_CHANGE_OK — orchestrator/orchestrator/web_boundary.py:42, 190-192 [DERIVED]
INVARIANT: proxied websocket → close 1008 (no proxied websocket route exists) — orchestrator/orchestrator/web_boundary.py:165-167 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — decision is a pure function of method/path/headers; no clock, random, uuid, db or env use in this file — orchestrator/orchestrator/web_boundary.py:21-28, 150-201 [DERIVED] (session validity itself is delegated to web_accounts, not resolved here)
idempotency: SAFE — middleware writes no durable state; it copies the scope (`dict(scope)`, `{**scope, ...}`) before mutating — orchestrator/orchestrator/web_boundary.py:198-200 [DERIVED]

## failure behaviour
No try/except in this file; every refusal is an explicit response. `_deny` sends JSON `{"detail": {"error_code": ..., **extra, "message": ...}}` with `cache-control: no-store` — orchestrator/orchestrator/web_boundary.py:136-141.
| condition | status | error_code | anchor |
|---|---|---|---|
| direct request, non-loopback Host | 403 | NON_LOOPBACK_HOST (also duplicated as `code`) | orchestrator/orchestrator/web_boundary.py:159-161 |
| proxied path not in RULES | 403 | ROUTE_NOT_ALLOWED | orchestrator/orchestrator/web_boundary.py:172 |
| session/registry not configured | 503 | LOGIN_NOT_CONFIGURED | orchestrator/orchestrator/web_boundary.py:177 |
| no valid session | 401 | LOGIN_REQUIRED (browsers on a report page get 302 instead) | orchestrator/orchestrator/web_boundary.py:182-185 |
| unsafe method, CSRF check fails | 403 | CSRF_FAILED | orchestrator/orchestrator/web_boundary.py:188 |
| must_change_password, path outside allowlist | 403 | PASSWORD_CHANGE_REQUIRED | orchestrator/orchestrator/web_boundary.py:191 |
| OWNER class, non-owner identity | 403 | OWNER_ONLY | orchestrator/orchestrator/web_boundary.py:194 |
302 sign-in redirect builds `"/v2/?next=" + quote(path, safe="")` — orchestrator/orchestrator/web_boundary.py:121-126.

## dumb-code flags
- `code="NON_LOOPBACK_HOST"` in the deny call duplicates the `error_code` value; the JSON body carries the same string under two keys — orchestrator/orchestrator/web_boundary.py:159-161 vs 136-137 [DERIVED]
- websocket close code `1008` written twice as a bare literal — orchestrator/orchestrator/web_boundary.py:157, 166 [DERIVED]
- "OPTIONS" is in SAFE_METHODS (CSRF-exempt) but no RULES method-set contains OPTIONS; only `_ANY` (owner) rules can classify an OPTIONS request — orchestrator/orchestrator/web_boundary.py:31, 44-87 [DERIVED]
- `_ANY = None` doubles as "any method" inside RULES while `classify` returning None means "refused" — two meanings of None in one path — orchestrator/orchestrator/web_boundary.py:44, 92-94 [DERIVED]
- REPORT_PAGE regex `^/product/report/[^/]+$` hand-duplicates the RULES shape `^/product/report/{_SEG}(/status)?$` with `_SEG = "[^/]+"`; a route change must touch both — orchestrator/orchestrator/web_boundary.py:40, 48, 74 [DERIVED]
- FACTS serializes PASSWORD_CHANGE_OK as a list `["/auth/logout", "/auth/me", "/auth/password"]` while source has a frozenset — representation drift between FACTS and source, membership semantics identical — orchestrator/orchestrator/web_boundary.py:42 [DERIVED]
- WRITE class covers only two rules (POST /upload, DELETE /documents/{SEG}) — orchestrator/orchestrator/web_boundary.py:77 [DERIVED]

## refactor notes
- Importers are orchestrator/orchestrator/main.py and orchestrator/orchestrator/api/web_auth.py (FACTS.importers); mounting order relative to PrincipalContextMiddleware is contractual — orchestrator/orchestrator/web_boundary.py:145 [DERIVED]
- RULES is first-match-wins policy-as-data; inserting a rule above an existing one can shadow it — orchestrator/orchestrator/web_boundary.py:50 [DERIVED]
- Per-route second layer named in the docstring (`refuse_unless_mcp_or_web`, `product.refuse_rebinding`) must stay in sync with RULES — orchestrator/orchestrator/web_boundary.py:16-17 [DERIVED]
- `_loopback` imports `orchestrator.api.acquisition.loopback_host` lazily at request time; moving that symbol breaks every direct request — orchestrator/orchestrator/web_boundary.py:130-133 [INFERRED: an ImportError would raise inside \_\_call\_\_]
- Error codes and the 302 `next` shape are consumed by the /v2 web app (C7) — orchestrator/orchestrator/web_boundary.py:38-39, 121-126 [DERIVED]
- web_accounts/web_scope contract used: `session_secret`, `read_session`, `resolve_session`, `csrf_ok`, `SESSION_COOKIE`, `CSRF_HEADER`, `REGISTRY.get()` — orchestrator/orchestrator/web_boundary.py:27-28, 175-187 [DERIVED]

## VERIFY
```verify
grep -Fq 'PROXY_HEADERS = frozenset({b"x-forwarded-for", b"forwarded", b"x-forwarded-host"})' orchestrator/orchestrator/web_boundary.py
grep -Fq 'SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})' orchestrator/orchestrator/web_boundary.py
grep -Fq 'PASSWORD_CHANGE_OK = frozenset({"/auth/me", "/auth/password", "/auth/logout"})' orchestrator/orchestrator/web_boundary.py
grep -Fq 'SIGN_IN = "/v2/"' orchestrator/orchestrator/web_boundary.py
grep -Fq 'NON_LOOPBACK_HOST' orchestrator/orchestrator/web_boundary.py
test "$(grep -c -F '_deny(' orchestrator/orchestrator/web_boundary.py)" -ge 8
! grep -Fq 'os.environ' orchestrator/orchestrator/web_boundary.py
```
