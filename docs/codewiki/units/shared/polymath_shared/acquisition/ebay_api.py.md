# unit: shared/polymath_shared/acquisition/ebay_api.py
anchor: shared/polymath_shared/acquisition/ebay_api.py:1-431

## purpose
Read-only eBay Browse API client that supplies the product-decision report's comparables: current NEW, fixed-price listings on EBAY_US with price in USD, shipping cost, eBay's delivery estimate, location and condition (docstring, shared/polymath_shared/acquisition/ebay_api.py:1-27). Scraping was measured dead (Jina 0/5, HTTP 403 on 2026-11-02), so the host uses the owner's developer keyset via the official API instead (shared/polymath_shared/acquisition/ebay_api.py:3-4). Consumers: orchestrator/orchestrator/api/product_report.py and shared/polymath_shared/product_search/host_data.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| missing | def | (env: Mapping) -> list[str] | shared/polymath_shared/acquisition/ebay_api.py:83-85 | — (module importers: product_report.py, host_data.py) |
| configured | def | (env: Mapping) -> bool | shared/polymath_shared/acquisition/ebay_api.py:88-89 | — |
| not_configured_why | def | (env: Mapping) -> str | shared/polymath_shared/acquisition/ebay_api.py:92-96 | — |
| clean_text | def | (value: Any, n: int) -> str | shared/polymath_shared/acquisition/ebay_api.py:129-132 | — |
| item_url | def | (value: Any) -> str \| None | shared/polymath_shared/acquisition/ebay_api.py:135-148 | — |
| listing | def | (item: Any) -> dict \| None | shared/polymath_shared/acquisition/ebay_api.py:193-208 | — |
| country_code | def | (value: Any) -> str | shared/polymath_shared/acquisition/ebay_api.py:212-216 | — |
| search_filter | def | (country: str) -> str | shared/polymath_shared/acquisition/ebay_api.py:219-221 | — |
| enduser_context | def | (country: str, zip_code: str \| None) -> str | shared/polymath_shared/acquisition/ebay_api.py:224-227 | — |
| EbayClient | class | \_\_init\_\_(client_id, client_secret, ...) / search(query, \*, ship_to="US", limit=25) / breaker() | shared/polymath_shared/acquisition/ebay_api.py:246-423 | — |
| client_from_env | def | (env: Mapping, \*\*kw) -> EbayClient \| None | shared/polymath_shared/acquisition/ebay_api.py:426-431 | — |

Module imports: `polymath_shared.acquisition.listing_apis` (+`ApiFailed`), `polymath_shared.acquisition.service.now_iso` (shared/polymath_shared/acquisition/ebay_api.py:46-47, FACTS.imports).

## contracts

**client_from_env** (shared/polymath_shared/acquisition/ebay_api.py:426-431)
- in: `env` mapping, optional kwargs forwarded to `EbayClient`.
- out: `EbayClient` when both `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` set, else `None` (never raises on unconfigured).
- post: `None` return is the `NOT_CONFIGURED = "EBAY_NOT_CONFIGURED"` signal, documented as not an error (shared/polymath_shared/acquisition/ebay_api.py:57, 427-428).

**EbayClient.\_\_init\_\_** (shared/polymath_shared/acquisition/ebay_api.py:249-268)
- pre: both id and secret non-blank after strip, else `ValueError`; `ship_to_zip` must match `_ZIP` (`[A-Za-z0-9][A-Za-z0-9 -]{1,9}`), else `ValueError` (shared/polymath_shared/acquisition/ebay_api.py:254-258, 76).
- post: instance shares a process-global `_Account` keyed by `sha256(f"{client_id}\0{secret}")[:16]` (shared/polymath_shared/acquisition/ebay_api.py:114-117).
- injectable for tests: `transport`, `sleep`, `clock` (defaults `time.sleep`, `time.monotonic`) (shared/polymath_shared/acquisition/ebay_api.py:250-251).

