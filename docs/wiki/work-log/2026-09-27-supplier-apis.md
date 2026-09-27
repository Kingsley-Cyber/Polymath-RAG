---
change_id: SUPPLIER-APIS
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Supplier research stops needing the pages that show human checks, and never gets past one: cjdropshipping.com listings from CJ's official API 2.0 (with CJ_API_KEY), alibaba.com listings from a local SearXNG's search-engine snippets (a new opt-in compose service), each falling back to the host browser said and counted; a challenge-page DETECTOR (never a solver) in the read paths and in the receipt check (CHALLENGE_PAGE_AS_EVIDENCE); the human-check handoff in every copy of the guide; four owner-only, read-only supplier tools on both MCP servers. Unit and worktree proven on feat/supplier-apis; not merged, not deployed, no live call made."
architecture_impact: "shared/polymath_shared/acquisition/{challenge,listing_apis,cj_api,searxng,supplier}.py (new), acquisition/service.py (shape: backend_notes in every state, a wall's text never a listing or search row; default_backend wraps the listing APIs), acquisition/opencli.py (blocked: the detector once a reader got nothing), acquisition/__init__.py (docstring); shared/polymath_shared/adapter/transitions.py (validate_receipt: CHALLENGE_PAGE_AS_EVIDENCE), adapter/harness_guide.py (the handoff, the wall line, the supplier tools); orchestrator/orchestrator/api/acquisition.py (refuse_unless_direct; POST /supplier/search, /supplier/product, /supplier/freight, GET /supplier/warehouses), web_boundary.py (an OWNER line), mcp_server.py + mcp_server/polymath_mcp.py (supplier_* tools; research_acquire's description), api/web_settings.py (connect prompt), mcp_server/CONNECTORS.md; compose.yaml (service `searxng`, profile `search`) + deployment/searxng/settings.yml (new); .env.example (CJ_API_KEY, SEARXNG_URL, SEARXNG_SECRET); architecture/contract-dependencies.yaml (RESEARCH_ACQUISITION paths, tests, consumed_by ADAPTER_RUNTIME); tests: 5 new files, tests/determinism/test_mcp_principals_gate.py (the owner-only set widened by the four tools); scripts/scaffold_polymath_v4.py (12 TREE entries). No schema, manifest, migration or pinned-Trail change."
last_reviewed: 2026-09-27
---

# SUPPLIER-APIS: supplier listings without the pages that show human checks

## Contract
- **The owner's request:** "fix captchas". R7 (register 11.495) sourced 0 of 16 supply queries: alibaba.com showed a human check on
  every call, cjdropshipping.com a verification redirect (gaps S-18, S-20). The fix is to stop needing those pages and to hand any
  check that remains to a person. **Hard rule:** nothing here solves, bypasses, evades or automates a CAPTCHA or bot detection: no
  solving service, no stealth or fingerprint trick, no clicking a check, no user-agent or proxy rotation.
- **The brief (lead, 2026-09-27), then two owner decisions relayed by the lead the same day:**
  1. CJ Dropshipping's official API for `cj_listings` when `CJ_API_KEY` is set: the documented sign-in, its token cached until it
     expires, the product search mapped onto the browser backend's listing shape, CJ's rate limit waited out.
  2. ~~Exa for `alibaba_listings`~~ DROPPED by the owner (no new accounts): alibaba.com listings come from a **self-hosted SearXNG**
     (compose service, loopback only, capped at half a CPU and 256 MB, engines bing / duckduckgo / brave, JSON on, limiter off, the
     secret from the environment), `GET {SEARXNG_URL}/search?q=site:alibaba.com <query>&format=json`, product-detail URLs only,
     title / price / minimum order from the snippet. Limitation: "found through search-engine results (SearXNG); snippet-level data".
  3. API or search first; a failure falls back to today's browser path, SAID in `limitations` and COUNTED.
  4. The human-check handoff in the guide and the `run_governed_research` prompt (and every other copy).
  5. Keys from the environment only; names in `.env.example`.
  6. ADDED: a **challenge-page detector** (a detector, never a solver): in the read paths (a wall is HUMAN_ACTION_REQUIRED, never
     records) and in `validate_receipt` (an observation quoting a wall is refused, CHALLENGE_PAGE_AS_EVIDENCE); a guide line.
  7. ADDED: **read-only supplier tools** on both MCP servers, owner-only, routed through the orchestrator (`/supplier/*`), built on
     the CJ REST client and the SearXNG backend; CJ's own MCP server NOT used (its token also reaches orders, payments, payment
     links, disputes and store listings); a test that no tool or endpoint can write.
