# unit: shared/polymath_shared/acquisition/searxng.py
anchor: shared/polymath_shared/acquisition/searxng.py:1-200

## purpose
Reads Alibaba product listings by asking the owner's LOCAL SearXNG instance (`GET {SEARXNG_URL}/search?q=site:alibaba.com <query>&format=json`) and parsing only what the search engines returned: URL, title, snippet. It never opens an alibaba.com page, because alibaba.com puts a human check in front of automated readers of its search page (the R7 run: every call). Owner decision of 2026-09-27. Consumed by the supplier-apis acquisition layer; importers are `shared/polymath_shared/acquisition/_small-modules` and `shared/polymath_shared/acquisition/supplier.py` (FACTS.importers). [DERIVED] — shared/polymath_shared/acquisition/searxng.py:1-12

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `base_url` | def | `(env: Mapping[str, str]) -> str \| None` | shared/polymath_shared/acquisition/searxng.py:58-68 | supplier.py, _small-modules (module importers) |
| `listing_url` | def | `(url: Any) -> tuple[str, str] \| None` | shared/polymath_shared/acquisition/searxng.py:71-81 | supplier.py, _small-modules (module importers) |
| `parse_snippet` | def | `(title: str, snippet: str, slug: str) -> dict[str, Any]` | shared/polymath_shared/acquisition/searxng.py:84-97 | supplier.py, _small-modules (module importers) |
| `SearXNGListings` | class | `(base, *, transport=None, sleep=time.sleep, clock=time.monotonic)`; methods `__init__`, `_pace`, `_page`, `read` | shared/polymath_shared/acquisition/searxng.py:100-199 | supplier.py, _small-modules (module importers) |
| `SearXNGListings.reader` / `.label` | class attrs | `"alibaba_listings"` / `LABEL = "SearXNG search"` | shared/polymath_shared/acquisition/searxng.py:103 | callers selecting the backend |

## contracts

**`base_url(env)`** — shared/polymath_shared/acquisition/searxng.py:58-68
- in: mapping; reads key `SEARXNG_URL`, stripped.
- out: `None` when the raw value lowercased is in `OFF = frozenset({"off", "0", "false", "no", "none"})` (:46), when `urlsplit` raises, or when scheme is not `http`/`https` or hostname missing (:61-68).
- post: otherwise returns the URL with trailing `/` stripped; unset/empty falls back to `DEFAULT_URL = "http://127.0.0.1:8888"` (:63).

**`listing_url(url)`** — shared/polymath_shared/acquisition/searxng.py:71-81
- in: any value, stringified and stripped.
- out: `None` unless scheme http/https AND host `== "alibaba.com"` or endswith `.alibaba.com` AND path fullmatches `_PRODUCT_PATH` = `/product-detail/([^/?#]+?)_(\d{8,})\.html` (:47, :78-80).
- post: on match returns `(f"https://{host}{parts.path}", m.group(2))` — query and fragment dropped, product number is the 8+-digit group (:81).

**`parse_snippet(title, snippet, slug)`** — shared/polymath_shared/acquisition/searxng.py:84-97
- in: title/snippet strings; slug used only as fallback title (`slug.replace("-", " ")`) (:89).
- out: dict keys `"title"` (≤300 chars, `_TITLE_TAIL` site tail cut off), `"price_as_listed"` (last `_PRICE` match before the MOQ, else the first anywhere in the snippet; else `None`), `"minimum_order_as_listed"` (`f"{moq.group(1)} {moq.group(2)}"` or `None`), `"supplier"` (`_MAKER` else `_COMPANY` group 1, else `None`), `"card"` (snippet whitespace-normalized, ≤300 chars) (:89-97).
- post: nothing guessed — what the snippet does not show stays `None` (:87-88).

**`SearXNGListings.read(target, limit)`** — shared/polymath_shared/acquisition/searxng.py:146-199
- in: `Target` (uses `target.query`), int limit.
- out: `{"state": "ok", "retrieved_at": now_iso(), "records": [...], "total": None, "complete": None, "order": "the search engines' own order, merged by SearXNG", "backend_notes": notes}` (:198-199).
- post: each record is `{"kind": "listing", "ref": <product number>, "url": <normalized url>, "text": <summary line>, "published_at": None, "precision": "none", "listing": <parse_snippet dict>}` (:180-181); duplicates by product number skipped via `seen` (:169-170, :175).

