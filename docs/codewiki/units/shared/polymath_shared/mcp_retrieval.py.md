# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-971

## purpose
The ONE description of Polymath's retrieval for both MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — "so the two cannot drift again" — shared/polymath_shared/mcp_retrieval.py:3-8 [DERIVED]. Also holds what both servers TELL an agent: the ordered playbook, the product_search / supplier_* / adapter_next / research_acquire descriptions (PRODUCT-SEARCH-E2E, 2026-11-01) and the four product_report_* tools' bodies and timeouts (PRODUCT-DECISION-REPORT-V1, B5, 2026-11-02) — shared/polymath_shared/mcp_retrieval.py:11-20 [DERIVED]. Pure: "no I/O and no orchestrator import (Server B runs outside the orchestrator package)" — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED].

Importers (FACTS): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules`. "A+B" in the table = the two MCP servers.

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `mode_lines` | def | () -> str | shared/polymath_shared/mcp_retrieval.py:82-83 | A+B |
| `normalize_mode` | def | (mode) -> str \| None | shared/polymath_shared/mcp_retrieval.py:86-90 | A+B |
| `mode_error` | def | (mode) -> dict | shared/polymath_shared/mcp_retrieval.py:93-95 | A+B |
| `normalize_reasoning` | def | (style) -> str \| None | shared/polymath_shared/mcp_retrieval.py:98-100 | A+B |
| `normalize_depth` | def | (depth) -> str \| None | shared/polymath_shared/mcp_retrieval.py:103-105 | A+B |
| `search_body` | def | (query, corpus_id, mode) -> dict | shared/polymath_shared/mcp_retrieval.py:110-114 | A+B |
| `explore_body` | def | (query, corpus_id, mode, corpus_explorer) -> dict | shared/polymath_shared/mcp_retrieval.py:117-118 | A+B |
| `answer_body` | def | (question, corpus_id, mode, *, reasoning=None, model=None, latent=None) -> dict | shared/polymath_shared/mcp_retrieval.py:121-130 | A+B |
| `compare_body` | def | (question, corpus_id, modes) -> dict | shared/polymath_shared/mcp_retrieval.py:133-134 | A+B |
| `deep_body` | def | (question, corpus_id, depth, mode, model=None) -> dict | shared/polymath_shared/mcp_retrieval.py:137-141 | A+B |
| `product_body` | def | (message, corpus_id=None, *, geography=None, model=None, hypotheses=None, limit_per_hypothesis=None) -> dict | shared/polymath_shared/mcp_retrieval.py:144-166 | A+B |
| `parse_body` | def | (site, raw_text) -> dict | shared/polymath_shared/mcp_retrieval.py:169-171 | A+B |
| `report_path` | def | (report_id, action) -> str | shared/polymath_shared/mcp_retrieval.py:194-196 | A+B |
| `report_status_path` | def | (report_id, upload_base=None) -> str | shared/polymath_shared/mcp_retrieval.py:199-203 | A+B |
| `normalize_report_id` | def | (value) -> str \| None | shared/polymath_shared/mcp_retrieval.py:206-209 | A+B |
| `report_id_error` | def | (value) -> dict | shared/polymath_shared/mcp_retrieval.py:212-214 | A+B |
| `_terms` | def | (value) -> list[str] | shared/polymath_shared/mcp_retrieval.py:217-219 | internal |
| `report_start_body` | def | (message=None, corpus_id=None, *, products=None, channels=None, ship_to="US", max_products=5, upload_base=None) -> dict | shared/polymath_shared/mcp_retrieval.py:222-250 | A+B |
| `report_compile_body` | def | (verdicts=None) -> dict | shared/polymath_shared/mcp_retrieval.py:253-262 | A+B |
| `report_token_from` | def | (answer, report_id=None) -> str \| None | shared/polymath_shared/mcp_retrieval.py:276-291 | A+B |
| `ReportTokens` | class | (cap=REPORT_TOKEN_CACHE_MAX); `__len__`, `get`, `headers`, `remember` | shared/polymath_shared/mcp_retrieval.py:294-330 | A+B |
| `shape_report` | def | (out) -> Any | shared/polymath_shared/mcp_retrieval.py:333-358 | A+B |
| `default_model` | def | (catalog) -> str \| None | shared/polymath_shared/mcp_retrieval.py:363-373 | A+B |
| `DefaultModel` | class | (ttl_s=DEFAULT_MODEL_TTL_S, clock=time.monotonic); `cached`, `remember` | shared/polymath_shared/mcp_retrieval.py:376-392 | A+B |
| `trim_rows` | def | (rows, max_chars=MAX_TEXT) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:397-410 | A+B |
| `_clip` | def | (text, n) -> tuple[str, bool] | shared/polymath_shared/mcp_retrieval.py:413-415 | internal |
| `shape_wildcard` | def | (items) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:418-436 | A+B |
| `_executed_mode` | def | (out) -> str \| None | shared/polymath_shared/mcp_retrieval.py:439-442 | internal |
| `_degraded` | def | (out) -> Any | shared/polymath_shared/mcp_retrieval.py:445-447 | internal |
| `_keep_product` | def | (out, shaped) -> dict | shared/polymath_shared/mcp_retrieval.py:450-456 | internal |
| `shape_search` | def | (out, max_evidence) -> dict | shared/polymath_shared/mcp_retrieval.py:459-480 | A+B |
| `shape_explore` | def | (out) -> dict | shared/polymath_shared/mcp_retrieval.py:483-504 | A+B |
| `trim_hits` | def | (items, max_items=ANSWER_HITS, max_chars=ANSWER_HIT_TEXT) -> Any | shared/polymath_shared/mcp_retrieval.py:507-512 | A+B |
| `shape_product` | def | (out) — builds `slim = dict(out)`, trims list keys | shared/polymath_shared/mcp_retrieval.py:515-524 | A+B |
| `shape_compare` | def | (out, max_rows) | shared/polymath_shared/mcp_retrieval.py:527-553 | A+B |
| `shape_models` | def | (out) | shared/polymath_shared/mcp_retrieval.py:556-562 | A+B |
| `parse_sse` | def | (lines) — "(event, data) for every frame of a text/event-stream; keep-alive comments and malformed frames are skipped" | shared/polymath_shared/mcp_retrieval.py:567-589 | A+B |
| `shape_deep` | def | (events, depth, mode) — answer from the stream: cited report, citations, coverage, run counts | shared/polymath_shared/mcp_retrieval.py:592-632 | A+B |
| `playbook` | def | (list_tool, add_documents) — the server instructions, "an ordered playbook any model can follow" | shared/polymath_shared/mcp_retrieval.py:660-707 | A+B |
| `list_corpora_description` | def | (lead) | shared/polymath_shared/mcp_retrieval.py:710-711 | A+B |

## contracts

- `normalize_mode` — in: any value; out: canonical mode or None. Post: `str(mode or DEFAULT_MODE).strip().upper()`, then `_ALIASES` applied, then membership in `RETRIEVAL_MODES` — shared/polymath_shared/mcp_retrieval.py:88-90 [DERIVED]. Empty/None falls back to `DEFAULT_MODE = "HYBRID"` — shared/polymath_shared/mcp_retrieval.py:35, 88 [DERIVED].
- `search_body` — out: exactly `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` (query compiler OFF, evidence rows ON) — shared/polymath_shared/mcp_retrieval.py:110-114 [DERIVED].
- `explore_body` / `answer_body` / `compare_body` / `deep_body` — key sets at shared/polymath_shared/mcp_retrieval.py:117-118, 123-129 (`reasoning` only when != "none", model travels as `"synthesizer"`), 133-134 (`modes` as list), 138-140 (`preset` + `"synthesizer"`) [DERIVED].
- `product_body` — pre: `hypotheses` items are dicts; post: each keeps only `{title, search_terms[]}` — "an extra key an agent invents never reaches the route"; blank `corpus_id` omitted = orchestrator searches every authorized library (owner R11) — shared/polymath_shared/mcp_retrieval.py:146-165 [DERIVED].
- `parse_body` — out: `{"site": stripped, "raw_text": unchanged-as-str}`; "what the user's local Agent Reach printed, unchanged" — shared/polymath_shared/mcp_retrieval.py:169-171 [DERIVED].
- `normalize_report_id` — post: returns the value only on `REPORT_ID.fullmatch` where `REPORT_ID = re.compile(r"rpt_[0-9a-f]{24}")`; "nothing else ever reaches a route path" — shared/polymath_shared/mcp_retrieval.py:185, 207-209 [DERIVED].
- `report_status_path` — `?upload_base=` appended only when the value is one of `REPORT_UPLOAD_BASES = ("local", "public")` — shared/polymath_shared/mcp_retrieval.py:191, 199-203 [DERIVED].
- `report_start_body` — post: `products` keep only `{title, search_terms[]}`; `channels` deduped (`dict.fromkeys`) lower-case; `ship_to` upper-case, default `"US"`; `max_products` sent as `int(...)` unclamped ("the route caps `max_products`"); `upload_base` only from `REPORT_UPLOAD_BASES` ("the server's own decision, never the agent's") — shared/polymath_shared/mcp_retrieval.py:222-250 [DERIVED].
- `report_compile_body` — post: `{"verdicts": {candidate_id: verdict}}` with blank keys/values dropped; `{}` when nothing survives; route bounds each verdict at `REPORT_VERDICT_MAX = 1200` chars — shared/polymath_shared/mcp_retrieval.py:179, 253-262 [DERIVED].
- `report_token_from` — pre: `answer` is a dict without `"error"`; out: start's `upload_token` when it matches `_UPLOAD_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")` (= `secrets.token_urlsafe(32)`), else the token inside `upload.url` only when `upload.token == "minted"` and the URL names this report; None for reused / required / expired / none, malformed URLs, placeholders — shared/polymath_shared/mcp_retrieval.py:272-273, 276-291 [DERIVED].
- `ReportTokens` — thread-safe LRU (`OrderedDict` + `threading.Lock`), at most `cap` (default `REPORT_TOKEN_CACHE_MAX = 256`), LRU dropped via `popitem(last=False)`; `headers()` returns `{REPORT_TOKEN_HEADER: token}` (`"X-Upload-Token"`) or `{}`; `remember()` forgets a key when its answer says `upload.token == "expired"`; "Never written to disk, never logged" — shared/polymath_shared/mcp_retrieval.py:269-271, 294-330 [DERIVED].
- `shape_report` — passthrough of everything (`next` included, C9); rewrites `status == 429` + `error_code == "REPORT_JOB_RUNNING"` into one sentence with `report_id` and `retry_after_s`; adds `upload_note` when `upload.token == "required"` — shared/polymath_shared/mcp_retrieval.py:333-358 [DERIVED].
- `default_model` — out: the `/synthesizers` entry with `"default" is True` among offered entries, else the first offered, else None on error catalog — shared/polymath_shared/mcp_retrieval.py:363-373 [DERIVED]. `DefaultModel` caches that id for `ttl_s` (`DEFAULT_MODEL_TTL_S = 300.0`); "a failed ask is not remembered" — shared/polymath_shared/mcp_retrieval.py:71, 376-392 [DERIVED].
- `trim_rows` — post: `text`/`text_clean` cut at `max_chars` (`MAX_TEXT = 1200`); a cut row gets `truncated: True` + `full_length` = the untrimmed `text` length, else `text_clean` (D-02) — shared/polymath_shared/mcp_retrieval.py:60, 397-410 [DERIVED].
- `shape_wildcard` — post: at most `WILDCARD_MAX = 8` items, each a keep-list of identity keys + text clipped at `WILDCARD_TEXT = 600`, `sources` capped at 4 — shared/polymath_shared/mcp_retrieval.py:61-62, 418-436 [DERIVED].
- `shape_search` — post: `mode` via `_executed_mode` (runtime's `VECTOR` remapped to `FAST`), `evidence_rows` = chunk rows (kind != `"graph_fact"`, at least `max(1, int(max_evidence))`) first then graph facts capped at `GRAPH_FACTS_MAX = 20`; `graph_facts` is the COUNT; WILDCARD lane added only when non-empty; `product_research`/`agent_steps` passed through whole — shared/polymath_shared/mcp_retrieval.py:459-480 [DERIVED].
- `shape_explore` — post: EvidencePacket, executed mode, `graph_facts` as the LIST (<= 20), WILDCARD lane; "the runtime's full retrieval inventory and phase list stay out (diagnostics, tens of KB)" — shared/polymath_shared/mcp_retrieval.py:483-504 [DERIVED].
- `trim_hits` — post: at most `max_items` (`ANSWER_HITS = 12`), each cut at `max_chars` (`ANSWER_HIT_TEXT = 600`); non-list input passes through — shared/polymath_shared/mcp_retrieval.py:66-67, 507-512 [DERIVED].
- `shape_product` — post: copy of the whole `/product/search` answer with list keys `("evidence", "chunks", "bundle")` run through `trim_hits` — shared/polymath_shared/mcp_retrieval.py:515-523 [DERIVED].
- `playbook` / `list_corpora_description` — the server instructions text, parameterized by each server's own `list_tool` / `add_documents` names — shared/polymath_shared/mcp_retrieval.py:660-707, 710-711 [DERIVED].

## effect surface
- Postgres: `tables_read = []`, `tables_written = []` (FACTS) — none.
- Qdrant / stores: none named in this module; FACTS `collections` entries are MCP tool-name string literals appearing in the file (`polymath_search`, `polymath_explore`, `polymath_answer`, `polymath_compare`, `polymath_deep_research` at shared/polymath_shared/mcp_retrieval.py:664, 715; `polymath_models` at :720 and :732; `polymath_query`, `polymath_retrieve` at :58) — not data stores [DERIVED].
- Network / subprocess / files: none — "Pure: no I/O and no orchestrator import" — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED]. Route paths exist only as string constants: `"/product/report/start"` (:186), `"/product/reports"` (:187); `AGENT_REACH_VERIFY = "agent-reach doctor --json"` is a description string, never executed here — shared/polymath_shared/mcp_retrieval.py:73-76 [DERIVED].
- Env flags: none read.
- Concurrency: `threading.Lock` inside `ReportTokens` — shared/polymath_shared/mcp_retrieval.py:304 [DERIVED].

