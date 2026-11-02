# unit: shared/polymath_shared/acquisition/agent_reach.py
anchor: shared/polymath_shared/acquisition/agent_reach.py:1-1565

## purpose
Builds the Agent Reach handoff (an Exa-via-mcporter site search, then Jina Reader page reads) for the USER to run on their own machine, and parses the command output the user pastes back into listing records — for supplier search (Alibaba, CJ) and the product-decision report (reddit, amazon, ebay, alibaba). This host never calls Exa, Jina or any page reader itself. shared/polymath_shared/acquisition/agent_reach.py:1-38 [DERIVED]
Module is pure: "Pure: no I/O." shared/polymath_shared/acquisition/agent_reach.py:38 [DERIVED]

## public surface
Module-level importers (FACTS.importers): orchestrator/orchestrator/api/product_report.py, shared/polymath_shared/acquisition/service.py, shared/polymath_shared/acquisition/supplier.py, shared/polymath_shared/product_search/fetch_plan.py, shared/polymath_shared/product_search/host_data.py, shared/polymath_shared/product_search/hypotheses.py, shared/polymath_shared/product_search/service.py. Per-symbol "used by" is not in FACTS.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| BadOutput | class | (code: str, message: str, status: int = 422) -> ValueError | shared/polymath_shared/acquisition/agent_reach.py:80-85 | — |
| site_of | def | (value: Any) -> str \| None | shared/polymath_shared/acquisition/agent_reach.py:89-93 | — |
| exa_command | def | (site: str, query: str) -> str | shared/polymath_shared/acquisition/agent_reach.py:107-111 | — |
| jina_command | def | (url: str = "\<PRODUCT_URL\>") -> str | shared/polymath_shared/acquisition/agent_reach.py:114-116 | — |
| fallback | def | (site: str, query: str \| None, reason_code: str, why: str) -> dict | shared/polymath_shared/acquisition/agent_reach.py:119-136 | — |
| on_site | def | (url: str, site: str) -> bool | shared/polymath_shared/acquisition/agent_reach.py:151-153 | — |
| cj_product_url | def | (url: Any) -> (url, product id) \| None | shared/polymath_shared/acquisition/agent_reach.py:156-163 | — |
| product_page | def | (site: str, url: str) -> (url, id) \| None | shared/polymath_shared/acquisition/agent_reach.py:166-167 | — |
| clean_text | def | (raw_text, max_bytes) -> bounded, normalised text | shared/polymath_shared/acquisition/agent_reach.py:465-474 | — |
| parse | def | (site, raw_text) -> {tool_class, records, refused, documents, notes} | shared/polymath_shared/acquisition/agent_reach.py:477-524 | — |
| head_terms | def | (term) -> the term's head terms | shared/polymath_shared/acquisition/agent_reach.py:676-687 | — |
| missing_terms | def | (title, head) -> list, empty = relevant | shared/polymath_shared/acquisition/agent_reach.py:709-720 | — |
| reddit_thread_url | def | (url) -> (canonical thread URL, sub) \| None | shared/polymath_shared/acquisition/agent_reach.py:837-846 | — |
| amazon_product_url | def | (url) -> (https://www.amazon.com/dp/\<ASIN\>, ASIN) \| None | shared/polymath_shared/acquisition/agent_reach.py:946-952 | — |
| ebay_item_url | def | (url) -> (https://www.\<domain\>/itm/\<id\>, id, domain) \| None | shared/polymath_shared/acquisition/agent_reach.py:1096-1105 | — |
| alibaba_page_url | def | (url) -> (url w/o query/fragment, product id, "detail"\|"introduction") \| None | shared/polymath_shared/acquisition/agent_reach.py:1196-1206 | — |
| parse_report_source | def | (source, raw_text, kind, candidate_terms) -> {status, source, kind, records, next_targets, refused} (+ tool_class, notes) | shared/polymath_shared/acquisition/agent_reach.py:1471-1564 | — |
| KIND/REPO/VERIFY/RUN_ON/NEVER | const | "AGENT_REACH" / repo URL / doctor cmd / "your machine" / never-rule | shared/polymath_shared/acquisition/agent_reach.py:53-57 | — |
| SITES, SOURCE_OF | const | (ALIBABA, CJ); {ALIBABA: "alibaba", CJ: "cj"} | shared/polymath_shared/acquisition/agent_reach.py:58-61 | — |
| MAX_RAW_BYTES / MAX_RECORDS / EXA_RESULTS | const | 200_000 / 50 / 10 | shared/polymath_shared/acquisition/agent_reach.py:62-64 | — |
| REPORT_SOURCES / REPORT_KINDS / REPORT_STATUSES | const | ["reddit","amazon","ebay","alibaba"] / ["search","page"] / ["OK","EMPTY","BLOCKED","HUMAN_CHECK","UNRECOGNISED"] | shared/polymath_shared/acquisition/agent_reach.py:529-531 | — |
| AMAZON_HOSTS / EBAY_US | const | ["amazon.com","smile.amazon.com","www.amazon.com"] / "ebay.com" | shared/polymath_shared/acquisition/agent_reach.py:537-538 | — |

ALIBABA and CJ are not literals here: `ALIBABA, CJ = searxng.SITE, cj_api.SITE`. shared/polymath_shared/acquisition/agent_reach.py:58 [DERIVED]

## contracts

**fallback(site, query, reason_code, why) -> dict** — shared/polymath_shared/acquisition/agent_reach.py:119-136
- in: site key, optional query words, a reason code and explanation.
- out: keys `kind, reason_code, why, site, query, run_on, never, install{repo,verify,how}, commands[2], submit{tool,route,arguments,max_bytes,one_output_per_call}, walls`. shared/polymath_shared/acquisition/agent_reach.py:122-135
- post: step 1 = `exa_command`, step 2 = `jina_command()` per product URL of form `PRODUCT_URL_FORM[site]`; submit sets `"one_output_per_call": True` and `max_bytes = MAX_RAW_BYTES`. shared/polymath_shared/acquisition/agent_reach.py:127-134
- pre: no network/subprocess — commands are returned as strings only. shared/polymath_shared/acquisition/agent_reach.py:7-10

**exa_command(site, query) -> str** — shared/polymath_shared/acquisition/agent_reach.py:107-111
- out: `"mcporter call exa.web_search_exa query=<q> numResults=10 objective=<objective>"` with every value `shlex.quote`d.
- post: query value starts with `site:` — never "@" (mcporter reads a FILE for `key=@path`). shared/polymath_shared/acquisition/agent_reach.py:109

**jina_command(url="<PRODUCT_URL>") -> str** — shared/polymath_shared/acquisition/agent_reach.py:114-116
- out: `"curl -s " + shlex.quote("https://r.jina.ai/" + url)`.

**parse(site, raw_text) -> dict** — shared/polymath_shared/acquisition/agent_reach.py:477-524
- in: ONE command's whole output, unedited (an Exa result text, or one Jina Reader page). shared/polymath_shared/acquisition/agent_reach.py:13,133-134
- pre: input bounded by MAX_RAW_BYTES (200_000); framing must be `Title:` + `URL:` (Exa) or `Title:` + `URL Source:` (Jina), else `BadOutput("UNRECOGNISED_OUTPUT", ...)`. shared/polymath_shared/acquisition/agent_reach.py:62,270
- out: `{tool_class, records, refused, documents, notes}`; records carry title, product URL + id, price/tiers, MOQ, supplier, years, sold, reviews. shared/polymath_shared/acquisition/agent_reach.py:318 (FACTS doc), 13-15
- post: a challenge/verification page yields HUMAN_CHECK and nothing from it becomes a record; nothing is solved or worked around. shared/polymath_shared/acquisition/agent_reach.py:19-21

**parse_report_source(source, raw_text, kind, candidate_terms) -> dict** — shared/polymath_shared/acquisition/agent_reach.py:1471-1564
- in: `source` ∈ REPORT_SOURCES, `kind` ∈ REPORT_KINDS; ONE upload of the report's fetch script. shared/polymath_shared/acquisition/agent_reach.py:529-530, 855 (FACTS doc)
- out: `{status, source, kind, records, next_targets, refused}` plus `tool_class, notes`; Amazon search pages and Alibaba Exa results name round-2 product pages in `next_targets`. shared/polymath_shared/acquisition/agent_reach.py:855 (FACTS doc), 28
- post: status ∈ REPORT_STATUSES; a Jina refusal ("Warning: Target URL returned error 403", block-page title) → BLOCKED; a verification page → HUMAN_CHECK; a number the page does not state stays null. shared/polymath_shared/acquisition/agent_reach.py:531,35-37

**clean_text(raw_text, max_bytes)** — shared/polymath_shared/acquisition/agent_reach.py:465-474
- out: submitted text bounded to `max_bytes` (MAX_RAW_BYTES unless the caller names its own cap) and normalised. shared/polymath_shared/acquisition/agent_reach.py:306 (FACTS doc)

**URL canonicalisers (cj_product_url / reddit_thread_url / amazon_product_url / ebay_item_url / alibaba_page_url)** — shared/polymath_shared/acquisition/agent_reach.py:156,837,946,1096,1196
- in: any URL shape the site uses; out: canonical URL + ids, or None off-site/ill-formed. shared/polymath_shared/acquisition/agent_reach.py:156-163,837-846,946-952,1096-1105,1196-1206 (FACTS docs)

## effect surface
- Postgres: none — `tables_read: []`, `tables_written: []` (FACTS).
- Network / subprocess: none from this host; "this host NEVER calls Exa, Jina or any page reader". shared/polymath_shared/acquisition/agent_reach.py:7-10
- Files, Qdrant, env flags: none; imports are stdlib only (`re, shlex, unicodedata, dataclasses, datetime, itertools, typing, urllib.parse`) plus `polymath_shared.acquisition.{cj_api, searxng, challenge}`. shared/polymath_shared/acquisition/agent_reach.py:41-51

## invariants
INVARIANT: MAX_RAW_BYTES == 200_000 — shared/polymath_shared/acquisition/agent_reach.py:62 [DERIVED]
  fails-if: oversized pastes reach the line parser unbounded.
INVARIANT: MAX_RECORDS == 50 — shared/polymath_shared/acquisition/agent_reach.py:63 [DERIVED]
  fails-if: parse returns more records than the documented cap.
INVARIANT: EXA_RESULTS == 10 (literal `numResults={EXA_RESULTS}` in the built command) — shared/polymath_shared/acquisition/agent_reach.py:64,110 [DERIVED]
  fails-if: the mcporter command fetches a different result count than documented.
INVARIANT: every built Exa query starts with "site:" (never "@") — shared/polymath_shared/acquisition/agent_reach.py:109 [DERIVED]
  fails-if: a leading-@ value makes mcporter treat it as a file path.
INVARIANT: _TITLE_SPAN == 8 lines between a `Title:` line and its `URL:` line — shared/polymath_shared/acquisition/agent_reach.py:179,199 [DERIVED]
  fails-if: wrapped Exa titles stop pairing with their URL line.
INVARIANT: REPORT_SOURCES == ["reddit", "amazon", "ebay", "alibaba"] and REPORT_STATUSES == ["OK", "EMPTY", "BLOCKED", "HUMAN_CHECK", "UNRECOGNISED"] — shared/polymath_shared/acquisition/agent_reach.py:529-531 [DERIVED]
  fails-if: parse_report_source accepts a source/kind or emits a status with no reader/contract.
INVARIANT: _BLOCK_HTTP == [401, 403, 405, 407, 429, 451, 503] — shared/polymath_shared/acquisition/agent_reach.py:787 [DERIVED]
  fails-if: a refused read (e.g. 403) is mistaken for content.
INVARIANT: records come only from the reader's own framing (Exa header after `---`; one Jina page per call) — shared/polymath_shared/acquisition/agent_reach.py:23-24,218-220,224-253 [DERIVED]
  fails-if: a page could smuggle in a record by printing a header inside its text.

## determinism & idempotency
determinism: DETERMINISTIC — "Pure: no I/O." shared/polymath_shared/acquisition/agent_reach.py:38; no clock/random/uuid/network/db/env use visible in shared/polymath_shared/acquisition/agent_reach.py:41-51.
idempotency: SAFE — builds strings/dicts only, writes no state. shared/polymath_shared/acquisition/agent_reach.py:38,107-116,119-136

## failure behaviour
- `BadOutput(ValueError)` carries `.code`, `.message`, `.status`; default HTTP status 422. shared/polymath_shared/acquisition/agent_reach.py:80-85
- Codes raised: `ONE_PAGE_PER_CALL` (shared/polymath_shared/acquisition/agent_reach.py:220), `MIXED_OUTPUT` (:262, :266), `UNRECOGNISED_OUTPUT` (:270).
- Wall handling (nothing swallowed, nothing becomes a record): verification/challenge page → HUMAN_CHECK, never solved or skipped. shared/polymath_shared/acquisition/agent_reach.py:19-21,70-77
- Jina answers 200 even on refusal: a `Warning: Target URL returned error 403` line or block-page title → BLOCKED. shared/polymath_shared/acquisition/agent_reach.py:35-36
- `_blocked` returns `(BLOCKED or TARGET_ERROR, why)` when the reader's output is the site refusing it. shared/polymath_shared/acquisition/agent_reach.py:812 (FACTS doc)
- `_status`: OK when anything was kept; else HUMAN_CHECK / BLOCKED when a wall stood in the way; else EMPTY. shared/polymath_shared/acquisition/agent_reach.py:1430 (FACTS doc)
- eBay Jina reads are never parsed ("eBay answers page readers with an error page, measured 2026-11-02"). shared/polymath_shared/acquisition/agent_reach.py:1438

## dumb-code flags
- Near-duplicate untrusted-text literals: UNTRUSTED ("the supplier's own untrusted text") vs REPORT_UNTRUSTED ("the page's own untrusted text") differ by one word. shared/polymath_shared/acquisition/agent_reach.py:69,539
- The "never work around a check" rule is stated twice as prose: WALLS constants and the module doc. shared/polymath_shared/acquisition/agent_reach.py:19-21,70-77
- Magic numbers: default status 422 (:83); title span 8 (:179); robot-check page cap 3000 (:797); CJ id length `{5,63}` (:140); company name `{1,140}` (:335); card link `{1,150}` (:339); SKU `{3,40}` (:340); MOQ clip 60 (:386,389); JOIN_MAX 3 (:670).
- Site-specific prompt strings hardcoded in `_objective` (Alibaba vs CJ branches). shared/polymath_shared/acquisition/agent_reach.py:96-104

## refactor notes
- Blast radius: 7 importer modules (FACTS.importers) incl. orchestrator/orchestrator/api/product_report.py — renaming `fallback`, `parse`, `parse_report_source` or the URL canonicalisers breaks them all. shared/polymath_shared/acquisition/agent_reach.py:119,477,1471
- `fallback`'s dict shape and `SUBMIT_TOOL`/`SUBMIT_ROUTE` (`"supplier_parse"`, `"POST /supplier/parse"`) are the wire contract with the user's agent and the submit route. shared/polymath_shared/acquisition/agent_reach.py:66,122-135
- Framing regexes (`_TITLE`, `_EXA_URL`, `_JINA_URL`, `_FINAL_URL`, the `---` separator rule) implement the anti-smuggling rule; loosening them lets a page inject records. shared/polymath_shared/acquisition/agent_reach.py:23-24,171-179,224-253
- ALIBABA/CJ keys come from `searxng.SITE`/`cj_api.SITE`; SITES, SOURCE_OF, WALLS, PRODUCT_URL_FORM are all keyed on them — must stay in sync across modules. shared/polymath_shared/acquisition/agent_reach.py:58-77
- Field regexes (:320-345) encode page shapes measured 2026-11-01/02 against fixtures in tests/fixtures/product_report/ — changes need fixture re-runs. shared/polymath_shared/acquisition/agent_reach.py:29,320-345
- `_SHAPE`/`_NEXT_WHY`/`_NOT_PARSED` dicts drive report round-2 targets and per-source notes. shared/polymath_shared/acquisition/agent_reach.py:1414-1438

## VERIFY
```verify
grep -Fq 'MAX_RAW_BYTES = 200_000' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'SUBMIT_TOOL, SUBMIT_ROUTE = "supplier_parse", "POST /supplier/parse"' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'TOOL_EXA, TOOL_JINA = "agent_reach.exa", "agent_reach.jina"' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'Pure: no I/O.' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'raise BadOutput("MIXED_OUTPUT"' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq '"one_output_per_call": True' shared/polymath_shared/acquisition/agent_reach.py
test "$(grep -c -F 'shlex.quote' shared/polymath_shared/acquisition/agent_reach.py)" -ge 3
! grep -Fq 'import requests' shared/polymath_shared/acquisition/agent_reach.py
```
