# flow: supplier-search
POST /supplier/search: the caller gate (MCP loopback or web boundary), fair-use pacing, the CJ REST client (token cache, 1.1 s pacing, circuit breaker), the Alibaba Agent-Reach handoff, and the one-shape answer the caller always gets.

## hops
| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Route `supplier_search` takes `SupplierSearchRequest` and calls `_supplier(request, "supplier_search", supplier.search, query, source, limit)` | orchestrator/orchestrator/api/acquisition.py:166-167 [DERIVED] | req.query/source/limit -> thread call | bad request body (FastAPI, not shown) |
| 2 | Caller gate `refuse_unless_mcp_or_web`: any PROXY_HEADERS header set -> `web_identity` on request state must exist; else Host header must be loopback | orchestrator/orchestrator/api/acquisition.py:137-149 [DERIVED] | request headers/state -> void | 403 `PROXIED_CALLER` or 403 `NON_LOOPBACK_HOST` |
| 3 | Loopback test: `urlsplit("//"+host).hostname in LOOPBACK_HOSTS` | orchestrator/orchestrator/api/acquisition.py:69-74 [DERIVED] | Host header -> bool | ValueError -> False [DERIVED] |
| 4 | Principal resolved: `principal_context.current()` (None = owner / trusted-local) and passed into the worker thread via `asyncio.to_thread` | orchestrator/orchestrator/api/acquisition.py:155; shared/polymath_shared/principal_context.py:23-25 [DERIVED] | contextvar -> principal_id or None | - |
| 5 | `supplier.search` -> `authorize(principal_id)`: every user allowed; a non-principal-id string refused (defence in depth) | shared/polymath_shared/acquisition/supplier.py:88-93, 211 [DERIVED] | principal_id -> void | 403 `BAD_PRINCIPAL` |
| 6 | Source checked against `SOURCES = {"cj": (cj_api.SITE, "cj_listings"), "alibaba": (agent_reach.ALIBABA, "alibaba_listings")}` | shared/polymath_shared/acquisition/supplier.py:56, 212-213 [DERIVED] | source string -> (site, reader) | 422 `UNKNOWN_SOURCE` |
| 7 | Query normalized by `_query` (service module), limit clamped to `max(1, min(limit, 50))`, default 10 (`SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX = 10, 50`) | shared/polymath_shared/acquisition/supplier.py:58, 214-218 [DERIVED] | query/limit -> q, n | 422 `BAD_LIMIT` on non-numeric |
| 8 | Fair-use admit: per-principal sliding 60 s deque; cap = `POLYMATH_SUPPLIER_RATE_PER_MINUTE` (default 30); owner (None) passes untouched | shared/polymath_shared/acquisition/supplier.py:105-108, 121-134 [DERIVED] | principal_id, env -> void | 429 `SUPPLIER_RATE_LIMITED` with `retry_after_s` |
| 9 | alibaba branch: nothing is read on this host; answer is status `AGENT_REACH_REQUIRED`, `reason_code` `ALIBABA_AGENT_REACH_ONLY`, `fallback` = Agent-Reach commands | shared/polymath_shared/acquisition/supplier.py:223-230 [DERIVED] | q -> handoff answer | never a local read; HUMAN_CHECK appears later on the parse leg |
| 10 | cj branch: client built from env — `client_from_env` returns a `CJClient` only when `CJ_API_KEY` is set, else None -> `code = "CJ_NO_KEY"` | shared/polymath_shared/acquisition/supplier.py:60, 231-235; shared/polymath_shared/acquisition/cj_api.py:294-302 [DERIVED] | env -> CJClient or None | UNAVAILABLE `CJ_NO_KEY` with fallback |
| 11 | `gate.cj_call(principal_id)`: one CJ call in flight per principal, second is refused, never queued | shared/polymath_shared/acquisition/supplier.py:136-151, 237 [DERIVED] | principal_id -> context manager | 429 `SUPPLIER_BUSY` (retry_after 1 s) |
| 12 | `CJListings(client).read(t, n)` runs the CJ read; `ApiFailed` -> typed code via `REASON_CODES`; any other exception -> `CJ_ERROR` + `log.exception` | shared/polymath_shared/acquisition/supplier.py:239-245, 65-67, 180-182 [DERIVED] | Target, n -> raw dict | every failure typed, none raised to the route (except fair use) |
| 13 | Circuit breaker first: an open breaker raises the same `ApiFailed` at once, no network call, reporting `retry_after_s` | shared/polymath_shared/acquisition/cj_api.py:178-184, 195-205 [DERIVED] | _Account.breaker -> ApiFailed | instant `disabled`/`auth`/`rate_limit` failure while held |
| 14 | Token: cached per key until `TOKEN_MARGIN_S = 600` s before expiry; else `POST /authentication/getAccessToken` with `{"apiKey": ...}`; unparsable expiry -> 1 h TTL (`TOKEN_FALLBACK_TTL_S = 3600`) | shared/polymath_shared/acquisition/cj_api.py:52-53, 164-175 [DERIVED] | apiKey -> accessToken | `bad_reply` if answer holds no token |
| 15 | Paced send under per-account `pace` lock: wait `MIN_INTERVAL_S = 1.1` s since last call, timeout `TIMEOUT_S = 20.0`, header `CJ-Access-Token` | shared/polymath_shared/acquisition/cj_api.py:49, 51, 150-162 [DERIVED] | method/path/params -> httpx.Response | `network` on Timeout/TransportError |
| 16 | Answer classified: `1600014` -> `disabled` (never retried, breaker `POLYMATH_CJ_BREAKER_S`); 429/`1600200` -> sleep 2 s then 4 s, else `rate_limit` (breaker 60 s); 401/403/auth codes -> renew token once, else `auth`; quota/`server`/`bad_reply`/`bad_request`/`refused` | shared/polymath_shared/acquisition/cj_api.py:84-89, 186-193, 224-245 [DERIVED] | response -> data or ApiFailed | every class of CJ refusal, each typed |
| 17 | Route read: `GET /product/listV2` with `keyWord`, `page: 1`, size clamped to `SEARCH_SIZE_MAX = 100`, `features: enable_category`; products from `content[].productList` (or flat blocks), total from `totalRecords` | shared/polymath_shared/acquisition/cj_api.py:12-13, 57, 248-261 [DERIVED] | query, size -> (products, total) | `bad_reply` if data is not a dict |
| 18 | Result re-ranked: the search asks for a larger page (at least `SEARCH_PAGE_MIN = 100`) and `rank_by_query` orders by the query's rarest words, log(N/df) weights; ties keep CJ order | shared/polymath_shared/acquisition/cj_api.py:58-61, 70-83 [DERIVED] (that CJListings applies it: [INFERRED] from the SEARCH_PAGE_MIN comment) | products, query -> ordered products | - |
| 19 | `shape(t, raw, ...)` builds the listing view; `status` EMPTY -> `code = "CJ_EMPTY"` | shared/polymath_shared/acquisition/supplier.py:246-248 [DERIVED] | raw -> status/items/sources/completeness | - |
| 20 | Any `code` -> `WHY[code]` text + `HANDOFF` + `agent_reach.fallback(site, q, code, why)`; `CJ_EMPTY` hints Exa may still find CJ pages | shared/polymath_shared/acquisition/supplier.py:68-84, 249-254 [DERIVED] | code, q -> fallback dict | - |
| 21 | Answer returned: `{contract, tool, source, site, query, retrieved_at, status, sources, items, completeness, limitations, reason_code, fallback}` | shared/polymath_shared/acquisition/supplier.py:255-257 [DERIVED] | - -> dict | - |
| 22 | Back in the route: `AcquisitionRefused` -> `HTTPException(status, {code, message})` + `Retry-After` when `retry_after_s` exists | orchestrator/orchestrator/api/acquisition.py:156-159 [DERIVED] | exception -> HTTP error | 429s carry Retry-After |
| 23 | `log.info("supplier %s source=%s status=%s reason_code=%s rows=%s")`, answer returned | orchestrator/orchestrator/api/acquisition.py:160-162 [DERIVED] | out -> log line + dict | - |
| 24 | Fallback loop: the user runs `fallback.commands` on their own machine and sends output to `supplier_parse`, which re-shapes it via `agent_reach.parse`; pages that became no item are listed in `refused` (`HUMAN_CHECK`, `OFF_SITE`, ...); all-verification-page input -> status `HUMAN_CHECK` | shared/polymath_shared/acquisition/supplier.py:82-84, 331-341, 357-358, 421 [DERIVED] | raw Agent-Reach output -> supplier_search shape | 422 `UNKNOWN_SITE`/bad output; HUMAN_CHECK pages |

