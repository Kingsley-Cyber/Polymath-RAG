# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-977

## purpose
- One module describes Polymath's retrieval for both MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two cannot drift — mcp_retrieval.py:3-5 [DERIVED]
- Holds the five public retrieval modes, the request body each tool sends, how each answer is cut down for an agent, the product-decision-report helpers, and the playbook text both servers tell agents — mcp_retrieval.py:6-21 [DERIVED]
- Pure module: "no I/O and no orchestrator import (Server B runs outside the orchestrator package)" — mcp_retrieval.py:22 [DERIVED]

## public surface
Module importers (FACTS.importers): `mcp_server/polymath_mcp.py`; `orchestrator/orchestrator/api/_small-modules`; `orchestrator/orchestrator/mcp_server.py`. Per-symbol use is not in FACTS.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| mode_lines | def | () -> str | mcp_retrieval.py:82-83 | importers† |
| normalize_mode | def | (mode) -> str \| None | mcp_retrieval.py:86-90 | importers† |
| mode_error | def | (mode) -> dict | mcp_retrieval.py:93-95 | importers† |
| normalize_reasoning | def | (style) -> str \| None | mcp_retrieval.py:98-100 | importers† |
| normalize_depth | def | (depth) -> str \| None | mcp_retrieval.py:103-105 | importers† |
| search_body | def | (query, corpus_id, mode) -> dict | mcp_retrieval.py:110-114 | importers† |
| explore_body | def | (query, corpus_id, mode, corpus_explorer) -> dict | mcp_retrieval.py:117-118 | importers† |
| answer_body | def | (question, corpus_id, mode, *, reasoning, model, latent) -> dict | mcp_retrieval.py:121-130 | importers† |
| compare_body | def | (question, corpus_id, modes) -> dict | mcp_retrieval.py:133-134 | importers† |
| deep_body | def | (question, corpus_id, depth, mode, model) -> dict | mcp_retrieval.py:137-141 | importers† |
| product_body | def | (message, corpus_id, *, geography, model, hypotheses, limit_per_hypothesis) -> dict | mcp_retrieval.py:144-166 | importers† |
| parse_body | def | (site, raw_text) -> dict | mcp_retrieval.py:169-171 | importers† |
| report_path | def | (report_id, action) -> str | mcp_retrieval.py:194-196 | importers† |
| report_status_path | def | (report_id, upload_base) -> str | mcp_retrieval.py:199-203 | importers† |
| normalize_report_id | def | (value) -> str \| None | mcp_retrieval.py:206-209 | importers† |
| report_id_error | def | (value) -> dict | mcp_retrieval.py:212-214 | importers† |
| report_start_body | def | (message, corpus_id, *, products, channels, ship_to="US", max_products, upload_base) -> dict | mcp_retrieval.py:222-250 | importers† |
| report_compile_body | def | (verdicts) -> dict | mcp_retrieval.py:253-262 | importers† |
| report_token_from | def | (answer, report_id) -> str \| None | mcp_retrieval.py:276-291 | importers† |
| ReportTokens | class | methods: `__init__`, `__len__`, `get`, `headers`, `remember` | mcp_retrieval.py:294-330 | importers† |
| shape_report | def | (out) -> Any | mcp_retrieval.py:333-358 | importers† |
| default_model | def | (catalog) -> str \| None | mcp_retrieval.py:363-373 | importers† |
| DefaultModel | class | methods: `__init__`, `cached`, `remember` | mcp_retrieval.py:376-392 | importers† |
| trim_rows | def | (rows, max_chars=1200) -> list[dict] | mcp_retrieval.py:397-410 | importers† |
| shape_wildcard | def | (items) -> list[dict] | mcp_retrieval.py:418-436 | importers† |
| shape_search | def | (out, max_evidence) -> dict | mcp_retrieval.py:459-482 | importers† |
| shape_explore | def | (out) -> dict | mcp_retrieval.py:485-506 | importers† |
| trim_hits | def | (items, max_items=12, max_chars=600) -> Any | mcp_retrieval.py:509-514 | importers† |
| shape_product | def | (out) -> dict | mcp_retrieval.py:517-526 | importers† |
| shape_compare | def | (out, max_rows) -> dict | mcp_retrieval.py:529-555 | importers† |
| shape_models | def | (out) -> dict | mcp_retrieval.py:558-564 | importers† |
| parse_sse | def | (lines) -> ? | mcp_retrieval.py:569-591 | importers† |
| shape_deep | def | (events, depth, mode) -> ? | mcp_retrieval.py:594-634 | importers† |
| playbook | def | (list_tool, add_documents) -> ? | mcp_retrieval.py:662-709 | importers† |
| list_corpora_description | def | (lead) -> ? | mcp_retrieval.py:712-713 | importers† |

