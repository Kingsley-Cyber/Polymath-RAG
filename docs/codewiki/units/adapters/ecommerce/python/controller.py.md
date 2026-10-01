# unit: adapters/ecommerce/python/controller.py
anchor: adapters/ecommerce/python/controller.py:1-707

## purpose
CLI graph runner: the deterministic spine an agent drives through a YAML work graph. The agent never decides what runs next — it calls `status` → does the node's work → `submit` → `step` until `node=stop`; illegal submissions and transitions are rejected with explicit reasons (module docstring, adapters/ecommerce/python/controller.py:2-17) [DERIVED]. Also owns run lifecycle (`pause`/`resume`/`abandon`), mode handoff to child runs, context export, triage, and doctor (adapters/ecommerce/python/controller.py:663-703) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `main` | def | () -> exit code (0/1) | controller.py:663-703 | `__main__` guard :706-707 |
| `cmd_init` | def | (args) -> 0/1 | controller.py:128-157 | `main` dispatch :700-703 |
| `cmd_status` | def | (args) -> 0 | controller.py:160-198 | `main` dispatch :700-703 |
| `cmd_submit` | def | (args) -> 0/1 | controller.py:201-352 | `main` dispatch :700-703 |
| `cmd_step` | def | (args) -> 0/1 | controller.py:355-513 | `main` dispatch :700-703 |
| `cmd_context_export` | def | (args) -> 0 | controller.py:516-527 | `main` dispatch :700-703 |
| `cmd_handoff` | def | (args) -> 0/1 | controller.py:530-595 | `main` dispatch :700-703 |
| `cmd_pause` / `cmd_resume` / `cmd_abandon` | def | (args) -> 0/1 | controller.py:598-610 / 613-622 / 625-638 | `main` dispatch :700-703 |
| `cmd_triage_run` | def | (args) -> 0/1 | controller.py:641-653 | `main` dispatch :700-703 |
| `cmd_doctor` | def | (args) -> 0/1 | controller.py:656-660 | `main` dispatch :666-667 |
| `node_output_specs` | def | (g, node) -> list[(key, schema, is_list)] | controller.py:68-79 | `cmd_submit` :230, `_node_needs` :119 |
| `node_required_keys` | def | (g, node) -> list[key] | controller.py:82-86 | `cmd_step` :396, :413 |
| `OUTPUT_SPECS` | const | node -> (state.data key, schema, is_list) | controller.py:90-101 | `node_output_specs` :72, `node_required_keys` :83 |
| `SCHEMA_BY_KEY` | const | payload key -> schema name | controller.py:36-57 | `node_output_specs` :77, :79 |
| `SINGULAR_KEYS` | const | set of scalar keys | controller.py:58-60 | `node_output_specs` :77, :79 |
| `MODE_GRAPHS` | const | mode -> graph yaml | controller.py:61-65 | `cmd_handoff` :536, :572 |

No importer data in FACTS; external callers = the shell/agent per the docstring loop (controller.py:15) [DERIVED].

## contracts

**cmd_init** (controller.py:128-157)
- in: `--state` (required), `--signal` default `""`, `--graph` default `None`, `--settings`, `--preset`, `--corpus`, `--document-id` (repeatable) (:677-685).
- pre: graph must pass `graphmod.validate_graph`; else emits `{"ok": false, "graph_errors": ...}` exit 1 (:130-132).
- post: state created at graph entry node (:135), run row created via `memory.create_run` (:151), settings resolved once with hash pinned (:146-150); invalid settings → `SETTINGS_REJECTED` exit 1 (:148-150).
- `--corpus` is provenance only, "never changes behavior" (:136-137); `--document-id` becomes `state["document_scope"]` deduped (:138-139).

**cmd_status** (controller.py:160-198)
- in: `--state`. out: JSON with `node`, `status`, `verdict`, `rounds`, `needs`, `edges` (each with `ready` from `transitions.evaluate`), `gaps`, `allocation`, `utilization`, `lived_world`, `context`, `counts` (:190-197). Read-only; always returns 0 (:198).
- `gaps`/`allocation` views only for nodes `web_research`, `curate`, `gaps`, `challenge`, `triage` (:174); `utilization` only for `qualify`/`stop` (:194); `lived_world` only when graph file is `control_graph.yaml` (:195).
- context envelope (hash + deficits) compiled only for node types `reason`/`retrieve`/`agent` (:169-172).

