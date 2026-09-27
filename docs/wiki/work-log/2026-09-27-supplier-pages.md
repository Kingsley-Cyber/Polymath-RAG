---
change_id: SUPPLIER-PAGES
owner: "@king"
date: 2026-09-27
status: complete
status_note: "An Alibaba supplier search reads up to three result pages until the listings reach the limit, and SearXNG asks five engines: many product links per search instead of one."
architecture_impact: "shared/polymath_shared/acquisition/searxng.py (_page, MAX_PAGES, FULL_PAGE); deployment/searxng/settings.yml (+qwant, +mojeek); tests/contracts/test_supplier_apis.py (+4 tests)."
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
- SearXNG's `keep_only` engines: bing, duckduckgo, brave, qwant, mojeek (an engine that shows SearXNG a check is reported
  unresponsive; nothing is bypassed).
- Variations and different products in a Trail run come from what already exists: `supply.plan` gives every concept up to 8 search
  terms (name, form factor, variations, candidates), the agent searches each term through `research_acquire` catalog, and each
  search now yields up to `limit` product pages instead of one.

## Proof
- 4 new tests (fake HTTP): the limit is reached across pages with no product twice and page 1 asked as before; a short page is the
  last and a page of nothing new ends the search; a failing later page keeps the earlier pages' listings; at most three pages.
- `tests/contracts` 770 passed; ruff clean on the changed files.
- Live after the deploy: `/supplier/search` source `alibaba`, limit 10, for the same query.

## Rejected claims
- "Showroom and category pages are listings": they are not product pages; they stay out (counted in the notes).

## Open contract gaps
- Prices and minimum orders come from snippets and are often "not shown"; CJ's API is the source for real supplier data once the
  owner's account has the API app installed and a key generated.
