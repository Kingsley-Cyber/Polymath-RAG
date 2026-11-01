# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-639

## purpose
Single shared description of Polymath's five public retrieval modes, the request body each MCP tool sends, and how each answer is cut down for an agent — used by BOTH MCP surfaces (Server A `orchestrator/orchestrator/mcp_server.py` streamable-http bearer; Server B `mcp_server/polymath_mcp.py` stdio) so they cannot drift — shared/polymath_shared/mcp_retrieval.py:1-17 [DERIVED].
Also holds the agent-facing instruction text both servers emit: the ordered playbook and the product_search / supplier_* / adapter / research_acquire descriptions — shared/polymath_shared/mcp_retrieval.py:11-15, shared/polymath_shared/mcp_retrieval.py:440-443 [DERIVED].
Pure module: no I/O, no orchestrator import (Server B runs outside the orchestrator package) — shared/polymath_shared/mcp_retrieval.py:17 [DERIVED].

## public surface
Module imported by `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules` (FACTS.importers). Per-symbol callers unknown beyond that.

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RETRIEVAL_MODES / DEFAULT_MODE / MODE_GUIDE | const | — | mcp_retrieval.py:26-36 | — |
| REASONING_STYLES / DEPTHS / DEFAULT_DEPTH | const | — | mcp_retrieval.py:40-46 | — |
| HIDDEN_TOOLS_A / HIDDEN_TOOLS_B | const | frozenset | mcp_retrieval.py:49-50 | — |
| normalize_mode | def | (mode) -> str \| None | mcp_retrieval.py:78-82 | — |
| normalize_reasoning / normalize_depth | def | (style/depth) -> str \| None | mcp_retrieval.py:90-97 | — |
| search_body | def | (query, corpus_id, mode) -> dict | mcp_retrieval.py:102-106 | — |
| explore_body | def | (query, corpus_id, mode, corpus_explorer) -> dict | mcp_retrieval.py:109-110 | — |
| answer_body | def | (question, corpus_id, mode, *, reasoning, model, latent) -> dict | mcp_retrieval.py:113-122 | — |
| compare_body | def | (question, corpus_id, modes) -> dict | mcp_retrieval.py:125-126 | — |
| deep_body | def | (question, corpus_id, depth, mode, model) -> dict | mcp_retrieval.py:129-133 | — |
| product_body | def | (message, corpus_id=None, *, geography, model, hypotheses, limit_per_hypothesis) -> dict | mcp_retrieval.py:136-158 | — |
| parse_body | def | (site, raw_text) -> dict | mcp_retrieval.py:161-163 | — |
| default_model | def | (catalog) -> str \| None | mcp_retrieval.py:168-178 | — |
| DefaultModel | class | __init__(ttl_s=DEFAULT_MODEL_TTL_S, clock=time.monotonic); cached(); remember(catalog) | mcp_retrieval.py:181-197 | — |
| trim_rows | def | (rows, max_chars=MAX_TEXT) -> list[dict] | mcp_retrieval.py:202-215 | — |
| shape_wildcard | def | (items) -> list[dict] | mcp_retrieval.py:223-241 | — |
| shape_search | def | (out, max_evidence) -> dict | mcp_retrieval.py:264-285 | — |
| shape_explore | def | (out) -> dict | mcp_retrieval.py:288-309 | — |
| trim_hits | def | (items, max_items=ANSWER_HITS, max_chars=ANSWER_HIT_TEXT) -> Any | mcp_retrieval.py:312-317 | — |
| shape_product | def | (out) -> dict | mcp_retrieval.py:320-329 | — |
| shape_compare | def | (out, max_rows=COMPARE_ROWS) -> dict | mcp_retrieval.py:332-358 | — |
| shape_models | def | (out) -> dict | mcp_retrieval.py:361-367 | — |
| parse_sse | def | (lines) -> Iterator[(event, data)] | mcp_retrieval.py:372-394 | — |
| shape_deep | def | (events, *, depth, mode) -> dict | mcp_retrieval.py:397-437 | — |
| playbook | def | (*, list_tool, add_documents) -> str | mcp_retrieval.py:465-493 | both servers (docstring 465-467) |
| list_corpora_description | def | (lead) -> str | mcp_retrieval.py:496-497 | — |
| ANSWER / PRODUCT_SEARCH / SUPPLIER_ANSWER | const (description strings) | — | mcp_retrieval.py:500-543 | both servers (440-443) |

