# unit: shared/polymath_shared/acquisition/agent_reach.py
anchor: shared/polymath_shared/acquisition/agent_reach.py:1-1786

## purpose
Builds the Agent Reach handoff for supplier sites Polymath cannot read itself: the USER's own Agent Reach runs an Exa search (via mcporter) and Jina Reader page reads on the user's machine, and this module only builds those commands (`fallback`) and parses the text sent back (`parse`) into listing records. [DERIVED] shared/polymath_shared/acquisition/agent_reach.py:1-13
Second entry point `parse_report_source` (PRODUCT-DECISION-REPORT-V1, 2026-11-02) parses reddit/amazon/ebay/alibaba fetch-script uploads with the same framing, bounds and wall check. [DERIVED] shared/polymath_shared/acquisition/agent_reach.py:26-29
Pure text transformation: "Pure: no I/O." [DERIVED] shared/polymath_shared/acquisition/agent_reach.py:38
Serves the acquisition/product_search stack and the orchestrator report API (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| BadOutput | class | (code: str, message: str, status: int = 422) -> ValueError | shared/polymath_shared/acquisition/agent_reach.py:81-86 | — |
| site_of | def | (value: Any) -> str \| None | shared/polymath_shared/acquisition/agent_reach.py:90-94 | — |
| exa_command | def | (site: str, query: str) -> str | shared/polymath_shared/acquisition/agent_reach.py:108-112 | — |
| jina_command | def | (url: str = "\<PRODUCT_URL\>") -> str | shared/polymath_shared/acquisition/agent_reach.py:115-117 | — |
| fallback | def | (site: str, query: str \| None, reason_code: str, why: str) -> dict[str, Any] | shared/polymath_shared/acquisition/agent_reach.py:120-137 | — |
| on_site | def | (url: str, site: str) -> bool | shared/polymath_shared/acquisition/agent_reach.py:152-154 | — |
| cj_product_url | def | (url: Any) -> tuple[str, str] \| None | shared/polymath_shared/acquisition/agent_reach.py:157-164 | — |
| product_page | def | (site: str, url: str) -> tuple[str, str] \| None | shared/polymath_shared/acquisition/agent_reach.py:167-168 | — |
| clean_text | def | (raw_text, max_bytes) -> bounded text | shared/polymath_shared/acquisition/agent_reach.py:466-475 | — |
| parse | def | (site: str, raw_text) -> {tool_class, records, refused, documents, notes} | shared/polymath_shared/acquisition/agent_reach.py:478-525 | — |
| head_terms | def | (term) -> head terms of a search term | shared/polymath_shared/acquisition/agent_reach.py:727-738 | — |
| missing_terms | def | (title, head) -> head terms title does not hold (empty = relevant) | shared/polymath_shared/acquisition/agent_reach.py:771-783 | — |
| reddit_thread_url | def | (url) -> (canonical thread URL, sub) \| None | shared/polymath_shared/acquisition/agent_reach.py:907-916 | — |
| amazon_product_url | def | (url) -> (https://www.amazon.com/dp/\<ASIN\>, ASIN) \| None | shared/polymath_shared/acquisition/agent_reach.py:1016-1022 | — |
| ebay_item_url | def | (url) -> (itm URL, id, domain) \| None | shared/polymath_shared/acquisition/agent_reach.py:1303-1312 | — |
| alibaba_page_url | def | (url) -> (URL, product id, "detail" \| "introduction") \| None | shared/polymath_shared/acquisition/agent_reach.py:1403-1413 | — |
| parse_report_source | def | (source, raw_text, kind=, candidate_terms=) -> {status, source, kind, records, next_targets, refused} (+ tool_class, notes) | shared/polymath_shared/acquisition/agent_reach.py:1678-1785 | — |

Per-symbol callers are not recorded in FACTS; the module as a whole is imported by (FACTS.importers): orchestrator/orchestrator/api/product_report.py; shared/polymath_shared/acquisition/service.py; shared/polymath_shared/acquisition/supplier.py; shared/polymath_shared/product_search/fetch_plan.py; shared/polymath_shared/product_search/host_data.py; shared/polymath_shared/product_search/hypotheses.py; shared/polymath_shared/product_search/service.py.

## contracts

**exa_command(site, query) -> str** — shared/polymath_shared/acquisition/agent_reach.py:108-112
- in: `q = " ".join(f"site:{site} {query}".split())` — whitespace-collapsed, always starts with `site:` (shared/polymath_shared/acquisition/agent_reach.py:110).
- out: one line `mcporter call exa.web_search_exa query=<shlex.quote(q)> numResults={EXA_RESULTS} objective=<shlex.quote(_objective(...))>` (shared/polymath_shared/acquisition/agent_reach.py:111-112).
- post: every interpolated value `shlex.quote`d; a value never starts with "@" (mcporter reads a FILE for `key=@path`) [DERIVED] shared/polymath_shared/acquisition/agent_reach.py:11, :110.

**jina_command(url="<PRODUCT_URL>") -> str** — shared/polymath_shared/acquisition/agent_reach.py:115-117
- out: `curl -s ` + `shlex.quote(f"https://r.jina.ai/{url}")` (shared/polymath_shared/acquisition/agent_reach.py:117).

**fallback(site, query, reason_code, why) -> dict** — shared/polymath_shared/acquisition/agent_reach.py:120-137
- in: `query` may be None -> words `"<your search words>"` (shared/polymath_shared/acquisition/agent_reach.py:122).
- out keys: kind=KIND ("AGENT_REACH"), reason_code, why, site, query, run_on, never, install{repo, verify, how}, commands[step 1 = exa_command, step 2 = jina_command per product URL], submit{tool="supplier_parse", route="POST /supplier/parse", arguments{site, raw_text}, max_bytes=MAX_RAW_BYTES, one_output_per_call=True}, walls=WALLS[site] (shared/polymath_shared/acquisition/agent_reach.py:123-136).
- pre: site must be one of SITES; WALLS is keyed only by ALIBABA and CJ, so any other site raises KeyError [INFERRED — dict lookup at :136 over WALLS defined :71-78].

**clean_text(raw_text, max_bytes)** — shared/polymath_shared/acquisition/agent_reach.py:466-475
- post: output at most `max_bytes`; default cap is MAX_RAW_BYTES unless a caller names its own (FACTS doc :466; MAX_RAW_BYTES at :63).

**parse(site, raw_text)** — shared/polymath_shared/acquisition/agent_reach.py:478-525
- in: ONE command's whole output, unedited (shared/polymath_shared/acquisition/agent_reach.py:13, :134).
- out: {tool_class, records, refused, documents, notes}; records carry title, product page URL + product id, price as listed or price tiers with quantities, minimum order, supplier, its years, units sold and reviews (FACTS doc :478; shared/polymath_shared/acquisition/agent_reach.py:13-15).
- err: BadOutput codes ONE_PAGE_PER_CALL, MIXED_OUTPUT (x2), UNRECOGNISED_OUTPUT raised from `_split`/`_jina` (shared/polymath_shared/acquisition/agent_reach.py:210-272).
- post: a verification/challenge page is refused (HUMAN_CHECK); nothing from it becomes a record (shared/polymath_shared/acquisition/agent_reach.py:19-21).

**parse_report_source(source, raw_text, kind=, candidate_terms=)** — shared/polymath_shared/acquisition/agent_reach.py:1678-1785
- in: source in REPORT_SOURCES (FACTS :530), kind in REPORT_KINDS ["search", "page"] (FACTS :531).
- out: {status, source, kind, records, next_targets, refused} plus tool_class and notes (FACTS :957); status in REPORT_STATUSES ["OK", "EMPTY", "BLOCKED", "HUMAN_CHECK", "UNRECOGNISED"] (FACTS :532).
- post: Amazon search pages and Alibaba Exa results name round-2 product pages in `next_targets` (shared/polymath_shared/acquisition/agent_reach.py:28-29); a Jina read of an eBay page is not parsed at all (FACTS _NOT_PARSED :1645).

**URL normalizers** — cj_product_url (:157-164, regex `_CJ_PRODUCT` at :141, id validated by `cj_api.valid_id` at :163), product_page (:167-168, dispatches to `searxng.listing_url` or `cj_product_url`), amazon_product_url (:1016-1022), ebay_item_url (:1303-1312), alibaba_page_url (:1403-1413), reddit_thread_url (:907-916). Each returns a canonical tuple or None. [DERIVED]

**relevance** — head_terms (:727-738) takes the term's own lower-case words up to a use/audience/feature cut (_HEAD_CUT, _HEAD_STOP, _FEATURE_PREFIX, FACTS :709-719); missing_terms (:771-783) — empty result means relevant. [DERIVED]

**BadOutput** — "`code` is stable, `status` is the HTTP status the route answers with" (:82); attributes code, message, status; status defaults to 422 (:84-86). [DERIVED]

## effect surface
- Postgres: none — FACTS tables_read and tables_written are both empty.
- Network / subprocess / env: none at runtime — the host never calls Exa, Jina or any page reader (:7-9); module is "Pure: no I/O." (:38). Commands are built as strings only.
- Library dependencies used: `polymath_shared.acquisition.cj_api` (SITE :59, valid_id :163), `polymath_shared.acquisition.searxng` (SITE, listing_url :59, :168), `polymath_shared.acquisition.challenge` (looks_like_challenge, segments :52, used per :20).
- Protocol strings emitted for other units: SUBMIT_TOOL = "supplier_parse", SUBMIT_ROUTE = "POST /supplier/parse" (:67) — the route itself lives in an importer (FACTS.importers).

## invariants
- INVARIANT: MAX_RAW_BYTES = 200_000 — shared/polymath_shared/acquisition/agent_reach.py:63 [DERIVED]; fails-if: submissions over the cap are rejected/bounded by clean_text (:466-475).
- INVARIANT: MAX_RECORDS = 50 — shared/polymath_shared/acquisition/agent_reach.py:64 [DERIVED]; fails-if: results beyond 50 are dropped.
- INVARIANT: EXA_RESULTS = 10 (numResults) — shared/polymath_shared/acquisition/agent_reach.py:65, :111 [DERIVED]; fails-if: command output size and record count change.
- INVARIANT: BadOutput default status = 422 — shared/polymath_shared/acquisition/agent_reach.py:85 [DERIVED]; fails-if: route answers a parse error with the wrong HTTP status.
- INVARIANT: exa query value always starts with `site:` (never "@") — shared/polymath_shared/acquisition/agent_reach.py:110-111 [DERIVED]; fails-if: mcporter would treat the query as a file reference.
- INVARIANT: one output per call — a second Jina page header raises ONE_PAGE_PER_CALL (:210-222), an Exa+Jina mix raises MIXED_OUTPUT (:257-272) [DERIVED]; fails-if: two outputs parsed as one corrupts record framing.
- INVARIANT: _TITLE_SPAN = 8 lines between a `Title:` line and its URL marker — shared/polymath_shared/acquisition/agent_reach.py:180 [DERIVED]; fails-if: longer wrapped titles are not recognized as records.
- INVARIANT: records come only from the reader's own framing (Exa header after a `---`, one Jina page per call) — shared/polymath_shared/acquisition/agent_reach.py:23-24 [DERIVED]; fails-if: a page could smuggle a record by printing a header inside its text.
- INVARIANT: READER_MIN_BYTES = 512 (FACTS :544), _BLOCK_PAGE_CHARS = 3000 (FACTS :863), _BLOCK_HTTP = [401, 403, 405, 407, 429, 451, 503] (FACTS :850) [DERIVED]; fails-if: block pages below/above these bounds misclassify as content.
- INVARIANT: JOIN_MAX = 3 (FACTS :716); AUDIENCE maps "pet" -> ["pet", "cat", "kitten", "dog", "puppy"] (FACTS :724); AMAZON_HOSTS = ["amazon.com", "smile.amazon.com", "www.amazon.com"] (FACTS :538); EBAY_US = "ebay.com" (FACTS :539) [DERIVED]; fails-if: relevance joins or host matching drift from measured page formats.
- INVARIANT: SITES = (ALIBABA, CJ) where ALIBABA = searxng.SITE and CJ = cj_api.SITE — shared/polymath_shared/acquisition/agent_reach.py:59-60 [DERIVED]; fails-if: site dispatch (SOURCE_OF, WALLS, PRODUCT_URL_FORM, _TAIL) keys stop matching.

## determinism & idempotency
determinism: DETERMINISTIC — pure text-to-records transformation; no clock/random/uuid/network/db/env visible; "Pure: no I/O." shared/polymath_shared/acquisition/agent_reach.py:38 [DERIVED]
idempotency: SAFE — same raw_text parses to the same records; no state is written anywhere in the unit [INFERRED — follows from :38, no stores in FACTS]

## failure behaviour
- BadOutput(ValueError) with stable codes, each carrying an HTTP status (default 422): ONE_PAGE_PER_CALL (:210-222), MIXED_OUTPUT twice (:257-272), UNRECOGNISED_OUTPUT (:257-272). [DERIVED]
- Wall handling: a verification/challenge page (e.g. CJ's `/egg/cj/validation.html`, a check-page title, `challenge.looks_like_challenge`) is refused as HUMAN_CHECK; nothing from it becomes a record; nobody solves, skips or works around a check (shared/polymath_shared/acquisition/agent_reach.py:19-21, WALLS :71-78).
- Jina answers 200 even when the site refused it: a `Warning: Target URL returned error 403` line, a block page's title or its own words make the page BLOCKED (:34-36; _blocked :882-893 returns "(BLOCKED or TARGET_ERROR, why)" per FACTS :602).
- A whole output that is the reader's error JSON (code 400-599 with a name) becomes "its own error \<code\> \<name\>" (_reader_error, FACTS :552-565).
- `_status`: OK when anything was kept; else HUMAN_CHECK / BLOCKED when a wall stood in the way; else EMPTY (FACTS :937-942).
- A number the page does not state stays null: "nothing is guessed" (:36-37).

## dumb-code flags
- Magic numbers: _TITLE_SPAN = 8 (:180), MAX_RAW_BYTES = 200_000 (:63), READER_MIN_BYTES = 512 (FACTS :544), _BLOCK_PAGE_CHARS = 3000 (FACTS :863). [DERIVED]
- Near-duplicate literal constants: UNTRUSTED (:70) vs REPORT_UNTRUSTED (FACTS :540) — same sentence, only "supplier's own" vs "page's own" differs. [DERIVED]
- Policy sentence "Never solve, skip or work around a check" repeated in both WALLS entries (:72-77). [DERIVED]
- Asymmetric site metadata: EBAY_US is a single string (FACTS :539) while AMAZON_HOSTS is a 3-item list (FACTS :538). [DERIVED]
- Dead path by design: a Jina read of an eBay page is never parsed (eBay answers page readers with an error page, measured 2026-11-02) — _NOT_PARSED (FACTS :1645). [DERIVED]
- `_OTHERS` section exclusion is a long hard-coded alternation of marketing phrases ("recommend", "frequently bought", "popular products", ...) (:283-284); wording changes on the site side silently break it. [DERIVED]

## refactor notes
- Site-key dispatch is replicated across SITES/SOURCE_OF (:60-62), WALLS (:71-78), PRODUCT_URL_FORM (:68-69) and _TAIL (:342-343), keyed by ALIBABA/CJ imported from searxng.SITE / cj_api.SITE (:59) — renaming a site key breaks five mappings plus fallback/exa_command/_objective dispatch. [DERIVED]
- The handoff protocol strings — REPO, VERIFY ("agent-reach doctor --json"), SUBMIT_TOOL "supplier_parse", SUBMIT_ROUTE "POST /supplier/parse", NEVER (:55-67, :129-135) — are the external contract user-side agents follow; changing any of them breaks every existing Agent Reach run. [DERIVED]
- BadOutput codes are declared stable and carry the route's HTTP status (:82-86); renaming a code is a breaking API change for the importing route (orchestrator/orchestrator/api/product_report.py per FACTS.importers). [DERIVED]
- The framing regexes (_TITLE/_EXA_URL/_JINA_URL/_FINAL_URL/_MARKDOWN, :172-179) encode Exa/mcporter and Jina Reader output formats as measured 2026-11-01/02 (:15-18, :29-34); any change here must track those tools. [DERIVED]
- `parse` and `parse_report_source` share the framing, bounds and wall check (:26-28, :466-475, :1678-1785); changes to _split/_header/_lines hit both entry points and all 7 FACTS.importers. [DERIVED]

## VERIFY
```verify
grep -Fq 'KIND = "AGENT_REACH"' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'MAX_RAW_BYTES = 200_000' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'EXA_RESULTS = 10' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'ONE_PAGE_PER_CALL' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'agent-reach doctor --json' shared/polymath_shared/acquisition/agent_reach.py
test "$(grep -c -F 'BadOutput' shared/polymath_shared/acquisition/agent_reach.py)" -ge 5
! grep -Fq 'import requests' shared/polymath_shared/acquisition/agent_reach.py
```