† one of the three module importers above; FACTS gives no per-symbol split.

## contracts

### normalize_mode — mcp_retrieval.py:86-90
- in: `mode: Any`; empty/None falls back to `DEFAULT_MODE` = `"HYBRID"` (:35, :88) — [DERIVED]
- out: canonical name in `RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")` (:34, :90); alias `"VECTOR"` → `"FAST"` (:45, :89); else `None` — [DERIVED]
- post: return value ∈ RETRIEVAL_MODES or None — :89-90 [DERIVED]

### search_body — mcp_retrieval.py:110-114
- out: exactly `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` — :113-114 [DERIVED]
- post: compiler off + evidence on = the chat runtime's evidence route with no planning — :111-112 [DERIVED]

### explore_body / answer_body / compare_body / deep_body — mcp_retrieval.py:117-141
- explore_body out: `{"message", "corpus_id", "mode", "corpus_explorer": bool}` — :118 [DERIVED]
- answer_body out: `{"message","corpus_id","mode"}`; adds `reasoning` only when != `"none"`, `synthesizer` when model named, `latent` as bool — :123-129 [DERIVED]
- deep_body out: `{"question","corpus_id","preset": depth,"mode"}` + optional `synthesizer` — :138-140 [DERIVED]

### product_body — mcp_retrieval.py:144-166
- pre: `corpus_id` optional; absent = orchestrator searches every authorized library (owner rule R11) — :146-147 [DERIVED]
- post: `hypotheses` keep only `{title, search_terms[]}`; entries without a title are dropped — :158-161 [DERIVED]

### normalize_report_id — mcp_retrieval.py:206-209
- pre: value is matched with `REPORT_ID = re.compile(r"rpt_[0-9a-f]{24}")` fullmatch — :185, :209 [DERIVED]
- post: returns the id or `None`; nothing else ever reaches a route path — :207-209 [DERIVED]

### report_status_path — mcp_retrieval.py:199-203
- post: `?upload_base=` appended only when value ∈ `REPORT_UPLOAD_BASES = ("local", "public")` — :191, :202-203 [DERIVED]

### report_start_body — mcp_retrieval.py:222-250
- in: `ship_to` defaults to `"US"`, upper-cased — :223, :245 [DERIVED]
- post: `products` keep `{title, search_terms}` only (:237-239); `channels` lower-case, de-duplicated via `dict.fromkeys` (:245); `max_products` sent as int, default `REPORT_DEFAULT_PRODUCTS = 5` (:177, :222) — [DERIVED]
- pre: `upload_base` is the server's own decision, never the agent's — :227-228, :248-249 [DERIVED]

### report_compile_body — mcp_retrieval.py:253-262
- in: `verdicts` = {candidate_id: text}; blank keys/values dropped — :258-261 [DERIVED]
- post: `{"verdicts": kept}` or `{}` when nothing survives — :262 [DERIVED]

### report_token_from — mcp_retrieval.py:276-291
- pre: answer must be a dict without `"error"` — :280-281 [DERIVED]
- out: `answer["upload_token"]` when it matches `[A-Za-z0-9_-]{43}` (:272, :282-284); else the token inside `upload.url` only when `upload.token == "minted"` and the URL names this report (:285-291, regex :273); else `None` — [DERIVED]

