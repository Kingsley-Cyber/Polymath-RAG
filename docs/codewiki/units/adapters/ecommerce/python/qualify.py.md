# unit: adapters/ecommerce/python/qualify.py
anchor: adapters/ecommerce/python/qualify.py:1-171

## purpose
CLI that rebuilds the "Architecture Qualification Report" (docs/15): recomputes the system's invariants over finished/in-flight run-state JSONs plus their SQLite audit trail and reports per-run graph path, loops, actions, recovery, coverage, and invariant violations — adapters/ecommerce/python/qualify.py:2-11 [DERIVED]. Zero violations across adversarial fixtures is the stated stopping condition for the v1 architecture freeze — adapters/ecommerce/python/qualify.py:8-9 [DERIVED]. Invoked as `qualify.py --states run1.json run2.json ... [--out report.json]` — adapters/ecommerce/python/qualify.py:11 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
| qualify_run | def | (state_path: str, policies: dict) -> dict | adapters/ecommerce/python/qualify.py:44-134 | build_report (138-139) |
| build_report | def | (state_paths: list[str]) -> dict | adapters/ecommerce/python/qualify.py:137-150 | main (158) |
| main | def | () -> int | adapters/ecommerce/python/qualify.py:153-167 | CLI entry `__main__` (170-171) |
| KNOWN_VERDICTS | module dict | 5 modes -> set of verdict strings | adapters/ecommerce/python/qualify.py:28-41 | qualify_run (75) |

## contracts
**qualify_run(state_path, policies) -> dict** — adapters/ecommerce/python/qualify.py:44-134
- in: `state_path` file loaded via `models.load_state`; graph via `graphmod.load_graph(state.get("graph_file", "control_graph.yaml"))` — 45-46.
- pre: `state["data"]`, `state["run_id"]`, `state["status"]` are direct indexing (KeyError if absent) — 48, 49, 55; `state["rounds"]["research"]` likewise — 120.
- out: dict with keys `run_id`, `mode`, `graph_path`, `loops_exercised`, `actions_generated`, `context_recovery`, `checkpoints`, `evidence_role_coverage`, `capability_failures`, `terminal`, `settings_hash`, `registry_candidates_emitted`, `handoffs`, `invariant_violations` — 116-133.
- post: `invariant_violations` holds one human-readable string per failed check; `context_recovery` is one of `"TERMINAL_IMMUTABLE"`, `"PENDING_ACTION_FROZEN"`, `"PENDING_NO_ENVELOPE"`, `"NO_LIVE_ACTION"` — 105-111.

**build_report(state_paths) -> dict** — adapters/ecommerce/python/qualify.py:137-150
- in: one or more state paths; policies from `graphmod.load_policies()` — 138.
- out: keys `report="architecture_qualification"`, `version="v1"`, `generated_at`, `config`, `runs`, `modes_covered`, `total_invariant_violations`, `stopping_condition_met` — 141-149.
- post: `stopping_condition_met == (total_invariant_violations == 0)` — 140, 149.

**main() -> int** — adapters/ecommerce/python/qualify.py:153-167
- in: argv; `--states` required (`nargs="+"`), `--out` optional — 155-156.
- out: `0` if `stopping_condition_met` else `1` — 167.
- side: with `--out`, writes JSON (indent=1, ensure_ascii=False, encoding utf-8) and prints `{"ok", "out", "total_invariant_violations"}`; without, prints full report — 159-166.

## effect surface
- Files read: run-state JSONs (`--states`) — 45; control graph, default `"control_graph.yaml"` — 46; policies — 138.
- SQLite audit trail read via `memory.run_audit(state["run_id"])` — 49; config hashes via `memory.config_hashes()` — 145. No table names visible (FACTS: `tables_read: []`, `tables_written: []`).
- Files written: optional `--out` report path, truncated/overwritten — 160-162.
- Import-path mutation: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before importing siblings `bridge`, `graph as graphmod`, `memory`, `models`, `verifiers` — 20-26.
- No network, subprocess, or env-flag reads visible.

## invariants
INVARIANT: `(state["status"] == "stopped") == (run_row.get("status") == "stopped")` — adapters/ecommerce/python/qualify.py:55 [DERIVED]
  fails-if: violation `state/SQLite terminal status disagree`
INVARIANT: `audit["live_actions"] <= 1` — adapters/ecommerce/python/qualify.py:62-63 [DERIVED]
  fails-if: violation `N live actions (one-writer law broken)`
INVARIANT: stopped run implies `live_actions == 0` — adapters/ecommerce/python/qualify.py:64-65 [DERIVED]
  fails-if: violation `terminal run still holds a live action`
INVARIANT: `audit["events_monotonic"]` is true — adapters/ecommerce/python/qualify.py:66-67 [DERIVED]
  fails-if: violation `event log not strictly monotonic`
INVARIANT: `model_actions_with_envelope == model_actions` — adapters/ecommerce/python/qualify.py:68-70 [DERIVED]
  fails-if: violation `N model actions without a frozen ContextEnvelope`
INVARIANT: stopped ∧ `verdict != "ABANDONED"` implies event `TERMINAL_REACHED` or `RUN_ABANDONED` present — adapters/ecommerce/python/qualify.py:71-74 [DERIVED]
  fails-if: violation `terminal run without TERMINAL_REACHED event`
