---
change_id: PRODUCT-SEARCH-E2E-V1
owner: "@king"
date: 2026-11-01
status: complete
status_note: "One patch (owner: 'i want one massive patch and fix any thing else'): product requests are recognised by any agent, the web link and claude.ai, answered with product hypotheses built from any library plus CJ Dropshipping finds; CJ = official API host-side for every user, with the user's LOCAL Agent Reach as the fallback and the only Alibaba path; the governed research run needs no niche and hands agents exact commands; libraries and friend access work the owner's way; 56 audited defects dispositioned."
architecture_impact: "New: shared/polymath_shared/product_search/ (intent, hypotheses, routing, service), orchestrator api/product.py (POST /product/search), acquisition/agent_reach.py (user-side fallback commands + parser, POST /supplier/parse), adapter corpus_seed.py + domain.py, the Agent Reach channel table (adapters/ecommerce/docs/24_agent_reach_channels.json), json_logging.py, migration 0067. Changed: the chat runtime (product mode), MCP tools and texts on both servers, supplier/CJ access for principals, library scope and friend grants, the governed run (seed optional, agent_reach + supplier_draft beside steps, submit-time law checks, lease/transaction split), interactive LLM admission, durable fleet logs, frontend-v2 product cards. ADR-0019 amended."
last_reviewed: 2026-11-01
---

# PRODUCT-SEARCH-E2E-V1: product search that works for any agent, any library and every user

## Contract
The owner, 2026-11-01 (verbatim, in order):
- "polymath is unaware when being used with an agent on finding products and it flags things as false and it just doesnt
  execute a trail agent os product search. it should prompt people with cj dropshipping finds"
- "its dumb from a user account a product search asks the users for a product but essentially it shouldnt really expect a niche
  it uses a corpus to find products, cj dropshipping is api and agent reach cli , and alibaba is strictly agent reach. the agent
  no matter the model tends to be unaware of what the tools do and how to use its also, its bad all around. it should never use a
  users claude native web search due to bot detections and it should work."
- "so im ensuring users of the connector and link works seamlessly as me"
- "it must work like a fallback, it requires agent reach which is a github requirement when being used ... the corpus it uses it
  should be able to use any corpus, idk why we have corpus false error its just a lot of dumb bugs. map all findings out that will
  make the use of this difficult for people especially emphasis on product search and finds. it needs fall backs and efficient
  workings a lot of dumb bugs."
- "i say prompt users to install it on their end and user their agent reach setup if api fails"
- "the trail agent os and or product search tools the agents must know how to use it, how it works, e2e. they dont and they become
  dumb about its. as well as corpus to use. it returns things like this corpus doesnt recomend products rather than using copus to
  hypothesize"
