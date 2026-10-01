# unit: shared/polymath_shared/acquisition/cj_api.py
anchor: shared/polymath_shared/acquisition/cj_api.py:1-389

## purpose
Read-only Python client for CJ Dropshipping's official API 2.0 (`developers.cjdropshipping.com/api2.0/v1`), used by the acquisition layer's supplier APIs. Covers sign-in/token cache, product search, product details, freight quote and warehouse list; maps CJ payloads into the browser backend's listing shape. Owner decision of 2026-09-27: supplier APIs, read-only — no order, cart, payment, dispute, store-listing or sourcing route. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:1-19,37-42

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `query_words` | def | `(query) -> tuple[str, ...]` | shared/polymath_shared/acquisition/cj_api.py:56-58 | — |
| `rank_by_query` | def | `(products, query, name_of) -> list[dict]` | shared/polymath_shared/acquisition/cj_api.py:61-74 | — |
| `CJClient` | class | `__init__(api_key, *, base_url=BASE_URL, transport=None, sleep=time.sleep, clock=time.monotonic, wall=time.time)`; methods `__init__ _scrub _send _token _call search product freight warehouses` | shared/polymath_shared/acquisition/cj_api.py:116-236 | — |
| `client_from_env` | def | `(env, **kw) -> CJClient \| None` | shared/polymath_shared/acquisition/cj_api.py:239-242 | — |
| `valid_id` | def | `(value) -> str \| None` | shared/polymath_shared/acquisition/cj_api.py:246-249 | — |
| `product_url` | def | `(pid, name) -> str` | shared/polymath_shared/acquisition/cj_api.py:252-255 | — |
| `usd` | def | `(value) -> str \| None` | shared/polymath_shared/acquisition/cj_api.py:258-266 | — |
| `listing_record` | def | `(p) -> dict \| None` | shared/polymath_shared/acquisition/cj_api.py:285-306 | — |
| `CJListings` | class | `__init__(client)`; `read(target, limit) -> dict`; attrs `reader="cj_listings"`, `label=LABEL` | shared/polymath_shared/acquisition/cj_api.py:309-340 | — |
| `product_view` | def | `(d) -> {"product", "variants"}` | shared/polymath_shared/acquisition/cj_api.py:343-365 | — |
| `freight_view` | def | `(o) -> dict` | shared/polymath_shared/acquisition/cj_api.py:378-382 | — |
| `warehouse_view` | def | `(w) -> dict` | shared/polymath_shared/acquisition/cj_api.py:385-388 | — |

Module-level importers (FACTS.importers, per-symbol use not in FACTS): `shared/polymath_shared/acquisition/_small-modules`, `shared/polymath_shared/acquisition/supplier.py`. [DERIVED] FACTS.importers

## contracts

**`client_from_env(env, **kw)`** — shared/polymath_shared/acquisition/cj_api.py:239-242
- in: env mapping holding `CJ_API_KEY`.
- out: `CJClient(key, **kw)` when the key is non-empty after `.strip()`, else `None`; key read from environment only.
- pre: `CJClient.__init__` raises `ValueError("a CJ API key is required")` on blank key. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:122-123

**`CJClient.search(query, size)`** — shared/polymath_shared/acquisition/cj_api.py:202-215
- in: free-text query, desired size.
- out: `(products, total)`; `size` clamped `max(1, min(int(size), SEARCH_SIZE_MAX))`; params `keyWord, page=1, features="enable_category"`; total is `totalRecords` when an int, else `None`.
- post: raises `ApiFailed("bad_reply", "CJ's product search held no data")` when `data` is not a dict.

**`CJClient.product(pid)`** — shared/polymath_shared/acquisition/cj_api.py:217-219
- out: details dict or `None` (GET `/product/query`, param `pid`).

**`CJClient.freight(vid, to_country, quantity, from_country)`** — shared/polymath_shared/acquisition/cj_api.py:221-228
- out: list of option dicts; `[]` when data is `None`; `ApiFailed("bad_reply", "CJ's freight answer is not a list of options")` on non-list. Body: `{"startCountryCode", "endCountryCode", "products": [{"quantity", "vid"}]}`.

**`CJClient.warehouses()`** — shared/polymath_shared/acquisition/cj_api.py:230-236
- out: list of dicts; `[]` on `None` data; `ApiFailed("bad_reply", "CJ's warehouse answer is not a list")` on non-list.

**`rank_by_query(products, query, name_of)`** — shared/polymath_shared/acquisition/cj_api.py:61-74
- in: product dicts, query, name accessor.
- out: products ordered by sum of word weights `log((len(names)+1)/(df+1))`; name spaces removed before matching; ties keep CJ's order (stable sort by index). Returns `list(products)` unchanged when no words or no products.

