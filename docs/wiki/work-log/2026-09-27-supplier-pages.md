---
change_id: SUPPLIER-PAGES
owner: "@king"
date: 2026-09-27
status: complete
status_note: "An Alibaba supplier search reads up to three result pages until the listings reach the limit, searches are paced 2 s apart, and SearXNG asks five engines (bing, duckduckgo, brave, qwant, yahoo): many product links per search instead of one."
architecture_impact: "shared/polymath_shared/acquisition/searxng.py (_page, MAX_PAGES, FULL_PAGE, _pace / MIN_INTERVAL_S); deployment/searxng/settings.yml (+qwant, +yahoo); tests/contracts/test_supplier_apis.py (+5 tests, an unpaced autouse fixture)."
last_reviewed: 2026-09-27
---

# SUPPLIER-PAGES: many Alibaba listings per search

## Contract
- The owner, 2026-09-27: "with alibaba it should be multiple products. a run of trail should bring about variations of the same
  products links but also multiple different products from chunks."
- The live check of 11.538 returned ONE listing for "touchscreen winter gloves": the engines answer `site:alibaba.com` mostly with
  Alibaba's category and showroom pages (page 1: 1 product page in 40 results; page 2: 5 more).

## Changes
- `SearXNGListings.read` asks up to `MAX_PAGES` (3) result pages (`pageno`) while the listings are short of the limit, stopping at a
  page with fewer than `FULL_PAGE` (10) results (the engines' last) or a page that adds no new product; the same product number on a
  later page is kept once; a later page that fails keeps what the earlier pages gave and says so (`result page N was not read`);
  page 1 is asked exactly as before. Notes carry "N result pages read".
- SearXNG's `keep_only` engines: bing, duckduckgo, brave, qwant, yahoo (an engine that shows SearXNG a check is reported
  unresponsive; nothing is bypassed). Mojeek was tried first and never loaded: upstream marks it, and Startpage, `inactive`
  because they use a proof-of-work captcha, which Polymath never solves.
- **Pacing (live finding, 2026-09-27 13:56 UTC):** after a burst of about ten test searches, every engine refused at once — Brave
  "too many requests" (suspended 180 s), DuckDuckGo and Qwant their checks, Bing a connection error — so a Trail run's dozens of
  searches would have done the same. `SearXNGListings._pace` asks the engines no faster than one search every `MIN_INTERVAL_S`
  (2 s) from this process, across pages and calls (an injected clock and sleep, so tests never wait).
- Variations and different products in a Trail run come from what already exists: `supply.plan` gives every concept up to 8 search
  terms (name, form factor, variations, candidates), the agent searches each term through `research_acquire` catalog, and each
  search now yields up to `limit` product pages instead of one.

## Proof
- 4 new tests (fake HTTP): the limit is reached across pages with no product twice and page 1 asked as before; a short page is the
  last and a page of nothing new ends the search; a failing later page keeps the earlier pages' listings; at most three pages.
- A pacing test: page 1 at once, then 2 s gaps, and a new search 0.5 s later waits the remaining 1.5 s.
- `tests/contracts` 771 passed; ruff clean on the changed files.
- Live after the deploy: `/supplier/search` source `alibaba`, limit 10, for the same query.

## Contract dispositions
- RESEARCH_ACQUISITION — UPDATED: the SearXNG listing backend reads up to three result pages; the request for page 1, the record
  shape and the notes' first lines are unchanged (`test_supplier_apis.py`).
- ADAPTER_RUNTIME — TESTED_UNCHANGED: `test_adapter_ecommerce_supply_join_api_records.py`, `test_adapter_evidence_boundary.py`,
  `test_adapter_runtime_pure.py` (65 passed with `test_mcp_*`); `test_adapter_product_discovery_loop.py` is a fleet-database test,
  not run.
- MCP_SURFACE — TESTED_UNCHANGED: `test_mcp_principals_gate.py`, `test_mcp_server_v2.py`, `test_supplier_tools.py`,
  `test_mcp_adapter_parity.py`, `test_hosted_mcp_acceptance.py` (in the 770 contract passes).

## Rejected claims
- "Showroom and category pages are listings": they are not product pages; they stay out (counted in the notes).

## Open contract gaps
- Prices and minimum orders come from snippets and are often "not shown"; CJ's API is the source for real supplier data once the
  owner's account has the API app installed and a key generated.