## invariants
INVARIANT: RETRIEVAL_MODES == ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN") and DEFAULT_MODE == "HYBRID" — shared/polymath_shared/mcp_retrieval.py:34-35 [DERIVED]
  fails-if: tools send a mode the app rejects; every caller gets `mode_error`'s 422 instead of evidence.
INVARIANT: `_ALIASES` maps exactly `{"VECTOR": "FAST"}` and `_executed_mode` reuses that map, so agents only ever see the public name FAST — shared/polymath_shared/mcp_retrieval.py:45, 439-442 [DERIVED]
  fails-if: the runtime's internal stamp VECTOR leaks to agents as an unknown mode.
INVARIANT: any id on a report route path matches `rpt_[0-9a-f]{24}` under `fullmatch` — shared/polymath_shared/mcp_retrieval.py:185, 206-209 [DERIVED]
  fails-if: arbitrary strings become URL path segments.
INVARIANT: an accepted upload token matches `[A-Za-z0-9_-]{43}` (`secrets.token_urlsafe(32)`) and its URL names the same report — shared/polymath_shared/mcp_retrieval.py:272-273, 283-290 [DERIVED]
  fails-if: placeholder or cross-report tokens get cached and replayed as `X-Upload-Token`.
INVARIANT: `ReportTokens` holds at most cap = REPORT_TOKEN_CACHE_MAX = 256 entries, least-recently-used dropped first — shared/polymath_shared/mcp_retrieval.py:271, 301-303, 327-328 [DERIVED]
  fails-if: a status loop mints one new link per call (review R3 #2) and breaks the running script.
INVARIANT: in `shape_search` `graph_facts` is `len(facts)` <= GRAPH_FACTS_MAX = 20; in `shape_explore` `graph_facts` is the list itself <= 20 — shared/polymath_shared/mcp_retrieval.py:63, 466-470, 492-497 [DERIVED]
  fails-if: a consumer that parses one shape breaks on the other (same key, different type).
INVARIANT: every cut row/hit carries `truncated: True` (D-02) — shared/polymath_shared/mcp_retrieval.py:397-410, 507-512 [DERIVED]
  fails-if: an agent silently reads a truncated passage as complete evidence.
INVARIANT: chunk rows in `shape_search` are at least `max(1, int(max_evidence))` even when the caller passes 0 — shared/polymath_shared/mcp_retrieval.py:465 [DERIVED]
  fails-if: a zero/negative cap produces an evidence-free success answer.

## determinism & idempotency
determinism: DETERMINISTIC for all body builders and shapers (pure, no I/O — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED]); NONDETERMINISTIC parts: `DefaultModel` expiry depends on `time.monotonic` (injectable `clock`) — shared/polymath_shared/mcp_retrieval.py:380, 386 [DERIVED]; `ReportTokens` order depends on call interleaving under `threading.Lock` — shared/polymath_shared/mcp_retrieval.py:304, 309-314 [DERIVED].
idempotency: SAFE — pure request builders return equal dicts for equal inputs; `ReportTokens.remember` converges (same answer → same token, expired → forget) — shared/polymath_shared/mcp_retrieval.py:320-330 [DERIVED].

