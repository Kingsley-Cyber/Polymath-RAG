# unit: adapters/ecommerce/python/memory.py
anchor: adapters/ecommerce/python/memory.py:1-488

## purpose
SQLite loop-memory adapter for the opportunity-research skill; per its own law, "the ONLY module allowed to know SQLite exists" — adapters/ecommerce/python/memory.py:1 [DERIVED]. Persists runs, actions, events, checks, context envelopes, and Work Graph nodes for `controller.py` (sole transition authority; this module "persists, it never decides") — adapters/ecommerce/python/memory.py:7-8 [DERIVED]. Also serves read-side consumers: `qualify.py` via `run_audit` (docs/15) — adapters/ecommerce/python/memory.py:307 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| db_path | def | () -> str | adapters/ecommerce/python/memory.py:25-29 | — |
| connect | def | () -> sqlite3.Connection | adapters/ecommerce/python/memory.py:35-51 | — |
| config_hashes | def | () -> dict | adapters/ecommerce/python/memory.py:107-122 | — |
| create_run | def | (run_id, objective, node) -> None | adapters/ecommerce/python/memory.py:130-141 | — |
| get_run | def | (run_id) -> dict \| None | adapters/ecommerce/python/memory.py:144-147 | — |
| check_drift | def | (run) -> list[str] | adapters/ecommerce/python/memory.py:150-152 | — |
| update_run | def | (run_id, \*, node, status, verdict, terminal_reason, cycle, bump_revision) -> None | adapters/ecommerce/python/memory.py:155-174 | — |
| pending_action | def | (run_id) -> dict \| None | adapters/ecommerce/python/memory.py:178-183 | — |
| create_action | def | (run_id, node, action_type, request) -> dict | adapters/ecommerce/python/memory.py:186-211 | — |
| apply_submission | def | (run_id, node, payload) -> tuple[str, str] | adapters/ecommerce/python/memory.py:214-268 | — |
| attach_envelope | def | (action_id, run_id, node, envelope) -> None | adapters/ecommerce/python/memory.py:272-283 | — |
| get_envelope | def | (action_id) -> dict \| None | adapters/ecommerce/python/memory.py:286-290 | — |
| load_work_nodes | def | (run_id, node_type=None) -> list[dict] | adapters/ecommerce/python/memory.py:293-303 | — |
| run_audit | def | (run_id) -> dict | adapters/ecommerce/python/memory.py:306-339 | — |
| candidate_recurrence | def | () -> list[dict] | adapters/ecommerce/python/memory.py:342-360 | — |
| load_candidates | def | (names) -> list[dict] | adapters/ecommerce/python/memory.py:363-376 | — |
| latest_checkpoint | def | (run_id) -> dict \| None | adapters/ecommerce/python/memory.py:379-384 | — |
| record_event | def | (run_id, event_type, payload=None, \*\*kw) -> None | adapters/ecommerce/python/memory.py:401-403 | — |
| write_check | def | (run_id, check_type, level, status, metrics, reasons=None, subject_id=None) -> None | adapters/ecommerce/python/memory.py:406-416 | — |
| sync_work_nodes | def | (run_id, state) -> int | adapters/ecommerce/python/memory.py:460-487 | — |

FACTS lists no importers. Docstrings name two external consumers: `controller.py` — adapters/ecommerce/python/memory.py:7 [DERIVED], and `qualify.py` — adapters/ecommerce/python/memory.py:307 [DERIVED].

## contracts

**connect() — adapters/ecommerce/python/memory.py:35-51**
- in: none; env `OPPORTUNITY_RESEARCH_DB` optional — adapters/ecommerce/python/memory.py:26 [DERIVED]
- out: `sqlite3.Connection` with `row_factory = sqlite3.Row` — adapters/ecommerce/python/memory.py:39 [DERIVED]
- post: `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 5000` on every call — adapters/ecommerce/python/memory.py:40-41 [DERIVED]
- post: first connect per db path per process also sets `journal_mode = WAL`, `synchronous = FULL`, and runs `_ensure_schema` — adapters/ecommerce/python/memory.py:43-50 [DERIVED]
- pre: `SKILL_ROOT/sql/001_initial.sql` and `sql/002_context.sql` must exist — adapters/ecommerce/python/memory.py:20-21, 58, 71 [DERIVED]

**create_run(run_id, objective, node) — adapters/ecommerce/python/memory.py:130-141**
- post: `INSERT OR IGNORE INTO runs` with `status='running'` and all six `config_hashes()` values pinned — adapters/ecommerce/python/memory.py:133-140 [DERIVED]
- post: emits `RUN_CREATED` event carrying objective + hashes — adapters/ecommerce/python/memory.py:141 [DERIVED]
- repeat with same run_id: ignored (OR IGNORE) — adapters/ecommerce/python/memory.py:133 [DERIVED]

