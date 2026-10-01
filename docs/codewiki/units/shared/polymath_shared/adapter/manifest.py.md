# unit: shared/polymath_shared/adapter/manifest.py
anchor: shared/polymath_shared/adapter/manifest.py:1-166

## purpose
Loads and validates admitted adapter manifests (`config/adapters/*.json`): JSON Schema validation via `contracts.validate` plus graph-integrity invariants the schema cannot express. Declared "Pure." — no DB, network, or writes. Consumed by the adapter service/store/transitions and the adapter step worker. — shared/polymath_shared/adapter/manifest.py:1 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Manifest` | frozen dataclass | 11 fields + `raw` | shared/polymath_shared/adapter/manifest.py:35-58 | module importers (below) |
| `Manifest.identity` | property | -> dict[str, str] (6 keys) | shared/polymath_shared/adapter/manifest.py:49-52 | module importers |
| `Manifest.step` | method | (step_id: str) -> dict[str, Any] | shared/polymath_shared/adapter/manifest.py:54-58 | module importers |
| `ManifestError` | class | subclass of `ValueError` | shared/polymath_shared/adapter/manifest.py:26-27 | module importers |
| `ManifestInvalid` | class | subclass of `ManifestError` | shared/polymath_shared/adapter/manifest.py:30-32 | module importers |
| `graph_integrity_errors` | def | (raw: dict[str, Any]) -> list[str] | shared/polymath_shared/adapter/manifest.py:61-142 | `load_manifest` (manifest.py:150) |
| `load_manifest` | def | (path: Path) -> Manifest | shared/polymath_shared/adapter/manifest.py:145-157 | `list_manifests` (manifest.py:162) |
| `list_manifests` | def | (directory: Path = ADAPTER_DIR) -> list[Manifest] | shared/polymath_shared/adapter/manifest.py:160-166 | module importers |
| `_is_input_path` | def (private) | (v: Any) -> bool | shared/polymath_shared/adapter/manifest.py:17-21 | `graph_integrity_errors` (manifest.py:104) |
| `ADAPTER_DIR` | module constant | `_REPO / "config" / "adapters"` | shared/polymath_shared/adapter/manifest.py:23 | default of `list_manifests` |

Module importers (FACTS.importers): `shared/polymath_shared/adapter/_small-modules`, `service.py`, `store.py`, `transitions.py`, `workers/workers/adapter_step_worker.py` — shared/polymath_shared/adapter/manifest.py:79-84 [DERIVED]

## contracts

**load_manifest(path)** — manifest.py:145-157
- in: any path; file read with `Path(path).read_text()` then `json.loads` (147).
- out: frozen `Manifest` (153-157) or raises `ManifestInvalid`.
- pre: none; malformed JSON is caught, not assumed absent (148-149).
- post: `steps={s["step_id"]: s for s in raw["steps"]}` — insertion order = manifest file order (46, 157); `budgets=dict(raw["budgets"])` shallow copy (156).
- check: errors = `validate("adapter_manifest", raw) + graph_integrity_errors(raw)` (150); non-empty → `ManifestInvalid(f"{path.name}: " + "; ".join(errors[:5]))` (152).

**list_manifests(directory=ADAPTER_DIR)** — manifest.py:160-166
- in: directory, default `ADAPTER_DIR` = `_REPO / "config" / "adapters"` (23).
- out: manifests `sorted(out, key=lambda m: m.adapter_id)` (166).
- post: every `sorted(Path(directory).glob("*.json"))` is loaded; a malformed file raises — "fails LOUDLY (never silently skipped)" (161-162).
- check: duplicate `adapter_id` → `ManifestInvalid` (164-165).

**graph_integrity_errors(raw)** — manifest.py:61-142
- in: raw manifest dict; out: list of error strings (empty = valid); docstring says it "mirrors tests/contracts/test_adapter_contract_v1.py" (62).

**Manifest.step(step_id)** — manifest.py:54-58
- out: `self.steps[step_id]`; `KeyError` → `ManifestError(f"{self.adapter_id}: unknown step {step_id!r}")` with `from None` (58).

**Manifest.identity** — manifest.py:49-52: exactly the keys `adapter_id, adapter_version, workflow_version, retrieval_policy_version, input_schema_version, output_schema_version`.

## effect surface
- Files read: `*.json` under `config/adapters` (glob 162, read_text 147, `ADAPTER_DIR` 23). No file writes.
- Postgres: none — FACTS.tables_read/tables_written empty. Qdrant/network/subprocess: none.
- Repo coupling: `_REPO` imported from `.contracts` (10) and evaluated at import time into `ADAPTER_DIR` (23).

## invariants

INVARIANT: `type(by_id[terminal_step_id])` == `"COMPILE_RESULT"` — manifest.py:74-75 [DERIVED]
  fails-if: manifest rejected at load; terminal is the only mandated step type.
INVARIANT: `COMPILE_RESULT.next` is `None`; every other type's `next` ∈ step_ids — manifest.py:80-84 [DERIVED]
  fails-if: dangling successor reference rejected.
INVARIANT: every branch target ∈ step_ids — manifest.py:85-87 [DERIVED]
INVARIANT: terminal step reachable from entry step (DFS over `next` + `branches`) — manifest.py:131-141 [DERIVED]
  fails-if: unreachable terminal rejected ("terminal step is unreachable from the entry step", 141).
INVARIANT: len(step_ids) == len(set(step_ids)) — manifest.py:65-67 [DERIVED]
INVARIANT: EXTERNAL_OPERATION `external.system` == `"trailsignal"` — manifest.py:92-93 [DERIVED]
INVARIANT: `availability == "planned"` implies `planned_node` present — manifest.py:94-95 [DERIVED]
INVARIANT: domain matches `^[a-z][a-z0-9_]{1,40}$` AND operation matches `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,5}$` — manifest.py:13-14, 99-102 [DERIVED]
INVARIANT: `theta_op` only on AGENT_REASON; `harness` key only on HARNESS_ACTION (which needs `harness.action_kind` + `objective`) — manifest.py:119-125 [DERIVED]
INVARIANT: BRANCH may not target HARNESS_ACTION directly — manifest.py:126-130 [DERIVED]
INVARIANT: `config.show` only on AGENT_REASON/HARNESS_ACTION, values start with `"outputs."`/`"input."`/`"semantics."` — manifest.py:108-114 [DERIVED]
INVARIANT: errors surfaced by load_manifest ≤ 5 (`errors[:5]`) — manifest.py:152 [DERIVED]

## determinism & idempotency
determinism: DETERMINISTIC — pure functions over file contents; sorted glob ordering (manifest.py:162); only external input is `_REPO` from `.contracts` (manifest.py:10).
idempotency: SAFE — read-only; repeated loads yield equal frozen dataclasses (`frozen=True`, manifest.py:35).

## failure behaviour
- `json.JSONDecodeError` → `ManifestInvalid(f"{Path(path).name}: not JSON: {exc}")` — manifest.py:148-149; nothing swallowed.
- Schema + graph errors → `ManifestInvalid` with up to 5 errors joined by `"; "` — manifest.py:150-152.
- `list_manifests`: malformed file propagates through the list comprehension (no try/except, 162); duplicate adapter_id → `ManifestInvalid(f"duplicate adapter_id in {directory}: {ids}")` (165).
- `Manifest.step`: KeyError converted to `ManifestError` — manifest.py:56-58.
- `ManifestInvalid` is a deploy-time error: "a caller never ends a run for it (bug hunt B-57)" — manifest.py:30-32.

## dumb-code flags
- Magic numbers: `{1,40}` domain length cap (13), `{0,5}` max dotted segments (14), `errors[:5]` truncation (152).
- Step-type strings repeated inline instead of constants: `"COMPILE_RESULT"` (74, 80), `"AGENT_REASON"` (88, 111, 124, 125), `"HARNESS_ACTION"` (111, 119, 122, 126, 129), `"DOMAIN_OPERATION"` (96, 106, 107) — only `STEP_TYPES` is imported (10, 78).
- `"trailsignal"` hard-coded (92-93).
- Show-path prefixes tuple `("outputs.", "input.", "semantics.")` inline; singular `"input."` vs plural `"outputs."` is an easy typo (113).
- Duplicate-step_id check uses `s.get("step_id")`; a missing step_id collapses to `None` and two missing ids collide (65-67) — schema check at 150 presumably catches absence [INFERRED].
- `_is_input_path` accepts any non-empty string as a path; no dotted-shape validation (19-21) [INFERRED from absence of a shape check].
- `ADAPTER_DIR` frozen at import time from `_REPO`; only the `directory` parameter can override it (23, 160).

## refactor notes
- Any change to `graph_integrity_errors` checks must be mirrored in `tests/contracts/test_adapter_contract_v1.py` (docstring, manifest.py:62).
- `Manifest` field set/order (37-47) and `identity` key list (51-52) are consumed by service.py, store.py, transitions.py, adapter_step_worker.py, _small-modules (FACTS.importers) — rename blast radius spans five modules.
- `validate("adapter_manifest", raw)` names a schema owned by `polymath_shared.adapter.contracts` (10, 150) — cross-module contract.
- Checks encode ADR-0019 (harness/theta/evidence-loop rules, 117-118, 119-130) and ADR-0020 (domain naming + `config.show`, 12, 97, 110); relaxing them changes adapter-graph policy, not just validation.
- Keep `ManifestInvalid` reserved for deploy-time set errors (B-57 semantics, 30-32); do not raise it for per-run failures.

## VERIFY
```verify
grep -Fq 'terminal step must be COMPILE_RESULT' shared/polymath_shared/adapter/manifest.py
grep -Fq 'ext.get("system") != "trailsignal"' shared/polymath_shared/adapter/manifest.py
grep -Fq 'ADAPTER_DIR = _REPO / "config" / "adapters"' shared/polymath_shared/adapter/manifest.py
grep -Fq 'errors[:5]' shared/polymath_shared/adapter/manifest.py
grep -Fq 'frozen=True' shared/polymath_shared/adapter/manifest.py
test "$(grep -c -F 'errs.append' shared/polymath_shared/adapter/manifest.py)" -ge 20
! grep -Fq 'except Exception' shared/polymath_shared/adapter/manifest.py
```
