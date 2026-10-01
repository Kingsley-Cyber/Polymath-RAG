# unit: control/control/fleet_autopilot.py
anchor: control/control/fleet_autopilot.py:1-262

## purpose
Computes the desired fleet slot set each tick from Postgres backlog (stage_tickets) plus query/UI recency signals; the supervisor then parks/spawns slots to reconcile. No LLM, no heuristics — demand-driven membership with grace windows and a budget preflight. — control/control/fleet_autopilot.py:1-27, control/control/fleet_autopilot.py:139-141 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `desired_slots` | def | (conn, known_slots: set[str]) -> tuple[set[str], dict] | control/control/fleet_autopilot.py:139-261 | control/control/process_supervisor.py, control/control/stall_tracer.py (module importers, FACTS) |
| `_open_work` | def (private) | (conn, stages: tuple[str, ...]) -> int | control/control/fleet_autopilot.py:87-118 | — (internal) |
| `_last_query_age_s` | def (private) | (conn) -> float \| None | control/control/fleet_autopilot.py:121-128 | — (internal) |
| `_last_ui_age_s` | def (private) | (conn) -> float \| None | control/control/fleet_autopilot.py:131-136 | — (internal) |

Module constants: `ALWAYS` (43-44), `LANES` (47-72), `MODEL_GRACE_S` (77), `QUERY_GRACE_S` (79), `DROP_ORDER` (82), module-global `_last_demand: dict[str, float] = {}` (84).

## contracts

### desired_slots(conn, known_slots)
- in: `conn` must accept Postgres-style params (`ANY(%s)` at 114-118); `known_slots` = names the supervisor can actually run.
- out: `(desired, reasons)`; `reasons` values are exactly one of `"always"` (143), `f"{lane}: {n} open"` / `f"{lane}: grace"` (205), `f"query {qage:.0f}s ago"` (210, 217), `f"ui open {uiage:.0f}s ago"` (231, 234), `"dropped: over budget"` (251).
- pre: `runtime_signals` table may not exist yet — created IF NOT EXISTS on first call (123-124); `_last_demand` starts empty per process (84).
- post: `desired &= known_slots | ALWAYS` (236); every name in `desired` has a `reasons` entry [INFERRED — each add path writes a reason: 143-144, 204-205, 209-217, 230-234]; `reasons` may hold keys no longer in `desired` (236 filter, 250 discard).

### _open_work(conn, stages)
- out: COUNT of stage_tickets joined to runs + corpora with `st.archived_at IS NULL`, `st.status IN ('pending', 'ready', 'leased')`, `r.status IN ('intake', 'reconciling', 'degraded', 'query_ready')` — control/control/fleet_autopilot.py:110-118 [DERIVED]
- pre/post: debris (archived tickets, closed runs, deleted corpora) must never count — exclusion lives in the JOINs and status filters — control/control/fleet_autopilot.py:88-93 [DERIVED]

### _last_query_age_s / _last_ui_age_s
- out: seconds since `runtime_signals.updated_at` for key `'last_query'` (125-128) / `'ui_active'` (133-136); `None` when the key is absent.
- pre: only `_last_query_age_s` creates the table (123-124); `_last_ui_age_s` assumes it exists (131-136) — control/control/fleet_autopilot.py:123-124, control/control/fleet_autopilot.py:131-136 [INFERRED — no DDL in the ui helper]

## effect surface
- Postgres read: `stage_tickets` ⨝ `runs` ⨝ `corpora` (110-118); `runtime_signals` keys `'last_query'` (127) and `'ui_active'` (135); SQL clock `now()` (126, 135) — FACTS.tables_read also lists `now`, which is this function, not a table.
- Postgres write: DDL `CREATE TABLE IF NOT EXISTS runtime_signals (key text PRIMARY KEY, updated_at timestamptz NOT NULL)` (123-124). FACTS reports `tables_written: []` — the DDL is visible in SOURCE and contradicts that.
- Import (optional, guarded): `polymath_shared.runtime_budget.plan` (240, 259-260); called as `plan(",".join(sorted(desired)))`, return value unused (243).
- No files, network, or subprocesses in this unit. No env flags read; `POLYMATH_DOC_PARENT_MAP_ENABLED` appears only in a comment about upstream ticket minting (69-70).

## invariants
INVARIANT: `ALWAYS` == `{"control", "orchestrator", "intake", "mcp", "sidecar_embedder", "sidecar_reranker"}` — control/control/fleet_autopilot.py:43-44 [DERIVED]
  fails-if: sidecars leave ALWAYS → first query of a session degrades (measured 97 s queries while health stayed green, comment 38-42).
INVARIANT: `desired` ⊆ `known_slots | ALWAYS` — control/control/fleet_autopilot.py:236 [DERIVED]
  fails-if: autopilot demands slots the supervisor cannot spawn → reconcile never converges.
