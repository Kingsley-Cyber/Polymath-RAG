# unit: shared/polymath_shared/acquisition/supplier.py
anchor: shared/polymath_shared/acquisition/supplier.py:1-373

## purpose
Read-only supplier lookup tools (`supplier_search`, `supplier_product`, `supplier_freight`, `supplier_warehouses`, `supplier_parse`) for every Polymath user — the owner, an MCP principal, or a web-signed-in user — against CJ Dropshipping's official REST API, with an Agent Reach handoff when the host cannot answer. shared/polymath_shared/acquisition/supplier.py:1-28 [DERIVED]
Nothing here creates, confirms, pays, deletes or disputes; the host never calls Exa/Jina and never uses the host browser; CJ keys come from the environment only and never reach a result, error or log. shared/polymath_shared/acquisition/supplier.py:25-28 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| authorize | def | (principal_id: str \| None) -> None | shared/polymath_shared/acquisition/supplier.py:88-93 | — |
| FairUseRefused | class | (code, message, retry_after_s: int) -> 429 refusal | shared/polymath_shared/acquisition/supplier.py:97-102 | — |
| rate_per_minute | def | (env: Mapping \| None) -> int | shared/polymath_shared/acquisition/supplier.py:105-108 | — |
| FairUse | class | (clock: Callable[[], float] = time.monotonic); .admit(principal_id, env) -> None; .cj_call(principal_id) -> ctx manager | shared/polymath_shared/acquisition/supplier.py:111-151 | — |
| search | def | (principal_id, query, source="cj", limit=10, env, cj, fair_use) -> dict | shared/polymath_shared/acquisition/supplier.py:206-257 | — |
| product | def | (principal_id, product_id, env, cj, fair_use) -> dict | shared/polymath_shared/acquisition/supplier.py:261-283 | — |
| freight | def | (principal_id, variant_id, country, quantity=1, from_country="CN", env, cj, fair_use) -> dict | shared/polymath_shared/acquisition/supplier.py:286-309 | — |
| warehouses | def | (principal_id, env, cj, fair_use) -> dict | shared/polymath_shared/acquisition/supplier.py:312-327 | — |
| parse | def | (principal_id, site, raw_text, env, fair_use) -> dict | shared/polymath_shared/acquisition/supplier.py:331-373 | — |

Module imported by (file level, per FACTS.importers): `orchestrator/orchestrator/api/acquisition.py`, `workers/workers/adapter_step_worker.py`. Per-symbol call sites unknown.

## contracts

**search** — shared/polymath_shared/acquisition/supplier.py:206-257
- in: `query` (validated by `service._query`), `source` in `{"cj", "alibaba"}` (default `"cj"`), `limit` default `10` clamped to `[1, 50]`. [DERIVED] :212-216
- pre: `authorize(principal_id)`; `UNKNOWN_SOURCE` (422) if source not in `SOURCES`; `BAD_LIMIT` (422) on non-numeric limit; `fair_use.admit` before any CJ work. [DERIVED] :211-220
- out: `{contract, tool, source, site, query, retrieved_at, status, sources, items, completeness, limitations, reason_code, fallback}`; status `OK/PARTIAL/EMPTY/UNAVAILABLE` (cj) or `AGENT_REACH_REQUIRED` (alibaba). [DERIVED] :202-210, :227-230
- post: `fallback` is set whenever the host could not give CJ listings (every CJ failure and `EMPTY`) and always for alibaba, else `None`. [DERIVED] :249-253, :222-230
- alibaba path: nothing is read on this host; `reason_code = "ALIBABA_AGENT_REACH_ONLY"`, `fallback` from `agent_reach.fallback`. [DERIVED] :223-230