## contracts

**normalize_mode(mode)** — mcp_retrieval.py:78-82
- in: any value; `None`/empty falls back to `DEFAULT_MODE` ("HYBRID") — mcp_retrieval.py:80 [DERIVED]
- out: uppercased name mapped through `_ALIASES` (`"VECTOR"` -> `"FAST"`), returned only if in `RETRIEVAL_MODES`, else `None` — mcp_retrieval.py:80-82 [DERIVED]
- post: never raises; `mode_error` companion returns `{"error", "status": 422, "modes": dict(MODE_GUIDE)}` — mcp_retrieval.py:85-87 [DERIVED]

**default_model(catalog)** — mcp_retrieval.py:168-178
- in: `/synthesizers` response dict
- out: id of the offered entry with `default is True`, else the first offered entry, else `None`; `None` when catalog is not a dict or contains `"error"` — mcp_retrieval.py:173-177 [DERIVED]

**DefaultModel** — mcp_retrieval.py:181-197
- `cached()` returns the remembered id only while `clock() - _at < ttl_s` (default 300.0 s) — mcp_retrieval.py:185-191 [DERIVED]
- `remember(catalog)` stores id + timestamp only when `default_model` picks something (a failed ask is not remembered) — mcp_retrieval.py:193-196 [DERIVED]

**trim_rows(rows, max_chars=1200)** — mcp_retrieval.py:202-215
- post: any row whose `text` or `text_clean` exceeds `max_chars` is cut and stamped `truncated: True` + `full_length` (untrimmed `text` length, else `text_clean`); rows that fit are unchanged; `None` rows -> `[]` — mcp_retrieval.py:206-214 [DERIVED]

**shape_search(out, max_evidence)** — mcp_retrieval.py:264-285
- post: `evidence_rows` = non-graph rows `[:max(1, int(max_evidence))]` + graph_fact rows `[:GRAPH_FACTS_MAX]`; `graph_facts` = count of kept facts; wildcard lane shaped (≤ 8 items); passes through `evidence_rows_error`, `latency_ms`, `scope`, `degraded`, and `PRODUCT_KEYS` — mcp_retrieval.py:270-284 [DERIVED]
- pre: an `out` containing `"error"` is returned unchanged — mcp_retrieval.py:267-268 [DERIVED]

**shape_compare(out, max_rows=6)** — mcp_retrieval.py:332-358
- post: per-mode arm keeps `latency_ms`, `evidence_count`, `documents[:12]`, `top_rows[:max(1, max_rows)]` (keys `chunk_id, doc_id, source_name, score, arrival`); `found_by_every_mode` = intersection of chunk-id sets; `only_this_mode[m]` = count of ids no other mode found — mcp_retrieval.py:349-357 [DERIVED]

**parse_sse(lines)** — mcp_retrieval.py:372-394
- out: yields `(event, data)` tuples; lines starting `:` (keep-alive) skipped; frames whose `data` fails `json.loads` are silently dropped — mcp_retrieval.py:380-393 [DERIVED]

**shape_deep(events, *, depth, mode)** — mcp_retrieval.py:397-437
- post: report text, model, verdict, citations (text clipped at `REPORT_CITATION_TEXT` = 400, cut ones stamped `truncated: True`), counts (goals/findings/sources/open_questions/confidence tallies), stop_reason, coverage, latency_ms — mcp_retrieval.py:427-437 [DERIVED]
- no `answer` frame: typed error -> `{"error", "status"}` with status `409` when `error_code == "DEEP_RESEARCH_BUSY"` else `502`; bare ended stream -> `{"error": "the deep research stream ended without a report", "status": 502, "stages": stages[-6:]}` — mcp_retrieval.py:410-415 [DERIVED]

**product_body(...)** — mcp_retrieval.py:136-158
- post: hypotheses reduced to exactly `{title, search_terms[]}` keys (stripped, empty titles dropped) so agent-invented keys never reach the route; `corpus_id` omitted when empty/None = search every authorized library — mcp_retrieval.py:139-155 [DERIVED]

