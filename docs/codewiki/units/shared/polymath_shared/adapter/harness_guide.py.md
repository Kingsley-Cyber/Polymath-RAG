# unit: shared/polymath_shared/adapter/harness_guide.py
anchor: shared/polymath_shared/adapter/harness_guide.py:1-182

## purpose
Publishes the single operating guide (`AUTORESEARCH-SOURCES-AND-HARNESS-V1`) for any MCP-capable agent harness, exposed by BOTH MCP servers as the prompt `run_governed_research` and as resources, so a harness that has never seen this repository can run a governed adapter end to end — shared/polymath_shared/adapter/harness_guide.py:1-13, 157-160 [DERIVED].
Source- and harness-neutral: what TrailSignal admits is served as TrailSignal's own pinned source table, never restated in the guide — shared/polymath_shared/adapter/harness_guide.py:5-7 [DERIVED].
Pure module: the servers read the files named in `FILES` and pass their text in; this module reads nothing itself — shared/polymath_shared/adapter/harness_guide.py:7, 27 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `prompt_text` | def | `(adapter_id: str = "", seed: str = "") -> str` | shared/polymath_shared/adapter/harness_guide.py:164-172 | module imported by mcp_server/polymath_mcp.py, orchestrator/orchestrator/mcp_server.py, shared/polymath_shared/adapter/transitions.py (FACTS.importers) |
| `resources` | def | `(file_texts: Mapping[str, str]) -> dict[str, tuple[str, str]]` | shared/polymath_shared/adapter/harness_guide.py:175-182 | same three importers (per-symbol attribution not in FACTS) |
| `PROMPT_NAME`, `PROMPT_DESCRIPTION`, `AGENT_REACH_REPO`, `GUIDE_URI`, `RECEIPT_SCHEMA_URI`, `ACTION_SCHEMA_URI`, `SOURCES_URI`, `FILES`, `MIME`, `TITLES`, `RESOURCE_URIS`, `GUIDE` | module constants | str / dict / tuple / str | shared/polymath_shared/adapter/harness_guide.py:18-37, 39-161 | same three importers |

## contracts

`prompt_text(adapter_id, seed)` — shared/polymath_shared/adapter/harness_guide.py:164-172
- in: `adapter_id: str = ""`, `seed: str = ""` (both default empty) — :164 [DERIVED]
- out: `GUIDE + "\n" + begin + ". Keep calling adapter_next until the run is terminal (you answer every step; research steps run in the user's local Agent Reach), then report adapter_result.\n"` — :171-172 [DERIVED]
- begin default: `"Begin: call adapter_list(), pick the PREFERRED adapter"`; with `adapter_id`: `f"Begin: run the adapter '{adapter_id}'"` (backticked); with `seed`: appends `f", and start it with seed: {seed!r}"` — :166-170 [DERIVED]
- pre: none. post: result starts with `GUIDE` and ends with `then report adapter_result.\n` — :171-172 [DERIVED]

`resources(file_texts)` — shared/polymath_shared/adapter/harness_guide.py:175-182
- in: `file_texts: Mapping[str, str]` keyed by every uri in `FILES` — :176-177 [DERIVED]
- pre: `set(FILES) ⊆ set(file_texts)`; else `ValueError` — :177-179 [DERIVED]
- post: dict of 4 entries: `GUIDE_URI -> (MIME[GUIDE_URI], GUIDE)` plus one `(MIME[uri], str(file_texts[uri]))` per `FILES` uri — :180-182 [DERIVED]
- MIME per uri: `GUIDE_URI: "text/markdown"`, both schema uris `"application/json"`, `SOURCES_URI: "text/csv"` — :31-32 [DERIVED]

## effect surface
- Postgres tables read/written: none (FACTS `tables_read` / `tables_written` empty).
- Files: none opened by this module. `FILES` names the repo files the servers read: `contracts/adapter/v1/harness_receipt.schema.json`, `contracts/adapter/v1/harness_action.schema.json`, `governance/trail/data/source_capabilities.csv` — shared/polymath_shared/adapter/harness_guide.py:28-30 [DERIVED]
- Qdrant / network / subprocess / env flags: none visible in SOURCE.

## invariants
INVARIANT: `len(RESOURCE_URIS) == 4 == len(MIME) == len(TITLES)` (GUIDE, RECEIPT_SCHEMA, ACTION_SCHEMA, SOURCES) — shared/polymath_shared/adapter/harness_guide.py:31-37 [DERIVED]
  fails-if: a published uri without a MIME/TITLES entry KeyErrors at :180-182 or drops the resource's metadata.
INVARIANT: `set(FILES) == set(RESOURCE_URIS) - {GUIDE_URI}` (3 entries; the guide text is in-module `GUIDE`, never file-read) — shared/polymath_shared/adapter/harness_guide.py:28-30, 37, 39 [DERIVED]
  fails-if: a new RESOURCE_URIS entry without a FILES row silently serves nothing for it.
