# unit: shared/polymath_shared/acquisition/agent_reach.py
anchor: shared/polymath_shared/acquisition/agent_reach.py:1-1726

## purpose
Builds Agent Reach handoff commands (Exa search via mcporter, Jina Reader curl) for the user's own machine and parses the text output the user sends back into listing records; this host never calls Exa, Jina or any page reader itself — shared/polymath_shared/acquisition/agent_reach.py:1-13 [DERIVED]. Second entry point `parse_report_source` (PRODUCT-DECISION-REPORT-V1, 2026-11-02) parses one upload of the report's fetch script for reddit / amazon / ebay / alibaba into report records — shared/polymath_shared/acquisition/agent_reach.py:26-38 [DERIVED]. Pure module, no I/O — shared/polymath_shared/acquisition/agent_reach.py:38 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `BadOutput` | class | `(code: str, message: str, status: int = 422)` | agent_reach.py:80-85 | — |
| `site_of` | def | `(value: Any) -> str \| None` | agent_reach.py:89-93 | — |
| `exa_command` | def | `(site: str, query: str) -> str` | agent_reach.py:107-111 | — |
| `jina_command` | def | `(url: str = "<PRODUCT_URL>") -> str` | agent_reach.py:114-116 | — |
| `fallback` | def | `(site: str, query: str \| None, reason_code: str, why: str) -> dict` | agent_reach.py:119-136 | — |
| `on_site` | def | `(url: str, site: str) -> bool` | agent_reach.py:151-153 | — |
| `cj_product_url` | def | `(url: Any) -> tuple[str, str] \| None` | agent_reach.py:156-163 | — |
| `product_page` | def | `(site: str, url: str) -> tuple[str, str] \| None` | agent_reach.py:166-167 | — |
| `clean_text` | def | `(raw_text, max_bytes) -> str` | agent_reach.py:465-474 | — |
| `parse` | def | `(site: str, raw_text) -> dict` | agent_reach.py:477-524 | — |
| `head_terms` | def | `(term) -> head terms of the term` | agent_reach.py:681-692 | — |
| `missing_terms` | def | `(title, head) -> terms `title` does not hold` | agent_reach.py:725-737 | — |
| `reddit_thread_url` | def | `(url) -> tuple \| None` | agent_reach.py:861-870 | — |
| `amazon_product_url` | def | `(url) -> tuple \| None` | agent_reach.py:970-976 | — |
| `ebay_item_url` | def | `(url) -> tuple \| None` | agent_reach.py:1257-1266 | — |
| `alibaba_page_url` | def | `(url) -> tuple \| None` | agent_reach.py:1357-1367 | — |
| `parse_report_source` | def | `(source, raw_text, kind, candidate_terms) -> dict` | agent_reach.py:1632-1725 | — |

Importers (per-symbol mapping not in FACTS): orchestrator/orchestrator/api/product_report.py, shared/polymath_shared/acquisition/service.py, shared/polymath_shared/acquisition/supplier.py, shared/polymath_shared/product_search/fetch_plan.py, host_data.py, hypotheses.py, product_search/service.py — FACTS.importers [DERIVED].

## contracts

**`fallback(site, query, reason_code, why)`** — agent_reach.py:119-136
- in: `site` must be a key of `WALLS` (`ALIBABA` or `CJ`); else `WALLS[site]` raises KeyError — agent_reach.py:135 [INFERRED: direct dict index].
- out: dict with keys `kind, reason_code, why, site, query, run_on, never, install, commands, submit, walls`; `commands` is a 2-step list (Exa search, then Jina per product page) — agent_reach.py:122-136.
- post: every built command value is shell-quoted (`shlex.quote`) — agent_reach.py:43-44, 110-111, 116.

**`exa_command(site, query)`** — agent_reach.py:107-111
- out: `mcporter call exa.web_search_exa query=<site:... quoted> numResults=10 objective=<quoted>`; `numResults` is `EXA_RESULTS` (10) — agent_reach.py:64, 110-111.
- pre/post: query value starts with `site:` so it never starts with `@` (mcporter reads a file for `key=@path`) — agent_reach.py:109.

**`jina_command(url)`** — agent_reach.py:114-116
- out: `curl -s 'https://r.jina.ai/<url>'`; default placeholder `<PRODUCT_URL>` — agent_reach.py:116.