## state written
- No database, vector store or file is written on this path; all state is in-process. [INFERRED] — no Postgres/Qdrant write appears anywhere in SOURCE for this chain.
- `FAIR_USE = FairUse()`: per-principal deque of call timestamps (`_calls`) and the `_busy` set, under a `threading.Lock` — shared/polymath_shared/acquisition/supplier.py:111-119, 154 [DERIVED].
- `_ACCOUNTS: dict[str, _Account]` keyed by `sha256(key)[:16]`: cached token, `expires_at`, `last_call`, `pace` lock, open `breaker` — shared/polymath_shared/acquisition/cj_api.py:97-114 [DERIVED].
- One log record per call (`supplier supplier_search source=... status=... reason_code=... rows=...`) — orchestrator/orchestrator/api/acquisition.py:160-161 [DERIVED].
- Both stores are process-local: a bounce resets them — shared/polymath_shared/acquisition/supplier.py:24; shared/polymath_shared/acquisition/cj_api.py:21-22 [DERIVED].

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `CJ_API_KEY` | unset | no key -> client None -> `CJ_NO_KEY` UNAVAILABLE with fallback | shared/polymath_shared/acquisition/cj_api.py:297-302 (via supplier.py:201-202, 231-235) [DERIVED] |
| `POLYMATH_SUPPLIER_RATE_PER_MINUTE` | 30 | per-principal supplier calls per minute; whole number >= 1, else default | shared/polymath_shared/acquisition/supplier.py:59, 105-108, 125 [DERIVED] |
| `POLYMATH_CJ_BREAKER_S` | 600.0 | breaker window (s) after `disabled`/`auth` | shared/polymath_shared/acquisition/cj_api.py:55, 300 [DERIVED] |
| `POLYMATH_CJ_RATE_BREAKER_S` | 60.0 | breaker window (s) after `rate_limit` | shared/polymath_shared/acquisition/cj_api.py:56, 301 [DERIVED] |

