# unit: adapters/ecommerce/python/doctor.py
anchor: adapters/ecommerce/python/doctor.py:1-202

## purpose
Configuration qualification gate for the ecommerce adapter — "fail closed" per docs/15 §1. Lints every graph, policy file, schema, prompt reference, executor binding, edge condition, ContextContract and EvidenceRole reference before a run trusts it. doctor.py runs standalone; `controller.py doctor` runs the same checks through the runner. [DERIVED] (doctor.py:1-12)

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| run | def | () -> dict | doctor.py:176-196 | `__main__` (doctor.py:200); `controller.py doctor` per docstring (doctor.py:11) |
| lint_yaml | def | (path: str) -> list[str] | doctor.py:49-56 | internal (check_graph_file, check_misc_yaml) |
| check_graph_file | def | (name: str) -> list[str] | doctor.py:59-107 | internal (run) |
| check_policies | def | () -> list[str] | doctor.py:110-141 | internal (run) |
| check_schemas | def | () -> list[str] | doctor.py:144-157 | internal (run) |
| check_settings_schema | def | () -> list[str] | doctor.py:160-162 | internal (run) |
| check_misc_yaml | def | () -> list[str] | doctor.py:165-173 | internal (run) |
| _known_data_keys | def | () -> set | doctor.py:34-46 | internal (check_graph_file) |

## contracts

**run() — doctor.py:176-196**
- in: none (reads config tree rooted at `ROOT = graphmod.ROOT`, doctor.py:25)
- out: `{"ok": not errors, "errors": errors, "checked": {"graphs": GRAPHS, "policies": True, "schemas": True, "settings_schema": True, "registry_snapshot": True}}` (doctor.py:194-196)
- pre: sibling modules `graph`, `controller`, `memory`, `models`, `executors`, `transitions`, `settings`, `registry`, `market_discovery`, `product_anchored` importable via sys.path insert (doctor.py:19)
- post: `ok == True` iff `errors == []`; process exits 0 iff ok (doctor.py:194, 202)

**check_graph_file(name) — doctor.py:59-107**
- in: filename relative to `ROOT/graph/`
- out: list of error strings, `[]` when clean
- pre: file parses as YAML (early return on lint errors, doctor.py:62-64)
- post: every node type, executor, prompt file, output key, context key, evidence role, and edge condition validated (doctor.py:71-106)

**check_policies() — doctor.py:110-141**
- in: none
- out: `["policies: evidence_roles.valid missing"]` if valid roles empty (doctor.py:115-116), else cross-reference errors
- post: source_suitability / freshness_requirements / physical_product_requirements / gap-role lists all ⊆ `evidence_roles.valid` (doctor.py:117-140)

**lint_yaml(path) — doctor.py:49-56**
- in: path string
- out: `[]` on success; `"{basename}: {e}"` for YAMLError; `"{basename}: unreadable ({e})"` for OSError

