# unit: orchestrator/orchestrator/_small-modules
anchor: orchestrator/orchestrator/__init__.py:1

## purpose
- Package marker only: `"""polymath package. See AGENTS.md for the process-role contract."""` — orchestrator/orchestrator/__init__.py:1 [DERIVED]
- contracts.py: "Orchestrator Pydantic models. Validation only." — orchestrator/orchestrator/contracts.py:1 [DERIVED]
- registry.py: one mechanism for "where does service X live" — `sidecars/*.toml` entries with explicit URL + release pin; unpinned manifests reported, never silently trusted; missing sidecars degrade `/ready` but never block startup — orchestrator/orchestrator/registry.py:1-6 [DERIVED]
- web_boundary.py: the public web door's authorization point (proxy `rag.kingsleylab.xyz → Caddy → :7200`); friends narrowed to their libraries via `X-Polymath-Principal`; unclassified routes refused (fail closed); direct loopback callers unchanged — orchestrator/orchestrator/web_boundary.py:1-9 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `IngestRequest` | class (BaseModel) | corpus_id: str Field(min_length=1); source: str Field(min_length=1); profile: str = "default" | contracts.py:7-10 [DERIVED] | — |
| `IngestResponse` | class (BaseModel) | run_id: str; accepted: bool | contracts.py:13-15 [DERIVED] | — |
| `ChatRequest` | class (BaseModel) | message: str Field(min_length=1); corpus_id: str \| None = None | contracts.py:18-20 [DERIVED] | — |
| `Sidecar` | class | (name: str, config: dict, manifest: dict \| None, base_url: str); props `unpinned` -> bool, `is_ready` -> bool | registry.py:17-35 [DERIVED] | — |
| `load_sidecar_registry` | def | (root: Path \| None = None) -> Mapping[str, Sidecar] | registry.py:38-57 [DERIVED] | — |
| `classify` | def | (method: str, path: str) -> str \| None | web_boundary.py:66-70 [DERIVED] | — |
| `proxied` | def | (headers) -> bool | web_boundary.py:73-74 [DERIVED] | — |
| `cookie` | def | (headers, name: str) -> str \| None | web_boundary.py:84-90 [DERIVED] | — |
| `WebBoundaryMiddleware` | class (ASGI) | (app); async `__call__`(scope, receive, send) | web_boundary.py:101-144 [DERIVED] | — |

Per-symbol importers unknown; unit-level FACTS.importers: `orchestrator/orchestrator/api/web_auth.py`, `orchestrator/orchestrator/api/web_settings.py`, `orchestrator/orchestrator/main.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/web_accounts.py`, `orchestrator/orchestrator/web_scope.py` (no line numbers given in FACTS). Unit-external imports used: `polymath_shared.principal_context`, `orchestrator.web_accounts` (as `W`), `orchestrator.web_scope.REGISTRY` — orchestrator/orchestrator/web_boundary.py:17-20 [DERIVED]

## contracts
`classify(method, path)` — orchestrator/orchestrator/web_boundary.py:66-70 [DERIVED]
- out: one of `"public"`, `"user"`, `"write"`, `"owner"` (values at web_boundary.py:23) or `None`
- post: FIRST matching `(methods, pattern, cls)` in `RULES` wins; `methods is None` (`_ANY`) matches every method; unmatched -> `None`

`proxied(headers)` — orchestrator/orchestrator/web_boundary.py:73-74 [DERIVED]
- out: True iff any header key (lowercased) is in `PROXY_HEADERS = frozenset({b"x-forwarded-for", b"forwarded", b"x-forwarded-host"})` — web_boundary.py:21

`cookie(headers, name)` — orchestrator/orchestrator/web_boundary.py:84-90 [DERIVED]
- in: raw `cookie` header split on `";"`, each part `strip()` then `partition("=")`
- out: cookie value or `None`