**EbayClient.search** (shared/polymath_shared/acquisition/ebay_api.py:387-423)
- in: `query` whitespace-collapsed, truncated to `QUERY_MAX = 100`, must be >= 2 chars else `ApiFailed("bad_request", ...)`; `ship_to` must be a 2-letter code; `limit` clamped to `1..SEARCH_LIMIT_MAX` (`50`) (shared/polymath_shared/acquisition/ebay_api.py:65, 391-398, 64).
- out: `{retrieved_at (now_iso), request, total, listings, unusable}`; listings deduped by URL, `unusable` counts summaries lacking title or eBay URL (shared/polymath_shared/acquisition/ebay_api.py:412-423).
- error: raises `ApiFailed` on any typed failure.

**EbayClient.breaker** (shared/polymath_shared/acquisition/ebay_api.py:356-362)
- out: `{reason, detail, retry_after_s}` (rounded to 1 decimal) while held, else `None`.

**listing** (shared/polymath_shared/acquisition/ebay_api.py:193-208)
- in: one Browse item summary mapping.
- out: `{title, url, price_usd, shipping_usd, delivery_min, delivery_max, location, condition, item_id, us_listing}` with per-field `None` allowed; returns `None` without title or eBay item URL (shared/polymath_shared/acquisition/ebay_api.py:194-200).

**clean_text** (shared/polymath_shared/acquisition/ebay_api.py:129-132)
- out: invisible/control chars (`Cc Cf Cs Co Cn`) replaced by space, whitespace collapsed, capped at `n` (shared/polymath_shared/acquisition/ebay_api.py:79, 131-132).

**item_url** (shared/polymath_shared/acquisition/ebay_api.py:135-148)
- out: `https://<host>/<path>` for hosts `ebay.com` or `*.ebay.com` only, query/fragment dropped, path <= `URL_PATH_MAX = 300` matching `_URL_PATH`; else `None` (shared/polymath_shared/acquisition/ebay_api.py:143-148, 66, 77).

## effect surface
- Network: `BASE_URL = "https://api.ebay.com"`; only routes `TOKEN = "/identity/v1/oauth2/token"` (POST, client-credentials) and `SEARCH = "/buy/browse/v1/item_summary/search"` (GET) — `ENDPOINTS = (TOKEN, SEARCH)` is the complete set (shared/polymath_shared/acquisition/ebay_api.py:49-53). One `httpx.Client` per exchange, `timeout=TIMEOUT_S` (`20.0`) (shared/polymath_shared/acquisition/ebay_api.py:285, 59).
- Env read: `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` (`ID_ENV, SECRET_ENV`), no defaults; keyset from environment only (shared/polymath_shared/acquisition/ebay_api.py:56, 26, 426-431).
- Concurrency: process-global `_ACCOUNTS` dict + `_ACCOUNTS_LOCK`, per-keyset `threading.Lock` for pacing (shared/polymath_shared/acquisition/ebay_api.py:110-111, 106).
- Postgres tables read/written: none (FACTS.tables_read, FACTS.tables_written empty). No files, no subprocess visible.
- Headers sent: `X-EBAY-C-MARKETPLACE-ID: EBAY_US`, `X-EBAY-C-ENDUSERCTX: contextualLocation=...` URL-encoded (shared/polymath_shared/acquisition/ebay_api.py:402-403, 224-227).

