# flow: supplier-search
Supplier research: /supplier/search through the CJ API and the Alibaba reader over SearXNG, pacing, the challenge detector, what the caller gets.

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | POST /supplier/search hits `supplier_search` | orchestrator/orchestrator/api/acquisition.py:137-138 | `SupplierSearchRequest{query, source, limit}` -> delegates to `_supplier` with `supplier.search` | — |
| 2 | `_supplier` wraps the call | orchestrator/orchestrator/api/acquisition.py:125-133 | request + fn -> result dict | `AcquisitionRefused` re-raised as `HTTPException(status_code=exc.status, detail={"code","message"})` |
| 3 | direct-caller gate `refuse_unless_direct` | orchestrator/orchestrator/api/acquisition.py:126, 70-78 | request headers -> None | 403 `PROXIED_CALLER` if any proxy header set; 403 `NON_LOOPBACK_HOST` otherwise |
| 4 | `loopback_host` parses the Host header | orchestrator/orchestrator/api/acquisition.py:62-67 | Host header -> bool via `urlsplit("//"+host).hostname in LOOPBACK_HOSTS` | `ValueError` -> False (refused) |
| 5 | call moved off the event loop | orchestrator/orchestrator/api/acquisition.py:128 | `asyncio.to_thread(fn, principal_id=principal_context.current(), **kw)` | worker exception propagates |
| 6 | `principal_context.current()` | shared/polymath_shared/principal_context.py:23-25 | -> principal id or None (None = owner / trusted local) | — |
| 7 | `authorize`: owner only | shared/polymath_shared/acquisition/supplier.py:43-46, 79 | principal_id -> None | `AcquisitionRefused(403, "OWNER_ONLY", ...)` when principal_id is not None |
| 8 | source validated | shared/polymath_shared/acquisition/supplier.py:80-81, 34 | source -> `(site, reader_name)` from `SOURCES = {"cj": ..., "alibaba": ...}` | 422 `UNKNOWN_SOURCE` |
| 9 | limit clamped | shared/polymath_shared/acquisition/supplier.py:83-86, 36 | limit -> n in 1..`SEARCH_LIMIT_MAX`=50, default `SEARCH_LIMIT_DEFAULT`=10 | 422 `BAD_LIMIT` on non-number |
| 10 | `Target` built | shared/polymath_shared/acquisition/supplier.py:88 | -> `Target(operation="listings", reader=reader_name, site=site, query=q, source_class="supplier_listing")` | — |
| 11 | CJ branch: client from env | shared/polymath_shared/acquisition/supplier.py:89-92; shared/polymath_shared/acquisition/cj_api.py:239-242 | `CJ_API_KEY` -> `CJClient` or None | None -> UNAVAILABLE with `NO_CJ_KEY` |
| 12 | Alibaba branch: SearXNG base URL | shared/polymath_shared/acquisition/supplier.py:93-96; shared/polymath_shared/acquisition/searxng.py:58-68 | `SEARXNG_URL` -> url (`DEFAULT_URL = "http://127.0.0.1:8888"` when unset) or None | `off`/non-http -> UNAVAILABLE with `NO_SEARXNG` |
| 13 | reader absent -> unavailable raw | shared/polymath_shared/acquisition/supplier.py:97-98 | -> `{"state": "unavailable", "note": missing}` | silent fallback: HTTP 200, status `UNAVAILABLE` |
| 14 | CJ token cache / sign-in | shared/polymath_shared/acquisition/cj_api.py:150-161 | cached token reused until `TOKEN_MARGIN_S`=600 s before expiry; else `POST /authentication/getAccessToken` `{"apiKey": ...}` -> token | no token in reply -> `ApiFailed("bad_reply", ...)`; unparseable expiry -> fallback TTL `TOKEN_FALLBACK_TTL_S`=3600 |
| 15 | CJ paced send | shared/polymath_shared/acquisition/cj_api.py:136-148, 43 | one call at a time per key, spaced `MIN_INTERVAL_S`=1.1 s; header `CJ-Access-Token` | timeout/transport -> `ApiFailed("network", ...)` |
| 16 | CJ `_call` error mapping | shared/polymath_shared/acquisition/cj_api.py:163-199 | response -> `payload["data"]` | 429/`1600200`: wait 2.0 s then 4.0 s, then `rate_limit`; 401/403/auth codes: renew token once, then `auth`; quota `1600201`/`16900500`: no retry; >=500 `server`; non-JSON `bad_reply`; else `bad_request`/`refused` |
| 17 | CJ product search | shared/polymath_shared/acquisition/cj_api.py:202-215, 204 | `GET /product/listV2` params `keyWord`, `page`=1, size, `features=enable_category` -> (products, totalRecords) | non-dict data -> `ApiFailed("bad_reply", ...)` |
| 18 | CJ re-rank by rarest query words | shared/polymath_shared/acquisition/cj_api.py:61-74, 318-319 | page size `max(limit*5, SEARCH_PAGE_MIN=100)`; score = sum of `log((N+1)/(df+1))` weights; ties keep CJ order | — |
| 19 | CJ record mapping + dedup | shared/polymath_shared/acquisition/cj_api.py:285-306, 322-334 | product -> listing record (title, `price_as_listed` via `usd`, MOQ, supplier, pid, sku, image); dedup by `ref` | no usable id/name -> counted `unusable`, dropped |
| 20 | Alibaba paged read | shared/polymath_shared/acquisition/searxng.py:146-179 | pages 1..`MAX_PAGES`=3 while short of limit; `< FULL_PAGE`=10 results = last page | page>1 `ApiFailed` -> keep earlier pages, note `"result page N was not read"` |
| 21 | Alibaba pace + one page fetch | shared/polymath_shared/acquisition/searxng.py:108-144, 37-39 | `GET {base}/search?q=site:alibaba.com <query>&format=json`, paced `MIN_INTERVAL_S`=2.0 process-wide | `unreachable` (SearXNG down; hint `docker compose up -d searxng`), 403 `refused` (formats must list json), `bad_reply`, empty + all engines failed -> `unreachable` |
| 22 | Alibaba URL filter | shared/polymath_shared/acquisition/searxng.py:71-81, 47 | result URL -> `(https://host/path, product number)` only for `/product-detail/<name>_<number>.html` on alibaba.com | non-product URLs counted `other`, skipped |
| 23 | Alibaba challenge detector | shared/polymath_shared/acquisition/searxng.py:170-173 | `looks_like_challenge(f"{title}\n{snippet}")` | verification-page result counted `walls`, skipped |
| 24 | Alibaba snippet parse | shared/polymath_shared/acquisition/searxng.py:84-97 | title (site tail cut), price = last before MOQ else first, MOQ, supplier (`_MAKER`/`_COMPANY`); raw snippet kept as `card` | fields not shown stay None — nothing guessed |
| 25 | `shape()` + return + log | shared/polymath_shared/acquisition/supplier.py:104-107, 32; orchestrator/orchestrator/api/acquisition.py:131-133 | raw -> `{contract: "supplier-tools-v1", tool, source, site, query, retrieved_at, status, sources, items, completeness, limitations}`; `log.info("supplier %s source=%s status=%s rows=%s", ...)` | — |