**cmd_submit** (controller.py:201-352)
- pre: run not paused (`RUN_PAUSED` :204-206); `--node` must equal current node — "no out-of-order submissions" (:207-209).
- capability_failure path: payload key `capability_failure` accepted only for node type `agent`/`retrieve`; recorded as coverage deficit, run continues (:212-229).
- in: payload JSON validated per `node_output_specs`; key-specific gates: `hypotheses` → `bridge.validate_all` against known evidence ids (:256-266), at `hypothesize` also lineage/anchor/portfolio checks (:267-280), at `challenge` also `starved_rejections` (:281-284); `primitives` → validate + mirror `latent_structures`/`corpus_observations` + merge relevance (:285-297); leads → validate + compile `channel_queries` (:298-304); `field_records`/`lived_situations` (:305-310); `product_concepts` → `ideation.validate_concepts` (:311-314); `observations` → `verifiers.admit_observations` (:315-318).
- merge: list keys deduped by `id`; `challenge` updates hypothesis statuses in place (:320-330).
- post: idempotency via `memory.apply_submission` — identical payload → `ALREADY_APPLIED`, ok, no mutation (:339-342); different payload at same node/revision → `IDEMPOTENCY_CONFLICT` exit 1 (:343-348). Errors → `schema_errors` (first 20) exit 1 (:334-335).

**cmd_step** (controller.py:355-513)
- terminal (`stopped`) runs: ok, immutable, no mutation (:364-368). paused → `RUN_PAUSED` exit 1 (:369-372).
- pre: `memory.check_drift` clean; drift → `BLOCKED_CONFIG_DRIFT` exit 1 (:373-380).
- `transform`/`gate`: runs `executors.EXECUTORS[spec.executor]`; unknown → `no executor ...` exit 1 (:385-389).
- `reason`/`retrieve`/`agent`: required keys must be submitted here (a merged-but-empty list counts as answered, :391-396); nodes with `fresh_submission_per_visit: true` need a submit or capability_failure per entry (:397-419); capability failure + missing → advance with recorded deficit (:420-427); still missing → `BLOCKED_CONTEXT_INCOMPLETE` exit 1 if envelope blocked (:433-441), else durable pending action + frozen context envelope, same packet on re-step (:442-457).
- post: advances along first edge whose `when` is None or evaluates true (:458-460); runs target's `on_enter` executor if declared (:461-474); on terminal sets `status="stopped"` and verdict `NO_DEFENSIBLE_BRIDGE` on edge `no_defensible_bridge`, else `STOPPED_WITHOUT_QUALIFICATION` (:478-486); checkpoints, `ROLE_COVERAGE` check, `memory.update_run(..., bump_revision=True)` (:491-505). No satisfied edge → error with hint, exit 1 (:510-513).

**cmd_handoff** (controller.py:530-595)
- in: `--to-mode` (must be a `MODE_GRAPHS` key), `--scope`, `--out` (all required, :691-694).
- pre: `--scope` must match an `id`/`scope_id` in `promoted_scopes`, `market_scopes`, `top_bridges`, `market_bridges`, `leads` (:541-550).
- post: new child state at destination graph entry with `data["handoff_packet"]` containing promoted scope, `evidence_refs` (≤40), `unresolved_questions` (≤8), `prior_rejections` (≤20), registry snapshot, authority boundaries, source checkpoint (:553-571); HANDOFF events recorded on both runs (:583-590). Parent run type never mutates (:531-534).

**lifecycle** — `pause` only from `running` (:602-603); `resume` only from `paused` (:615-616); `abandon` rejected on `stopped` ("a terminal run never changes") and sets verdict `ABANDONED` (:627-631).

**cmd_context_export** — one-way projection to `working_context.md`; "NEVER canonical", edits never flow back (:516-527). **cmd_triage_run** — read-only; exit 1 when BLOCKER/DEFECT present (:641-653). **cmd_doctor** — wraps `doctor.run()`, exit gates on `result["ok"]` (:656-660).

