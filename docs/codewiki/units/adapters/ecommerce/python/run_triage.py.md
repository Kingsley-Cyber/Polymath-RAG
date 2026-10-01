# unit: adapters/ecommerce/python/run_triage.py
anchor: adapters/ecommerce/python/run_triage.py:1-359

## purpose
Read-only triage of a stuck/suspicious run: lists everything the run can be wrong about, from two authorities — the state JSON and SQLite via `memory.py` ("the one module allowed to know SQLite exists") — adapters/ecommerce/python/run_triage.py:1-21. Each finding carries a severity (`BLOCKER`/`DEFECT`/`SMELL`), a stable code, where, what, and a fix; `ok` means no BLOCKER and no DEFECT. Nothing mutates. [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `triage` | def | (state_path: str, policies: dict, stale_minutes: int = 30) -> dict | adapters/ecommerce/python/run_triage.py:74-322 | `main` (line 351), CLI |
| `utilization_markdown` | def | (state_path: str) -> str | adapters/ecommerce/python/run_triage.py:325-328 | `main` (line 353) |
| `to_markdown` | def | (res: dict) -> str | adapters/ecommerce/python/run_triage.py:331-341 | `main` (line 352) |
| `main` | def | () -> int | adapters/ecommerce/python/run_triage.py:344-354 | `__main__` (line 357-358) |

Private: `_parse_ts` (42-49), `_Bugs` (52-59), `_schema_by_key` (62-71), `SEVERITIES` (38), `_NON_USD` (39).

## contracts

**triage(state_path, policies, stale_minutes=30)** — adapters/ecommerce/python/run_triage.py:74-322
- in: `state_path` loaded via `models.load_state(state_path)` (76); graph via `graphmod.load_graph(state.get("graph_file", "control_graph.yaml"))` (77); `policies` from `graphmod.load_policies()` at the CLI (351).
- out: dict `{"ok", "run_id", "node", "status", "verdict", "counts", "bugs", "checked_at": models.now()}` (319-322); `bugs` sorted by `(severity rank, code, where)` (317-318).
- pre: `state["run_id"]` must exist — used unguarded at 140. [INFERRED: missing key raises KeyError before any bug is recorded]
- post: `ok == (counts["BLOCKER"] == 0 and counts["DEFECT"] == 0)` (319).

**to_markdown(res)** — adapters/ecommerce/python/run_triage.py:331-341
- in: the `triage` result dict.
- out: header line + markdown table `| severity | code | where | what | fix |`; cells escape `|` -> `\|` and newlines -> space (337-340).

**utilization_markdown(state_path)** — adapters/ecommerce/python/run_triage.py:325-328
- out: `"\n## Evidence utilization (docs/21)\n\n" + _util.to_markdown(_util.compute(st)) + "\n"` (328); imports `utilization` locally (326).

**main()** — adapters/ecommerce/python/run_triage.py:344-354
- flags: `--state` (required), `--markdown`, `--stale-minutes` default 30 (347-349).
- out: prints markdown or `json.dumps(res, indent=1, ensure_ascii=False)` (352); exit `0 if res["ok"] else 1` (354).

## effect surface
- SQLite: no direct access, no tables read/written (FACTS `tables_read`/`tables_written` empty); reached only through `memory.get_run` (140), `memory.check_drift` (156), `memory.run_audit` (166), `memory.pending_action` (183).
- Files: state JSON read via `models.load_state` (76); graph file, default `"control_graph.yaml"` (77).
- Stdout: two `print` calls (352-353).
- Subprocesses / network / env flags: none visible.

## invariants
INVARIANT: `counts["BLOCKER"] == 0 and counts["DEFECT"] == 0` ⟺ `res["ok"]` — adapters/ecommerce/python/run_triage.py:319 [DERIVED]
  fails-if: any BLOCKER or DEFECT finding makes the CLI exit non-zero (354).
INVARIANT: default `stale_minutes` 30 (signature, 74) == default `--stale-minutes` 30 (349) — adapters/ecommerce/python/run_triage.py:74,349 [DERIVED]
  fails-if: changing one without the other makes CLI staleness differ from library calls.
INVARIANT: `min_independent_sources` fallback `3` at both call sites — adapters/ecommerce/python/run_triage.py:109,259 [DERIVED]
  fails-if: divergent fallbacks flag a gap as starved in one check but supported in the other.
INVARIANT: `max_research_rounds` fallback `3` — adapters/ecommerce/python/run_triage.py:110 [DERIVED]
INVARIANT: `message[:400]`, `fix[:300]` truncation in `_Bugs.add` — adapters/ecommerce/python/run_triage.py:59 [DERIVED]
  fails-if: longer text silently truncated.
INVARIANT: duplicate observation ⟺ same `(quote_ref, gap_id)` pair; one quote may answer two gaps — adapters/ecommerce/python/run_triage.py:247 [DERIVED]
INVARIANT: `live_actions > 1` ⇒ BLOCKER `LIVE_ACTIONS_MULTI` (one-writer law) — adapters/ecommerce/python/run_triage.py:168-170 [DERIVED]
INVARIANT: bug sort order = `(enumerate(SEVERITIES) rank, code, where)` — adapters/ecommerce/python/run_triage.py:317-318 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `_dt.datetime.now(_dt.timezone.utc)` at adapters/ecommerce/python/run_triage.py:80, per FACTS.nondeterminism; result key `checked_at: models.now()` at 322 is also time-derived [INFERRED])
idempotency: SAFE — "Nothing here mutates anything" (docstring, line 8); only reads state/SQLite and prints.