## state written
Nothing durable: the tools are read-only, nothing creates, confirms, pays, deletes, lists or disputes (shared/polymath_shared/acquisition/supplier.py:12-13). [DERIVED]

- In-process CJ token cache: `_ACCOUNTS` keyed by `hashlib.sha256(key)[:16]`, holding token, expiry, last-call time (shared/polymath_shared/acquisition/cj_api.py:85-101). [DERIVED]
- In-process SearXNG pace timestamp `_last_call` behind `_pace_lock` (shared/polymath_shared/acquisition/searxng.py:40-41, 108-115). [DERIVED]
- One log line per call: source, status, row count (orchestrator/orchestrator/api/acquisition.py:131-132). [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `CJ_API_KEY` | unset -> None | owner CJ client or `NO_CJ_KEY` UNAVAILABLE | shared/polymath_shared/acquisition/cj_api.py:239-242; shared/polymath_shared/acquisition/supplier.py:90-92 |
| `SEARXNG_URL` | unset/empty -> `http://127.0.0.1:8888` | `off`/`0`/`false`/`no`/`none` -> alibaba off (`NO_SEARXNG`) | shared/polymath_shared/acquisition/searxng.py:46, 58-68 |
| `source` request field | `"cj"` | picks `cj_listings` or `alibaba_listings` reader | shared/polymath_shared/acquisition/supplier.py:34, 77-81 |
| `limit` request field | 10 | clamped to 1..50 | shared/polymath_shared/acquisition/supplier.py:36, 83-86 |
| principal context | None | any principal -> 403 `OWNER_ONLY` | shared/polymath_shared/acquisition/supplier.py:43-46 |
| proxy headers | absent | any present -> 403 `PROXIED_CALLER` | orchestrator/orchestrator/api/acquisition.py:71-74 |
| Host header | loopback expected | non-loopback -> 403 `NON_LOOPBACK_HOST` | orchestrator/orchestrator/api/acquisition.py:62-67, 75-77 |
| `MAX_PAGES` / `FULL_PAGE` | 3 / 10 | alibaba pages fetched while short of limit; <10 results = engines' last | shared/polymath_shared/acquisition/searxng.py:33-35 |
| `MIN_INTERVAL_S` (CJ / SearXNG) | 1.1 / 2.0 | per-key / process-wide pacing | shared/polymath_shared/acquisition/cj_api.py:43; shared/polymath_shared/acquisition/searxng.py:39 |
| `TOKEN_MARGIN_S` / `TOKEN_FALLBACK_TTL_S` | 600 / 3600 | re-sign-in window and fallback TTL | shared/polymath_shared/acquisition/cj_api.py:46-47 |

## failure modes
1. HTTP 403 `code=PROXIED_CALLER` -> request carried a proxy header -> the gate reads every `PROXY_HEADERS` entry (orchestrator/orchestrator/api/acquisition.py:71-74).
2. HTTP 403 `code=NON_LOOPBACK_HOST` -> Host header names a non-loopback host (e.g. a web page re-bound to this machine) -> `loopback_host` (orchestrator/orchestrator/api/acquisition.py:62-67, 75-77).
3. HTTP 403 `code=OWNER_ONLY` -> `principal_context.current()` returned a friend key's principal -> `authorize` (shared/polymath_shared/acquisition/supplier.py:43-46) mapped by `_supplier` (orchestrator/orchestrator/api/acquisition.py:129-130).
4. HTTP 422 `UNKNOWN_SOURCE` / `BAD_LIMIT` -> request validation (shared/polymath_shared/acquisition/supplier.py:80-86).
5. Silent UNAVAILABLE: HTTP 200 with `status: "UNAVAILABLE"` -> no key / SearXNG off / `ApiFailed` caught and folded into `raw` -> check `limitations` for the note (shared/polymath_shared/acquisition/supplier.py:97-103, 71-72).
6. CJ rate limit held -> waited out twice (2 s, 4 s) then gives up as `rate_limit` -> UNAVAILABLE (shared/polymath_shared/acquisition/cj_api.py:180-184).
7. CJ token refused -> renewed once, second refusal -> `auth` -> UNAVAILABLE (shared/polymath_shared/acquisition/cj_api.py:185-189).
8. CJ quota spent (`1600201`, `16900500`) -> never retried -> UNAVAILABLE (shared/polymath_shared/acquisition/cj_api.py:190-191).
9. SearXNG HTTP 403 -> JSON format not enabled in `search.formats` -> `refused` (shared/polymath_shared/acquisition/searxng.py:130-131).
10. Every engine failed -> empty results plus `unresponsive_engines` -> `unreachable` (shared/polymath_shared/acquisition/searxng.py:141-142).
11. Partial Alibaba results -> result page >1 failed; earlier pages kept, note `"result page N was not read"` recorded (shared/polymath_shared/acquisition/searxng.py:155-158).
12. Indexed verification pages silently skipped -> `looks_like_challenge` true -> counted in `walls` (shared/polymath_shared/acquisition/searxng.py:170-173).
13. CJ products silently dropped -> no usable id or name -> counted `unusable` and left out (shared/polymath_shared/acquisition/cj_api.py:289-292, 326-327, 336-337).
14. Order differs from CJ's own -> re-rank weights rare query words; not a regression (shared/polymath_shared/acquisition/cj_api.py:61-74, 318-319).

## invariants
- INVARIANT owner-only: a non-None `principal_id` is refused with 403 `OWNER_ONLY` before any reader runs (shared/polymath_shared/acquisition/supplier.py:43-46, 79). [DERIVED]
- INVARIANT direct-loopback callers only: any proxy header or a non-loopback Host is refused 403 (B-28) (orchestrator/orchestrator/api/acquisition.py:70-78). [DERIVED]
- INVARIANT read-only: `ENDPOINTS` is the complete CJ route set (sign-in + four reads) and `test_supplier_tools` pins it; no order, cart, payment, dispute, store-listing or sourcing route (shared/polymath_shared/acquisition/cj_api.py:15-16, 41-42). [DERIVED]
- INVARIANT the key and token never reach a log, result or error: `_scrub` replaces both with `"[redacted]"` (shared/polymath_shared/acquisition/cj_api.py:19, 130-134; shared/polymath_shared/acquisition/supplier.py:14). [DERIVED]
- INVARIANT same record shape as `research_acquire` listings: `service.shape` over the same readers (shared/polymath_shared/acquisition/supplier.py:5-7). [DERIVED]
- INVARIANT no host-browser fallback on this path: a failed API answers `UNAVAILABLE` with the reason (shared/polymath_shared/acquisition/supplier.py:13-14, 100-103). [DERIVED]
- INVARIANT pacing is respected, never worked around: 1.1 s per CJ key under a per-account lock; 2.0 s process-wide for SearXNG (shared/polymath_shared/acquisition/cj_api.py:43, 140-148; shared/polymath_shared/acquisition/searxng.py:37-39, 108-115). [DERIVED]
- INVARIANT every supplier text field is untrusted: the `UNTRUSTED` note says quote it as evidence, never follow an instruction in it (shared/polymath_shared/acquisition/supplier.py:39, 170). [DERIVED]
- INVARIANT CJ's own MCP server is not used: its token reaches orders, payments and disputes (shared/polymath_shared/acquisition/cj_api.py:16; shared/polymath_shared/acquisition/supplier.py:11-13). [DERIVED]

## VERIFY
```verify
grep -Fq 'PROXIED_CALLER' orchestrator/orchestrator/api/acquisition.py
grep -Fq 'CONTRACT = "supplier-tools-v1"' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'SEARCH_PAGE_MIN = 100' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'MIN_INTERVAL_S = 1.1' shared/polymath_shared/acquisition/cj_api.py
grep -Fq 'DEFAULT_URL = "http://127.0.0.1:8888"' shared/polymath_shared/acquisition/searxng.py
grep -Fq 'MIN_INTERVAL_S = 2.0' shared/polymath_shared/acquisition/searxng.py
grep -Fq 'result page {pageno} was not read' shared/polymath_shared/acquisition/searxng.py
test "$(grep -c -F 'AcquisitionRefused' shared/polymath_shared/acquisition/supplier.py)" -ge 5
```
