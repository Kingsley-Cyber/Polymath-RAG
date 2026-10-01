# unit: shared/polymath_shared/adapter/harness_guide.py
anchor: shared/polymath_shared/adapter/harness_guide.py:1-153

## purpose
One operating guide (`GUIDE`) for any MCP-capable agent harness to run a governed Polymath adapter run end to end; BOTH MCP servers publish it as the prompt `run_governed_research` and as resources — shared/polymath_shared/adapter/harness_guide.py:1-3 [DERIVED].
Source- and harness-neutral (ADR-0019 §6, `test_adapter_runtime_neutrality`): what TrailSignal admits is served as TrailSignal's own pinned source table, never restated here — shared/polymath_shared/adapter/harness_guide.py:5-7 [DERIVED].
Pure module: the servers read the repo files named in `FILES` and pass their text in; this unit opens nothing — shared/polymath_shared/adapter/harness_guide.py:7 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `PROMPT_NAME` | str const | = `"run_governed_research"` | shared/polymath_shared/adapter/harness_guide.py:13 | unit importers (below) |
| `PROMPT_DESCRIPTION` | str const | how-to description string | shared/polymath_shared/adapter/harness_guide.py:14-15 | unit importers |
| `GUIDE_URI` | str const | = `"polymath://adapter/guide"` | shared/polymath_shared/adapter/harness_guide.py:16 | unit importers |
| `RECEIPT_SCHEMA_URI` | str const | = `"polymath://adapter/harness-receipt.schema.json"` | shared/polymath_shared/adapter/harness_guide.py:17 | unit importers |
| `ACTION_SCHEMA_URI` | str const | = `"polymath://adapter/harness-action.schema.json"` | shared/polymath_shared/adapter/harness_guide.py:18 | unit importers |
| `SOURCES_URI` | str const | = `"polymath://trail/source-capabilities.csv"` | shared/polymath_shared/adapter/harness_guide.py:19 | unit importers |
| `FILES` | dict[str, str] | 3 uri -> repo file path | shared/polymath_shared/adapter/harness_guide.py:21-23 | unit importers |
| `MIME` | dict[str, str] | 4 uri -> mime type | shared/polymath_shared/adapter/harness_guide.py:24-25 | unit importers |
| `TITLES` | dict[str, str] | 4 uri -> title | shared/polymath_shared/adapter/harness_guide.py:26-29 | unit importers |
| `RESOURCE_URIS` | tuple[str, ...] | 4 uris in order | shared/polymath_shared/adapter/harness_guide.py:30 | unit importers |
| `GUIDE` | str const | f-string markdown, 102 lines | shared/polymath_shared/adapter/harness_guide.py:32-133 | unit importers |
| `prompt_text` | def | (adapter_id: str = "", seed: str = "") -> str | shared/polymath_shared/adapter/harness_guide.py:136-143 | unit importers |
| `resources` | def | (file_texts: Mapping[str, str]) -> dict[str, tuple[str, str]] | shared/polymath_shared/adapter/harness_guide.py:146-153 | unit importers |

