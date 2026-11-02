# unit: shared/polymath_shared/product_search/host_data.py
anchor: shared/polymath_shared/product_search/host_data.py:1-832

## purpose
Collects the HOST side of a product decision report (PRODUCT-DECISION-REPORT-V1 §4.3, contract `"product-report-host-v1"`): for each candidate product it queries CJ (via the supplier tools, as the caller's principal so fair use applies to friends) and eBay once, filters by head-term relevance, costs one variant, quotes freight, and leaves a receipt per call — before any Agent Reach round runs on the user's machine. shared/polymath_shared/product_search/host_data.py:1-4,57 [DERIVED]
Deterministic code only: no model, no web page, no key in any result; every text field is the supplier's or seller's untrusted text. shared/polymath_shared/product_search/host_data.py:36-37,108 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `collect` | def | `(candidates, *, principal_id, ship_to="US", supplier_fns=None, ebay=None, ... env, sleep, fair_use, ebay_daily)` -> `{cj, ebay, receipts, ...}` | shared/polymath_shared/product_search/host_data.py:786-831 | orchestrator/orchestrator/api/product_report.py |
| `choose_variant` | def | `(variants, *, title, term)` -> `(variant or None, kept, dropped, rule)` | shared/polymath_shared/product_search/host_data.py:546-576 | — |
| `freight_options` | def | `(answer)` -> `[{carrier, cost_usd, days_min, days_max, days_text, days_unit}]`, cheapest first | shared/polymath_shared/product_search/host_data.py:630-644 | — |
| `parse_days` | def | `(text)` -> `(days_min, days_max)` or `(None, None)` | shared/polymath_shared/product_search/host_data.py:147-160 | — |
| `days_unit` | def | `(text)` -> `"business" | "calendar" | None` | shared/polymath_shared/product_search/host_data.py:163-168 | — |
| `number_range` | def | `(text)` -> `(low, high)` or `(None, None)` | shared/polymath_shared/product_search/host_data.py:171-179 | — |
| `search_term` | def | `(candidate)` -> term or None | shared/polymath_shared/product_search/host_data.py:223-233 | — |
| `EbayDaily` | class | `__init__(now=None, limit=EBAY_DAILY_SEARCHES)`, `admit`, `refund`, `used` | shared/polymath_shared/product_search/host_data.py:300-337 | — |
| `CONTRACT` | const | `"product-report-host-v1"` | shared/polymath_shared/product_search/host_data.py:57 | — |

Sole importer per FACTS: `orchestrator/orchestrator/api/product_report.py`.

## contracts

**`collect`** — shared/polymath_shared/product_search/host_data.py:786-831, doc 5-37
- in: `candidates` = list of `{candidate_id, title, search_terms}`; `principal_id` (None = owner); `ship_to` default `"US"`; `supplier_fns` None / mapping / object (5, 236-257, 261-272).
- pre: `candidates` not list/tuple -> `AcquisitionRefused(422, "BAD_CANDIDATES", ...)` (237-238); `ship_to` not a 2-letter code -> `AcquisitionRefused(422, "BAD_COUNTRY", ...)` (210-214).
- out: `{cj: {candidate_id: {status, reason_code, ...}}, ebay, receipts, ...}`; statuses OK, PARTIAL, NO_MATCH, EMPTY, UNAVAILABLE, NOT_SEARCHED, NOT_CONFIGURED (eBay only) (5, 35-36).
- post: every call leaves a receipt (what was asked, status, reason code, rows, when); one candidate's failure never stops the others; a failure is a typed status with `reason_code`; supplier `fallback` handoff carried through unchanged (30-32).

**`choose_variant`** — shared/polymath_shared/product_search/host_data.py:546-576
- in: variant list, product `title`, search `term` (keyword-only).
- out: the costed variant or None, kept variants cheapest-first (ties: lower variant id), dropped variants each with `why` (`ACCESSORY_NAME` + words, or `LIGHT_WEIGHT` + cutoff), the rule as applied.
- post: none left -> `detail_status` `NO_COSTED_VARIANT`, no price (17, 33).

**`parse_days` / `days_unit`** (contract C2) — shared/polymath_shared/product_search/host_data.py:147-168
- `"4-9"`, `"3"`, `"10 - 23 days"`, `"2-5 business days"` -> int pairs; anything else `(None, None)`; the named unit is read separately, never dropped (148-149, 164-165).

**`EbayDaily.admit`** — shared/polymath_shared/product_search/host_data.py:311-325
- in: `principal_id`; owner (`None`) passes untouched (314-315).
- out: None = admitted; otherwise whole seconds to the next UTC day once the principal made `limit` searches today (321-324).

**`_Run.cj`** (internal, shapes all CJ calls) — shared/polymath_shared/product_search/host_data.py:393-442
- At most `CJ_CALLS_PER_CANDIDATE` (4) calls that may reach CJ per candidate; past it answers `NOT_FETCHED` / `CJ_CALL_BUDGET` (395, 404-406). A refusal never counts: the counter increments only after a non-refused call (432).

## effect surface

| effect | detail | anchor |
|---|---|---|
| network (CJ) | supplier tools `supplier_search` / `supplier_product` / `supplier_freight` (CJ official API, pacing + circuit breaker), invoked as the run's principal | shared/polymath_shared/product_search/host_data.py:6-7,77,410 |
| network (eBay) | `ebay_browse_search` via `ebay_api`, Browse API on the owner's keyset | shared/polymath_shared/product_search/host_data.py:24,78 |
| Postgres / Qdrant | none (`tables_read` / `tables_written` empty in FACTS) | — |
| env | `env: Mapping[str,str] | None` threaded into the supplier tools; no flag parsed in this file | shared/polymath_shared/product_search/host_data.py:265-266 |
| in-process state | module singleton `EBAY_DAILY = EbayDaily()` guarded by `threading.Lock`; resets each UTC day; lost on restart | shared/polymath_shared/product_search/host_data.py:74,305,309,318-319,340 |
| clock | `datetime.now(UTC)` via injectable `now` | shared/polymath_shared/product_search/host_data.py:304-305 |
| sleep | injectable `sleep` used only for fair-use Retry-After waits | shared/polymath_shared/product_search/host_data.py:347,419 |

## invariants

INVARIANT: CJ calls that may reach CJ per candidate <= `CJ_CALLS_PER_CANDIDATE` (4) = 1 search + 1 details + 2 freight (CN, US) — shared/polymath_shared/product_search/host_data.py:62,404 [DERIVED]; fails-if: budget bypass spends CJ's ~1 call/s allowance and trips the shared breaker.
INVARIANT: kept relevant products per candidate <= `MAX_PRODUCTS` (3); candidates <= `MAX_CANDIDATES` (8) — shared/polymath_shared/product_search/host_data.py:60-61,116-126,251 [DERIVED]; fails-if: report cap (§3) exceeded.
INVARIANT: fair-use wait per refusal <= `FAIR_USE_WAIT_MAX_S` (60.0) AND cumulative waits <= `FAIR_USE_WAIT_TOTAL_S` (120.0), waited out at most once per call — shared/polymath_shared/product_search/host_data.py:71,414-421 [DERIVED]; fails-if: collect stalls past 2 minutes on repeated 429s.
INVARIANT: eBay searches per non-owner principal per UTC day <= `EBAY_DAILY_SEARCHES` (300); owner (`principal_id=None`) exempt — shared/polymath_shared/product_search/host_data.py:75,314-324 [DERIVED]; fails-if: one friend burns the shared 5,000/day keyset budget and opens the breaker for everyone (72-74).
INVARIANT: run memo reused only for status in `_REUSABLE` = `("OK", "PARTIAL", "EMPTY", "NOT_FOUND")`; failures are asked again — shared/polymath_shared/product_search/host_data.py:285-286,440-441 [DERIVED]; fails-if: a transient failure gets cached and reported as permanent.
INVARIANT: `parse_days` returns values only when `1 <= hi <= MAX_DAYS` (365) — shared/polymath_shared/product_search/host_data.py:67,160 [DERIVED]; fails-if: absurd CJ text ("0 days", "9999 days") enters the report as real ranges.
INVARIANT: `us_stock_confirmed` true only when CJ STATES US-warehouse units for the quoted variant — a US->US freight quote is not proof — shared/polymath_shared/product_search/host_data.py:20-21,103-104,505-514 [DERIVED]; fails-if: report claims US stock CJ never declared.
INVARIANT: every CJ/eBay fair-use refusal surfaces as `FAIR_USE_LIMITED` with the gate's own code in `fair_use_code` (contract C6) — shared/polymath_shared/product_search/host_data.py:69-70,289-297 [DERIVED]; fails-if: downstream can't distinguish rate limits from real failures.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `datetime.now(UTC)` shared/polymath_shared/product_search/host_data.py:305; network calls to CJ/eBay shared/polymath_shared/product_search/host_data.py:410; concurrency `threading.Lock` shared/polymath_shared/product_search/host_data.py:309; env passthrough shared/polymath_shared/product_search/host_data.py:265)
idempotency: UNSAFE — a repeated `collect` re-spends the principal's fair use (shared/polymath_shared/product_search/host_data.py:376,410), EbayDaily counts (324) and the per-candidate CJ budget (432); `EbayDaily.refund` returns only gate-refused searches, never completed ones (327-333,378).

