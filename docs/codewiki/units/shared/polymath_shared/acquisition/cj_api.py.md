# unit: shared/polymath_shared/acquisition/cj_api.py
anchor: shared/polymath_shared/acquisition/cj_api.py:1-449

## purpose
Read-only client for CJ Dropshipping's official API 2.0 (supplier APIs, owner decision of 2026-09-27): sign-in, product search, product details, freight quote, warehouse list — nothing that writes. shared/polymath_shared/acquisition/cj_api.py:1-16 [DERIVED]
Maps CJ answers into the browser backend's listing shape (`opencli.OpenCLIBackend._listing`) for `service.shape`; consumed by the acquisition layer. shared/polymath_shared/acquisition/cj_api.py:345-346,369-370 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| CJClient | class | (api_key, base_url, transport, sleep, clock, wall, breaker_s, rate_breaker_s) -> client | cj_api.py:129-141 | — |
| client_from_env | def | (env, **kw) -> CJClient \| None | cj_api.py:294-302 | — |
| CJListings | class | (client) -> reader; .read(target, limit) -> dict | cj_api.py:369-400 | — |
| listing_record | def | (p) -> dict \| None | cj_api.py:345-366 | — |
| product_view | def | (d) -> {product, variants} | cj_api.py:403-425 | — |
| freight_view | def | (o) -> dict | cj_api.py:438-442 | — |
| warehouse_view | def | (w) -> dict | cj_api.py:445-448 | — |
| query_words | def | (query) -> tuple[str, ...] | cj_api.py:65-67 | — |
| rank_by_query | def | (products, query, name_of) -> list | cj_api.py:70-83 | — |
| valid_id | def | (value) -> str \| None | cj_api.py:306-309 | — |
| product_url | def | (pid, name) -> str | cj_api.py:312-315 | — |
| usd | def | (value) -> str \| None | cj_api.py:318-326 | — |

Module imported by: `shared/polymath_shared/acquisition/supplier.py`, `shared/polymath_shared/acquisition/_small-modules` (FACTS.importers). Imports in: `listing_apis.ApiFailed`, `service.Target`, `service.now_iso` (FACTS.imports).

## contracts
**client_from_env(env, **kw)** — cj_api.py:294-302
- in: mapping; key = `env.get("CJ_API_KEY")` stripped.
- out: `CJClient(key, **kw)` when key non-empty, else `None`.
- post: `kw["breaker_s"]` = `_seconds(env[POLYMATH_CJ_BREAKER_S], 600.0)`, `kw["rate_breaker_s"]` = `_seconds(env[POLYMATH_CJ_RATE_BREAKER_S], 60.0)` via `setdefault`.

**CJClient.search(query, size)** — cj_api.py:248-261
- in: query text, size int.
- call: `GET /product/listV2` params `keyWord=query, page=1, size=max(1, min(int(size), 100)), features="enable_category"`.
- out: `(products, total)`; products from `content[].productList` dicts, or flat blocks having `id`/`pid`; `total` = `totalRecords` only when an int (not bool), else `None`.
- errors: `ApiFailed("bad_reply", ...)` when `data` is not a dict.

**CJClient.product(pid)** — cj_api.py:263-265
- call: `GET /product/query` params `pid`.
- out: `data` dict when non-empty, else `None`.

**CJClient.freight(vid, to_country, quantity, from_country)** — cj_api.py:267-274
- call: `POST /logistic/freightCalculate` body `{startCountryCode, endCountryCode, products: [{quantity, vid}]}` (docstring: a calculation, creates nothing — cj_api.py:13-14).
- out: list of dict options; `[]` when data is `None`; `ApiFailed("bad_reply")` when not a list.

**CJClient.warehouses()** — cj_api.py:276-282
- call: `GET /product/globalWarehouseList`; out: list of dicts or `[]`.

**CJListings.read(target, limit)** — cj_api.py:377-400
- in: `Target` (uses `target.query`), limit int.
- flow: `search(query, max(limit * 5, SEARCH_PAGE_MIN=100))` → `rank_by_query` over `nameEn or productNameEn` → `listing_record` per product, dedupe by `ref`, stop at `limit`.
- out: `{"state": "ok", "retrieved_at": now_iso(), "records", "total", "complete": len(records) >= total (None when total is None), "order": "CJ's own best-match order", "backend_notes": [SOURCE_NOTE, ranking note, optional unusable-count note]}`.
- pre: `limit` products only counted after passing `listing_record` (unusable ones counted, dropped).