**`listing_record(p)`** — shared/polymath_shared/acquisition/cj_api.py:285-306
- in: one CJ search product dict.
- out: `{"kind": "listing", "ref": pid, "url", "text", "published_at": None, "precision": "none", "listing": {...}}` in the shape of `opencli.OpenCLIBackend._listing`; `None` when no usable id and name.

**`CJListings.read(target, limit)`** — shared/polymath_shared/acquisition/cj_api.py:317-340
- in: `Target` (uses `target.query`), limit.
- out: `{"state": "ok", "retrieved_at", "records", "total", "complete", "order": "CJ's own best-match order", "backend_notes"}`; searches with `max(limit * 5, SEARCH_PAGE_MIN)` size, re-ranks, dedupes by `ref`, truncates at `limit`; `complete` is `len(records) >= total` or `None`; notes always include `SOURCE_NOTE` and the ranking note.

**`valid_id(value)`** — shared/polymath_shared/acquisition/cj_api.py:246-249
- out: the trimmed string when it fullmatches `_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{5,63}")`, else `None`.

**`usd(value)`** — shared/polymath_shared/acquisition/cj_api.py:258-266
- out: `"US$<lo>"` or `"US$<lo>-<hi>"` from the first/last of at most 2 numbers; `None` for `None`/bool, no numbers, >2 numbers, or first number `<= 0`.

**`product_url(pid, name)`** — shared/polymath_shared/acquisition/cj_api.py:252-255
- out: `https://cjdropshipping.com/product/<slug>-p-<pid>.html`; slug = lowercased name, apostrophes dropped, non-alnum → `-`, clipped to 120 chars, fallback `"product"`.

## effect surface
- Network: `httpx.Client` to `BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"`; only `ENDPOINTS = (TOKEN, SEARCH, PRODUCT, FREIGHT, WAREHOUSES)` may be called. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:37-42,145
- Env: `CJ_API_KEY` (default `null`), read only in `client_from_env`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:240-241
- Process-global state: `_ACCOUNTS: dict[str, _Account]` keyed by `hashlib.sha256(key)[:16]`, guarded by `_ACCOUNTS_LOCK`; per-account `pace` lock. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:91-101
- Postgres tables: none read, none written (FACTS `tables_read`/`tables_written` empty). Files, Qdrant, subprocess: none in SOURCE.

## invariants
INVARIANT: per-key call spacing >= `MIN_INTERVAL_S` = `1.1` seconds — shared/polymath_shared/acquisition/cj_api.py:43,140-148 [DERIVED]
  fails-if: two calls inside 1.1 s breach CJ's one-request-a-second limit; CJ answers 429 / code 1600200.
INVARIANT: rate-limit retries are exactly `RATE_LIMIT_WAITS_S = (2.0, 4.0)`, then `ApiFailed("rate_limit")` — shared/polymath_shared/acquisition/cj_api.py:44,180-184 [DERIVED]
  fails-if: extra/longer waits change worst-case latency and the pinned give-up message.
INVARIANT: token reused only while `expires_at - TOKEN_MARGIN_S(600) > wall()`; unparsable/missing expiry falls back to `TOKEN_FALLBACK_TTL_S = 3600` — shared/polymath_shared/acquisition/cj_api.py:46-47,150-160 [DERIVED]
  fails-if: stale token sent on every call → auth refuse → one forced re-sign-in per call.
INVARIANT: success == HTTP 200 and (`code` absent or `code == 200`) — shared/polymath_shared/acquisition/cj_api.py:196-199 [DERIVED]
  fails-if: any other combination is misread as success and bad data flows into listing records.
INVARIANT: at most one token renewal per `_call` (`renewed` flag) — shared/polymath_shared/acquisition/cj_api.py:165,185-189 [DERIVED]
  fails-if: infinite sign-in loop on a permanently refused key.
INVARIANT: quota codes (1600201, 16900500) are never retried — shared/polymath_shared/acquisition/cj_api.py:190-191 [DERIVED]
  fails-if: retrying a spent quota burns the rate budget for nothing.
INVARIANT: `SEARCH_SIZE_MAX` == `SEARCH_PAGE_MIN` == `100` — shared/polymath_shared/acquisition/cj_api.py:48,52 [DERIVED]
  fails-if: if they diverge, `CJListings.read` pages smaller than the route maximum, shrinking `rank_by_query`'s df pool.
INVARIANT: api key and cached token never appear in message/error text — both replaced with `"[redacted]"` by `_scrub` — shared/polymath_shared/acquisition/cj_api.py:130-134 [DERIVED]
  fails-if: secret leaks into `ApiFailed` messages reachable by callers.
INVARIANT: `rank_by_query` ties keep CJ's own order (sort key `(-scores[i], i)`) — shared/polymath_shared/acquisition/cj_api.py:73 [DERIVED]
  fails-if: reordering ties breaks the documented "CJ's own order decides ties".

