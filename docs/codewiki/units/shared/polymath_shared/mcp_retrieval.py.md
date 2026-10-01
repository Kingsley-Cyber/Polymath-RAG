# unit: shared/polymath_shared/mcp_retrieval.py
anchor: shared/polymath_shared/mcp_retrieval.py:1-318

## purpose

Single shared description of Polymath's retrieval for both MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`, streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two cannot drift — shared/polymath_shared/mcp_retrieval.py:1-11 [DERIVED].
Defines the five public retrieval modes, the request body each tool sends, and how each answer is cut down for an agent — shared/polymath_shared/mcp_retrieval.py:1-11 [DERIVED].
Pure module: no I/O, no orchestrator import (Server B runs outside the orchestrator package) — shared/polymath_shared/mcp_retrieval.py:11 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `RETRIEVAL_MODES` / `DEFAULT_MODE` / `MODE_GUIDE` | constants | 5-tuple / `"HYBRID"` / dict | 18-29 | importers below |
| `REASONING_STYLES` | constant | 13-tuple of style names | 32-34 | importers below |
| `DEPTHS` / `DEFAULT_DEPTH` | constants | dict of 3 presets / `"quick"` | 36-39 | importers below |
| `HIDDEN_TOOLS_A` / `HIDDEN_TOOLS_B` | constants | frozenset of legacy tool names | 41-43 | importers below |
| `mode_lines` | def | `() -> str` | 53-54 | importers below |
| `normalize_mode` | def | `(mode: Any) -> str \| None` | 57-61 | importers below |
| `mode_error` | def | `(mode: Any) -> dict` | 64-66 | importers below |
| `normalize_reasoning` | def | `(style: Any) -> str \| None` | 69-71 | importers below |
| `normalize_depth` | def | `(depth: Any) -> str \| None` | 74-76 | importers below |
| `search_body` | def | `(query, corpus_id, mode) -> dict` | 81-85 | importers below |
| `explore_body` | def | `(query, corpus_id, mode, corpus_explorer) -> dict` | 88-89 | importers below |
| `answer_body` | def | `(question, corpus_id, mode, *, reasoning=None, model=None, latent=None) -> dict` | 92-101 | importers below |
| `compare_body` | def | `(question, corpus_id, modes) -> dict` | 104-105 | importers below |
| `deep_body` | def | `(question, corpus_id, depth, mode, model=None) -> dict` | 108-112 | importers below |
| `trim_rows` | def | `(rows, max_chars=MAX_TEXT) -> list[dict]` | 117-130 | importers below |
| `shape_wildcard` | def | `(items: Any) -> list[dict]` | 138-156 | importers below |
| `shape_search` | def | `(out: dict, max_evidence: int) -> dict` | 164-185 | importers below |
| `shape_explore` | def | `(out: dict) -> dict` | 188-209 | importers below |
| `shape_compare` | def | `(out: dict, max_rows=COMPARE_ROWS) -> dict` | 212-238 | importers below |
| `shape_models` | def | `(out: dict) -> dict` | 241-247 | importers below |
| `parse_sse` | def | `(lines: Iterable[str]) -> Iterator[tuple[str, dict]]` | 252-274 | importers below |
| `shape_deep` | def | `(events, *, depth, mode) -> dict` | 277-317 | importers below |

Importers (FACTS.importers; per-symbol attribution not available): `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/mcp_server.py` — shared/polymath_shared/mcp_retrieval.py:1-318 [DERIVED].

## contracts

**normalize_mode** — shared/polymath_shared/mcp_retrieval.py:57-61
- in: any value; `None`/empty falls back to `DEFAULT_MODE` before casing (`str(mode or DEFAULT_MODE).strip().upper()`) — 59.
- out: canonical mode name, or `None` when not one of the five; alias `_ALIASES = {"VECTOR": "FAST"}` applied first — 30, 59-60.
- post: `None`/`""` input returns `"HYBRID"`, never `None` — 20, 59, 61.

**mode_error** — shared/polymath_shared/mcp_retrieval.py:64-66
- out: `{"error": "unknown retrieval mode {mode!r}; use one of [...]", "status": 422, "modes": dict(MODE_GUIDE)}`.

**normalize_reasoning / normalize_depth** — shared/polymath_shared/mcp_retrieval.py:69-76
- out: lowercased value if in `REASONING_STYLES` / `DEPTHS`, else `None`; empty input defaults to `"none"` / `"quick"` — 70, 75.

**search_body** — shared/polymath_shared/mcp_retrieval.py:81-85
- out: exactly `{"message", "corpus_id", "mode", "compiler": "off", "corpus_explorer": False, "evidence": True}` — 84-85. These flags select the chat runtime's evidence route with the query compiler off and `RETRIEVE-EVIDENCE-ROWS-V1` rows on — 82-83.