## failure behaviour
- `_fallback`: any `Exception` SWALLOWED — `log.exception`, return None; the Agent Reach handoff is advice and must never fail the report — shared/polymath_shared/product_search/host_data.py:279-281. Caller then sees `fallback: None` in the failed answer (454-455).
- `_Run.cj`: non-refusal `Exception` handled — logged, answered `UNAVAILABLE` / `CJ_ERROR` with the exception type name; never raised — shared/polymath_shared/product_search/host_data.py:428-430.
- Non-mapping supplier answer -> `UNAVAILABLE` / `CJ_BAD_REPLY` — shared/polymath_shared/product_search/host_data.py:434-435.
- `_ebay_entry`: `Exception` handled (log, assign, return entry) at shared/polymath_shared/product_search/host_data.py:747; two `collect`-level handlers (log, assign) at 818 and 823 [DERIVED from FACTS.fallbacks].
- Raised to caller: `AcquisitionRefused` 422 `BAD_CANDIDATES` (237-238) and 422 `BAD_COUNTRY` (213).
- Reason codes emitted: `FAIR_USE_LIMITED`, `EBAY_DAILY_LIMIT`, `CJ_CALL_BUDGET`, `CJ_ERROR`, `CJ_BAD_REPLY`, `CJ_EMPTY` / `CJ_PRODUCT_NOT_FOUND` / `CJ_UNAVAILABLE` as defaults in `_failure_code` (462-464), `NO_COSTED_VARIANT` (17).

