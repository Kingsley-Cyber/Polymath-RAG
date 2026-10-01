# unit: adapters/ecommerce/python/context.py
anchor: adapters/ecommerce/python/context.py:1-348

## purpose
Context Compiler (docs/10): compiles the per-action ContextEnvelope (RunBrief + ActionContext + manifest) presented to θ for one action — adapters/ecommerce/python/context.py:1-7,181-183 [DERIVED].
Owns only the temporary context window: SQLite owns workflow truth via `memory.py` (this module never touches SQL), the corpus backend owns source truth, the pinned RegistrySnapshot owns priors, graph/policy files own rules — adapters/ecommerce/python/context.py:3-7 [DERIVED].
Also emits deterministic phase checkpoints (283-300) and the one-way `working_context.md` projection for humans and emergency recovery (302-348) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| contract_of | def | (g: dict, node: str) -> dict | adapters/ecommerce/python/context.py:71-72 [DERIVED] | — |
| build_run_brief | def | (state: dict, g: dict, pol: dict) -> dict | adapters/ecommerce/python/context.py:76-101 [DERIVED] | — |
| compile_envelope | def | (state: dict, g: dict, pol: dict, node: str or None = None) -> dict | adapters/ecommerce/python/context.py:181-259 [DERIVED] | — |
| build_checkpoint | def | (state: dict, phase: str) -> dict | adapters/ecommerce/python/context.py:283-300 [DERIVED] | — |
| export_working_context | def | (state: dict, g: dict, pol: dict) -> str | adapters/ecommerce/python/context.py:309-348 [DERIVED] | — |

FACTS record no importers. Docstring names `controller.py step --run <id>` and `controller.py context-export` as external consumers of this module's outputs — adapters/ecommerce/python/context.py:9-11,307 [DERIVED].

## contracts

**compile_envelope(state, g, pol, node=None) -> dict**
- pre: `(set(require) | set(prefer)) & exclude` must be empty, else raises `ValueError(f"contract for {node!r} both requires and excludes {sorted(bad)}")` — adapters/ecommerce/python/context.py:190-192 [DERIVED].
- in: `graphmod.node_spec(g, node)` for spec + `context` contract (185-186); reads `state["run_id"]`, `state["node"]`, `state["data"]`, `state["status"]`, `state["rounds"]`, `state.get("history"/"verdict"/"corpus")` via build_run_brief (78-95) [DERIVED].
- out: `{"status": "READY" | "BLOCKED_CONTEXT_INCOMPLETE", "run_brief", "action_context", "manifest"}` — adapters/ecommerce/python/context.py:237,258-259 [DERIVED].
- post: `manifest["context_hash"] = _hash(core)` where core is exactly `{"run_brief": ..., "action_context": ...}`; "same canonical state -> same context_hash"; `manifest["compiled_at"] = models.now()` sits outside the hashed core — adapters/ecommerce/python/context.py:182-183,238-239,255-256 [DERIVED].
- deficit entry: `{"key", "owner": _SPECIAL_OWNERS.get(key, "graph_routing"), "detail": "required object does not exist yet — it must be produced by its owning step, never invented here"}` — adapters/ecommerce/python/context.py:208-212 [DERIVED].
- required key whose raw list is non-empty but fully filtered becomes `all_rejected`, source `"state (all rejected)"`, items projected to keys `("id", "status", "path", "target_mechanism", "invariant")` — adapters/ecommerce/python/context.py:199-206 [DERIVED].
- manifest pins: `sources.registry = memory.config_hashes()["registry_build"]`, `sources.policy_hash = memory.config_hashes()["policy_hash"]`, `context_id = "ctx_" + _hash(...)` — adapters/ecommerce/python/context.py:240-247 [DERIVED].

**build_run_brief(state, g, pol) -> dict**
- out: `major_decisions` = last `[-6:]` history events with `event == "advance"` (79,97); `unresolved_critical_gaps` = first `[:6]` open-gap questions (80-81); `original_user_goal` = `signal` string or `signal.interpretation` or `""` (87-89); `progress_signature = _hash({k: len(v) if isinstance(v, list) else 1 ...})` (99-100) — adapters/ecommerce/python/context.py [DERIVED].

**build_checkpoint(state, phase) -> dict**
- out: `surviving_hypotheses` = ids with `status not in ("REJECTED",)` (290-292); `unresolved_gaps` = status `"open"` (293-294); `resolved_gaps` = status `not in (None, "open")` (295-296); same `progress_signature` formula as the brief (298-299) — adapters/ecommerce/python/context.py [DERIVED].