## effect surface
- Files read: state JSON (`args.state`) :161, :203, :356; submit payload JSON :210, :233; settings JSON :144; graph YAMLs named in `MODE_GRAPHS` (`control_graph.yaml`, `loadout_graph.yaml`, `market_discovery_graph.yaml`, `product_anchored_graph.yaml`, `maintenance_graph.yaml`) :61-65 via `graphmod.load_graph` :129, :162, :203, :357, :520, :555, :572; policies via `graphmod.load_policies` :162, :236, :357.
- Files written: state file via `models.save_state` :154, :350, :443, :487, :512, :591, :605, :618, :631; working context markdown (default `<state-basename>.working_context.md`) :522-524; child handoff state :591.
- Prompt file path constructed (not read here): `os.path.join("prompts", f"{spec.get('prompt', node)}.md")` :113.
- Persistence side effects via `memory.*`: `create_run`, `record_event`, `apply_submission`, `get_run`, `check_drift`, `create_action`, `attach_envelope`, `get_envelope`, `sync_work_nodes`, `update_run`, `write_check`, `latest_checkpoint`, `config_hashes` (:151-153, :338, :358-361, :442-447, :488-505, :568-590, :626-635). Backing tables unknown — FACTS `tables_read`/`tables_written` are empty.
- stdout: JSON via `_emit` (`json.dumps(obj, indent=1, ensure_ascii=False)`) :104-105; plain markdown for `triage-run --markdown` :648-650.
- Env flags: none read (no `os.environ` in source; only `os.path` :26, :113, :133-134, :522, :578). Network/subprocess: none in source [DERIVED].

## invariants
INVARIANT: `MODE_GRAPHS` cardinality = 5 modes (`opportunity_research`, `niche_loadout`, `market_discovery`, `product_anchored`, `registry_maintenance`) — controller.py:61-65 [DERIVED]
  fails-if: `handoff --to-mode` accepts an unknown graph or a mode loses its graph file (rejected at :536-539).
INVARIANT: handoff packet caps = `evidence_refs[:40]`, `unresolved_questions[:8]`, `prior_rejections[:20]` — controller.py:561-567 [DERIVED]
  fails-if: child run sees more parent context than the design allows ("never the parent's whole context window", :533-534).
INVARIANT: `capability_failure` accepted ⇔ node type ∈ {`agent`, `retrieve`} — controller.py:216-218 [DERIVED]
  fails-if: a `reason` node could fake a coverage deficit instead of submitting outputs.
INVARIANT: `min_independent_sources` default = `3` — controller.py:180 [DERIVED]
  fails-if: status `need_more` computation silently changes when policies omit the key.
INVARIANT: reported `schema_errors` length ≤ 20 (`errors[:20]`) — controller.py:335, :463 [DERIVED]
  fails-if: callers parsing full error lists truncate differently.
INVARIANT: terminal run is immutable — `status == "stopped"` short-circuits `step` (:364-368) and `abandon` errors (:627-628) [DERIVED]
  fails-if: config evolution after completion would mutate history ("config evolution after a run finished is not drift", :362-363).
INVARIANT: terminal verdict = `NO_DEFENSIBLE_BRIDGE` iff exit edge `when == "no_defensible_bridge"`, else `STOPPED_WITHOUT_QUALIFICATION` — controller.py:481-486 [DERIVED]
INVARIANT: `triage-run` `--stale-minutes` default = `30` — controller.py:675 [DERIVED]
INVARIANT: submit is node-ordered — `args.node == state["node"]` or reject — controller.py:207-209 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `models.now()` timestamps :221-222, :349, :476; filesystem: state/payload/graph/policy loads :161-162, :210, :357; memory store reads :358, :442-447) [DERIVED]
idempotency: SAFE for `submit` — identical payload returns `ALREADY_APPLIED` with no duplicate mutation (:339-342); divergent duplicate refused via `IDEMPOTENCY_CONFLICT` (:343-348). UNSAFE for `step`/`pause`/`resume`/`abandon` — each mutates state/history (:475-477, :604-607, :617-620, :629-635); mitigated for pending `step` by the frozen action+envelope returning the same packet (:445-456) [DERIVED]