**create_action(run_id, node, action_type, request) — adapters/ecommerce/python/memory.py:186-211**
- out: action dict; `action_id = "act_" + _h({"run","node","type","revision"})` — adapters/ecommerce/python/memory.py:197-199 [DERIVED]
- post: if a live `PENDING`/`RUNNING` action exists, returns THAT one with `attempt_count+1` — never a duplicate — adapters/ecommerce/python/memory.py:189-195 [DERIVED]
- post: new rows insert with `status='PENDING'`, `attempt_count=1` — adapters/ecommerce/python/memory.py:204 [DERIVED]

**apply_submission(run_id, node, payload) — adapters/ecommerce/python/memory.py:214-268**
- out: `(disposition, action_id)` with disposition ∈ `APPLY | ALREADY_APPLIED | CONFLICT` — adapters/ecommerce/python/memory.py:215-219, 231, 244, 255, 268 [DERIVED]
- pre: `BEGIN IMMEDIATE` taken before the SELECTs (one-writer law) — adapters/ecommerce/python/memory.py:223-226 [DERIVED]
- post: exact re-submit of a `SUCCEEDED` result_hash → `ALREADY_APPLIED` — adapters/ecommerce/python/memory.py:227-231 [DERIVED]
- post: different payload at a node the run has not advanced past, same revision → `CONFLICT` — adapters/ecommerce/python/memory.py:239-244 [DERIVED]
- post: live action at same node → marked `SUCCEEDED` with `result_hash`, `completed_at`, `revision_at` — adapters/ecommerce/python/memory.py:248-255 [DERIVED]; no live action → `SUBMISSION` row inserted directly as `SUCCEEDED` — adapters/ecommerce/python/memory.py:256-268 [DERIVED]

**attach_envelope(action_id, run_id, node, envelope) — adapters/ecommerce/python/memory.py:272-283**
- post: write-once via `INSERT OR IGNORE`; `context_hash` read from `envelope["manifest"]["context_hash"]` defaulting to `""` — adapters/ecommerce/python/memory.py:277-283 [DERIVED]

**run_audit(run_id) — adapters/ecommerce/python/memory.py:306-339**
- out keys: `run, actions_total, live_actions, model_actions, model_actions_with_envelope, events_monotonic, event_types, checks, checkpoints` — adapters/ecommerce/python/memory.py:328-339 [DERIVED]
- `model_actions` excludes `action_type == "SUBMISSION"` — adapters/ecommerce/python/memory.py:323 [DERIVED]
- `events_monotonic` = sequences sorted AND unique — adapters/ecommerce/python/memory.py:335 [DERIVED]

**sync_work_nodes(run_id, state) — adapters/ecommerce/python/memory.py:460-487**
- in: `state["rounds"]["research"]` and `state["data"][key]` lists — adapters/ecommerce/python/memory.py:462, 466 [DERIVED]
- out: count of changed/upserted rows — adapters/ecommerce/python/memory.py:487 [DERIVED]
- post: only keys present in `_NODE_TYPES` are persisted; items without dict shape or `id` are skipped — adapters/ecommerce/python/memory.py:465-468 [DERIVED]
- post: unchanged `semantic_hash` rows skipped — adapters/ecommerce/python/memory.py:471-474 [DERIVED]

**check_drift(run) — adapters/ecommerce/python/memory.py:150-152**
- out: subset of `DRIFT_FIELDS` where stored hash differs from current `config_hashes()` — adapters/ecommerce/python/memory.py:151-152 [DERIVED]

**update_run(run_id, ...) — adapters/ecommerce/python/memory.py:155-174**
- post: `status='stopped'` also sets `terminal_at`; `bump_revision=True` → `revision=revision+1` — adapters/ecommerce/python/memory.py:162-163, 170-171 [DERIVED]

## effect surface

- SQLite tables read: `runs` (146, 232, 237, 249, 259, 310), `actions` (181, 227-229, 234-236, 245-247, 312), `events` (315, 318, 326, 382), `checks` (324), `context_envelopes` (288, 322), `work_nodes` (296-303, 348, 366, 471), `schema_meta` (67), `sqlite_master` (55-56) — adapters/ecommerce/python/memory.py [DERIVED]
- SQLite tables written: `runs` (133-140, 174), `actions` (192, 201-206, 250-252, 260-265), `context_envelopes` (277-283), `events` (393-397), `checks` (410-416), `work_nodes` (475-485), `schema_meta` (63-64, 73-74) — adapters/ecommerce/python/memory.py [DERIVED]
- Files read: `sql/001_initial.sql` (20, 58), `sql/002_context.sql` (21, 71), `graph/control_graph.yaml` (116), `loop.yaml` (117), `graph/policies.yaml` (118), `schemas/` dir (119), `prompts/` dir (120) — adapters/ecommerce/python/memory.py [DERIVED]
- Dynamic import: `import registry` + `registry.load_snapshot()` inside `config_hashes` — adapters/ecommerce/python/memory.py:110-112 [DERIVED]
- env: `OPPORTUNITY_RESEARCH_DB` (default null) overriding `~/.hermes/state/opportunity-research/opportunity.sqlite3` — adapters/ecommerce/python/memory.py:26-29 [DERIVED]
- No network calls, no subprocesses visible in SOURCE.

