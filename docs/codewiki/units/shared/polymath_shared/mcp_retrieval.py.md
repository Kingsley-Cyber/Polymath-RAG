# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-953

## purpose
The single description of Polymath's retrieval shared by BOTH MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two cannot drift: the five public retrieval modes, the request body each tool sends, and how each answer is cut down for an agent — shared/polymath_shared/mcp_retrieval.py:1-22 [DERIVED]. Also holds the product decision-report tooling (PRODUCT-DECISION-REPORT-V1): report request bodies, timeouts, and the upload-token cache — shared/polymath_shared/mcp_retrieval.py:17-20 [DERIVED]. Pure: no I/O and no orchestrator import (Server B runs outside the orchestrator package) — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED].

## public surface
Module importers (FACTS.importers, module-level; per-symbol split not in FACTS): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py`.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RETRIEVAL_MODES | const | ("FAST","HYBRID","GRAPH","WILDCARD","GNN") | shared/polymath_shared/mcp_retrieval.py:34 | importers |
| DEFAULT_MODE | const | "HYBRID" | shared/polymath_shared/mcp_retrieval.py:35 | importers |
| MODE_GUIDE | const | dict mode -> one-line guide | shared/polymath_shared/mcp_retrieval.py:36-44 | importers |
| HIDDEN_TOOLS_A / HIDDEN_TOOLS_B | const | frozensets of legacy tool names hidden from tools/list | shared/polymath_shared/mcp_retrieval.py:57-58 | importers |
| mode_lines | def | () -> str | shared/polymath_shared/mcp_retrieval.py:82-83 | importers |
| normalize_mode | def | (mode) -> str or None | shared/polymath_shared/mcp_retrieval.py:86-90 | importers |
| mode_error | def | (mode) -> dict | shared/polymath_shared/mcp_retrieval.py:93-95 | importers |
| normalize_reasoning | def | (style) -> str or None | shared/polymath_shared/mcp_retrieval.py:98-100 | importers |
| normalize_depth | def | (depth) -> str or None | shared/polymath_shared/mcp_retrieval.py:103-105 | importers |
| search_body | def | (query, corpus_id, mode) -> dict | shared/polymath_shared/mcp_retrieval.py:110-114 | importers |
| explore_body | def | (query, corpus_id, mode, corpus_explorer) -> dict | shared/polymath_shared/mcp_retrieval.py:117-118 | importers |
| answer_body | def | (question, corpus_id, mode, *, reasoning=None, model=None, latent=None) -> dict | shared/polymath_shared/mcp_retrieval.py:121-130 | importers |
| compare_body | def | (question, corpus_id, modes) -> dict | shared/polymath_shared/mcp_retrieval.py:133-134 | importers |
| deep_body | def | (question, corpus_id, depth, mode, model=None) -> dict | shared/polymath_shared/mcp_retrieval.py:137-141 | importers |
| product_body | def | (message, corpus_id=None, *, geography=None, model=None, hypotheses=None, limit_per_hypothesis=None) -> dict | shared/polymath_shared/mcp_retrieval.py:144-166 | importers |
| parse_body | def | (site, raw_text) -> dict | shared/polymath_shared/mcp_retrieval.py:169-171 | importers |
| report_path | def | (report_id, action) -> str | shared/polymath_shared/mcp_retrieval.py:194-196 | importers |
| report_status_path | def | (report_id, upload_base=None) -> str | shared/polymath_shared/mcp_retrieval.py:199-203 | importers |
| normalize_report_id | def | (value) -> str or None | shared/polymath_shared/mcp_retrieval.py:206-209 | importers |
| report_id_error | def | (value) -> dict | shared/polymath_shared/mcp_retrieval.py:212-214 | importers |
| report_start_body | def | (message=None, corpus_id=None, *, products=None, channels=None, ship_to="US", max_products=5, upload_base=None) -> dict | shared/polymath_shared/mcp_retrieval.py:222-250 | importers |
| report_compile_body | def | (verdicts=None) -> dict | shared/polymath_shared/mcp_retrieval.py:253-262 | importers |
| report_token_from | def | (answer, report_id=None) -> str or None | shared/polymath_shared/mcp_retrieval.py:276-291 | importers |
| ReportTokens | class | LRU token cache; `__init__(cap=256)`, `__len__`, `get(key)`, `headers(key)`, `remember(key, answer, report_id=None)` | shared/polymath_shared/mcp_retrieval.py:294-330 | importers |
| shape_report | def | (out) -> Any | shared/polymath_shared/mcp_retrieval.py:333-358 | importers |
| default_model | def | (catalog) -> str or None | shared/polymath_shared/mcp_retrieval.py:363-373 | importers |
| DefaultModel | class | `__init__(ttl_s=300.0, clock=time.monotonic)`, `cached()`, `remember(catalog)` | shared/polymath_shared/mcp_retrieval.py:376-392 | importers |
| trim_rows | def | (rows, max_chars=1200) -> list of dict | shared/polymath_shared/mcp_retrieval.py:397-410 | importers |
| shape_wildcard | def | (items) -> list of dict | shared/polymath_shared/mcp_retrieval.py:418-436 | importers |
| shape_search | def | (out, max_evidence) -> dict | shared/polymath_shared/mcp_retrieval.py:459-480 | importers |
| shape_explore | def | (out) -> dict | shared/polymath_shared/mcp_retrieval.py:483-504 | importers |
| trim_hits | def | (items, max_items=12, max_chars=600) -> Any | shared/polymath_shared/mcp_retrieval.py:507-512 | importers |
| shape_product | def | (out) -> dict | shared/polymath_shared/mcp_retrieval.py:515-524 | importers |
| shape_compare | def | (out, max_rows=6) -> dict | shared/polymath_shared/mcp_retrieval.py:527-553 | importers |
| parse_sse | def | (lines) -> (event, data) frames | shared/polymath_shared/mcp_retrieval.py:567-589 | importers |
| shape_deep | def | (events, depth, mode) -> shaped deep-research answer | shared/polymath_shared/mcp_retrieval.py:592-632 | importers |
| playbook | def | (list_tool, add_documents) -> str | shared/polymath_shared/mcp_retrieval.py:660-704 | importers |
| list_corpora_description | def | (lead) -> str | shared/polymath_shared/mcp_retrieval.py:707-708 | importers |

Private helpers: `_terms` :217-219, `_clip` :413-415, `_executed_mode` :439-442, `_degraded` :445-447, `_keep_product` :450-456.

## contracts

**normalize_mode** — shared/polymath_shared/mcp_retrieval.py:86-90 [DERIVED]
- in: any mode value; empty/None falls back to `DEFAULT_MODE` "HYBRID" (:88, :35).
- out: canonical upper-case mode name, or None when not one of the five.
- post: alias `VECTOR` mapped to `FAST` via `_ALIASES` (:89, :45).

**search_body** — shared/polymath_shared/mcp_retrieval.py:110-114 [DERIVED]
- out keys: `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` (:113-114).
- post: query compiler OFF, `evidence` on → answer carries RETRIEVE-EVIDENCE-ROWS-V1 rows (:111-112).

**product_body** — shared/polymath_shared/mcp_retrieval.py:144-166 [DERIVED]
- pre: omitted `corpus_id` = orchestrator searches every library the caller may use (ALL_AUTHORIZED) (:146-147).
- post: `hypotheses` reduced to `[{title, search_terms[]}]` — only those two keys travel (:148-149, :158-163).

**normalize_report_id** — shared/polymath_shared/mcp_retrieval.py:206-209 [DERIVED]
- post: `REPORT_ID.fullmatch` on `rpt_[0-9a-f]{24}` else None; nothing else ever reaches a route path (:185, :207, :209).

**report_start_body** — shared/polymath_shared/mcp_retrieval.py:222-250 [DERIVED]
- defaults: `ship_to="US"` (:223, :245), `max_products=REPORT_DEFAULT_PRODUCTS` (5) (:224, :177).
- post: products keep `{title, search_terms[]}` (:225, :237-239); channels lower-cased, de-duped, order kept (:242-244); `upload_base` included only when in `("local", "public")` (:248-249, :191).

**report_compile_body** — shared/polymath_shared/mcp_retrieval.py:253-262 [DERIVED]
- in: `verdicts` = {candidate_id: short verdict}.
- post: blank keys/values dropped (:256-261); no kept verdicts → `{}` (:262); route bounds each verdict at `REPORT_VERDICT_MAX` = 1200 chars (:179, :255).

**report_token_from** — shared/polymath_shared/mcp_retrieval.py:276-291 [DERIVED]
- out: token from `answer["upload_token"]` matching `[A-Za-z0-9_-]{43}` (:270-272, :282-284), or from `upload.url` when `upload.token == "minted"` and the URL's report id equals `report_id` (:285-291, :273).
- None for: `"error"` answers, reused/required/expired/none token states, placeholder or malformed URLs (:277-291).

**ReportTokens** — shared/polymath_shared/mcp_retrieval.py:294-330 [DERIVED]
- `get` refreshes LRU position (:309-314); `headers` → `{"X-Upload-Token": token}` or `{}` (:270, :316-318).
- `remember`: stores a new token, evicts least-recently-used past `cap` (:320-328); forgets a token whose answer says `upload.token == "expired"` (:329-330).
- memory only, never written to disk, never logged (:299).

**shape_report** — shared/polymath_shared/mcp_retrieval.py:333-358 [DERIVED]
- in: any report-route answer; non-dict passes through (:338-339).
- post: `status == 429` + `error_code == "REPORT_JOB_RUNNING"` → one sentence plus `{error_code, status: 429, report_id, retry_after_s}` (:340-349); `upload.token == "required"` → adds `upload_note` telling the agent to call status again after `upload.mint_after` (:350-357).

**default_model / DefaultModel** — shared/polymath_shared/mcp_retrieval.py:363-392 [DERIVED]
- in: a `/synthesizers` catalog; out: id of the entry with `default: true`, else the first `offered` entry, else None (:367-372); None when the catalog carries `"error"` (:368-369).
- `DefaultModel.cached()` valid for `ttl_s` (default `DEFAULT_MODEL_TTL_S` = 300.0) (:71, :380, :385-386); a failed pick is not remembered, so the next call asks again (:377, :388-391).

**trim_rows** — shared/polymath_shared/mcp_retrieval.py:397-410 [DERIVED]
- post: `text` / `text_clean` cut at `max_chars` (default `MAX_TEXT` = 1200, :60); a cut row gets `truncated: true` + `full_length` (D-02); a row that fits is unchanged (:398-409).

**shape_search** — shared/polymath_shared/mcp_retrieval.py:459-480 [DERIVED]
- `"error"` answers pass through unchanged (:461-463).
- post: chunk rows first, `kind == "graph_fact"` rows after; chunks capped at `max(1, int(max_evidence))`, facts at `GRAPH_FACTS_MAX` = 20 (:63, :464-466); `graph_facts` stays the count (:470); `wildcard` lane included only when non-empty (:471-473); `product_research` / `agent_steps` copied through whole (:450-456, :69).

**shape_explore** — shared/polymath_shared/mcp_retrieval.py:483-504 [DERIVED]
- post: keeps mode, `evidence_packet`, `synthesis_performed` (default False) (:489-491); the runtime's full retrieval inventory and phase list stay out (:484-485); graph facts capped at 20 (:492).

**trim_hits** — shared/polymath_shared/mcp_retrieval.py:507-512 [DERIVED]
- post: at most `max_items` (default `ANSWER_HITS` = 12) hits, each text cut at `max_chars` (default `ANSWER_HIT_TEXT` = 600) (:66-67, :507-509); a non-list passes through unchanged (:510-511).

**shape_product** — shared/polymath_shared/mcp_retrieval.py:515-524 [DERIVED]
- post: everything `/product/search` returned passes, with only the lists under `"evidence"`, `"chunks"`, `"bundle"` cut via `trim_hits` (:518-523).

## effect surface
- Postgres tables read/written: none (FACTS `tables_read: []`, `tables_written: []`).
- Qdrant collections: none. FACTS "collections" entries (`polymath_query`, `polymath_retrieve`, `polymath_search`, `polymath_explore`, `polymath_models`, ...) are tool-name string literals at shared/polymath_shared/mcp_retrieval.py:58, :664, :712, :717, :729, not data stores [DERIVED].
- Network/file/subprocess/env: none — "Pure: no I/O and no orchestrator import"; imports are only `json`, `re`, `threading`, `time`, `collections`, `collections.abc`, `typing` — shared/polymath_shared/mcp_retrieval.py:22, :25-31 [DERIVED].
- Route paths built for callers (strings, not calls): `/product/report/start` :186, `/product/reports` :187, `/product/report/{id}/{action}` :194-196, `/product/report/{id}/status?upload_base=` :199-203, `/product/report/{id}/upload/{token}` :273 [DERIVED].
- In-process state: `ReportTokens._held` OrderedDict + `threading.Lock` :303-304; `DefaultModel` clock `time.monotonic` :380 [DERIVED].

## invariants
INVARIANT: RETRIEVAL_MODES == ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN") and MODE_GUIDE has one entry per mode — shared/polymath_shared/mcp_retrieval.py:34-44 [DERIVED]
  fails-if: a mode accepted here but unknown to the app serves tools from the frozen LEGACY lane the app no longer uses (:7-8).
INVARIANT: _ALIASES maps exactly one name, VECTOR -> FAST — shared/polymath_shared/mcp_retrieval.py:45 [DERIVED]
  fails-if: `_executed_mode` reports an internal name agents do not know (:439-442).
INVARIANT: REPORT_DEFAULT_PRODUCTS (5) <= REPORT_MAX_PRODUCTS (8) — shared/polymath_shared/mcp_retrieval.py:177-178 [DERIVED]
  fails-if: a start body asks for more products than the route caps.
INVARIANT: len(ReportTokens) <= REPORT_TOKEN_CACHE_MAX == 256, LRU evicted first — shared/polymath_shared/mcp_retrieval.py:271, :327-328 [DERIVED]
  fails-if: unbounded token growth in a long-running server.
INVARIANT: wildcard lane length <= WILDCARD_MAX == 8, excerpt <= WILDCARD_TEXT == 600 — shared/polymath_shared/mcp_retrieval.py:61-62, :421-430 [DERIVED]
INVARIANT: shaped graph facts <= GRAPH_FACTS_MAX == 20 — shared/polymath_shared/mcp_retrieval.py:63, :466, :492 [DERIVED]
INVARIANT: REPORT_ID == rpt_ + 24 hex == product_reports.report_id / report_store.REPORT_ID_RE — shared/polymath_shared/mcp_retrieval.py:183-185 [DERIVED]
INVARIANT: _UPLOAD_TOKEN == [A-Za-z0-9_-]{43} == secrets.token_urlsafe(32) size == report_store.TOKEN_RE — shared/polymath_shared/mcp_retrieval.py:272 [DERIVED]
INVARIANT: DEFAULT_DEPTH == "quick"; DEPTHS keys == ("quick", "standard", "thorough") — shared/polymath_shared/mcp_retrieval.py:52-54 [DERIVED]
INVARIANT: one live upload link per report (token reused via X-Upload-Token), not one minted per status call — shared/polymath_shared/mcp_retrieval.py:295-297 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `DefaultModel` reads `time.monotonic` — shared/polymath_shared/mcp_retrieval.py:380; concurrency: `ReportTokens` mutates shared state under `threading.Lock` — shared/polymath_shared/mcp_retrieval.py:304). All body builders, normalizers and shapers are pure functions of their inputs (:22, :110-141, :397-524) [DERIVED].
idempotency: SAFE — pure functions; `ReportTokens`/`DefaultModel` mutate process-local memory only, never disk or network (:299, :376-392) [DERIVED].

## failure behaviour
FACTS records no fallbacks. Visible error returns:
- `mode_error` → `{"error": "unknown retrieval mode ...", "status": 422, "modes": dict(MODE_GUIDE)}` — shared/polymath_shared/mcp_retrieval.py:93-95 [DERIVED].
- `normalize_reasoning` / `normalize_depth` → None on unknown input — shared/polymath_shared/mcp_retrieval.py:98-105 [DERIVED].
- `report_id_error` → `{"error": "REPORT_ID_INVALID: ...", "status": 422}` — shared/polymath_shared/mcp_retrieval.py:212-214 [DERIVED].
- `report_token_from` → None for error answers, non-"minted" token states, malformed or wrong-report URLs — shared/polymath_shared/mcp_retrieval.py:277-291 [DERIVED].
- `default_model` → None when the catalog is not a dict or carries `"error"` — shared/polymath_shared/mcp_retrieval.py:368-369 [DERIVED].
- `DefaultModel.remember` does not cache a failed pick — shared/polymath_shared/mcp_retrieval.py:377, :388-391 [DERIVED].
- `shape_search` / `shape_explore` / `shape_product` pass any `"error"` answer through unchanged — shared/polymath_shared/mcp_retrieval.py:461-463, :486-487, :518-519 [DERIVED].
- `shape_report` rewrites 429 `REPORT_JOB_RUNNING` into one plain sentence with `report_id` and `retry_after_s` — shared/polymath_shared/mcp_retrieval.py:340-349 [DERIVED].

## dumb-code flags
- Literal `1200` with two meanings: `MAX_TEXT` (evidence row cut) :60 vs `REPORT_VERDICT_MAX` (verdict char bound) :179 [DERIVED].
- Literal `600` twice: `WILDCARD_TEXT` :62 vs `ANSWER_HIT_TEXT` :67 [DERIVED].
- `REPORT_TIMEOUT_S` repeats `30.0` for `status` and `list` — shared/polymath_shared/mcp_retrieval.py:182 [DERIVED].
- Magic slice `sources[:4]` in `shape_wildcard` — shared/polymath_shared/mcp_retrieval.py:433 [DERIVED].
- Tool-name literals repeated at several lines (`polymath_search`/`polymath_explore` at :664 and :712; `polymath_models` at :717 twice per FACTS) — rename must touch all occurrences [DERIVED].
- Live-stamp workaround: the runtime stamps FAST as VECTOR ("seen live 2026-10-01"), patched back in `_executed_mode` — shared/polymath_shared/mcp_retrieval.py:440 [DERIVED].

## refactor notes
- Blast radius: both MCP servers plus `orchestrator/orchestrator/api/_small-modules` import this module (FACTS.importers); it exists precisely so the two surfaces cannot drift — shared/polymath_shared/mcp_retrieval.py:3-5 [DERIVED].
- Mode and reasoning-style lists are pinned by tests — shared/polymath_shared/mcp_retrieval.py:33, :47 [DERIVED].
- `PRODUCT_REASON_STEPS` = 9 is pinned by a test and must match `config/adapters/ecommerce.product_research.json` — shared/polymath_shared/mcp_retrieval.py:78-79 [DERIVED].
- `REPORT_ID` / `_UPLOAD_TOKEN` must stay identical to `report_store.REPORT_ID_RE` / `report_store.TOKEN_RE` and the `product_reports.report_id` format — shared/polymath_shared/mcp_retrieval.py:183-185, :272 [DERIVED].
- Never add an orchestrator import: Server B runs outside the orchestrator package — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED].
- `HIDDEN_TOOLS_A`/`HIDDEN_TOOLS_B` names are kept for old callers but hidden from tools/list — shared/polymath_shared/mcp_retrieval.py:56-58 [DERIVED].
- `REPORT_UPLOAD_BASES` semantics are tied to Server A's `_is_local_caller` and Server B always saying local — shared/polymath_shared/mcp_retrieval.py:188-191 [DERIVED].

## VERIFY
```verify
grep -Fq 'rpt_[0-9a-f]{24}' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'REPORT_TOKEN_HEADER = "X-Upload-Token"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODEL_TTL_S = 300.0' shared/polymath_shared/mcp_retrieval.py
grep -Fq '_ALIASES = {"VECTOR": "FAST"}' shared/polymath_shared/mcp_retrieval.py
! grep -Fq 'import requests' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'truncated' shared/polymath_shared/mcp_retrieval.py)" -ge 3
```
