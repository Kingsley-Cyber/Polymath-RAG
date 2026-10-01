# unit: shared/polymath_shared/adapter/run_view.py
anchor: shared/polymath_shared/adapter/run_view.py:1-184

## purpose
Read model behind the web UI's Research section: the runs list and one run's view (T5: owner's registry coordinates + the journal a run's dossier is rendered from) — shared/polymath_shared/adapter/run_view.py:1-2 [DERIVED].
Observes only: "nothing here writes, scores or decides (TrailSignal's score is its own, LAW 1)" — shared/polymath_shared/adapter/run_view.py:4 [DERIVED].
A run's output is recompiled from step outputs through the fixed readers (gap A-15); the stored result stays the untouched record — shared/polymath_shared/adapter/run_view.py:4-5 [DERIVED].
Field text passes through as data; UI renders it as text, never HTML — shared/polymath_shared/adapter/run_view.py:5-6 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| title_of | def | (inp: Any) -> str | shared/polymath_shared/adapter/run_view.py:23-30 | orchestrator/orchestrator/api/adapter.py (module import) |
| outcome_of | def | (status: str, scores: int \| None, refusals: int \| None, gap: Any) -> str | shared/polymath_shared/adapter/run_view.py:33-54 | orchestrator/orchestrator/api/adapter.py (module import) |
| list_runs | def | (conn, principal_id: str \| None, *, status=None, adapter_id=None, limit=50, before=None) -> list[dict] | shared/polymath_shared/adapter/run_view.py:66-70 | orchestrator/orchestrator/api/adapter.py (module import) |
| progress_of | def | (manifest_steps: dict, stored_steps: list[dict], state: RunState) -> list[dict] | shared/polymath_shared/adapter/run_view.py:73-97 | orchestrator/orchestrator/api/adapter.py (module import) |
| all_qualifications | def | (stored_steps: list[dict]) -> list[dict] | shared/polymath_shared/adapter/run_view.py:100-116 | orchestrator/orchestrator/api/adapter.py (module import) |
| registry_of | def | (state: RunState, lineage: dict) -> dict \| None | shared/polymath_shared/adapter/run_view.py:119-129 | orchestrator/orchestrator/api/adapter.py (module import) |
| dossier_journal | def | (conn, run_id: str, directory: Path \| None = None) -> dict | shared/polymath_shared/adapter/run_view.py:132-152 | orchestrator/orchestrator/api/adapter.py (module import) |
| build_view | def | (conn, run_id: str, directory: Path \| None = None, *, owner: bool = False) -> dict | shared/polymath_shared/adapter/run_view.py:155-184 | orchestrator/orchestrator/api/adapter.py (module import) |
| SECTION_KEYS | constant (tuple, 10 keys) | module-level | shared/polymath_shared/adapter/run_view.py:17-18 | — |

FACTS.importers lists only `orchestrator/orchestrator/api/adapter.py`; per-symbol usage is not distinguishable.

## contracts
**title_of** — in: any input value. out: first non-empty `str` under keys in order `("seed", "seed_idea", "question", "topic", "brief")`, whitespace-normalized via `" ".join(v.split())`; `text if len(text) <= 140 else text[:139] + "…"`; else `"Untitled run"` — shared/polymath_shared/adapter/run_view.py:23-30 [DERIVED].

**outcome_of** — in: status string + counts only ("the score VALUES are TrailSignal's and never read here"). out literal map: `awaiting_agent`→`"Waiting for your agent"`, `awaiting_harness`→`"Waiting for web research"`, `created`/`running`→`"Running"`, `cancelled`→`"Cancelled"`, `failed`→`"Failed"`, `terminal_gap`→`f"Stopped: {code}"` or `"Stopped early"`, else counts: `f"{scores} scored"` (+ `f", {refusals} refused"`), refusal lines `"TrailSignal refused the score"` / `f"TrailSignal refused all {refusals} scores"`, `scores == 0 and refusals == 0`→`"Completed, nothing scored"`, fallback `"Completed"` — shared/polymath_shared/adapter/run_view.py:33-54 [DERIVED].

**list_runs** — pre: `principal_id=None` means owner/trusted-local caller sees every run; a principal sees only their own. out: `_summary` rows with keys `run_id, adapter_id, adapter_version, title, status, current_step_id, steps_accepted, harness_actions, started_at, updated_at, finished_at, agent_identity, owner, outcome`; delegates to `store.list_runs(owner_principal_id=principal_id, ...)` with defaults `limit=50` — shared/polymath_shared/adapter/run_view.py:57-70 [DERIVED].

