# unit: shared/polymath_shared/product_search/host_data.py
anchor: shared/polymath_shared/product_search/host_data.py:1-733

## purpose
Builds the HOST half of a product decision report (PRODUCT-DECISION-REPORT-V1 §4.3, slice B2): what the Polymath host itself learns about each candidate product from CJ (official API via the supplier tools) and eBay (Browse API), before any Agent Reach round runs on the user's machine. Every user — the owner, a friend's connector key, a friend on the web app — gets the same data, spent under the caller's fair use. — shared/polymath_shared/product_search/host_data.py:1-5 [DERIVED]
Entry point: `collect(candidates, *, principal_id, ship_to="US", supplier_fns=None, ebay=None) -> {cj, ebay, receipts, ...}` — shared/polymath_shared/product_search/host_data.py:5 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| collect | def | (candidates, principal_id, ship_to, supplier_fns, ebay, env, sleep, fair_use, ebay_daily) -> dict | shared/polymath_shared/product_search/host_data.py:687-732 | — |
| EbayDaily | class | (now=None, limit=EBAY_DAILY_SEARCHES); admit(principal_id) -> int \| None; refund(principal_id) -> None; used(principal_id) -> int | shared/polymath_shared/product_search/host_data.py:281-318 | — (module singleton `EBAY_DAILY` at :321) |
| search_term | def | (candidate: Mapping) -> str \| None | shared/polymath_shared/product_search/host_data.py:204-214 | — |
| parse_days | def | (text) -> tuple[int \| None, int \| None] | shared/polymath_shared/product_search/host_data.py:128-141 | — |
| days_unit | def | (text) -> str \| None | shared/polymath_shared/product_search/host_data.py:144-149 | — |
| number_range | def | (text) -> tuple[float \| None, float \| None] | shared/polymath_shared/product_search/host_data.py:152-160 | — |
| freight_options | def | (answer: Mapping) -> list[dict] | shared/polymath_shared/product_search/host_data.py:538-552 | — |

Only importer: `orchestrator/orchestrator/api/product_report.py` (module-level import; per-symbol use not shown). — shared/polymath_shared/product_search/host_data.py:1-733 [DERIVED]

## contracts

**collect** — shared/polymath_shared/product_search/host_data.py:687-732, documented at :5-33
- in: `candidates` = list/tuple of `{candidate_id|id, title, search_terms}` (:217-238); anything else raises `AcquisitionRefused(422, "BAD_CANDIDATES", ...)` (:219). `ship_to` = two-letter country code, default `"US"` (:5, :191-195); else `AcquisitionRefused(422, "BAD_COUNTRY", ...)` (:194).
- in: `supplier_fns` = None (real supplier tools; `env` and `fair_use` forwarded, :245-247) or a Mapping/object exposing `search`/`product`/`freight` callables (:248-253); missing ones raise `TypeError` (:252).
- out: `{cj, ebay, receipts, ...}` (:5); per-source status ∈ OK, PARTIAL, NO_MATCH, EMPTY, UNAVAILABLE, NOT_SEARCHED, NOT_CONFIGURED (eBay only) (:31-32); receipt rows `{n, source, call, candidate_id, request, status, reason_code, rows, retrieved_at}` (:370-372).
- post: at most CJ_CALLS_PER_CANDIDATE (4) CJ calls per candidate (:58, :385-387); at most MAX_PRODUCTS (3) relevant products kept (:57, :577); relevance rule = title holds every head term as a whole word (plural/singular or 2–3 adjacent joined words count; substring never counts) (:8-11, :75-76); one eBay search per candidate, spent from the same fair-use gate and EbayDaily (:347-365); every network call leaves a receipt (:26, :370-372); results hold only supplier/seller untrusted text — no model, web page, or key (:33).

**parse_days(text)** — "4-9", "3", "10 - 23 days", "2-5 business days" -> (days_min, days_max); `(None, None)` unless `1 <= hi <= MAX_DAYS` (365). — shared/polymath_shared/product_search/host_data.py:128-141
**days_unit(text)** — "business" / "calendar" / None (when text says neither or both). — shared/polymath_shared/product_search/host_data.py:144-149
**number_range(text)** — 1–2 numbers (thousands commas stripped) -> (low, high); `(None, None)` unless `lo >= 0` and `hi < 10_000_000`. — shared/polymath_shared/product_search/host_data.py:152-160
**search_term(candidate)** — first usable `search_terms` entry, else title head words up to 5, else None; usable = length ≥ 2 and has head terms. — shared/polymath_shared/product_search/host_data.py:199-214
**freight_options(answer)** — `{carrier, cost_usd, days_min, days_max, days_text, days_unit}` per option; `cost_usd` prefers `total_usd` over `cost_usd` (:546-548); sorted cheapest-first then shortest, capped at 40. — shared/polymath_shared/product_search/host_data.py:538-552
**EbayDaily.admit(principal_id)** — None = admitted; a value = whole seconds to next UTC midnight (refused); `principal_id` None (owner) always admitted. — shared/polymath_shared/product_search/host_data.py:292-306