### ReportTokens — mcp_retrieval.py:294-330
- in: `remember(key, answer, report_id)` stores what `report_token_from` finds; on `upload.token == "expired"` the key is forgotten — :322, :329-330 [DERIVED]
- post: `headers(key)` returns `{REPORT_TOKEN_HEADER: token}` (`"X-Upload-Token"`, :270) or `{}` — :316-318 [DERIVED]
- post: at most `REPORT_TOKEN_CACHE_MAX = 256` reports; least recently used dropped first — :271, :327-328 [DERIVED]

### shape_report — mcp_retrieval.py:333-358
- in: any report-route answer; everything passes through unchanged, `next` included — :334-337, :358 [DERIVED]
- post: 429 + `error_code == "REPORT_JOB_RUNNING"` becomes one sentence naming the report and the wait — :342-349 [DERIVED]
- post: `upload.token == "required"` adds `upload_note` (call status again after `mint_after`) — :350-357 [DERIVED]

### default_model / DefaultModel — mcp_retrieval.py:363-392
- in: /synthesizers catalog; `None` when it is not a dict or carries `"error"` — :368-369 [DERIVED]
- post: picks the entry with `default is True`, else the first offered; `DefaultModel` remembers it for `DEFAULT_MODEL_TTL_S = 300.0`; a failed pick is not remembered — :71, :370-372, :388-391 [DERIVED]

### trim_rows — mcp_retrieval.py:397-410
- post: `text` / `text_clean` cut at `max_chars` (default `MAX_TEXT = 1200`); a cut row gains `truncated: true` + `full_length` (untrimmed `text`, else `text_clean`, in characters) — :60, :403-408 [DERIVED]
- post: input rows are copied (`dict(r)`), never mutated — :402 [DERIVED]

### shape_search — mcp_retrieval.py:459-482
- in: `out` from the evidence route; an `"error"` answer returns unchanged — :462-463 [DERIVED]
- post: chunk rows first (capped `max(1, int(max_evidence))`), graph facts after (capped `GRAPH_FACTS_MAX = 20`); `"graph_facts"` stays the **count** — :63, :465-470 [DERIVED]
- post: passes `evidence_rows_error`, `evidence_relevance`, `latency_ms`, `scope`, `degraded`, and product keys (`product_research`, `agent_steps`) when present — :476-481, :450-456, :69 [DERIVED]

### shape_explore — mcp_retrieval.py:485-506
- post: EvidencePacket passes whole; `"graph_facts"` is the **list** (capped 20); wildcard lane via `shape_wildcard`; `latency_ms` / `scope` / `degraded` pass when present — :490-505 [DERIVED]

### trim_hits — mcp_retrieval.py:509-514
- post: at most `ANSWER_HITS = 12` items, each cut at `ANSWER_HIT_TEXT = 600`; non-list input passes through — :66-67, :512-514 [DERIVED]

### parse_sse / shape_deep / playbook — mcp_retrieval.py:569-591, 594-634, 662-709
- parse_sse yields `(event, data)` per SSE frame; keep-alive comments and malformed frames skipped (FACTS doc) — mcp_retrieval.py:569-591 [DERIVED]
- shape_deep builds polymath_deep_research's answer from the stream: cited report, citations, coverage, counts (FACTS doc) — mcp_retrieval.py:594-634 [DERIVED]
- playbook(list_tool, add_documents) returns the ordered server instructions; the two params name each server's own tools (FACTS doc) — mcp_retrieval.py:662-709 [DERIVED]