**progress_of** — in: manifest steps, stored step rows, RunState. out: one row per manifest step in manifest order, `state` ∈ `done · current · waiting_agent · waiting_harness · failed · skipped · pending`, plus `visits` = count of stored rows for that step. Current-step override applies only when `not state.terminal`; step state otherwise from newest visit's status (`visits[-1]["status"]`), with `_DONE={"accepted","executed"}`, `_FAILED={"failed","rejected"}`, `skipped`, `issued`→`current`, else `pending` — shared/polymath_shared/adapter/run_view.py:73-97, 19-20 [DERIVED].

**all_qualifications** — in: stored step rows. out: every qualification from every step whose output satisfies `trail_client.fills(o.get("operation_kind"), "qualifications")`, in step order, deduped by `q.get("record_id") or id(q)`; includes the pre-HR4 singular `o["qualification"]` dict — shared/polymath_shared/adapter/run_view.py:100-116 [DERIVED].

**registry_of** — in: RunState + lineage dict. out: `{"snapshot", "snapshot_ids", "priors", "territories"}` (snapshot ids from `lineage.get("registry_snapshot_ids")`, priors/territories via `service._gather(state.outputs, ..., state.output_order)`, dict entries only); returns `None` when all four are empty — shared/polymath_shared/adapter/run_view.py:119-129 [DERIVED].

**dossier_journal** — pre: run must exist (else `service.UnknownRun`) and `state.adapter_id in dossier.DOSSIER_ADAPTERS` (else `dossier.NoDossier`). out: `dossier.journal_from_store(run, steps, result)`; `result` compiled only when `state.terminal`, with `persist=False`, and `qualifications` merged into output when steps hold any; non-terminal runs get `result = None` and read as in progress — shared/polymath_shared/adapter/run_view.py:132-152 [DERIVED].

**build_view** — pre: run must exist (else `service.UnknownRun`). out: dict keys `run, progress, sections, other_output_keys, contradictions, unknowns, stored_result_shadowed, report`, plus `registry` only when `owner=True`. Result recompiled with `output=None, persist=False`; `sections` = SECTION_KEYS present in recompiled output, then `qualifications` from `all_qualifications(steps)` merged over it — shared/polymath_shared/adapter/run_view.py:155-184 [DERIVED].

## effect surface
- Postgres tables: none directly (FACTS `tables_read: []`, `tables_written: []`). All reads via `store.list_runs` (shared/polymath_shared/adapter/run_view.py:69), `store.load_run` (137, 157), `store.list_steps` (143, 162), `store.load_result` (165) [DERIVED].
- Writes: none — both compiles pass `persist=False` (shared/polymath_shared/adapter/run_view.py:146, 163) [DERIVED].
- Files: `directory` param forwarded to `service.manifest_for` (shared/polymath_shared/adapter/run_view.py:146, 161) [DERIVED].
- Network / Qdrant / subprocess / env flags: none visible in this file — imports are only `Path`, `Any`, and siblings `dossier, service, store, trail_client`, `RunState` (shared/polymath_shared/adapter/run_view.py:9-13) [DERIVED].

## invariants
INVARIANT: title length ≤ 140 chars (truncation writes 139 chars + `"…"`) — shared/polymath_shared/adapter/run_view.py:29 [DERIVED]
  fails-if: UI titles overflow layout; longer inputs silently truncated.
INVARIANT: `len(SECTION_KEYS)` = 10, `"qualifications"` ∈ SECTION_KEYS — shared/polymath_shared/adapter/run_view.py:17-18 [DERIVED]
  fails-if: Research screens drop or add sections unexpectedly.
INVARIANT: `"qualifications"` in `sections` = `all_qualifications(steps)` result whenever non-empty, overriding the compiled output's value — shared/polymath_shared/adapter/run_view.py:175-176 [DERIVED]
  fails-if: UI shows stale compiled qualifications instead of per-step records.
INVARIANT: `other_output_keys` ∩ SECTION_KEYS = ∅ — shared/polymath_shared/adapter/run_view.py:177 [DERIVED]
  fails-if: rendered sections also appear in the by-name-only list.
INVARIANT: `registry` key present ⇔ `owner=True` — shared/polymath_shared/adapter/run_view.py:183 [DERIVED]
  fails-if: a principal (friend) sees the owner's registry coordinates.
INVARIANT: `stored_result_shadowed` = `bool(stored) and not stored_quals and bool(output.get("qualifications"))` — shared/polymath_shared/adapter/run_view.py:181 [DERIVED]
  fails-if: pre-A-15 runs' data loss goes unflagged.
INVARIANT: `report.available` ⇔ `state.adapter_id in dossier.DOSSIER_ADAPTERS` — shared/polymath_shared/adapter/run_view.py:182 [DERIVED]
  fails-if: UI offers GET /adapter/{id}/report for an adapter with no dossier.
INVARIANT: dossier_journal compiles a result ⇔ `state.terminal` — shared/polymath_shared/adapter/run_view.py:145-146 [DERIVED]
  fails-if: a live run renders a finished dossier.