## invariants
- INVARIANT: min spacing between calls per keyset = `MIN_INTERVAL_S = 1.0` s — shared/polymath_shared/acquisition/ebay_api.py:58, 280-283 [DERIVED]. fails-if: burst calls exceed eBay's default 5,000/day pace assumption and draw HTTP 429.
- INVARIANT: breaker hold after `auth` = `BREAKER_S = 600.0` s > hold after `rate_limit` = `RATE_BREAKER_S = 300.0` s — shared/polymath_shared/acquisition/ebay_api.py:62, 369 [DERIVED]. fails-if: bad keyset hammers eBay with sign-ins every call.
- INVARIANT: cached token reused only while `expires_at - TOKEN_MARGIN_S (300.0) > clock()` — shared/polymath_shared/acquisition/ebay_api.py:60, 343 [DERIVED]. fails-if: expired token in flight causes 401 on every search.
- INVARIANT: response body bytes <= `MAX_RESPONSE_BYTES = 2_000_000` (checked against content-length and while streaming) — shared/polymath_shared/acquisition/ebay_api.py:63, 289-296 [DERIVED]. fails-if: oversized reply is read into memory.
- INVARIANT: `price_usd` accepted only when `0 <= value < 1_000_000` and currency `"USD"` — shared/polymath_shared/acquisition/ebay_api.py:153-159 [DERIVED]. fails-if: non-USD or garbage amounts enter the report.
- INVARIANT: delivery dates accepted only for `2000 <= year <= 2100`, UTC — shared/polymath_shared/acquisition/ebay_api.py:168-174 [DERIVED]. fails-if: nonsense timestamps poison delivery windows.
- INVARIANT: search result count `1 <= n <= SEARCH_LIMIT_MAX = 50` (default `SEARCH_LIMIT = 25`) — shared/polymath_shared/acquisition/ebay_api.py:64, 396 [DERIVED]. fails-if: request rejected by eBay or report overloaded.
- INVARIANT: every request the client can make is in `ENDPOINTS = (TOKEN, SEARCH)`; sold-history Marketplace Insights API never called — shared/polymath_shared/acquisition/ebay_api.py:53, 16 [DERIVED]. fails-if: client gains write/restricted routes.

## determinism & idempotency
determinism: NONDETERMINISTIC (network `httpx.Client` shared/polymath_shared/acquisition/ebay_api.py:285; clock `time.monotonic` and sleep `time.sleep` defaults shared/polymath_shared/acquisition/ebay_api.py:251; env keyset shared/polymath_shared/acquisition/ebay_api.py:56; concurrency via module locks shared/polymath_shared/acquisition/ebay_api.py:106,111). Pure helpers (`clean_text`, `item_url`, `listing`, `country_code`, `search_filter`, `enduser_context`) are deterministic over their inputs.
idempotency: SAFE (only one GET read plus the OAuth token POST; no buys/bids/offers/watches/lists per shared/polymath_shared/acquisition/ebay_api.py:16-17, 53; token caching mutates only in-process state shared/polymath_shared/acquisition/ebay_api.py:341-353).

## failure behaviour
- Every failure surfaces as `ApiFailed(reason, detail)` from `polymath_shared.acquisition.listing_apis` (shared/polymath_shared/acquisition/ebay_api.py:46); `REASON_CODES` maps reason -> typed code: `auth->EBAY_AUTH`, `rate_limit->EBAY_RATE_LIMITED`, `network->EBAY_NETWORK`, `server->EBAY_SERVER_ERROR`, `bad_reply->EBAY_BAD_REPLY`, `bad_request->EBAY_BAD_REQUEST`, `refused->EBAY_REFUSED`, `error->EBAY_ERROR` (shared/polymath_shared/acquisition/ebay_api.py:68-69).
- HTTP 429 -> `rate_limit`, never retried (shared/polymath_shared/acquisition/ebay_api.py:326-327, 18-19).
- Signed 401 -> token dropped and renewed once, then `auth` on repeat; 401/403 -> `auth`; unsigned 400 -> `auth` (shared/polymath_shared/acquisition/ebay_api.py:328-332).
- `httpx.TimeoutException`/`httpx.HTTPError` -> `network` (shared/polymath_shared/acquisition/ebay_api.py:317-320); 5xx -> `server` (shared/polymath_shared/acquisition/ebay_api.py:333-334); non-dict JSON -> `bad_reply` (shared/polymath_shared/acquisition/ebay_api.py:335-336); other non-200 -> `bad_request`/`refused` (shared/polymath_shared/acquisition/ebay_api.py:337-338).
- Open breaker answers `ApiFailed` at once with `retry_after_s`, no network call, no pacing wait (shared/polymath_shared/acquisition/ebay_api.py:376-379, 20-22); a breaker-raised failure never extends the breaker (shared/polymath_shared/acquisition/ebay_api.py:367-368).
- Secrets never reach error text: `_scrub` replaces secret, basic auth, token and client id with `"[redacted]"`; eBay's message is treated as untrusted text (shared/polymath_shared/acquisition/ebay_api.py:271-275, 230-242).
- `client_from_env` swallows nothing: unconfigured returns `None`, caller reports `EBAY_NOT_CONFIGURED` (shared/polymath_shared/acquisition/ebay_api.py:429-430, 57).