## failure behaviour
- Broad handler at controller.py:470 (`except Exception as exc:  # noqa: BLE001`) around `on_enter` executors: failure is swallowed into a history `on_enter_error` entry and a `FAILED {type}: {exc}` note; the run still advances and the caller sees `ok: true` with the note (:469-474, :506-508). FACTS fallbacks: "handled: assign, expr" at :470.
- Error codes emitted (all exit 1 unless noted): `SETTINGS_REJECTED` :149, `RUN_PAUSED` :205, :370, node-mismatch message :208, `capability_failure only applies to agent/retrieve nodes` :217, `takes no submissions` :232, `schema_errors` :335, :463, `IDEMPOTENCY_CONFLICT` :344, `no executor ...` :388, `BLOCKED_CONFIG_DRIFT` :376, `BLOCKED_CONTEXT_INCOMPLETE` :437, `no on_enter executor ...` :467, `no satisfied edge out of ...` (with hint) :510-511, unknown handoff mode :537, promoted object not found :549, cannot pause/resume wrong status :603, :616, `already terminal` :628.
- `capability_failure` and `ALREADY_APPLIED` are ok:true outcomes (:225-229, :340-342).

## dumb-code flags
- `OUTPUT_SPECS` is defined at :90 but referenced by `node_output_specs` (:72) and `node_required_keys` (:83) defined above it — works only via late binding at call time [DERIVED].
- `cmd_triage_run` tests the same flag twice back-to-back: `if args.markdown:` then `if getattr(args, 'markdown', False):` (:647-650) — the inner check is dead-redundant [DERIVED].
- `import lived_world as _lw` is re-executed inside `cmd_submit` at :270 and again at :277 within the same `hypothesize` block, plus :291, :299, :306, :309 — six imports in one function [DERIVED].
- Default graph literal `"control_graph.yaml"` repeated on 9 lines (:61, :129, :134, :162, :195 ×2, :203, :357, :520, :555) — a rename touches all of them [DERIVED].
- `SCHEMA_BY_KEY` aliases 5 keys to one schema: `field_signals`/`trend_signals`/`corpus_signals`/`supply_signals`/`commerce_signals` → `market_signal` (:41-43); 2 keys → `population_lead` (:54) [DERIVED].
- String-based lazy imports `__import__("utilization")` and `__import__("lived_world")` (:194-195) — invisible to normal import-graph tooling [DERIVED].
- Magic truncations: gap `question` cut to `[:100]` (:189); `errors[:20]` (:335, :463); handoff caps 40/8/20 (:561-567) — unexplained constants [DERIVED].
- `triage-run --markdown` prints markdown only, never `_emit` JSON (:648-652) — output-mode divergence in one command [INFERRED: both branches can't be observed from one invocation, but the code paths are disjoint].

## refactor notes
- `OUTPUT_SPECS`, `SCHEMA_BY_KEY`, `SINGULAR_KEYS` jointly define the submit contract for every node; adding/renaming a data key requires updating all three or `node_output_specs` silently drops schema/list flags (:72-79, :90-101, :36-60) [DERIVED].
- `MODE_GRAPHS` keys are the public `--to-mode` vocabulary (:536, :61-65); renaming a mode breaks handoff callers [DERIVED].
- `memory.apply_submission` disposition strings `"ALREADY_APPLIED"` / `"CONFLICT"` are a wire protocol with the memory module (:338-348) — changing either side breaks idempotency reporting [DERIVED].
- `executors.EXECUTORS` keys must match graph `executor` and `on_enter` strings exactly or `step` hard-fails (:386-388, :465-467) [DERIVED].
- The dispatch dict in `main` (:700-703) and the parser loop (:668-669) must stay in sync with every `cmd_*` function and its flags (:672-696) [DERIVED].
- Graph node names are hardcoded in Python conditions: `semantic_review` (:114), `web_research`/`curate`/`gaps`/`challenge`/`triage` (:174), `qualify`/`stop` (:194), `hypothesize`/`challenge` (:267, :281), `challenge`+`hypotheses` in-place update (:324-329) — renaming graph nodes breaks these branches [DERIVED].

## VERIFY
```verify
grep -Fq 'IDEMPOTENCY_CONFLICT' adapters/ecommerce/python/controller.py
grep -Fq 'BLOCKED_CONFIG_DRIFT' adapters/ecommerce/python/controller.py
grep -Fq 'NO_DEFENSIBLE_BRIDGE' adapters/ecommerce/python/controller.py
grep -Fq 'get("min_independent_sources", 3)' adapters/ecommerce/python/controller.py
grep -Fq 'fresh_submission_per_visit' adapters/ecommerce/python/controller.py
test "$(grep -c -F 'control_graph.yaml' adapters/ecommerce/python/controller.py)" -ge 9
! grep -Fq 'os.environ' adapters/ecommerce/python/controller.py
```