## failure behaviour
- `except Exception` at 85 → handled: becomes BLOCKER `NODE_UNKNOWN` (84-88); unknown node does not crash triage.
- `except Exception` at 99 → SWALLOWED (`pass`, 99-100): graph dead-end check silently skipped on an odd graph; caller sees no `GRAPH_DEAD_END` finding.
- `except Exception` at 136 → SWALLOWED (`pass`, 136-137): starvation/sourcing checks (docs/20) silently skipped; caller sees no `STARVED_REJECTION`/`CONCEPT_UNSOURCED`.
- `except Exception as exc` at 312 → handled: becomes SMELL `QUALIFY_UNAVAILABLE` — "triage must always produce output" (312-314).
- CLI exit codes: 0 ok, 1 otherwise (354).
- Unhandled: `state["run_id"]` KeyError at 140 if absent. [INFERRED]

## dumb-code flags
- `main` line 353: `print(...) if getattr(a, 'markdown', False) and getattr(a, 'state', None) else None` — conditional-expression-as-statement; argparse always sets both attrs, so the `getattr` guards are dead branches (353).
- Duplicated fallback literals: `3` for `min_independent_sources` at 109 and 259; `3` for `max_research_rounds` at 110; `30` for staleness at 74 and 349.
- Hard-coded node-name lists: `("normalize_supplier", "qualify", "stop", "report")` (130), `("web_research", "curate", "gaps", "challenge")` (274), `("transform", "gate")` (94), `("WORKING_HYPOTHESIS", "CHALLENGED", "SUPPORTED")` (281).
- QUALIFY exclusion prefixes `("state/SQLite", "no run row", "event log", "terminal run still")` hard-code another module's message wording (311).
- `cell` lambda re-created on every loop iteration in `to_markdown` (339).

## refactor notes
- Bug `code` strings (e.g. `NODE_DISAGREE`, `STARVED_REJECTION`) are the docstring-declared "stable code" contract (line 10); renaming breaks any consumer matching on them.
- `SEVERITIES` tuple order doubles as sort rank (317) — reordering reshuffles all output.
- `_schema_by_key` depends on `controller.OUTPUT_SPECS` tuple shape `(key, schema, _is_list)` and `controller.SCHEMA_BY_KEY` (66-70); a controller shape change breaks schema re-validation (206-221).
- The QUALIFY prefix filter (311) must track `qualify.py`'s violation message prefixes verbatim or duplicates reappear.
- Exit-code contract 0/1 (354) and `--state` required (348) are the CLI contract.
- `triage`'s returned dict keys (319-322) and the markdown table columns (337) are the output schema for `to_markdown` and callers.

## VERIFY
```verify
grep -Fq 'def triage(state_path: str, policies: dict, stale_minutes: int = 30) -> dict:' adapters/ecommerce/python/run_triage.py
grep -Fq 'SEVERITIES = ("BLOCKER", "DEFECT", "SMELL")' adapters/ecommerce/python/run_triage.py
grep -Fq 'now = _dt.datetime.now(_dt.timezone.utc)' adapters/ecommerce/python/run_triage.py
grep -Fq 'return 0 if res["ok"] else 1' adapters/ecommerce/python/run_triage.py
grep -Eq 'except Exception( as exc)?:' adapters/ecommerce/python/run_triage.py
test "$(grep -c -F 'bugs.add(' adapters/ecommerce/python/run_triage.py)" -ge 30
! grep -Fq 'import sqlite3' adapters/ecommerce/python/run_triage.py
```