## dumb-code flags
- `REASON_CODES` key `"error": "EBAY_ERROR"` has no `raise ApiFailed("error", ...)` anywhere in this file (all raises use other reasons) — consumer must live elsewhere [INFERRED] (shared/polymath_shared/acquisition/ebay_api.py:69).
- `TOKEN_MARGIN_S = 300.0` is a fixed module constant applied inside `_token`, while interval/breaker/max_bytes are constructor-injectable — mixed configurability (shared/polymath_shared/acquisition/ebay_api.py:60, 343 vs 252-253).
- Country validated twice with different outcomes: `country_code` raises `ApiFailed("bad_request")` (shared/polymath_shared/acquisition/ebay_api.py:212-216) while `listing` silently blanks a bad country via the same `_COUNTRY` regex (shared/polymath_shared/acquisition/ebay_api.py:204).
- Magic literals: error-text cap `160` in `_said` (shared/polymath_shared/acquisition/ebay_api.py:237, 241); min token length `8` (shared/polymath_shared/acquisition/ebay_api.py:348); `expires_in` bound `10**7` (shared/polymath_shared/acquisition/ebay_api.py:351); `max_bytes` floor `1024` (shared/polymath_shared/acquisition/ebay_api.py:267).
- `not_configured_why` fallback `missing(env) or [ID_ENV, SECRET_ENV]`: when env IS configured the message still names both vars (shared/polymath_shared/acquisition/ebay_api.py:94).

## refactor notes
- Two importers depend on this module (FACTS.importers): orchestrator/orchestrator/api/product_report.py and shared/polymath_shared/product_search/host_data.py — changing `client_from_env`'s `None` semantics or `listing`'s output keys hits both (shared/polymath_shared/acquisition/ebay_api.py:194, 426-431).
- `listing()` keys are "the report's listing shape" — exact key set is a cross-repo contract (shared/polymath_shared/acquisition/ebay_api.py:194-208).
- `ENDPOINTS` is pinned by `test_ebay_api` per the comment — adding any route requires updating that test (shared/polymath_shared/acquisition/ebay_api.py:52).
- `REASON_CODES` keys map to typed failure codes consumed downstream; renaming a reason changes caller-visible codes (shared/polymath_shared/acquisition/ebay_api.py:67-69).
- Process-global `_ACCOUNTS` means multiple `EbayClient` instances on one keyset share token cache, pacing and breaker — removing it changes rate behavior (shared/polymath_shared/acquisition/ebay_api.py:110-117).
- `SOURCE_NOTE` and `UNTRUSTED` are one-line strings destined for the report's `limitations` — wording is user-visible (shared/polymath_shared/acquisition/ebay_api.py:70-74).

## VERIFY
```verify
grep -Fq 'ENDPOINTS = (TOKEN, SEARCH)' shared/polymath_shared/acquisition/ebay_api.py
grep -Fq 'MIN_INTERVAL_S = 1.0' shared/polymath_shared/acquisition/ebay_api.py
grep -Fq 'MAX_RESPONSE_BYTES = 2_000_000' shared/polymath_shared/acquisition/ebay_api.py
grep -Fq 'BREAKER_S, RATE_BREAKER_S = 600.0, 300.0' shared/polymath_shared/acquisition/ebay_api.py
grep -Fq 'MARKETPLACE = "EBAY_US"' shared/polymath_shared/acquisition/ebay_api.py
test "$(grep -c -F 'raise ApiFailed' shared/polymath_shared/acquisition/ebay_api.py)" -ge 10
! grep -Fq 'sell/inventory' shared/polymath_shared/acquisition/ebay_api.py
```
