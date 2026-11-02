# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-973

## purpose
The ONE description of Polymath's retrieval for both MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two cannot drift — shared/polymath_shared/mcp_retrieval.py:3-5 [DERIVED].
Defines the five public retrieval modes, the request body each tool sends, and how each answer is cut down for an agent; also the product-decision-report tools' bodies, timeouts, and upload-token handling — shared/polymath_shared/mcp_retrieval.py:5-20 [DERIVED].
Pure: no I/O and no orchestrator import (Server B runs outside the orchestrator package) — shared/polymath_shared/mcp_retrieval.py:22 [DERIVED].
Importers (FACTS): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py` — shared/polymath_shared/mcp_retrieval.py:552-556 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RETRIEVAL_MODES / DEFAULT_MODE / MODE_GUIDE | const | `("FAST","HYBRID","GRAPH","WILDCARD","GNN")` / `"HYBRID"` / guide dict | :34-44 | both MCP servers |
| mode_lines | def | `() -> str` | :82-83 | importers |
| normalize_mode | def | `(mode: Any) -> str \| None` | :86-90 | importers |
| mode_error | def | `(mode: Any) -> dict` | :93-95 | importers |
| normalize_reasoning | def | `(style: Any) -> str \| None` | :98-100 | importers |
| normalize_depth | def | `(depth: Any) -> str \| None` | :103-105 | importers |
| search_body | def | `(query, corpus_id, mode) -> dict` | :110-114 | Server A + B |
| explore_body | def | `(query, corpus_id, mode, corpus_explorer) -> dict` | :117-118 | Server A + B |
| answer_body | def | `(question, corpus_id, mode, *, reasoning=None, model=None, latent=None) -> dict` | :121-130 | Server A + B |
| compare_body | def | `(question, corpus_id, modes: Iterable[str]) -> dict` | :133-134 | Server A + B |
| deep_body | def | `(question, corpus_id, depth, mode, model=None) -> dict` | :137-141 | Server A + B |
| product_body | def | `(message, corpus_id=None, *, geography=None, model=None, hypotheses=None, limit_per_hypothesis=None) -> dict` | :144-166 | Server A + B |
| parse_body | def | `(site, raw_text) -> dict` | :169-171 | Server A + B |
| report_path / report_status_path | def | `(report_id, action) -> str` / `(report_id, upload_base=None) -> str` | :194-196 / :199-203 | Server A + B |
| normalize_report_id / report_id_error | def | `(value) -> str \| None` / `(value) -> dict` | :206-209 / :212-214 | Server A + B |
| report_start_body | def | `(message=None, corpus_id=None, *, products=None, channels=None, ship_to="US", max_products=REPORT_DEFAULT_PRODUCTS, upload_base=None) -> dict` | :222-250 | Server A + B |
| report_compile_body | def | `(verdicts=None) -> dict` | :253-262 | Server A + B |
| report_token_from | def | `(answer, report_id=None) -> str \| None` | :276-291 | ReportTokens |
| ReportTokens | class | `__init__(cap=REPORT_TOKEN_CACHE_MAX)`, `__len__`, `get(key)`, `headers(key)`, `remember(key, answer, report_id=None)` | :294-330 | both servers |
| shape_report | def | `(out: Any) -> Any` | :333-358 | Server A + B |
| default_model | def | `(catalog: Any) -> str \| None` | :363-373 | Server A + B |
| DefaultModel | class | `__init__(ttl_s=DEFAULT_MODEL_TTL_S, clock=time.monotonic)`, `cached()`, `remember(catalog)` | :376-392 | both servers |
| trim_rows | def | `(rows, max_chars=MAX_TEXT) -> list[dict]` | :397-410 | shapers |
| shape_wildcard | def | `(items) -> list[dict]` | :418-436 | shape_search/shape_explore |
| shape_search | def | `(out: dict, max_evidence: int) -> dict` | :459-480 | Server A + B |
| shape_explore | def | `(out: dict) -> dict` | :483-504 | Server A + B |
| trim_hits | def | `(items, max_items=ANSWER_HITS, max_chars=ANSWER_HIT_TEXT) -> Any` | :507-512 | shape_product |
| shape_product | def | `(out: dict) -> dict` | :515-524 | Server A + B |
| shape_compare | def | `(out, max_rows)` | :527-553 [DERIVED from FACTS] | Server A + B |
| shape_models | def | `(out)` | :556-562 [DERIVED from FACTS] | Server A + B |
| parse_sse | def | `(lines)` — "(event, data) for every frame of a text/event-stream; keep-alive comments and malformed frames are skipped" | :567-589 [DERIVED from FACTS] | Server A + B |
| shape_deep | def | `(events, depth, mode)` | :592-632 [DERIVED from FACTS] | Server A + B |
| playbook | def | `(list_tool, add_documents)` — ordered server-instruction playbook | :660-707 [DERIVED from FACTS] | Server A + B |
| list_corpora_description | def | `(lead)` | :710-711 [DERIVED from FACTS] | Server A + B |

## contracts

**normalize_mode** (:86-90)
- in: any value; falsy → treated as `DEFAULT_MODE` (`str(mode or DEFAULT_MODE)`), upper-cased, then `_ALIASES` applied — :88-89 [DERIVED]
- out: the canonical mode name, or `None` when not one of the five — :90 [DERIVED]
- pre: `_ALIASES = {"VECTOR": "FAST"}` — the old name of FAST, still accepted — :45, :89 [DERIVED]

**search_body** (:110-114)
- out: exactly `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` — :113-114 [DERIVED]
- post: answer carries RETRIEVE-EVIDENCE-ROWS-V1 rows — :111-112 [DERIVED]

**answer_body** (:121-130)
- `reasoning` key only added when set and `!= "none"` — :124-125 [DERIVED]
- `model` travels as `"synthesizer"` — :126-127 [DERIVED]
- `latent` coerced to bool when not None — :128-129 [DERIVED]

**product_body** (:144-166)
- `corpus_id` included only when non-blank; absent = orchestrator searches every authorized library (owner R11) — :146-153 [DERIVED]
- hypotheses reduced to `{title, search_terms[]}` only; an extra key an agent invents never reaches the route — :148-149, :158-163 [DERIVED]

**report_start_body** (:222-250)
- `products` keep only `{title, search_terms[]}` with non-blank title — :225, :237-241 [DERIVED]
- `channels` lower-cased, de-duplicated via `dict.fromkeys` — :242-244 [DERIVED]
- `ship_to` upper-cased, defaults `"US"` — :245 [DERIVED]
- `upload_base` included only when in `REPORT_UPLOAD_BASES` ("the server's own decision, never the agent's") — :248-249, :227-228 [DERIVED]

**report_compile_body** (:253-262)
- in: `verdicts` dict; blank keys/values dropped; nothing else travels — :254-255, :256-262 [DERIVED]
- out: `{"verdicts": kept}` or `{}` when empty — :262 [DERIVED]

**report_token_from** (:276-291)
- returns `None` for any non-dict answer or any answer carrying `"error"` — :280-281 [DERIVED]
- accepts start's `upload_token` only when it matches `_UPLOAD_TOKEN = [A-Za-z0-9_-]{43}` — :272, :282-284 [DERIVED]
- else only when `upload.token == "minted"` AND `_UPLOAD_URL` matches AND names this `report_id` — :285-291 [DERIVED]

**ReportTokens** (:294-330)
- in-memory only; never written to disk, never logged — :298-299 [DERIVED]
- `get` refreshes LRU position — :312-313 [DERIVED]
- `remember` evicts least-recently-used past `cap`; forgets a token whose answer says `expired` — :325-330 [DERIVED]
- exists so a report keeps ONE live upload link instead of one new link per status call (review R3 #2) — :296-297 [DERIVED]

**shape_report** (:333-358)
- everything passes through, `next` included (the route's sentence is the instruction, C9) — :334-335 [DERIVED]
- 429 + `REPORT_JOB_RUNNING` → one sentence naming the report to check and the wait (C8) — :342-349 [DERIVED]
- `upload.token == "required"` adds `upload_note` (no runnable script; call status again after `upload.mint_after`) — :351-357 [DERIVED]

**trim_rows** (:397-410)
- cuts `text` / `text_clean` at `max_chars`; a cut row gains `truncated: True` + `full_length` (D-02); a row that fits is unchanged — :398-408 [DERIVED]

**default_model** (:363-373)
- `None` when catalog is not a dict or carries `"error"` — :368-369 [DERIVED]
- picks the offered entry with `default is True`, else the first offered — :370-372 [DERIVED]

**DefaultModel** (:376-392)
- `cached()` returns the id only while `clock() - at < ttl_s` — :385-386 [DERIVED]
- `remember()` stores only a valid pick; a failed ask is not remembered, so the next call asks again — :377, :387-391 [DERIVED]

**shape_search** (:459-480)
- chunk rows first, `kind == "graph_fact"` rows after; chunks capped at `max(1, int(max_evidence))` — :465-466 [DERIVED]
- `graph_facts` stays a count (`len(facts)`), capped by `GRAPH_FACTS_MAX` — :466, :470 [DERIVED]
- wildcard lane added only when non-empty — :471-473 [DERIVED]
- `product_research` / `agent_steps` pass through whole via `_keep_product` — :450-456, :480 [DERIVED]

**shape_explore** (:483-504)
- EvidencePacket passed already-bounded; the runtime's full retrieval inventory and phase list stay out (diagnostics, tens of KB) — :484-485, :493 [DERIVED]

**shape_product** (:515-523)
- everything `/product/search` returned is kept; only the bulky evidence lists (`evidence`, `chunks`, `bundle`) are trimmed — :517-523 [DERIVED]

## effect surface
- Postgres: none — FACTS `tables_read: []`, `tables_written: []` — shared/polymath_shared/mcp_retrieval.py:557-558 [DERIVED]
- Qdrant / files / network / subprocess / env flags: none in this module; it is pure with imports only `json, re, threading, time, collections, typing` — :25-31 [DERIVED]
- Constants describing external systems: `AGENT_REACH_REPO` :75, `AGENT_REACH_VERIFY = "agent-reach doctor --json"` (command text travels in tool results, never executed here) :73-76, `PRODUCT_ADAPTER = "ecommerce.product_research"` :77, `REPORT_START_PATH = "/product/report/start"` :186, `REPORT_LIST_PATH = "/product/reports"` :187, `REPORT_TIMEOUT_S = {"start": 60.0, "status": 30.0, "compile": 120.0, "list": 30.0}` :182 [DERIVED]
- Shared mutable state: `ReportTokens` (OrderedDict + `threading.Lock`) :303-304; `DefaultModel` (id + timestamp) :382-383 [DERIVED]

## invariants
INVARIANT: REPORT_TOKEN_CACHE_MAX = 256 ≥ len(ReportTokens._held) at all times — :271, :327-328 [DERIVED]
  fails-if: unbounded token growth; the R3 #2 status-loop token-minting bug returns.
INVARIANT: RETRIEVAL_MODES length = 5 and DEFAULT_MODE = "HYBRID" ∈ RETRIEVAL_MODES — :34-35 [DERIVED]
  fails-if: normalize_mode(default) returns None; every tool call errors with 422.
INVARIANT: REPORT_MAX_PRODUCTS (8) ≥ REPORT_DEFAULT_PRODUCTS (5) — :177-178 [DERIVED]
  fails-if: default start body asks for more products than the route's cap.
INVARIANT: REPORT_TIMEOUT_S compile (120.0) > start (60.0) > status = list (30.0) — :182 [DERIVED]
  fails-if: a status read outlives compile; HTML render times out.
INVARIANT: _UPLOAD_TOKEN pattern length = 43 chars = secrets.token_urlsafe(32) output (report_store.TOKEN_RE) — :272 [DERIVED]
  fails-if: real tokens rejected as malformed; placeholder tokens kept.
INVARIANT: GRAPH_FACTS_MAX = 20 caps facts in both shape_search and shape_explore — :63, :466, :492 [DERIVED]
  fails-if: answers balloon past agent context limits.
INVARIANT: WILDCARD_MAX = 8 items, each excerpt ≤ WILDCARD_TEXT = 600, sources ≤ 4 — :61-62, :421, :426, :434 [DERIVED]
  fails-if: wildcard lane displaces the evidence it must never displace (:41-42).
INVARIANT: ANSWER_HITS = 12 items × ANSWER_HIT_TEXT = 600 chars — :66-67, :507 [DERIVED]
  fails-if: answer evidence exceeds the cut polymath_answer always made (:66).
INVARIANT: executed mode "VECTOR" is reported as "FAST" via _ALIASES — :45, :439-442 [DERIVED]
  fails-if: agent sees a mode name that is not in RETRIEVAL_MODES.

## determinism & idempotency
determinism: DETERMINISTIC — pure body builders and shapers build new dicts (`dict(r)` :403, `{**out}` :357); only clock reads in DefaultModel via injectable `clock=time.monotonic` :380 and lock-guarded cache order in ReportTokens :304 [DERIVED]
idempotency: SAFE — no I/O; `remember`/`cached` mutate in-memory caches only, and repeated calls with the same answer converge — :320-330, :388-391 [DERIVED]

## failure behaviour
- No broad try/except anywhere in the visible source (lines 82-523); failures are returned as error dicts, not raised — :93-95, :212-214 [INFERRED: absence of handlers in shown range].
- `mode_error` → `{"error": "unknown retrieval mode ...", "status": 422, "modes": dict(MODE_GUIDE)}` — :93-95 [DERIVED]
- `report_id_error` → `{"error": "REPORT_ID_INVALID: ...", "status": 422}`; nothing that fails `normalize_report_id` ever reaches a route path — :206-209, :212-214 [DERIVED]
- `shape_report` rewrites 429 `REPORT_JOB_RUNNING` into one plain sentence with `report_id` and `retry_after_s`; the caller sees status 429 preserved — :342-349 [DERIVED]
- `report_token_from` swallows malformed/foreign answers to `None` (a placeholder or wrong-report URL is never kept) — :278-291 [DERIVED]
- `default_model` returns `None` on an unavailable/erroring catalog; DefaultModel does not remember a failed ask — :368-369, :377 [DERIVED]

## dumb-code flags
- `1200` appears twice with different meanings: `MAX_TEXT` :60 vs `REPORT_VERDICT_MAX` :179 [DERIVED]
- `600` appears twice: `WILDCARD_TEXT` :62 vs `ANSWER_HIT_TEXT` :67 [DERIVED]
- `REPORT_TOKEN_STATES = ("minted", "reused", "required", "expired", "none")` is defined :269 but the code compares the string literals directly — `"minted"` :286, `"expired"` :329, `"required"` :351 [INFERRED: constant unused in the visible range]
- Magic number `sources[:4]` in shape_wildcard, no named constant — :434 [DERIVED]
- `_ALIASES` duplicates knowledge the runtime already stamps (runtime reports FAST as VECTOR; seen live 2026-10-01) — :45, :440 [DERIVED]
- `HIDDEN_TOOLS_A` / `HIDDEN_TOOLS_B` kept only for old callers but hidden from tools/list — dead tools carried forward — :56-58 [DERIVED]

## refactor notes
- Both MCP surfaces import this module (FACTS importers: `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules`); any body/shape change hits both servers at once — that single-definition property is the module's reason to exist — :3-5 [DERIVED]
- `RETRIEVAL_MODES` is pinned to frontend-v2 `PUBLIC_MODES` = retrieval_modes.EXPOSED_MODES minus LEGACY by tests — :33 [DERIVED]
- `REASONING_STYLES` pinned to orchestrator api/reasoning.py `CURATED_MODES` by a test — :47 [DERIVED]
- `PRODUCT_REASON_STEPS = 9` pinned by a test against config/adapters/ecommerce.product_research.json — :78-79 [DERIVED]
- `REPORT_ID` and `_UPLOAD_TOKEN`/`_UPLOAD_URL` must stay in sync with `report_store.REPORT_ID_RE` / `TOKEN_RE` — :183-185, :272-273 [DERIVED]
- Purity constraint: never add an orchestrator import — Server B runs outside the orchestrator package — :22 [DERIVED]
- Do not remove `HIDDEN_TOOLS_A`/`HIDDEN_TOOLS_B`; old callers still use them — :56-58 [DERIVED]
- `shape_report`'s pass-through of `next` (C9) and the 429 rewrite (C8) are review-fix contracts C1-C10 recorded in docs/wiki/work-log/2026-11-02-product-decision-report.md — :265-267 [DERIVED]

## VERIFY
```verify
grep -Fq 'RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'rpt_[0-9a-f]{24}' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'REPORT_TOKEN_HEADER = "X-Upload-Token"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '_ALIASES = {"VECTOR": "FAST"}' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODEL_TTL_S = 300.0' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'trim_rows' shared/polymath_shared/mcp_retrieval.py)" -ge 3
! grep -Fq 'import orchestrator' shared/polymath_shared/mcp_retrieval.py
```