- "i want one massive patch and fix any thing else"
- Decisions (asked 2026-11-01): users without a terminal — "this will only work locally on their devices" (Agent Reach runs only on
  the user's own device; the web link and claude.ai get CJ API results only); who answers the research run's reasoning steps —
  "Always the agent"; a product question's default — Polymath's own answer with corpus hypotheses and CJ finds, ending with an
  offer of the full run (explained in plain words after "i dont know what you are asking here"; not contested).

| # | Requirement |
|---|---|
| R1 | A product request from any agent, the web link or claude.ai is recognised and answered as product search, never as a library question that abstains |
| R2 | No niche needed: products are found from the corpus; a seed stays optional (quick answer and governed run) |
| R3 | CJ = official API host-side + the user's local Agent Reach CLI when the API fails; Alibaba = the user's Agent Reach only |
| R4 | People are shown CJ Dropshipping finds |
| R5 | Works with any agent and any model: the tools say what they do and how, end to end |
| R6 | Never the user's built-in web search / fetch / browser; exact Agent Reach commands instead |
| R7 | It works end to end, with proof |
| R8 | Any corpus works, for the owner and for friends |
| R9 | The "corpus false" error and the library-scope bugs are gone |
| R10 | Agents learn the product search and Trail Agent OS flow end to end from the tools |
| R11 | Agents never have to guess the library |
| R12 | Product requests are answered by hypothesising from the corpus, never "this corpus doesn't recommend products" |
| R13 | Connector and web-link users get the owner's experience |
| R14 | Every other defect found on the way is fixed or dispositioned ("fix any thing else") |

The audit (six read-only agents + live probes, 2026-11-01) produced 56 defects, published as the artifact "Polymath Product Search
Inspection" (https://claude.ai/artifact/RrRnhxEiv85XzupF3kzqfi): 10 critical, 24 major, 22 minor; IDs PS-, TR-, CO-, CF-, RS-.

## Measured (root causes, 2026-11-01, before any change)
- "Find me products I could dropship for pet owners in the US" on commerce-v1 via `polymath_answer`: compiled `CREATE_FROM_KNOWLEDGE`,
  30 business-book passages, 39 claims `unsupported` + 8 `withheld_insufficient_coverage` → "I don't have enough grounded evidence"
  (receipt `q_fe63bd4e…`, 96 s). Cause: no product intent anywhere; MCP `polymath_answer` without `model` used the quote-only
  `deterministic-template-v3` (chat.py:41) while claiming "exactly as the app's chat writes it"; its description told agents to relay
  `insufficient_evidence` and stop; nothing pointed to the supplier tools or the research run.
- Every agent-facing passage (14) sent agents to their OWN web search / browser (adapter_next "YOUR OWN tools — web search, browser,
  APIs", the guide "Use any tool you have", the Settings connect prompt, the adapter manifest, HarnessActionV1).
- CJ answered 1600014 "Your API access has been disabled" on every call (account-level; the owner unfroze it at ~19:40Z — a live
  `supplier_search` returned PARTIAL 3 of 100 at 19:41:12Z and a fresh sign-in with the configured key succeeded); the code mapped it to a
  plain HTTP 200 `UNAVAILABLE` and retried it on every call. Alibaba went through the host's SearXNG (engines blocked); its snippet
  parser misread prices / suppliers / tiered MOQs; CJ's human-check page passed the wall detector as markdown.
- Supplier tools owner-only behind five locks; friend connect prompt told claude.ai users to send a header; friend "every library"
  grants were snapshots; every library `probe`, so "all libraries" resolved to nothing (owner 500 IndexError, friend misleading 403);
  `list_corpora` showed `query_enabled:false` unexplained (the "corpus false" error).
- Governed run: `seed` required (absent → category/language silently became the query); corpus signals unreachable by steps; 38 runs
  ever, no ecommerce product ever scored (3/3 completed runs refused every candidate HARD_GATE_UNMET); law refusals surfaced only after a
  redo (1024 s once); retrieval 233 s inside a 120 s lease and one transaction; 27 % of retrieval repeated; A-09 (an agent REVISE erased
  TrailSignal's `weakened`).
- Compiler lane `compiler_ollama_gemma` failed 44/44 today (429, none since 2026-10-17) and every failure cost a 30 s blocking breaker wait
  on chat turns; 26 fleet logs were unlinked while open by macOS's /tmp cleaner.
- The full audit (56 defects) is the artifact "Polymath Product Search Inspection".

## Changes (by slice; seven parallel slices + integration)
- **S1 acquisition** (`acquisition/{supplier,cj_api,listing_apis,searxng,service,opencli,challenge,agent_reach}.py`, `api/acquisition.py`,
  `mcp_principals.py`, `web_boundary.py`): CJ open to every user (owner and principals; fair use 1 in flight + 30/min per principal,
  `POLYMATH_SUPPLIER_RATE_PER_MINUTE`); 14 typed reason codes (1600014 → `CJ_API_DISABLED`); every CJ search/product failure returns a
  `fallback` = exact local Agent Reach commands (objects `{step, run, what, for_each?, then}`) + install/verify + `submit` to the new
  `supplier_parse`; freight / warehouses return `fallback: null` + `reason_code`; Alibaba = `AGENT_REACH_REQUIRED` (SearXNG reader, its
  pacing and the Alibaba browser reader deleted); line-by-line parser for Exa / Jina output (`POST /supplier/parse`, ≤ 200 KB, refuses
  check pages); `parse_snippet` retired; wall detection by route / Final URL / title; CJ circuit breaker (600 s disabled/auth, 60 s rate);
  `CORPUS_OPTIONAL` policy kind; friend scopes = one list incl. deep research; wildcard grant (never another friend's `fr-*`); an
  `adapter_start` naming no library passes to the runtime's default; `research_acquire` stays owner-only.
- **S2 agent surface** (`mcp_server.py`, `mcp_server/polymath_mcp.py`, `mcp_retrieval.py`, `adapter/harness_guide.py`, `api/web_settings.py`,
  `CONNECTORS.md`, `api/capabilities.py`): new tools `product_search` (library optional) and `supplier_parse` on both servers; one ordered
  6-step playbook; `polymath_answer` sends the app's default synthesizer (the `/synthesizers` default, cached 300 s; `ask` keeps /chat's
  deterministic default for TRAIL); every own-tools passage rewritten (local Agent Reach only, never built-in web search; platforms
  counted; users without a terminal get CJ API results only); friend keys get the `/k/<key>/mcp` connector link; "every library" stored
  as `["*"]`; `upload_text` forwards the principal; `list_corpora` passes the per-caller list through and explains each flag.
- **S3 product route** (`product_search/{intent,hypotheses,routing,service}.py`, `api/product.py`, `ui.py`, `chat.py`, `query_receipts.py`,
  `main.py`): deterministic PRODUCT-INTENT-V1 on the raw message; product mode steers retrieval toward frictions / workarounds / jobs /
  audiences (no seed → generic discovery aspects), appends the PRODUCT HYPOTHESIS contract to the LLM synthesis, parses a fenced block,
  looks each hypothesis up on CJ (principal-aware) and hands Alibaba to local Agent Reach; verdicts `product_hypotheses` /
  `product_hypotheses_thin` / `product_terms_only` (never a bare abstention); evidence-only turns carry `agent_steps`; several
  libraries → routed to the best one through the document profile collection (the skeleton's router job), receipted; `POST
  /product/search` (agent-supplied hypotheses → lookups only); adapter-step clients never trigger product mode; the empty-scope IndexError
  fixed; /chat/evidence receipts keep evidence ids.
- **S4 libraries and access** (`query_scope.py`, `web_scope.py`, `web_accounts.py`, `ui.py` corpora routes, `api/health.py`, `json_logging.py`,
  `main.py`, `intake_worker.py`, `scripts/web_accounts.py`, `scripts/hosted_mcp_acceptance.py`, migration 0067): `/corpora` leads with
  `query_ready`, adds `in_all_libraries` / `private` / `notes`; "all libraries" = every query-ready production library the caller may use,
  typed 404 `QUERY_SCOPE_EMPTY` with `next_step`; user-created libraries are production + query-enabled; migration 0067 sets the owner's
  seven real libraries (explicit ids, idempotent); wildcard grants resolved per request; friends' private library created with the
  account; `/ready` checks Postgres; orchestrator JSON logging; acceptance expectations at friend parity; friends may start a run with no
  library named.
- **S5 governed run** (`config/adapters/*.json`, `contracts/adapter/v1/harness_action.schema.json`, `shared/polymath_shared/adapter/**`,
  `adapters/ecommerce/**`, `adapter_step_worker.py`, `api/adapter.py`): adapter 0.8.0; `seed` optional (corpus seed derived at start from
  profile topics / tension atoms / research topics as a routing signal, `seed_origin:"corpus"` + lineage); no silent substitution;
  `corpus_ids` default to the caller's searchable libraries; early non-generative-seed hint; HARNESS_ACTION steps carry an `agent_reach`
  sibling key built from the channel DATA TABLE (no source-name branches; a new row needs no code); S_supply prefetches CJ and carries
  `supplier_draft`; law checks at submit (422 + `last_rejection`); `portfolio_unreachable` → C_hypotheses; A-09 / A-10 / A-12 fixed;
  network calls outside the transaction, lease renewed per call (HTTP 180 s, lease ≥ timeout + 60 s); per-run evidence cache by corpus
  generation; two retrievals at a time; cancel closes the open step; idle runs expire (24 h, configurable); check-page source URLs refused
  in `validate_receipt`; `product:false` on the run's own evidence calls; web runs list filtered per principal.
- **S6 web UI** (`frontend-v2`): `ProductResearch` cards (hypotheses with citation chips, CJ cards, Agent Reach panel with copy buttons,
  Alibaba row, limitations); "Start full research" (T6-lite: `POST /adapter/start`, run id, Research link, copyable agent prompt); friend
  keys show the claude.ai connector link in Settings.
- **S7 reliability** (`llm_extraction/{client,limiter}.py`, `ui.py` compiler/facet calls, `api/deep_research.py`, `process_supervisor.py`,
  boot / bounce / supervise scripts, `chat_m_replay.py`): interactive chat and deep-research LLM calls skip a lane the limiter refuses (no
  30 s wait; receipted; all refused → typed degraded); extraction / enrichment keep blocking admission; fleet logs in
  `~/PolymathRuntime/logs/fleet` (`POLYMATH_FLEET_LOG_DIR`), `/private/tmp/polymath_fleet` linked to it.
- **Integration (coordinator)**: `/retrieve/plan` writes a query receipt per HTTP call (RS-10, `corpus_plan.py`); `/product/search` wakes a
  parked embedder (`main.py`); capabilities list the product and supplier routes; product steering moved before the evidence-route override
  (the existing call-site pin); `supplier_draft` / `last_rejection` / `parse` documented in `adapter_next` / `adapter_submit` on both servers;
  the legacy manifest no longer promises per-step commands; web friends and script friends share one scope list; ADR-0019 amended (the
  harness's web channel is the user's local Agent Reach; decision 6 stands); runbooks / CLAUDE.md / CONTINUATION point at the durable log
  dir (the quarantine reset deletes the real state file, not the link); 35 new files declared; code wiki refreshed (the orphaned
  `searxng.py` unit page removed — the module now lives in the acquisition small-modules page).

## Deviations not yet approved by the owner (each listed in the closing report)
1. S4: the `corpora.purpose` / `query_enabled` column defaults stay `probe` / `false`; every user creation path sets production explicitly
   (test and evaluation inserts stay out of "all libraries"). The owner's "all libraries" excludes friends' private `fr-*` libraries.
2. S1: the owner is not rate-limited (principals only); `supplier_product` also returns a fallback; adding a friend by script now needs
   `--writable-corpus` (the friend profile includes upload).
3. S3: empty scope answers 404 `QUERY_SCOPE_EMPTY` (S4's code), not the planned 422; on a non-facet plan the product aspects can replace the
   lowest-weight compiler subqueries (q0 never); adapter-step clients never trigger product mode.
4. S5: manifest wording "Corpus-informed …; a niche is optional"; law refusals now answer at submit (422 + `last_rejection`) — an agent
   protocol change; F4 question cap = max_rows ÷ min_rows_per_need (6 on F_retrieve / F_graph, so all ≤ 6 hypotheses keep a share).
5. S7: `deep_research.py` covered too (same lanes); lane skipping applies to every limiter refusal on interactive paths, not only an open
   breaker; nothing rotates the durable fleet logs.
6. S6: null input fields dropped before `/adapter/start`; "Open in Research" opens the run's page; the started run is saved on the turn.
7. Coordinator: product steering runs before the evidence-route override, so an evidence-only product turn records the steering rule rather
   than the evidence-route rule on its compiler receipt.

## Existing tests changed (each follows an explicit owner decision of 2026-11-01)
- "users of the connector and link works seamlessly as me" (supplier tools for principals, friend scopes, wildcard grants, no-library run
  start): `test_supplier_tools.py` :142, :157, :179, :270, :303, :320 and two description/connect-prompt assertions; `test_mcp_principals_gate.py`
  :36, :253 and the §9 list; `test_mcp_principals_registry.py` :32, :39, :51, :67; `test_web_settings.py` (two assertions);
  `test_web_invite_signup.py` :165; `test_web_boundary.py`; `test_hosted_mcp_acceptance.py`.
- "alibaba is strictly agent reach": `test_supplier_apis.py` :260 and 13 SearXNG tests deleted with the removed behaviour (replacement :309);
  `test_supplier_tools.py` :227; `test_research_acquisition.py` :203, :415; `test_adapter_ecommerce_supply_join_api_records.py` :34, :96-97
  (a real parsed Exa result replaces the SearXNG one).
- "it shouldnt really expect a niche" / the run protocol: adapter e2e and dossier drivers handle submit-time rejections, version pin 0.8.0,
  the evidence request body is six fields, the transient-error test patches `prepare`.
- `tests/conftest.py`: private-library creation off for the test session.

## Incidents (live system, during the build)
- ~18:34Z: a S4 database test committed a test library `zz-parity-upload-7b529006` (1 document, 2 runs) to the LIVE Postgres; the control
  plane minted 16 tickets and made 3 Groq `doc_profile` calls (~850 tokens each) before the rows were deleted ~3 min later. The test was
  removed; the coordinator verified independently: 0 rows naming it across 36 corpus-keyed tables, 0 orphan tickets, 0 Neo4j nodes, 0 rows
  in the 18:25–18:50Z window pointing at deleted runs, and no corpora / runs / adapter runs created since 17:45Z.
- ~18:15Z: a S5 store test ran once against the live Postgres; its fixture created and deleted its own probe runs; verified: no adapter or
  pipeline runs remain from it.
- No live process was restarted; the live checkout's code was never edited.

## Proof
- **Sealed CI reproduction** (a throwaway `postgres:16-alpine` on a spare port with all 67 migrations applied in order, a clean environment:
  no `.env`, no live store; the CI workflow's own steps): **contracts + determinism 4,517 tests: 4,480 passed, 20 skipped, 17 failed —
  the identical 17 that fail on untouched `production` 1403f3ac in the same harness** (4,220 tests: 4,183 passed, 20 skipped, 17 failed;
  chat-funnel / generation-bound / extraction-pool / wildcard-mapped / graph-lifecycle tests that need live config or services). 0 new
  failures, 0 baseline failures changed; the patch adds 297 tests, all passing. A first patched run found 3 regressions, all fixed before
  the final run: two existing contract tests pinned the evidence request body (the coordinator had added `product: false`; removed — the
  route already skips product mode by the run's attributable user agent, which the same test pins), and a new log test assumed pytest's
  temp dir is outside /tmp (true on macOS, false on Linux CI).
- Engine suite `adapters/ecommerce/tests/run_all.py`: **612 / 612**. Web UI (`frontend-v2`): **213 passed, 7 skipped**; `npm run build` passes
  (the >500 kB chunk warning predates the patch: 558 → 574 kB).
- Code wiki: `pages.py refresh` (GLM on the owner's coding plan; 8 flows + the changed unit pages) and `verify.py --strict-anchors`
  **2,266 / 2,266** assertions on 351 pages, 0 missing / stale anchors.
- Guards on the final tree: `repo_guard.py`, `wiki_worm.py --check`, `agent_preflight.py` (results in the commit's closing check).
- Live, read-only (the running fleet is pre-patch): the original abstention reproduced (`q_fe63bd4e…`); CJ answered 1600014 until the owner
  unfroze the account, then `supplier_search` "candle warmer" → PARTIAL 3 of 100 with stock and store counts (19:41:12Z), and a fresh-process
  sign-in with the configured key succeeded (no cached token).
- NOT yet proven (needs the owner's deploy): the patched routes through the public connector as owner and as a friend, migration 0067 on the
  live database, a seed-less governed run on a non-commerce library reaching X_compile, and a TrailSignal score (TR-09).
- `tests/integration/test_cross_domain_routing.py` (named by the impact check) fails to collect (`No module named
  'orchestrator.orchestrator'`) on untouched `production` too: pre-existing, not run.

## Coverage — requirements
| # | Evidence | Verdict |
|---|---|---|
| R1 | `product_search/intent.py` + `ui.py:4038` (detect) · verdicts `service.py:39` · `test_product_intent` (79), `test_product_runtime` (17) | MATCH (live after deploy) |
| R2 | quick answer: generic discovery aspects (`hypotheses.py` steer_plan) · run: corpus seed (`adapter/service.py:105-200`, `corpus_seed.py`) | MATCH |
| R3 | CJ API + fallback (`supplier.py:206-258`, `agent_reach.py:104`) · Alibaba `AGENT_REACH_REQUIRED` (`supplier.py:222-230`) | MATCH |
| R4 | `product_research` hypotheses with CJ items · Markdown finds in the answer · `ProductResearch.tsx` | MATCH (live CJ proven on the pre-patch fleet) |
| R5 | one playbook on both servers (`mcp_retrieval.py:459`) · `product_search` single entry · `test_mcp_agent_playbook` (25) | MATCH |
| R6 | 83 agent-facing texts guarded by regex · `agent_reach` beside steps · `fallback.commands` | MATCH |
| R7 | sealed CI (above), engine 612/612, UI 213, code wiki 2,266/2,266 | PARTIAL: proven in the worktree; LIVE after the owner's deploy |
| R8 | `query_scope.py:41,96,165` · `web_scope.py:94-132` · `routing.py` · adapter `corpus_ids` default | MATCH (0067 at deploy) |
| R9 | `/corpora` shape (`ui.py:143,155`) · IndexError fix (`ui.py:4188`) · typed `QUERY_SCOPE_EMPTY` | MATCH |
| R10 | playbook + guide (Agent Reach local, platforms counted, `supplier_draft`, `last_rejection`) + `CONNECTORS.md` | MATCH |
| R11 | `CORPUS_OPTIONAL` (`mcp_principals.py:82,177`) · library routing (`routing.py`) · run default | MATCH |
| R12 | PRODUCT HYPOTHESIS contract (`ui.py:3203`) · parser (`hypotheses.py`) · never bare `insufficient_evidence` | MATCH |
| R13 | CJ for principals · `FRIEND_SCOPES` one list · connector link for friend keys · wildcard · Settings link | MATCH (CF-06 onboarding: owner) |
| R14 | defect map below | 50 built · 1 resolved by the owner · 1 proof after deploy · 4 need the owner |

## Coverage — the 56 audited defects
- **Built (MATCH):** PS-01 (intent + product mode), PS-02 (hypothesis contract), PS-03 (default synthesizer `mcp_server.py:475,492`),
  PS-04, PS-05, PS-07 (`cj_api.py:86,224` + breaker `:55-56,178-205`), PS-08, PS-09, PS-10 (`agent_reach.py:449,460`), PS-11 (`challenge.py:99-178`,
  `transitions.py:375`), PS-12 (`api/acquisition.py:186`), PS-13 (`supplier.py:88`, `mcp_principals.py:71,91-99`, `web_boundary.py:50-51`),
  PS-14 (`supplier.py:111-150`), PS-15, PS-16 (T6-lite), PS-17; TR-01, TR-02, TR-03, TR-04 (`24_agent_reach_channels.json`,
  `executors.py:198-320`), TR-05 (`service.py:780,1081`), TR-06 (`service.py:487`), TR-07 (`hypotheses.py:31,324`), TR-08 (guide text),
  TR-10, TR-11, TR-12 (`api/adapter.py:93`, `mcp_principals.py:184-195`, `web_scope.py:168`), TR-13 (`binding.py:1107`), TR-14 (`binding.py:621`),
  TR-15 (`service.py:684,696`), TR-16 (`lived_world.py:412`, `service.py:1121-1180`), TR-17 (`api/adapter.py:71`); CO-01 … CO-06; CF-01 … CF-05;
  RS-01 (code: `client.py:371,592`, `ui.py:1777,2658,2672`, `deep_research.py:234-270`), RS-02 (`process_supervisor.py:165-286`), RS-03, RS-04,
  RS-05, RS-06, RS-10 (`corpus_plan.py`).
- **Resolved by the owner:** PS-06 (CJ unfrozen ~19:40Z).
- **Proof after deploy:** TR-09 (a TrailSignal score needs a governed run with CJ data and evidence from several platforms).
- **Need the owner:** CF-06 (friend onboarding: invite flow or keys), RS-01's lane (drop `compiler_ollama_gemma` or set
  `POLYMATH_CHAT_COMPILER_PREFERRED_LANE=compiler_alibaba_deepseek`; 0 successes since 2026-10-17), RS-07 (`chmod 600 .env`), RS-08 (remove the now
  unused SearXNG service, settings and env lines), RS-09 (commerce-v1 holds business books; product / customer sources would give stronger
  hypotheses).

## Contract impact (pre-commit, `scripts/contract_impact.py --staged`)
- ADAPTER_RUNTIME — UPDATED (0.8.0; `seed` optional; `agent_reach` / `supplier_draft` sibling keys; submit-time law checks; lease split).
- EVIDENCE_BOUNDARY_API — UPDATED (`product_research` + `agent_steps` on product turns; non-product turns byte-identical, tested; the run's own
  calls skip product mode by user agent; receipts keep evidence ids).
- MCP_SURFACE — UPDATED (`product_search`, `supplier_parse`, `polymath_answer` default model, texts, `list_corpora`, `CORPUS_OPTIONAL`).
- PROFILE_SCOUT_WIRING — TESTED_UNCHANGED (the profile index is read only as a library router by the product route; scout wiring untouched).
- RESEARCH_ACQUISITION — UPDATED (Alibaba handoff, CJ fallback / breaker, wall detection; `research_acquire` stays owner-only).
- ACCEPTANCE — UPDATED (friend-parity expectations in `hosted_mcp_acceptance.py`; not run against public hosts).
- QUERY_PLANNER — UPDATED in product mode only (aspects inside the compiler's cap); TESTED_UNCHANGED otherwise.
- RETRIEVAL_RECEIPT — UPDATED (`product_search` meta key; `/chat/evidence` evidence ids; `/retrieve/plan` receipts).
- CANDIDATE_ENGINE, EVIDENCE_PACKET, PROFILE_YIELD_RECEIPT, RESOLUTION_STATE, SUBQUERY_PROVENANCE — TESTED_UNCHANGED (sealed run).

## Rejected claims
- "Product search works now": not live until the owner's deploy; proven in the worktree only.
- "A product was scored": no — no ecommerce product has ever been scored; TR-09 stays open until a governed run proves it.
- "The CJ fallback through Agent Reach returns CJ listings": often not — measured, CJ shows a human check to Exa and Jina (2 of 3 results);
  the fallback says so, and Alibaba product pages are the reliable Agent Reach source.
- "Users of the web link or claude.ai get the fallback": no — by the owner's decision Agent Reach runs only on the user's own device.
- "The integration test in the impact list passed": it fails to collect on untouched `production` too; not run.

## Open contract gaps
- LIVE proof (R7, TR-09) after the owner's Run button; migration 0067 applies in the same window.
- The 7 deviations above await the owner's approval.
- CF-06, RS-01 lane, RS-07, RS-08, RS-09: owner decisions.
- The CJ circuit breaker and the per-principal fair use are per process (the orchestrator is one process today).
- Nothing rotates the durable fleet logs.
- The 17 sealed-harness failures predate this patch (environment-dependent; reported, not fixed here).