**listing_record(p)** — cj_api.py:345-366
- pre: needs `valid_id(p["id"] or p["pid"])` (regex `[0-9A-Za-z][0-9A-Za-z-]{5,63}`, cj_api.py:93) and a name; else returns `None`.
- out: `{"kind": "listing", "ref": pid, "url", "text", "published_at": None, "precision": "none", "listing": {...}}` with title, `price_as_listed`, `minimum_order_as_listed`, `supplier`, discount, category, image, product_id, sku, `listed_by_stores`, `warehouse_inventory`.

**rank_by_query(products, query, name_of)** — cj_api.py:70-83
- word weight = `math.log((len(names) + 1) / (df[w] + 1))`; name spaces removed before matching; ties keep CJ's order (stable sort by `(-score, i)`).
- returns input unchanged (copy) when no words or no products.

**usd(value)** — cj_api.py:318-326
- in: number, `"11.85"`, range `"0.97-4.08"` or `"2.83 -- 3.74"`.
- out: `"US$11.85"` / `"US$0.97-4.08"`; `None` for `None`/bool, no digits, >2 numbers, or first number <= 0.

## effect surface
- Network: `httpx.Client(transport=..., timeout=TIMEOUT_S)` at cj_api.py:159; base `BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"` (cj_api.py:43); routes `ENDPOINTS = (TOKEN, SEARCH, PRODUCT, FREIGHT, WAREHOUSES)` = `/authentication/getAccessToken`, `/product/listV2`, `/product/query`, `/logistic/freightCalculate`, `/product/globalWarehouseList` (cj_api.py:45-48).
- Env flags: `CJ_API_KEY` = None (cj_api.py:297); `POLYMATH_CJ_BREAKER_S` = 600.0, `POLYMATH_CJ_RATE_BREAKER_S` = 60.0 (cj_api.py:56,300-301).
- Postgres/Qdrant: none (FACTS.tables_read, tables_written empty).
- Process-global state: `_ACCOUNTS: dict[str, _Account]` keyed by `hashlib.sha256(key)[:16]`, guarded by `_ACCOUNTS_LOCK`; per-account `threading.Lock` `pace` (cj_api.py:103,107-114). A process bounce resets the breaker (cj_api.py:21-22).
- Secret scrubbing: `_scrub` replaces the key and cached token with `"[redacted]"` in all error text (cj_api.py:144-148,223).

## invariants
INVARIANT: request size ≤ `SEARCH_SIZE_MAX` (100) — `max(1, min(int(size), SEARCH_SIZE_MAX))` cj_api.py:250,57 [DERIVED]
  fails-if: CJ rejects oversized pages; search returns `bad_request`.
INVARIANT: token reused only while `expires_at - TOKEN_MARGIN_S (600) > wall()` — cj_api.py:166,52 [DERIVED]
  fails-if: expired token sent → auth path renews once (cj_api.py:232-234).
INVARIANT: inter-call spacing per key = `MIN_INTERVAL_S` (1.1) — cj_api.py:154-157,49 [DERIVED]
  fails-if: CJ returns 1600200 / HTTP 429; waits 2.0 then 4.0 then `ApiFailed("rate_limit")` (cj_api.py:226-230).
INVARIANT: breaker window(disabled|auth) = `BREAKER_S` (600.0), window(rate_limit) = `RATE_BREAKER_S` (60.0), any other reason = 0.0 — cj_api.py:191,55 [DERIVED]
  fails-if: hammering a dead account; while open every call raises at once with `retry_after_s` (cj_api.py:196-204).
INVARIANT: `CJListings.read` asks for `max(limit * 5, SEARCH_PAGE_MIN=100)` — cj_api.py:378,61 [DERIVED]
  fails-if: too-small page → ranking pool too thin; distinctive-word reordering degrades.
INVARIANT: token renewed at most once per `_request` (flag `renewed`) — cj_api.py:209,232-234 [DERIVED]
  fails-if: infinite renew loop on persistent 401.
INVARIANT: breaker-raised `ApiFailed` never re-trips the breaker (`retry_after_s is not None` guard) — cj_api.py:189-190 [DERIVED]
  fails-if: breaker window extended forever by its own refusals.