## invariants

INVARIANT: `SCHEMA_VERSION = "2"` == max `MIGRATIONS` target `"2"` — adapters/ecommerce/python/memory.py:21-22 [DERIVED]
  fails-if: `_ensure_schema` raises `RuntimeError("unsupported schema_version ...")` — adapters/ecommerce/python/memory.py:77-78
INVARIANT: connect timeout `5.0` s == `busy_timeout = 5000` ms — adapters/ecommerce/python/memory.py:40-41 [DERIVED]
  fails-if: lock-wait behavior diverges between driver and engine layers.
INVARIANT: all content hashes are 16 hex chars (`hexdigest()[:16]` in `_h` and `_file_hash`) — adapters/ecommerce/python/memory.py:84, 90 [DERIVED]
  fails-if: `action_id = "act_" + _h(...)` length/format changes; stored ids stop matching recomputed ones — adapters/ecommerce/python/memory.py:199
INVARIANT: `DRIFT_FIELDS` (5 fields) ⊂ `config_hashes()` keys (6 keys); `registry_build` excluded — adapters/ecommerce/python/memory.py:115-121, 125-126 [DERIVED]
  fails-if: adding `registry_build` to drift blocks resume on any registry rebuild (`"none"` ↔ build_id flapping) [INFERRED: from the two literal lists]
INVARIANT: `create_action` returns the existing live action with `attempt_count+1` instead of inserting a second — adapters/ecommerce/python/memory.py:189-195 [DERIVED]
  fails-if: duplicate live actions make `pending_action`/`apply_submission`'s single-live-row assumption ambiguous — adapters/ecommerce/python/memory.py:178-183, 245-248
INVARIANT: `attach_envelope` is write-once (`INSERT OR IGNORE`) — adapters/ecommerce/python/memory.py:277 [DERIVED]
  fails-if: crash-resume sees a recompiled envelope, violating docs/10 replay stability per the docstring — adapters/ecommerce/python/memory.py:273-275
INVARIANT: `events.sequence` per run = `COALESCE(MAX(sequence),0)+1`, actor always `"controller"` — adapters/ecommerce/python/memory.py:391, 396 [DERIVED]
  fails-if: gap/duplicate sequence makes `run_audit`'s `events_monotonic` False — adapters/ecommerce/python/memory.py:335
INVARIANT: default DB path `~/.hermes/state/opportunity-research/opportunity.sqlite3` lies outside `SKILL_ROOT` — adapters/ecommerce/python/memory.py:19, 29 [DERIVED]
  fails-if: skill reinstall destroys run state, violating the module law — adapters/ecommerce/python/memory.py:4

## determinism & idempotency
determinism: NONDETERMINISTIC (env `OPPORTUNITY_RESEARCH_DB` — adapters/ecommerce/python/memory.py:26; clock via `now()` from `models` — adapters/ecommerce/python/memory.py:140, 174, 398; filesystem reads in `_file_hash`/`_dir_hash` — adapters/ecommerce/python/memory.py:89, 98; dynamic `import registry` — adapters/ecommerce/python/memory.py:110; SQLite concurrency `BEGIN IMMEDIATE`, `busy_timeout` — adapters/ecommerce/python/memory.py:41, 226). Hashing itself is order-stable: `json.dumps(..., sort_keys=True, default=str)` — adapters/ecommerce/python/memory.py:82.
idempotency: SAFE for `create_run` (OR IGNORE — 133), `create_action` (returns existing — 189-195), `attach_envelope` (OR IGNORE — 277), `apply_submission` (`ALREADY_APPLIED` — 227-231), `sync_work_nodes` (unchanged hash skipped — 471-474). UNSAFE per call: `record_event`/`_event` (new row each call — 393-397), `write_check` (new row each call — 410-416), `update_run(bump_revision=True)` (increments `revision` each call — 171).