INVARIANT: qualification records unique by `record_id` — shared/polymath_shared/adapter/run_view.py:112 [DERIVED]
  fails-if: same record listed twice when steps repeat.

## determinism & idempotency
determinism: DETERMINISTIC (pure transforms over stored rows; imports contain no clock/random/uuid/network — shared/polymath_shared/adapter/run_view.py:9-13). Caveat: dedupe key fallback `id(q)` is process-address based — shared/polymath_shared/adapter/run_view.py:112 [INFERRED: affects only key choice, not output order/content within one call].
idempotency: SAFE (read-only; `persist=False` on both compile calls — shared/polymath_shared/adapter/run_view.py:146, 163; module docstring "nothing here writes" — shared/polymath_shared/adapter/run_view.py:4).

## failure behaviour
- `service.UnknownRun(run_id)` raised by `dossier_journal` and `build_view` when `store.load_run` returns falsy — shared/polymath_shared/adapter/run_view.py:137-139, 157-159 [DERIVED].
- `dossier.NoDossier(state.adapter_id)` raised by `dossier_journal` when adapter not in `dossier.DOSSIER_ADAPTERS` — shared/polymath_shared/adapter/run_view.py:141-142 [DERIVED].
- No try/except in the module; nothing swallowed here — shared/polymath_shared/adapter/run_view.py:1-184 [DERIVED].

## dumb-code flags
- Magic numbers `140` / `139` in title truncation — shared/polymath_shared/adapter/run_view.py:29 [DERIVED].
- `limit: int = 50` default buried in signature — shared/polymath_shared/adapter/run_view.py:67 [DERIVED].
- `"qualifications"` literal repeated at lines 17, 106, 148, 176, 181 (constant, fills predicate, two merges, shadow flag) — shared/polymath_shared/adapter/run_view.py:17,106,148,176,181 [DERIVED].
- Status literals `"awaiting_agent"` / `"awaiting_harness"` duplicated across `outcome_of` (35, 37) and `progress_of` (84) with different output mappings — shared/polymath_shared/adapter/run_view.py:35,37,84 [DERIVED].
- Legacy branch for pre-HR4 singular key `o.get("qualification")` — shared/polymath_shared/adapter/run_view.py:109-110 [DERIVED].
- `outcome_of` fallthrough: `scores=None` with `refusals=0`, or `scores=0` with `refusals=None`, skips the `scores == 0 and refusals == 0` guard and returns `"Completed"` — shared/polymath_shared/adapter/run_view.py:48-54 [INFERRED: strict `== 0` fails on None].
- `progress_of` uses only the newest visit's status (`visits[-1]`); earlier visit states are invisible except via `visits` count — shared/polymath_shared/adapter/run_view.py:82 [DERIVED].

## refactor notes
- Sole known importer: `orchestrator/orchestrator/api/adapter.py` (FACTS.importers) — any public signature change ripples there.
- Private cross-module helpers from `service` are hard dependencies: `service._ts` (61, 149-151), `service._registry_snapshot` (123), `service._gather` (124-125), `service._compile_result` (146, 163), `service.manifest_for` (146, 161); renaming them in `service` breaks this file — shared/polymath_shared/adapter/run_view.py:61,123-125,146,149-151,161,163 [DERIVED].
- `_summary` consumes 15 stored-row keys verbatim (`run_id, adapter_id, adapter_version, input, status, current_step_id, steps_accepted, harness_action_count, created_at, updated_at, terminal_at, agent_identity, owner_principal_id, scores, refusals, gap`) — `store.list_runs` row shape is a hard contract — shared/polymath_shared/adapter/run_view.py:57-63 [DERIVED].
- `SECTION_KEYS` is exported (no underscore); its membership of `"qualifications"` interacts with the override at line 176 — change either only together — shared/polymath_shared/adapter/run_view.py:17-18,175-176 [DERIVED].
- `trail_client.fills(operation_kind, "qualifications")` predicate couples qualification discovery to trail_client's fill table — shared/polymath_shared/adapter/run_view.py:106 [DERIVED].

## VERIFY
```verify
grep -Fq 'Untitled run' shared/polymath_shared/adapter/run_view.py
grep -Fq 'Waiting for your agent' shared/polymath_shared/adapter/run_view.py
grep -Fq 'text[:139] + "…"' shared/polymath_shared/adapter/run_view.py
grep -Fq 'limit: int = 50' shared/polymath_shared/adapter/run_view.py
grep -Fq 'persist=False' shared/polymath_shared/adapter/run_view.py
! grep -Fq 'persist=True' shared/polymath_shared/adapter/run_view.py
grep -Fq 'raise service.UnknownRun(run_id)' shared/polymath_shared/adapter/run_view.py
grep -Fq 'SECTION_KEYS' shared/polymath_shared/adapter/run_view.py
```
