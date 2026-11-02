# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-975

## purpose
Single source of truth for Polymath's retrieval contract across both MCP servers — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two surfaces cannot drift: the five public retrieval modes, the request body each tool sends, and how each answer is cut down for an agent. Also holds the agent-facing playbook text for product search / supplier / adapter / research tools and the four `product_report_*` tool bodies (PRODUCT-DECISION-REPORT-V1, B5). Pure module: no I/O, no orchestrator import, because Server B runs outside the orchestrator package. [DERIVED] shared/polymath_shared/mcp_retrieval.py:1-22

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RETRIEVAL_MODES / DEFAULT_MODE / MODE_GUIDE | const | tuple of 5 / `"HYBRID"` / dict | shared/polymath_shared/mcp_retrieval.py:34-44 | — |
| normalize_mode | def | (mode: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:86-90 | — |
| mode_error | def | (mode: Any) -> dict | shared/polymath_shared/mcp_retrieval.py:93-95 | — |
| normalize_reasoning | def | (style: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:98-100 | — |
| normalize_depth | def | (depth: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:103-105 | — |
| search_body | def | (query, corpus_id, mode) -> dict | shared/polymath_shared/mcp_retrieval.py:110-114 | — |
| explore_body | def | (query, corpus_id, mode, corpus_explorer) -> dict | shared/polymath_shared/mcp_retrieval.py:117-118 | — |
| answer_body | def | (question, corpus_id, mode, *, reasoning, model, latent) -> dict | shared/polymath_shared/mcp_retrieval.py:121-130 | — |
| compare_body | def | (question, corpus_id, modes) -> dict | shared/polymath_shared/mcp_retrieval.py:133-134 | — |
| deep_body | def | (question, corpus_id, depth, mode, model) -> dict | shared/polymath_shared/mcp_retrieval.py:137-141 | — |
| product_body | def | (message, corpus_id=None, *, geography, model, hypotheses, limit_per_hypothesis) -> dict | shared/polymath_shared/mcp_retrieval.py:144-166 | — |
| parse_body | def | (site, raw_text) -> dict | shared/polymath_shared/mcp_retrieval.py:169-171 | — |
| normalize_report_id | def | (value: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:206-209 | — |
| report_path / report_status_path | def | (report_id, action) -> str | shared/polymath_shared/mcp_retrieval.py:194-203 | — |
| report_start_body | def | (message, corpus_id, *, products, channels, ship_to="US", max_products, upload_base) -> dict | shared/polymath_shared/mcp_retrieval.py:222-250 | — |
| report_compile_body | def | (verdicts: Any) -> dict | shared/polymath_shared/mcp_retrieval.py:253-262 | — |
| report_token_from | def | (answer: Any, report_id=None) -> str \| None | shared/polymath_shared/mcp_retrieval.py:276-291 | — |
| ReportTokens | class | `__init__(cap=256)`, `__len__`, `get(key)`, `headers(key)`, `remember(key, answer, report_id=None)` | shared/polymath_shared/mcp_retrieval.py:294-330 | — |
| shape_report | def | (out: Any) -> Any | shared/polymath_shared/mcp_retrieval.py:333-358 | — |
| default_model | def | (catalog: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:363-373 | — |
| DefaultModel | class | `__init__(ttl_s=300.0, clock=time.monotonic)`, `cached()`, `remember(catalog)` | shared/polymath_shared/mcp_retrieval.py:376-392 | — |
| trim_rows | def | (rows, max_chars=1200) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:397-410 | — |
| shape_wildcard | def | (items: Any) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:418-436 | — |
| shape_search | def | (out: dict, max_evidence: int) -> dict | shared/polymath_shared/mcp_retrieval.py:459-480 | — |
| shape_explore | def | (out: dict) -> dict | shared/polymath_shared/mcp_retrieval.py:483-504 | — |
| trim_hits | def | (items, max_items=12, max_chars=600) -> Any | shared/polymath_shared/mcp_retrieval.py:507-512 | — |
| shape_product | def | (out: dict) -> dict | shared/polymath_shared/mcp_retrieval.py:515-524 | — |
| shape_compare / shape_models / parse_sse / shape_deep | def | per FACTS symbols list | shared/polymath_shared/mcp_retrieval.py:527-632 | — |
| playbook / list_corpora_description | def | (list_tool, add_documents) / (lead) -> str | shared/polymath_shared/mcp_retrieval.py:660-711 | — |

Module imported by (FACTS.importers): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py`.

## contracts

**normalize_mode** — shared/polymath_shared/mcp_retrieval.py:86-90
- in: any value; `str(mode or DEFAULT_MODE).strip().upper()`, then `_ALIASES` lookup (`"VECTOR"` -> `"FAST"`).
- out: one of RETRIEVAL_MODES or None. Post: falsy input yields `"HYBRID"` (DEFAULT_MODE), never None. [DERIVED] (from `mode or DEFAULT_MODE`)

**mode_error** — shared/polymath_shared/mcp_retrieval.py:93-95
- out: `{"error": ..., "status": 422, "modes": dict(MODE_GUIDE)}`.

**search_body** — shared/polymath_shared/mcp_retrieval.py:110-114
- out exactly: `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` — evidence route with query compiler OFF.

**product_body** — shared/polymath_shared/mcp_retrieval.py:144-166
- pre: `hypotheses` items must be dicts; only `title` and `search_terms[]` keys travel; entries without a non-blank title are dropped.
- post: `corpus_id` key omitted when blank (owner R11: agent never guesses the library).

**normalize_report_id** — shared/polymath_shared/mcp_retrieval.py:206-209,185
- post: returns the value only on `REPORT_ID.fullmatch` (`rpt_` + 24 hex); anything else is None, so no other string reaches a route path.

**report_start_body** — shared/polymath_shared/mcp_retrieval.py:222-250
- in: `products` keep `{title, search_terms[]}` only; `channels` trimmed lower-case deduped; `ship_to` upper-cased, defaults `"US"`; `upload_base` only if in `("local", "public")`.
- post: `max_products` sent as int when not None (route caps it at REPORT_MAX_PRODUCTS = 8).

**report_compile_body** — shared/polymath_shared/mcp_retrieval.py:253-262
- out: `{"verdicts": {candidate_id: text}}` with blank keys/values dropped; `{}` when nothing survives. Route bounds each verdict at REPORT_VERDICT_MAX = 1200 chars.

**report_token_from** — shared/polymath_shared/mcp_retrieval.py:276-291
- pre: answer is a dict without `"error"`.
- post: token only from start's `upload_token` or from `upload.url` when `upload.token == "minted"` and the URL's report id matches; returns None for reused / required / expired / none, placeholder or malformed URL. Token must fullmatch `[A-Za-z0-9_-]{43}`.

**ReportTokens** — shared/polymath_shared/mcp_retrieval.py:294-330
- in: `remember(key, answer, report_id=None)` stores a minted token; drops the key when `upload.token == "expired"`.
- post: LRU `OrderedDict`, cap `REPORT_TOKEN_CACHE_MAX` (256), least-recently-used evicted first; guarded by `threading.Lock`; memory only, never written to disk, never logged.

**shape_report** — shared/polymath_shared/mcp_retrieval.py:333-358
- post: a `status == 429` with `error_code == "REPORT_JOB_RUNNING"` is rewritten to one sentence plus `report_id`, `retry_after_s`; `upload.token == "required"` adds an `upload_note` telling the agent to call status again after `upload.mint_after` and never run an older script.

**default_model / DefaultModel** — shared/polymath_shared/mcp_retrieval.py:363-392
- post: picks the `default: true` entry among offered synthesizers, else the first offered; None on error catalog. `remember` only stores when a pick exists (a failed ask is not remembered); `cached()` expires after `ttl_s` = 300.0 s.

**trim_rows / trim_hits** — shared/polymath_shared/mcp_retrieval.py:397-415,507-512
- post (D-02): a row cut at `max_chars` gets `truncated: true` and `full_length` (from `text`, else `text_clean`); rows that fit are unchanged. `trim_hits` caps the list at `max_items` (default 12) and passes non-lists through.

**shape_search** — shared/polymath_shared/mcp_retrieval.py:459-480
- post: chunk rows first (capped at `max(1, int(max_evidence))`), graph facts after (capped at GRAPH_FACTS_MAX = 20); `graph_facts` reports the length of the capped list; `wildcard` lane added only when non-empty; error answers pass through unchanged.

**shape_explore** — shared/polymath_shared/mcp_retrieval.py:483-504
- post: keeps `evidence_packet`, executed mode, graph facts (≤ 20), wildcard; drops the runtime's full retrieval inventory and phase list (diagnostics, tens of KB).

**shape_product** — shared/polymath_shared/mcp_retrieval.py:515-524
- post: passes everything through with only the bulky evidence lists (`evidence`, `chunks`, `bundle`) cut down via `trim_hits`.

## effect surface
- Postgres tables: none read, none written (FACTS.tables_read / tables_written empty).
- Qdrant collections: none (module is pure, shared/polymath_shared/mcp_retrieval.py:22).
- Network / subprocess / files / env flags: none in this module. Route paths and Agent Reach commands exist only as string constants: `"/product/report/start"`, `"/product/reports"` (shared/polymath_shared/mcp_retrieval.py:186-187), `"agent-reach doctor --json"` (shared/polymath_shared/mcp_retrieval.py:76).
- In-memory state only: `ReportTokens` (token cache, shared/polymath_shared/mcp_retrieval.py:294-330) and `DefaultModel` (model-id cache, shared/polymath_shared/mcp_retrieval.py:376-392).

## invariants
INVARIANT: RETRIEVAL_MODES has exactly 5 members ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN") — shared/polymath_shared/mcp_retrieval.py:34 [DERIVED]
  fails-if: normalize_mode accepts/rejects a different mode set on the two servers.
INVARIANT: REPORT_MAX_PRODUCTS (8) >= REPORT_DEFAULT_PRODUCTS (5) — shared/polymath_shared/mcp_retrieval.py:177-178 [DERIVED]
  fails-if: the default body would ask the route for more products than its cap.
INVARIANT: a report id matches `rpt_[0-9a-f]{24}` (REPORT_ID.fullmatch) — shared/polymath_shared/mcp_retrieval.py:185,206-209 [DERIVED]
  fails-if: an arbitrary agent string becomes part of a route path.
INVARIANT: upload token length == 43 (`[A-Za-z0-9_-]{43}`, `secrets.token_urlsafe(32)`) — shared/polymath_shared/mcp_retrieval.py:272 [DERIVED]
  fails-if: report_token_from keeps a placeholder or truncated token as live.
INVARIANT: len(ReportTokens) <= REPORT_TOKEN_CACHE_MAX (256) after remember — shared/polymath_shared/mcp_retrieval.py:271,301,327-328 [DERIVED]
  fails-if: a status loop grows the cache unboundedly across reports.
INVARIANT: wildcard lane length <= WILDCARD_MAX (8), excerpt <= WILDCARD_TEXT (600) — shared/polymath_shared/mcp_retrieval.py:61-62,418-430 [DERIVED]
  fails-if: agent-facing answers balloon with the full wildcard lane.
INVARIANT: graph facts kept <= GRAPH_FACTS_MAX (20) in shape_search and shape_explore — shared/polymath_shared/mcp_retrieval.py:63,465-466,492 [DERIVED]
  fails-if: GRAPH answers carry unbounded fact lists.
INVARIANT: answer evidence list <= ANSWER_HITS (12) items, each text <= ANSWER_HIT_TEXT (600) chars — shared/polymath_shared/mcp_retrieval.py:66-67,507-512 [DERIVED]
  fails-if: polymath_answer-sized evidence reaches the agent uncapped.
INVARIANT: DefaultModel cache lifetime < DEFAULT_MODEL_TTL_S (300.0 s) — shared/polymath_shared/mcp_retrieval.py:71,376-386 [DERIVED]
  fails-if: a synthesizer key added in Settings stays invisible to tools for longer than 5 minutes.
INVARIANT: `_executed_mode` maps internal "VECTOR" to public "FAST" for display — shared/polymath_shared/mcp_retrieval.py:45,439-442 [DERIVED]
  fails-if: the agent sees a mode name that is not in RETRIEVAL_MODES.

## determinism & idempotency
determinism: DETERMINISTIC for all body/shaping/normalize functions (pure module, no I/O — shared/polymath_shared/mcp_retrieval.py:22); NONDETERMINISTIC only in the two caches: DefaultModel reads a clock (`time.monotonic`, shared/polymath_shared/mcp_retrieval.py:380) and ReportTokens is concurrent (`threading.Lock`, shared/polymath_shared/mcp_retrieval.py:304).
idempotency: SAFE — every function is a pure mapping of its input; caches mutate only their own in-memory state and `remember` is convergent (same answer -> same held token).

## failure behaviour
FACTS.fallbacks is empty; no broad try/except visible in SOURCE. Failure surfaces as values, not exceptions:
- `normalize_mode` / `normalize_reasoning` / `normalize_depth` return None on unknown input — shared/polymath_shared/mcp_retrieval.py:86-105.
- `mode_error` returns `{"error": ..., "status": 422, "modes": dict(MODE_GUIDE)}` — shared/polymath_shared/mcp_retrieval.py:93-95.
- `report_id_error` returns `{"error": "REPORT_ID_INVALID: ...", "status": 422}` — shared/polymath_shared/mcp_retrieval.py:212-214.
- `shape_report` rewrites a 429 `REPORT_JOB_RUNNING` into one sentence naming the report and the wait — shared/polymath_shared/mcp_retrieval.py:342-349.
- `default_model` returns None when the catalog is not a dict or carries `"error"` — shared/polymath_shared/mcp_retrieval.py:368-369.
- Every shape_* passes an `"error"` answer through unchanged — shared/polymath_shared/mcp_retrieval.py:462,486,518.

## dumb-code flags
- `MAX_TEXT = 1200` (shared/polymath_shared/mcp_retrieval.py:60) and `REPORT_VERDICT_MAX = 1200` (shared/polymath_shared/mcp_retrieval.py:179): same number, two unrelated meanings — a change to one must not drag the other.
- `WILDCARD_TEXT = 600` (shared/polymath_shared/mcp_retrieval.py:62) and `ANSWER_HIT_TEXT = 600` (shared/polymath_shared/mcp_retrieval.py:67): duplicated literal, no shared constant.
- `shape_search` docstring says "`graph_facts` stays the count it always was" while the code reports `len(facts)` after the GRAPH_FACTS_MAX cap — shared/polymath_shared/mcp_retrieval.py:460-470. [INFERRED] docstring counts the uncapped list; the value can differ when more than 20 facts were returned.
- `normalize_mode("")` returns `"HYBRID"` rather than None because of `str(mode or DEFAULT_MODE)` — shared/polymath_shared/mcp_retrieval.py:88. [INFERRED] empty-string mode silently becomes the default instead of an error.
- `DEFAULT_MODE = "HYBRID"` here matches the module comment tying it to the app's exposed modes; the frozen LEGACY lane is reachable only via the alias path, not via this module — shared/polymath_shared/mcp_retrieval.py:8,35,45. [INFERRED] LEGACY deliberately absent from RETRIEVAL_MODES.

## refactor notes
- RETRIEVAL_MODES / DEFAULT_MODE / MODE_GUIDE / _ALIASES are the contract both MCP servers describe to agents; renaming a mode or dropping the `"VECTOR"` alias changes every agent-visible description at once — shared/polymath_shared/mcp_retrieval.py:34-45. Importers: `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules` (FACTS.importers).
- Body builders must keep their exact key sets (`compiler: "off"`, `corpus_explorer: False`, `evidence: True` in search_body — shared/polymath_shared/mcp_retrieval.py:113-114); routes filter on these keys and a missing key re-routes to the frozen LEGACY lane the app no longer uses (shared/polymath_shared/mcp_retrieval.py:7-8).
- `report_start_body` / `report_compile_body` strip every key the route does not know (`products` keep only `{title, search_terms[]}`); widening them leaks agent-invented keys into `/product/report/*` — shared/polymath_shared/mcp_retrieval.py:225-229,253-262.
- ReportTokens must stay memory-only and lock-guarded; the LRU cap and the `expired` drop exist because a status loop minted tokens until it broke the running script (review R3 #2) — shared/polymath_shared/mcp_retrieval.py:294-299.
- Module must stay free of orchestrator imports (Server B runs outside the package) — shared/polymath_shared/mcp_retrieval.py:22.
- `HIDDEN_TOOLS_A` / `HIDDEN_TOOLS_B` keep old tool names callable but hidden from tools/list; removing them breaks old callers — shared/polymath_shared/mcp_retrieval.py:56-58.

## VERIFY
```verify
grep -Fq 'RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'rpt_[0-9a-f]{24}' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'REPORT_TOKEN_HEADER = "X-Upload-Token"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '_ALIASES = {"VECTOR": "FAST"}' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'def shape_' shared/polymath_shared/mcp_retrieval.py)" -ge 8
! grep -Fq 'import requests' shared/polymath_shared/mcp_retrieval.py
```
