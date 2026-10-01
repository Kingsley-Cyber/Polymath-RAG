# unit: orchestrator/orchestrator/_small-modules
anchor: orchestrator/orchestrator/__init__.py:1-2

## purpose
Package root plus four small modules of the orchestrator service: Pydantic request/response models ("Validation only", contracts.py:1), the sidecar registry loader that answers "where does service X live" from `sidecars/*.toml` (registry.py:1-7), the ASGI authorization middleware for the proxied public web door `rag.kingsleylab.xyz → Caddy → :7200` (web_boundary.py:1-10), and in-route principal narrowing helpers (web_scope.py:1-8) — web_boundary.py:1-10, web_scope.py:1-8 [DERIVED]. Consumed by `api/*` routes, `main.py`, `mcp_server.py`, `web_accounts.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| IngestRequest | class (BaseModel) | corpus_id: str Field(min_length=1), source: str Field(min_length=1), profile: str = "default" | contracts.py:7-10 | — |
| IngestResponse | class (BaseModel) | run_id: str, accepted: bool | contracts.py:13-15 | — |
| ChatRequest | class (BaseModel) | message: str Field(min_length=1), corpus_id: str \| None = None | contracts.py:18-20 | — |
| Sidecar | class | \_\_init\_\_(name, config, manifest, base_url) -> None; unpinned -> bool; is_ready() -> bool | registry.py:17-35 | — |
| load_sidecar_registry | def | (root: Path \| None = None) -> Mapping[str, Sidecar] | registry.py:38-57 | — |
| classify | def | (method: str, path: str) -> str \| None | web_boundary.py:63-67 | — |
| proxied | def | (headers) -> bool | web_boundary.py:70-71 | — |
| cookie | def | (headers, name: str) -> str \| None | web_boundary.py:81-87 | — |
| WebBoundaryMiddleware | class (ASGI) | \_\_init\_\_(app); \_\_call\_\_(scope, receive, send) | web_boundary.py:98-141 | — |
| RegistryCache | class | \_\_init\_\_() -> None; get() -> dict[str, Any] \| None | web_scope.py:23-51 | — |
| REGISTRY | instance | RegistryCache() | web_scope.py:54 | web_boundary.py:19 |
| current_principal | def | () -> P.Principal \| None | web_scope.py:61-69 | — |
| allowed_corpora | def | (write: bool = False) -> frozenset[str] \| None | web_scope.py:72-77 | — |
| can_see | def | (corpus_id: str \| None, write: bool = False) -> bool | web_scope.py:80-82 | — |
| require_corpus / require_corpora | def | (corpus_id, write=False) / (corpus_ids, write=False) -> None (raise HTTPException) | web_scope.py:85-92 | — |
| narrow_scope | def | (scope: QueryScope) -> QueryScope | web_scope.py:95-107 | — |
| filter_by_corpus | def | (rows: list[Any], key: str = "corpus_id") -> list[Any] | web_scope.py:110-114 | — |
| require_document | def | (conn, doc_id: str, write: bool = False) -> None (raise HTTPException) | web_scope.py:117-123 | — |
| require_adapter_start | def | (adapter_id, input_payload: dict \| None, request_options: dict \| None = None) -> None | web_scope.py:126-138 | — |

Unit importers (FACTS.importers): `orchestrator/orchestrator/main.py`, `mcp_server.py`, `web_accounts.py`, `api/adapter.py`, `api/compare_review.py`, `api/corpus_plan.py`, `api/deep_research.py`, `api/graph_browse.py`, `api/health.py`, `api/retrieve.py`, `api/ui.py`, `api/web_auth.py`, `api/web_settings.py`, `api/_small-modules`.

## contracts

**classify(method, path)** — web_boundary.py:63-67
- out: one of "public", "user", "write", "owner" (constants at web_boundary.py:23) or None; RULES is a first-match table (comment web_boundary.py:32); unmatched ⇒ None. [DERIVED]

**proxied(headers)** — True iff any header name lowercased is in {b"x-forwarded-for", b"forwarded", b"x-forwarded-host"} — web_boundary.py:21,70-71. [DERIVED]

**cookie(headers, name)** — parses the `cookie` header: split ";", strip, partition "="; returns value or None — web_boundary.py:81-87. [DERIVED]

**WebBoundaryMiddleware.\_\_call\_\_(scope, receive, send)** — web_boundary.py:104-141
- pre: pass-through untouched when type ∉ {http, websocket} or not proxied — web_boundary.py:105-107. [DERIVED]
- steps (proxied http): strip any incoming principal header (111); classify (113); PUBLIC ⇒ forward (117); otherwise require `W.session_secret()` and `REGISTRY.get()` both non-None (118-120), a valid session (122-125), CSRF header when method ∉ SAFE_METHODS (127-129), `not ident.must_change_password or path in PASSWORD_CHANGE_OK` (130-132), `cls == OWNER ⇒ ident.is_owner` (133-135). [DERIVED]
- post: non-owner gets `principal_context.HEADER` appended with `ident.principal_id` (136-137); `scope["state"]["web_identity"] = ident` (139); headers replaced (140). [DERIVED]

**load_sidecar_registry(root=None)** — registry.py:38-57
- default root is repo-relative: `Path(__file__).resolve().parents[2] / "sidecars"` regardless of cwd (39-42); iterates `sorted(root.glob("*.toml"))`, each TOML entry keyed by sidecar name (44-47). [DERIVED]
- base url: `cfg["manifest_url"].rsplit("/manifest", 1)[0]` (48); manifest fetched via GET `{base}/manifest` or None on any Exception (50-55). [DERIVED]

**Sidecar** — registry.py:17-35
- `manifest or {}` default (21); `pinned_release = config.get("release")` (23). [DERIVED]
- unpinned ⇔ `(pinned_release or "").startswith("__PIN_")` — registry.py:26-28. [DERIVED]
- is_ready: GET `{base_url}/ready` timeout=2.0 ⇒ `status_code == 200 and bool(r.json().get("ready"))`; any Exception ⇒ False (30-35). [DERIVED]

**RegistryCache.get()** — web_scope.py:33-51
- `W.registry_path()` None ⇒ None (34-36); `path.stat()` OSError ⇒ `{"schema": P.SCHEMA, "principals": []}` (37-40). [DERIVED]
- cache key `(str(path), st_mtime_ns, st_ino, st_size)`; re-read under `threading.Lock` only when key changes (41-50). [DERIVED]
- `st.st_mode & 0o077` ⇒ ValueError ⇒ doc None + `last_error` set (44-48). [DERIVED]

**current_principal()** — web_scope.py:61-69
- `principal_context.current()` None ⇒ None (owner / trusted local caller) (63-65). [DERIVED]
- pid not found in registry or `not P._active(rec, datetime.now(UTC))` ⇒ 403 PRINCIPAL_UNKNOWN (66-68). [DERIVED]

**allowed_corpora(write=False)** — None principal ⇒ None (unrestricted); else `writable_corpus_ids` if write else `corpus_ids` — web_scope.py:72-77. [DERIVED]

**narrow_scope(scope)** — web_scope.py:95-107
- allowed None ⇒ scope unchanged (98-100); mode in {"CORPUS", "CORPORA"} ⇒ each of `scope.corpus_ids` required, scope returned (101-103); otherwise ids = corpus_ids ∩ allowed, empty ⇒ 403 CORPUS_NOT_ALLOWED (104-106). Narrowing only, never widens — web_scope.py:7,95-107. [DERIVED]

**filter_by_corpus(rows, key="corpus_id")** — allowed None ⇒ rows unchanged; else keep rows where `r.get(key)` (dict) or `getattr(r, key, None)` (object) is in allowed — web_scope.py:110-114. [DERIVED]

**require_document(conn, doc_id, write=False)** — allowed None ⇒ return; else `SELECT corpus_id FROM documents WHERE doc_id = %s`; row None or `not can_see(row[0], write)` ⇒ 403 DOCUMENT_NOT_ALLOWED — web_scope.py:117-123. Unknown doc and hidden doc are indistinguishable — web_scope.py:118. [DERIVED]

**require_adapter_start(adapter_id, input_payload, request_options=None)** — web_scope.py:126-138
- principal None ⇒ return (129-131); `adapter_id not in p.adapter_ids` ⇒ 403 ADAPTER_NOT_ALLOWED (132-133). [DERIVED]
- named = `P._ids(input.corpus_ids)` + `P._ids(request_options.corpus_ids)`; empty ⇒ 422 CORPUS_IDS_REQUIRED; then `require_corpora(named)` (134-138). [DERIVED]

**Pydantic models** — validation only (contracts.py:1); IngestRequest enforces min_length=1 on corpus_id and source, profile defaults "default" (7-10); ChatRequest min_length=1 on message, corpus_id optional None (18-20). [DERIVED]

## effect surface
- Postgres read: table `documents`, columns `corpus_id`, `doc_id` — web_scope.py:121. No tables written (FACTS.tables_written = []). [DERIVED]
- Network: `httpx.get(f"{self.base_url}/ready", timeout=2.0)` — registry.py:32; `httpx.get(f"{base}/manifest", timeout=5.0)` — registry.py:51. [DERIVED]
- Files read: `<repo>/sidecars/*.toml` via `tomllib.load` — registry.py:42-46; principal registry file via `W.registry_path()` parsed by `P.read_registry(path)` — web_scope.py:34,46. No file writes. [DERIVED]
- Clock: `datetime.now(UTC)` for principal activity check — web_scope.py:67. Threads: `threading.Lock` in RegistryCache — web_scope.py:30. [DERIVED]
- Qdrant / subprocess / env flags: none visible in SOURCE.

## invariants
INVARIANT: methods in SAFE_METHODS = {"GET", "HEAD", "OPTIONS"} are exactly those exempt from the CSRF check — web_boundary.py:22,127-129 [DERIVED]
  fails-if: a state-changing method added to SAFE_METHODS bypasses CSRF silently.
INVARIANT: every proxied request has the incoming principal header removed before anything else — web_boundary.py:111 [DERIVED]
  fails-if: a browser could claim any principal id.
INVARIANT: principal header appended only when `not ident.is_owner` — web_boundary.py:136-139 [DERIVED]
  fails-if: owner traffic through the proxy would be narrowed like a friend's.
INVARIANT: classify(method, path) is None ⇒ 403 ROUTE_NOT_ALLOWED; no unclassified route is served through the web — web_boundary.py:63-67,114-116 [DERIVED]
  fails-if: a new route becomes publicly reachable by accident.
INVARIANT: registry file mode & 0o077 == 0, else REGISTRY.get() returns None — web_scope.py:44-48 [DERIVED]
  fails-if: group/other-readable registry ⇒ 503 LOGIN_NOT_CONFIGURED for all non-public proxied routes (web_boundary.py:118-120).
INVARIANT: RegistryCache re-reads only when (str(path), st_mtime_ns, st_ino, st_size) changes — web_scope.py:41-50 [DERIVED]
  fails-if: same-size same-mtime edit leaves revoked principals active.
INVARIANT: missing registry file ⇒ {"schema": P.SCHEMA, "principals": []} (owner-only world), not an error — web_scope.py:39-40 [DERIVED]
  fails-if: treating it as an error would lock out the owner.
INVARIANT: unknown doc_id and forbidden doc_id raise the same 403 DOCUMENT_NOT_ALLOWED — web_scope.py:118,121-123 [DERIVED]
  fails-if: differing responses leak which doc_ids exist.
INVARIANT: adapter start must name ≥ 1 corpus id from input.corpus_ids ∪ request_options.corpus_ids — web_scope.py:134-137 [DERIVED]
  fails-if: a principal could start a run over unspecified (possibly all) libraries.
INVARIANT: unpinned ⇔ release placeholder prefix "__PIN_" — registry.py:26-28 [DERIVED]
  fails-if: unpinned sidecars silently trusted (module docstring says they must be reported, registry.py:3-6).
INVARIANT: proxied websocket ⇒ close code 1008, never forwarded — web_boundary.py:108-110 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network: httpx.get registry.py:32 and registry.py:51; clock: datetime.now(UTC) web_scope.py:67; concurrency: shared RegistryCache doc under threading.Lock web_scope.py:30,42-50)
idempotency: SAFE — no table writes (FACTS.tables_written = []), no file writes; only in-memory cache mutation (web_scope.py:46-50) and gate checks; middleware either forwards or denies (web_boundary.py:104-141).

## failure behaviour
- `/ready` fetch: any Exception swallowed, `is_ready()` returns False — registry.py:34-35; caller sees the sidecar as not ready. [DERIVED]
- `/manifest` fetch: any Exception handled by assign, `manifest = None`; Sidecar coerces to `{}` via `manifest or {}` — registry.py:54-55,21. [DERIVED]
- `_deny` JSON body: `{"detail": {"error_code", "message"}}`, headers `content-type application/json`, `cache-control no-store` — web_boundary.py:90-95. [DERIVED]
- Boundary denials: 403 ROUTE_NOT_ALLOWED (115), 503 LOGIN_NOT_CONFIGURED (120), 401 LOGIN_REQUIRED (125), 403 CSRF_FAILED (129), 403 PASSWORD_CHANGE_REQUIRED (132), 403 OWNER_ONLY (135) — web_boundary.py:114-135. [DERIVED]
- Proxied websocket refused with close code 1008 — web_boundary.py:108-110. [DERIVED]
- web_scope raises HTTPException via `_refuse` (default status 403, web_scope.py:57-58): PRINCIPAL_UNKNOWN (68), CORPUS_NOT_ALLOWED (87, 106), DOCUMENT_NOT_ALLOWED (123), ADAPTER_NOT_ALLOWED (133), CORPUS_IDS_REQUIRED status 422 (137). [DERIVED]
- RegistryCache failure mode: unreadable/insecure file ⇒ doc None + `last_error` string (web_scope.py:44-48); downstream effect is 503 LOGIN_NOT_CONFIGURED — web_boundary.py:118-120. [DERIVED]

## dumb-code flags
- Two inline timeouts with no named constant: `timeout=2.0` (ready) vs `timeout=5.0` (manifest) — registry.py:32,51. [DERIVED]
- Permission check masks `0o077` but the error message hardcodes "chmod 600" — web_scope.py:44-45. [DERIVED]
- `cfg["manifest_url"].rsplit("/manifest", 1)[0]` — a URL without the literal "/manifest" segment silently becomes the full URL as base_url — registry.py:48. [INFERRED: rsplit returns the input unchanged when the separator is absent.]
- Path strings duplicated between RULES and PASSWORD_CHANGE_OK: "/auth/me", "/auth/password", "/auth/logout" appear at web_boundary.py:24 and again at 38-39; they must stay in sync. [DERIVED]
- `cookie()` parses the raw Cookie header by splitting ";" with no quoted-value handling — web_boundary.py:83-87. [DERIVED]
- `filter_by_corpus` uses a dual accessor (dict `.get` / `getattr`) per row — web_scope.py:114. [DERIVED]

## refactor notes
- RULES is a first-match table (comment web_boundary.py:32); overlapping patterns exist (GET `/documents/{_SEG}/(sections|status)` USER at 43, DELETE `/documents/{_SEG}` WRITE at 51, POST `/documents/{_SEG}/enrich` OWNER at 56) — reordering or editing entries changes web exposure for every proxied request. [DERIVED]
- The principal header name comes from `polymath_shared.principal_context.HEADER`; it is stripped at web_boundary.py:111 and re-added at 136-139 — a rename must touch both sides plus every importer in FACTS.importers (main.py, mcp_server.py, api/*). [DERIVED]
- `REGISTRY` is a module-level singleton imported directly (`from orchestrator.web_scope import REGISTRY`, web_boundary.py:19) — its API cannot change without updating that import. [DERIVED]
- `narrow_scope` matches QueryScope.mode literals "CORPUS" / "CORPORA" — must track polymath_shared.query_scope definitions — web_scope.py:101. [DERIVED]
- Raw SQL against `documents` (`corpus_id`, `doc_id`) in require_document — schema changes break it silently — web_scope.py:121. [DERIVED]
- `require_adapter_start` deliberately mirrors Server A's rule (mcp_principals.authorize, resource START) — changing one side splits policy — web_scope.py:127-128. [DERIVED]
- Private helpers of other modules are used here: `P.SCHEMA`, `P.read_registry`, `P._active`, `P._ids`, `P.principal_from_record` — web_scope.py:39,46,66,69,134-135. [DERIVED]
- The "__PIN_" placeholder convention is shared with whatever writes `sidecars/*.toml` (registry.py:3-6). [DERIVED]

## VERIFY
```verify
grep -Fq 'PASSWORD_CHANGE_OK = frozenset({"/auth/me", "/auth/password", "/auth/logout"})' orchestrator/orchestrator/web_boundary.py
grep -Fq 'release.startswith("__PIN_")' orchestrator/orchestrator/registry.py
grep -Fq 'st.st_mode & 0o077' orchestrator/orchestrator/web_scope.py
grep -Fq 'SELECT corpus_id FROM documents WHERE doc_id = %s' orchestrator/orchestrator/web_scope.py
grep -Fq 'profile: str = "default"' orchestrator/orchestrator/contracts.py
grep -Fq '{"type": "websocket.close", "code": 1008}' orchestrator/orchestrator/web_boundary.py
test "$(grep -c -F 'httpx.get' orchestrator/orchestrator/registry.py)" -ge 2
! grep -Fq 'os.environ' orchestrator/orchestrator/web_scope.py
```
