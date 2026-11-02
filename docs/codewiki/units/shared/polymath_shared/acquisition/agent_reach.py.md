# unit: shared/polymath_shared/acquisition/agent_reach.py
anchor: shared/polymath_shared/acquisition/agent_reach.py:1-1762

## purpose
Agent Reach handoff module for product search: when Polymath cannot read a supplier site itself, it builds the exact commands for the USER's own Agent Reach install (Exa via mcporter, Jina Reader via curl) and parses the text the user sends back — shared/polymath_shared/acquisition/agent_reach.py:1-13 [DERIVED]. The host never calls Exa, Jina or any page reader; an agent's built-in web search/fetch is never the route — shared/polymath_shared/acquisition/agent_reach.py:7-10 [DERIVED]. Second entry point `parse_report_source` reads one upload of the report's fetch script for reddit/amazon/ebay/alibaba with the same framing, bounds and wall check — shared/polymath_shared/acquisition/agent_reach.py:26-37 [DERIVED]. Pure: no I/O — shared/polymath_shared/acquisition/agent_reach.py:38 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| BadOutput | class | `(code: str, message: str, status: int = 422)` | shared/polymath_shared/acquisition/agent_reach.py:81-86 | — |
| site_of | def | `(value: Any) -> str \| None` | shared/polymath_shared/acquisition/agent_reach.py:90-94 | — |
| exa_command | def | `(site: str, query: str) -> str` | shared/polymath_shared/acquisition/agent_reach.py:108-112 | — |
| jina_command | def | `(url: str = "<PRODUCT_URL>") -> str` | shared/polymath_shared/acquisition/agent_reach.py:115-117 | — |
| fallback | def | `(site: str, query: str \| None, reason_code: str, why: str) -> dict[str, Any]` | shared/polymath_shared/acquisition/agent_reach.py:120-137 | — |
| cj_product_url | def | `(url: Any) -> tuple[str, str] \| None` | shared/polymath_shared/acquisition/agent_reach.py:157-164 | — |
| product_page | def | `(site: str, url: str) -> tuple[str, str] \| None` | shared/polymath_shared/acquisition/agent_reach.py:167-168 | — |
| clean_text | def | `(raw_text, max_bytes) -> bounded, normalised text; default cap MAX_RAW_BYTES` | shared/polymath_shared/acquisition/agent_reach.py:466-475 | — |
| parse | def | `(site, raw_text) -> {tool_class, records, refused, documents, notes}` | shared/polymath_shared/acquisition/agent_reach.py:478-525 | — |
| head_terms | def | `(term) -> the term's HEAD TERMS (own words, lower-case)` | shared/polymath_shared/acquisition/agent_reach.py:707-718 | — |
| missing_terms | def | `(title, head) -> head terms the title does not hold (empty = relevant)` | shared/polymath_shared/acquisition/agent_reach.py:751-763 | — |
| reddit_thread_url | def | `(url) -> (canonical thread URL, sub) \| None` | shared/polymath_shared/acquisition/agent_reach.py:887-896 | — |
| amazon_product_url | def | `(url) -> (https://www.amazon.com/dp/<ASIN>, <ASIN>) \| None` | shared/polymath_shared/acquisition/agent_reach.py:996-1002 | — |
| ebay_item_url | def | `(url) -> (https://www.<domain>/itm/<id>, <id>, <domain>) \| None` | shared/polymath_shared/acquisition/agent_reach.py:1283-1292 | — |
| alibaba_page_url | def | `(url) -> (URL sans query/fragment, pid, "detail"\|"introduction")` | shared/polymath_shared/acquisition/agent_reach.py:1383-1393 | — |
| parse_report_source | def | `(source, raw_text, kind, candidate_terms) -> {status, source, kind, records, next_targets, refused} (+ tool_class, notes)` | shared/polymath_shared/acquisition/agent_reach.py:1658-1761 | — |

Importers (FACTS, module-level): orchestrator/orchestrator/api/product_report.py; shared/polymath_shared/acquisition/service.py; shared/polymath_shared/acquisition/supplier.py; shared/polymath_shared/product_search/fetch_plan.py; shared/polymath_shared/product_search/host_data.py; shared/polymath_shared/product_search/hypotheses.py; shared/polymath_shared/product_search/service.py.

## contracts

