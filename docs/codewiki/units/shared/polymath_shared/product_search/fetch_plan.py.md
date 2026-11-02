# unit: shared/polymath_shared/product_search/fetch_plan.py
anchor: shared/polymath_shared/product_search/fetch_plan.py:1-421

## purpose
Builds the fetch plan of one round of a Polymath product-decision report: every Agent Reach read becomes a packet with its exact command, plus one POSIX bash script that runs all reads on the user's machine and uploads each raw output straight to Polymath, so no fetched page passes through the agent's model. — fetch_plan.py:1-4 [DERIVED]
Polymath parses each upload with `agent_reach.parse_report_source`. — fetch_plan.py:4 [DERIVED]
Pure and deterministic: same arguments give the same plan, byte for byte. — fetch_plan.py:34 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `build` | def | `(report_id: str, candidates: list[dict], *, round: int, upload: dict, targets: list[dict] \| None = None, ebay_api: bool = False) -> dict[str, Any]` | fetch_plan.py:357-420 [DERIVED] | orchestrator/orchestrator/api/product_report.py [INFERRED: only module importer, FACTS.importers] |
| `exa_command` | def | `(source: str, words: str, *, objective: str \| None = None, suffix: str = "") -> str` | fetch_plan.py:106-113 [DERIVED] | — |
| `jina_command` | def | `(url: str, *, links: bool = False, retry: bool = False) -> str` | fetch_plan.py:116-124 [DERIVED] | — |
| `amazon_search_url` | def | `(words: str) -> str` | fetch_plan.py:133-134 [DERIVED] | — |

## contracts

**build** — fetch_plan.py:357-420
- in: `report_id` must fullmatch `[A-Za-z0-9_-]{1,64}` else `ValueError("report_id is 1-64 letters, digits, '_' or '-'")`. — fetch_plan.py:366-367, 73 [DERIVED]
- in: `round` in `ROUNDS = (1, 2)` else ValueError. — fetch_plan.py:368-369, 47 [DERIVED]
- in: `upload.url` must fullmatch `_SAFE_URL`, scheme http/https, have hostname, no `#`, length ≤ 2000; `upload.expires_at` must match `_ISO`; else ValueError. — fetch_plan.py:371-376, 75-77 [DERIVED]
- in: each `candidate_id` must fullmatch `[A-Za-z0-9_.:-]{1,64}` and be unique, else ValueError; a missing id becomes `"c<n>"`. — fetch_plan.py:383-387 [DERIVED]
- in round 1: per candidate exactly 5 packets (reddit-1 suffix `"worth it"`, reddit-2 objective `_OBJECTIVE["reddit_2"]` suffix `"recommendations"`, amazon-1 Exa, amazon-2 Jina search with links header, alibaba-1 Exa) plus `ebay-1` only when `not ebay_api`. — fetch_plan.py:155-167 [DERIVED]
- in round 2: `targets` from the parser; only canonical amazon `/dp/<ASIN>` and alibaba `product-detail` URLs (re-validated, alibaba via `_ALIBABA_DETAIL` fullmatch), deduped by `(candidate_id, url)`. — fetch_plan.py:171-179, 78, 196-207 [DERIVED]
- out: `{contract, round, packets: [{packet_id, candidate_id, source, kind, commands: [str], reads, expect}], script, script_sha256, limits: {**LIMITS, with_keys}, how, skipped}`. — fetch_plan.py:419-420, 147-149 [DERIVED]
- post: `script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()`. — fetch_plan.py:401-402 [DERIVED]
- expect sub-dict: `{"tool_class": AR.TOOL_*|"curl", "parse": {"source", "kind"}, "max_bytes": AR.MAX_REPORT_BYTES}`. — fetch_plan.py:149 [DERIVED]

**exa_command** — fetch_plan.py:106-113
- out: `mcporter call ${EXA_API_KEY:+--http-url …} exa.web_search_exa query=<site:domain words suffix> numResults=8 objective=<goal>`, query and objective `shlex.quote`d; query starts with `site:` so no value starts with `@`. — fetch_plan.py:110-113 [DERIVED]

**jina_command** — fetch_plan.py:116-124
- out: `curl -s -g -m <90 | 120> ${JINA_API_KEY:+-H Authorization…} [-H X-With-Links-Summary: true] [-H X-No-Cache: true] [-H X-Timeout: 30] <https://r.jina.ai/url>`; `retry=True` switches curl limit to `JINA_RETRY_TIMEOUT_S` (120) and adds the retry headers; URL `shlex.quote`d. — fetch_plan.py:120-124, 65-66 [DERIVED]