`WebBoundaryMiddleware.__call__` — orchestrator/orchestrator/web_boundary.py:106-144 [DERIVED], ordered gates:
1. non-`http`/`websocket` scope OR not proxied -> pass-through — 107-109
2. proxied websocket -> `websocket.close` code `1008` (no proxied websocket route exists) — 110-112
3. incoming `principal_context.HEADER` always stripped from headers — 113
4. `classify` returns `None` -> 403 `ROUTE_NOT_ALLOWED` — 115-118
5. `cls != PUBLIC` and (`W.session_secret()` or `REGISTRY.get()`) is None -> 503 `LOGIN_NOT_CONFIGURED` — 119-123
6. session unresolvable -> 401 `LOGIN_REQUIRED` — 124-128
7. `method not in SAFE_METHODS` and `W.csrf_ok(...)` false -> 403 `CSRF_FAILED` — 129-131
8. `ident.must_change_password` and path not in `PASSWORD_CHANGE_OK` -> 403 `PASSWORD_CHANGE_REQUIRED` — 132-134
9. `cls == OWNER and not ident.is_owner` -> 403 `OWNER_ONLY` — 135-137
10. non-owner: header `(principal_context.HEADER, ident.principal_id)` appended; `scope["state"]["web_identity"] = ident` — 138-141
11. forwarded with filtered headers — 143-144

`Sidecar` — orchestrator/orchestrator/registry.py:17-35 [DERIVED]
- ctor post: `manifest or {}`; `pinned_release = config.get("release")` — 21, 23
- `unpinned`: `release.startswith("__PIN_")` on `pinned_release or ""` — 26-28
- `is_ready`: GET `f"{self.base_url}/ready"` `timeout=2.0`; true iff status 200 and `r.json().get("ready")` truthy — 30-33

`load_sidecar_registry(root=None)` — orchestrator/orchestrator/registry.py:38-57 [DERIVED]
- pre: `root` contains readable `*.toml` (iterated `sorted(root.glob("*.toml"))`) — 44
- out: one `Sidecar` per top-level TOML key — 47, 56
- post: default root is repo-relative `Path(__file__).resolve().parents[2] / "sidecars"` regardless of cwd — 39-42

Pydantic field constraints: `corpus_id`/`source`/`message` all `Field(min_length=1)`; `profile` defaults `"default"`; `corpus_id` optional `None` — orchestrator/orchestrator/contracts.py:8-10, 19-20 [DERIVED]

## effect surface
- network: `httpx.get(f"{self.base_url}/ready", timeout=2.0)` — orchestrator/orchestrator/registry.py:32 [DERIVED]
- network: `httpx.get(f"{base}/manifest", timeout=5.0)` — orchestrator/orchestrator/registry.py:51 [DERIVED]
- files: reads `sidecars/*.toml` via `toml.open("rb")` + `tomllib.load` — orchestrator/orchestrator/registry.py:44-46 [DERIVED]
- Postgres/Qdrant: none (FACTS `tables_read=[]`, `tables_written=[]`); no subprocess; no env flags read in SOURCE [DERIVED]

## invariants
INVARIANT: classify result == class of FIRST matching RULES entry; no match == `None` — orchestrator/orchestrator/web_boundary.py:32-33, 66-70 [DERIVED]
  fails-if: inserting/reordering a rule silently reclassifies overlapping paths (e.g. OWNER `^/corpora/{_SEG}(/.*)?$` at :60 vs USER `^/(corpora|...)$` at :42).
INVARIANT: proxied request headers seen by routes contain zero client-supplied `principal_context.HEADER`; only a non-owner ident gets one appended — orchestrator/orchestrator/web_boundary.py:113, 138-139 [DERIVED]
  fails-if: a browser could claim any principal.
INVARIANT: CSRF enforced exactly when `method not in SAFE_METHODS`, `SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})` — orchestrator/orchestrator/web_boundary.py:22, 129 [DERIVED]
  fails-if: adding a state-changing method to SAFE_METHODS skips the token check.