## effect surface
- Postgres: none — FACTS `tables_read` and `tables_written` are both empty [DERIVED]
- Files / network / subprocess / env flags: none; module docstring declares "Pure: no I/O and no orchestrator import" and imports are stdlib only (`json`, `re`, `threading`, `time`, `collections`, `typing`) — mcp_retrieval.py:22, 25-31 [DERIVED]
- In-memory state only: `ReportTokens._held` (OrderedDict + `threading.Lock`) — mcp_retrieval.py:303-304; `DefaultModel._id` / `_at` — mcp_retrieval.py:382-383 [DERIVED]
- Route targets named (built here, called by the servers, not here): the chat evidence route — mcp_retrieval.py:111-112; `/product/search` — :146; `/supplier/parse` — :170; `/product/report/start`, `/product/reports`, `/product/report/{id}/{action}` — :186-187, :194-196; `/synthesizers` — :364. Per-route waits in `REPORT_TIMEOUT_S = {"start": 60.0, "status": 30.0, "compile": 120.0, "list": 30.0}` — :182 [DERIVED]

## invariants
INVARIANT: DEFAULT_MODE == "HYBRID" and "HYBRID" ∈ RETRIEVAL_MODES — mcp_retrieval.py:34-35 [DERIVED]
  fails-if: normalize_mode on an empty mode returns a name no route accepts.
INVARIANT: every normalize_mode return ∈ RETRIEVAL_MODES ∪ {None}; only alias is "VECTOR" → "FAST" — mcp_retrieval.py:34, 45, 89-90 [DERIVED]
  fails-if: a legacy "VECTOR" caller gets 422 instead of FAST.
INVARIANT: REPORT_ID pattern == "rpt_" + exactly 24 hex chars, fullmatch — mcp_retrieval.py:185, 209 [DERIVED]
  fails-if: ids the route minted get rejected by normalize_report_id → 422.
INVARIANT: accepted upload token length == 43 chars of [A-Za-z0-9_-] — mcp_retrieval.py:272, 283 [DERIVED]
  fails-if: report_token_from discards valid tokens, status loops re-mint links.
INVARIANT: len(ReportTokens) <= REPORT_TOKEN_CACHE_MAX == 256 after every remember — mcp_retrieval.py:271, 327-328 [DERIVED]
  fails-if: unbounded growth; >256 live reports silently drop the LRU token.
INVARIANT: search kept chunk rows >= 1 even when max_evidence <= 0 (`max(1, int(max_evidence))`) — mcp_retrieval.py:465 [DERIVED]
  fails-if: a caller passing 0 for "no rows" still receives 1 row.
INVARIANT: graph_fact rows kept <= GRAPH_FACTS_MAX == 20 on both search and explore — mcp_retrieval.py:63, 466, 494 [DERIVED]
  fails-if: oversized fact lists reach the agent context.
INVARIANT: wildcard items <= WILDCARD_MAX == 8, excerpt <= WILDCARD_TEXT == 600 — mcp_retrieval.py:61-62, 420, 426 [DERIVED]
  fails-if: wildcard lane outweighs the evidence it must never displace (:41-42).
INVARIANT: answer hits <= ANSWER_HITS == 12, each <= ANSWER_HIT_TEXT == 600 — mcp_retrieval.py:66-67, 509-514 [DERIVED]
INVARIANT: `ship_to` in report_start_body is upper-case, default "US" — mcp_retrieval.py:223, 245 [DERIVED]
INVARIANT: _executed_mode maps runtime stamp "VECTOR" back to "FAST" — mcp_retrieval.py:439-442 [DERIVED]
  fails-if: agents see an internal mode name absent from RETRIEVAL_MODES.

## determinism & idempotency
determinism: DETERMINISTIC — pure functions of their args; stdlib imports only, no random/uuid/network/db/env — mcp_retrieval.py:22, 25-31 [DERIVED]. Exceptions: DefaultModel reads a clock (default `time.monotonic`, injectable) — mcp_retrieval.py:380, 386 [DERIVED]; ReportTokens LRU order depends on call sequence under a `threading.Lock` — mcp_retrieval.py:304, 327-328 [DERIVED]
idempotency: SAFE — body builders are pure; `trim_rows` copies each row (`dict(r)`) and `shape_report` builds a new dict (`{**out, ...}`), inputs are not mutated — mcp_retrieval.py:354, 402 [DERIVED]