## effect surface
- Postgres/Qdrant: none (FACTS.tables_read / tables_written empty). [DERIVED]
- Module itself performs no I/O; imports `hashlib, re, shlex, unicodedata, typing, urllib.parse` and `polymath_shared.acquisition.agent_reach as AR`. — fetch_plan.py:37-44 [DERIVED]
- Generated script (returned as text, never run here): subprocesses `mcporter` (Exa) and `curl`; network targets `https://r.jina.ai/<url>`, `https://mcp.exa.ai/mcp?exaApiKey=` (only when EXA_API_KEY set), and POST of each output as `text/plain` to the upload URL with `?packet=<id>`. — fetch_plan.py:112, 124, 67, 283 [DERIVED]
- Env flags read by the generated script at run time: `EXA_API_KEY` (default unset → keyless pacing 3 in flight), `JINA_API_KEY` (default unset → 20 reads/min); keys enter only via shell `${VAR:+…}` and are never written into the script or plan. — fetch_plan.py:69-70, 225-226, 18-19 [DERIVED]
- Generated script writes only under a `mktemp` work dir, removed by an EXIT trap. — fetch_plan.py:230-231 [DERIVED]

## invariants
INVARIANT: planned candidates ≤ `MAX_CANDIDATES = 8` — fetch_plan.py:48, 389-391 [DERIVED]
  fails-if: candidate 9+ is silently moved to `skipped` with code `"OVER_LIMIT"`; its data is never fetched.
INVARIANT: round-2 pages per candidate ≤ `ROUND2_PAGES = {"amazon": 3, "alibaba": 3}` — fetch_plan.py:50, 203-204 [DERIVED]
  fails-if: extra targets skipped as `"OVER_LIMIT"`; round 2 under-fetches comparables.
INVARIANT: round-1 packets per candidate = 5 + (1 if not `ebay_api` else 0) — fetch_plan.py:155-167 [DERIVED]
  fails-if: passing `ebay_api=True` without a host Browse API drops all eBay coverage.
INVARIANT: keyless Jina gap = `_jina_gap({"exa_parallel": 3, "jina_per_minute": 20}, 1)` = ceil(60/20) = 3 s; keyed = ceil(60·5/300) = 1 s — fetch_plan.py:326-328, 52-54 [DERIVED]
  fails-if: gap below the limit triggers Jina 429s, which the script records as EMPTY uploads.
INVARIANT: retries per packet = exactly 1, after `RETRY_AFTER_S = {"exa": 5, "jina": 4}` seconds, inside the packet's own pacing slot — fetch_plan.py:61, 291, 300 [DERIVED]
  fails-if: a permanently blocked read yields one EMPTY upload; the round still completes.
INVARIANT: every value from a candidate or page is embedded only through `shlex.quote`; round-2 URLs are regex-validated and rebuilt to canonical form first — fetch_plan.py:21-22, 110-113, 124, 171-179, 345 [DERIVED]
  fails-if: a term like `$(touch /tmp/x)` becomes a command instead of a search word (injection).
INVARIANT: `script_sha256` equals sha256 of the returned `script` bytes; same arguments reproduce both — fetch_plan.py:401-402, 34 [DERIVED]
  fails-if: any nondeterminism breaks the plan's stated byte-for-byte reproducibility and the verify hash.
INVARIANT: search words ≤ `_TERM_CHARS = 120` chars after NFKC, control/bidi removal, `site:` stripping — fetch_plan.py:80, 99-103 [DERIVED]
  fails-if: over-long or control-laden terms leak into shell strings past the quoting contract.

## determinism & idempotency
determinism: DETERMINISTIC — docstring: "no clock, no randomness, no environment" (fetch_plan.py:34); module reads no env and performs no I/O (fetch_plan.py:37-44); env vars affect only the generated script's runtime behavior (fetch_plan.py:225-226). [DERIVED]
idempotency: SAFE — `build` is a pure function of its arguments producing a fresh dict; nothing is persisted or executed. — fetch_plan.py:357-420 [DERIVED]

