# unit: shared/polymath_shared/product_search/fetch_plan.py
anchor: shared/polymath_shared/product_search/fetch_plan.py:1-382

## purpose
Builds the deterministic FETCH PLAN for one round of a product decision report: a packet list (one exact command per read) plus one generated bash script that runs every Agent Reach read on the user's machine and POSTs each raw output straight to Polymath's upload capability, so no fetched page passes through the agent's model — shared/polymath_shared/product_search/fetch_plan.py:1-4 [DERIVED]. Uploaded outputs are parsed by `agent_reach.parse_report_source` — shared/polymath_shared/product_search/fetch_plan.py:4 [DERIVED]. Round 1: Reddit/Amazon/Alibaba/(eBay) searches per candidate; round 2: at most 3 Amazon + 3 Alibaba product pages per candidate, read by Jina — shared/polymath_shared/product_search/fetch_plan.py:6-11 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build` | def | `(report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] \| None = None, ebay_api: bool = False) -> dict[str, Any]` | shared/polymath_shared/product_search/fetch_plan.py:318-319 | orchestrator/orchestrator/api/product_report.py (module import, FACTS.importers) |
| `exa_command` | def | `(source: str, words: str, *, objective: str \| None = None, suffix: str = "") -> str` | shared/polymath_shared/product_search/fetch_plan.py:97 | — |
| `jina_command` | def | `(url: str, *, links: bool = False) -> str` | shared/polymath_shared/product_search/fetch_plan.py:107 | — |
| `amazon_search_url` | def | `(words: str) -> str` | shared/polymath_shared/product_search/fetch_plan.py:116 | — |

## contracts
**build** — shared/polymath_shared/product_search/fetch_plan.py:318-381
- in: `report_id` must match `_ID` `[A-Za-z0-9_-]{1,64}` (shared/polymath_shared/product_search/fetch_plan.py:64, checked :327); `round` ∈ `ROUNDS = (1, 2)` (:44, checked :329); `upload.url` http(s), `_SAFE_URL`-shaped, no `#`, length ≤ 2000 (:333-334); `upload.expires_at` ISO 8601 via `_ISO` (:336); `candidate_id` must match `[A-Za-z0-9_.:-]{1,64}` (:65, checked :345) and be unique (:347). [DERIVED]
- pre (raises): `ValueError("report_id is 1-64 letters, digits, '_' or '-'")` (:328); `ValueError(f"round is one of {ROUNDS}")` (:330); `ValueError("upload.url is the http(s) upload capability, without spaces, quotes or a fragment")` (:335); `ValueError("upload.expires_at is an ISO 8601 time")` (:337); `ValueError` on candidate_id shape/duplication (:346, :348). [DERIVED]
- out: dict with keys `contract, round, packets, script, script_sha256, limits, how, skipped` (:380-381); each packet is `{packet_id, candidate_id, source, kind, commands: [str], reads, expect}` (:131-132). [DERIVED]
- post: same arguments → same plan, byte for byte (no clock, no randomness, no environment) (:31); `script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()` (:363). [DERIVED]
- Round 1 packet ids `r1-c{index}-{source}-{n}` (:137-150); round 2 ids `r2-c{index}-{source}-{n}` (:191); eBay packet emitted only when `not ebay_api` (:149-150). [DERIVED]

**exa_command** — shared/polymath_shared/product_search/fetch_plan.py:97-104
- out: `mcporter call ${EXA_API_KEY:+--http-url …} exa.web_search_exa 'query=site:<host> <words> <suffix>' numResults=8 'objective=<goal>'`; query and objective are `shlex.quote`d (:103-104); query starts with `site:` so no value starts with `@` (:99-100). [DERIVED]

**jina_command** — shared/polymath_shared/product_search/fetch_plan.py:107-113
- out: `curl -s -g -m 90 ${JINA_API_KEY:+-H …} [-H 'X-With-Links-Summary: true'] 'https://r.jina.ai/<url>'` — URL globbing off (`-g`), 90 s limit, URL `shlex.quote`d (:110-113). [DERIVED]

