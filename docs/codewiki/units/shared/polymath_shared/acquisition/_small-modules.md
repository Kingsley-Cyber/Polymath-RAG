# unit: shared/polymath_shared/acquisition/_small-modules
anchor: shared/polymath_shared/acquisition/__init__.py:1-9

## purpose
Package doc names the parts: `service` (contract + policy: owner only, open research step, fixed read-only catalog, budget), `opencli` (host-browser backend), `listing_apis` (supplier official API in front of that browser), `challenge` (detects verification walls, never solves), `supplier` (read-only tool policy) — shared/polymath_shared/acquisition/__init__.py:1-6 [DERIVED]. Since PRODUCT-SEARCH-E2E (2026-11-01), alibaba.com goes through the user's own Agent Reach on the user's machine; `searxng` keeps only the alibaba.com product-page URL check — shared/polymath_shared/acquisition/__init__.py:6-8, shared/polymath_shared/acquisition/searxng.py:3-12 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| ApiFailed | class | (reason: str, detail: str, *, retry_after_s: float \| None = None) | listing_apis.py:26-33 | — |
| counts | def | () -> dict[str, dict[str, Any]] | listing_apis.py:50-53 | — |
| ListingAPIs | class | (browser: Backend, apis: Mapping[str, Any]) | listing_apis.py:56-60 | — |
| ListingAPIs.status | method | () -> dict[str, Any] | listing_apis.py:62-67 | catalog (shows it under `host.listing_apis`) — listing_apis.py:11 [DERIVED] |
| ListingAPIs.read | method | (target: Target, limit: int) -> dict[str, Any] | listing_apis.py:69-81 | — |
| configured | def | (env: Mapping[str, str]) -> dict[str, Any] | listing_apis.py:96-104 | — |
| wrap | def | (browser: Backend, env: Mapping[str, str]) -> Backend | listing_apis.py:107-110 | — |
| listing_url | def | (url: Any) -> tuple[str, str] \| None | searxng.py:23-33 | `agent_reach` parser — searxng.py:11 [DERIVED] |
| product_slug | def | (url: str) -> str \| None | searxng.py:36-42 | `agent_reach` parser — searxng.py:11 [DERIVED] |
| _count | def | (reader: str, outcome: str, reason: str \| None = None) -> dict | listing_apis.py:40-47 | private |

Package importers (FACTS.importers, per-symbol breakdown not given): orchestrator/orchestrator/api/acquisition.py, shared/polymath_shared/acquisition/cj_api.py, shared/polymath_shared/acquisition/service.py, shared/polymath_shared/acquisition/supplier.py, workers/workers/adapter_step_worker.py — shared/polymath_shared/acquisition/__init__.py:1-9 [INFERRED: FACTS.importers].

## contracts
**wrap(browser, env)** — shared/polymath_shared/acquisition/listing_apis.py:107-110
- out: `ListingAPIs(browser, apis)` iff `configured(env)` is non-empty; else the same `browser` object ("today's backend, untouched").
- post: no API configured ⇒ backend identity and behaviour preserved.

**configured(env)** — shared/polymath_shared/acquisition/listing_apis.py:96-104
- in: environment mapping only; CJ enabled via `CJ_API_KEY` through `cj_api.client_from_env(env)` (:101).
- out: `{}` or `{"cj_listings": cj_api.CJListings(client)}` (:103).
- lazy import of `cj_api` inside the body (:99).

**ListingAPIs.read(target, limit)** — shared/polymath_shared/acquisition/listing_apis.py:69-81
- pre: `target.reader` not in `self.apis` ⇒ returns exactly `self.browser.read(target, limit)` (:70-72).
- out: `api.read` result verbatim on success (:74, :81); `ApiFailed` ⇒ `_fall_back(target, limit, api.label, exc.reason, exc.detail)` (:75-76); any other exception ⇒ logged then `_fall_back(..., "error", type(exc).__name__)` (:77-79).
- post: success bumps `api_reads` via `_count(target.reader, "api_reads")` (:80).

**ListingAPIs._fall_back(target, limit, label, reason, detail)** — shared/polymath_shared/acquisition/listing_apis.py:83-93
- post: counts `fallbacks` + reason first (:84), logs warning (:85-86), builds note `f"the {label} could not answer ({reason}: {detail}); the host browser read {target.site} instead"` (:87), prepends it: `raw["backend_notes"] = [note, *(raw.get("backend_notes") or [])]` (:92).
- out on browser failure too: `{"state": "unavailable", "note": f"the read failed ({type(exc).__name__}: {str(exc)[:200]})", "retrieved_at": now_iso()}` (:90-91).