Unit imported by: `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `shared/polymath_shared/adapter/transitions.py` [FACTS.importers; per-symbol split not visible in this material].

## contracts

**prompt_text** — shared/polymath_shared/adapter/harness_guide.py:136-143
- in: `adapter_id: str = ""`, `seed: str = ""` — shared/polymath_shared/adapter/harness_guide.py:136 [DERIVED]
- out: `GUIDE + "\n" + begin + ". Keep calling adapter_next until the run is terminal, then report adapter_result.\n"` — shared/polymath_shared/adapter/harness_guide.py:143 [DERIVED]
- pre: none.
- post: `begin = "Begin: call adapter_list(), pick the PREFERRED adapter"` iff `adapter_id == ""` — shared/polymath_shared/adapter/harness_guide.py:138-139 [DERIVED]; non-empty `adapter_id` replaces it with ``"Begin: run the adapter `{adapter_id}`"`` — shared/polymath_shared/adapter/harness_guide.py:140 [DERIVED]; non-empty `seed` appends `", and start it with seed: {seed!r}"` — shared/polymath_shared/adapter/harness_guide.py:141-142 [DERIVED].

**resources** — shared/polymath_shared/adapter/harness_guide.py:146-153
- in: mapping keyed by every uri in `FILES` — shared/polymath_shared/adapter/harness_guide.py:147-148 [DERIVED]
- out: `{GUIDE_URI: (MIME[GUIDE_URI], GUIDE)}` plus `{uri: (MIME[uri], str(file_texts[uri])) for uri in FILES}` — shared/polymath_shared/adapter/harness_guide.py:151-152 [DERIVED]; keys outside `FILES` are ignored — shared/polymath_shared/adapter/harness_guide.py:152 [DERIVED]
- pre: `set(FILES) ⊆ set(file_texts)` — shared/polymath_shared/adapter/harness_guide.py:148-149 [DERIVED]
- post: on violation raises `ValueError(f"harness guide files not supplied: {missing}")` with `missing` sorted — shared/polymath_shared/adapter/harness_guide.py:148-150 [DERIVED]; the guide entry is always served even though `GUIDE_URI` is not a `FILES` key — shared/polymath_shared/adapter/harness_guide.py:151 [DERIVED].

## effect surface
- Postgres tables read/written: none — FACTS `tables_read`/`tables_written` both `[]` [DERIVED].
- Qdrant collections: none visible.
- Files: none opened by this unit; `FILES` names three repo files the servers read: `contracts/adapter/v1/harness_receipt.schema.json`, `contracts/adapter/v1/harness_action.schema.json`, `governance/trail/data/source_capabilities.csv` — shared/polymath_shared/adapter/harness_guide.py:21-23, 7 [DERIVED].
- Network / subprocess / env flags: none; sole import is `from collections.abc import Mapping` — shared/polymath_shared/adapter/harness_guide.py:11 [DERIVED].
- Published artefacts consumed by both MCP servers: prompt text and the resource dict keyed by `RESOURCE_URIS` — shared/polymath_shared/adapter/harness_guide.py:1-3, 30 [DERIVED].

## invariants
INVARIANT: set(`RESOURCE_URIS`) (4 uris) == {`GUIDE_URI`} ∪ keys(`FILES`) (3 uris) — shared/polymath_shared/adapter/harness_guide.py:16-30 [DERIVED]
  fails-if: servers advertise a uri `resources()` never serves, or serve a uri not in `RESOURCE_URIS`.
INVARIANT: `GUIDE_URI` not in `FILES` — shared/polymath_shared/adapter/harness_guide.py:16, 21-23 [DERIVED]
  fails-if: `resources()` would demand a guide file although `GUIDE` is compiled into the module — shared/polymath_shared/adapter/harness_guide.py:151.
INVARIANT: keys(`MIME`) == set(`RESOURCE_URIS`) (4 == 4) — shared/polymath_shared/adapter/harness_guide.py:24-25, 30 [DERIVED]
  fails-if: `KeyError` at `MIME[uri]` in `resources()` — shared/polymath_shared/adapter/harness_guide.py:151-152.
INVARIANT: keys(`TITLES`) == set(`RESOURCE_URIS`) (4 == 4) — shared/polymath_shared/adapter/harness_guide.py:26-30 [DERIVED]
  fails-if: `KeyError` in whichever importer publishes titles.
INVARIANT: `len(RESOURCE_URIS) == 4` and `len(FILES) == 3` — shared/polymath_shared/adapter/harness_guide.py:30, 21-23 [DERIVED]
  fails-if: the published resource set silently shrinks/grows on both servers.
INVARIANT: error list in `resources()` is `sorted(set(FILES) - set(file_texts))` (deterministic message) — shared/polymath_shared/adapter/harness_guide.py:148 [DERIVED]
  fails-if: non-deterministic error text breaks log/tests comparison.

## determinism & idempotency
determinism: DETERMINISTIC (pure string/dict operations over constants; no clock/random/uuid/network/db/env; only import `Mapping` — shared/polymath_shared/adapter/harness_guide.py:11) [DERIVED]
idempotency: SAFE (both functions only build new values; no side effects or writes — shared/polymath_shared/adapter/harness_guide.py:136-153) [DERIVED]

## failure behaviour
- `resources` raises `ValueError("harness guide files not supplied: {sorted missing uris}")` when any `FILES` uri is absent from `file_texts`; nothing is swallowed — shared/polymath_shared/adapter/harness_guide.py:148-150 [DERIVED].
- No other explicit handlers; no error codes beyond that `ValueError` — shared/polymath_shared/adapter/harness_guide.py:136-153 [DERIVED].
- Latent failure: `MIME[uri]` KeyError if `MIME` and `FILES`/`RESOURCE_URIS` key sets ever drift — shared/polymath_shared/adapter/harness_guide.py:151-152 [INFERRED: dict lookup with no guard].

## dumb-code flags
- Receipt limits restated in guide prose: "at most 100 sources, 200 observations and 50 limitations" — shared/polymath_shared/adapter/harness_guide.py:95-96; "at most 600 characters" — shared/polymath_shared/adapter/harness_guide.py:105-106. Authoritative copy is the schema file at `contracts/adapter/v1/harness_receipt.schema.json` — shared/polymath_shared/adapter/harness_guide.py:21 [INFERRED: two places to drift, the schema is not in this material].
- `ACTION_SCHEMA_URI` is published in `RESOURCE_URIS` but never interpolated into `GUIDE` text (only `{RECEIPT_SCHEMA_URI}`, `{SOURCES_URI}`, `{PROMPT_NAME}` are) — shared/polymath_shared/adapter/harness_guide.py:18, 30, 95, 115, 131 [DERIVED].
- Inconsistent coercion: `str(file_texts[uri])` applied to file texts but `GUIDE` inserted raw — shared/polymath_shared/adapter/harness_guide.py:151-152 [DERIVED].
- `TITLES` unused inside this unit — shared/polymath_shared/adapter/harness_guide.py:26-29 [DERIVED]; consumer must be an importer [INFERRED: no internal reference].
- "PREFERRED" wording duplicated: guide §1 (`**PREFERRED**`) and the `prompt_text` default begin string — shared/polymath_shared/adapter/harness_guide.py:39, 138 [DERIVED].
- Doubled braces `{{kind: "status", ...}}` required inside the GUIDE f-string tables — shared/polymath_shared/adapter/harness_guide.py:52-54 [DERIVED].

## refactor notes
- URI constants are interpolation inputs: `GUIDE` embeds `{RECEIPT_SCHEMA_URI}`, `{SOURCES_URI}`, `{PROMPT_NAME}`, and `FILES`/`MIME`/`TITLES`/`RESOURCE_URIS` key off them — shared/polymath_shared/adapter/harness_guide.py:16-30, 95, 115, 131. Renaming any constant changes the published prompt and resources on both servers; blast radius = `mcp_server/polymath_mcp.py`, `orchestrator/orchestrator/mcp_server.py`, `shared/polymath_shared/adapter/transitions.py` [FACTS.importers].
- `FILES` paths must exist at those repo locations for the servers that read them ("the pinned Trail table moves with every re-pin") — shared/polymath_shared/adapter/harness_guide.py:7, 20-23 [DERIVED].
- Prose numbers 100/200/50/600 must stay in sync with `harness_receipt.schema.json` — shared/polymath_shared/adapter/harness_guide.py:21, 95-96, 105-106 [INFERRED: guide restates schema limits].
- `RESOURCE_URIS` tuple order is the publication order — shared/polymath_shared/adapter/harness_guide.py:30 [DERIVED].

## VERIFY
```verify
grep -Fq 'PROMPT_NAME = "run_governed_research"' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'SOURCES_URI = "polymath://trail/source-capabilities.csv"' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'governance/trail/data/source_capabilities.csv' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'harness guide files not supplied' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'Keep calling adapter_next until the run is terminal, then report adapter_result.' shared/polymath_shared/adapter/harness_guide.py
! grep -Fq '{ACTION_SCHEMA_URI}' shared/polymath_shared/adapter/harness_guide.py
test "$(grep -c -F 'polymath://adapter/' shared/polymath_shared/adapter/harness_guide.py)" -ge 3
```