## effect surface
- Network: CJ official API via `supplier.search/product/freight`, called as the run's principal (:6-7, :391); eBay Browse API (`ebay_browse_search`) on the owner's keyset (:20-21, :74).
- Postgres / Qdrant / files / subprocess: none (FACTS tables_read and tables_written are empty). — shared/polymath_shared/product_search/host_data.py:1-733 [DERIVED]
- Env: none read directly; `env` mapping is forwarded into the supplier tools when `supplier_fns is None` (:246).
- Process state: module singleton `EBAY_DAILY` (per-principal, per-UTC-day counters) behind a `threading.Lock` (:288-290, :321); per-run memo dict (:336).
- Clock/sleep: `datetime.now(UTC)` (:286), `now_iso()` in every receipt (:372), injected `sleep(wait)` for fair-use Retry-After (:400).

## invariants
INVARIANT: CJ calls per candidate ≤ CJ_CALLS_PER_CANDIDATE = 4 (search, details, freight CN, freight US) — shared/polymath_shared/product_search/host_data.py:58,385-387 [DERIVED]
  fails-if: extra calls exceed CJ's ~1/s pacing the budget exists for (:82-83)
INVARIANT: kept products per candidate ≤ MAX_PRODUCTS = 3; the rest land in relevance.dropped with why — shared/polymath_shared/product_search/host_data.py:57,103,577 [DERIVED]
  fails-if: report grows past its product cap; near misses silently lost
INVARIANT: candidates kept ≤ MAX_CANDIDATES = 8; extras skipped as "OVER_LIMIT" — shared/polymath_shared/product_search/host_data.py:56,232-234 [DERIVED]
  fails-if: report exceeds the §3 cap (default 5, cap 8 per :56 comment)
INVARIANT: friend eBay searches ≤ EBAY_DAILY_SEARCHES = 300 per UTC day; principal None exempt — shared/polymath_shared/product_search/host_data.py:71,295-296,302-304 [DERIVED]
  fails-if: one key spends the shared 5,000/day keyset budget and 429s trip the keyset-wide breaker for everyone (:68-70)
INVARIANT: fair-use wait at most once per call, wait ≤ FAIR_USE_WAIT_MAX_S = 60.0, run total ≤ FAIR_USE_WAIT_TOTAL_S = 120.0 — shared/polymath_shared/product_search/host_data.py:67,394-396 [DERIVED]
  fails-if: collect blocks past its latency budget waiting on CJ
INVARIANT: parse_days returns values only when 1 ≤ days_max ≤ MAX_DAYS = 365 — shared/polymath_shared/product_search/host_data.py:63,141 [DERIVED]
  fails-if: garbage day text becomes a fake delivery window
INVARIANT: number_range bound hi < 10_000_000 vs _money bound n < 1_000_000 (both round/reject negatives) — shared/polymath_shared/product_search/host_data.py:160,170 [DERIVED]
  fails-if: parsed prices go negative or absurd; the 10× bound mismatch makes one parser accept what the other drops
INVARIANT: us_stock_confirmed true only when the cheapest variant's us_stock_units > 0; a US→US quote alone never confirms — shared/polymath_shared/product_search/host_data.py:531,87-88 [DERIVED]
  fails-if: report claims US stock CJ never stated (measured 2026-11-02: stock by country [] while the US quote answered, :87-88)
INVARIANT: only statuses in _REUSABLE = ("OK", "PARTIAL", "EMPTY", "NOT_FOUND") are memoized within a run — shared/polymath_shared/product_search/host_data.py:267,421-422 [DERIVED]
  fails-if: a failed answer gets reused for a second candidate with the same term
INVARIANT: freight options sorted (cost asc, None-cost last, days_max asc, carrier), ≤ 40; variants sorted price asc (None last), ≤ 30 — shared/polymath_shared/product_search/host_data.py:551-552,513-514 [DERIVED]
  fails-if: the "cheapest first" ordering the report promises breaks
INVARIANT: every network call appends a receipt, success or failure — shared/polymath_shared/product_search/host_data.py:26,370-372,418-420 [DERIVED]
  fails-if: unaccounted API spend

## determinism & idempotency
determinism: NONDETERMINISTIC — clock `datetime.now(UTC)` :286 and `now_iso()` :372; live network to CJ :391 and eBay :344-346; shared mutable `EBAY_DAILY` :321. Result content itself holds no model/web page/key (:33).
idempotency: UNSAFE — re-running collect re-spends the fair-use gate (:357) and EbayDaily day counts (:305, :321); a daily admission is refunded only when the fair-use gate refuses immediately after (:359, :308-314); the CJ per-candidate budget resets each run (:333, :385).