## effect surface
- Postgres / Qdrant: none — `tables_read: []`, `tables_written: []` (FACTS); imports are only `hashlib, re, shlex, unicodedata, typing, urllib.parse` — shared/polymath_shared/product_search/fetch_plan.py:34-39 [DERIVED].
- Plan-time I/O: none; pure string building (:31, :362). [DERIVED]
- Network (inside the *generated script*, not this module): `mcporter call … exa.web_search_exa` (:103); `curl https://r.jina.ai/<url>` (:110, :113); upload POST `--data-binary "@$out" … "${UPLOAD_URL}${UPLOAD_SEP}packet=$1"` (:252); keyed Exa endpoint `https://mcp.exa.ai/mcp?exaApiKey=` (:58). [DERIVED]
- Env flags read by the generated script: `EXA_API_KEY` = unset (keyed endpoint added only when set, via `${EXA_API_KEY:+…}` :60, :208); `JINA_API_KEY` = unset (Bearer header only when set :61, :209); `TMPDIR` = `/tmp` fallback in `mktemp` (:213). [DERIVED]
- Subprocess requirements: `curl` (script exits 3 without it :211) and `mcporter` (warn only :212); script targets bash 3.2 (:13). [DERIVED]

## invariants
INVARIANT: candidates planned per report ≤ `MAX_CANDIDATES = 8` — shared/polymath_shared/product_search/fetch_plan.py:45, :350-351 [DERIVED]
  fails-if: the 9th+ candidate lands in `skipped` with code `"OVER_LIMIT"` and is never searched.
INVARIANT: every Exa command carries `numResults={EXA_RESULTS}` with `EXA_RESULTS = 8` — shared/polymath_shared/product_search/fetch_plan.py:46, :104 [DERIVED]
  fails-if: result-count drift between the plan text and the measured probes (2026-11-02 used 8).
INVARIANT: round-2 pages per candidate ≤ `ROUND2_PAGES = {"amazon": 3, "alibaba": 3}` — shared/polymath_shared/product_search/fetch_plan.py:47, :186-187 [DERIVED]
  fails-if: extra targets get code `"OVER_LIMIT"` and the round silently reads fewer pages than asked.
INVARIANT: keyless `exa_parallel` (3) < keyed (8); keyless `jina_per_minute` (20) < keyed (300) — shared/polymath_shared/product_search/fetch_plan.py:49-50 [DERIVED]
  fails-if: keyless Exa answered 429 at 4 parallel calls (:14); raising the keyless parallel value re-triggers 429s.
INVARIANT: `_jina_gap(LIMITS, 1) = 3` s and `_jina_gap(LIMITS_WITH_KEYS, 5) = 1` s — shared/polymath_shared/product_search/fetch_plan.py:294 (`max(1, -(-60 * parallel // limits["jina_per_minute"]))`) [INFERRED: 60·1/20 → 3; 60·5/300 → 1]
  fails-if: gap below these values exceeds `jina_per_minute` (20 keyless / 300 keyed).
INVARIANT: search-words line length ≤ `_TERM_CHARS = 120` characters — shared/polymath_shared/product_search/fetch_plan.py:71, :94 [DERIVED]
  fails-if: longer candidate text truncates silently and changes every derived query.
INVARIANT: retries per packet ≤ 1, after `RETRY_AFTER_S = {"exa": 5, "jina": 4}` — shared/polymath_shared/product_search/fetch_plan.py:57, :238-243 [DERIVED]
  fails-if: a second retry would break the summary-line contract "retried once" (:28, :242).
INVARIANT: `script_sha256 == sha256(script.encode("utf-8")).hexdigest()` — shared/polymath_shared/product_search/fetch_plan.py:363, :380 [DERIVED]
  fails-if: any byte change to `_HEAD`/`_TAIL`/commands invalidates the published digest without a code change in this file.
INVARIANT: script exit code ∈ {0, 3} — 0 even when a site blocks the reader, 3 only when it cannot run (no curl) — shared/polymath_shared/product_search/fetch_plan.py:25, :211, :288 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — "the same arguments give the same plan, byte for byte (no clock, no randomness, no environment)" — shared/polymath_shared/product_search/fetch_plan.py:31 [DERIVED]
idempotency: SAFE for `build` (pure, :31); the generated script's re-run re-POSTs every packet to `UPLOAD_URL` (:252) — duplicate handling is the host's, not visible here [INFERRED]