## failure behaviour
- FACTS carries no `fallbacks`; no try/except appears in SOURCE lines 1-520 — [DERIVED]
- mode_error: `{"error": ..., "status": 422, "modes": dict(MODE_GUIDE)}` — mcp_retrieval.py:93-95 [DERIVED]
- report_id_error: `{"error": "REPORT_ID_INVALID: ...", "status": 422}` — mcp_retrieval.py:212-214 [DERIVED]
- shape_search / shape_explore return an `"error"` answer unchanged — mcp_retrieval.py:462-463, 488-489; shape_product returns non-dict or `"error"` input as-is — :519-520 [DERIVED]
- shape_report rewrites 429 REPORT_JOB_RUNNING into one actionable sentence (keeps `status: 429`, `report_id`, `retry_after_s`) — mcp_retrieval.py:342-349 [DERIVED]
- default_model returns None on an errored/unavailable catalog; DefaultModel does not remember a failed pick — mcp_retrieval.py:368-369, 388-391 [DERIVED]
- report_token_from returns None on error answers, non-"minted" states, placeholder or malformed URLs — mcp_retrieval.py:280-291 [DERIVED]

## dumb-code flags
- `1200` used twice with different meanings: `MAX_TEXT` (evidence row text, :60) and `REPORT_VERDICT_MAX` (verdict characters, route-enforced, :179) — [DERIVED]
- `600` used twice: `WILDCARD_TEXT` (:62) and `ANSWER_HIT_TEXT` (:67) — [DERIVED]
- Same key, two types: `"graph_facts"` is a count in shape_search (:470) but a list in shape_explore (:494-496) — [DERIVED]
- REPORT_ID regex duplicates `report_store.REPORT_ID_RE`, `_UPLOAD_TOKEN` duplicates `report_store.TOKEN_RE` (comments name the source of each copy) — mcp_retrieval.py:183-185, 272 [DERIVED]
- Alias "VECTOR" is handled on both directions in two places that must stay symmetric: input `_ALIASES` (:45, :89) and output `_executed_mode` (:439-442) — [DERIVED]
- Paragraph-length prose constants live in code: `CORPUS_FLAGS` (:644), `NO_TERMINAL` (:652), `_CJ_HOST` (:745), `ADAPTER_START` (:810), `RESEARCH_ACQUIRE` (:839), `PRODUCT_REPORT_LIST` (:973); agent-facing wording changes are code changes — [DERIVED]
- `COMPARE_ROWS = 6` (:64) sits beside `shape_compare(out, max_rows)` (:529); the link is plausible but not visible in the shown source — [INFERRED] (name and neighbourhood only)

## refactor notes
- Do not add an orchestrator import: Server B runs outside the orchestrator package — mcp_retrieval.py:22 [DERIVED]; breaks `mcp_server/polymath_mcp.py` (FACTS.importers)
- Any change to a body key or a route path changes the wire contract with `/retrieve`, `/product/search`, `/product/report/*` for BOTH servers at once — mcp_retrieval.py:3-5, 110-141, 144-171, 186-250 [DERIVED]
- `RETRIEVAL_MODES` (:33), `REASONING_STYLES` (:47) and `PRODUCT_REASON_STEPS` (:78-79) are "pinned by tests" per their comments — [DERIVED]
- Report protocol constants — states (:269), header `"X-Upload-Token"` (:270), cache max (:271), URL regex (:273) — mirror `report_store`; both sides must change together — mcp_retrieval.py:183-185, 269-273 [DERIVED]
- `MODE_GUIDE` text (:36-44) is what both servers tell agents about each mode; wording changes alter agent tool choice on both surfaces — mcp_retrieval.py:11-15 [DERIVED]
- Blast radius for any signature change: the three importers in FACTS.importers [DERIVED]

## VERIFY
```verify
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'rpt_[0-9a-f]{24}' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"compiler": "off"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'REPORT_TOKEN_HEADER = "X-Upload-Token"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"VECTOR": "FAST"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODEL_TTL_S = 300.0' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'polymath_search' shared/polymath_shared/mcp_retrieval.py)" -ge 2
```