## effect surface
- Network: one `httpx.Client` GET per result page to `{self.base}/search` with `params = {"q": f"site:{SITE} {query}", "format": "json"}` (+ `pageno` when > 1), header `Accept: application/json`, timeout `TIMEOUT_S = 20.0` — shared/polymath_shared/acquisition/searxng.py:31, :119-125.
- Env flag: `SEARXNG_URL` (default `http://127.0.0.1:8888` via `DEFAULT_URL`; `off`/`0`/`false`/`no`/`none` disables → `base_url` returns `None`) — shared/polymath_shared/acquisition/searxng.py:28, :46, :59-63.
- Sleep: `time.sleep` for pacing; `time.monotonic` clock — shared/polymath_shared/acquisition/searxng.py:105, :112-114.
- Process-shared state: `_pace_lock` (threading.Lock) and `_last_call` module globals — shared/polymath_shared/acquisition/searxng.py:40-41, :108-115.
- Postgres tables read/written: none (FACTS `tables_read`/`tables_written` empty). No files, no subprocess.

## invariants

INVARIANT: seconds between two SearXNG searches in this process ≥ `MIN_INTERVAL_S` = `2.0` — shared/polymath_shared/acquisition/searxng.py:39, :108-115 [DERIVED]
  fails-if: engine countermeasures — a burst had Brave suspend SearXNG for 180 s and DuckDuckGo / Qwant show checks (:36-37).

INVARIANT: result pages read per `read()` call ≤ `MAX_PAGES` = `3` — shared/polymath_shared/acquisition/searxng.py:35, :152 [DERIVED]
  fails-if: pagination loop stops early, listings stay under `limit` on sparse queries.

INVARIANT: every emitted record URL is `https://{host}{path}` with host under `"alibaba.com"` and path matching `/product-detail/<name>_<8+digits>.html` — shared/polymath_shared/acquisition/searxng.py:47, :78-81 [DERIVED]
  fails-if: non-product results (category/showroom pages) leak into records as listings.

INVARIANT: `"ref"` values are unique within one `read()` (dedup by product-number `seen` set) — shared/polymath_shared/acquisition/searxng.py:169-175 [DERIVED]
  fails-if: the same product on a later page or twice on one page is recorded twice.

INVARIANT: `"total"` and `"complete"` in the return dict are always `None` — shared/polymath_shared/acquisition/searxng.py:198 [DERIVED]
  fails-if: a caller relying on totals for completeness paging misbehaves.

INVARIANT: HTTP request timeout ≤ `TIMEOUT_S` = `20.0` — shared/polymath_shared/acquisition/searxng.py:31, :124 [DERIVED]
  fails-if: a hung SearXNG blocks the reader past its own budget.

INVARIANT: `"title"` and `"card"` are ≤ 300 chars — shared/polymath_shared/acquisition/searxng.py:96 [DERIVED]
  fails-if: oversized snippet text reaches record consumers unchanged.

## determinism & idempotency
determinism: NONDETERMINISTIC (network call `httpx.Client` — shared/polymath_shared/acquisition/searxng.py:124 and FACTS.nondeterminism; clock `time.monotonic`/`time.sleep` — :105, :112-114; `now_iso()` wall clock — :198; concurrency via shared `_pace_lock`/`_last_call` — :40-41; search-engine results vary by run).
idempotency: SAFE (GET-only requests, no tables/files written per FACTS; only the in-memory pacing timestamp mutates — shared/polymath_shared/acquisition/searxng.py:108-115).