## failure behaviour
- `build` raises `ValueError` at 6 sites for malformed report id / round / upload url / expires_at / candidate id / duplicate id — shared/polymath_shared/product_search/fetch_plan.py:327-348 [DERIVED].
- Non-errors go to `skipped`: candidate-level `"OVER_LIMIT"`, `"NO_SEARCH_TERMS"` (:350-355); target-level `"UNKNOWN_CANDIDATE"` (:173), `"SOURCE_NOT_READ"` (round 2 reads Amazon and Alibaba only, :176-177), `"NOT_A_PRODUCT_PAGE"` (:181-182), `"OVER_LIMIT"` (:187). [DERIVED]
- Generated script: a failed read (non-zero exit, under `AR.READER_MIN_BYTES` bytes, or Jina's own error JSON `"code": 4xx/5xx` with `"name"`/`"readableMessage"`) is retried once (:28-30, :217-227, :238-243); an EMPTY output is uploaded too so the round can complete (:26, :247-250). [DERIVED]

## dumb-code flags
- Parameter named `round` shadows the builtin inside `build` (:318); `_script` spells it `round_` to avoid the same trap (:297). [DERIVED]
- `[:10]` cap on `search_terms` with no named constant or comment (:123). [DERIVED]
- Three unrelated caps: URL length 2000 (:334), `_ALIBABA_DETAIL` slug `{1,300}` (:69), `AR._clip(..., 300)` in skipped records (:173, :176, :181). [DERIVED]
- Docstring hardcodes `512` for the min-bytes threshold while code uses `AR.READER_MIN_BYTES` (:29 vs :305) — drift risk if AR changes. [DERIVED]
- Comment records "plan §3: max_products default 5, cap 8" (:45): the default 5 lives outside this file; only the cap 8 is enforced here. [DERIVED]
- Pacing split across four constants (`LIMITS`, `LIMITS_WITH_KEYS`, `JINA_PARALLEL`, `EXA_GAP_S`) instead of one table (:49-52); the value 3 means three different things: exa_parallel=3 (:49), round-2 pages=3 (:47), keyless Jina gap=3 s (derived from :294). [DERIVED]
- FACTS renders the `ROUND2_PAGES` value with keys sorted (`{"alibaba": 3, "amazon": 3}`) while SOURCE writes `{"amazon": 3, "alibaba": 3}` (:47) — copy SOURCE, not the FACTS JSON. [DERIVED]

## refactor notes
- Return keys of `build` (:380-381) are the host contract; importer is orchestrator/orchestrator/api/product_report.py (FACTS.importers) — renaming any key breaks it. [DERIVED]
- Packet id formats `r1-c{index}-…` (:137-150) and `r2-c{index}-{source}-{n}` (:191) feed the upload query `packet=$1` (:252); host-side parsing keys on them. [DERIVED]
- `shlex.quote` on every candidate-derived and URL value (:103-104, :113, :299, :311) is the injection defence — a term like `$(touch /tmp/x)` must stay a search word (:20-22); do not drop it. [DERIVED]
- `_HEAD`/`_TAIL` are `str.format` templates with doubled braces for shell syntax (:196-270, :272-289, formatted at :299-306, :314); edits must preserve `{{`/`}}` and bash-3.2 compatibility (:13). [DERIVED]
- `CONTRACT = "product-report-fetch-plan-v1"` appears in the returned dict (:380) and is injected into the script header via `contract=CONTRACT` (:43, :299); bumping it changes every script's `script_sha256`. [DERIVED]
- Depends on `polymath_shared.acquisition.agent_reach` attributes: `AR._CONTROL` (:93), `AR.MAX_REPORT_BYTES` (:416), `AR.TOOL_EXA`/`AR.TOOL_JINA` (:428-431, :595-596), `AR.amazon_product_url`/`AR.alibaba_page_url` (:441, :444), `AR._clip` (:173), `AR.READER_MIN_BYTES` (:305), `AR.REPO`/`AR.VERIFY` (:367) — renames there break this file. [DERIVED]

## VERIFY
```verify
grep -Fq 'CONTRACT = "product-report-fetch-plan-v1"' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'LIMITS = {"exa_parallel": 3, "jina_per_minute": 20}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'ROUND2_PAGES = {"amazon": 3, "alibaba": 3}' shared/polymath_shared/product_search/fetch_plan.py
grep -Eq 'RETRY_AFTER_S = \{"exa": 5, "jina": 4\}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'numResults={EXA_RESULTS}' shared/polymath_shared/product_search/fetch_plan.py
! grep -Fq 'os.environ' shared/polymath_shared/product_search/fetch_plan.py
test "$(grep -c -F 'raise ValueError' shared/polymath_shared/product_search/fetch_plan.py)" -ge 6
```