**`parse(site, raw_text)`** — agent_reach.py:477-524
- in: one Agent Reach command's whole output, unedited; bounded to `MAX_RAW_BYTES` — agent_reach.py:13, 62.
- out: `{tool_class, records, refused, documents, notes}`; records are listing fields (title, product URL + id, price or tiers with quantities, MOQ, supplier, years, sold, reviews) — agent_reach.py:13-15, 477-524.
- post: a verification/challenge page is refused (`HUMAN_CHECK`) and yields no record — agent_reach.py:19-21.
- error: mixed or unrecognised output raises `BadOutput` (`MIXED_OUTPUT`, `UNRECOGNISED_OUTPUT`, `ONE_PAGE_PER_CALL`) — agent_reach.py:220, 262, 268, 270.

**`clean_text(raw_text, max_bytes)`** — agent_reach.py:465-474
- out: submitted text bounded and normalised to at most `max_bytes`, default cap `MAX_RAW_BYTES` — agent_reach.py:465-474.

**`parse_report_source(source, raw_text, kind, candidate_terms)`** — agent_reach.py:1632-1725
- in: one upload of the report's fetch script; `source` in `REPORT_SOURCES = ["reddit", "amazon", "ebay", "alibaba"]`, `kind` in `REPORT_KINDS = ["search", "page"]` — agent_reach.py:529-530.
- out: `{status, source, kind, records, next_targets, refused}` plus `tool_class, notes`; `status` in `REPORT_STATUSES = ["OK", "EMPTY", "BLOCKED", "HUMAN_CHECK", "UNRECOGNISED"]` — agent_reach.py:531, 1632-1725.
- post: a number the page does not state stays null; nothing is guessed — agent_reach.py:37.

**`site_of(value)`** — agent_reach.py:89-93
- in: host name, URL, or source name; out: a site in `SITES = (ALIBABA, CJ)` or `None` — agent_reach.py:59, 89-93.

## effect surface
- Postgres tables read/written: none — FACTS.tables_read, FACTS.tables_written [DERIVED].
- Network calls, subprocesses, files, env flags: none executed by this host; it only builds command strings for the user's machine — agent_reach.py:7-9, 38, 107-116 [DERIVED].
- Reads sibling modules `cj_api`, `searxng` (site constants, `listing_url`, `valid_id`) and `challenge` (`looks_like_challenge`, `segments`) — agent_reach.py:50-51, 58, 163, 167-168.

## invariants
- INVARIANT: parse input bound = `MAX_RAW_BYTES = 200_000` bytes — agent_reach.py:62; fails-if: oversized user output is accepted unbounded, framing/wall checks run on truncated or huge text.
- INVARIANT: records cap = `MAX_RECORDS = 50` — agent_reach.py:63; fails-if: a single upload can flood listing records past the contract.
- INVARIANT: Exa result count = `EXA_RESULTS = 10` — agent_reach.py:64, 110; fails-if: handoff command returns a different page count than parse fixtures assume.
- INVARIANT: mcporter query always starts with `site:` (never `@`) — agent_reach.py:109; fails-if: mcporter treats the query as a file path.
- INVARIANT: one Jina page per call; a second `Title:`/`URL Source:` header raises `ONE_PAGE_PER_CALL` — agent_reach.py:219-221; fails-if: a page's own printed header smuggles in a second record set.
- INVARIANT: every record comes only from reader framing (Exa result after `---` with full header, or one Jina page) — agent_reach.py:23-24, 224-253; fails-if: page text can inject fake records.
- INVARIANT: `BadOutput` default HTTP status = `422` — agent_reach.py:84; fails-if: route answers with a different status than callers expect.
- INVARIANT: `_BLOCK_HTTP = [401, 403, 405, 407, 429, 451, 503]` are the reader-warning statuses treated as a block — agent_reach.py:804; fails-if: a blocked site looks like an empty result.
- INVARIANT: `_BLOCK_PAGE_CHARS = 3000` caps how much of a page the check-page word scan reads — agent_reach.py:817; fails-if: long pages' check-page titles are missed and walls are parsed as data.
- INVARIANT: `SITES = (ALIBABA, CJ)` and `SOURCE_OF = {ALIBABA: "alibaba", CJ: "cj"}` — agent_reach.py:58-61; fails-if: `site_of`/`fallback` accept or reject the wrong hosts.

