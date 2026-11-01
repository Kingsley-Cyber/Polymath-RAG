# unit: orchestrator/orchestrator/api/acquisition.py
anchor: orchestrator/orchestrator/api/acquisition.py:1-188

## purpose
FastAPI router behind the MCP tool `research_acquire` (`POST /adapter/{run_id}/acquire`) and the five read-only supplier tool routes (`/supplier/search|product|freight|warehouses|parse`). — orchestrator/orchestrator/api/acquisition.py:1-5,13-15 [DERIVED]
All policy lives in `polymath_shared.acquisition.service` / `polymath_shared.acquisition.supplier`; this module gates callers (direct-loopback MCP only for acquire; MCP-direct or proxy-that-passed-the-web-boundary for supplier), runs reads off the event loop, and maps refusals to status codes. — orchestrator/orchestrator/api/acquisition.py:2-5,21-23 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| router | APIRouter | module-level, 6 routes | orchestrator/orchestrator/api/acquisition.py:40 | orchestrator/orchestrator/main.py |
| acquire | route handler | POST /adapter/{run_id}/acquire (run_id: str, req: AcquireRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:88-108 | MCP tool `research_acquire` |
| supplier_search | route handler | POST /supplier/search (req: SupplierSearchRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:165-167 | MCP tool supplier_search |
| supplier_product | route handler | POST /supplier/product (req: SupplierProductRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:170-172 | MCP tool supplier_product |
| supplier_freight | route handler | POST /supplier/freight (req: SupplierFreightRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:175-178 | MCP tool supplier_freight |
| supplier_warehouses | route handler | GET /supplier/warehouses (request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:181-183 | MCP tool supplier_warehouses |
| supplier_parse | route handler | POST /supplier/parse (req: SupplierParseRequest, request: Request) -> dict | orchestrator/orchestrator/api/acquisition.py:186-188 | MCP tool supplier_parse |
| AcquireRequest | pydantic model | operation: str; target: str = ""; site: Optional[str] = None; search_intent_id: Optional[str] = None; limit: Optional[int] = None | orchestrator/orchestrator/api/acquisition.py:44-49 | wire schema |
| SupplierSearchRequest | pydantic model | query: str; source: str = "cj"; limit: int \| None = supplier.SEARCH_LIMIT_DEFAULT | orchestrator/orchestrator/api/acquisition.py:112-115 | wire schema |
| SupplierProductRequest | pydantic model | product_id: str | orchestrator/orchestrator/api/acquisition.py:118-119 | wire schema |
| SupplierFreightRequest | pydantic model | variant_id: str; country: str; quantity: int = 1; from_country: str = "CN" | orchestrator/orchestrator/api/acquisition.py:122-126 | wire schema |
| SupplierParseRequest | pydantic model | site: str; raw_text: str | orchestrator/orchestrator/api/acquisition.py:129-131 | wire schema |
| open_harness_action | def | (conn, run_id: str) -> dict[str, Any] \| None | orchestrator/orchestrator/api/acquisition.py:52-61 | internal (acquire) |
| loopback_host | def | (host: str \| None) -> bool | orchestrator/orchestrator/api/acquisition.py:69-74 | internal |
| refuse_unless_direct | def | (request, what="research acquisition", tools="tool research_acquire") -> None | orchestrator/orchestrator/api/acquisition.py:77-85 | internal (acquire) |
| refuse_unless_mcp_or_web | def | (request, what=_SUPPLIER_WHAT, tools=_SUPPLIER_TOOLS) -> None | orchestrator/orchestrator/api/acquisition.py:137-149 | internal (_supplier) |
| _supplier | async def | (request, tool: str, fn, **kw: Any) -> dict | orchestrator/orchestrator/api/acquisition.py:152-162 | internal (5 supplier routes) |

## contracts
**acquire(run_id, req, request) -> dict** — orchestrator/orchestrator/api/acquisition.py:89-108
- in: path `run_id: str`; body `AcquireRequest` (operation required, target = "", site/search_intent_id/limit optional) — orchestrator/orchestrator/api/acquisition.py:44-49
- pre: none of `PROXY_HEADERS` present AND Host is loopback, else 403 before any DB or principal work — orchestrator/orchestrator/api/acquisition.py:77-85,90-91
- pre: inside one `tx()`: `service.assert_owner(conn, run_id, principal)`; `NotRunOwner` -> 403 "no such run for this principal"; `UnknownRun` -> 404 "unknown adapter run {run_id!r}" — orchestrator/orchestrator/api/acquisition.py:93-99
- effect: `acquisition.acquire` run via `asyncio.to_thread` with the run's open HARNESS_ACTION — orchestrator/orchestrator/api/acquisition.py:95,101-102
- post: the `with tx()` block closes before the read (no transaction held during the browser read) — orchestrator/orchestrator/api/acquisition.py:93-102 (docstring 4-5)
- out: dict from `acquisition.acquire`; `AcquisitionRefused` -> HTTPException `exc.status` with `{"code", "message"}` — orchestrator/orchestrator/api/acquisition.py:103-104,108
- post: one info log (acquisition_id, action_id, operation, site, target[:300], status, item count, source ids[:600]) — orchestrator/orchestrator/api/acquisition.py:105-107

**open_harness_action(conn, run_id) -> dict | None** — orchestrator/orchestrator/api/acquisition.py:52-61
- returns `step["harness_action"]` iff `service.status(...)["status"] == "awaiting_harness"` AND current-step row `status == "issued"` AND `step["harness_action"]` is a dict; else None — orchestrator/orchestrator/api/acquisition.py:54-61
- read-only — orchestrator/orchestrator/api/acquisition.py:53

**loopback_host(host) -> bool** — orchestrator/orchestrator/api/acquisition.py:69-74
- True iff `urlsplit("//" + host).hostname` is in `LOOPBACK_HOSTS`; `ValueError` -> False — orchestrator/orchestrator/api/acquisition.py:71-74

**refuse_unless_direct(request, what, tools) -> None** — orchestrator/orchestrator/api/acquisition.py:77-85
- any proxy header -> 403 `{"code": "PROXIED_CALLER"}` — orchestrator/orchestrator/api/acquisition.py:79-81
- non-loopback Host -> 403 `{"code": "NON_LOOPBACK_HOST"}` — orchestrator/orchestrator/api/acquisition.py:82-85

**refuse_unless_mcp_or_web(request, what, tools) -> None** — orchestrator/orchestrator/api/acquisition.py:137-149
- proxied request: allowed only if `request.state.web_identity` is set (left by `WebBoundaryMiddleware` after valid session + CSRF), else 403 `PROXIED_CALLER` — orchestrator/orchestrator/api/acquisition.py:140-144
- direct request: allowed only at loopback Host, else 403 `NON_LOOPBACK_HOST` — orchestrator/orchestrator/api/acquisition.py:145-149

**_supplier(request, tool, fn, **kw) -> dict** — orchestrator/orchestrator/api/acquisition.py:152-162
- pre: `refuse_unless_mcp_or_web(request)` before anything else — orchestrator/orchestrator/api/acquisition.py:153
- effect: `fn` run via `asyncio.to_thread` with `principal_id=principal_context.current()` — orchestrator/orchestrator/api/acquisition.py:155
- out: fn's dict; `AcquisitionRefused` -> HTTPException `exc.status` `{"code","message"}` plus `Retry-After: str(retry)` header only when `exc.retry_after_s` is set — orchestrator/orchestrator/api/acquisition.py:156-159
- post: one info log "supplier %s source=%s status=%s reason=%s rows=%s" — orchestrator/orchestrator/api/acquisition.py:160-161

## effect surface
- Postgres: one `tx()` per acquire call (assert_owner + status + current_step reads); no table names appear in this file — orchestrator/orchestrator/api/acquisition.py:93-95
- Network: browser/page read inside `acquisition.acquire` — orchestrator/orchestrator/api/acquisition.py:101-102; supplier API calls via `supplier.search/product/freight/warehouses/parse` (actual HTTP + fair-use policy in polymath_shared.acquisition.supplier) — orchestrator/orchestrator/api/acquisition.py:167-188,22-23
- Env: comment documents POLYMATH_ORCH_URL / POLYMATH_API with default `http://127.0.0.1:7200` (how MCP callers address this listener; not read in this file) — orchestrator/orchestrator/api/acquisition.py:65
- Logging: logger name "orchestrator.acquisition" — orchestrator/orchestrator/api/acquisition.py:41

## invariants
INVARIANT: PROXY_HEADERS == ("x-forwarded-for", "x-forwarded-host", "forwarded") — orchestrator/orchestrator/api/acquisition.py:64 [DERIVED]
  fails-if: adding/dropping a header name changes which requests count as relayed in both gates.
INVARIANT: LOOPBACK_HOSTS == frozenset({"127.0.0.1", "localhost", "::1"}) — orchestrator/orchestrator/api/acquisition.py:66 [DERIVED]
  fails-if: any other loopback spelling (e.g. "127.0.0.2") is treated as non-loopback and refused.
INVARIANT: gate-before-state — `refuse_unless_direct(request)` at line 90 precedes `principal_context.current()`/`tx()` at 91-93 — orchestrator/orchestrator/api/acquisition.py:90-93 [DERIVED]
  fails-if: a proxied or DNS-rebound caller reaches run-id probing.
INVARIANT: tx scope (93-95) ends before `asyncio.to_thread(acquisition.acquire, ...)` (101) — no transaction held during the read — orchestrator/orchestrator/api/acquisition.py:93-102 [DERIVED]
  fails-if: moving the read inside the `with` violates the documented no-tx-during-read behavior (docstring 4-5).
INVARIANT: open_harness_action non-None ⇒ status == "awaiting_harness" ∧ row status == "issued" ∧ isinstance(step["harness_action"], dict) — orchestrator/orchestrator/api/acquisition.py:54-61 [DERIVED]
  fails-if: acquire would run a read for a step that is not the issued open action.
INVARIANT: every supplier route funnels through `_supplier`, which calls `refuse_unless_mcp_or_web` exactly once before `fn` — orchestrator/orchestrator/api/acquisition.py:153,167,172,177-178,183,188 [DERIVED]
  fails-if: a supplier route added outside `_supplier` bypasses the MCP/web gate.
INVARIANT: acquire gate never consults `web_identity`; supplier gate requires it for proxied calls — orchestrator/orchestrator/api/acquisition.py:77-85 vs 140-144 [DERIVED]
  fails-if: swapping the gates would either expose the owner-only browser read to web traffic or block the web app's supplier lane.

## determinism & idempotency
determinism: NONDETERMINISTIC (network: browser read in acquisition.acquire orchestrator/orchestrator/api/acquisition.py:101-102 and supplier API calls :155; db: run/step state :93-95; concurrency: asyncio.to_thread)
idempotency: UNSAFE for /adapter/{run_id}/acquire — each call performs an acquisition and yields an `acquisition_id`, and `AcquireRequest` carries no idempotency key (:44-49, :105-108) [INFERRED]; supplier routes are read-only lookups (:13, :22-23) [DERIVED]

## failure behaviour
- No broad except anywhere; every handler maps a named exception.
- `service.NotRunOwner` -> 403 detail "no such run for this principal" — orchestrator/orchestrator/api/acquisition.py:96-97
- `service.UnknownRun` -> 404 detail "unknown adapter run {run_id!r}" — orchestrator/orchestrator/api/acquisition.py:98-99
- `acquisition.AcquisitionRefused` -> `exc.status` with `{"code", "message"}`; acquire path drops `retry_after_s` (:103-104), supplier path converts it to a `Retry-After` header (:156-159)
- Gate refusals: 403 `PROXIED_CALLER` (:80-81, :142-143); 403 `NON_LOOPBACK_HOST` (:83-85, :146-149)
- `loopback_host` swallows `ValueError` from `urlsplit` and returns False — a malformed Host header is treated as non-loopback, i.e. refused — orchestrator/orchestrator/api/acquisition.py:72-74
- supplier log falls back through items/variants/options/warehouses to `[]` — orchestrator/orchestrator/api/acquisition.py:161

## dumb-code flags
- Retry-After asymmetry: `_supplier` forwards `exc.retry_after_s` (:156-159) but acquire's `AcquisitionRefused` mapping does not (:103-104), though both catch the same exception type.
- Magic truncation lengths 300 (target) and 600 (source ids) in the acquire log — orchestrator/orchestrator/api/acquisition.py:106-107
- Duplicated gate code: proxy-header scan + loopback check + near-identical 403 messages appear twice — orchestrator/orchestrator/api/acquisition.py:79-85 vs 140-149
- Singular default `tools: str = "tool research_acquire"` vs plural `"tools " + ...` in the supplier gate — orchestrator/orchestrator/api/acquisition.py:77 vs 134
- Supplier defaults hardcoded at the API layer: `source: str = "cj"` (:114), `quantity: int = 1`, `from_country: str = "CN"` (:125-126)

## refactor notes
- Router is mounted by its only importer, orchestrator/orchestrator/main.py; route paths are the MCP tools' contract (`research_acquire` -> /adapter/{run_id}/acquire :1, :88; supplier.TOOLS -> /supplier/* :134, :165-186) — renaming any path breaks the MCP servers and the web app.
- Error codes "PROXIED_CALLER", "NON_LOOPBACK_HOST" and detail "no such run for this principal" are wire contract for callers — orchestrator/orchestrator/api/acquisition.py:80-84,97,142-147
- The supplier web lane reads `request.state.web_identity`, set by `WebBoundaryMiddleware` — orchestrator/orchestrator/api/acquisition.py:141; renaming that state key silently 403s all proxied supplier traffic.
- PROXY_HEADERS / LOOPBACK_HOSTS are the B-28 DNS-rebinding defense and gate BOTH route families — orchestrator/orchestrator/api/acquisition.py:64,66
- AcquireRequest / Supplier*Request field names are the wire schemas for MCP servers — orchestrator/orchestrator/api/acquisition.py:44-49,112-131
- acquire's ordering (gate -> tx reads -> off-loop read) is documented behavior; reordering re-introduces a transaction across the browser read — orchestrator/orchestrator/api/acquisition.py:4-5,90-102

## VERIFY
```verify
grep -Fq 'PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded")' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})' orchestrator/orchestrator/api/acquisition.py
grep -Fq '@router.post("/adapter/{run_id}/acquire")' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'from_country: str = "CN"' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'request.state, "web_identity", None' orchestrator/orchestrator/api/acquisition.py
test "$(grep -c -F '@router.post("/supplier/' orchestrator/orchestrator/api/acquisition.py)" -ge 4
test "$(grep -c -F 'refuse_unless_mcp_or_web' orchestrator/orchestrator/api/acquisition.py)" -ge 2
```