- **Owner:** `shared` (the acquisition package: policy, readers, detector) with the orchestrator route and the two MCP servers as its
  public entrypoints (RESEARCH_ACQUISITION, MCP_SURFACE). Persistence: none (the token cache and the counters live in the
  orchestrator process; a bounce resets them).
- **Boundaries:** worktree `pmv4-supply`, branch `feat/supplier-apis` from `feat/fix-it-all` at `5d34fe49`. No live system, no CJ,
  search-engine or SearXNG call (fake HTTP only), no container started, no register / CONTINUITY / plan edit, no push.

## Changes
- **CJ's official API** (`acquisition/cj_api.py`, new). Read from CJ's documentation (developers.cjdropshipping.com, API 2.0,
  2026-09-27):
  - sign-in `POST /authentication/getAccessToken` with `{"apiKey"}` only (API 2.0 needs no e-mail, so `CJ_ACCOUNT_EMAIL` does not
    exist); `accessToken` + `accessTokenExpiryDate` (about 180 days) cached per key in the process until ten minutes before it
    expires; a token CJ refuses (1600001 / 1600002 / 1600003 / 1601000, HTTP 401 / 403) is dropped and the sign-in runs once more;
  - one request a second per key (CJ's free-account limit, the sign-in too): calls spaced 1.1 s apart; "too much request"
    (1600200, HTTP 429) waited out twice (2 s, 4 s); a spent quota (1600201, 16900500) never retried;
  - reads only: `GET /product/listV2` (keyWord, page 1, size <= 100, features=enable_category), `GET /product/query`,
    `POST /logistic/freightCalculate` (a calculation), `GET /product/globalWarehouseList`. `ENDPOINTS` is the whole set;
  - a product maps onto the browser listing record (`kind`, `ref`, `url`, `text`, `listing{title, price_as_listed,
    minimum_order_as_listed, supplier}`) plus what only the API gives: `product_id`, `sku`, `image`, `category`,
    `discount_price_as_listed`, `listed_by_stores`, `warehouse_inventory`. Prices are CJ's USD sell price as `US$11.85` (a range
    `US$0.97-4.08`); the minimum order only where the API states `directMinOrderNum`; the supplier only where `supplierName` is set.
    The API returns no page URL: it is built from the site's pattern `https://cjdropshipping.com/product/<slug>-p-<pid>.html`;
  - neither key nor token reaches a result, an error or a log (`_scrub`; the module never logs).
- **SearXNG** (`acquisition/searxng.py`, new): `GET {SEARXNG_URL}/search?q=site:alibaba.com <query>&format=json`; a result is kept
  only when its URL parses as `https://<alibaba.com or a subdomain>/product-detail/<name>_<8+ digits>.html` (query and fragment
  dropped, one per product number); title (the " - Buy … on Alibaba.com" tail cut), price as listed (the last price before the
  minimum order, else the first), minimum order and supplier ("Supplier or Manufacturer-<company>") from the snippet, verbatim; the
  snippet kept as `card`; a result whose text is a verification page is left out. `SEARXNG_URL` unset or empty =
  `http://127.0.0.1:8888`, `off` = not used. Unreachable, HTTP 403 (JSON off), not JSON, or every engine failing = a failure.