## determinism & idempotency
determinism: DETERMINISTIC (docstring states "Pure: no I/O.", no clock/random/network/db use — agent_reach.py:38, 41-48) [DERIVED]
idempotency: SAFE (string-in/dict-out pure functions; nothing is written or mutated outside the call — agent_reach.py:38) [DERIVED]

## failure behaviour
- `BadOutput(ValueError)` with stable `code`, `message`, `status=422`: `ONE_PAGE_PER_CALL` — agent_reach.py:220; `MIXED_OUTPUT` (Exa+Jina in one payload) — agent_reach.py:262, 268; `UNRECOGNISED_OUTPUT` (no Exa result and no Jina page found) — agent_reach.py:270-271.
- `_host` swallows `urlsplit` `ValueError` and returns `None` (bad URL -> not on site, not an exception) — agent_reach.py:143-148.
- Wall pages are refusals, not exceptions: a challenge page -> `HUMAN_CHECK`, a block page (Jina 200 + `Warning: Target URL returned error 403`, block title or words) -> `BLOCKED`; nothing from either becomes a record — agent_reach.py:19-21, 35-37, 836-847.
- `_status`: `OK` when anything was kept; else `HUMAN_CHECK` / `BLOCKED` when a wall stood in the way; else `EMPTY` — agent_reach.py:1591-1596.

## dumb-code flags
- Near-duplicate literals `UNTRUSTED` ("the supplier's own untrusted text...") and `REPORT_UNTRUSTED` ("the page's own untrusted text...") differ by one word — agent_reach.py:69, 539.
- `WALLS` repeats the same "Never solve, skip or work around a check" sentence in both per-site strings — agent_reach.py:70-77.
- Magic numbers: `_TITLE_SPAN = 8` (Exa title wrap window) — agent_reach.py:179; `_BLOCK_PAGE_CHARS = 3000` — agent_reach.py:817; `JOIN_MAX = 3` — agent_reach.py:670.
- Measurement dates burned into strings/docstrings ("measured 2026-11-01", "measured 2026-11-02", "live 2026-11-02") — agent_reach.py:71-76, 108, 1237, 1599.
- eBay Jina reads are a documented dead lane: `_NOT_PARSED` says a Jina read of an eBay page is not parsed (error page, measured 2026-11-02) — agent_reach.py:1599.

## refactor notes
- Seven importers depend on this module (orchestrator product_report API, acquisition service/supplier, product_search fetch_plan/host_data/hypotheses/service) — FACTS.importers [DERIVED]; renaming any public symbol above touches all seven.
- `BadOutput.code` values (`ONE_PAGE_PER_CALL`, `MIXED_OUTPUT`, `UNRECOGNISED_OUTPUT`) and `status=422` are a stable API answered by route `POST /supplier/parse` — agent_reach.py:66, 84, 220-271; changing them breaks the route's error contract.
- `REPORT_SOURCES` / `REPORT_KINDS` / `REPORT_STATUSES` are the schema of `parse_report_source` output consumed by product_report — agent_reach.py:529-531, 1632-1725.
- `fallback`'s payload keys (`commands`, `submit`, `walls`, `install`) are read by user-facing agents as instructions; wording changes are user-visible — agent_reach.py:119-136.
- Framing regexes (`_TITLE`, `_EXA_URL`, `_JINA_URL`, `_FINAL_URL`) and the `---` rule define what counts as a record boundary; loosening them re-opens the record-smuggling hole the docstring calls out — agent_reach.py:23-24, 171-178, 224-253.
- Site coupling: `ALIBABA, CJ` come from `searxng.SITE` / `cj_api.SITE`; `product_page` dispatches per site — agent_reach.py:58, 166-167.

## VERIFY
```verify
grep -Fq 'MAX_RAW_BYTES = 200_000' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'EXA_RESULTS = 10' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'status: int = 422' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'ONE_PAGE_PER_CALL' shared/polymath_shared/acquisition/agent_reach.py
grep -Fq 'https://r.jina.ai/' shared/polymath_shared/acquisition/agent_reach.py
test "$(grep -c -F 'BadOutput' shared/polymath_shared/acquisition/agent_reach.py)" -ge 5
```
