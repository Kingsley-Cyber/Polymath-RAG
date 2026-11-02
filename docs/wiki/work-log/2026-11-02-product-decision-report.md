---
change_id: PRODUCT-DECISION-REPORT-V1
owner: "@king"
date: 2026-11-02
status: complete
status_note: "One HTML decision report per product search, compiled by Polymath for any agent (Claude, Codex, DeepSeek): CJ (official API, on the host) and eBay Browse API comparables; Reddit, Amazon and Alibaba read by the user's LOCAL Agent Reach through one generated script that uploads raw outputs to a capability URL (raw pages never pass through the model); deterministic parsers; unit economics with dropship and inventory models and delivery verdicts per channel (TikTok US and cross-border side by side, Shopify, eBay, Amazon FBM), 19.3 % returns and break-even ad cost; stored privately per principal; four MCP tools on both servers; a web panel and a Reports screen. Three adversarial reviews (security, correctness, reliability) plus deterministic scans (graft, graphify, the failure-pattern ledger); every confirmed finding fixed and re-verified."
architecture_impact: "New: orchestrator api/product_report.py (6 routes), product_search/{fetch_plan,host_data,report_store}.py, acquisition/ebay_api.py, adapters/ecommerce/python/unit_economics.py, migration 0068 (product_reports, product_report_uploads), contracts/product/v1/product_report.schema.json, ADR-0023 (the capability upload route), the web ProductReport panel and Reports screen. Changed: agent_reach.py (report parsers), dossier.py + report.py (DECISION layout), policies.yaml (sales_channels, report_settings), web_boundary.py (CAPABILITY class, sign-in redirect), json_logging.py (token redaction), api/product.py (Host check), both MCP servers (4 tools, upload-token cache), mcp_principals.py (TOOL_POLICY rows, corpus-id strip), mcp_retrieval.py (report loop, subagent recipe), contract map (PRODUCT_SEARCH, PRODUCT_REPORT)."
last_reviewed: 2026-11-02
---

# PRODUCT-DECISION-REPORT-V1: one HTML decision report per product search, for any agent

## Contract
The owner, 2026-11-02 (verbatim):
- "I need the web search to essentially know regardless of claude, deepseek, or codex to create a html compiled report of products
  with links reddit findings that signals this is good, a finacial report from the standpoint of a drop shipping for profit margins, it
  should take into account moq and other realted info needed to make a decision from alibaba and cj dropshipping, to include delivery
  time. Imagine if i had a tik tok shop that has a strict delivery time or of i had my own shopify which is very free and loose with
  delivery time, this is info i must know. And for profit margins analysis, ebay and amazon should be used to compare similar products
  as of now which is important from a dropshipper perspective so they can analyze the market. This is important concept. If subagents
  increase the speed of this then look into how that works with subagents call and initiations for closed source models and
  opensource models to be used for claude and chat gpt the most capable but token efficient modle and effort can be importnat. On top
  of that this should be annotated and executed and should follow proper developer steps in order to ensure any code changes and
  merges and git since i know little about coding and workflows."
- "For the reddit it doesnt need to be a full lsit of comments just comemnts with dates and summary. But so far i like your plan this
  ends when commitedd and merged properly no bugs, but also reasonable scan of logic based on code archetype and follow of of it use
  graft and graphify deteministic to scan and anticipate areas where codes might have bugs. And run the flow one time and analzye the
  output. This should work simply if someone was to connect to the mcp with a agent so guage how easy and well this works with nl and
  how well a new session agent that just connected grasps the tools/mcps and simply works e2e."
- Decisions (asked 2026-11-02): "Store privately (Recommended)"; "Both, side by side (Recommended)" (TikTok US and cross-border);
  "19.3% returns, ads as break-even (Recommended)".
- Plan of record: `docs/wiki/plans/PRODUCT-DECISION-REPORT-V1.md` (owner approved 2026-11-02). Standing rules from PRODUCT-SEARCH-E2E-V1
  (register 11.575): web reads only through the user's local Agent Reach, never an agent's built-in web search; CJ through the official
  API on the host; the connected agent does all reasoning; deterministic code does every number.

| # | Requirement |
|---|---|
| N1 | Any agent (Claude, DeepSeek, Codex) can produce the HTML report, without its own web search |
| N2 | Products with links |
| N3 | Reddit findings that signal demand: comments with dates and a summary, not the full list |
| N4 | A profit-margin report from a dropshipper's standpoint |
| N5 | MOQ and the other decision facts from Alibaba and CJ |
| N6 | Delivery time judged per channel: strict TikTok Shop versus loose Shopify |
| N7 | eBay and Amazon comparables for market and margin analysis |
| N8 | How subagents could speed it up, for closed and open models: the most capable but token-efficient model and effort |
| N9 | Annotated, executed, proper developer steps (branches, commits, merge) |
| N10 | Committed and merged properly, no bugs |
| N11 | A deterministic logic scan by code archetype with graft and graphify, anticipating where bugs may be |
| N12 | The flow run once and its output analysed |
| N13 | A freshly connected agent understands the tools from plain language and works end to end; ease gauged |
| D1 | Reports stored privately per user |
| D2 | TikTok US and cross-border shown side by side |
| D3 | 19.3 % returns; ads as break-even ad cost |

