# unit: shared/polymath_shared/product_search/fetch_plan.py
anchor: shared/polymath_shared/product_search/fetch_plan.py:1-357

## purpose
Builds the fetch plan of one round of a product decision report (contract `product-report-fetch-plan-v1`): one packet per Agent Reach read with its exact shell command, plus one bash script that runs every read on the user's machine and uploads each raw output straight to Polymath — no fetched page passes through an agent's model; Polymath parses uploads with `agent_reach.parse_report_source` — shared/polymath_shared/product_search/fetch_plan.py:1-4,40 [DERIVED]. Round 1 reads Reddit (2 Exa searches), Amazon (1 Exa search + 1 Jina read of the search page with `X-With-Links-Summary: true`), Alibaba (1 Exa search), eBay (1 Exa search only when the host has no eBay Browse API); round 2 reads at most 3 Amazon + 3 Alibaba product pages per candidate via Jina — shared/polymath_shared/product_search/fetch_plan.py:6-11 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build` | function | `(report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] \| None = None, ebay_api: bool = False) -> dict[str, Any]` | shared/polymath_shared/product_search/fetch_plan.py:294-357 | orchestrator/orchestrator/api/product_report.py (module importer; exact symbols not shown in FACTS) |
| `exa_command` | function | `(source: str, words: str, *, objective: str \| None = None, suffix: str = "") -> str` | shared/polymath_shared/product_search/fetch_plan.py:90-97 | — |
| `jina_command` | function | `(url: str, *, links: bool = False) -> str` | shared/polymath_shared/product_search/fetch_plan.py:100-106 | — |
| `amazon_search_url` | function | `(words: str) -> str` | shared/polymath_shared/product_search/fetch_plan.py:109-110 | — |
| `CONTRACT` | constant | `"product-report-fetch-plan-v1"` | shared/polymath_shared/product_search/fetch_plan.py:40 | — |

## contracts

**`build`** — shared/polymath_shared/product_search/fetch_plan.py:294-357
- in: `report_id` matches `[A-Za-z0-9_-]{1,64}` (303-304); `round` in `ROUNDS = (1, 2)` (305-306, 41); `upload.url` matches `_SAFE_URL`, scheme http(s), no `#`, `len(url) <= 2000` (309-311); `upload.expires_at` matches `_ISO` (312-313, 59); candidate ids match `[A-Za-z0-9_.:-]{1,64}`, unique, missing id becomes `f"c{n}"` (320-324, 58).
- in: `candidates` items are `{candidate_id?, title, search_terms?: [str]}` (299-300); `targets` (round 2) are the parser's `next_targets` `{url, source, candidate_id, ...}` (300-301).
- out: `{contract, round, packets, script, script_sha256, limits: {**LIMITS, with_keys: LIMITS_WITH_KEYS}, how, skipped}` (356-357); each packet is `{packet_id, candidate_id, source, kind, commands: [command], reads, expect: {tool_class, parse: {source, kind}, max_bytes: AR.MAX_REPORT_BYTES}}` (123-125).
- pre: raises `ValueError` on malformed report id (304), round (306), upload.url (311), expires_at (313), candidate_id (322), duplicate candidate_id (324).
- post: round 1 emits per candidate packets `r1-c{i}-reddit-1`, `-reddit-2`, `-amazon-1` (Exa), `-amazon-2` (Jina with `links=True`), `-alibaba-1`, plus `-ebay-1` only when `ebay_api` is false (128-144); round 2 emits `r2-c{i}-{source}-{n}` Jina packets, max 3 amazon + 3 alibaba per candidate (179-184, 44); `script_sha256 = sha256(script.encode("utf-8"))` (338-339); `PACKETS` in the script head equals `len(packets)` (277).
- post: `how` carries keys `run`, `needs`, `keys`, `never`, `output`, `then`, `expires`, `verify` (342-354).

**`exa_command`** — shared/polymath_shared/product_search/fetch_plan.py:90-97
- in: `source` must be a `_SITE` key (`reddit`/`amazon`/`alibaba`/`ebay`) — indexed at 94-95; `objective` defaults to `_OBJECTIVE[source]` (95).
- out: one line `mcporter call ${EXA_API_KEY:+…} exa.web_search_exa query=<site: …> numResults=8 objective=<…>`, query and objective `shlex.quote`d (96-97, 43).
- post: the query always starts with `site:` so no argument starts with `@` (mcporter reads a FILE for `key=@path`) (92-94).

**`jina_command`** — shared/polymath_shared/product_search/fetch_plan.py:100-106
- in: `url` string; `links` adds `-H 'X-With-Links-Summary: true'` (104-105, 55).
- out: `curl -s -g -m 90 ${JINA_API_KEY:+…} [links header] 'https://r.jina.ai/<url>'` — globbing off (`-g`), 90 s limit, URL quoted (103-106, 50).