## dumb-code flags
- Two different money ceilings in the same file: `_money` rejects `n >= 1_000_000` (shared/polymath_shared/product_search/host_data.py:189) but `number_range` allows `hi < 10_000_000` (195). Same domain (USD), inconsistent bounds.
- The relevance/variant policy text is written out three times: module docstring (8-17), `RULE` / `VARIANT_RULE` constants (79-93), `NOTES` (96-109). Drift risk on every edit.
- `MAX_CANDIDATES = 8` is the report CAP, while the report's `max_products` default is 5 — comment says so, code takes only the cap — shared/polymath_shared/product_search/host_data.py:60.
- `days_unit` returns None when the text says both "business" and "calendar" (silent ambiguity, not an error) — shared/polymath_shared/product_search/host_data.py:184.
- `_term` silently discards terms under 2 chars or without head terms; `search_term` then falls back to title words — shared/polymath_shared/product_search/host_data.py:219-233.
- `EBAY_SEARCH_LIMIT, MAX_LISTINGS = 30, 20` and `MAX_VARIANTS, MAX_FREIGHT_OPTIONS, MAX_DROPPED, MAX_LIMITATIONS = 30, 40, 12, 8` are defined at shared/polymath_shared/product_search/host_data.py:64-65 but their consuming code lies beyond the visible source range; only `MAX_DROPPED` (132) and `MAX_LIMITATIONS` (459) usages are visible here.
- Receipts stringify time eagerly: `str(retrieved_at or now_iso())` — shared/polymath_shared/product_search/host_data.py:407.

## refactor notes
- Blast radius of `collect`'s return shape: `orchestrator/orchestrator/api/product_report.py` is the only importer (FACTS.importers); its receipts, `cj`/`ebay` per-candidate entries and status vocabulary all come from here — shared/polymath_shared/product_search/host_data.py:5,35-36,387-391.
- `head_terms` / `missing_terms` live in `acquisition.agent_reach` and are shared by CJ, eBay here AND Amazon, Alibaba, Reddit parsers in the report — changing term semantics changes every parser at once — shared/polymath_shared/product_search/host_data.py:112-113.
- `FAIR_USE_LIMITED` is contract C6 shared with the gate; `fair_use_code` carries the gate's own code — renaming either breaks the contract — shared/polymath_shared/product_search/host_data.py:69-70,294.
- Test seams to preserve: injectable `now`/`limit` on `EbayDaily` (304), injectable `daily` on `_Run` (348-350), injectable `sleep` (347), `supplier_fns` as mapping or object (261-272).
- The module singleton `EBAY_DAILY` (340) is process-wide state; moving `collect` to another process changes friend rate-limit semantics silently.

## VERIFY
```verify
grep -Fq 'CONTRACT = "product-report-host-v1"' shared/polymath_shared/product_search/host_data.py
grep -Fq 'CJ_CALLS_PER_CANDIDATE = 4' shared/polymath_shared/product_search/host_data.py
grep -Fq 'EBAY_DAILY_SEARCHES = 300' shared/polymath_shared/product_search/host_data.py
grep -Fq '_REUSABLE = ("OK", "PARTIAL", "EMPTY", "NOT_FOUND")' shared/polymath_shared/product_search/host_data.py
grep -Fq 'VARIANT_SPREAD, VARIANT_LIGHT_SHARE = 2.5, 0.40' shared/polymath_shared/product_search/host_data.py
grep -Eq 'FAIR_USE_WAIT_MAX_S, FAIR_USE_WAIT_TOTAL_S = 60\.0, 120\.0' shared/polymath_shared/product_search/host_data.py
test "$(grep -c -F 'MAX_DROPPED' shared/polymath_shared/product_search/host_data.py)" -ge 2
```