INVARIANT: `len(records) <= limit` and refs unique — cj_api.py:389-394 [DERIVED]
INVARIANT: success ⇔ HTTP 200 and (`code` 200 or `code` absent) — cj_api.py:242-245 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (network `httpx.Client` cj_api.py:159; clocks `time.monotonic`/`time.time` injected cj_api.py:133-134; shared `_ACCOUNTS` across threads cj_api.py:107-108).
idempotency: SAFE — five read routes only (cj_api.py:47-48); freight `POST` is documented as creating nothing (cj_api.py:13-14).

## failure behaviour
All failures raise `ApiFailed(reason, detail)` from `listing_apis` (cj_api.py:40); never a raw httpx error escapes.
| reason | trigger | behaviour | anchor |
|---|---|---|---|
| network | `httpx.TimeoutException` / `httpx.TransportError` | no retry | cj_api.py:214-217 |
| disabled | code in `{1600014}` | never retried; trips 600 s breaker | cj_api.py:224-225,86 |
| rate_limit | HTTP 429 or code `1600200` | sleep 2.0 then 4.0, then raise; trips 60 s breaker | cj_api.py:226-230,50,87 |
| auth | HTTP 401/403 or code in `{1600001, 1600002, 1600003, 1601000}` | one token renewal, then raise; trips 600 s breaker | cj_api.py:231-235,84 |
| quota | code in `{1600201, 16900500}` | not retried | cj_api.py:236-237,88 |
| server | HTTP ≥ 500 | no retry | cj_api.py:238-239 |
| bad_reply | non-JSON, missing data/token/non-list | no retry | cj_api.py:171-172,240-241,252-253,272-273,280-281 |
| bad_request | code in `{1600300, 16900403, 16900205}` | no retry | cj_api.py:242-244,89 |
| refused | any other non-200 code/status | no retry | cj_api.py:242-244 |
Open breaker: `_call` raises immediately, no network call, no pacing wait, detail states seconds remaining (cj_api.py:196-204).

## dumb-code flags
- `SEARCH_SIZE_MAX = 100` and `SEARCH_PAGE_MIN = 100`: same literal, two constants, cap vs floor — cj_api.py:57,61 [DERIVED]
- `TOKEN_MARGIN_S = 600` (int) vs `BREAKER_S = 600.0` (float): equal value, unrelated meaning — cj_api.py:52,55 [DERIVED]
- `_clip(value, n=160)` default 160 is overridden at every call site (8/40/64/100/120/200/300/500) — cj_api.py:125-126 [DERIVED]
- `_first` computes `_clip(p.get(k), 300)` twice per key — cj_api.py:341-342 [DERIVED]
- `DISABLED_CODES` is a single-member frozenset `{1600014}` — cj_api.py:86 [DERIVED]
- Slug built with double `.strip("-")` around `[:120]` — cj_api.py:314 [DERIVED]
- `product_view` images hard-capped `[:10]`; weight clipped to 40 chars — cj_api.py:407,410 [DERIVED]

## refactor notes
- `ENDPOINTS` is pinned by `test_supplier_tools`; no order/cart/payment/dispute/store-listing/sourcing route can be added without breaking the pin — cj_api.py:15-16,47-48 [DERIVED]
- `listing_record`'s output shape mirrors `opencli.OpenCLIBackend._listing`; `CJListings.read` feeds `service.shape` — both consumers must track any field rename — cj_api.py:345-346,369-370 [DERIVED]
- Module imported by `shared/polymath_shared/acquisition/supplier.py` and `_small-modules`; signature changes ripple there (FACTS.importers). [DERIVED]
- All `CJClient` instances with the same key share one `_Account` (token, pacing, breaker) process-wide — splitting state breaks the 1.1 s spacing — cj_api.py:141,107-114 [INFERRED: shared dict keyed by key hash]
- Tests inject `transport`, `sleep`, `clock`, `wall` (no network); keep those constructor kwargs — cj_api.py:130-134 [DERIVED]
- CJ's own MCP server deliberately not used: its token reaches orders, payments, disputes — cj_api.py:15-16 [DERIVED]

## VERIFY
```verify
grep -Fq 'BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'MIN_INTERVAL_S = 1.1' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'RATE_LIMIT_WAITS_S = (2.0, 4.0)' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'BREAKER_ENV, RATE_BREAKER_ENV = "POLYMATH_CJ_BREAKER_S", "POLYMATH_CJ_RATE_BREAKER_S"' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'enable_category' shared/polymath_shared/acquisition/cj_api.py
! grep -Fq 'createOrder' shared/polymath_shared/acquisition/cj_api.py
test "$(grep -c -F 'raise ApiFailed(' shared/polymath_shared/acquisition/cj_api.py)" -ge 10
```