## failure behaviour
- `build` raises `ValueError` on: bad `report_id` (367), `round` outside `(1, 2)` (369), malformed `upload.url` (374), non-ISO `expires_at` (376), bad `candidate_id` (385), duplicate `candidate_id` (387). No swallowing; nothing is returned on these. — fetch_plan.py:366-387 [DERIVED]
- Bad round-2 targets are not raised but collected into `skipped` with codes `"UNKNOWN_CANDIDATE"`, `"SOURCE_NOT_READ"`, `"NOT_A_PRODUCT_PAGE"`, `"OVER_LIMIT"`; callers see them in the return dict. — fetch_plan.py:190-204, 420 [DERIVED]
- Candidates with no title/search terms are skipped with `"NO_SEARCH_TERMS"`; over-cap candidates with `"OVER_LIMIT"`. — fetch_plan.py:389-394 [DERIVED]
- Generated script: exits 0 even when a site blocks the reader (upload records it); exits 3 only when it cannot run at all (no curl at 228, no temp dir at 230); empty outputs are still uploaded and recorded as EMPTY so the round completes. — fetch_plan.py:228, 230, 278-283, 25-27 [DERIVED]
- Failed-read detection in the script: non-zero exit, Jina cached-snapshot-of-unloaded-page (awk check), size < `AR.READER_MIN_BYTES` (512), or Jina error JSON (`"code": 4xx/5xx` with `"name"`/`"readableMessage"`). — fetch_plan.py:247-258, 30 [DERIVED]

## dumb-code flags
- Docstring says `JINA_API_KEY (500 RPM)` but `LIMITS_WITH_KEYS["jina_per_minute"] = 300` — stated quota and pacing constant disagree by 200. — fetch_plan.py:16, 53 [DERIVED]
- Literal `300` means three things: keyed Jina RPM (53), `_clip` length in `skipped` entries (190, 193, 198), and (with `120`) unrelated timeouts.
- `AR._clip(t.get("url"), 300)` duplicated three times in `_round2` — fetch_plan.py:190, 193, 198 [DERIVED]
- `120` is both `JINA_RETRY_TIMEOUT_S` (66) and `UPLOAD_TIMEOUT_S` (56); also `_TERM_CHARS = 120` (80) — one number, three unrelated meanings.
- `(candidate.get("search_terms") or [])[:10]` caps at 10 terms but `_phrases` consumes at most 2 (first, then first differing of `[*terms[1:], title]`). — fetch_plan.py:140-144 [DERIVED]
- `if not ebay_api` appends the eBay packet — positive flag suppresses the packet; easy to invert when reading `_round1`. — fetch_plan.py:166-167 [DERIVED]

## refactor notes
- `CONTRACT = "product-report-fetch-plan-v1"` flows into the plan dict and the script header; uploads are parsed against it via `agent_reach.parse_report_source` — changing it breaks the round trip. — fetch_plan.py:46, 213-214, 4, 419 [DERIVED]
- Only importer is orchestrator/orchestrator/api/product_report.py (FACTS.importers); changing `build`'s return keys (`packets[].packet_id/candidate_id/source/kind/commands/expect/reads`, `script`, `script_sha256`, `limits`, `how`, `skipped`) or the `how` keys (`run, needs, keys, never, output, then, expires, verify`) requires updating it. — fetch_plan.py:419-420, 405-417 [INFERRED: sole importer must consume the dict]
- `expect.tool_class` selects the script queue (exa vs jina) and `expect.parse = {"source", "kind"}` drives downstream parsing — rename either and dispatch breaks. — fetch_plan.py:345-350, 149 [DERIVED]
- Packet id scheme `r1-c<i>-…` (154) / `r2-c<i>-<source>-<n>` (208) is the upload key `?packet=<id>`; ids are matched back to packets by the host. — fetch_plan.py:154, 208, 283 [DERIVED]
- `_HEAD`/`_TAIL` are `str.format` templates: bash braces are doubled (`{{`) and must stay doubled, and every placeholder name (`min_bytes`, `exa_retry`, `jina_retry`, `upload_timeout`, …) must keep a matching argument in `_script`. — fetch_plan.py:213-323, 331-340 [DERIVED]

## VERIFY
```verify
grep -Fq 'product-report-fetch-plan-v1' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'LIMITS = {"exa_parallel": 3, "jina_per_minute": 20}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'LIMITS_WITH_KEYS = {"exa_parallel": 8, "jina_per_minute": 300}' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'JINA_RETRY_HEADERS = ("X-No-Cache: true", "X-Timeout: 30")' shared/polymath_shared/product_search/fetch_plan.py
grep -Fq 'RETRY_AFTER_S = {"exa": 5, "jina": 4}' shared/polymath_shared/product_search/fetch_plan.py
! grep -Fq 'import subprocess' shared/polymath_shared/product_search/fetch_plan.py
test "$(grep -c -F 'shlex.quote' shared/polymath_shared/product_search/fetch_plan.py)" -ge 6
```