## determinism & idempotency
determinism: NONDETERMINISTIC (network via `httpx.Client` at shared/polymath_shared/acquisition/cj_api.py:145 per FACTS.nondeterminism; injected `sleep`/`clock`/`wall` time functions at shared/polymath_shared/acquisition/cj_api.py:119-121; thread-shared `_ACCOUNTS` at shared/polymath_shared/acquisition/cj_api.py:94). Pure helpers (`query_words`, `rank_by_query`, `valid_id`, `usd`, `product_url`, `*_view`, `listing_record`) are deterministic on their inputs. [DERIVED]
idempotency: SAFE — all four reads are GETs plus `POST /logistic/freightCalculate`, documented as a calculation that creates nothing. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:12-16

## failure behaviour
All failures surface as `ApiFailed` (imported from `polymath_shared.acquisition.listing_apis`, shared/polymath_shared/acquisition/cj_api.py:34), raised in `CJClient._call`:
- `httpx.TimeoutException` → `ApiFailed("network", "CJ did not answer in time")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:170-171
- `httpx.TransportError` → `ApiFailed("network", "CJ could not be reached (<type>)")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:172-173
- HTTP 429 or code 1600200 → wait `2.0` s then `4.0` s → `ApiFailed("rate_limit", "CJ's rate limit still held after waiting 2 s and 4 s")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:180-184
- HTTP 401/403 or AUTH_CODES {1600001, 1600002, 1600003, 1601000} → one silent re-sign-in, else `ApiFailed("auth", ...)`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:185-189
- QUOTA_CODES {1600201, 16900500} → `ApiFailed("quota", ...)`, no retry. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:190-191
- HTTP >= 500 → `ApiFailed("server", "CJ answered HTTP <n>")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:192-193
- Non-dict JSON → `ApiFailed("bad_reply", ...)`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:194-195
- Other non-success → `ApiFailed("bad_request")` when code in PARAM_CODES {1600300, 16900403, 16900205}, else `ApiFailed("refused")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:196-198
- Sign-in without a token string → `ApiFailed("bad_reply", "CJ's sign-in answer held no access token")`. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:156-158
- `CJClient.__init__` on blank key → `ValueError("a CJ API key is required")` (not ApiFailed). [DERIVED] shared/polymath_shared/acquisition/cj_api.py:122-123
- `CJListings.read` silently drops unusable search hits (counted in a backend note) instead of failing. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:323-337

## dumb-code flags
- `SEARCH_SIZE_MAX = 100` and `SEARCH_PAGE_MIN = 100` are two names for the same literal, one file apart. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:48,52
- `_first` evaluates `_clip(p.get(k), 300)` twice per key (once for the truthiness test, once for the value). [DERIVED] shared/polymath_shared/acquisition/cj_api.py:282
- String-typed counters compared as strings: `moq == "1"`, `moq != "0"` on `_whole` output. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:296
- `usd` silently drops any price holding more than 2 numbers (`len(nums) > 2`), e.g. a 3-part range. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:263
- `warehouse_view` reads id from two keys (`id` else `areaId`) — dual-key fallback duplicated inline. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:386
- `search` keeps a dead-ish branch for "a flat list, as the older route answered". [DERIVED] shared/polymath_shared/acquisition/cj_api.py:212-213

## refactor notes
- `ENDPOINTS` is pinned by `test_supplier_tools`; adding any route (order/cart/payment/dispute/sourcing) breaks that pin. CJ's own MCP server is deliberately not used. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:15-16,41-42
- `listing_record`'s output keys must stay identical to `opencli.OpenCLIBackend._listing`'s shape; the browser backend depends on them. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:286-306
- `CJListings.read`'s result dict is consumed by `service.shape` (reader `cj_listings`, label `LABEL`); changing keys/notes is a cross-unit change. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:310-340
- `_scrub`'s redaction contract (key and token → `"[redacted]"`) must hold in every error path; callers rely on no secret in logs/results/errors. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:19,130-134
- Rate pacing, token margin and wait constants encode CJ's live limits (1 req/s, ~180-day tokens); retuning them changes live behaviour, not just tests. [DERIVED] shared/polymath_shared/acquisition/cj_api.py:4-10,43-47
- Importers to update on any signature change: `shared/polymath_shared/acquisition/supplier.py` and `shared/polymath_shared/acquisition/_small-modules`. [DERIVED] FACTS.importers

## VERIFY
```verify
grep -Fq 'MIN_INTERVAL_S = 1.1' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'RATE_LIMIT_WAITS_S = (2.0, 4.0)' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'TOKEN_FALLBACK_TTL_S = 3600' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'SEARCH_PAGE_MIN = 100' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'CJ-Access-Token' shared/polymath_shared/acquisition/cj_api.py
! grep -Fq 'import requests' shared/polymath_shared/acquisition/cj_api.py
test "$(grep -c -F 'ApiFailed' shared/polymath_shared/acquisition/cj_api.py)" -ge 10
```