**export_working_context(state, g, pol) -> str**
- out: Markdown starting `# Run {run_id}` + `_MD_WARNING`; sections include `## What we currently believe` (only `status == "SUPPORTED"` hypotheses, 323-328), `## Critical contradictions` (`[:6]`, 331), `## Surviving products` (`[:8]`, 335), `## Next legal action` (via `graphmod.node_spec`, 340-343), `## Config pins` (`registry_build`, `policy_hash`, `control_graph_hash`, `revision` from `memory.get_run`, 344-346) — adapters/ecommerce/python/context.py:312-346 [DERIVED].

## effect surface
- SQL: none — module "never touches SQL"; all persistence via `memory` — adapters/ecommerce/python/context.py:3-4 [DERIVED]. FACTS `tables_read`/`tables_written` are empty.
- memory.py calls: `memory._NODE_TYPES.get(key)` (156), `memory.load_work_nodes(state["run_id"], ntype)` (158), `memory.config_hashes()` (245,247), `memory.get_run` (312), `memory.latest_checkpoint` (313) — adapters/ecommerce/python/context.py [DERIVED].
- function-local imports: `registry` (114), `evaluator` (175), `settings as _settings` (221); top-level: `graph as graphmod`, `memory`, `models` (22-24) — adapters/ecommerce/python/context.py [DERIVED].
- artifact: `working_context.md` text returned as a string; rebuilt by `controller.py context-export` if deleted — adapters/ecommerce/python/context.py:304-307,348 [DERIVED].
- network / subprocess / env flags: none visible in this file.

## invariants
INVARIANT: default context budget `max_chars` == `60000`, overridable by policy `context.budgets.max_chars` then per-contract `budget.max_chars` — adapters/ecommerce/python/context.py:264-266 [DERIVED]
  fails-if: envelopes exceed intended size or trim at the wrong threshold.
INVARIANT: `_apply_budget` drops only priority levels `(4, 3, 2)`; priority-1 keys are never dropped — adapters/ecommerce/python/context.py:269-273 [DERIVED]
  fails-if: decision-critical keys (`hypotheses`, `gaps`, `challenges`) vanish under budget pressure.
INVARIANT: keys absent from `_PRIORITY` are treated as priority `4` via `_PRIORITY.get(key, 4)` — adapters/ecommerce/python/context.py:272-273 [DERIVED]
  fails-if: an unclassified contract key is trimmed first.
INVARIANT: `len(_hash(x)) == 16` hex chars (`hexdigest()[:16]`) — adapters/ecommerce/python/context.py:67-68 [DERIVED]
  fails-if: `context_hash`/`progress_signature` comparisons break across versions.
INVARIANT: backfill returns `(rows, "sqlite_work_graph", True)` only when re-filtered rows are non-empty, with `_node_type` stripped from each row — adapters/ecommerce/python/context.py:155-163 [DERIVED]
  fails-if: manifest `backfilled` list misreports provenance.
INVARIANT: backfill is "recovery of known state, never creation of new state" — adapters/ecommerce/python/context.py:13-15,146-147 [DERIVED]
  fails-if: the compiler invents evidence, breaking the ownership law (3-7).
INVARIANT: effective priority of `lived_situations` == `1` — literal `"lived_situations": 2` is shadowed by `"lived_situations": 1` — adapters/ecommerce/python/context.py:36,50 [INFERRED] (duplicate dict key, last assignment wins)
  fails-if: removing line 50 silently demotes lived situations to P2 trimming.
INVARIANT: `major_decisions <= 6` and `unresolved_critical_gaps <= 6` — adapters/ecommerce/python/context.py:79-81 [DERIVED]
  fails-if: brief grows unbounded on long runs.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock — `manifest["compiled_at"] = models.now()` at adapters/ecommerce/python/context.py:256); everything hashed into `context_hash` is deterministic (sorted-key JSON + sha256, 63-68; claim at 182-183); registry snapshot contents depend on the pinned external build (114-119).
idempotency: SAFE — no writes to state, memory, or files; `_apply_budget` mutates only `action_ctx["working_set"]`, a dict constructed earlier in the same call — adapters/ecommerce/python/context.py:222-235,267,278 [INFERRED].