## failure behaviour
- No `try`/`except` anywhere in the visible source range (lines 1-523); nothing is swallowed here — shared/polymath_shared/mcp_retrieval.py:1-523 [DERIVED].
- Errors travel as returned dicts, not raised: `mode_error` → `{"error": ..., "status": 422, "modes": dict(MODE_GUIDE)}` — shared/polymath_shared/mcp_retrieval.py:93-95; `report_id_error` → `"REPORT_ID_INVALID"` + `"status": 422` — shared/polymath_shared/mcp_retrieval.py:212-214 [DERIVED].
- Shapers pass error answers through untouched: `shape_search`/`shape_explore` return `out` when `"error" in out` — shared/polymath_shared/mcp_retrieval.py:462-463, 486-487; `shape_product` same — :518-519; `report_token_from` returns None on error answers — :280-281; `default_model` returns None on an error catalog — :368-369 [DERIVED].
- `shape_report` translates two route conditions for the agent: 429 + `REPORT_JOB_RUNNING` (C8) becomes one sentence naming the report and the wait; `upload.token == "required"` (C1) adds `upload_note` pointing at the next status call — shared/polymath_shared/mcp_retrieval.py:340-357 [DERIVED].

## dumb-code flags
- `1200` used with two unrelated meanings: `MAX_TEXT = 1200` (evidence row cut) and `REPORT_VERDICT_MAX = 1200` (verdict bound) — shared/polymath_shared/mcp_retrieval.py:60, 179 [DERIVED].
- `600` likewise: `WILDCARD_TEXT = 600` and `ANSWER_HIT_TEXT = 600` — shared/polymath_shared/mcp_retrieval.py:62, 67 [DERIVED].
- Same key `graph_facts`, two types (count vs list) across `shape_search` / `shape_explore` — shared/polymath_shared/mcp_retrieval.py:470, 492-497 [DERIVED].
- `report_start_body` does not clamp `max_products` to `REPORT_MAX_PRODUCTS = 8`; it sends `int(max_products)` as-is ("the route caps `max_products`") — shared/polymath_shared/mcp_retrieval.py:177-178, 246-247 [DERIVED].
- `normalize_mode` silently rewrites a bad mode to the default before validating (`str(mode or DEFAULT_MODE)`), so `None` and `"HYBRID"` are indistinguishable inputs — shared/polymath_shared/mcp_retrieval.py:88 [INFERRED: visible order of operations; a typo'd mode still returns None, but empty input never errors].
- Hidden tools kept for old callers but excluded from tools/list in two parallel frozensets — shared/polymath_shared/mcp_retrieval.py:56-58 [DERIVED].
- Deep-research depth strings (`"quick"`/`"standard"`/`"thorough"`) duplicated between `DEPTHS` keys and the `"preset"` value `deep_body` forwards — shared/polymath_shared/mcp_retrieval.py:52-53, 138 [DERIVED].

## refactor notes
- Blast radius: three importers (FACTS) — `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules`. Any rename of a `*_body` / `shape_*` helper or a wire key breaks both MCP surfaces at once — shared/polymath_shared/mcp_retrieval.py:3-5 [DERIVED].
- Purity is a hard constraint: adding an orchestrator import breaks Server B, which "runs outside the orchestrator package" — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED].
- Wire-key literals are the contract with app routes: `"compiler": "off"`, `"corpus_explorer": False`, `"evidence": True` (:113-114), `"synthesizer"` (:127, :140), `"preset"` (:138), `"upload_base"` (:248-249), `"X-Upload-Token"` (:270) — shared/polymath_shared/mcp_retrieval.py:110-141, 248-270 [DERIVED].
- Test-pinned values (per comments): `RETRIEVAL_MODES` mirrors frontend `PUBLIC_MODES` = `EXPOSED_MODES` minus LEGACY — shared/polymath_shared/mcp_retrieval.py:33-34; `REASONING_STYLES` mirrors `api/reasoning.py CURATED_MODES` — :47-48; `PRODUCT_REASON_STEPS = 9` mirrors `config/adapters/ecommerce.product_research.json` — :78-79 [DERIVED].
- Do not narrow the `{title, search_terms[]}` filter or the `rpt_`/token regexes without updating the orchestrator routes they guard — shared/polymath_shared/mcp_retrieval.py:146-149, 158-163, 185, 222-250, 272-273 [DERIVED].

## VERIFY
```verify
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"VECTOR": "FAST"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'rpt_[0-9a-f]{24}' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'X-Upload-Token' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"compiler": "off"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'REPORT_TOKEN_CACHE_MAX = 256' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'upload_token' shared/polymath_shared/mcp_retrieval.py)" -ge 2
```