**explore_body** — 88-89: `{"message", "corpus_id", "mode", "corpus_explorer": bool(corpus_explorer)}`.
**answer_body** — 92-101: base `{"message", "corpus_id", "mode"}`; adds `"reasoning"` only when truthy and `!= "none"` (95-96), `"synthesizer"` when `model` set (97-98), `"latent"` when `latent is not None` (99-100).
**compare_body** — 104-105: `{"message", "corpus_id", "modes": list(modes)}`.
**deep_body** — 108-112: `{"question", "corpus_id", "preset": depth, "mode"}` plus `"synthesizer"` when `model` set.

**trim_rows** — shared/polymath_shared/mcp_retrieval.py:117-130
- in: rows (or `None`), `max_chars` default `MAX_TEXT = 1200` — 45, 117.
- out: copied dicts; `text`/`text_clean` longer than `max_chars` are cut to `max_chars` and the row gains `"truncated": True` and `"full_length"` (the untrimmed `text` length, else `text_clean`) — 121-128.
- post: rows that fit are unchanged; D-02 contract: a cut row must say so — 118-119.

**shape_wildcard** — shared/polymath_shared/mcp_retrieval.py:138-156
- in: any; non-list / non-dict items dropped — 140-141.
- out: at most `WILDCARD_MAX = 8` rows; keep-keys are `chunk_id, doc_id, source_name, title, heading_path, score, kind, label, insight, bridge, reason, facet_id, arrival` when non-empty; text = `text` or `text_clean` or `insight`, clipped at `WILDCARD_TEXT = 600` with `"truncated": True` when cut; `sources`/`children` reduced to first 4 of `chunk_id/doc_id/source_name` — 46-47, 141-154.

**shape_search** — shared/polymath_shared/mcp_retrieval.py:164-185
- in: runtime `out` dict; `max_evidence` (required, no default).
- pre: if `"error" in out`, returned unchanged — 167-168.
- out: `{"mode": out.meta.mode, "evidence_rows": trim_rows(chunk rows then graph facts), "evidence_contract", "graph_facts": len(facts)}`; chunk rows capped at `max(1, int(max_evidence))`, facts at `GRAPH_FACTS_MAX = 20`; optional `wildcard`, `evidence_rows_error`, `latency_ms`, `scope`, `degraded` — 48, 169-184.

**shape_explore** — shared/polymath_shared/mcp_retrieval.py:188-209
- out: `{"mode", "evidence_packet", "synthesis_performed": out.get("synthesis_performed", False)}`; `graph_facts` here is the **capped list** (≤ 20), not a count; optional `wildcard`, `latency_ms`, `scope`, `degraded` — 194-208.

**shape_compare** — shared/polymath_shared/mcp_retrieval.py:212-238
- out: per-arm `{mode, ok, latency_ms, ...}`; failed arm keeps `error`; ok arm gets `evidence_count`, first 12 `documents`, `top_rows` (first `max(1, int(max_rows))`, default `COMPARE_ROWS = 6`, keys `chunk_id, doc_id, source_name, score, arrival`) — 49, 222-233.
- post: `found_by_every_mode` = sorted intersection of all per-mode `chunk_id` sets; `only_this_mode[m]` = count of `m`'s ids not in any other mode's set — 234-237.

**shape_models** — shared/polymath_shared/mcp_retrieval.py:241-247
- in: `out["synthesizers"]` or `out["models"]`; entries with `offered` not `False` — 244-245.
- out: `{"default": models[0]["id"] or None, "models": [{id, label, provider_label, description}]}` — 246-247.

**parse_sse** — shared/polymath_shared/mcp_retrieval.py:252-274
- in: lines (str or bytes; bytes decoded utf-8/replace) — 256.
- out: yields `(event, json-data)` per complete frame; blank line ends a frame; `:` keep-alive lines skipped; frames with JSON parse errors are silently dropped — 257-262, 271-274.

**shape_deep** — shared/polymath_shared/mcp_retrieval.py:277-317
- in: `(event, data)` stream; last `answer` wins, first `error` wins, `phase` labels collected — 281-289.
- error path: no answer + error frame → `{"error": "{code}: {message}", "status": 409 if code == "DEEP_RESEARCH_BUSY" else 502, "error_code", ["summary"]}` with default code `"DEEP_RESEARCH_FAILED"` — 290-294.
- no answer, no error → `{"error": "the deep research stream ended without a report", "status": 502, "stages": last 6}` — 295.
- out: `{depth, mode, report, model, verdict, citations (text clipped at REPORT_CITATION_TEXT = 400), unknown_citations, counts, stop_reason, coverage, latency_ms}`; `counts` = goals/findings/sources/open_questions lengths plus `confidence` breakdown over `strong / single_source / contested` — 50, 296-317.