INVARIANT: `PASSWORD_CHANGE_OK == frozenset({"/auth/me", "/auth/password", "/auth/logout"})` gates `ident.must_change_password` — orchestrator/orchestrator/web_boundary.py:24, 132 [DERIVED]
  fails-if: a forced-password-reset account can act beyond those three paths.
INVARIANT: OWNER denial only when `cls == OWNER and not ident.is_owner` — orchestrator/orchestrator/web_boundary.py:135-137 [DERIVED]
  fails-if: tightening to `not is_owner` for all classes would lock friends out of USER routes.
INVARIANT: `base_url == cfg["manifest_url"].rsplit("/manifest", 1)[0]` and manifest fetch URL == `f"{base}/manifest"` — orchestrator/orchestrator/registry.py:48, 51 [DERIVED]
  fails-if: a `manifest_url` without a `/manifest` suffix yields `base_url == manifest_url` and a doubled fetch path.
INVARIANT: `Sidecar.unpinned == pinned_release.startswith("__PIN_")` — orchestrator/orchestrator/registry.py:26-28 [DERIVED]
  fails-if: a `__PIN_` placeholder would be treated as a real release pin.
INVARIANT: default registry root == `Path(__file__).resolve().parents[2] / "sidecars"` — orchestrator/orchestrator/registry.py:40-42 [DERIVED]
  fails-if: moving registry.py one directory deeper breaks sidecar discovery.

## determinism & idempotency
determinism: registry.py NONDETERMINISTIC (network registry.py:32, registry.py:51; filesystem glob registry.py:44) [DERIVED]; classify/proxied/_header/cookie DETERMINISTIC (pure header/string parsing, web_boundary.py:66-90) [DERIVED]; `WebBoundaryMiddleware` outcome depends on `W.session_secret()` / `REGISTRY.get()` / session state — web_boundary.py:120, 124-125 [INFERRED: external state lives in web_accounts/web_scope, not visible here]
idempotency: registry SAFE — read-only, no writes in SOURCE (registry.py:44-56) [DERIVED]; middleware SAFE — gate/forward only, does not mutate stores (web_boundary.py:144) [DERIVED]

## failure behaviour
- `except Exception: return False` in `Sidecar.is_ready` — SWALLOWED (FACTS.fallbacks registry.py:34); caller sees a not-ready sidecar — orchestrator/orchestrator/registry.py:30-35 [DERIVED]
- `except Exception: manifest = None` in `load_sidecar_registry` — handled: assign (FACTS.fallbacks registry.py:54); `Sidecar.manifest` becomes `{}` via `manifest or {}` — orchestrator/orchestrator/registry.py:21, 50-55 [DERIVED]
- docstring policy: unpinned manifests reported never silently trusted; missing sidecars degrade `/ready`, never block startup — orchestrator/orchestrator/registry.py:3-6 [DERIVED]
- web_boundary denial table (body `{"detail": {"error_code", "message"}}`, `cache-control: no-store` — web_boundary.py:93-98):

| status | code | trigger | anchor |
|---|---|---|---|
| 403 | `ROUTE_NOT_ALLOWED` | unclassified proxied route | web_boundary.py:117 [DERIVED] |
| 503 | `LOGIN_NOT_CONFIGURED` | secret or registry doc missing | web_boundary.py:122 [DERIVED] |
| 401 | `LOGIN_REQUIRED` | session unresolvable | web_boundary.py:127 [DERIVED] |
| 403 | `CSRF_FAILED` | unsafe method, bad token | web_boundary.py:130 [DERIVED] |
| 403 | `PASSWORD_CHANGE_REQUIRED` | forced reset, path outside allowlist | web_boundary.py:133 [DERIVED] |
| 403 | `OWNER_ONLY` | friend on OWNER route | web_boundary.py:136 [DERIVED] |
| n/a | websocket close `1008` | any proxied websocket | web_boundary.py:111 [DERIVED] |