INVARIANT: extract workers ≤ 3 (`range(2, min(int(n_extract), 3) + 1)`) — control/control/fleet_autopilot.py:159-161 [DERIVED]
INVARIANT: doc_profile slots ≤ 6 (`min(int(n_dp), 6)`) — control/control/fleet_autopilot.py:170-172 [DERIVED]
INVARIANT: doc_parent_map slots ≤ 6 (`min(int(n_pm), 6)`) — control/control/fleet_autopilot.py:185-187 [DERIVED]
INVARIANT: `summaries2` added only when lane count `int(n) >= 2` — control/control/fleet_autopilot.py:190, control/control/fleet_autopilot.py:199-200 [DERIVED]
INVARIANT: grace window = `MODEL_GRACE_S` (300.0) for `sidecar_*` slots, `30.0` otherwise — control/control/fleet_autopilot.py:77, control/control/fleet_autopilot.py:202-203 [DERIVED]
INVARIANT: query/UI warmth applies only when age `< QUERY_GRACE_S` (600.0) — control/control/fleet_autopilot.py:79, control/control/fleet_autopilot.py:208, control/control/fleet_autopilot.py:229 [DERIVED]
INVARIANT: budget drop order == `["sidecar_reranker"]`, one victim — control/control/fleet_autopilot.py:82, control/control/fleet_autopilot.py:248-254 [DERIVED]
  fails-if: set still over budget after the drop → error logged, over-budget set returned anyway (255-258).

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` at 141; db — SELECT results 110-118, 125-127, 133-135; hidden module state `_last_demand` 84) — control/control/fleet_autopilot.py:141 [DERIVED]
idempotency: UNSAFE (each call re-stamps `_last_demand` timestamps at 149, 162, 173, 188, 199, so repeated calls with open work extend grace residency; the DDL at 123-124 is itself idempotent)

## failure behaviour
- `except Exception` around the budget loop (FACTS.fallbacks, line 245): any error from `plan` whose class name is not `"BudgetExceeded"` silently `break`s — the desired set is returned with no budget validation — control/control/fleet_autopilot.py:245-247 [DERIVED]
- `BudgetExceeded` is matched by `type(exc).__name__ != "BudgetExceeded"` string compare, not the class (246) — a renamed exception silently disables the gate — control/control/fleet_autopilot.py:246 [INFERRED — no class import anywhere in the unit]
- `ImportError` on `polymath_shared.runtime_budget` → `pass`: budget gate skipped entirely — control/control/fleet_autopilot.py:259-260 [DERIVED]
- Over budget with nothing left in DROP_ORDER → `log.error("autopilot: desired set over budget with nothing left to drop: ...")` and the set is returned anyway — control/control/fleet_autopilot.py:255-258 [DERIVED]
- Missing `runtime_signals` row → both age helpers return `None`, treated as "no warmth" (128, 136).
- This unit raises nothing itself; all anomalies surface via `log.warning`/`log.error` (252-253, 256-257).

## dumb-code flags
- Dead local: `extract_demand` assigned `False`/`True` (145, 151), never read — control/control/fleet_autopilot.py:145, control/control/fleet_autopilot.py:151 [DERIVED]
- No-op branch: `if True:   # GLiNER sidecar deleted (ADR-0017); no memory conflict remains` — control/control/fleet_autopilot.py:232 [DERIVED]
- Docstring/code mismatch: docstring promises drop order "(reranker first, then spacy)" (26-27) but `DROP_ORDER = ["sidecar_reranker"]` has no spacy entry — control/control/fleet_autopilot.py:26-27, control/control/fleet_autopilot.py:82 [DERIVED]
- Magic numbers: caps `3` (161), `6` (172, 187), threshold `2` (190); non-sidecar grace `30.0` (203); never-seen sentinel `-1e9` (202).
- DDL write hidden inside read-helper `_last_query_age_s` while `_last_ui_age_s` assumes the table exists — control/control/fleet_autopilot.py:123-124, control/control/fleet_autopilot.py:131-136 [DERIVED]
- `stale reasons`: entries survive the `&=` filter (236) and budget discard (250-251), so `reasons` can list slots not in `desired`.
- Duplicated reranker-warmth logic in two nearly identical blocks (query grace 208-217, UI warmth 229-234).

## refactor notes
- Renaming `desired_slots` or changing its `(set, dict)` return touches both importers: control/control/process_supervisor.py, control/control/stall_tracer.py (FACTS.importers); the supervisor consumes the set to park/spawn (3-4).
- `_open_work` status filters encode measured regressions: dropping `'pending'` froze the fleet (94-101); dropping `'query_ready'` from the run filter froze the tail 45+ min (102-109) — control/control/fleet_autopilot.py:94-109 [DERIVED]
- Scale-out caps pair with external limits: 3 cloud extract workers (158), six profile accounts (169), six Groq pMAP accounts (182-183) — raising caps without those resources overloads accounts.
- ALWAYS residency is the QUERY-PATH-RESIDENT-V1 contract; removing sidecars regresses first-query latency (38-42).
- `reasons` value strings are the unit's only observable explanation surface; consumers keying on them ("always", "dropped: over budget", …) break on rewording — control/control/fleet_autopilot.py:143, control/control/fleet_autopilot.py:205, control/control/fleet_autopilot.py:251 [INFERRED — no local consumer visible, but it is the returned diagnostic]

## VERIFY
```verify
grep -Fq 'MODEL_GRACE_S = 300.0' control/control/fleet_autopilot.py
grep -Fq 'DROP_ORDER = ["sidecar_reranker"]' control/control/fleet_autopilot.py
grep -Eq 'range\(2, min\(int\(n_extract\), 3\) \+ 1\)' control/control/fleet_autopilot.py
grep -Fq 'type(exc).__name__ != "BudgetExceeded"' control/control/fleet_autopilot.py
grep -Eq 'if True:.*ADR-0017' control/control/fleet_autopilot.py
test "$(grep -c -F 'sidecar_reranker' control/control/fleet_autopilot.py)" -ge 6
```