**product** — shared/polymath_shared/acquisition/supplier.py:261-283
- in: `product_id` validated by `_id` via `cj_api.valid_id` (6–64 letters/digits/hyphens) else 422 `BAD_ID`. [DERIVED] :162-166, :265
- out: `{contract, tool, source, product_id, retrieved_at, status, reason_code, product, variants, limitations}`; status `OK/NOT_FOUND/UNAVAILABLE`. [DERIVED] :263, :278-281
- post: `UNAVAILABLE` carries `_product_fallback(pid, code)` (find the product page on cjdropshipping.com with the user's own Agent Reach); `NOT_FOUND` and `OK` carry `fallback: None`. [DERIVED] :270-276, :278-281

**freight** — shared/polymath_shared/acquisition/supplier.py:286-309
- in: `variant_id` (`_id`), `country` and `from_country` (default `"CN"`) two-letter ISO via `_COUNTRY.fullmatch`, `quantity` int in `[1, 10000]` (bool rejected). [DERIVED] :284-294
- out: `{contract, tool, source, request, retrieved_at, status, reason_code, options, limitations}`; status `OK/EMPTY/UNAVAILABLE`; `fallback` always null (no user-side equivalent). [DERIVED] :288, :299-308

**warehouses** — shared/polymath_shared/acquisition/supplier.py:312-327
- out: `{contract, tool, source, retrieved_at, status, reason_code, warehouses, limitations}`; status `OK/EMPTY/UNAVAILABLE`; `fallback` null. [DERIVED] :314, :320-321

**parse** — shared/polymath_shared/acquisition/supplier.py:331-373
- in: `site` resolved by `agent_reach.site_of` (alibaba.com / cjdropshipping.com or source name) else 422 `UNKNOWN_SITE`; `raw_text` cleaned by `agent_reach.clean_text`. [DERIVED] :339-345
- out: the `supplier_search` shape plus `tool_class`, `tool_trace`, `refused` (codes `HUMAN_CHECK, OFF_SITE, NOT_A_PRODUCT_PAGE, DUPLICATE, OVER_LIMIT`), `next` (Jina commands per product after an Exa search). [DERIVED] :333-337, :369-373
- post: status `HUMAN_CHECK` when every page was a verification page and no items resulted; Polymath opens no page. [DERIVED] :357-358, :337

## effect surface
- Network: CJ REST API via `cj_api.CJClient` — `CJListings(client).read` :239, `client.product` :273, `client.freight` :302, `client.warehouses` :323. No Exa/Jina/host-browser calls from this host. [DERIVED] :17-18, :305-313
- Env: `POLYMATH_SUPPLIER_RATE_PER_MINUTE` = 30 default :59, :105-108; `CJ_API_KEY` read via `cj_api.client_from_env` :202 (missing key → `NO_CJ_KEY` :60).
- In-process state: module singleton `FAIR_USE = FairUse()` :154; guarded by `threading.Lock` :119.
- Postgres/Qdrant: none (FACTS.tables_read and tables_written empty). Files, subprocesses: none.

## invariants
INVARIANT: supplier calls per principal in any 60.0 s sliding window <= `rate_per_minute` (default 30) — shared/polymath_shared/acquisition/supplier.py:121-134 [DERIVED]
  fails-if: `FairUseRefused("SUPPLIER_RATE_LIMITED", ..., wait)` with `Retry-After` = `ceil(60.0 - (now - calls[0]))`
INVARIANT: CJ calls in flight per principal <= 1 — shared/polymath_shared/acquisition/supplier.py:136-151 [DERIVED]
  fails-if: `FairUseRefused("SUPPLIER_BUSY", ..., 1)`; never queued
INVARIANT: owner (principal_id None) passes `admit` and `cj_call` untouched — shared/polymath_shared/acquisition/supplier.py:123-124, :139-141 [DERIVED]
  fails-if: owner would be rate-limited like a principal
INVARIANT: search result count n = `max(1, min(limit, 50))` — shared/polymath_shared/acquisition/supplier.py:216 [DERIVED]
  fails-if: CJ asked for more than its page allows or limit 0 slips through
INVARIANT: freight quantity in `[1, 10000]`, booleans rejected — shared/polymath_shared/acquisition/supplier.py:292-293 [DERIVED]
  fails-if: 422 `BAD_QUANTITY`
INVARIANT: `FairUseRefused.retry_after_s >= 1` — shared/polymath_shared/acquisition/supplier.py:102 [DERIVED]
  fails-if: route would send `Retry-After: 0`
INVARIANT: every search result where `reason_code is not None` also sets `fallback` — shared/polymath_shared/acquisition/supplier.py:249-253 [DERIVED]
  fails-if: user gets a typed failure with no handoff commands
INVARIANT: every tool result carries both `reason_code` and `fallback` keys (null when not needed) — shared/polymath_shared/acquisition/supplier.py:20-21, :270, :299, :320, :369-373 [DERIVED]
  fails-if: consumers switch on missing keys

## determinism & idempotency
determinism: NONDETERMINISTIC (network: CJ API :239/:273/:302/:323; clock: `time.monotonic` default in `FairUse` :115; env: rate :107 and CJ_API_KEY :202; concurrency: `threading.Lock` :119)
idempotency: SAFE (read-only; no writes, files or subprocesses — but each call, including `parse`, consumes fair-use budget via `admit` :220, :267, :296, :317, :346)

## failure behaviour
- Broad `except Exception` (FACTS.fallbacks, line 243): only around the CJ listings read in `search` — logged via `log.exception("supplier search: the CJ reader raised")`, converted to `reason_code = "CJ_ERROR"`; caller sees status `UNAVAILABLE`, never the exception. shared/polymath_shared/acquisition/supplier.py:243-245 [DERIVED]
- `ApiFailed` → `_failed` maps `exc.reason` through `REASON_CODES` (default `"CJ_ERROR"`) into `reason_code` + limitation. shared/polymath_shared/acquisition/supplier.py:65-67, :180-182 [DERIVED]
- `FairUseRefused` subclasses `AcquisitionRefused` with HTTP 429 plus `retry_after_s`; codes `SUPPLIER_RATE_LIMITED` :132, `SUPPLIER_BUSY` :144. [DERIVED]
- Refusals raised: 403 `BAD_PRINCIPAL` :93, 422 `UNKNOWN_SOURCE` :213, `BAD_LIMIT` :218, `BAD_ID` :165, `BAD_COUNTRY` :172, `BAD_QUANTITY` :293, `UNKNOWN_SITE` :341. [DERIVED]
- `agent_reach.BadOutput` in `parse` is re-raised as `AcquisitionRefused(exc.status, exc.code, exc.message)`. shared/polymath_shared/acquisition/supplier.py:344-345, :349-350 [DERIVED]
- `product`/`freight`/`warehouses` catch only `ApiFailed`; any other exception from `client.product`/`client.freight`/`client.warehouses` propagates to the caller. shared/polymath_shared/acquisition/supplier.py:272-276, :301-304, :322-325 [DERIVED]

## dumb-code flags
- Asymmetric error handling: the "reader's own bug is a failure like any other" handler exists only in `search` (:243-245); `product`, `freight`, `warehouses` lack it. [DERIVED]
- `_head` hardcodes `"source": "cj"` (:177); safe today because only CJ tools use it, but any new non-CJ tool built on `_head` would be mislabelled. [INFERRED: no non-CJ caller exists in this file]
- `CJ_RATE_LIMITED` text hardcodes CJ's wait schedule "after waiting 2 s and 4 s" (:73) — that behaviour lives in `cj_api`, duplicated here as prose. [INFERRED: the waits are not implemented in this file]
- Magic numbers inline: `60.0` window (:128, :131), `1` as busy retry (:145).
- Default `30` stated in constant (:59) and repeated in `rate_per_minute` docstring (:106) — consistent, but two places to update.
- FACTS reports `TOOLS` as a list while SOURCE shows the tuple `("supplier_search", "supplier_product", "supplier_freight", "supplier_warehouses", "supplier_parse")` (:57) — static-analysis rendering artifact, not a code defect. [DERIVED]

## refactor notes
- `CONTRACT = "supplier-tools-v1"` is stamped into every result (:54, :177, :227, :369); `orchestrator/orchestrator/api/acquisition.py` and `workers/workers/adapter_step_worker.py` import this module (FACTS.importers) — changing the contract string or result keys breaks both.
- `search` reuses `service.shape`/`Target` so its record shape matches `research_acquire`'s listings (:5-7, :540); reshaping `items`/`sources`/`completeness` crosses that contract.
- `FAIR_USE` is a module-level singleton (:154); counts live in-process only and reset on a bounce (:22-24) — replacing it with shared storage changes the fair-use guarantees callers rely on.
- `SOURCES` (:56) drives both validation and reader selection; adding a source requires a matching reader plus `agent_reach` support, or `UNKNOWN_SOURCE` stays.
- `freight`/`warehouses` returning `fallback: None` is deliberate (:20-21); `_unavailable` changes its limitation text when a fallback appears (:187-190), so adding one alters user-visible strings.
- Keys never reach results, errors or logs (:27-28) — any refactor adding CJ client details to output violates a stated guarantee.

## VERIFY
```verify
grep -Fq 'CONTRACT = "supplier-tools-v1"' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'RATE_ENV, RATE_DEFAULT = "POLYMATH_SUPPLIER_RATE_PER_MINUTE", 30' shared/polymath_shared/acquisition/supplier.py
grep -Fq 'SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX, QUANTITY_MAX = 10, 50, 10000' shared/polymath_shared/acquisition/supplier.py
grep -Eq 'raise FairUseRefused\("SUPPLIER_(RATE_LIMITED|BUSY)"' shared/polymath_shared/acquisition/supplier.py
test "$(grep -c -F 'FairUseRefused' shared/polymath_shared/acquisition/supplier.py)" -ge 3
test "$(grep -c -F 'except Exception' shared/polymath_shared/acquisition/supplier.py)" -ge 1
test "$(grep -c -F 'except ApiFailed' shared/polymath_shared/acquisition/supplier.py)" -ge 4
```
