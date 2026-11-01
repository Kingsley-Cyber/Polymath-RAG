# unit: shared/polymath_shared/adapter/manifest.py
anchor: shared/polymath_shared/adapter/manifest.py:1-224

## purpose
Loads admitted adapter manifests from `config/adapters/*.json`, validates each with the shared JSON Schema (`contracts.validate`) plus graph-integrity invariants, and returns a frozen `Manifest` value object. Consumers are the adapter runtime and step worker (see importers below). Pure module — file reads only, no DB/network. — shared/polymath_shared/adapter/manifest.py:1, :23 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ManifestError` | class | subclass of `ValueError` | shared/polymath_shared/adapter/manifest.py:26-27 | importers (module-level) |
| `ManifestInvalid` | class | subclass of `ManifestError` | shared/polymath_shared/adapter/manifest.py:30-32 | importers (module-level) |
| `Manifest` | `@dataclass(frozen=True)` | 11 fields; `.identity -> dict[str, str]`; `.step(step_id: str) -> dict[str, Any]` | shared/polymath_shared/adapter/manifest.py:35-58 | importers (module-level) |
| `graph_integrity_errors` | def | `(raw: dict[str, Any]) -> list[str]` | shared/polymath_shared/adapter/manifest.py:61-143 | importers (module-level) |
| `load_manifest` | def | `(path: Path) -> Manifest` | shared/polymath_shared/adapter/manifest.py:203-215 | importers (module-level) |
| `list_manifests` | def | `(directory: Path = ADAPTER_DIR) -> list[Manifest]` | shared/polymath_shared/adapter/manifest.py:218-224 | importers (module-level) |
| `ADAPTER_DIR` | constant | `Path = _REPO / "config" / "adapters"` | shared/polymath_shared/adapter/manifest.py:23 | — |
| `_is_input_path` | def (private) | `(v: Any) -> bool` | shared/polymath_shared/adapter/manifest.py:17-21 | — (internal) |
| `_runtime_config_errors` | def (private) | `(s, by_id, entry) -> list[str]` | shared/polymath_shared/adapter/manifest.py:152-200 | — (internal) |

FACTS list module-level importers only (per-symbol split unknown): `shared/polymath_shared/adapter/service.py`, `shared/polymath_shared/adapter/store.py`, `shared/polymath_shared/adapter/transitions.py`, `shared/polymath_shared/adapter/_small-modules`, `workers/workers/adapter_step_worker.py` — FACTS.importers.

## contracts

### `load_manifest(path: Path) -> Manifest` — shared/polymath_shared/adapter/manifest.py:203-215
- in: path to a JSON manifest file.
- pre: contents parse as JSON (:205); `validate("adapter_manifest", raw)` + `graph_integrity_errors(raw)` both return `[]` (:208).
- post: `Manifest` built from keys `adapter_id, adapter_version, workflow_version, retrieval_policy_version, input_schema_version, output_schema_version, entry_step_id, terminal_step_id`, `budgets=dict(raw["budgets"])`, `steps={s["step_id"]: s}`, `raw=raw` (:211-215); `steps` preserves manifest insertion order (:46).
- errors: `ManifestInvalid("{name}: not JSON: {exc}")` (:206-207); `ManifestInvalid("{path.name}: " + "; ".join(errors[:5]))` (:209-210).

### `list_manifests(directory=ADAPTER_DIR) -> list[Manifest]` — shared/polymath_shared/adapter/manifest.py:218-224
- in: directory of `*.json` manifests (default `config/adapters`, :23).
- pre: every `*.json` file is a valid manifest — malformed files fail loudly, never silently skipped (:219-220).
- post: unique `adapter_id`s (:221-223); output sorted by `adapter_id` (:224).

### `graph_integrity_errors(raw) -> list[str]` — shared/polymath_shared/adapter/manifest.py:61-143
- in: raw manifest dict; out: error strings, `[]` = valid. Docstring: mirrors `tests/contracts/test_adapter_contract_v1.py` (:62).
- rules enforced (per step unless noted):

| rule | requirement | anchor |
|---|---|---|
| step ids | no duplicate `step_id` | shared/polymath_shared/adapter/manifest.py:66-67 |
| entry/terminal | both resolve to steps; terminal `type == "COMPILE_RESULT"` | shared/polymath_shared/adapter/manifest.py:69-75 |
| successors | `COMPILE_RESULT` has `next=None`; every other step's `next` is a known step | shared/polymath_shared/adapter/manifest.py:80-84 |
| branches | every branch `next` is a known step | shared/polymath_shared/adapter/manifest.py:85-87 |
| AGENT_REASON | needs `objective` + `output_schema` | shared/polymath_shared/adapter/manifest.py:88-89 |
| EXTERNAL_OPERATION | `external.system == "trailsignal"`; `availability == "planned"` needs `planned_node` | shared/polymath_shared/adapter/manifest.py:90-95 |
| DOMAIN_OPERATION | `config.domain` matches `_DOMAIN_RE`; `config.operation` matches `_DOMAIN_OP_RE`; `config.inputs` maps name -> dotted path or non-empty list of dotted paths | shared/polymath_shared/adapter/manifest.py:96-105 |
| domain keys | `config.domain` / `config.operation` invalid on non-DOMAIN_OPERATION | shared/polymath_shared/adapter/manifest.py:106-107 |
| config.show | only AGENT_REASON / HARNESS_ACTION; values start with `outputs.` / `input.` / `semantics.` | shared/polymath_shared/adapter/manifest.py:108-114 |
| BRANCH | needs `branches` or a default `next` | shared/polymath_shared/adapter/manifest.py:116-117 |
| HARNESS_ACTION | needs `harness.action_kind` + `objective`; `harness` key only valid here | shared/polymath_shared/adapter/manifest.py:118-124 |
| theta_op | only valid on AGENT_REASON | shared/polymath_shared/adapter/manifest.py:125-126 |
| BRANCH targets | may not target HARNESS_ACTION directly | shared/polymath_shared/adapter/manifest.py:127-131 |
| reachability | terminal reachable from entry via `next` + branches | shared/polymath_shared/adapter/manifest.py:132-142 |

### `_runtime_config_errors` — shared/polymath_shared/adapter/manifest.py:152-200

| key | requirement | anchor |
|---|---|---|
| `beside` | only AGENT_REASON / HARNESS_ACTION; keys match `_NAME_RE` and not in `_RESERVED_BESIDE`; values are `outputs.` / `input.` / `prefetch.` paths or non-empty lists of them | shared/polymath_shared/adapter/manifest.py:160-168 |
| `host_prefetch` | only HARNESS_ACTION; `lookups` str starting `outputs.`; `build` = `{domain, operation}` matching the two regexes | shared/polymath_shared/adapter/manifest.py:169-176 |
| `law_at_submit` | only AGENT_REASON, literal `True`; `next` must be DOMAIN_OPERATION whose `next` is BRANCH | shared/polymath_shared/adapter/manifest.py:177-182 |
| `max_live_hypotheses` | only AGENT_REASON; int (not bool) `>= 1` | shared/polymath_shared/adapter/manifest.py:183-185 |
| `context_budget` | dict over `("field_evidence", "chunk", "graph_fact", "other")`; ints `>= 0`; sum `<= 500` | shared/polymath_shared/adapter/manifest.py:186-189 |
| `seed_check` / `corpus_scope` / `corpus_seed` | entry step only; each an object (dict) | shared/polymath_shared/adapter/manifest.py:190-196 |
| `seed_check` content | names `domain` + `operation` matching the regexes | shared/polymath_shared/adapter/manifest.py:197-199 |

### `Manifest` — shared/polymath_shared/adapter/manifest.py:36-58
- `.identity` returns exactly 6 fields in order: `adapter_id, adapter_version, workflow_version, retrieval_policy_version, input_schema_version, output_schema_version` (:50-52).
- `.step(step_id)` returns the step dict or raises `ManifestError("{adapter_id}: unknown step {step_id!r}")` (:54-58).

## effect surface
- Files read: `config/adapters/*.json` via `ADAPTER_DIR` (:23); any `path` given to `load_manifest` (:205); `*.json` glob in `list_manifests` (:220).
- Imports `polymath_shared.adapter.contracts` symbols `_REPO`, `STEP_TYPES`, `validate` (:10) — FACTS.imports.
- Postgres tables: none read/written — FACTS.tables_read/tables_written empty.
- Qdrant / network / subprocess / env flags: none; module docstring says "Pure." (:1).

## invariants
INVARIANT: terminal step type == "COMPILE_RESULT" — shared/polymath_shared/adapter/manifest.py:74-75 [DERIVED]
  fails-if: ManifestInvalid at load (:210); deploy blocked, no run starts (:31-32)
INVARIANT: len(step_ids) == len(set(step_ids)) — shared/polymath_shared/adapter/manifest.py:66-67 [DERIVED]
  fails-if: "duplicate step_id" error
INVARIANT: COMPILE_RESULT.next == None — shared/polymath_shared/adapter/manifest.py:80-82 [DERIVED]
  fails-if: "{sid}: COMPILE_RESULT has no successor"
INVARIANT: context_budget sum(values) <= 500 — shared/polymath_shared/adapter/manifest.py:186-188 [DERIVED]
  fails-if: "{sid}: config.context_budget maps classes ..." error; bound is hard-coded here, not shared
INVARIANT: max_live_hypotheses >= 1 and isinstance int and not bool — shared/polymath_shared/adapter/manifest.py:183-185 [DERIVED]
  fails-if: AGENT_REASON step rejected
INVARIANT: domain regex `^[a-z][a-z0-9_]{1,40}$` governs both config.domain and seed_check.domain — shared/polymath_shared/adapter/manifest.py:13, :99, :198 [DERIVED]
  fails-if: DOMAIN_OPERATION / seed_check rejected
INVARIANT: operation regex `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,5}$` caps ids at 6 segments — shared/polymath_shared/adapter/manifest.py:14, :101 [DERIVED]
  fails-if: longer dotted operation ids rejected
INVARIANT: beside keys ∩ _RESERVED_BESIDE == ∅, _RESERVED_BESIDE = {"kind", "step", "status", "evidence", "materials", "last_rejection"} — shared/polymath_shared/adapter/manifest.py:148, :164-168 [DERIVED]
  fails-if: sibling key would shadow an adapter_next reply key
INVARIANT: EXTERNAL_OPERATION external.system == "trailsignal" — shared/polymath_shared/adapter/manifest.py:92 [DERIVED]
  fails-if: any other external system rejected
INVARIANT: terminal reachable from entry — shared/polymath_shared/adapter/manifest.py:132-142 [DERIVED]
  fails-if: "terminal step is unreachable from the entry step"
INVARIANT: adapter_id unique per directory (len(ids) == len(set(ids))) — shared/polymath_shared/adapter/manifest.py:221-223 [DERIVED]
  fails-if: ManifestInvalid "duplicate adapter_id in {directory}: {ids}"
INVARIANT: ManifestInvalid message contains <= 5 errors (errors[:5]) — shared/polymath_shared/adapter/manifest.py:210 [DERIVED]
  fails-if: silent truncation of remaining validation errors

## determinism & idempotency
determinism: DETERMINISTIC (imports only json/re/dataclasses/pathlib/typing + .contracts, shared/polymath_shared/adapter/manifest.py:4-10; sole external input is file content, :205, :220 — no clock/random/uuid/network/db/env)
idempotency: SAFE (read-only file loads; `Manifest` frozen at :35; `budgets` defensively copied via `dict(raw["budgets"])` at :214)

## failure behaviour
- `json.JSONDecodeError` caught and converted: `ManifestInvalid(f"{Path(path).name}: not JSON: {exc}")` — shared/polymath_shared/adapter/manifest.py:206-207. Nothing else is caught; no retries/defaults.
- Schema + integrity failures raise `ManifestInvalid` with `"{path.name}: " + "; ".join(errors[:5])` — shared/polymath_shared/adapter/manifest.py:208-210.
- Duplicate `adapter_id` across the directory raises `ManifestInvalid` — shared/polymath_shared/adapter/manifest.py:222-223.
- Unknown step lookup raises `ManifestError(f"{self.adapter_id}: unknown step {step_id!r}")` — shared/polymath_shared/adapter/manifest.py:57-58.
- Contract stated in docstring: `ManifestInvalid` is a deploy error "a caller never ends a run for it (bug hunt B-57)"; malformed files are never silently skipped — shared/polymath_shared/adapter/manifest.py:31-32, :219.
- FACTS.fallbacks: not present — no fallback behaviour defined.

## dumb-code flags
- `_NAME_RE` (:146) is an exact duplicate of `_DOMAIN_RE` (:13): both `^[a-z][a-z0-9_]{1,40}$` — one rule compiled twice under two names.
- Magic `5` in `errors[:5]` message truncation (:210).
- Magic `500` context_budget sum bound (:188), justified only as "the step contract's bound" — value not shared with the contract module.
- Magic segment cap 6 in `_DOMAIN_OP_RE` (`{0,5}`) (:14).
- `paths_ok` assigned as a lambda with `# noqa: E731` (:161).
- `Path(path)` re-wraps a parameter already typed `Path` (:205, :207).
- Hard-coded domain literal `"trailsignal"` (:92) in a module whose `_runtime_config_errors` docstring claims "the runtime names no domain or source" (:153).
- [INFERRED] rule conflict: a BRANCH with `branches` but no default `next` satisfies :116-117 ("BRANCH needs branches or a default next") yet still fails :83-84, because `nxt` is `None` and `None not in by_id` (unless some step lacks `step_id`, making `None` a key at :68). The `elif` at :83 exempts only COMPILE_RESULT.
- `seed_check` content validated (:197-199) but `corpus_scope` / `corpus_seed` are checked only for `isinstance(..., dict)` (:190-196) — asymmetric depth.

## refactor notes
- Five importers depend on this module (FACTS.importers: `service.py`, `store.py`, `transitions.py`, `adapter/_small-modules`, `workers/workers/adapter_step_worker.py`) — renaming `Manifest`, `ManifestError`, `ManifestInvalid`, `load_manifest`, `list_manifests`, `graph_integrity_errors`, or `ADAPTER_DIR` touches all five.
- `graph_integrity_errors` mirrors `tests/contracts/test_adapter_contract_v1.py` (:62) — any rule change must update that test in lockstep.
- `_RESERVED_BESIDE` (:148) is documented to mirror `service.RESERVED_BESIDE` (:147) — the two sets must stay in sync across files.
- Depends on contracts exports `_REPO`, `STEP_TYPES`, `validate` (:10); `ADAPTER_DIR` derives from `_REPO` (:23) — moving config layout changes both.
- `Manifest.identity` field order (:51-52) and `step()` error text (:58) are observable output; callers may match them. [INFERRED — importers not shown per-symbol in FACTS]

## VERIFY
```verify
grep -Fq 'terminal step must be COMPILE_RESULT' shared/polymath_shared/adapter/manifest.py
grep -Fq 'frozenset({"kind", "step", "status", "evidence", "materials", "last_rejection"})' shared/polymath_shared/adapter/manifest.py
grep -Fq 'sum(budget.values()) <= 500' shared/polymath_shared/adapter/manifest.py
grep -Fq 'errors[:5]' shared/polymath_shared/adapter/manifest.py
grep -Fq 'duplicate adapter_id in {directory}: {ids}' shared/polymath_shared/adapter/manifest.py
grep -Fq '_DOMAIN_OP_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,5}$")' shared/polymath_shared/adapter/manifest.py
test "$(grep -c -F 'errs.append' shared/polymath_shared/adapter/manifest.py)" -ge 30
! grep -Fq 'import asyncio' shared/polymath_shared/adapter/manifest.py
```