## failure modes
1. 403 with code `PROXIED_CALLER` -> request carried a proxy header but `request.state.web_identity` is None (no web sign-in/CSRF) -> orchestrator/orchestrator/api/acquisition.py:140-143 [DERIVED].
2. 403 with code `NON_LOOPBACK_HOST` -> direct call whose Host header is not 127.0.0.1/localhost (e.g. a re-bound name) -> orchestrator/orchestrator/api/acquisition.py:145-149, 69-74 [DERIVED].
3. 429 `SUPPLIER_RATE_LIMITED` -> principal hit the per-minute cap; `Retry-After` = seconds until the oldest call ages out of the 60 s window -> shared/polymath_shared/acquisition/supplier.py:129-133; header set at orchestrator/orchestrator/api/acquisition.py:157-159 [DERIVED].
4. 429 `SUPPLIER_BUSY` -> same principal already holds the one in-flight CJ call; never queued -> shared/polymath_shared/acquisition/supplier.py:143-145 [DERIVED].
5. UNAVAILABLE `CJ_NO_KEY` -> `CJ_API_KEY` absent from the environment; answer keeps the shape and hands off to the user's Agent Reach -> shared/polymath_shared/acquisition/supplier.py:60, 233-235, 249-253 [DERIVED].
6. UNAVAILABLE `CJ_API_DISABLED` -> CJ answered code `1600014`; breaker then holds 600 s (default) and every later call fails at once with no network traffic — a fast failure that looks like CJ being down is the breaker -> shared/polymath_shared/acquisition/cj_api.py:224-225, 186-193, 197-200; WHY text at shared/polymath_shared/acquisition/supplier.py:70 [DERIVED].
7. Silent waits: CJ 429/`1600200` is retried after 2 s and 4 s before `CJ_RATE_LIMITED`; a refused token is silently renewed once before `CJ_AUTH` -> shared/polymath_shared/acquisition/cj_api.py:209-235 [DERIVED].
8. Status `AGENT_REACH_REQUIRED` / `ALIBABA_AGENT_REACH_ONLY` -> source `alibaba` is never read on this host; always a handoff, never an error -> shared/polymath_shared/acquisition/supplier.py:223-230 [DERIVED].
9. `CJ_EMPTY` -> CJ answered with no product; fallback still built (Exa may find CJ pages) -> shared/polymath_shared/acquisition/supplier.py:247-248, 251 [DERIVED].
10. `CJ_ERROR` -> the reader itself raised; caught, logged (`log.exception`) and typed like any other failure, so a bug never breaks the shape -> shared/polymath_shared/acquisition/supplier.py:243-245 [DERIVED].
11. 422 `UNKNOWN_SOURCE` / `BAD_LIMIT`; 403 `BAD_PRINCIPAL` -> validation before any CJ work -> shared/polymath_shared/acquisition/supplier.py:212-218, 92-93 [DERIVED].
12. `HUMAN_CHECK` on the parse leg -> every submitted Agent-Reach page was a verification page; `agent_reach.WALLS[host]` note added -> shared/polymath_shared/acquisition/supplier.py:357-358, 366-368, 421 [DERIVED].