**ListingAPIs.status()** — shared/polymath_shared/acquisition/listing_apis.py:62-67
- out: copy of `browser.status()` plus `listing_apis` per reader: `{"api": api.label, **counts}`.

**counts()** — shared/polymath_shared/acquisition/listing_apis.py:50-53
- out: lock-held snapshot with fresh inner dicts; mutating the result cannot affect `_COUNTS`.

**ApiFailed** — shared/polymath_shared/acquisition/listing_apis.py:26-33
- message: `f"{reason}: {detail}"` (:32); attrs `reason`, `detail`, `retry_after_s`.
- `retry_after_s` set only when the API was NOT called (open circuit breaker in `cj_api`) — :28-29; `detail` never holds a key or token — :28.

**listing_url(url)** — shared/polymath_shared/acquisition/searxng.py:23-33
- in: any value; stringified, stripped (:26).
- out: `(f"https://{host}{parts.path}", m.group(2))` only when scheme ∈ `("http", "https")`, host `== "alibaba.com"` or `endswith(".alibaba.com")`, and path fullmatches `_PRODUCT_PATH`; else `None` (:30-33). Query and fragment dropped.
- regex: `r"/product-detail/([^/?#]+?)_(\d{8,})\.html"`, `re.IGNORECASE` (:20).

**product_slug(url)** — shared/polymath_shared/acquisition/searxng.py:36-42
- out: group(1) of the same regex (e.g. `Waterproof-Camera-Rain-Cover`), else `None`.

## effect surface
- Postgres/Qdrant: none; import blocks are only `logging`, `threading`, `collections.abc.Mapping`, `typing.Any` (listing_apis.py:16-19) and `re`, `typing.Any`, `urllib.parse.urlsplit` (searxng.py:15-17) [DERIVED].
- Network: indirect — `api.read(target, limit)` at listing_apis.py:74 (CJ official API) and `self.browser.read(...)` at listing_apis.py:72, :89 [DERIVED calls; endpoints live in cj_api/service].
- Env: `CJ_API_KEY` (default unset ⇒ no CJ API, `wrap` returns the bare browser) — listing_apis.py:5, :97, :101-103 [DERIVED].
- Process-global mutable state: `_COUNTS = {}` + `_COUNT_LOCK` — listing_apis.py:36-37; reset by a process bounce — listing_apis.py:41.
- Logging: logger `"polymath.acquisition"` — listing_apis.py:23; `log.exception` at :78, `log.warning` at :85.
- Clock: `now_iso()` in the both-failed note — listing_apis.py:91.

## invariants
INVARIANT: every `_fall_back` call increments `fallbacks` by 1 and, when `reason` is given, `fallback_reasons[reason]` by 1 — listing_apis.py:43-46, :84 [DERIVED]
  fails-if: catalog `host.listing_apis` undercounts; fallbacks hide from status.
INVARIANT: every read/write of `_COUNTS` happens under `_COUNT_LOCK` — listing_apis.py:42, :51 [DERIVED]
  fails-if: concurrent readers lose counts.
INVARIANT: `wrap` returns the identical `browser` object iff `configured(env)` is empty — listing_apis.py:109-110 [DERIVED]
  fails-if: API-less hosts silently get wrapped behaviour.
INVARIANT: reader not in `self.apis` ⇒ `read` returns exactly `self.browser.read(target, limit)` — listing_apis.py:70-72 [DERIVED]
  fails-if: non-API readers change code path.
INVARIANT: `listing_url` accepts only scheme `http`/`https` AND (`host == "alibaba.com"` OR `host.endswith(".alibaba.com")`) — searxng.py:30 [DERIVED]
  fails-if: lookalike domains pass, or genuine subdomains get rejected.
INVARIANT: product number matches `\d{8,}` (≥ 8 digits), path match case-insensitive — searxng.py:20 [DERIVED]
  fails-if: shorter product IDs misclassified as non-listing URLs.
INVARIANT: a fallback result always carries `backend_notes` with the fallback note first — listing_apis.py:92 [DERIVED]
  fails-if: downstream `limitations` line (listing_apis.py:10-11) goes missing.

