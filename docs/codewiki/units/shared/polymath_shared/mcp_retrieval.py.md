# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-324

## purpose
MCP-RETRIEVAL-MODES-V1: the single description of Polymath's five public retrieval modes, the request body each tool sends, and how each answer is cut down for an agent — shared by both MCP surfaces, Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio), so the two cannot drift — shared/polymath_shared/mcp_retrieval.py:1-5 [DERIVED].
Fixes the stale behavior where `polymath_search` sent no mode and `/retrieve` served it from the frozen LEGACY lane route (`retrieval_modes.DEFAULT_MODE`) the app no longer uses — shared/polymath_shared/mcp_retrieval.py:6-9 [DERIVED].
Pure module: no I/O, no orchestrator import (Server B runs outside the orchestrator package) — shared/polymath_shared/mcp_retrieval.py:10-11 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| RETRIEVAL_MODES | const | tuple ("FAST","HYBRID","GRAPH","WILDCARD","GNN") | shared/polymath_shared/mcp_retrieval.py:19 [DERIVED] | — |
| DEFAULT_MODE | const | "HYBRID" | shared/polymath_shared/mcp_retrieval.py:20 [DERIVED] | — |
| REASONING_STYLES | const | 13-tuple of style names | shared/polymath_shared/mcp_retrieval.py:33-34 [DERIVED] | — |
| DEPTHS / DEFAULT_DEPTH | const | {"quick","standard","thorough"} / "quick" | shared/polymath_shared/mcp_retrieval.py:37-39 [DERIVED] | — |
| HIDDEN_TOOLS_A / _B | const | frozensets of legacy tool names | shared/polymath_shared/mcp_retrieval.py:42-43 [DERIVED] | — |
| mode_lines | def | () -> str | shared/polymath_shared/mcp_retrieval.py:53-54 [DERIVED] | — |
| normalize_mode | def | (mode: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:57-61 [DERIVED] | — |
| mode_error | def | (mode: Any) -> dict | shared/polymath_shared/mcp_retrieval.py:64-66 [DERIVED] | — |
| normalize_reasoning | def | (style: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:69-71 [DERIVED] | — |
| normalize_depth | def | (depth: Any) -> str \| None | shared/polymath_shared/mcp_retrieval.py:74-76 [DERIVED] | — |
| search_body | def | (query: str, corpus_id: str, mode: str) -> dict | shared/polymath_shared/mcp_retrieval.py:81-85 [DERIVED] | — |
| explore_body | def | (query, corpus_id, mode, corpus_explorer: bool) -> dict | shared/polymath_shared/mcp_retrieval.py:88-89 [DERIVED] | — |
| answer_body | def | (question, corpus_id, mode, *, reasoning=None, model=None, latent=None) -> dict | shared/polymath_shared/mcp_retrieval.py:92-101 [DERIVED] | — |
| compare_body | def | (question, corpus_id, modes: Iterable[str]) -> dict | shared/polymath_shared/mcp_retrieval.py:104-105 [DERIVED] | — |
| deep_body | def | (question, corpus_id, depth, mode, model=None) -> dict | shared/polymath_shared/mcp_retrieval.py:108-112 [DERIVED] | — |
| trim_rows | def | (rows, max_chars=MAX_TEXT) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:117-130 [DERIVED] | shape_search :178-179 |
| shape_wildcard | def | (items: Any) -> list[dict] | shared/polymath_shared/mcp_retrieval.py:138-156 [DERIVED] | shape_search :182, shape_explore :206 |
| shape_search | def | (out: dict, max_evidence: int) -> dict | shared/polymath_shared/mcp_retrieval.py:170-191 [DERIVED] | polymath_search tool :171 |
| shape_explore | def | (out: dict) -> dict | shared/polymath_shared/mcp_retrieval.py:194-215 [DERIVED] | polymath_explore tool :195 |
| shape_compare | def | (out: dict, max_rows=COMPARE_ROWS) -> dict | shared/polymath_shared/mcp_retrieval.py:218-244 [DERIVED] | polymath_compare tool :219 |
| shape_models | def | (out: dict) -> dict | shared/polymath_shared/mcp_retrieval.py:247-253 [DERIVED] | — |
| parse_sse | def | (lines: Iterable[str]) -> Iterator[tuple[str, dict]] | shared/polymath_shared/mcp_retrieval.py:258-280 [DERIVED] | shape_deep :283 |
| shape_deep | def | (events, *, depth: str, mode: str) -> dict | shared/polymath_shared/mcp_retrieval.py:283-323 [DERIVED] | polymath_deep_research tool :284 |

Module imported by (FACTS.importers): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py` [DERIVED].

## contracts
**normalize_mode** — shared/polymath_shared/mcp_retrieval.py:57-61
- in: any value; empty/None falls back to `DEFAULT_MODE` ("HYBRID"), uppercased, then `_ALIASES` applied — :59-60 [DERIVED]
- out: the canonical mode name iff it is one of RETRIEVAL_MODES, else `None` — :61 [DERIVED]
- post: `"VECTOR"` in → `"FAST"` out — :30, :60 [DERIVED]

**mode_error** — shared/polymath_shared/mcp_retrieval.py:64-66
- out: `{"error": "unknown retrieval mode {mode!r}; use one of [...]", "status": 422, "modes": dict(MODE_GUIDE)}` — :64-66 [DERIVED]

**search_body** — shared/polymath_shared/mcp_retrieval.py:81-85
- out keys exactly: `message`, `corpus_id`, `mode`, `compiler="off"`, `corpus_explorer=False`, `evidence=True` — :84-85 [DERIVED]
- post: per docstring, the answer carries RETRIEVE-EVIDENCE-ROWS-V1 rows — :82-83 [DERIVED]

**answer_body** — shared/polymath_shared/mcp_retrieval.py:92-101
- base keys: `message`, `corpus_id`, `mode` — :94 [DERIVED]
- `reasoning` added only when truthy and `!= "none"` — :95-96 [DERIVED]
- `model` maps to key `"synthesizer"` — :97-98 [DERIVED]; `latent` added as bool only when not None — :99-100 [DERIVED]

**deep_body** — shared/polymath_shared/mcp_retrieval.py:108-112
- out keys: `question`, `corpus_id`, `preset=depth`, `mode`, optional `synthesizer` — :109-111 [DERIVED]

**trim_rows** — shared/polymath_shared/mcp_retrieval.py:117-130
- in: rows iterable or None — :121 [DERIVED]
- out: row copies with `text`/`text_clean` cut at `max_chars` (default `MAX_TEXT = 1200`) — :122-125, :45 [DERIVED]
- post: cut row carries `truncated: true` + `full_length` (untrimmed `text` length, else `text_clean`); a fitting row is unchanged — :118-119, :126-129 [DERIVED]

**shape_search** — shared/polymath_shared/mcp_retrieval.py:170-191
- passthrough: `"error" in out` → returned untouched — :173-174 [DERIVED]
- chunk rows (`kind != "graph_fact"`) capped at `max(1, int(max_evidence))`; graph facts capped at `GRAPH_FACTS_MAX = 20` — :176-177, :48 [DERIVED]
- out: `mode` (alias-mapped), `evidence_rows = trim_rows(chunks + facts)` (chunks before facts), `evidence_contract`, `graph_facts = len(facts)` (the count) — :178-181 [DERIVED]
- `wildcard` lane added only when non-empty — :182-184 [DERIVED]; `evidence_rows_error`/`latency_ms`/`scope` copied only when not None, `degraded` when truthy — :185-190 [DERIVED]

**shape_explore** — shared/polymath_shared/mcp_retrieval.py:194-215
- passthrough `"error"` — :197-198 [DERIVED]
- out: `mode`, `evidence_packet` (as-is), `synthesis_performed` default `False` — :200-202 [DERIVED]
- `graph_facts` here is the capped list (≤ 20), not a count — :203-205 [DERIVED]; wildcard, optional `latency_ms`/`scope`, `degraded` — :206-214 [DERIVED]

**shape_compare** — shared/polymath_shared/mcp_retrieval.py:218-244
- failed arm: `{mode, ok: False, latency_ms, error}` — :229-231 [DERIVED]
- ok arm: `{mode, ok: True, latency_ms, evidence_count, documents[:12], top_rows[:max(1, int(max_rows))]}` with row keys `chunk_id, doc_id, source_name, score, arrival`, optional `degraded` — :235-239 [DERIVED]
- `found_by_every_mode` = sorted intersection of per-mode chunk_id sets — :240-242 [DERIVED]; `only_this_mode[m]` = count of chunk_ids no other mode found — :243 [DERIVED]

**shape_models** — shared/polymath_shared/mcp_retrieval.py:247-253
- entries from `out["synthesizers"]` or `out["models"]` — :250 [DERIVED]
- only entries with `offered != False` (default True) — :251 [DERIVED]
- out: `{"default": models[0]["id"] if models else None, "models": [...]}` with keys `id, label, provider_label, description` — :252-253 [DERIVED]

**parse_sse** — shared/polymath_shared/mcp_retrieval.py:258-280
- in: lines, str or bytes (decoded utf-8, errors replaced) — :261-262 [DERIVED]
- yields `(event, dict)` per frame; `":"` comment lines skipped; blank line flushes a frame — :263-271 [DERIVED]
- event name = `line[6:].strip()` after `event:`; data lines stripped at `line[5:]` — :272-275 [DERIVED]
- frames whose `data` fails `json.loads` are dropped silently — :265-268, :276-280 [DERIVED]

**shape_deep** — shared/polymath_shared/mcp_retrieval.py:283-323
- event handling: `answer` last wins, `error` first wins, `coverage` last wins, `phase` appends `label` when truthy — :287-295 [DERIVED]
- no answer + error frame: `{"error": "CODE: message", "status": 409 iff code == "DEEP_RESEARCH_BUSY" else 502, "error_code", optional "summary"}`; code defaults `"DEEP_RESEARCH_FAILED"` — :296-300 [DERIVED]
- no answer, no error: `{"error": "the deep research stream ended without a report", "status": 502, "stages": stages[-6:]}` — :301 [DERIVED]
- success: `depth, mode, report, model, verdict, citations` (each text clipped at `REPORT_CITATION_TEXT = 400`, `truncated` flag), `unknown_citations, counts` (goals/findings/sources/open_questions + confidence histogram over `strong/single_source/contested`), `stop_reason, coverage, latency_ms` — :302-323, :50 [DERIVED]

## effect surface
- Postgres tables read/written: none — FACTS `tables_read`/`tables_written` empty; module is "Pure: no I/O" — shared/polymath_shared/mcp_retrieval.py:11 [DERIVED]
- Qdrant collections / files / network / subprocess: none — imports are only `json`, `collections.abc`, `typing` — shared/polymath_shared/mcp_retrieval.py:13-16 [DERIVED]
- Env flags read: none — shared/polymath_shared/mcp_retrieval.py:13-16 [DERIVED]

## invariants
INVARIANT: DEFAULT_MODE == "HYBRID" and "HYBRID" in RETRIEVAL_MODES — shared/polymath_shared/mcp_retrieval.py:19-20 [DERIVED]
  fails-if: the empty-mode fallback would normalize to None and every tool would need mode_error.
INVARIANT: every _ALIASES value ("FAST") is in RETRIEVAL_MODES — shared/polymath_shared/mcp_retrieval.py:19,:30 [DERIVED]
  fails-if: "VECTOR" would map to a mode the app rejects.
INVARIANT: len(shape_wildcard(items)) <= WILDCARD_MAX (8) — shared/polymath_shared/mcp_retrieval.py:141,:46 [DERIVED]
  fails-if: the wildcard lane could displace/drown the main evidence in the agent context.
INVARIANT: wildcard text length <= WILDCARD_TEXT (600) chars — shared/polymath_shared/mcp_retrieval.py:146-150,:47 [DERIVED]
  fails-if: silent context blow-up per wildcard item.
INVARIANT: graph-fact rows kept <= GRAPH_FACTS_MAX (20) in both shape_search and shape_explore — shared/polymath_shared/mcp_retrieval.py:177,:203,:48 [DERIVED]
  fails-if: GRAPH mode answers grow unbounded.
INVARIANT: a trim_rows row with len(text) > max_chars has truncated == True and full_length == original length — shared/polymath_shared/mcp_retrieval.py:123-128 [DERIVED]
  fails-if: agents cannot tell a cut row from a complete one (D-02 contract, :117-119).
INVARIANT: chunks kept >= 1 in shape_search and top_rows >= 1 in shape_compare (max(1, int(...))) — shared/polymath_shared/mcp_retrieval.py:176,:238 [DERIVED]
  fails-if: a max_evidence/max_rows of 0 or negative would return empty evidence silently.
INVARIANT: shape_deep status == 409 iff error_code == "DEEP_RESEARCH_BUSY", else 502 — shared/polymath_shared/mcp_retrieval.py:299 [DERIVED]
  fails-if: busy retries would be treated as hard failures (or vice versa).

## determinism & idempotency
determinism: DETERMINISTIC — pure functions; only imports json/collections.abc/typing, no clock/random/uuid/network/db/env — shared/polymath_shared/mcp_retrieval.py:11,:13-16 [DERIVED]
idempotency: SAFE — no writes; every shaper builds fresh dicts/lists (e.g. trim_rows copies each row) — shared/polymath_shared/mcp_retrieval.py:121-122 [DERIVED]

## failure behaviour
- No exceptions raised in-module for bad input: invalid mode/reasoning/depth become `None` — shared/polymath_shared/mcp_retrieval.py:57-76 [DERIVED]; unknown mode becomes a `{"error": ..., "status": 422, "modes": ...}` payload via mode_error — :64-66 [DERIVED]
- All four shapers pass through any `out` containing `"error"` unchanged (search/explore/compare/models) — shared/polymath_shared/mcp_retrieval.py:173-174,:197-198,:222-223,:248-249 [DERIVED]
- parse_sse swallows frames whose data fails `json.loads` (`except ValueError: pass`) — a malformed frame is indistinguishable from a missing one to the caller — shared/polymath_shared/mcp_retrieval.py:265-268,:276-280 [DERIVED]
- shape_deep error codes: `DEEP_RESEARCH_BUSY` → 409, anything else → 502, default code `DEEP_RESEARCH_FAILED`; a stream with no report at all → 502 plus the last 6 phase labels — shared/polymath_shared/mcp_retrieval.py:296-301 [DERIVED]

## dumb-code flags
- Magic `documents[:12]` — no named constant — shared/polymath_shared/mcp_retrieval.py:236 [DERIVED]
- Magic `sources[:4]` in shape_wildcard — shared/polymath_shared/mcp_retrieval.py:153 [DERIVED]
- Magic `stages[-6:]` — shared/polymath_shared/mcp_retrieval.py:301 [DERIVED]
- Same key `"graph_facts"` is `len(facts)` (int) in shape_search but the capped list in shape_explore — shared/polymath_shared/mcp_retrieval.py:181,:204 [DERIVED]
- Two body dialects: deep_body uses `"question"`/`"preset"` while search/explore/answer/compare use `"message"` — shared/polymath_shared/mcp_retrieval.py:84,:89,:94,:105,:109 [INFERRED] same-module inconsistency, easy to copy wrong when adding a tool.
- `model` param silently renamed to `"synthesizer"` on the wire in answer_body and deep_body — shared/polymath_shared/mcp_retrieval.py:97-98,:110-111 [DERIVED]
- `"none"` is both a REASONING_STYLES member and the sentinel meaning "omit the key" — shared/polymath_shared/mcp_retrieval.py:33-34,:95-96 [DERIVED]
- shape_models accepts two input keys, `"synthesizers"` or `"models"` — shared/polymath_shared/mcp_retrieval.py:250 [DERIVED]
- DEPTHS and REASONING_STYLES duplicate values owned elsewhere (orchestrator `api/deep_research.py` presets, `api/reasoning.py` CURATED_MODES; comments claim test-pinned) — shared/polymath_shared/mcp_retrieval.py:32,:36-38 [INFERRED] comments name foreign owners, so the copies can drift from the source of truth.

## refactor notes
- Blast radius: three importers — `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py` (FACTS.importers); any signature change hits both MCP servers at once [DERIVED].
- Body key names are the wire contract to the app endpoints: `compiler="off"`, `evidence=True`, `corpus_explorer`, `preset`, `synthesizer`, `latent`, `message` vs `question` — shared/polymath_shared/mcp_retrieval.py:84-85,:89,:94-100,:109-111 [DERIVED]
- Keep orchestrator imports out: Server B (stdio) runs outside the orchestrator package — shared/polymath_shared/mcp_retrieval.py:3-4,:10-11 [DERIVED]
- RETRIEVAL_MODES mirrors frontend-v2 `PUBLIC_MODES` = `retrieval_modes.EXPOSED_MODES` minus LEGACY and is pinned by tests; REASONING_STYLES is pinned by a test — shared/polymath_shared/mcp_retrieval.py:18,:32-33 [DERIVED]
- Do not drop `_ALIASES = {"VECTOR": "FAST"}`: the runtime still stamps FAST as VECTOR internally (seen live 2026-10-01), and `_executed_mode` relies on the reverse mapping — shared/polymath_shared/mcp_retrieval.py:30,:159-162 [DERIVED]
- trim_rows implements the D-02 truncation contract (`truncated`/`full_length`); downstream consumers read those fields — shared/polymath_shared/mcp_retrieval.py:117-119,:45 [DERIVED]

## VERIFY
```verify
grep -Fq 'RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq '_ALIASES = {"VECTOR": "FAST"}' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"compiler": "off"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'GRAPH_FACTS_MAX = 20' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'shape_wildcard' shared/polymath_shared/mcp_retrieval.py)" -ge 3
! grep -Fq 'import orchestrator' shared/polymath_shared/mcp_retrieval.py
```