## effect surface

- Postgres tables read/written: none — FACTS `"tables_read": []`, `"tables_written": []`.
- Qdrant collections: none. FACTS lists `polymath_query` / `polymath_retrieve` at line 43, but that line is `HIDDEN_TOOLS_B = frozenset({"polymath_query", "polymath_retrieve"})` — an analyzer misparse of a tool-name set, not a store — shared/polymath_shared/mcp_retrieval.py:43 [INFERRED: line 43 is a frozenset literal of tool names].
- Files / network / subprocess / env flags: none — module is pure, no I/O — shared/polymath_shared/mcp_retrieval.py:11 [DERIVED].

## invariants

INVARIANT: `len(RETRIEVAL_MODES) == 5` with members `"FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"` — shared/polymath_shared/mcp_retrieval.py:18-19 [DERIVED]
  fails-if: `mode_lines()` raises `KeyError` on a mode missing from `MODE_GUIDE` (53-54); `normalize_mode` rejects the mode.
INVARIANT: `mode_lines()` output covers exactly `RETRIEVAL_MODES` × `MODE_GUIDE` — shared/polymath_shared/mcp_retrieval.py:53-54 [DERIVED]
  fails-if: guide text or mode list edited without the other.
INVARIANT: `normalize_mode(None) == "HYBRID" == DEFAULT_MODE` — shared/polymath_shared/mcp_retrieval.py:20, 59-61 [DERIVED]
  fails-if: falsy mode silently becomes HYBRID instead of an error; callers must use `mode_error` explicitly for bad strings.
INVARIANT: `trim_rows` default cut == `MAX_TEXT` == `1200`; wildcard excerpt == `WILDCARD_TEXT` == `600` ≤ `MAX_TEXT` — shared/polymath_shared/mcp_retrieval.py:45, 47, 117, 146 [DERIVED]
  fails-if: D-02 breaks — a cut row without `truncated: true` + `full_length` (118-119).
INVARIANT: `shape_wildcard` length ≤ `WILDCARD_MAX` == `8`; `sources` per item ≤ `4` — shared/polymath_shared/mcp_retrieval.py:46, 141, 152-153 [DERIVED]
  fails-if: agent payload grows unbounded.
INVARIANT: graph facts per answer ≤ `GRAPH_FACTS_MAX` == `20` in both `shape_search` and `shape_explore` — shared/polymath_shared/mcp_retrieval.py:48, 171, 197 [DERIVED]
  fails-if: divergent caps between the two tools.
INVARIANT: `shape_search["graph_facts"]` is an `int` (175) but `shape_explore["graph_facts"]` is a `list` (197-199) — same key, different type — shared/polymath_shared/mcp_retrieval.py:175, 197-199 [DERIVED]
  fails-if: a consumer reading both shapes with one expectation crashes or under-reports.
INVARIANT: `shape_compare` `top_rows` ≤ `max(1, int(max_rows))`, default `COMPARE_ROWS` == `6`; `documents` ≤ `12` — shared/polymath_shared/mcp_retrieval.py:49, 229-232 [DERIVED]
  fails-if: compare payload blows past agent context.
INVARIANT: `shape_deep` citation text ≤ `REPORT_CITATION_TEXT` == `400` chars, flagged `truncated` when cut — shared/polymath_shared/mcp_retrieval.py:50, 310-311 [DERIVED]
  fails-if: oversized citations in the deep-research answer.
INVARIANT: `only_this_mode` counts + shared ids partition each mode's found set: `sum(only_this_mode) + len(found_by_every_mode) == total distinct ids` — shared/polymath_shared/mcp_retrieval.py:234-237 [INFERRED: set difference vs intersection of the same `found` dict].
INVARIANT: `parse_sse` yields only frames with a set `event` and non-empty `data`, all JSON-parsed — shared/polymath_shared/mcp_retrieval.py:257-262 [DERIVED]
  fails-if: a keep-alive or malformed frame is surfaced as data.

## determinism & idempotency

determinism: DETERMINISTIC (pure functions of their inputs; no clock/random/uuid/db/network/env anywhere in the module — shared/polymath_shared/mcp_retrieval.py:11 [DERIVED])
idempotency: SAFE (no side effects; `trim_rows` copies each row via `dict(r)` before mutating — shared/polymath_shared/mcp_retrieval.py:121-122 [DERIVED])