**fallback(site, query, reason_code, why)**
- in: `site` ∈ SITES `(ALIBABA, CJ)` — shared/polymath_shared/acquisition/agent_reach.py:60,120; `query` may be None → placeholder `"<your search words>"` — shared/polymath_shared/acquisition/agent_reach.py:122.
- out: keys `kind, reason_code, why, site, query, run_on, never, install{repo,verify,how}, commands, submit, walls` — shared/polymath_shared/acquisition/agent_reach.py:123-136.
- post: exactly 2 commands: step 1 Exa search, step 2 Jina read per product URL — shared/polymath_shared/acquisition/agent_reach.py:129-133.
- post: submit block names `SUBMIT_TOOL = "supplier_parse"`, `SUBMIT_ROUTE = "POST /supplier/parse"`, `max_bytes = MAX_RAW_BYTES`, `one_output_per_call: True` — shared/polymath_shared/acquisition/agent_reach.py:67,134-135.

**exa_command / jina_command**
- out: `"mcporter call exa.web_search_exa query=<quoted> numResults=10 objective=<quoted>"` — shared/polymath_shared/acquisition/agent_reach.py:111-112.
- pre/post: query value starts with `site:` so it never starts with "@" (mcporter reads a FILE for `key=@path`) — shared/polymath_shared/acquisition/agent_reach.py:110.
- out: `"curl -s " + shlex.quote("https://r.jina.ai/<url>")` — shared/polymath_shared/acquisition/agent_reach.py:117.

**site_of(value)**
- out: host name or source name (`"cj"`, `"alibaba"`) normalised (lower-case, scheme/`www.` stripped, source names mapped through inverse of `SOURCE_OF = {ALIBABA: "alibaba", CJ: "cj"}`) and returned only if in SITES — shared/polymath_shared/acquisition/agent_reach.py:59-62,92-94.

**parse(site, raw_text)**
- in: ONE Agent Reach command's whole output, unedited; bounded by MAX_RAW_BYTES — shared/polymath_shared/acquisition/agent_reach.py:13,63.
- pre: one Jina page per call; a second page header raises `BadOutput("ONE_PAGE_PER_CALL", ...)` — shared/polymath_shared/acquisition/agent_reach.py:219-220.
- pre: Exa and Jina output mixed in one call raises `BadOutput("MIXED_OUTPUT", ...)`; no recognised framing raises `BadOutput("UNRECOGNISED_OUTPUT", ...)` — shared/polymath_shared/acquisition/agent_reach.py:262-263,268-269,271-272.
- post: records carry title, product URL + id, price or price tiers with quantities, MOQ, supplier, years, sold, reviews where shown — shared/polymath_shared/acquisition/agent_reach.py:13-15.
- post: a verification/check page is refused (HUMAN_CHECK); nothing from it becomes a record — shared/polymath_shared/acquisition/agent_reach.py:19-21.
- post: records come only from the reader's own framing (Exa result after `---` with full header; ONE Jina page per call), so a page cannot smuggle in a record — shared/polymath_shared/acquisition/agent_reach.py:23-24.

**parse_report_source(source, raw_text, kind, candidate_terms)**
- in: `source` ∈ `REPORT_SOURCES = ["reddit", "amazon", "ebay", "alibaba"]`; `kind` ∈ `REPORT_KINDS = ["search", "page"]` — shared/polymath_shared/acquisition/agent_reach.py:530-531.
- out: `{status, source, kind, records, next_targets, refused}` plus `tool_class, notes`; `status` ∈ `REPORT_STATUSES = ["OK", "EMPTY", "BLOCKED", "HUMAN_CHECK", "UNRECOGNISED"]` — shared/polymath_shared/acquisition/agent_reach.py:26,532.
- post: Amazon search pages and Alibaba Exa results name the round-2 product pages in `next_targets` — shared/polymath_shared/acquisition/agent_reach.py:27-28.
- post: a number the page does not state stays null; nothing is guessed — shared/polymath_shared/acquisition/agent_reach.py:37.

**URL normalizers**
- cj_product_url: path must fullmatch `/product/(.+)-p-([0-9A-Za-z][0-9A-Za-z-]{5,63})\.html`; id checked by `cj_api.valid_id` — shared/polymath_shared/acquisition/agent_reach.py:141,157-164.
- product_page: `searxng.listing_url(url)` for ALIBABA, else `cj_product_url(url)` — shared/polymath_shared/acquisition/agent_reach.py:167-168.
- amazon_product_url: US store hosts only, `AMAZON_HOSTS = ["amazon.com", "smile.amazon.com", "www.amazon.com"]` — shared/polymath_shared/acquisition/agent_reach.py:538,996.