- **Selection and the counted fallback** (`acquisition/listing_apis.py`, new): `wrap(browser, env)` returns the browser backend
  ITSELF when no listing API is configured, else `ListingAPIs`: a configured site reads through its API first; `ApiFailed` (or a
  reader's own exception) falls back to `browser.read`, adds `the <API> could not answer (<reason>: <detail>); the host browser
  read <site> instead` to `backend_notes`, counts it per reader and reason (`catalog` → `host.listing_apis`), and logs a warning
  with the running counts. `service.default_backend` calls `wrap`.
- **`service.shape`**: `raw.backend_notes` reach `limitations` in EVERY state (a fallback that then met a human check still says
  the API failed); a listing or search row whose text is a verification wall is dropped and counted, and a listing read left with
  none is HUMAN_ACTION_REQUIRED. Comment reads are untouched (they parse the sites' own comment lists; a joke about a captcha stays).
- **The detector** (`acquisition/challenge.py`, new, pure): `looks_like_challenge(text)` names a wall (slider, unusual-traffic notice,
  human / robot check, browser check, block page, security check, "access denied" beside a bot notice, the CJK security check) or
  None. B-17's rule, generalised: a wall line must match a WHOLE segment (a line or one sentence); lines content also carries
  ("Captcha", "I'm not a robot", "Just a moment") count only in pairs; content beyond 3 segments or 200 characters makes the text
  content. Used by `opencli.blocked(read_nothing=True)` (a Cloudflare-style interstitial or a CJK slider, which hold none of the
  three old wall words, is now a human check instead of UNAVAILABLE; before a read nothing changed), `service.shape`, the SearXNG
  reader, and `transitions.validate_receipt` → `CHALLENGE_PAGE_AS_EVIDENCE: observation <id> (source <id>) quotes a verification
  page (<kind>), not evidence: …`.
- **The handoff** (one text per surface, all saying the same): `harness_guide.GUIDE` §4 (so the `run_governed_research` prompt and
  the `polymath://adapter/guide` resource), the `research_acquire` description on both servers (identical), CONNECTORS.md: stop,
  ask your user to open the named site in their own browser on the Polymath host and pass the check themselves, wait for their
  reply, call again with the same query; never try to solve, skip or work around a check; if they cannot, record it in the
  receipt's limitations and continue without that source. Plus the wall line: a fetched verification wall is not evidence, mark
  the source "needs you" and move on. `listings` in the tool description and the guide says it may read through the site's API
  or search-engine results. The guide names no source (the neutrality law).
- **Supplier tools** (`acquisition/supplier.py`, new; routes in `api/acquisition.py`; tools in both servers):
  `supplier_search(query, source="cj", limit=10)`, `supplier_product(product_id)`,
  `supplier_freight(variant_id, country, quantity=1, from_country="CN")`, `supplier_warehouses()` →
  `POST /supplier/search | /supplier/product | /supplier/freight`, `GET /supplier/warehouses`. Search is `service.shape` over the
  same readers (the same record shape and limitations as `research_acquire` listings). Owner-only twice: not in the principals'
  `TOOL_POLICY` (default deny at Server A's gate) and `supplier.authorize` (403 OWNER_ONLY for any principal). The routes share
  `refuse_unless_direct` with `/adapter/{id}/acquire` (PROXIED_CALLER, NON_LOOPBACK_HOST; `acquire`'s messages byte-identical).
  No browser fallback here: a failed API answers UNAVAILABLE with its reason. Web boundary: `^/supplier/(search|product|freight|
  warehouses)$` → OWNER. The connect prompt's "How to use it" list (item 5) and CONNECTORS.md name them as owner-only.
- **SearXNG service**: `compose.yaml` service `searxng` (`searxng/searxng:2026.9.25-12f8b6515`, profile `search`, `127.0.0.1:8888:8080`,
  `deploy.resources.limits` 0.5 CPU / 256M, `./deployment/searxng/settings.yml:/etc/searxng/settings.yml:ro`, `SEARXNG_SECRET`
  passed through unvalued, `FORCE_OWNERSHIP=false` so the container never chowns the repository file). The profile keeps it out of
  `make db-up` (`docker compose up -d --wait`); `boot_polymath.sh` names its four stores. `deployment/searxng/settings.yml`:
  `use_default_settings` with `keep_only: [bing, duckduckgo, brave]`, bing switched on (off in SearXNG's defaults), formats html +
  json, limiter / public_instance / image_proxy off, no `secret_key`, no proxies, no Tor. SearXNG exits at start while its key is
  still the placeholder, so an unset `SEARXNG_SECRET` fails closed. Start: `docker compose up -d searxng`.
- **`.env.example`**: `CJ_API_KEY=`, `SEARXNG_URL=`, `SEARXNG_SECRET=`, one comment line each. No `EXA_API_KEY`, no e-mail.
- **Tests** (all fake HTTP): `tests/contracts/test_supplier_apis.py` (54 cases), `test_supplier_tools.py` (18),
  `test_acquisition_challenge.py` (41), `test_harness_guide_human_check_handoff.py` (13),
  `tests/determinism/test_adapter_ecommerce_supply_join_api_records.py` (2): 128 in all. `tests/determinism/test_mcp_principals_gate.py`:
  `ADMIN_ONLY_TOOLS` gains the four supplier tools (its own rule: every tool is in TOOL_POLICY or admin-only on purpose).
- `architecture/contract-dependencies.yaml` (RESEARCH_ACQUISITION: the new paths and tests; consumed_by ADAPTER_RUNTIME, whose
  `validate_receipt` now imports the detector); `scripts/scaffold_polymath_v4.py` (12 TREE entries).

## Proof
- **Sources read first** (WebFetch, public pages only; no CJ, search-engine or SearXNG API was called): CJ's API 2.0 pages (auth,
  product, logistic, rate limits, global error codes, the MCP guide), Exa's search reference (before the owner dropped it), SearXNG's
  settings / search-API / container docs and its `settings.yml`, `webapp.py`, `webutils.py` and `container/entrypoint.sh` on GitHub,
  Docker Hub's tag list (the pinned tag exists, 2026-09-25).
- **EXECUTED, fake HTTP (`httpx.MockTransport`), the 128 new cases.** What they pin:
  - CJ: one sign-in (key only) for three reads, the token header on every read, the 1.1 s spacing, a new sign-in inside the
    ten-minute margin; a refused token renewed once; 1600200 then 429 waited out (2 s, 4 s) and the read goes on, a rate limit that
    holds fails after 3 tries, a spent quota after 1; the mapping (URL, title, US$ price, discount, no invented minimum order or
    supplier, SKU, category, "100" stores, a stock of "0" kept as "0"), `PARTIAL` with "read 1 of 240"; a stated minimum order
    ("10 units", "1 unit");
  - the fallback for auth / quota / network / HTTP 502: the browser reads, one limitation line names the API and the reason, the
    counter and its reason go up, a warning is logged, and neither the key nor the token appears in the result, the status or the
    log; a fallback that meets a human check is HUMAN_ACTION_REQUIRED and still says the API failed;
  - no key and `SEARXNG_URL=off`: `default_backend()` IS `OpenCLIBackend`; with SearXNG on, a CJ read without a key equals the
    browser's read and its shaped result is byte-identical;
  - SearXNG: the request (`/search`, `site:alibaba.com camera rain cover`, `json`); of 8 results only the 2 product pages stay (a
    tracking query dropped, a duplicate, a showroom, a mobile page, a spoofed path, another site and a verification snippet left out,
    each counted in the notes); price / minimum order / supplier / title parsed verbatim (9 URL cases, 5 snippet cases, nothing
    guessed for "¥18.50" or no price); unreachable, every engine failing, HTTP 403 and a non-JSON answer fall back, said and counted;
    `SEARXNG_URL` on / off / invalid;
  - compose: exactly the four stores + `searxng`, pinned tag, loopback port, 0.5 CPU / 256M, read-only settings, secret passed
    through, profile `search`, no profile on the stores; settings: keep_only bing / duckduckgo / brave, json, limiter off, no secret,
    no proxies, no Tor; `.env.example` has the three names, empty, one comment each, and no Exa or e-mail name;
  - the detector: 15 walls named (Latin and CJK), 13 contents not (B-17's pages, a lyric, "slide to unlock", a plain 403, a CJK
    review that mentions 安全验证, a joke), the module imports no I/O; three interstitials without the old wall words are
    HUMAN_ACTION_REQUIRED once the reader got nothing (unchanged before a read); a wall's listing / search rows dropped, a listing
    read of walls only HUMAN_ACTION_REQUIRED, a comment joke kept; `validate_receipt` refuses exactly the wall quote
    (CHALLENGE_PAGE_AS_EVIDENCE naming observation and source), still accepts the contract's example receipt and a quote that
    mentions a check;
  - the handoff in the guide, the prompt and both tool descriptions (and CONNECTORS.md in the third person); no copy has a sentence
    about solving / skipping / working around / evading / rotating / proxies without "never" or "not";
  - the tools: the same four names, parameters, defaults and descriptions on both servers, not in TOOL_POLICY; ENDPOINTS is the
    sign-in and four reads, the module names no other CJ route, the methods on the wire are POST sign-in / GET search / GET product
    / POST freight / GET warehouses, no tool or route matches order / cart / pay / dispute / listing words; OWNER at the boundary;
    the four routes answer the owner (search's shape = research_acquire's, product + variants + stock, freight options and the
    exact body sent, warehouses), refuse a principal (OWNER_ONLY), a proxy (PROXIED_CALLER) and a foreign Host (NON_LOOPBACK_HOST)
    before CJ is called, refuse 6 bad arguments with 422 before CJ is called, and answer UNAVAILABLE without a key or with SearXNG
    off; through Server A's REAL gate the owner key's `supplier_search` reaches the fake CJ, a friend's key gets 403
    `tool_not_permitted` on all four and never sees them listed, and CJ saw exactly one sign-in and one search;
  - the supply join (the REAL `supply.leads` executor through the supply-join test's harness): a CJ listing and a SearXNG listing,
    shaped and written as the supply intent asks, join as `cjdropshipping` 11.85 / MOQ 1 (the channel default, noted) and
    `alibaba` 2.06-3.49 / MOQ 200 with its supplier; the concept is sourced; CJ's missing supplier is counted, never invented.
- **Fails first.** The guide test run against the base tree (`git archive 5d34fe49`): 6 of 13 fail (the handoff and the wall line
  are missing); a mutated guide saying "If the check is simple, solve it yourself and call again." fails the no-bypass test for the
  guide and the prompt. The other new files cannot import on the base tree (the modules do not exist there).
- **Suites** on the final tree, each exit code checked on its own:
  - `tests/contracts -k "not test_live_"`: 766 passed, exit 0 (640 at `5d34fe49`, + 126 new);
  - the adapter / trail determinism set (every `test_*adapter*` / `test_*trail*` but the four excluded): 308 passed, exit 0
    (306 + 2 new); `tests/determinism/test_mcp_principals_gate.py` and `test_mcp_server_v2.py` also pass;
  - `scripts/agent_preflight.py` ok, `scripts/repo_guard.py` ok, `scripts/wiki_worm.py --check` ok (its two open work logs are
    DR4 and DR6d, not this one);
  - ruff: no new findings (62 in the touched files at `5d34fe49`, 62 now, all pre-existing; the new files are clean).
- **Not proven here:** no live CJ, SearXNG or search-engine call, no container started, not merged, not deployed.

## Rejected claims
- "Exa for alibaba.com": dropped by the owner (no new accounts). Nothing of it remains.
- "Wrap or configure CJ's official MCP server": rejected by the owner. It exists (CJ's docs, `developers.cjdropshipping.com/en/api/
  api2/mcp.html`: remote `https://developers.cjdropshipping.com/mcp/<MCP token>` over streamable HTTP, or local stdio from
  `github.com/CJ-dropshipping/api-mcp`; 17 tools incl. `create_order`, `add_to_cart`, `create_dispute`, `merge_orders`), and its
  one token reaches every one of them. Nothing here installs or calls it.
- "CJ's sign-in needs the account e-mail": not in API 2.0 (the key alone); `CJ_ACCOUNT_EMAIL` was not added.
- "An API that answers with nothing should fall back to the browser": no. An empty answer is an answer (EMPTY, one query spent,
  as the browser's); falling back would send the read straight into the check the API avoids.
- "Run the detector before a read, too": no. B-17's pinned test (`test_a_wall_word_still_names_the_wall_when_the_page_gave_nothing`)
  requires the reader to run on a page whose title only mentions a check; the detector joins the wall words once the reader got
  nothing, as they do.
- "Filter comment reads through the detector": no. Comments come from the sites' own comment lists (JSON), never from a wall; a
  comment that jokes "Captcha? I'm not a robot" would have been lost.
- "Fall back to the browser inside the supplier tools": no. They are API-only (no owner's browser, no human check); a failure says
  why.
- "Crawl the product page live for fresher prices": no. The search engines' snippet as indexed is the data (the limitation says the
  listing page was not opened and may have changed); nothing fetches alibaba.com for us.

## Open contract gaps
- DISPOSITIONS (scripts/contract_impact.py over the changed files): RESEARCH_ACQUISITION **UPDATED**; ADAPTER_RUNTIME **UPDATED**
  (validate_receipt refuses a quoted wall; the guide text); MCP_SURFACE **UPDATED** (four tools; research_acquire's description);
  EVIDENCE_PACKET / EVIDENCE_BOUNDARY_API **NOT_AFFECTED**; TrailSignal's receipt parity **TESTED_UNCHANGED**
  (`test_harness_receipt_trail_parity.py` passes: the new refusal is stricter than Trail and happens before Trail sees a receipt).
- **ADR-0003 says compose holds exactly the data stores.** The owner decided to add SearXNG (a non-model, loopback-only metasearch,
  opt-in by profile). The ADR amendment and the register row are the lead's; this slice wrote neither.
- **Live proof is the owner's**, three steps: put `CJ_API_KEY` (My CJ > Authorization > API) and a random `SEARXNG_SECRET` in `.env`;
  `docker compose up -d searxng`; merge + bounce, then one `supplier_search` per source and one supply step through
  `research_acquire`. Unverified until then: CJ's encoding of the `features` array in a GET (sent as `features=enable_category`;
  a refusal would fall back, said); `directMinOrderNum` (documented, read only when present); whether CJ serves the product page
  under the built URL's slug (the `-p-<pid>` part is the product; the slug is derived from the English name); what the three
  engines' snippets hold for alibaba.com product pages (often no price: then "not shown", never guessed).
- **SearXNG is on by default** (the owner's "defaults to http://127.0.0.1:8888"): until it runs, every alibaba.com listing read tries
  it first, is refused at once, and falls back to the browser with one limitation line and one counted fallback. `SEARXNG_URL=off`
  restores the old path exactly. The CJ path is byte-identical without a key (tested).
- The engines SearXNG asks can rate-limit or challenge SearXNG itself: SearXNG reports them as unresponsive, the note names them, and
  a read where every engine failed falls back. Nothing tries to get past them.
- `SEARXNG_SECRET=` left EMPTY in `.env` would start SearXNG with an empty key (only an unset one fails closed): the template says
  "never empty". Harmless for a loopback JSON reader, but not the intent.
- The fallback counters and the token cache live in the orchestrator process (a bounce resets them), like the query budget (S-09).
- A harness that uses `supplier_search` at a research step writes its own `tool_trace` row (the tools are not bound to a step);
  the guide says so.
