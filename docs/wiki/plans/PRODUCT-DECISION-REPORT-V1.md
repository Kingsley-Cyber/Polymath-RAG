---
title: "PRODUCT-DECISION-REPORT-V1 — one HTML decision report per product search, compiled by Polymath for any agent"
last_reviewed: 2026-11-02
last_touched: 2026-11-02
status: plan-of-record (owner approved 2026-11-02)
---

# PRODUCT-DECISION-REPORT-V1

## 0. The owner's request (2026-11-02, verbatim) and decisions
"I need the web search to essentially know regardless of claude, deepseek, or codex to create a html compiled report of products
with links reddit findings that signals this is good, a finacial report from the standpoint of a drop shipping for profit margins, it
should take into account moq and other realted info needed to make a decision from alibaba and cj dropshipping, to include delivery
time. Imagine if i had a tik tok shop that has a strict delivery time or of i had my own shopify which is very free and loose with
delivery time, this is info i must know. And for profit margins analysis, ebay and amazon should be used to compare similar products
as of now which is important from a dropshipper perspective so they can analyze the market. ... If subagents increase the speed of
this then look into how that works with subagents call and initiations for closed source models and opensource models ... this should
be annotated and executed and should follow proper developer steps".

Decisions (2026-11-02): reports are **stored privately** per user (one migration); TikTok Shop is shown **both** as a US local account
and as a cross-border account; the money model uses **19.3 % returns** (NRF, 2025-10-15) and shows **break-even ad cost** instead of
an assumed ad cost. Standing rules from PRODUCT-SEARCH-E2E-V1 (register 11.575): web reads only through the user's LOCAL Agent Reach
(never an agent's built-in web search); CJ through the official API on the host for every user; the connected agent does all
reasoning; deterministic code does every number.

## 1. Measured facts the design rests on (2026-11-02; raw outputs kept as test fixtures)
| Source | Path | Result |
|---|---|---|
| CJ | API, host | product (weight, price, suggested retail), freight per carrier CN→US and US→US with cost + days; stock by country came back `[]` (a US quote does NOT prove US stock); keyword search can return near misses |
| Alibaba | user's Agent Reach: Exa 16/16, Jina pages 2/4 (Akamai) | price tiers, MOQ, "Delivery Time 7-15 Days", lead-time table, supplier rating, on-time dispatch, transit "Est. 17-24 days", per-kg shipping |
| Amazon | user's Agent Reach: Exa 16/16, Jina 3/3 (search page needs `X-With-Links-Summary: true` for ASINs) | price, rating, rating count, BSR, "bought in past month", delivery text (Amazon-fulfilled only) |
| Reddit | user's Agent Reach: Exa 16/16; Jina 0/7 (blocked) | title, subreddit, date, 1–3 comments with points + text; full threads unavailable |
| eBay | Jina 0/5 (403), Exa mostly non-US | needs the eBay **Browse API** (host, the owner's free developer key: `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`); sold history (Marketplace Insights) is restricted — not used |
| Rate limits | keyless Exa 429 at 4 parallel; keyless Jina 20/min per IP; CJ ~1/s | the fetch script paces itself; optional user keys `EXA_API_KEY` (10 QPS) / `JINA_API_KEY` (500 RPM) speed it up |
Jina answers HTTP 200 even when the target blocks it: block markers are `Warning: Target URL returned error 403`, titles `Blocked`,
`Error Page | eBay`, `Access Denied`, `whoa there, pardner!`, "You've been blocked by network security".

## 2. Channel rules and fees (official pages read 2026-11-02; printed with their URL and date in every report)
| Channel id | Delivery rule (H = days to first carrier scan, D = delivery days) | Fee per order |
|---|---|---|
| `tiktok_us` | FAIL if shipped from China; PASS from a US warehouse only if H ≤ 2 and D ≤ 6 business days (custom handling 3–7: D ≤ H + 5) | 6 % × (price + shipping) — 8 % sensitivity (UNCONFIRMED, trade blogs) |
| `tiktok_cross_border` | PASS if in transit ≤ 3 calendar days and delivered ≤ 15 calendar days, else FAIL | same |
| `shopify` | PASS (FTC: ship within the stated time or 30 days); WARN if D > 7 (McKinsey norm) | 2.9 % × (price + shipping) + $0.30 + plan ÷ monthly orders (Basic $39, owner may change) |
| `ebay` | PASS with an honest handling time; free-shipping badge only if H ≤ 1 and D ≤ 4 business days (report shows badge eligibility) | 13.6 % × (price + shipping) + $0.30 (≤ $10) / $0.40 (> $10) |
| `amazon_fbm` | PASS with an accurate promise; WARN as D grows; Prime FAIL from China | max(15 % × (price + shipping), $0.30) + $0.99 per item |
Common lines: returns allowance 19.3 % of revenue × (unit cost + shipping) — owner setting; chargebacks are not modelled per unit;
ad cost is reported as **break-even ad cost per sale** (= margin before ads). Sources: TikTok seller university (knowledge ids
3995852763301633, 8308896260065025, 7089769777235729, 5988482086864682), shopify.com/pricing, ebay.com/help ids 4822 / 4086 / 4176,
sell.amazon.com/pricing and Seller Central G201817070 / G201808410, nrf.com 2025-10-15, mckinsey.com 2025-02-13 (full URLs in
`adapters/ecommerce/graph/policies.yaml` `sales_channels`).

## 3. Flow (model-agnostic)
1. `product_report_start` (MCP) → `POST /product/report/start {message?, corpus_id?, corpus_ids?, products?: [{title, search_terms[]}],
   ship_to: "US", channels?: [...], max_products? (default 5, cap 8)}`. Products come from the caller, or — when absent — from the
   product route's hypotheses (PRODUCT-SEARCH-E2E-V1, run internally in the background). Returns at once: `report_id`, `status`,
   candidates (when known), host-data status, and the **round-1 fetch plan** with a one-time upload capability.
2. Host data (background): CJ search → relevance filter → product → freight CN→US and US→US per candidate; eBay Browse API comps when
   configured (else `EBAY_NOT_CONFIGURED`).
3. The agent runs the fetch **script** (one shell command) on the user's machine: every Agent Reach read for that round, paced,
   uploaded straight to Polymath. Raw pages never pass through the model. Round 2 (product pages chosen from round-1 results) comes
   from `product_report_status`.
4. Polymath parses each upload deterministically, matches comparables to candidates, keeps receipts.
5. `product_report_compile(report_id, verdicts?)` → the decision model (unit economics + delivery verdicts, engine, out of process)
   → HTML (the existing dossier renderer, DECISION layout) → stored privately → link.
6. Users without a terminal: steps 1, 2, 4, 5 still run (CJ + eBay); the report marks the Agent Reach sections "needs a local agent"
   and shows the script so anyone with a terminal can run it for that report.

## 4. Interfaces (each slice builds exactly these; names are binding)
### 4.1 Parsers — `shared/polymath_shared/acquisition/agent_reach.py` (B1)
`parse_report_source(source: str, raw_text: str, *, kind: str, candidate_terms: list[str] | None = None) -> dict`
→ `{status: OK|EMPTY|BLOCKED|HUMAN_CHECK|UNRECOGNISED, source, kind, records: [...], next_targets: [{url, source, kind: "page", why}], refused: [{url?, code, why}]}`
- `source="reddit"` (Exa text): records `{kind:"thread", title, subreddit, url, published_at, score, comments_count, comments:[{author, points, date, text}], links:[...]}` (missing fields null).
- `source="amazon"`: Exa text, a Jina search page (with links summary → ASINs into `next_targets`), or a Jina product page → `{kind:"listing", asin, title, url, price_usd, list_price_usd, rating, ratings_count, bsr:{rank, category}, bought_past_month, delivery_text, fulfilled_by, prime}`.
- `source="ebay"` (Exa fallback only) → `{kind:"listing", title, url, domain, price, currency, shipping_text, location, delivery_text, sold_count, condition, us_listing: bool}`.
- `source="alibaba"`: the existing listing parse PLUS `{lead_time_text, lead_time_days_min, lead_time_days_max, delivery_estimate_text, transit_days_min, transit_days_max, shipping_per_kg_usd, on_time_dispatch_rate, ships_to}`; product pages from Exa results go to `next_targets`.
- Block / check pages → `BLOCKED` / `HUMAN_CHECK`, nothing admitted. Every text field stays untrusted supplier/page text.

### 4.2 Fetch plan — `shared/polymath_shared/product_search/fetch_plan.py` (B1)
`build(report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] | None = None) -> dict`
→ `{round, packets:[{packet_id, candidate_id, source, kind, commands:[str], expect}], script, script_sha256, limits:{exa_parallel, jina_per_minute}, how}`
- Round 1 per candidate: Reddit (2 Exa queries), Amazon (1 Exa + 1 Jina search page with links summary), Alibaba (1 Exa), eBay (1 Exa,
  only when the host has no eBay API). Round 2: page reads from `targets` (≤ 3 Amazon product pages, ≤ 3 Alibaba pages per candidate).
- `script`: POSIX `bash`, needs `mcporter` + `curl`; uses `EXA_API_KEY` / `JINA_API_KEY` if set (faster limits), otherwise paces to
  keyless limits (Exa ≤ 3 in flight, Jina ≤ 20/min); each output is POSTed as `text/plain` to `upload.url` with `?packet=<packet_id>`;
  prints a one-line summary per packet; exits 0 even when a source is blocked (the upload records it). No `eval` of fetched content.

### 4.3 Host data — `shared/polymath_shared/product_search/host_data.py` + `shared/polymath_shared/acquisition/ebay_api.py` (B2)
`collect(candidates: list[dict], *, principal_id: str | None, ship_to: str = "US", supplier_fns=None, ebay=None) -> dict`
→ `{cj: {candidate_id: {status, reason_code, products:[{product_id, title, url, image, sell_price_usd, suggested_retail_usd, weight_g, variants:[{variant_id, price_usd, weight_g}], freight:{"CN":[{carrier, cost_usd, days_min, days_max}], "US":[...]}, us_stock_confirmed: bool}], relevance:{kept:[...], dropped:[...]}}}, ebay: {candidate_id: {status, reason_code, listings:[{title, url, price_usd, shipping_usd, delivery_min, delivery_max, location, condition}]}}, receipts:[...]}`
- CJ: ≤ 3 relevant products per candidate (title must hold the candidate's head terms), cheapest variant, freight from CN and from US.
- eBay Browse API: client credentials (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`), `X-EBAY-C-MARKETPLACE-ID: EBAY_US`, ship-to US context;
  paced; breaker; `EBAY_NOT_CONFIGURED` when the keys are unset (never an error).

### 4.4 Unit economics — `adapters/ecommerce/python/unit_economics.py` + `adapters/ecommerce/graph/policies.yaml` `sales_channels` (B3)
Engine-side, pure: `compute(bundle: dict, policy: dict) -> dict` (invoked out of process with a JSON bundle, like the dossier).
`bundle = {candidates, host (4.3), parsed: {candidate_id: {reddit:[...], amazon:[...], ebay:[...], alibaba:[...]}}, settings}`
→ `{products:[{candidate_id, title, offers:[{offer_id, source: cj|alibaba, url, unit_cost_usd, moq, moq_capital_usd, shipping:[{origin, carrier, cost_usd, days_min, days_max}], lead_time_days}], market:{amazon:{n, median, min, max}, ebay:{n, median, min, max}, reference_price_usd, basis}, demand:{reddit:{threads, comments, newest, signals:[...]}, amazon:{bought_past_month_max, bsr_best, ratings_count_max}}, channels:{<channel_id>:{sell_price_usd, unit_cost_usd, shipping_usd, fees_usd, returns_usd, margin_before_ads_usd, margin_pct, break_even_ad_cost_usd, delivery:{verdict: PASS|WARN|FAIL|UNKNOWN, reason, origin, days_max}}}, sensitivity:{tiktok_8pct:{...}}, receipts:[...]}], assumptions:{...each with source url + date}}`.
Every number carries a receipt (inputs → formula → result); a missing input yields `UNKNOWN`, never a guess.

### 4.5 Renderer — `adapters/ecommerce/python/report.py` + `shared/polymath_shared/adapter/dossier.py` (B4a)
`report.build_model_from_bundle(decision) -> ReportModel` + a `DECISION` layout; `dossier.render_decision(bundle) -> {"html": str,
"decision": dict}` runs ONE engine subprocess (the dossier's existing pattern: the engine never imports `shared`) that calls
`unit_economics.compute(bundle, policy)` (4.4), then `build_model_from_bundle`, then renders with the same sanitizer. http(s) links become real anchors (`rel="noopener noreferrer"`, `target="_blank"`); every other scheme
stays plain text (the existing `javascript:` pin in `tests/contracts/test_adapter_dossier.py` must keep passing). Governed runs:
`build_model_from_governed` gains the same decision section from admitted S_supply leads and P_reality prices (one renderer, rows
labelled TrailSignal-admitted vs unadmitted).

### 4.6 Service, storage, routes — `orchestrator/orchestrator/api/product_report.py`, `shared/polymath_shared/product_search/report_store.py`, migration `0068_product_reports.sql` (B4b)
- Tables: `product_reports(report_id pk 'rpt_'+24 hex, owner_principal_id, status collecting|compiling|compiled|failed, request jsonb,
  candidates jsonb, host jsonb, model jsonb, html text, verdicts jsonb, upload_token_sha256, upload_expires_at, round int, created_at,
  updated_at)`, `product_report_uploads(report_id, packet_id, round, source, kind, received_at, bytes, sha256, status, parsed jsonb,
  refused jsonb, PRIMARY KEY(report_id, packet_id))`.
- Routes: `POST /product/report/start`; `GET /product/report/{id}/status` (progress, candidates, host status, the current round's fetch
  plan, upload counts); `POST /product/report/{id}/upload/{token}?packet=<id>` (CAPABILITY: no session, token checked by sha256, ≤ 2 MB
  per upload, ≤ 300 uploads, expires 6 h); `POST /product/report/{id}/compile {verdicts?: {candidate_id: text ≤ 1200 chars}}`;
  `GET /product/report/{id}` (HTML, CSP without scripts); `GET /product/reports` (the caller's list).
- Privacy: owner sees all; a principal sees only its own (same rule as adapter runs). Upload URLs: `http://127.0.0.1:7200/...` for a
  local caller and `{public_base}/...` for a remote one.

### 4.7 Agent surface (B5)
MCP tools on both servers: `product_report_start`, `product_report_status`, `product_report_compile`, `product_report_list`; TOOL_POLICY
rows for friends; the playbook gains the report loop (start → run the script → status → round 2 → compile) and the subagent recipe per
harness (workers on a cheap model at low effort, never fetching through a model when the script can; Claude Code workers block
WebSearch/WebFetch; Hermes children run Agent Reach in the terminal; raise MCP tool timeouts in Codex/OpenCode).

### 4.8 Web UI (B6)
"Build decision report" on the product cards (sends the hypotheses as `products`); a Reports list; open a report; for web users the
script is shown with a copy button and the upload capability, so anyone with a terminal can feed the report.

## 5. Gates
Unit + contract tests per slice on recorded real fixtures; the full sealed suite (throwaway Postgres) with no failure outside the
17 that fail on untouched production; a sample report compiled end to end from recorded fixtures (published for the owner); after the
owner's deploy, one live report through the connector as the owner and one as a friend key. Register row IMPLEMENTED until the live gate.
