# unit: orchestrator/orchestrator/api/acquisition.py
anchor: orchestrator/orchestrator/api/acquisition.py:1-154

## purpose
FastAPI router that is the public entrypoint behind the MCP tool `research_acquire`: a connected harness without its own browser asks Polymath to read a permitted page for the run's OPEN research step — orchestrator/orchestrator/api/acquisition.py:1-5 [DERIVED]. Also hosts the READ-ONLY supplier routes behind MCP tools `supplier_search` / `supplier_product` / `supplier_freight` / `supplier_warehouses` — orchestrator/orchestrator/api/acquisition.py:13-16 [DERIVED]. All policy lives in `polymath_shared.acquisition.service` and `...supplier`; this module applies run ownership, runs reads off the event loop, and maps refusals to status codes — orchestrator/orchestrator/api/acquisition.py:2-5 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `acquire` | route handler, POST `/adapter/{run_id}/acquire` | (run_id: str, req: AcquireRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:82-101 | MCP tool `research_acquire` (:1); module imported by `orchestrator/orchestrator/main.py` (FACTS.importers) |
| `supplier_search` | route handler, POST `/supplier/search` | (req: SupplierSearchRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:137-138 | MCP tool `supplier_search` (:13) |
| `supplier_product` | route handler, POST `/supplier/product` | (req: SupplierProductRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:142-143 | MCP tool `supplier_product` (:13) |
| `supplier_freight` | route handler, POST `/supplier/freight` | (req: SupplierFreightRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:147-149 | MCP tool `supplier_freight` (:14) |
| `supplier_warehouses` | route handler, GET `/supplier/warehouses` | (request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:153-154 | MCP tool `supplier_warehouses` (:14) |
| `refuse_unless_direct` | guard fn | (request: Request, what: str = "research acquisition", tools: str = "tool research_acquire") -> None | orchestrator/orchestrator/api/acquisition.py:70-78 | `acquire` (:83), `_supplier` (:126) |
| `loopback_host` | helper fn | (host: str \| None) -> bool | orchestrator/orchestrator/api/acquisition.py:62-67 | `refuse_unless_direct` (:75) |
| `open_harness_action` | helper fn | (conn, run_id: str) -> dict[str, Any] \| None | orchestrator/orchestrator/api/acquisition.py:45-54 | `acquire` (:88) |
| `AcquireRequest` | pydantic model | operation: str; target: str = ""; site/search_intent_id: Optional[str] = None; limit: Optional[int] = None | orchestrator/orchestrator/api/acquisition.py:37-42 | `acquire` |
| `SupplierSearchRequest` | pydantic model | query: str; source: str = "cj"; limit: int \| None = supplier.SEARCH_LIMIT_DEFAULT | orchestrator/orchestrator/api/acquisition.py:105-108 | `supplier_search` |
| `SupplierProductRequest` | pydantic model | product_id: str | orchestrator/orchestrator/api/acquisition.py:111-112 | `supplier_product` |
| `SupplierFreightRequest` | pydantic model | variant_id: str; country: str; quantity: int = 1; from_country: str = "CN" | orchestrator/orchestrator/api/acquisition.py:115-119 | `supplier_freight` |

## contracts

**acquire (POST /adapter/{run_id}/acquire)**
- pre: `refuse_unless_direct(request)` — 403 unless direct MCP-server call — orchestrator/orchestrator/api/acquisition.py:83 [DERIVED]
- pre: inside `tx()`: `service.assert_owner(conn, run_id, principal)` then `open_harness_action(conn, run_id)`; `NotRunOwner` → 403 `"no such run for this principal"`, `UnknownRun` → 404 `f"unknown adapter run {run_id!r}"` — orchestrator/orchestrator/api/acquisition.py:86-92 [DERIVED]
- in: `req.operation` (required), `req.target` (default `""`), `req.site`, `req.search_intent_id`, `req.limit` (default `None`), plus the open `action` (may be `None`) — orchestrator/orchestrator/api/acquisition.py:37-42, 88, 94-95 [DERIVED]
- post: the browser read runs via `asyncio.to_thread(acquisition.acquire, ...)` after the `tx()` block closes — no DB transaction held while the browser reads — orchestrator/orchestrator/api/acquisition.py:86-95, 4-5 [DERIVED]
- out: the `acquisition.acquire` dict returned verbatim — orchestrator/orchestrator/api/acquisition.py:95, 101 [DERIVED]
- error: `acquisition.AcquisitionRefused` → `HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})` — orchestrator/orchestrator/api/acquisition.py:96-97 [DERIVED]
- post: logs one info line (`acquisition_id`, run, `action_id`, operation, site, `target[:300]`, status, item count, `source_id`s joined `[:600]`) — orchestrator/orchestrator/api/acquisition.py:98-100 [DERIVED]

**open_harness_action**
- in: `conn`, `run_id` — orchestrator/orchestrator/api/acquisition.py:45 [DERIVED]
- out: `step["harness_action"]` iff `service.status(...)["status"] == "awaiting_harness"` AND `store.current_step(...)` status `"issued"` AND `step["harness_action"]` is a `dict`; otherwise `None` — orchestrator/orchestrator/api/acquisition.py:47-54 [DERIVED]
- read-only — orchestrator/orchestrator/api/acquisition.py:46 [DERIVED]

**refuse_unless_direct / loopback_host**
- 403 `{"code": "PROXIED_CALLER", ...}` when any of `x-forwarded-for`, `x-forwarded-host`, `forwarded` is present — orchestrator/orchestrator/api/acquisition.py:57, 72-74 [DERIVED]
- 403 `{"code": "NON_LOOPBACK_HOST", ...}` unless Host hostname is `127.0.0.1`, `localhost`, or `::1` (any port — `urlsplit("//" + host).hostname`) — orchestrator/orchestrator/api/acquisition.py:59, 62-67, 75-78 [DERIVED]
- `urlsplit` `ValueError` is swallowed → `False` (treated as non-loopback) — orchestrator/orchestrator/api/acquisition.py:66-67 [DERIVED]

**_supplier (shared by all four supplier routes)**
- pre: `refuse_unless_direct(request, "supplier lookup", "tools " + ", ".join(supplier.TOOLS))` — orchestrator/orchestrator/api/acquisition.py:122, 126 [DERIVED]
- body: `await asyncio.to_thread(fn, principal_id=principal_context.current(), **kw)` — orchestrator/orchestrator/api/acquisition.py:128 [DERIVED]
- error: `AcquisitionRefused` → `HTTPException(exc.status, {"code", "message"})` — orchestrator/orchestrator/api/acquisition.py:129-130 [DERIVED]
- post: logs `"supplier %s source=%s status=%s rows=%s"` with `len()` of first truthy of `items`/`variants`/`options`/`warehouses` — orchestrator/orchestrator/api/acquisition.py:131-132 [DERIVED]
- policy: owner only — these calls spend the owner's CJ account and quota; "a principal gets 403" (enforced in `polymath_shared.acquisition.supplier`, not here) — orchestrator/orchestrator/api/acquisition.py:13-16 [DERIVED]

## effect surface
- Postgres: no tables read or written by this module (FACTS `tables_read`/`tables_written` empty); DB touched only through `service`/`store` inside `tx()` — orchestrator/orchestrator/api/acquisition.py:86-88 [DERIVED]
- Network: browser page read via `acquisition.acquire` — orchestrator/orchestrator/api/acquisition.py:94; supplier API calls via `supplier.search/product/freight/warehouses` — orchestrator/orchestrator/api/acquisition.py:128, 138, 143, 148-149, 154 [DERIVED]
- Env: none read in this file; comment notes MCP servers address the listener via `POLYMATH_ORCH_URL` / `POLYMATH_API`, default `http://127.0.0.1:7200` — orchestrator/orchestrator/api/acquisition.py:58 [DERIVED]
- Qdrant / files / subprocesses: none visible.
- Imported by `orchestrator/orchestrator/main.py` (FACTS.importers) — orchestrator/orchestrator/api/acquisition.py:1 [DERIVED]

## invariants
INVARIANT: accepted Host hostname ∈ `{"127.0.0.1", "localhost", "::1"}` — orchestrator/orchestrator/api/acquisition.py:59, 62-67, 75-78 [DERIVED]
  fails-if: a DNS-rebinding page (B-28) or remote caller passes the gate; or a legitimately configured non-loopback MCP address is refused.
INVARIANT: proxy-header set checked == exactly `("x-forwarded-for", "x-forwarded-host", "forwarded")` — orchestrator/orchestrator/api/acquisition.py:57, 72 [DERIVED]
  fails-if: any other forwarded-header convention (e.g. a differently named proxy header) lets a proxied request count as direct.
INVARIANT: non-None action ⟺ status `"awaiting_harness"` AND step status `"issued"` AND `harness_action` is dict — orchestrator/orchestrator/api/acquisition.py:47-53 [DERIVED]
  fails-if: acquisition runs against a closed, unissued, or malformed step.
INVARIANT: `tx()` closes before `asyncio.to_thread(acquisition.acquire, ...)` starts — orchestrator/orchestrator/api/acquisition.py:86-95 [DERIVED]
  fails-if: a DB transaction is pinned for the duration of a browser read.
INVARIANT: `@router.post` count == 4, `@router.get` count == 1 — orchestrator/orchestrator/api/acquisition.py:81, 136, 141, 146, 152 [DERIVED]
  fails-if: a removed/retyped route 404s its MCP tool.
INVARIANT: supplier routes are read-only — "nothing here orders, pays, lists or disputes" — orchestrator/orchestrator/api/acquisition.py:13-16 [DERIVED]
  fails-if: an ordering/pay path appears behind the owner's CJ credentials.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: browser read orchestrator/orchestrator/api/acquisition.py:94 and supplier API calls :128; db: `service.status`/`store.current_step` :47, :50; concurrency: `asyncio.to_thread` :94, :128)
idempotency: SAFE within this module (no direct table writes, FACTS `tables_written` empty); `acquire` delegates to `acquisition.acquire`, whose returned `acquisition_id` (:98-99) implies any persistence lives in `polymath_shared.acquisition.service`, not visible here.

## failure behaviour
- 403 `PROXIED_CALLER` with `{"code", "message"}` detail — orchestrator/orchestrator/api/acquisition.py:73-74 [DERIVED]
- 403 `NON_LOOPBACK_HOST` with `{"code", "message"}` detail — orchestrator/orchestrator/api/acquisition.py:76-78 [DERIVED]
- 403 plain-detail `"no such run for this principal"` on `service.NotRunOwner` — orchestrator/orchestrator/api/acquisition.py:89-90 [DERIVED]
- 404 `f"unknown adapter run {run_id!r}"` on `service.UnknownRun` — orchestrator/orchestrator/api/acquisition.py:91-92 [DERIVED]
- `acquisition.AcquisitionRefused` → `exc.status` with `{"code": exc.code, "message": exc.message}` — orchestrator/orchestrator/api/acquisition.py:96-97, 129-130 [DERIVED]
- `loopback_host` swallows `urlsplit` `ValueError` → returns `False` → caller receives the `NON_LOOPBACK_HOST` 403 — orchestrator/orchestrator/api/acquisition.py:66-67 [INFERRED: refusal path is the only consumer of `False`]
- No other handlers; unexpected exceptions propagate to FastAPI — whole file [DERIVED]

## dumb-code flags
- Literal `"127.0.0.1:7200"` duplicated in two comments — orchestrator/orchestrator/api/acquisition.py:10, 58 [DERIVED]
- Guard default `tools: str = "tool research_acquire"` hardcodes the MCP tool name in a signature — orchestrator/orchestrator/api/acquisition.py:70 [DERIVED]
- Log truncation magic numbers `300` (target) and `600` (sources) — orchestrator/orchestrator/api/acquisition.py:99-100 [DERIVED]
- Hardcoded request defaults `source = "cj"` and `from_country = "CN"` — orchestrator/orchestrator/api/acquisition.py:107, 119 [DERIVED]
- `_supplier` row count `out.get("items") or out.get("variants") or out.get("options") or out.get("warehouses") or []` — an empty `items` list silently falls through to the next key — orchestrator/orchestrator/api/acquisition.py:132 [DERIVED]
- FACTS renders `LOOPBACK_HOSTS` as list `["127.0.0.1", "::1", "localhost"]`; code is `frozenset({"127.0.0.1", "localhost", "::1"})` — same members, set semantics — orchestrator/orchestrator/api/acquisition.py:59 [DERIVED]

## refactor notes
- Route paths/methods are the MCP contract: `/adapter/{run_id}/acquire`, `/supplier/search`, `/supplier/product`, `/supplier/freight` (POST), `/supplier/warehouses` (GET); renaming breaks the MCP tools named at :1, :13-15 and the sole importer `orchestrator/orchestrator/main.py` — orchestrator/orchestrator/api/acquisition.py:81, 136, 141, 146, 152 [DERIVED]
- Error detail shape `{"code", "message"}` and codes `PROXIED_CALLER` / `NON_LOOPBACK_HOST` are caller-visible; changing them breaks MCP-side error handling — orchestrator/orchestrator/api/acquisition.py:73-78, 96-97 [DERIVED]
- `PROXY_HEADERS` / `LOOPBACK_HOSTS` implement the B-28 DNS-rebinding defense; any change weakens or breaks that guarantee — orchestrator/orchestrator/api/acquisition.py:57-59, 70-78 [DERIVED]
- `refuse_unless_direct` defaults must track tool renames (`"tool research_acquire"`, `supplier.TOOLS`) — orchestrator/orchestrator/api/acquisition.py:70, 122 [DERIVED]
- `open_harness_action` encodes the `"awaiting_harness"` / `"issued"` / dict-shape expectations of `service`/`store`; changing those state names requires updating this filter — orchestrator/orchestrator/api/acquisition.py:47-53 [DERIVED]

## VERIFY
```verify
grep -Fq 'PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded")' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'if st.get("status") != "awaiting_harness":' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'out = await asyncio.to_thread(acquisition.acquire, principal_id=principal, action=action, operation=req.operation,' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'from_country: str = "CN"' orchestrator/orchestrator/api/acquisition.py
test "$(grep -c -F '@router.post' orchestrator/orchestrator/api/acquisition.py)" -ge 4
! grep -Fq 'x-real-ip' orchestrator/orchestrator/api/acquisition.py
```