INVARIANT: `state["verdict"] ∈ KNOWN_VERDICTS[mode]` — adapters/ecommerce/python/qualify.py:75-77 [DERIVED]
  fails-if: violation `unknown verdict ... for mode ...`
INVARIANT: `run_row["registry_build"]` is truthy — adapters/ecommerce/python/qualify.py:78-79 [DERIVED]
  fails-if: violation `run not pinned to a registry build`
INVARIANT: every persisted observation re-passes `verifiers.admit_observations` — adapters/ecommerce/python/qualify.py:83-86 [DERIVED]
  fails-if: violation `N observations no longer admissible`
INVARIANT: observation `evidence_roles ⊆ policies["evidence_roles"]["valid"]` — adapters/ecommerce/python/qualify.py:87-91 [DERIVED]
  fails-if: violation `observation X carries unknown roles`
INVARIANT: every `SUPPORTED` hypothesis in mode `opportunity_research` passes `bridge.validate_bridge` — adapters/ecommerce/python/qualify.py:94-98 [DERIVED]
  fails-if: violation `SUPPORTED bridge X fails admissibility: ...`
INVARIANT: verdict `"QUALIFIED_LEADS"` with leads implies `satisfaction.core_satisfied` — adapters/ecommerce/python/qualify.py:99-102 [DERIVED]
  fails-if: violation `QUALIFIED_LEADS with unsatisfied core coverage`
INVARIANT: exit code `0` iff `total_invariant_violations == 0` — adapters/ecommerce/python/qualify.py:140,149,167 [DERIVED]
  fails-if: CI/stopping-condition consumers treat a violating run as passing (or vice versa)

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `models.now()` at 144; filesystem: state/graph/policy reads at 45-46, 138; db: `memory.run_audit`/`config_hashes` at 49, 145)
idempotency: SAFE (pure recomputation over inputs; only side effect is overwriting the optional `--out` file at 160-162)

## failure behaviour
No `try`/`except` anywhere in the file; exceptions from `models.load_state`, `memory.run_audit`, `verifiers.admit_observations`, `bridge.validate_bridge` propagate uncaught to the caller — adapters/ecommerce/python/qualify.py:44-167 [INFERRED from absence of handlers]. Signal channel is the exit code: `0` = zero violations, `1` = violations present — 167. A missing SQLite run row is not an exception; it becomes violation `no run row in SQLite` — 60-61.

## dumb-code flags
- `sys.path.insert(0, ...)` sibling-import hack instead of package-relative imports — adapters/ecommerce/python/qualify.py:20-26 [DERIVED].
- Hardcoded default graph filename `"control_graph.yaml"` — adapters/ecommerce/python/qualify.py:46 [DERIVED].
- `KNOWN_VERDICTS` duplicates the verdict vocabulary per mode (5 sets; `"ABANDONED"` and `"STOPPED_WITHOUT_QUALIFICATION"` repeated) — a verdict renamed in the graph definitions drifts silently here — adapters/ecommerce/python/qualify.py:28-41 [INFERRED: two sources of truth].
- Verdict check is skipped entirely for any mode not in `KNOWN_VERDICTS` (`if mode in KNOWN_VERDICTS and ...`) — adapters/ecommerce/python/qualify.py:75 [DERIVED].
- `cov = state.get("satisfaction") or {}` computed twice with identical expression — adapters/ecommerce/python/qualify.py:99 and 115 [DERIVED].
- Mixed safety styles: guarded `(state.get("settings") or {}).get("hash")` at 129 vs unguarded `state["rounds"]["research"]` at 120 [DERIVED].
- Unusual `json.dumps(report, indent=1, ensure_ascii=False)` — adapters/ecommerce/python/qualify.py:159 [DERIVED].

## refactor notes
- The 14-key per-run dict and 8-key report dict (incl. `"architecture_qualification"`, `"v1"`) are the output contract of the freeze gate; renaming any key breaks downstream readers of `report.json` — adapters/ecommerce/python/qualify.py:116-133, 141-149 [DERIVED].
- Exit code `0/1` is the machine-readable stopping condition; changing it changes the freeze gate semantics — adapters/ecommerce/python/qualify.py:167, 8-9 [DERIVED].
- Verdict strings are a cross-module vocabulary: editing verdicts in graph definitions requires editing `KNOWN_VERDICTS` in lockstep — adapters/ecommerce/python/qualify.py:28-41, 75-77 [DERIVED].
- Depends on sibling modules `bridge`, `graph`, `memory`, `models`, `verifiers` via `sys.path.insert`; moving this file out of `adapters/ecommerce/python/` breaks all imports — adapters/ecommerce/python/qualify.py:20-26 [DERIVED].
- Adding/removing an invariant changes `total_invariant_violations` counts and can flip `stopping_condition_met` on historical fixtures — adapters/ecommerce/python/qualify.py:140-149 [DERIVED].

## VERIFY
```verify
grep -Fq 'one-writer law broken' adapters/ecommerce/python/qualify.py
grep -Fq 'control_graph.yaml' adapters/ecommerce/python/qualify.py
grep -Fq 'architecture_qualification' adapters/ecommerce/python/qualify.py
test "$(grep -c -F 'ABANDONED' adapters/ecommerce/python/qualify.py)" -ge 5
! grep -Fq 'try:' adapters/ecommerce/python/qualify.py
grep -Eq 'raise SystemExit\(main\(\)\)' adapters/ecommerce/python/qualify.py
```