## failure behaviour

- Invalid mode/reasoning/depth never raise: normalizers return `None` (57-61, 69-71, 74-76); the caller is expected to send `mode_error`'s `status: 422` payload (64-66).
- Every `shape_*` passes an already-errored `out` through unchanged on `"error" in out` — 167-168, 189-190, 215-216, 242.
- `parse_sse` swallows `ValueError` from `json.loads` (malformed frames dropped silently) — 259-262, 271-274.
- Non-dict members are skipped, not errors: wildcard items (140-141), evidence rows (169), compare arms (218-219), model entries (244), deep citations (308-309).
- `shape_deep` maps a typed error frame to `{"error", "status"}` with `409` for `DEEP_RESEARCH_BUSY`, `502` otherwise, default code `DEEP_RESEARCH_FAILED`; a report-less stream becomes a `502` with the last 6 stage labels — 290-295.
- `_degraded` reads `out["retrieval"]["degraded"]` or `out["meta"]["degraded"]`, `None` when absent — 159-161.

## dumb-code flags

- Dead guard: `block` is always a `dict` after line 298's conditional, so `isinstance(block, dict)` at line 300 is always true — shared/polymath_shared/mcp_retrieval.py:298-300 [DERIVED].
- Magic numbers without named constants: `documents[:12]` (230), `sources[:4]` (152-153), `stages[-6:]` (295).
- Same key, two types: `graph_facts` int in `shape_search` (175) vs list in `shape_explore` (197-199).
- `shape_models` accepts two input keys, `"synthesizers"` or `"models"` (244) — dual-literal compat surface.
- `trim_rows` `full_length` prefers `text` length over `text_clean` when both are cut (`full.get("text", full.get("text_clean"))`) — 128.
- `answer_body` silently drops `reasoning == "none"` (95-96) while `normalize_reasoning` maps empty input to `"none"` (70) — default round-trips to an absent key.
- `shape_search.max_evidence` is required with no default (164) while sibling `shape_compare.max_rows` defaults to `COMPARE_ROWS` (212) — asymmetric signatures.
- `HIDDEN_TOOLS_A`/`HIDDEN_TOOLS_B` are parallel per-server sets (42-43); FACTS reports their values in sorted order (`["ask", "compile_plan", "retrieve", "retrieve_evidence"]`) while the source writes `{"retrieve", "retrieve_evidence", "compile_plan", "ask"}` — same members, order-only difference — shared/polymath_shared/mcp_retrieval.py:42 [DERIVED].

## refactor notes

- Three units import this module (FACTS.importers: `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `orchestrator/orchestrator/api/_small-modules`); renaming any `*_body` key or `shape_*` output key changes both MCP servers' wire contracts at once — shared/polymath_shared/mcp_retrieval.py:1-11 [DERIVED].
- `RETRIEVAL_MODES` mirrors frontend-v2 `PUBLIC_MODES` = `retrieval_modes.EXPOSED_MODES` minus LEGACY, "pinned by tests" — 18; `REASONING_STYLES` mirrors orchestrator `api/reasoning.py CURATED_MODES`, "pinned by a test" — 32; `DEPTHS` mirrors `api/deep_research.py` presets — 36. Changing any of these requires updating those external definitions and their tests.
- D-02 truncation keys `"truncated"`/`"full_length"` are a stated contract (118-119, 126-128) — consumers may rely on both.
- `search_body`'s `"compiler": "off", "corpus_explorer": False, "evidence": True` selects the `RETRIEVE-EVIDENCE-ROWS-V1` evidence contract (82-85) — flipping any flag changes the row shape downstream.
- `HIDDEN_TOOLS_A`/`HIDDEN_TOOLS_B` keep old callers working while hiding tools from `tools/list` (41-43) — names must not be deleted.
- `_ALIASES = {"VECTOR": "FAST"}` is the only accepted legacy alias (30, 60).

## VERIFY

```verify
grep -Fq 'RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'DEFAULT_MODE = "HYBRID"' shared/polymath_shared/mcp_retrieval.py
grep -Fq 'MAX_TEXT = 1200' shared/polymath_shared/mcp_retrieval.py
grep -Fq '"compiler": "off", "corpus_explorer": False,' shared/polymath_shared/mcp_retrieval.py
grep -Eq '409 if code == .DEEP_RESEARCH_BUSY. else 502' shared/polymath_shared/mcp_retrieval.py
! grep -Fq 'import orchestrator' shared/polymath_shared/mcp_retrieval.py
test "$(grep -c -F 'truncated' shared/polymath_shared/mcp_retrieval.py)" -ge 4
```