## invariants
- INVARIANT: every supplier_search answer — success or failure — carries the full shape `contract, tool, source, site, query, retrieved_at, status, sources, items, completeness, limitations, reason_code, fallback`, with both `reason_code` and `fallback` present (null when not needed) — shared/polymath_shared/acquisition/supplier.py:20-21, 255-257 [DERIVED].
- INVARIANT: a fallback always directs to the user's own Agent Reach commands, never the host browser and never an agent's built-in web search or fetch — shared/polymath_shared/acquisition/supplier.py:64-67, 82-84 [DERIVED].
- INVARIANT: alibaba.com is never read by this host, by any engine or browser — shared/polymath_shared/acquisition/supplier.py:223-230 [DERIVED]. (No SearXNG appears anywhere on this path in SOURCE.)
- INVARIANT: read-only — `ENDPOINTS` is the sign-in plus four reads (`/product/listV2`, `/product/query`, `/logistic/freightCalculate`, `/product/globalWarehouseList`) and is pinned; no order/payment/dispute route exists in the client — shared/polymath_shared/acquisition/cj_api.py:46-48, 15-16 [DERIVED].
- INVARIANT: the key and the token never reach a log, result or error text — `_scrub` replaces both with `[redacted]`; keys come from the environment only — shared/polymath_shared/acquisition/cj_api.py:25, 144-148; shared/polymath_shared/acquisition/supplier.py:27-28 [DERIVED].
- INVARIANT: the owner (principal None) is never rate-limited and never holds a busy slot — shared/polymath_shared/acquisition/supplier.py:71-73, 123-124, 139-140, 187-190 [DERIVED].
- INVARIANT: per key, at most one CJ request at a time, spaced `MIN_INTERVAL_S = 1.1` s (CJ's one-request-a-second rule) — shared/polymath_shared/acquisition/cj_api.py:49, 154-157 [DERIVED].
- INVARIANT: fair-use counters, cached tokens and breakers live in this process only; a bounce resets them — shared/polymath_shared/acquisition/supplier.py:24; shared/polymath_shared/acquisition/cj_api.py:21-22 [DERIVED].

## VERIFY
```verify
grep -Fq 'refuse_unless_mcp_or_web(request)' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'PROXIED_CALLER' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'SUPPLIER_RATE_LIMITED' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'ALIBABA_AGENT_REACH_ONLY' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'MIN_INTERVAL_S = 1.1' shared/polymath_shared/acquisition/cj_api.py
grep -Fq '1600014' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'CJ-Access-Token' shared/polymath_shared/acquisition/cj_api.py
test "$(grep -c -F 'CJ_NO_KEY' shared/polymath_shared/acquisition/supplier.py)" -ge 3
```