## effect surface
- Postgres tables: none read, none written (FACTS `tables_read`/`tables_written` empty).
- Network: none — this host never calls Exa, Jina or any page reader — shared/polymath_shared/acquisition/agent_reach.py:7-8.
- Subprocesses: none executed; command STRINGS built for the user's machine (`mcporter call exa.web_search_exa ...`, `curl -s https://r.jina.ai/...`) — shared/polymath_shared/acquisition/agent_reach.py:111,117.
- Files / Qdrant / env flags: none; imports are stdlib plus `cj_api`, `searxng`, `challenge` — shared/polymath_shared/acquisition/agent_reach.py:41-52.

## invariants
- INVARIANT: MAX_RAW_BYTES = 200_000 — shared/polymath_shared/acquisition/agent_reach.py:63 [DERIVED]
  fails-if: inputs larger than 200 kB are accepted, breaking the bound promised to callers.
- INVARIANT: MAX_RECORDS = 50 — shared/polymath_shared/acquisition/agent_reach.py:64 [DERIVED]
  fails-if: record cap changes silently for every importer.
- INVARIANT: EXA_RESULTS = 10 == `numResults=10` in exa_command — shared/polymath_shared/acquisition/agent_reach.py:65,111 [DERIVED]
  fails-if: built command and module constant disagree on result count.
- INVARIANT: BadOutput default status = 422 — shared/polymath_shared/acquisition/agent_reach.py:84 [DERIVED]
  fails-if: the supplier_parse route's HTTP answer changes for every BadOutput code.
- INVARIANT: exa query always starts with `site:` and so never with `@` — shared/polymath_shared/acquisition/agent_reach.py:110 [DERIVED]
  fails-if: mcporter interprets the value as a file reference (`key=@path`).
- INVARIANT: header match window _TITLE_SPAN = 8 lines — shared/polymath_shared/acquisition/agent_reach.py:180 [DERIVED]
  fails-if: `Title:`/`URL:` framing of wrapped Exa titles stops matching.
- INVARIANT: one Jina page per call (second page header rejected) — shared/polymath_shared/acquisition/agent_reach.py:219-220 [DERIVED]
  fails-if: a multi-page paste could smuggle extra records.
- INVARIANT: _BLOCK_HTTP = [401, 403, 405, 407, 429, 451, 503] — shared/polymath_shared/acquisition/agent_reach.py:830 [DERIVED]
  fails-if: a refused read is parsed as content instead of BLOCKED.
- INVARIANT: READER_MIN_BYTES = 512 and _BLOCK_PAGE_CHARS = 3000 — shared/polymath_shared/acquisition/agent_reach.py:544,843 [DERIVED]
  fails-if: tiny/error pages are treated as real reader output.
- INVARIANT: JOIN_MAX = 3 adjacent words joined for head-term matching — shared/polymath_shared/acquisition/agent_reach.py:696 [DERIVED]
  fails-if: relevance matching ("selfcleaning" joins) changes scope.
- INVARIANT: SITES = (searxng.SITE, cj_api.SITE) and SOURCE_OF = {ALIBABA: "alibaba", CJ: "cj"} — shared/polymath_shared/acquisition/agent_reach.py:59-62 [DERIVED]
  fails-if: site acceptance drifts from the sibling modules' own SITE constants.

## determinism & idempotency
determinism: DETERMINISTIC (module docstring "Pure: no I/O." — shared/polymath_shared/acquisition/agent_reach.py:38; imports are stdlib regex/dataclass tools plus sibling pure modules — shared/polymath_shared/acquisition/agent_reach.py:41-52)
idempotency: SAFE (pure text-in/dict-out functions; no writes, calls or subprocesses anywhere in the module — shared/polymath_shared/acquisition/agent_reach.py:7-8,38)