**`amazon_search_url`** — out `f"https://www.amazon.com/s?k={quote_plus(words)}"` — shared/polymath_shared/product_search/fetch_plan.py:110 [DERIVED].

## effect surface
- Postgres: none (FACTS `tables_read: []`, `tables_written: []`). Qdrant: none visible.
- Plan build: pure — no clock, randomness, environment, network or files (28; imports 31-38 are `hashlib`, `re`, `shlex`, `unicodedata`, `typing`, `urllib.parse`, `polymath_shared.acquisition.agent_reach as AR`).
- AR surface used: `AR._CONTROL` (86), `AR.MAX_REPORT_BYTES` (125), `AR.TOOL_EXA`/`AR.TOOL_JINA` (132-143, 184, 287-288), `AR.amazon_product_url` (150), `AR.alibaba_page_url` (153), `AR._clip` (166, 168, 174), `AR.REPO` (281, 343), `AR.VERIFY` (343).
- Generated script (runs on the user's machine, not here): subprocesses `mcporter` (Exa; keyed endpoint `https://mcp.exa.ai/mcp?exaApiKey=` 51) and `curl` (Jina `https://r.jina.ai/<url>` 104; upload POST as `text/plain` with `?packet=<packet_id>` 229); files under `mktemp -d "${TMPDIR:-/tmp}/polymath-report.XXXXXX"` — `$WORK/$1.out`, `$WORK/$1.err`, `$WORK/uploaded`, removed by EXIT trap (206-207, 212-213, 230).
- Env flags read by the generated script: `EXA_API_KEY` (default unset; selects keyed endpoint and parallel 8, 53, 201), `JINA_API_KEY` (default unset; Authorization header and 300 RPM pacing, 54, 202), `TMPDIR` (default `/tmp`, 206).

## invariants
INVARIANT: planned candidates <= `MAX_CANDIDATES = 8` — shared/polymath_shared/product_search/fetch_plan.py:42,326-327 [DERIVED]
  fails-if: the 9th+ candidate is never fetched; it only appears in `skipped` with code `OVER_LIMIT`.
INVARIANT: round-2 pages per candidate = `ROUND2_PAGES = {"amazon": 3, "alibaba": 3}` — shared/polymath_shared/product_search/fetch_plan.py:44,179-184 [DERIVED]
  fails-if: extras are dropped (`OVER_LIMIT`) or the read budget silently grows.
INVARIANT: keyless Jina start gap = ceil(60×1/20) = 3 s; with keys = ceil(60×5/300) = 1 s — shared/polymath_shared/product_search/fetch_plan.py:46-48,269-271 (docstring 14-16) [DERIVED]
  fails-if: gap too small → HTTP 429 (keyless limit measured 20 reads/min/IP, line 14).
INVARIANT: Exa in flight <= 3 keyless (429 measured at 4 parallel), <= 8 keyed — shared/polymath_shared/product_search/fetch_plan.py:14-16,46-47 [DERIVED]
  fails-if: Exa 429s; the script retries once (sleep 5) then records the packet EMPTY.
INVARIANT: `len(packet["commands"]) == 1` — shared/polymath_shared/product_search/fetch_plan.py:124,286-287 [DERIVED]
  fails-if: the script's `p{n}() {{ <command>; }}` body desyncs from the plan's `commands`.
INVARIANT: every Exa query starts with `site:` — shared/polymath_shared/product_search/fetch_plan.py:92-94 [DERIVED]
  fails-if: a value starting with `@` would make mcporter read a file instead of searching (line 93).
INVARIANT: API keys exist only as shell `${VAR:+…}` expansions; never literals in plan or script — shared/polymath_shared/product_search/fetch_plan.py:17-19,53-54 [DERIVED]
  fails-if: secrets leak into the stored plan/script text.
INVARIANT: `script_sha256` == sha256 of the returned `script` — shared/polymath_shared/product_search/fetch_plan.py:338-339,354 [DERIVED]
  fails-if: `how.verify` no longer matches the script the user runs.
INVARIANT: script exit ∈ {0, 3} — 0 even when a site blocks the reader, 3 only when `curl` is missing — shared/polymath_shared/product_search/fetch_plan.py:25,204,265 [DERIVED]
  fails-if: a caller treating nonzero exit as fatal loops on blocked sites.
INVARIANT: every packet is uploaded, empty outputs too (recorded EMPTY), so a round can always complete — shared/polymath_shared/product_search/fetch_plan.py:26-27,224-228 [DERIVED]
  fails-if: round 1 never completes, so round 2 is never minted (line 27).

## determinism & idempotency
determinism: DETERMINISTIC — "the same arguments give the same plan, byte for byte (no clock, no randomness, no environment)" — shared/polymath_shared/product_search/fetch_plan.py:28,31-38 [DERIVED]
idempotency: SAFE — `build` is a pure function: no DB, no network, no file writes at build time (FACTS `tables_read/tables_written` empty; only output is the returned dict, 356-357).

## failure behaviour
- No try/except in the module; `build` raises `ValueError` with fixed messages: `"report_id is 1-64 letters, digits, '_' or '-'"` (304), `f"round is one of {ROUNDS}"` (306), `"upload.url is the http(s) upload capability, without spaces, quotes or a fragment"` (311), `"upload.expires_at is an ISO 8601 time"` (313), candidate-id shape and duplicate messages (322, 324).
- Soft failures are collected in the returned `skipped` list, never raised: candidate codes `OVER_LIMIT` (327), `NO_SEARCH_TERMS` (330); round-2 target codes `UNKNOWN_CANDIDATE` (166), `SOURCE_NOT_READ` (169-170), `NOT_A_PRODUCT_PAGE` (174-175), `OVER_LIMIT` (180).
- Generated script: one retry after a 429 with empty output (`sleep 5`) (216-220); zero-byte output uploaded as EMPTY with a rate-limit note (224-227); missing `mcporter` only warns (205); missing `curl` exits 3 (204); `set -u` (195).

## dumb-code flags
- Magic numbers: URL length cap `2000` (310); clip length `300` in `AR._clip(..., 300)` (166, 168, 174); `[:10]` search-terms cap (116); `_TERM_CHARS = 120` (64, 87).
- `"OVER_LIMIT"` carries two meanings: too many candidates (327) vs too many round-2 pages per candidate (180).
- `_OBJECTIVE` has key `"reddit_2"` with no matching `_SITE` key; `exa_command("reddit_2", ...)` would KeyError at `_SITE[source]` (67-79, 94-95) — only safe because the caller passes `source="reddit"` with `objective=_OBJECTIVE["reddit_2"]` (134-135). [DERIVED for the dict mismatch; INFERRED for the KeyError since dict indexing raises]
- Asymmetric tool check: no `curl` → `exit 3`, no `mcporter` → warning only, Exa packets then fail (204-205).
- `JINA_TIMEOUT_S, UPLOAD_TIMEOUT_S, RETRY_AFTER_S = 90, 120, 5` packed in one tuple (50).
- `build`'s parameter `round` shadows the `round` builtin (294).

## refactor notes
- Importer `orchestrator/orchestrator/api/product_report.py` (FACTS.importers) — changing `build`'s return keys (`contract, round, packets, script, script_sha256, limits, how, skipped`, 356-357) or the ValueError messages ripples there.
- `CONTRACT = "product-report-fetch-plan-v1"` is baked into the generated script header (190) and the plan output (356); any change alters script bytes → `script_sha256` and `how.verify` (339, 354).
- Packet id format `r1-c{index}-{source}-{n}` / `r2-c{index}-{source}-{n}` (130, 132-143, 184) becomes the upload query param `?packet=<packet_id>` (229); renaming breaks host-side packet correlation. [INFERRED — host records packets by id per docstring line 4]
- `exa_command` indexes both `_SITE` and `_OBJECTIVE` by `source` (94-95); adding a source requires both dicts, plus `ROUND2_PAGES` if round 2 should read it (44, 168).
- Pacing constants `LIMITS`/`LIMITS_WITH_KEYS`/`JINA_PARALLEL`/`EXA_GAP_S` (46-49) are mirrored into the script head text (201-203, 277-281); change them in both places or the reported `limits` disagree with actual script pacing.
- Heavy `AR` (agent_reach) coupling: `_CONTROL`, `MAX_REPORT_BYTES`, `TOOL_EXA`, `TOOL_JINA`, `amazon_product_url`, `alibaba_page_url`, `_clip`, `REPO`, `VERIFY` (86, 125, 132-143, 150, 153, 166-174, 281, 343) — renaming any of those in `polymath_shared.acquisition` breaks this module.

## VERIFY
```verify
grep -Fq 'CONTRACT = "product-report-fetch-plan-v1"' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'LIMITS = {"exa_parallel": 3, "jina_per_minute": 20}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'ROUND2_PAGES = {"amazon": 3, "alibaba": 3}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'X-With-Links-Summary: true' shared/polymath_shared/product_search/fetch_plan.py
grep -Eq 'site:.*_SITE\[source\]' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'raise ValueError(f"round is one of {ROUNDS}")' shared/polymath_shared/product_search/fetch_plan.py
test "$(grep -c -F 'OVER_LIMIT' shared/polymath_shared/product_search/fetch_plan.py)" -ge 2
! grep -Fq 'os.environ' shared/polymath_shared/product_search/fetch_plan.py
```