**playbook(list_tool, add_documents)** — mcp_retrieval.py:465-493
- post: ordered 6-step instruction string embedding `mode_lines()` and `PRODUCT_REASON_STEPS`; `list_tool`/`add_documents` name each server's own corpus tools — mcp_retrieval.py:466-493 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS.tables_read / tables_written empty).
- Qdrant collections: none — the tool-name strings at mcp_retrieval.py:50, 469, 501, 506, 518 are description text, not collection access [INFERRED: FACTS "collections" entries point at lines inside frozenset/description strings].
- Files / network / subprocess: none; only stdlib imports `json`, `time` — mcp_retrieval.py:20-21 [DERIVED]. Endpoints `/retrieve`, `/product/search`, `/supplier/parse`, `/synthesizers`, `/research/deep` appear in docstrings/description text only — mcp_retrieval.py:7, 138, 162, 169, 370 [DERIVED].
- Clock: `DefaultModel.__init__` defaults `clock=time.monotonic` — mcp_retrieval.py:185 [DERIVED].
- Env flags read: none visible.

## invariants
INVARIANT: RETRIEVAL_MODES == ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN") and DEFAULT_MODE == "HYBRID" — mcp_retrieval.py:26-27 [DERIVED]
  fails-if: normalize_mode rejects a valid mode; mode_error 422s a working call.
INVARIANT: `_ALIASES` contains exactly one mapping, `"VECTOR"` -> `"FAST"` — mcp_retrieval.py:37 [DERIVED]
  fails-if: `_executed_mode` leaks the runtime's internal name VECTOR to agents (runtime stamps FAST as VECTOR, seen live 2026-10-01) — mcp_retrieval.py:244-247 [DERIVED].
INVARIANT: wildcard lane ≤ WILDCARD_MAX = 8 items, each text ≤ WILDCARD_TEXT = 600 chars, sources ≤ 4 — mcp_retrieval.py:226-239 [DERIVED]
  fails-if: tool-result payload bloat on both servers.
INVARIANT: graph facts kept in shaped answers ≤ GRAPH_FACTS_MAX = 20 — mcp_retrieval.py:270-271, 297 [DERIVED]
  fails-if: same as above.
INVARIANT: every cut row carries `truncated: True` + `full_length` (rule D-02) — mcp_retrieval.py:208-213 [DERIVED]
  fails-if: agent cannot distinguish a cut excerpt from a full passage.
INVARIANT: DefaultModel cached id honoured only for < ttl_s = 300.0 s; a failed `/synthesizers` ask is not remembered — mcp_retrieval.py:63, 185-196 [DERIVED]
  fails-if: a key added in Settings never shows up, or a stale id is pinned forever.
INVARIANT: `product_body` hypotheses carry only the keys `title` and `search_terms` — mcp_retrieval.py:150-153 [DERIVED]
  fails-if: an extra agent-invented key reaches `/product/search`.
INVARIANT: HIDDEN_TOOLS_A = {"retrieve", "retrieve_evidence", "compile_plan", "ask"}, HIDDEN_TOOLS_B = {"polymath_query", "polymath_retrieve"} — kept for old callers, hidden from tools/list — mcp_retrieval.py:48-50 [DERIVED]
  fails-if: agents are offered stale tools the app no longer documents.
INVARIANT: shape_search keeps at least 1 chunk row (`max(1, int(max_evidence))`) — mcp_retrieval.py:270 [DERIVED]
  fails-if: max_evidence ≤ 0 silently empties the evidence.

## determinism & idempotency
determinism: NONDETERMINISTIC only in `DefaultModel` via its clock (default `time.monotonic`, injectable) — mcp_retrieval.py:185 [DERIVED]; all other functions are pure data shaping on their inputs.
idempotency: SAFE — no I/O or writes; `DefaultModel.remember` only mutates an in-process memo — mcp_retrieval.py:193-196 [DERIVED].

## failure behaviour
- `parse_sse` swallows `ValueError` from `json.loads` (malformed frames dropped, both mid-stream and at end) and skips keep-alive `:` lines — caller just sees fewer events — mcp_retrieval.py:380-393 [DERIVED].
- `shape_deep` never raises on a bad stream: typed error -> `{"error": "<code>: <message>", "status": 409|502}` (409 only for `DEEP_RESEARCH_BUSY`); report-less stream -> status 502 with the last 6 phase labels — mcp_retrieval.py:410-415 [DERIVED].
- Every `shape_*` returns an `out` containing `"error"` unchanged (search 267-268, explore 291-292, product 323-324, compare 335-336, models 362-363) — the caller sees the upstream error dict — mcp_retrieval.py:267, 291, 323, 335, 362 [DERIVED].
- Bad mode/reasoning/depth never raise: `normalize_*` return `None`, `mode_error` returns status 422 with the full `MODE_GUIDE` — mcp_retrieval.py:78-97, 85-87 [DERIVED].
- `default_model` on an unavailable/errored catalog returns `None` instead of raising — mcp_retrieval.py:173-174 [DERIVED].