- web_boundary.py has no try/except; every failure is an explicit `_deny` send — orchestrator/orchestrator/web_boundary.py:93-144 [DERIVED]

## dumb-code flags
- Literal `"/manifest"` duplicated: stripped at registry.py:48, re-appended at registry.py:51 — a TOML `manifest_url` not ending in `/manifest` silently produces a wrong `base_url`. [DERIVED]
- Timeout asymmetry: `timeout=2.0` for `/ready` (registry.py:32) vs `timeout=5.0` for `/manifest` (registry.py:51); no named constant. [DERIVED]
- `_ANY = None` sentinel: a rule with `methods=None` means "any method" (web_boundary.py:26, 67) — reads like "no methods allowed". [DERIVED]
- `WRITE` class has no dedicated branch in `__call__`; only `cls != PUBLIC` is special-cased (web_boundary.py:119), so WRITE rules (`/upload`, `DELETE /documents/{seg}` at :53) get identical checks to USER. [DERIVED]
- FACTS.constants renders these frozensets as JSON lists and reorders `PASSWORD_CHANGE_OK` (e.g. `["/auth/logout", "/auth/me", "/auth/password"]` at "line 24") vs SOURCE `frozenset({"/auth/me", "/auth/password", "/auth/logout"})` at web_boundary.py:24 — trust SOURCE. [DERIVED]

## refactor notes
- `RULES` order is load-bearing ("the FIRST match wins; unmatched = refused", FRIENDS-ACCESS-V1 §3) — any insertion must be checked against every later pattern — orchestrator/orchestrator/web_boundary.py:32-63 [DERIVED]
- `principal_context.HEADER` is the interop contract with `polymath_shared` and the route layer (strip at :113, re-add at :139) — renaming it breaks principal propagation — orchestrator/orchestrator/web_boundary.py:17, 113, 139 [DERIVED]
- web_accounts (`W`) API consumed here: `session_secret`, `read_session`, `resolve_session`, `csrf_ok`, `SESSION_COOKIE`, `CSRF_HEADER`, `ident.principal_id/.must_change_password/.is_owner` — changing any signature/field breaks the gate chain — orchestrator/orchestrator/web_boundary.py:120-139 [DERIVED]
- `REGISTRY.get()` from `orchestrator.web_scope` returning None disables all logins (503) — orchestrator/orchestrator/web_boundary.py:120-122 [DERIVED]
- `load_sidecar_registry` default root depends on file depth `parents[2]` — moving registry.py changes which `sidecars/` dir is scanned — orchestrator/orchestrator/registry.py:40-42 [DERIVED]
- Renaming any public symbol here touches the six FACTS.importers files (api/web_auth.py, api/web_settings.py, main.py, mcp_server.py, web_accounts.py, web_scope.py). [DERIVED]
- `profile: str = "default"` is a wire-format default; changing it alters ingest behaviour for callers that omit the field — orchestrator/orchestrator/contracts.py:10 [DERIVED]

## VERIFY
```verify
grep -Fq 'profile: str = "default"' orchestrator/orchestrator/contracts.py
grep -Fq 'timeout=2.0' orchestrator/orchestrator/registry.py
grep -Fq 'parents[2] / "sidecars"' orchestrator/orchestrator/registry.py
grep -Fq 'startswith("__PIN_")' orchestrator/orchestrator/registry.py
grep -Fq 'PASSWORD_CHANGE_OK = frozenset({"/auth/me", "/auth/password", "/auth/logout"})' orchestrator/orchestrator/web_boundary.py
grep -Fq 'websocket.close", "code": 1008' orchestrator/orchestrator/web_boundary.py
test "$(grep -c -F 'httpx.get' orchestrator/orchestrator/registry.py)" -ge 2
! grep -Fq 'except Exception' orchestrator/orchestrator/web_boundary.py
```