## failure behaviour
- `except Exception: pass` around the registry probe in `config_hashes` — FACTS.fallbacks (SWALLOWED at line 113); caller sees `registry_build: "none"` with no signal that the import failed vs registry absent — adapters/ecommerce/python/memory.py:108-114, 121 [DERIVED]
- `OSError` in `_file_hash`/`_dir_hash` returns literal `"missing"` — adapters/ecommerce/python/memory.py:91-92, 102-103 [DERIVED]; a missing config file becomes a hash change, surfacing as drift in `check_drift` instead of an error — adapters/ecommerce/python/memory.py:150-152 [INFERRED: "missing" compared as a normal hash value]
- `json.JSONDecodeError` → `continue` in `candidate_recurrence` and `load_candidates`: corrupt `work_nodes` payloads silently dropped — adapters/ecommerce/python/memory.py:354-355, 371-372 [DERIVED]
- Only raised error: `RuntimeError(f"unsupported schema_version {current} (supported {SCHEMA_VERSION})")` — adapters/ecommerce/python/memory.py:77-78 [DERIVED]
- SQLite lock waits bounded by `timeout=5.0` and `busy_timeout = 5000`; no other explicit handlers — adapters/ecommerce/python/memory.py:40-41 [DERIVED]

## dumb-code flags
- Dead query: `run = conn.execute("SELECT current_graph_node FROM runs WHERE run_id=?", ...)` result never read; `run_full` re-selects the same table two lines later — adapters/ecommerce/python/memory.py:232-233, 237-238 [DERIVED]
- `write_check` hardcodes `subject_type` to `None` in the INSERT though the column exists — adapters/ecommerce/python/memory.py:414 [DERIVED]
- FACTS `tables_written` lists `"set"` — not a table; it is `_SCHEMA_READY.add(path)` misparsed as a write — adapters/ecommerce/python/memory.py:50 [DERIVED]
- FACTS `tables_written` omits `context_envelopes` and `schema_meta` though both are INSERTed — adapters/ecommerce/python/memory.py:277, 63-64, 73-74 [DERIVED]
- Version literal `"1"` fallback when a `schema_meta` row is missing duplicates the implicit 001 baseline — adapters/ecommerce/python/memory.py:68 [DERIVED]
- `_NODE_TYPES` assembled across four statements (init dict + `"corpus_answers"` + two `.update` calls); `"corpus_answers"` flagged `# LEGACY (< v2.2.0)` — adapters/ecommerce/python/memory.py:420-457, 452 [DERIVED]
- `load_candidates` dedup is O(n²) over `out` and two payloads both missing `id` (both `None`) dedup against each other — adapters/ecommerce/python/memory.py:374 [DERIVED]

## refactor notes
- Module law: only this file may know SQLite exists; `context.py` explicitly named as never touching it — adapters/ecommerce/python/memory.py:1, 295 [DERIVED]. Moving SQL into any other module breaks the docs/03 boundary; all consumers reroute.
- `controller.py` stays the sole transition authority — keep decision logic out; this module only persists — adapters/ecommerce/python/memory.py:7-8 [DERIVED]
- `run_audit`'s exact key set feeds `qualify.py` (docs/15): renaming `actions_total`, `live_actions`, `model_actions`, `model_actions_with_envelope`, `events_monotonic`, `event_types`, `checks`, `checkpoints` breaks the audit — adapters/ecommerce/python/memory.py:307, 328-339 [DERIVED]
- `candidate_recurrence` output shape `{kind, name, runs}` sorted by `-runs` feeds docs/17 triggers — adapters/ecommerce/python/memory.py:343, 358-360 [DERIVED]
- `_NODE_TYPES` governs what `sync_work_nodes` persists: a `state["data"]` key without a mapping is silently dropped — adapters/ecommerce/python/memory.py:465-466 [DERIVED]
- Schema file layout `sql/001_initial.sql` + `sql/002_context.sql` under `SKILL_ROOT` is load-bearing for `connect`; moving/renaming breaks the first connect — adapters/ecommerce/python/memory.py:20-21, 58, 71 [DERIVED]
- `apply_submission`'s `CONFLICT` branch depends on `prior["revision_at"] == run_full["revision"]`; changing revision semantics in `update_run(bump_revision=...)` alters conflict detection — adapters/ecommerce/python/memory.py:171, 239-244 [DERIVED]

## VERIFY
```verify
grep -Fq 'unsupported schema_version' adapters/ecommerce/python/memory.py
grep -Fq 'BEGIN IMMEDIATE' adapters/ecommerce/python/memory.py
grep -Fq 'OPPORTUNITY_RESEARCH_DB' adapters/ecommerce/python/memory.py
grep -Fq 'return "ALREADY_APPLIED", exact["action_id"]' adapters/ecommerce/python/memory.py
grep -Eq 'PRAGMA (busy_timeout = 5000|journal_mode = WAL)' adapters/ecommerce/python/memory.py
test "$(grep -c -F 'return "APPLY"' adapters/ecommerce/python/memory.py)" -ge 2
! grep -Fq 'import psycopg2' adapters/ecommerce/python/memory.py
```