## dumb-code flags
- `_ALIASES` is a band-aid with one entry: any new internal runtime mode name would pass through `_executed_mode` unaliased — mcp_retrieval.py:37, 244-247 [DERIVED].
- Duplicated catalog logic: the `"synthesizers" or "models"` key fallback and the `offered` default-True filter appear twice, in `default_model` and in `shape_models` — mcp_retrieval.py:175-176 vs mcp_retrieval.py:364-365 [DERIVED].
- Same value under two names: `WILDCARD_TEXT = 600` and `ANSWER_HIT_TEXT = 600` — mcp_retrieval.py:54, 59 [DERIVED].
- `trim_hits` reuses `trim_rows` by wrapping each hit in a one-element list (`trim_rows([h], max_chars)[0]`) — mcp_retrieval.py:317 [DERIVED].
- Dead-by-design tool names kept in `HIDDEN_TOOLS_A`/`HIDDEN_TOOLS_B` for old callers — mcp_retrieval.py:48-50 [DERIVED].
- Magic agent-facing bounds all inline at module top (MAX_TEXT 1200, WILDCARD_MAX 8, GRAPH_FACTS_MAX 20, COMPARE_ROWS 6, REPORT_CITATION_TEXT 400, ANSWER_HITS 12) — mcp_retrieval.py:52-59 [DERIVED].
- `shape_compare.documents` hard-codes `[:12]` instead of a named constant (contrast `COMPARE_ROWS = 6` one line up in use) — mcp_retrieval.py:350 vs mcp_retrieval.py:56 [DERIVED].

## refactor notes
- This module is the ONE copy for both MCP servers; any change to `playbook()` or the description strings (`ANSWER`, `PRODUCT_SEARCH`, `SUPPLIER_*`, `ADAPTER_START`, `RESEARCH_ACQUIRE`) changes agent instructions on both surfaces at once — mcp_retrieval.py:1-5, 440-449, 500-639; importers `mcp_server/polymath_mcp.py` and `orchestrator/orchestrator/mcp_server.py` (FACTS.importers) [DERIVED].
- Must stay pure: Server B (`mcp_server/polymath_mcp.py`) runs outside the orchestrator package — adding an orchestrator import breaks it — mcp_retrieval.py:17 [DERIVED].
- Values pinned to other modules by tests — changing one side breaks the pin: `RETRIEVAL_MODES` = frontend-v2 `PUBLIC_MODES` = `retrieval_modes.EXPOSED_MODES` minus LEGACY (mcp_retrieval.py:25); `REASONING_STYLES` = `api/reasoning.py` `CURATED_MODES` (mcp_retrieval.py:39); `DEPTHS` = `api/deep_research.py` presets (mcp_retrieval.py:43); `PRODUCT_REASON_STEPS = 9` = `config/adapters/ecommerce.product_research.json` (mcp_retrieval.py:70-71); `GUIDE_PROMPT`/`GUIDE_RESOURCE` = `harness_guide.PROMPT_NAME`/`GUIDE_URI` (mcp_retrieval.py:444-445) [DERIVED].
- The trim constants (mcp_retrieval.py:52-59) bound every tool result an agent receives on both servers; resizing them is an agent-visible payload change, not a local tweak [INFERRED: they are the only bounds applied in every `shape_*`].
- `_executed_mode`'s VECTOR->FAST alias exists because the runtime stamps the internal name; if the runtime is ever fixed to emit public names, `_ALIASES` at mcp_retrieval.py:37 becomes dead but must stay for old responses — mcp_retrieval.py:244-247 [INFERRED from the live-observation comment].

## VERIFY
```verify
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"VECTOR": "FAST"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODEL_TTL_S = 300.0' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'MAX_TEXT = 1200' shared/polymath_shared/mcp_retrieval.py
! grep -Fq 'import orchestrator' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'polymath_search' shared/polymath_shared/mcp_retrieval.py)" -ge 2
```