## failure behaviour
- `except Exception` around `registry.load_snapshot()` is swallowed: returns `(None, "registry")` — FACTS.fallbacks; adapters/ecommerce/python/context.py:120-121 [DERIVED].
- Downstream of that swallow: a required empty key becomes a deficit with `owner: "registry"` and envelope status `BLOCKED_CONTEXT_INCOMPLETE` (208-213, 237); a preferred empty key is silently skipped (214-215) — adapters/ecommerce/python/context.py [DERIVED].
- `ValueError` on a node contract that both requires/prefer and excludes the same key — adapters/ecommerce/python/context.py:190-192 [DERIVED]. No other explicit raise in the file.

## dumb-code flags
- Duplicate dict key `"lived_situations"`: `"lived_situations": 2` then `"lived_situations": 1` (second wins) — adapters/ecommerce/python/context.py:36,50 [DERIVED].
- Comment promises "P0 (constitution + action) ... never dropped" but `_PRIORITY` contains only values 1-3 and no 0; unknown keys default to 4 — adapters/ecommerce/python/context.py:30-31,269-273 [DERIVED].
- Magic caps: `[-6:]` decisions (79), `[:6]` gaps (81), `[:6]` challenges (331), `[:8]` products (335), `[:16]` hash (68), `60000` budget (265) — adapters/ecommerce/python/context.py [DERIVED].
- Duplicated `progress_signature` formula in `build_run_brief` and `build_checkpoint` — adapters/ecommerce/python/context.py:99-100,298-299 [DERIVED].
- Identity comprehension `{k: v for k, v in brief.items()}` copies without filtering — adapters/ecommerce/python/context.py:238 [DERIVED].
- `_filter_items` status check tolerates non-dict items (131-133) but the `observations` role filter calls `o.get("evidence_roles")` and would raise on a non-dict item — adapters/ecommerce/python/context.py:136 [INFERRED].
- Status drop checks two different member names, `status` and `state` — adapters/ecommerce/python/context.py:131-133 [DERIVED].

## refactor notes
- `state` key names (`run_id`, `node`, `status`, `data`, `rounds`, `history`, `verdict`, `corpus`) and every `state["data"]` key are load-bearing; `_resolve_key` falls back `d.get(key) if key in d else state.get(key)` — adapters/ecommerce/python/context.py:151-152 [DERIVED].
- `_PRIORITY` must cover every contract `require`/`prefer` key, otherwise that key defaults to trim-first P4 — adapters/ecommerce/python/context.py:269-273 [DERIVED].
- `memory._NODE_TYPES` is a private cross-module access; renaming it in memory.py silently disables backfill (falls through to `([], "state", False)`) — adapters/ecommerce/python/context.py:155-163 [DERIVED].
- `_sanitize` is a three-way coupling: spec value `"dossier"`, key `"hypotheses"`, and `evaluator.DOSSIER_HYP_FIELDS` — adapters/ecommerce/python/context.py:173-176 [DERIVED].
- External envelope shape: statuses `"READY"`/`"BLOCKED_CONTEXT_INCOMPLETE"` and manifest keys `context_id`, `context_hash`, `sources`, `included_objects`, `backfilled`, `excluded_due_to_budget`, `required_contract_complete`, `deficits`, `all_rejected` — adapters/ecommerce/python/context.py:237,240-257 [DERIVED].
- Prompt-visible strings: `action_ctx["law"]` ("Everything required for this action is HERE. ...") and `_MD_WARNING`; edits change θ-facing behavior and the human projection — adapters/ecommerce/python/context.py:233-234,304-307 [DERIVED].
- Docstring invariants bind to `controller.py step --run <id>` and `controller.py context-export` — adapters/ecommerce/python/context.py:9-11,307 [DERIVED].

## VERIFY
```verify
grep -Fq '_STATUS_DROP = {"REJECTED", "REJECT", "COLLAPSED", "PRUNED"}' adapters/ecommerce/python/context.py
grep -Fq '.get("max_chars", 60000)' adapters/ecommerce/python/context.py
test "$(grep -c -F '"lived_situations"' adapters/ecommerce/python/context.py)" -ge 2
grep -Fq 'BLOCKED_CONTEXT_INCOMPLETE' adapters/ecommerce/python/context.py
grep -Fq 'hexdigest()[:16]' adapters/ecommerce/python/context.py
grep -Fq 'sqlite_work_graph' adapters/ecommerce/python/context.py
grep -Eq 'for level in \(4, 3, 2\)' adapters/ecommerce/python/context.py
! grep -Fq 'import sqlite3' adapters/ecommerce/python/context.py
```