## determinism & idempotency
determinism: searxng DETERMINISTIC (pure `re`/`urlsplit`, no clock/network/env — searxng.py:15-17, :23-42) [DERIVED]; listing_apis NONDETERMINISTIC (network via `api.read` listing_apis.py:74 and `browser.read` :72/:89; env `CJ_API_KEY` :97; clock `now_iso()` :91; concurrency via `_COUNT_LOCK` :37) [DERIVED]
idempotency: UNSAFE for `ListingAPIs.read` — each call mutates `_COUNTS` (listing_apis.py:40-47, :80, :84) so `counts()` output changes per call; SAFE for `listing_url`/`product_slug` (pure functions — searxng.py:23-42)

## failure behaviour
- `except ApiFailed` at listing_apis.py:75-76: reason/detail propagate into `_fall_back`; caller sees the browser result, never the exception [DERIVED].
- Broad `except Exception` at listing_apis.py:77 (FACTS: SWALLOWED — log, return `self._fall_back(target, limit, api.label, ...)`): a reader's own bug is `log.exception`-ed, then converted to fallback with reason `"error"` and detail `type(exc).__name__` — "never a silent 500" (:77-79) [DERIVED].
- Broad `except Exception` at listing_apis.py:90 (FACTS: handled — assign): browser read failed too ⇒ `raw = {"state": "unavailable", "note": ..., "retrieved_at": now_iso()}`, note still prepended to `backend_notes` so both reasons are said (:90-92) [DERIVED].
- Stable `ApiFailed.reason` words: `unreachable, network, auth, disabled, quota, rate_limit, bad_request, refused, bad_reply, server, error` — listing_apis.py:27-28 [DERIVED].
- No error codes raised by searxng; it returns `None` on any non-match (searxng.py:29, :31-33, :39-40) [DERIVED].

## dumb-code flags
- Magic `8` in `\d{8,}` product-number minimum, no named constant — searxng.py:20 [DERIVED].
- Magic truncation `str(exc)[:200]` — listing_apis.py:91 [DERIVED].
- Zero-counts literal `{"api_reads": 0, "fallbacks": 0, "fallback_reasons": {}}` duplicated at listing_apis.py:43 and :65 [DERIVED].
- Magic reader key `"cj_listings"` set at listing_apis.py:103, looked up via `self.apis.get(target.reader)` at :70 — must equal `Target.reader` values produced elsewhere [INFERRED: coupling visible in the get/set pair].
- Inconsistent lint suppression: `except Exception` at listing_apis.py:90 carries `# noqa: BLE001`, the one at :77 does not [DERIVED].
- Dead infra (docstring-flagged, code already gone): compose.yaml service `searxng`, `deployment/searxng/settings.yml`, `SEARXNG_URL`/`SEARXNG_SECRET` in `.env.example` unused by code — searxng.py:8-9 [DERIVED].

## refactor notes
- Five files import this package (FACTS.importers): orchestrator/orchestrator/api/acquisition.py, cj_api.py, service.py, supplier.py, workers/workers/adapter_step_worker.py — renaming any public symbol hits all — shared/polymath_shared/acquisition/__init__.py:1-9 [INFERRED: FACTS.importers, no per-symbol breakdown].
- `status()` output key `listing_apis` feeds the catalog display under `host.listing_apis` — listing_apis.py:11, :65; renaming breaks the catalog.
- `backend_notes` entries reach `limitations` in every state — listing_apis.py:10-11, :92; downstream state consumers depend on the list shape.
- Reader key `"cj_listings"` couples `configured()` to `Target.reader` producers — listing_apis.py:70 vs :103.
- Do not reintroduce host-side alibaba search: owner decision PRODUCT-SEARCH-E2E 2026-11-01 ("alibaba is strictly agent reach") — searxng.py:3-5, listing_apis.py:6-8.
- Removing the unused searxng compose service/settings is a separate owner decision, not a code fix — searxng.py:9.
- `wrap`'s identity guarantee (same `browser` object when no APIs) — listing_apis.py:110; callers may rely on it.

## VERIFY
```verify
grep -Fq 'class ApiFailed(Exception):' shared/polymath_shared/acquisition/listing_apis.py
grep -Fq 'apis["cj_listings"] = cj_api.CJListings(client)' shared/polymath_shared/acquisition/listing_apis.py
grep -Fq 'return ListingAPIs(browser, apis) if apis else browser' shared/polymath_shared/acquisition/listing_apis.py
grep -Fq 'SITE = "alibaba.com"' shared/polymath_shared/acquisition/searxng.py
grep -Eq 'd\{8,\}' shared/polymath_shared/acquisition/searxng.py
! grep -Fq 'import requests' shared/polymath_shared/acquisition/listing_apis.py
test "$(grep -c -F 'backend_notes' shared/polymath_shared/acquisition/listing_apis.py)" -ge 2
```