INVARIANT: `resources(...)` return size `== 4` (1 guide entry + `len(FILES)`) — shared/polymath_shared/adapter/harness_guide.py:180-182 [DERIVED]
  fails-if: clients of both servers lose a published resource.
INVARIANT: `resources` returns normally only when `set(FILES) ⊆ set(file_texts)`, else raises — shared/polymath_shared/adapter/harness_guide.py:177-179 [DERIVED]
  fails-if: guard removed -> KeyError instead of a named error.
INVARIANT: every `prompt_text` result starts with `GUIDE` and ends with `then report adapter_result.\n` — shared/polymath_shared/adapter/harness_guide.py:171-172 [DERIVED]
  fails-if: harnesses lose the loop-until-terminal instruction.

## determinism & idempotency
determinism: DETERMINISTIC (pure string/dict assembly; only imports are `from __future__ import annotations` and `from collections.abc import Mapping` — shared/polymath_shared/adapter/harness_guide.py:14-16) [DERIVED]
idempotency: SAFE (no side effects; no I/O, clock, random, or network anywhere in SOURCE)

## failure behaviour
No try/except anywhere; nothing is swallowed. Single explicit raise: `ValueError(f"harness guide files not supplied: {missing}")` with `missing = sorted(set(FILES) - set(file_texts))` — shared/polymath_shared/adapter/harness_guide.py:177-179 [DERIVED]; the calling MCP server sees this ValueError. FACTS lists no fallbacks.
Codes named in the guide text (`HUMAN_ACTION_REQUIRED` :95, `CHALLENGE_PAGE_AS_EVIDENCE` :111, `SOURCE_UNREGISTERED`, `SOURCE_STAGE_UNSUITABLE`, `SOURCE_ROLE_UNSUITABLE`, `SUPPLY_IS_NOT_DEMAND`, `HYPOTHESIS_LINK_MISSING`, `STALE_BEYOND_POLICY` :153-154) are documented strings for other components, not raised here — shared/polymath_shared/adapter/harness_guide.py:95-154 [DERIVED].

## dumb-code flags
- Policy numbers hardcoded as prose inside `GUIDE`, not shared constants: 100 sources / 200 observations / 50 limitations (:119), 600-char excerpt (:129), 3 platforms (price) / 1 (risk) / 3 (ANCHOR) (:151-152), HTTP 429 (:60), HTTP 422 (:72) — shared/polymath_shared/adapter/harness_guide.py:60-152 [DERIVED]. They must hand-match `harness_receipt.schema.json` (:29), a separate file — duplication risk [INFERRED: schema lives in another file per FILES].
- `str(file_texts[uri])` silently stringifies a non-str value instead of rejecting it — shared/polymath_shared/adapter/harness_guide.py:182 [DERIVED].
- `PROMPT_DESCRIPTION` restates guide section names ("start, the adapter_next loop, ... the receipt, and what TrailSignal admits") in a second copy — shared/polymath_shared/adapter/harness_guide.py:19-21 [DERIVED]; drifts when `GUIDE` sections change.

## refactor notes
- `PROMPT_NAME = "run_governed_research"` (:18) and the four `polymath://` uris (:23-26) are the published contract of BOTH MCP servers (:157-160 says both publish this prompt and these resources); renaming breaks every connected harness — shared/polymath_shared/adapter/harness_guide.py:18-26, 157-160 [DERIVED].
- `FILES` paths pin repo locations; the comment says the pinned Trail table "moves with every re-pin" — moving `contracts/adapter/v1/*` or `governance/trail/data/source_capabilities.csv` breaks resource serving — shared/polymath_shared/adapter/harness_guide.py:27-30 [DERIVED].
- Blast radius: mcp_server/polymath_mcp.py, orchestrator/orchestrator/mcp_server.py, shared/polymath_shared/adapter/transitions.py import this module (FACTS.importers); the `resources` ValueError contract and 4-entry shape are what they depend on.
- Numeric limits embedded in `GUIDE` (:119, 129, 151-152) must change in lockstep with the receipt schema file — shared/polymath_shared/adapter/harness_guide.py:29 [INFERRED].

## VERIFY
```verify
grep -Fq 'PROMPT_NAME = "run_governed_research"' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'GUIDE_URI = "polymath://adapter/guide"' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'governance/trail/data/source_capabilities.csv' shared/polymath_shared/adapter/harness_guide.py
grep -Fq 'harness guide files not supplied' shared/polymath_shared/adapter/harness_guide.py
grep -Eq 'harness-(receipt|action).schema.json' shared/polymath_shared/adapter/harness_guide.py
test "$(grep -c -F 'adapter_next' shared/polymath_shared/adapter/harness_guide.py)" -ge 3
! grep -Fq 'import requests' shared/polymath_shared/adapter/harness_guide.py
```