## failure behaviour
- Swallowed: any exception while building the Agent Reach handoff -> `log.exception` + return None; the handoff "is advice: failing to build it must never fail the report" — shared/polymath_shared/product_search/host_data.py:256-263 [DERIVED]
- A supplier tool raising anything -> typed UNAVAILABLE answer with `reason_code` "CJ_ERROR", logged, never re-raised ("a supplier tool's own bug is a failure like any other: typed, never raised") — shared/polymath_shared/product_search/host_data.py:409-411 [DERIVED]
- `AcquisitionRefused` with code in FAIR_USE_CODES ("SUPPLIER_RATE_LIMITED", "SUPPLIER_BUSY") -> reported as FAIR_USE_LIMITED plus `fair_use_code` and `retry_after_s`; any other refusal keeps its own code — shared/polymath_shared/product_search/host_data.py:270-278 [DERIVED]. A CJ fair-use refusal is waited out once (:394-403); an eBay one is answered at once (:356-365).
- Per-candidate exceptions inside `_ebay_entry`/`collect` are handled (log + assign; FACTS fallbacks at :648, :719, :724) so "one candidate's failure never stops the others" — shared/polymath_shared/product_search/host_data.py:28 [DERIVED]
- Non-Mapping supplier answer -> "CJ_BAD_REPLY" (:414-416). Budget skip -> status NOT_FETCHED with "CJ_CALL_BUDGET" (:385-387). Status-to-code mapping: EMPTY -> CJ_EMPTY, NOT_FOUND -> CJ_PRODUCT_NOT_FOUND, else CJ_UNAVAILABLE (:443-445).
- Raised by this module itself: `AcquisitionRefused(422, "BAD_COUNTRY", ...)` :194; `AcquisitionRefused(422, "BAD_CANDIDATES", ...)` :219; `TypeError` from `_fns` :252.

## dumb-code flags
- Docstring signature shows 5 params (:5) but collect takes 9 — `env`, `sleep`, `fair_use`, `ebay_daily` are undocumented in the docstring line (per FACTS arg list). — shared/polymath_shared/product_search/host_data.py:5 [DERIVED]
- Docstring says "EBAY_NOT_CONFIGURED (status NOT_CONFIGURED)" (:21) while the status vocabulary (:31-32) says NOT_CONFIGURED; the EBAY_-prefixed name exists only in prose.
- Two money parsers with different caps: `number_range` hi < 10_000_000 (:160) vs `_money` n < 1_000_000 (:170).
- MAX_CANDIDATES = 8 justified by a comment citing another artifact's default ("max_products default 5, cap 8") — the 5 is not a symbol here (:56).
- `EBAY_SEARCH_LIMIT, MAX_LISTINGS = 30, 20` declared (:60) but unused in the visible lines 1-579; any use sits in `_ebay_entry` (:615-670, past the shown range). — shared/polymath_shared/product_search/host_data.py:60 [DERIVED]
- Magic 600-char URL cap inside `_url` (:187) next to named TERM_MAX/TITLE_MAX constants (:62); min term length 2 hardcoded in `_term` (:200-201) and restated as text in the NO_SEARCH_TERM limitation (:562).
- Long inline refusal "why" message literals duplicated across the EBAY_DAILY_LIMIT and FAIR_USE_LIMITED branches (:349-351, :361-362).

## refactor notes
- collect's return shape (`{cj, ebay, receipts}` keys, the status/reason_code vocabulary :31-32, CONTRACT "product-report-host-v1" :53) is consumed by `orchestrator/orchestrator/api/product_report.py` (FACTS.importers) — renaming keys or statuses breaks it.
- Relevance matching is shared infrastructure: `head_terms`/`missing_terms` come from `polymath_shared.acquisition.agent_reach` (:48) and the same term reading serves CJ, eBay here and Amazon, Alibaba, Reddit in the report's parsers (:93-94); the RULE text (:75-76) must stay in sync with that module.
- `EBAY_DAILY` is process-global policy state (:321); its limit/owner-exemption/UTC-reset semantics are the R1 policy (:68-71). Tests inject `now`/`limit` (:285) and `_Run` accepts a `daily` (:331) — keep those seams.
- The `supplier_fns` protocol (None | Mapping | attribute object over TOOLS names :73) is the seam callers and tests inject fakes through (:242-253); TOOLS names also select `_failed`'s fallback branches (:430-435).
- FAIR_USE_WAIT_MAX_S / FAIR_USE_WAIT_TOTAL_S (:67) bound worst-case collect blocking (:394-400); changing them changes latency every caller sees.

## VERIFY
```verify
grep -Fq 'CJ_CALLS_PER_CANDIDATE = 4' shared/polymath_shared/product_search/host_data.py
grep -Fq 'EBAY_DAILY_SEARCHES = 300' shared/polymath_shared/product_search/host_data.py
grep -Fq 'FAIR_USE_WAIT_MAX_S, FAIR_USE_WAIT_TOTAL_S = 60.0, 120.0' shared/polymath_shared/product_search/host_data.py
grep -Fq 'AcquisitionRefused(422, "BAD_COUNTRY"' shared/polymath_shared/product_search/host_data.py
grep -Fq '"CJ_CALL_BUDGET"' shared/polymath_shared/product_search/host_data.py
grep -Eq 'def collect\(' shared/polymath_shared/product_search/host_data.py
test "$(grep -c -F 'FAIR_USE_LIMITED' shared/polymath_shared/product_search/host_data.py)" -ge 3
```