## failure behaviour
`ApiFailed` codes raised by `_page`, all from shared/polymath_shared/acquisition/searxng.py:117-144:
- `"unreachable"` — `httpx.TimeoutException` (:127), other `httpx.TransportError` (message suggests `docker compose up -d searxng`, :129), or every engine failed with an empty result list (:141-143).
- `"refused"` — HTTP 403 (message: `search.formats must list json`, :131) or any other status < 500 (:132-133).
- `"server"` — status ≥ 500 (:133).
- `"bad_reply"` — body not JSON (:136-137) or no `results` list (:138-140).

In `read()`: an `ApiFailed` on page 1 is re-raised (:155-157); on a later page it is swallowed into the note `f"result page {pageno} was not read ({exc})"` and earlier pages' records are kept (:158-159). Non-product results and challenge-page texts (`looks_like_challenge`) are dropped but counted into `backend_notes` (:163-174, :192-195). Unresponsive engines are listed in notes (:141, :197). Per the module contract, on `ApiFailed` "the host browser reads the site as before, said and counted (`listing_apis`)" — shared/polymath_shared/acquisition/searxng.py:10-11.

## dumb-code flags
- Magic number `300` in three different roles: `title[:300]`/`text[:300]` (:96) and engine-failure joins `[:300]` at :143 and :197. [DERIVED]
- `FULL_PAGE = 10` (:36) assumes engines return exactly 10 results per page; a short-but-last page stops pagination (:185) — if an engine returns fewer by policy, pagination ends early. [INFERRED from :33-36, :185]
- `"state": "ok"` is hardcoded even when a later result page failed (`page_error`) — a partial read still reports ok (:198, :190-191). [DERIVED]
- `OFF` matches `"0"`, `"false"`, `"no"`, `"none"`, `"off"` case-insensitively after strip (:60-61, :46) — `SEARXNG_URL="None"` (Python-repr string) also disables. [INFERRED: `raw.lower() in OFF` matches the literal string "none"]
- `_page` builds the failed-engines string twice (once for the exception at :143, once for notes at :197) with the same `[:300]` truncation. [DERIVED]
- `DEFAULT_URL` duplicates knowledge of the compose service address also encoded in the error hint `docker compose up -d searxng` (:5, :129). [DERIVED]

## refactor notes
- Importers `shared/polymath_shared/acquisition/_small-modules` and `shared/polymath_shared/acquisition/supplier.py` (FACTS.importers) break if `base_url`, `listing_url`, `parse_snippet`, `SearXNGListings`, `LABEL`, or the `reader = "alibaba_listings"` identifier (:103) are renamed.
- The `ApiFailed` reason strings (`"unreachable"`, `"refused"`, `"server"`, `"bad_reply"`, :127-143) are the routing contract for the listing_apis host-browser fallback (:10-11); changing them changes fallback behaviour in the caller.
- Record shape `{"kind": "listing", "ref", "url", "text", "published_at": None, "precision": "none", "listing"}` (:180-181) and `parse_snippet` keys `"title"`, `"price_as_listed"`, `"minimum_order_as_listed"`, `"supplier"`, `"card"` (:96-97) are consumed by `read`'s text builder (:178-179) and downstream importers.
- `_PRODUCT_PATH` (:47) mirrors the pattern of `adapters/ecommerce/python/sourcing_exa.py` per the docstring (:7-8); change one, check the other.
- `_pace` uses module globals `_last_call`/`_pace_lock` — "one pace for every SearXNGListings" (:108-109); removing the process-wide lock re-enables the burst behaviour that got Brave to suspend SearXNG (:36-37).

## VERIFY
```verify
grep -Fq 'DEFAULT_URL = "http://127.0.0.1:8888"' shared/polymath_shared/acquisition/searxng.py
grep -Fq 'MIN_INTERVAL_S = 2.0' shared/polymath_shared/acquisition/searxng.py
grep -Fq 'reader, label = "alibaba_listings", LABEL' shared/polymath_shared/acquisition/searxng.py
grep -Fq '"q": f"site:{SITE} {query}", "format": "json"' shared/polymath_shared/acquisition/searxng.py
! grep -Fq 'import requests' shared/polymath_shared/acquisition/searxng.py
test "$(grep -c -F 'raise ApiFailed(' shared/polymath_shared/acquisition/searxng.py)" -ge 7
```