## Measured (2026-11-02, before the build; raw outputs kept as test fixtures)
- Data access through the user's Agent Reach: Reddit Exa 16/16, Jina 0/7 (blocked); Amazon Exa 16/16, Jina 3/3 (the search page needs
  `X-With-Links-Summary: true` to list ASINs); Alibaba Exa 16/16, Jina pages 2/4 (Akamai); eBay Jina 0/5 (403) and Exa mostly non-US, so
  eBay comparables need the eBay Browse API on the host (the owner's free developer keys; sold history is restricted and not used).
- Rate limits: keyless Exa answers 429 at 4 parallel calls; keyless Jina allows 20/min per IP; CJ about 1/s. CJ freight answers per
  carrier CN→US and US→US with cost and days; CJ stock by country came back empty, so a US quote does not prove US stock.
- Channel rules and fees: plan §2 (official pages read 2026-11-02; URLs and dates in `adapters/ecommerce/graph/policies.yaml`).
- Subagents (N8): researched for Claude Code, Codex, OpenCode and Hermes with Claude (Opus / Sonnet / Haiku 5.5, Fable 5.1), OpenAI
  (GPT-6.1 Sol / Terra, GPT-6 Luna) and DeepSeek (v4.1 flash, v4 pro). Finding: the fetch work is I/O bound and paced by the sources'
  limits, so one generated script beats model subagents (no model tokens on raw pages, and parallel model fetches hit the same 429);
  subagents help only for per-candidate reasoning, on a cheap model at low effort, and an inherited default (the parent's model and
  effort) is the expensive trap; Claude Code workers must block WebSearch / WebFetch; Hermes children have their own web tool, not Agent
  Reach; OpenCode had no Polymath MCP configured. The recipe per harness is the agent-facing `REPORT_SUBAGENTS` text
  (`shared/polymath_shared/mcp_retrieval.py`) and `mcp_server/CONNECTORS.md` section 5.

## Changes (seven parallel slices, three reviews, one fix round)
- **B1 parsers and fetch plan** (`acquisition/agent_reach.py`, `product_search/fetch_plan.py`): `parse_report_source` for Reddit (Exa;
  dated comments, at most 5 per thread, highest points first, 300 characters), Amazon (Exa, Jina search page with links, Jina product
  page), eBay (Exa fallback) and Alibaba (tiers, MOQ, lead-time table, transit, per-kg and minimum shipping, quotes for a stated quantity,
  on-time dispatch, `ships_to`); block and check pages give BLOCKED / HUMAN_CHECK and admit nothing. `fetch_plan.build` writes one POSIX
  bash script per round (Exa via `mcporter`, Jina via `curl`), paced to keyless limits (Exa ≤ 3 in flight, Jina ≤ 20/min) unless the user
  has keys, uploading each output as text to the capability URL; empty outputs are uploaded as EMPTY.
- **B2 host data** (`product_search/host_data.py`, `acquisition/ebay_api.py`): CJ search → whole-word relevance filter → product →
  freight CN→US and US→US (at most 4 CJ calls per candidate, through the per-principal fair use); eBay Browse API comparables (US
  marketplace, ship-to header, pacing, breaker, `EBAY_NOT_CONFIGURED` without keys) through the same fair use.
- **B3 unit economics** (`adapters/ecommerce/python/unit_economics.py`, `policies.yaml` `sales_channels` + `report_settings`): per
  candidate, offers (CJ = dropship; Alibaba = inventory: inbound by the listing's QUOTE / PER_KG / MIN_KG / MIN_CHARGE rule, time to first
  stock = lead time + transit, MOQ capital plus inbound = cash before first stock, last mile per channel from the cheapest passing CJ US→US
  quote or the owner's setting), market (Amazon and eBay medians), demand (Reddit summary, comments, excluded threads; Amazon bought / BSR
  / ratings), and per channel the fees, returns (19.3 %), margin before ads, break-even ad cost and a delivery verdict with the seller's
  handling time; the TikTok 8 % what-if. Every number has a receipt; a missing input gives UNKNOWN.
- **B4a renderer** (`adapters/ecommerce/python/report.py`, `shared/polymath_shared/adapter/dossier.py`): `build_model_from_bundle`, the
  DECISION layout (summary, links, demand, supply with the US-stock caution, market, margins whose rows add up, the 8 % what-if, the
  agent's verdict, receipts, assumptions), `report.py decision`, `dossier.render_decision` in one engine process; http(s) links only.
- **B4b service** (`api/product_report.py`, `product_search/report_store.py`, migration 0068, `contracts/product/v1/`): the six routes,
  background product turn and host collection as the caller's principal, private storage, the capability upload (ADR-0023), receipts.
- **B5 agent surface** (both MCP servers, `mcp_principals.py`, `mcp_retrieval.py`, `CONNECTORS.md`, `web_settings.py`,
  `capabilities.py`, `hosted_mcp_acceptance.py`): `product_report_start / _status / _compile / _list`, friend policy rows, the report loop
  in the playbook and the subagent recipe per harness, the connect prompt's step 8.
- **B6 web UI** (`components/ProductReport.tsx`, `lib/productReport.ts`, `screens/Reports.tsx`): "Build decision report" on the
  product cards, the report panel (round, script with a copy button, uploads, Compile, Open), the Reports screen.
- **Coordinator**: the contract map (`PRODUCT_SEARCH`, `PRODUCT_REPORT`; `MCP_SURFACE` depends on both), scaffold declarations, ADR-0023,
  the review briefs and the fix contracts below, the `Reports` prop and two stale comments in the web app.
- **Review fixes** (all confirmed findings; the reviews are summarised under Reviews):

| Review | Finding | Fix |
|---|---|---|
| R1 #1 | DNS rebinding: report routes and `/product/search` had no Host check | `refuse_unless_mcp_or_web` first in every report route and `/product/search`; upload refuses a non-proxied non-loopback Host |
| R1 #2 | one friend could spend the owner's eBay quota and hold every report worker | eBay through the per-principal fair use; one background job per principal (429 REPORT_JOB_RUNNING) |
| R1 #3 | a bad upload token still cost a 2 MiB read | capability checked before the body |
| R1 #4 | upload token in access logs and browser storage | log redaction; memory-only token in the web panel |
| R1 #5 | the MCP gate checked the raw corpus id but forwarded a stripped one | ids stripped in `authorize` |
| R2 #1 | delivery checks ignored the seller's handling time | `handling_business_days` (default 1) in every order-clocked rule; printed in each reason |
| R2 #2 | a price range was costed at its low end | `unit_price` = high end, `unit_price_low` kept |
| R2 #3 | a sponsored Amazon ad's numbers leaked into the result above it | a result block ends at `## [` or "Sponsored" |
| R2 #4 | lead time came from the smallest-quantity row | the row holding the MOQ; "to be negotiated" gives UNKNOWN |
| R2 #5 | "capital" left out the MOQ order's freight | cash before first stock = goods + inbound |
| R2 #6 | CJ relevance matched words inside words | whole words, plurals, or 2–3 adjacent words joined (CJ and eBay) |
| R2 #7 | Reddit relevance dropped most threads and the report hid it | title rule on the term's key words; excluded threads listed |
| R2 #8 | Amazon's robot check parsed as OK | HUMAN_CHECK |
| R2 #9 | cross-border US stock only a note; `ships_to` unchecked; last mile across weights; "business days" lost | verdict by the US-warehouse rule; destination checked; 25 % weight rule; `days_unit` |
| R3 #1 | report jobs blocked a restart (non-daemon pool) | daemon threads |
| R3 #2 | status polling minted tokens and evicted the agent's | at most one mint per report per 60 s for callers without a token; a held token is reused |
| R3 #3 | a report could stay `compiling` | `compile_started_at`, stale after 300 s, COMPILE_SAVE_FAILED, U+0000 stripped |
| R3 #4 | uploads during the render were left out silently | staleness by the (packet, sha256) set |
| R3 #5 | one oversize packet stalled its round | OUTPUT_TOO_LARGE row |
| R3 #6 | receipts hid degraded runs | `host.degraded`, `host.reasons`, receipt `meta.degraded`, the product turn's receipt id kept |
| R3 #7 | the report link gave a JSON 401 to a browser without a session | 302 to the /v2 sign-in, which returns to the report |

- **Verify round** (the same three reviewers re-read the fixed code; 20 of 21 findings FIXED, R2 #7 PARTIAL, R1 #2 PARTIAL) and a
  second fix round:

| Review | Finding (verify round) | Fix |
|---|---|---|
| R2 #7, N3 | Reddit rule took the term's last two words (0 of 8 threads kept for "slicker brush for long hair dogs") yet admitted "Cleaning my paint brush" | one head-word definition (`agent_reach.head_terms`, cut at "for" / "with" / ...) shared by CJ, eBay, Amazon, Alibaba and Reddit; a thread title must name the product's first two head words side by side |
| R2 round-1 miss | a candidate without search terms got "candle warmer lamp timer jar" (2 of 7 Amazon matches, below the 3-comparable minimum) | `hypotheses._terms` derives the default term from the title's head words ("candle warmer lamp") |
| R2 N1 | the robot-check wording refused real Exa content quoting it | only a whole line of a short Jina page |
| R2 N2 | handling added to calendar-day rules without the worst week | a Friday order is scanned on Monday: 3 calendar days |
| R2 N4 | per-unit and total inbound rounded apart; three stale assumption texts | per-unit derived from the total (4 decimals); texts read the policy |
| R3 NEW-1 | a worse re-upload replaced a good packet | an OK packet is never replaced by a non-OK one (`kept_earlier`) |
| R3 NEW-2 | a `required` answer carried a script that cannot upload | `fetch_plan.script` null with `script_withheld` (also on `expired`); agent texts say to call status after `mint_after` |
| R3 NEW-3 | one owner job slot, no deadline, restarts ignored claims | owner 2 slots, a friend 1; a claim lapses after 15 min; restarts go through the claim |
| R3 NEW-4 | 0068 edited in place | `ADD COLUMN IF NOT EXISTS compile_started_at` |
| R1 #2 | one friend could still spend the keyset's 5,000 eBay calls a day | 300 eBay searches per friend per UTC day (`EBAY_DAILY_LIMIT`), owner exempt |
| R1 N1 (CRITICAL, already on `production`) | a DNS-rebinding page could read the owner's MCP key (`GET /keys/owner`) or reset the owner's web password (`POST /auth/owner-password`) | the web boundary refuses every request without proxy headers whose Host is not loopback |

## Review-fix contracts C1–C10 (the code comments cite these labels)
- **C1 upload tokens.** `upload.token` is minted | reused | required | expired | none. Start always mints (and returns `upload_token`).
  A held token sent in `X-Upload-Token` is reused. Without one, a token is minted at most once per report per 60 s, else `required` with
  `upload.mint_after`. A wrong token counts as absent. Both MCP servers keep the token per report (Server A per principal and report) in
  memory and send it back; the web panel keeps it in memory only.
- **C2** every CJ freight option carries `days_unit` (business | calendar | null); null is read as the policy's `supplier_days_read_as`.
- **C3** Alibaba tiers: `unit_price` is the high end of a range, `unit_price_low` the low end.
- **C4** Reddit relevance is a per-record `relevant` flag set by the parser; the report lists the excluded threads.
- **C5** inventory offers carry `moq_inbound_usd` and `cash_to_first_stock_usd`; the sentence is "requires holding US stock: first stock in
  N days, cash $X before first stock (goods $G + inbound $I)".
- **C6** host data stays `done` when collection returns, with `degraded` and `reasons`; the compile receipt's `meta.degraded` holds the
  host reasons and the non-OK upload counts; the product turn's receipt id stays on the report.
- **C7** a browser opening a report page without a session gets 302 to the /v2 sign-in (JSON 401 for other clients); agent texts say the
  link opens in a browser signed in to Polymath.
- **C8** start answers 429 REPORT_JOB_RUNNING (`retry_after_s`, the running `report_id`) while the principal's background-job slots
  are full: the owner has 2, a friend 1; a slot lapses after 15 minutes; a lost stage restarts only by taking a slot.
- **C9** `compile_started_at`; a compile older than 300 s may run again; a failed save after the render leaves the report `failed` with
  COMPILE_SAVE_FAILED; U+0000 is stripped before every jsonb or text write.
- **C10** an upload over 2 MiB is answered 413 and recorded as an OUTPUT_TOO_LARGE packet.
- **C11** the compile bundle carries `sources` (per Agent Reach source: packets planned, received, statuses); the page says "Needs a
  local agent" for a source with nothing uploaded and "could not be read" for one with no OK upload (plan §3.6).

## Reviews and deterministic scans (N11)
- **graft 0.18.0** (`--dir` outside the repo): `build`, then `blast` of the working tree against HEAD at depth 2 — 92 changed files in
  6 areas, 773 seed symbols, 44 impacted symbols in 9 areas; the untested-looking hubs it flagged (`_refuse`, `_dict`, `_s`, `_adapter`)
  were checked by review R3: name collisions with unchanged functions elsewhere, and `_adapter` only gained a timeout default.
- **graphify** (AST only, no model): 84 changed and neighbouring files, 3,397 nodes, 7,155 edges, 150 communities; its hubs and bridges
  (unit_economics, report_store, host_data, ebay_api, product_report, the MCP servers, web_settings) set the reviewers' focus; the engine's
  import boundary holds (the engine never imports `polymath_shared`; its own test checks it).
- **Failure-pattern ledger** (`docs/codewiki/failures/_patterns.json`, 225 patterns): the 158 that apply to this code archetype
  (parsers of untrusted pages, money arithmetic, capability routes, background jobs, agent texts) went to the reviewers as a checklist.
- **Three adversarial reviews** (read-only, own sealed databases): R1 security (5 findings), R2 parsers and money (9), R3 reliability
  (7); then a verify round by the same reviewers on the fixed code (R1: 4 FIXED, 1 PARTIAL, plus one CRITICAL pre-existing hole; R2: 8
  FIXED, 1 PARTIAL, plus 4 new; R3: 7 FIXED, plus 4 new) and a second fix round. Every finding and its fix is in the tables above.

## Deviations not yet approved by the owner (each listed in the closing report)
1. **Upload tokens (B4b, plan §4.6):** a report holds up to 30 token hashes, one minted at start and at most one per minute on status
   for a caller without one, instead of the plan's single `upload_token_sha256` (ADR-0023 item 3, status proposed). Reason: the agent,
   a second agent and the web panel hold the script at once; one rotating token breaks whoever did not rotate it.
2. **Background-job slots (B4b):** the owner 2, a friend 1, a slot lapses after 15 minutes; `retry_after_s` for REPORT_JOB_RUNNING is
   a fixed 30 s (a guess, not measured).
3. **B1:** report parse cap 2 MiB (the real Amazon search page with links is 449 KB; `supplier_parse` keeps 200 KB); `fetch_plan.build`
   takes an `ebay_api` flag; Jina reads add `curl -g -m 90`; extra fields (`tool_class`, `notes`, `lead_time_basis`, `unit_price_low`,
   `shipping_quote_usd` / `_qty`); Reddit relevance is judged on the thread title by the term's head words.
4. **B2:** only the best-matching CJ product gets details and freight (the cap of 4 CJ calls per candidate); the relevance filter also
   applies to eBay; eBay asks for new, fixed-price items that ship to the ship-to country; a CJ fair-use refusal is waited out once
   (≤ 60 s, ≤ 120 s per collect), an eBay one is typed at once; freight `cost_usd` is CJ's total postage; identical calls in one
   collect go out once; `FAIR_USE_LIMITED` names both CJ and eBay fair-use refusals; 300 eBay searches per friend per UTC day (owner
   exempt).
5. **B3:** CJ's day ranges are read as calendar days and judged on the worst week against business-day rules (`supplier_days_read_as:
   business` gives the strict reading); `handling_business_days` defaults to 1; off-topic records are left out and listed; a price range
   is costed at its high end; the inventory model for Alibaba (inbound by the listing's rule, time to first stock, cash before first
   stock, last mile per channel from CJ US→US quotes within a 25 % weight tolerance or the owner's own last-mile setting; a stated
   non-US destination drops that quote's cost and days).
6. **B4a:** best channel = the highest margin before ads among PASS or WARN channels (printed on the page). With handling counted, Shopify
   at WARN can beat TikTok US at PASS (the recorded reference: Shopify $1.37 WARN vs TikTok US $1.00 PASS). A `report.py decision`
   subcommand; governed-run margins stay UNKNOWN (no freight quotes in a governed run).
7. **B4b:** an empty scope answers 404; `POLYMATH_PUBLIC_URL` (default `https://rag.kingsleylab.xyz`) is the remote upload base; `ship_to`
   accepts only US; no retry after a round closes; `script_withheld` on `required` and `expired`; the product turn's receipt is labelled
   `product/report/start`.
8. **B5:** playbook step 3 offers the report too; a malformed report id is refused (422 `REPORT_ID_INVALID`) before any route; the
   script is re-run at most once, and only for an incomplete round; verdicts are written after a first compile; Server B's `--http` mode
   always gives the local upload URL.
9. **B6:** the report calls live in `reportApi` (not `api`) until the routes are deployed (the live-contract test checks `api` against
   the running backend); `/product` added to the dev proxy; a Details button on each Reports row; on `required` the panel shows a summary,
   not a script; after sign-in the app returns to `next` only for an exact report path.
10. **Coordinator:** the DNS-rebinding fix covers every route (a pre-existing CRITICAL hole outside the plan; review R1) and needed the
    test-client Host change below; `hypotheses._terms` (PRODUCT-SEARCH-E2E-V1 code) derives a title's default term from its head words.

## Existing tests changed
- On `production`, Host only, for the DNS-rebinding fix (a security fix, not an owner decision — the owner confirms):
  `tests/contracts/test_web_boundary.py` `_client(proxied=False)` (`test_direct_loopback_callers_are_unchanged`,
  `test_me_reports_the_owner_for_a_direct_caller`) and `tests/contracts/test_web_settings.py` :92, :158 move from Host `testserver` to
  `127.0.0.1`; `tests/conftest.py` gives a TestClient built without a base_url or Host the Host `127.0.0.1` (no assertion changes).
- On `production`, by the owner-approved plan (§4.8 a Reports screen): `frontend-v2/src/__tests__/ui-pieces.test.tsx` nav list gains
  "Reports".
- Added only: `tests/contracts/test_web_boundary.py` (+8 tests), `tests/determinism/test_mcp_principals_gate.py` (+1),
  `adapters/ecommerce/tests/run_all.py` (+36 engine checks).
- New on the PRODUCT-SEARCH-E2E-V1 commits of this branch (not on `production`), updated where a fix changed what they pin:
  `test_product_search_route.py` (loopback Host), `test_corpus_access_parity.py` (the fake Server A's friend tool list),
  `test_mcp_agent_playbook.py` (report texts).

## Incidents (live system, during the build)
- A slice's first-round run of `tests/contracts/test_corpus_access_parity.py` outside the sealed harness connected its 4 database tests
  to the live Postgres. They work on session TEMP copies (`ON COMMIT DROP`), assert the copy shadows the real table, and read `runs`:
  nothing persisted.
- The repo's suites probe the running fleet by design: six determinism files call `http://127.0.0.1:7200/chat` and `/chat/stream`
  whenever it answers, the web suite's free tier calls `/compare` and `/retrieve`, and one integration test's worker calls `/retrieve`.
  Today's runs wrote 84 live chat receipts (72 `chat_stream`, 12 `chat`; 16:18–19:00Z; every question a test probe, e.g. "What does the
  book say about the Zorblax-9 shutter protocol?"), 7 retrievals from the web suite and 1 from the integration test (its adapter rows
  went to the sealed database; no live adapter run was created, checked). The chat turns spent model calls on the live providers. The
  final web run pointed `POLYMATH_BASE_URL` at a closed port (the live tier skipped).
- graft wrote `graft/.cache/telemetry-repo-id.json` into the worktree despite `--dir`; removed; never committed.
- The fleet was not restarted and the live checkout's code was not edited during the build.

## Live run 1 (after the merge of `07a80e4f`, migrations 0067 + 0068 and the bounce, 2026-11-02 ~20:07Z) and its fixes
The deploy: `git merge --ff-only` (production `1403f3ac` → `07a80e4f`), 0067 (`UPDATE 7`: the seven libraries production and
query-enabled), 0068 (two tables), web build, `bounce_fleet.sh` READY after ~55 s (26 healthy workers, 13 types, one bundle).
`/product/reports` answered; a rebound Host got 403 on `/health`, loopback 200. Two owner reports through the routes the MCP tools
proxy:
- `rpt_30887faa…` ("Find me products I could dropship to pet owners in the US", commerce-v1, no products): the product turn (receipt
  `q_765918915c7f…`, deepseek-v4-flash) gave 0 hypotheses (`parse: fallback`), so the candidates became the request's own words "pet
  products" and "pet accessories". The same turn rerun a minute later gave 5 hypotheses: the model's block parses on some runs only.
- `rpt_00c434852e89…` (three named products: self-cleaning slicker brush, pet water fountain, automatic pet feeder): round 1, 18
  packets in 43 s, all uploaded; round 2, 12 packets in 1 min 49 s; host data CJ OK for all three (eBay `EBAY_NOT_CONFIGURED`);
  compile in ~1 s, a 602 KB page with 106 http(s) links and no script. The brush: reference price $13.29 (Amazon median), TikTok US
  $1.66 (12.5 %) PASS on US stock, Shopify $2.05 WARN, eBay $0.92, Amazon FBM −$0.52, cash before first stock $130.00. The fountain and
  the feeder: every margin UNKNOWN ("fewer than 3 matched listings, Amazon n = 1").

| Live finding | Cause | Fix |
|---|---|---|
| request words used as products | an empty product turn fell back to the request's term finds silently | the turn runs once more; still empty → `candidates.source` request_terms, a note, and `next` / agent texts say to pass `products` |
| two Amazon search pages EMPTY (143 KB each, 40 product links) | Jina returned its plain-text layout; the parser read only the markdown layout | the plain layout is parsed (43 listings from the recorded page, new fixture `jina_amazon_search_plain.out`) |
| fountain / feeder comparables n = 1 | "pet" required in titles that say "Cat Water Fountain" | an AUDIENCE group in the shared matcher: pet = pet / cat / kitten / dog / puppy (41 of 43 listings now relevant) |
| five Alibaba pages titled "Captcha Interception" stored OK | the check-page detector missed Alibaba's captcha title | HUMAN_CHECK, nothing admitted |

After these: the 27 affected suites in the sealed harness **865 passed**; engine 648 / 648; code wiki 2,412 / 2,412 on 378 pages.

## Live run 2 (after `94f3d58b`, ~20:24Z) and its fixes
- Friend gate through Server A with a temporary friend key (`prn_report_gate`, created for the gate, revoked at 20:33:36Z, key file
  deleted): handshake, 30 tools incl. the four report tools; `rpt_00810757…` round 1 6/6 and round 2 6/6 uploaded with the token
  reused; compile 207 KB; the brush priced exactly as the owner's run; the friend's list held only its report; the owner's report
  answered the friend 404 REPORT_NOT_FOUND; the owner's list showed all three reports.
- Owner report `rpt_164ed807…` (pet water fountain, automatic pet feeder): round 1 12/12 in 19 s, round 2 11/11 in 93 s; Amazon 10 OK
  (the plain layout now parsed), Alibaba 5 OK + 2 BLOCKED; reference prices $45.99 and $48.99 (were UNKNOWN). But the fountain's TikTok
  US line read $32.43 (70.5 %): CJ product 1651788214971146240 was costed at its $2.94 / 120 g variant (a filter set) while its
  fountain variants weigh 770–1,016 g, and two never-read CJ products showed their search "from" prices as unit costs.

| Live finding | Fix |
|---|---|
| the cheapest CJ variant was a part | `host_data.choose_variant`: variant names kept; variants named as parts or accessories dropped; when the heaviest variant weighs ≥ 2.5× the lightest, variants under 40 % of the heaviest dropped; then the cheapest; `variant_rule` and `variants_dropped` recorded; nothing left → CJ_NO_COSTED_VARIANT. The fountain is now costed at $11.94 / 1,016 g (a 1,984 g bundle sets the cut-off, so the 770 g units go too: the rule errs toward a higher cost, never a part) |
| search "from" prices shown as unit costs | the page says "from $1.74 (CJ search price: the lowest variant, not checked)" and such offers stay out of every margin line |

After these: 15 affected suites in the sealed harness **455 passed**; engine 648 / 648.

## Fresh agents (N13), one plain-English request, no tool names
"I want to start dropshipping to pet owners in the US. Use my Polymath to pick a few products worth selling and build me the
decision report I can open in a browser: product links, what people on Reddit say, profit margins, supplier MOQ and delivery times
for TikTok Shop versus my own Shopify store, and how eBay and Amazon prices compare. Send me the link when it is done."
- Hermes on DeepSeek v4.1 flash (bailian), started 20:37Z, done in 22 min, unaided: read the four tools' descriptions, ran
  `agent-reach doctor`, started a report from the library (`rpt_268e9060…`), checked the script's sha256, ran round 1 (30 packets, 68 s)
  and round 2 (29 packets, 4.5 min), compiled; judged the library's ideas ("Crate-Free Travel Anxiety Kit", …) too vague, started a
  second report with five concrete products (`rpt_b36a9936…`), compiled it, and answered with a plain summary (hair-remover roller the
  clean winner, eBay UNKNOWN because no eBay key). Friction: it guessed raw HTTP routes (two 404s) and met an ambiguous Hermes skill
  name; it also copied the page into its own public hub (`~/.hermes/public-hub/`, a Hermes behaviour outside Polymath).
- Claude Code (`claude -p`): did not start — "OAuth session expired and could not be refreshed" (the CLI's login; owner action).
- Codex (`codex exec`): did not start on its configured `gpt-6.1-sol` ("not supported when using Codex with a ChatGPT account");
  `gpt-6-luna` is the model this account can run (probed), rerun below.

## Proof
- **Sealed CI reproduction** (a throwaway `postgres:16-alpine` with all 68 migrations applied in order, a clean environment, the CI
  workflow's suites `tests/contracts` + `tests/determinism`), final tree before the C11 change: **4,871 tests: 4,834 passed, 20 skipped,
  17 failed — the identical 17 that fail on untouched `production` 1403f3ac** (list kept with the PRODUCT-SEARCH-E2E-V1 proof). After
  C11, every report suite again in the same harness: **541 passed** (routes and store on the in-memory store and on Postgres, render,
  unit economics, web boundary, web settings, playbook, parsers, host data, fetch plan, eBay, hypotheses, product search route, MCP
  gate, corpus parity).
- New tests: parsers 28, fetch plan 14, host data 17, eBay 14, unit economics 26, render 35, routes 45 and store 23 (both run on
  memory and Postgres), web panel 32; engine checks +36 (`adapters/ecommerce/tests/run_all.py`: **648 / 648**). Each review finding
  has a regression test built from the reviewer's reproduction; the reviewers' own reproduction files now fail (the bugs are gone),
  and the host-data and web-panel fixers also undid each fix in memory and saw its new tests fail.
- Web UI (`frontend-v2`): **245 passed, 7 skipped** with the live tier (B6's last run); 240 passed, 12 skipped with the live tier
  pointed at a closed port (final tree); `npm run build` passes (the > 500 kB chunk warning predates this change).
- A report compiled end to end from recorded real fixtures (CJ answers, Exa / Jina outputs) through the real parsers, engine and
  renderer (review R2's `e2e.py`, rerun on the fixed code; sell price $12.59 = the Amazon median of 43 matched listings):

| Line (Alibaba page A, inventory) | Arithmetic | Margin before ads | Delivery |
|---|---|---|---|
| TikTok US, USPS+VIP $7.78 | 12.59 − 9.08 − 0.76 − 1.75 | $1.00 (7.9 %) | PASS (5 + 1 ≤ 6 business days) |
| TikTok cross-border, US stock | same line | $1.00 | PASS (US-warehouse rule) |
| Shopify, UniUni+ $7.22 | 12.59 − 8.52 − 1.06 − 1.64 | $1.37 (10.9 %) | WARN (> 7 days) |
| eBay | 12.59 − 8.52 − 2.11 − 1.64 | $0.32 | PASS |
| Amazon FBM, USPS+VIP | 12.59 − 9.08 − 2.88 − 1.75 | −$1.12 | PASS |
| TikTok US at the 8 % what-if | 12.59 − 9.08 − 1.01 − 1.75 | $0.75 | — |

  Page A needs $130.00 cash before first stock (goods $88.00 + inbound $42.00) and 55 days to first stock; the B_retry page
  $7,737.00 ($2,200.00 + $5,537.00).
- Code wiki: `pages.py refresh` (GLM on the owner's coding plan) regenerated 40 unit pages and 4 flows, adding pages for every new
  module (`product_report.py`, `report_store.py`, `fetch_plan.py`, `host_data.py`, `ebay_api.py`, `unit_economics.py`, the web panel)
  and for PRODUCT-SEARCH-E2E-V1's (`api/product.py`, `intent.py`, `service.py`, `hypotheses.py`, `corpus_seed.py`); `verify.py
  --strict-anchors`: **2,413 / 2,413** assertions on 377 pages, 0 missing or stale anchors; 380 code-wiki files declared.
- Guards on the final tree: `repo_guard.py`, `wiki_worm.py --check`, `agent_preflight.py` (results in the commit's closing check).
- Security lint (ruff `S` on the 67 changed non-test Python files, both branches' changes): 87 findings vs 72 on the same files at
  `production`. New in this change, all false positives: header-name and placeholder constants read as passwords
  (`product_report.py` S105 / S106 ×4, `mcp_retrieval.py` S105), the renderer's fixed engine subprocess (`dossier.py` S603: fixed
  interpreter and arguments, minimal environment, timeout), five SQL strings built only from constant column lists and SET clauses with
  bound values (`report_store.py` S608), and the engine checks' own subprocess (`run_all.py` S603). The PRODUCT-SEARCH-E2E-V1 ones were
  triaged in its work-log.
- Live (read-only, before the merge): the fleet was quiet (no running work; 12 pending tickets wait behind a failed intake from
  2026-09-07; one adapter run awaiting its agent since 2026-11-01); 0067 and 0068 are not applied; the live stack runs in Docker
  Desktop (`DOCKER_CONTEXT=desktop-linux`), not the default OrbStack context.
- NOT yet proven here (the merge, migrations 0067 + 0068, the bounce, one live report through the connector as the owner and one as a
  friend key, and fresh agents in Claude Code, Codex and Hermes): recorded in the closing records after the deploy.

## Coverage — plan items
| Plan item | Evidence | Verdict |
|---|---|---|
| §3.1 start answers at once: id, status, candidates, host status, round-1 plan, upload capability | `product_report.py:741`; routes tests | MATCH; capability DEVIATION 1 |
| §3.2 host data in the background (CJ → relevance → product → freight CN/US; eBay or EBAY_NOT_CONFIGURED) | `host_data.py:687`; host-data and eBay tests | MATCH (DEVIATION 4) |
| §3.3 one script per round, raw pages never through the model; round 2 from status | `fetch_plan.py:294`; status route | MATCH (DEVIATION 3) |
| §3.4 deterministic parsing, matching to candidates, receipts | `agent_reach.py:1471`; upload route `:871` | MATCH |
| §3.5 compile → engine → HTML → stored privately → link | `product_report.py:1030`, `dossier.py:276`, `report_store.py` | MATCH |
| §3.6 no terminal: CJ + eBay still run; sections say "needs a local agent"; the script is shown | C11 (`product_report.py` `build_bundle`, `report.py`); web panel script | MATCH (C11 built after the coverage check found it missing) |
| §4.1 `parse_report_source` and its record shapes; BLOCKED / HUMAN_CHECK admit nothing | `agent_reach.py:1471` | MATCH (DEVIATION 3) |
| §4.2 `fetch_plan.build`, pacing, keys, uploads, exit 0 | `fetch_plan.py:294` | MATCH (DEVIATION 3) |
| §4.3 `collect`: ≤ 3 relevant CJ products, cheapest variant, freight; eBay Browse API | `host_data.py:687`, `ebay_api.py` | MATCH (DEVIATION 4: details for the best match only) |
| §4.4 `compute`: offers, market, demand, channels, 8 % what-if, receipts, UNKNOWN never guessed | `unit_economics.py:1532` | MATCH (DEVIATION 5; Reddit returns dated comments per the owner's 2026-11-02 instruction) |
| §4.5 `build_model_from_bundle`, DECISION layout, `render_decision`, http(s) anchors only | `report.py:971`, `dossier.py:276` | MATCH (DEVIATION 6) |
| §4.6 tables, routes, privacy, upload URLs | `0068_product_reports.sql`, `report_store.py`, `product_report.py` | DEVIATION 1 (token list), otherwise MATCH |
| §4.7 four MCP tools on both servers, TOOL_POLICY rows, report loop, subagent recipe | `mcp_server.py`, `polymath_mcp.py`, `mcp_principals.py`, `mcp_retrieval.py` | MATCH (DEVIATION 8) |
| §4.8 Build button, Reports list, open a report, script with copy button | `ProductReport.tsx`, `Reports.tsx` | MATCH (DEVIATION 9) |
| §5 gate 1: unit + contract tests per slice on recorded real fixtures | the test files above | MATCH |
| §5 gate 2: full sealed suite, no failure outside the 17 | sealed run above | MATCH |
| §5 gate 3: a sample report compiled end to end from recorded fixtures, published for the owner | e2e above; publication in the closing report | MATCH once published |
| §5 gate 4: one live report as the owner and one as a friend key | after the deploy | NOT YET (closing records) |
| §5 gate 5: register row IMPLEMENTED until the live gate | register 11.576 | MATCH |

## Coverage — requirements
| # | Evidence | Verdict |
|---|---|---|
| N1 | MCP tools on both servers with the loop in plain words; the script does every web read through the user's local Agent Reach | MATCH in tests; fresh agents after the deploy |
| N2 | candidate, offer, comparable and thread links as http(s) anchors (`report.py`) | MATCH |
| N3 | dated Reddit comments, ≤ 5 per thread, summary of counts; excluded threads listed | MATCH |
| N4 | per channel: fees, returns 19.3 %, margin before ads, break-even ad cost; rows add up (test re-adds every row) | MATCH |
| N5 | MOQ, tiers (high end), lead time at the MOQ row, cash before first stock, inbound rule, CJ variants and freight | MATCH |
| N6 | delivery verdict per channel with handling time; TikTok US and cross-border side by side; Shopify loose (WARN only) | MATCH |
| N7 | Amazon (Exa / Jina) and eBay (Browse API, else Exa) comparables, medians and demand signals | MATCH (eBay API needs the owner's keys) |
| N8 | researched per harness and model; the recipe in `REPORT_SUBAGENTS` and `CONNECTORS.md` §5 | MATCH as research; speed-up not benchmarked |
| N9 | branch, worktree, slices, reviews, guards, this work-log, one commit, fast-forward merge | MATCH (merge in the closing records) |
| N10 | three reviews + a verify round, every confirmed finding fixed, sealed suite at the baseline | MATCH in the worktree; merge pending |
| N11 | graft and graphify scans and the failure-pattern checklist before the reviews | MATCH |
| N12 | one live run analysed | NOT YET (after the deploy) |
| N13 | fresh Claude Code, Codex and Hermes sessions given one plain-English request | NOT YET (after the deploy) |
| D1 | `product_reports.owner_principal_id`; "not yours" and "no such report" are the same 404 | MATCH |
| D2 | `tiktok_us` and `tiktok_cross_border` columns side by side | MATCH |
| D3 | `returns_rate` 0.193 and `break_even_ad_cost_usd` | MATCH |

## Contract impact (pre-commit, `scripts/contract_impact.py --staged`)
- MCP_SURFACE — UPDATED (four report tools on both servers, the upload-token cache, TOOL_POLICY rows, corpus ids stripped before the gate
  checks them, report texts and the connect prompt's step 8).
- PRODUCT_REPORT — UPDATED (new: `contracts/product/v1/product_report.schema.json`, six routes, store, migration 0068).
- PRODUCT_SEARCH — UPDATED (`/product/search` refuses a rebound Host; a title's default search term is its head words).
- Transitive impact: none. Every test the check names ran in the sealed run or the C11 rerun.

## Rejected claims
- "The report is live": not until the merge, migrations 0067 + 0068 and the bounce; proven in the worktree and the sealed harness only.
- "Reddit relevance is solved": no. The head-word title rule keeps 5–7 of 8 recorded threads per term and misses titles that name the
  product in other words ("Brush recs for my doodle?"); the page lists every excluded thread so a reader can see them.
- "A US→US CJ quote proves US stock": no. CJ's stock-by-country came back empty; the page says so on every dropship offer.
- "Subagents make the report faster": not measured. The fetch work is paced by the sources' limits; the recipe is documented, not
  benchmarked.
- "The sealed suite never touches the live fleet": false. Six determinism files and the web suite's free tier probe the running
  orchestrator by design (see Incidents).

## Open contract gaps
- The live gate (plan §5 gate 4) and N12 / N13: after the deploy, in the closing records.
- The deviations above await the owner's approval; ADR-0023 is `proposed` until then.
- eBay comparables need the owner's free developer keys (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` in `.env`); without them eBay comes
  from the user's Exa reads (mostly non-US).
- Fair use, the eBay daily budget, the job slots and the token cache live in process memory (one orchestrator process today).
- Reddit titles that do not name the product's head words are missed (documented in `_thread_relevance`).
- The live probes in the repo's own suites spend model calls whenever the fleet is up; making the sealed harness truly offline is not
  done here.