## effect surface
- Files read: `ROOT/graph/{control,loadout,market_discovery,product_anchored,maintenance}_graph.yaml` (doctor.py:28-29, 61), `ROOT/prompts/{prompt}.md` existence checks (doctor.py:87-88), `ROOT/schemas/*.json` (doctor.py:146-152), `loop.yaml`, `registry/niche_scopes.yaml`, `graph/loadout_policies.yaml`, `graph/settings_schema.yaml` if present (doctor.py:167-169), policies via `graphmod.load_policies()` (doctor.py:70, 112), registry snapshot via `registry.load_snapshot()` (doctor.py:188-189), `models.new_state("probe")` (doctor.py:40)
- Files written: none. Postgres tables: none (FACTS.tables_read=[], tables_written=[]). Qdrant: none. Network/subprocess: none visible.
- Interpreter state: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` at import (doctor.py:19)
- Env flags: none read

## invariants
INVARIANT: len(GRAPHS) == 5 — {"control_graph.yaml", "loadout_graph.yaml", "market_discovery_graph.yaml", "product_anchored_graph.yaml", "maintenance_graph.yaml"} — doctor.py:28-29 [DERIVED]
  fails-if: a graph yaml added under graph/ but not to GRAPHS is never qualified before a run trusts it [INFERRED]
INVARIANT: DEFERRED_GRAPHS == set() (empty) — doctor.py:31 [DERIVED]
  fails-if: adding a graph name there silently skips executor, prompt-file, and edge-condition checks for it (doctor.py:84, 86, 105)
INVARIANT: node.type ∈ NODE_TYPES == {"reason", "retrieve", "agent", "transform", "gate", "terminal"} — doctor.py:26, 74-75 [DERIVED]
  fails-if: unknown type reported as `"unknown node type {ntype!r}"`
INVARIANT: type ∈ {"transform", "gate"} ⇒ executor non-empty — doctor.py:80-82 [DERIVED]
  fails-if: `"{ntype} node without executor"` error
INVARIANT: outputs ∪ optional_outputs ⊆ _known_data_keys() — doctor.py:90-92 [DERIVED]
  fails-if: legitimate new state key flagged `"output key {k!r} unknown to the data model"`
INVARIANT: context keys ⊆ CONTRACT_KEYS == {"require", "prefer", "exclude", "evidence_roles", "branch_scope", "budget"} — doctor.py:27, 93-96 [DERIVED]
  fails-if: unknown ContextContract key rejected
INVARIANT: edge.when ∈ transitions.CONDITIONS — doctor.py:103-106 [DERIVED]
  fails-if: `"unknown condition {cond!r}"` error
INVARIANT: gap roles from executors._GAP_DEFAULT_ROLES ∪ market_discovery._WHITESPACE_GAP_ROLES ∪ product_anchored._BRIDGE_GAP_ROLES ⊆ policies.evidence_roles.valid — doctor.py:135-140 [DERIVED]
  fails-if: compiled role lists drift outside the constitution
INVARIANT: schemas/*.json except "work_state.json" ⇒ required[] non-empty — doctor.py:153-154 [DERIVED]
  fails-if: `"no required[] — schema-lite validation would be vacuous"`
INVARIANT: registry snapshot truthy AND has "build_id" — doctor.py:190-191 [DERIVED]
  fails-if: `"registry: snapshot unavailable — CSV compile failed (run registry.py build for errors)"`
INVARIANT: exit code 0 ⇔ errors == [] — doctor.py:194, 202 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC (pure file reads; directory iteration sorted at doctor.py:147; fixed GRAPHS order at doctor.py:28-29; no clock/random/uuid/network/db/env use visible)
idempotency: SAFE (no writes of any kind; only side effect is the sys.path.insert at doctor.py:19)

## failure behaviour
- `lint_yaml`: yaml.YAMLError → `"{basename}: {e}"`; OSError → `"{basename}: unreadable ({e})"` — doctor.py:50-56
- `check_schemas`: (json.JSONDecodeError, OSError) → `"schemas/{fn}: {e}"` — doctor.py:150-156
- `run` broad `except Exception` around `check_settings_schema()` → error string `"settings schema: {e}"`, run continues — doctor.py:182-184
- `run` broad `except Exception` around registry import/load → `"registry: {e}"`, run continues — doctor.py:187-193
- check_misc_yaml/check_policies/check_schemas/check_graph_file called unguarded (doctor.py:178-180, 185) — [INFERRED] an exception there (e.g. ImportError from `import executors` at doctor.py:67) escapes run() and crashes the process
- Terminal behavior: `raise SystemExit(0 if result["ok"] else 1)` — doctor.py:202

## dumb-code flags
- `DEFERRED_GRAPHS` is an empty set yet consulted at three sites (doctor.py:84, 86, 105); comment says every graph is bound since 2026-09-03 (doctor.py:30-31) — vestigial branch kept alive.
- 16 state keys hard-coded in `_known_data_keys` (doctor.py:41-45: "handoff_packet" … "excluded_leads", labeled docs/25) duplicate knowledge living in models/controller/memory — drift risk against `models.new_state("probe")["data"]` (doctor.py:40).
- Magic filename exemption `"work_state.json"` in schema check (doctor.py:153).
- valid-roles set derived twice from the same policy payload: doctor.py:70 and doctor.py:112-113.
- `run`'s `checked` dict reports `"settings_schema": True` / `"registry_snapshot": True` even when those checks failed — [INFERRED] it records attempt, not success, which is easy to misread.

## refactor notes
- Adding a graph yaml requires updating GRAPHS (doctor.py:28-29) or it is never linted.
- Any new state key in models/controller/memory must be mirrored into `_known_data_keys` (doctor.py:38-45) or `check_graph_file` rejects every node outputting it (doctor.py:90-92).
- Return shape `{"ok", "errors", "checked"}` and exit code 0/1 are the contract consumed by `__main__` (doctor.py:200-202) and the controller runner (doctor.py:11) — changing keys breaks callers.
- Gap-role constant names `executors._GAP_DEFAULT_ROLES`, `market_discovery._WHITESPACE_GAP_ROLES`, `product_anchored._BRIDGE_GAP_ROLES` are consumed by name (doctor.py:135-137) — renaming them breaks `check_policies`.
- `sys.path.insert(0, ...)` (doctor.py:19) is required for all sibling imports; moving this file breaks every import in the module.
- Removing `DEFERRED_GRAPHS` touches doctor.py:31, 84, 86, 105 and the comment at doctor.py:30.

## VERIFY
```verify
grep -Fq 'DEFERRED_GRAPHS: set = set()' adapters/ecommerce/python/doctor.py
grep -Fq 'NODE_TYPES = {"reason", "retrieve", "agent", "transform", "gate", "terminal"}' adapters/ecommerce/python/doctor.py
grep -Fq 'raise SystemExit(0 if result["ok"] else 1)' adapters/ecommerce/python/doctor.py
grep -Fq 'if not (snap and snap.get("build_id")):' adapters/ecommerce/python/doctor.py
grep -Fq 'fn != "work_state.json" and not s.get("required")' adapters/ecommerce/python/doctor.py
test "$(grep -c -F 'maintenance_graph.yaml' adapters/ecommerce/python/doctor.py)" -ge 1
! grep -Fq 'DEFERRED_GRAPHS.append' adapters/ecommerce/python/doctor.py
```