## failure behaviour
- `BadOutput(ValueError)` carries `code, message, status` (default 422); raised codes: `ONE_PAGE_PER_CALL` (:220), `MIXED_OUTPUT` (:263, :269), `UNRECOGNISED_OUTPUT` (:271-272) — shared/polymath_shared/acquisition/agent_reach.py:81-86,220,263,269,271-272 [DERIVED].
- Walls are not exceptions but refusals: a challenge/verification page → HUMAN_CHECK, an access-denied/block page → BLOCKED; nothing from either becomes a record — shared/polymath_shared/acquisition/agent_reach.py:19-21,35-37 [DERIVED].
- `_status`: OK when anything was kept; else HUMAN_CHECK/BLOCKED when a wall stood in the way; else EMPTY — shared/polymath_shared/acquisition/agent_reach.py:1617-1622 [DERIVED].
- `_reader_error`: whole output being the reader's error JSON (a "code" of 400-599 with a "name") becomes its own error — shared/polymath_shared/acquisition/agent_reach.py:548-561 [DERIVED].
- `_blocked`: (BLOCKED or TARGET_ERROR, why) when the reader's output is the site refusing it (Jina still answers 200) — shared/polymath_shared/acquisition/agent_reach.py:862-873 [DERIVED].
- `_NOT_PARSED` documents per-source dead ends, e.g. a Jina read of an eBay page or reddit thread is not parsed (measured 2026-11-02) — shared/polymath_shared/acquisition/agent_reach.py:1625 [DERIVED].
- Per-source measured failure modes (fixtures in tests/fixtures/product_report/): Reddit Jina blocked 7 of 7; eBay Jina error page 5 of 5; Alibaba Akamai "Access Denied" on 2 of 4 — shared/polymath_shared/acquisition/agent_reach.py:29-34 [DERIVED].

## dumb-code flags
- Magic numbers: 8 (:180), 512 (:544), 3000 (:843), 3 (:696), 200_000 (:63), 50 (:64), 10 (:65).
- Near-duplicate literals: `UNTRUSTED` ("the supplier's own untrusted text…") vs `REPORT_UNTRUSTED` ("the page's own untrusted text…") differ by one word — shared/polymath_shared/acquisition/agent_reach.py:70,540.
- The `MIXED_OUTPUT` message string is duplicated at two raise sites — shared/polymath_shared/acquisition/agent_reach.py:263,269.
- Measurement dates hardcoded in docs/strings ("measured 2026-11-01" :16, "measured 2026-11-02" in _NOT_PARSED :1625, "live 2026-11-02" in the _amazon_plain_search docstring per FACTS :1228) — they will go stale.
- `EBAY_US = "ebay.com"` is a single-value constant used as a marker — shared/polymath_shared/acquisition/agent_reach.py:539.

## refactor notes
- Seven importers depend on this module (FACTS.importers, incl. the orchestrator's product_report API); renaming or re-signing any public symbol above breaks all of them — shared/polymath_shared/acquisition/agent_reach.py (FACTS.importers).
- `SUBMIT_TOOL`/`SUBMIT_ROUTE` ("supplier_parse", "POST /supplier/parse") are printed into user-facing handoff JSON; renaming the route orphans every in-flight handoff — shared/polymath_shared/acquisition/agent_reach.py:67,134.
- The framing regexes `_TITLE`, `_EXA_URL`, `_JINA_URL` (:172-174) enforce "records only from the reader's framing" (:23-24); loosening them lets a hostile page smuggle its own records.
- The `site:`-prefix rule in exa_command is a security property (never "@" for mcporter); do not reorder — shared/polymath_shared/acquisition/agent_reach.py:110.
- `SITES`/`SOURCE_OF`/`ALIBABA`/`CJ` are derived from `searxng.SITE` and `cj_api.SITE`; changing those modules silently changes accepted sites and `WALLS` keys — shared/polymath_shared/acquisition/agent_reach.py:59-78.
- Every text field is treated as untrusted supplier text; any new field must preserve quote-as-evidence semantics — shared/polymath_shared/acquisition/agent_reach.py:22,70.

## VERIFY
```verify
grep -Fq 'MAX_RAW_BYTES = 200_000' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'Pure: no I/O' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'status: int = 422' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'BadOutput("MIXED_OUTPUT"' shared/polymath_shared/acquisition/agent_reach.py
grep -Eq 'ONE_PAGE_PER_CALL|UNRECOGNISED_OUTPUT' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'https://r.jina.ai/' shared/polymath_shared/acquisition/agent_reach.py
test "$(grep -c -F 'shlex.quote' shared/polymath_shared/acquisition/agent_reach.py)" -ge 2
! grep -Fq 'import requests' shared/polymath_shared/acquisition/agent_reach.py
```
