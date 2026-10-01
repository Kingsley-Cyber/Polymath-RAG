# unit: adapters/ecommerce/python/settings.py
anchor: adapters/ecommerce/python/settings.py:1-314

## purpose
Hermes Preference Control Plane (docs/16) for the ecommerce adapter: the sole gate between user preferences and run behavior, driven by `graph/settings_schema.yaml` — adapters/ecommerce/python/settings.py:2-8 [DERIVED]. Hermes discovers controls via `describe`, explains via `explain`, submits compiled patches here; it never edits graph/policy/code files — adapters/ecommerce/python/settings.py:6-8 [DERIVED]. Laws: settings resolve once at init into a hashed snapshot; mid-run changes are versioned, non-retroactive `SettingsRevision`s; `SYSTEM_LOCKED` settings are visible/explainable but never settable — adapters/ecommerce/python/settings.py:10-16 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `load_schema` | def | () -> dict | adapters/ecommerce/python/settings.py:48-49 | describe:128, resolve:162, apply_revision:202, for_mode:255 |
| `load_presets` | def | () -> dict | adapters/ecommerce/python/settings.py:52-53 | validate_schema:104, describe:147, resolve:165 |
| `validate_schema` | def | () -> list[str] | adapters/ecommerce/python/settings.py:71-115 | doctor hook (docstring 72) |
| `describe` | def | (mode: str \| None = None) -> dict | adapters/ecommerce/python/settings.py:124-148 | main:274-275; Hermes (docstring 6-7) |
| `explain` | def | (setting_id: str) -> dict | adapters/ecommerce/python/settings.py:151-155 | main:276-277 |
| `resolve` | def | (overrides: dict \| None = None, preset: str \| None = None) -> dict | adapters/ecommerce/python/settings.py:159-189 | apply_revision:203; main:286 |
| `apply_revision` | def | (state: dict, patch: dict, requested_by: str = "USER") -> dict | adapters/ecommerce/python/settings.py:198-238 | apply_overrides_mid_run:243; main:300 |
| `apply_overrides_mid_run` | def | (state: dict, overrides: dict) -> dict | adapters/ecommerce/python/settings.py:242-244 | legacy callers/tests pre-dating docs/16 (comment 241) |
| `effective` | def | (state: dict, key: str, fallback) -> value | adapters/ecommerce/python/settings.py:247-250 | runtime consumers (docstring 248-249) |
| `for_mode` | def | (state: dict, mode: str \| None) -> dict | adapters/ecommerce/python/settings.py:253-258 | workers (docstring 254) |
| `main` | def | () -> int | adapters/ecommerce/python/settings.py:262-310 | CLI (`settings.py describe/explain/presets/resolve/apply`, docstring 18-22) |
| `_doc` | def (private) | () -> dict | adapters/ecommerce/python/settings.py:44-45 | load_schema, load_presets |
| `_check_value` | def (private) | (key: str, spec: dict, val) -> str \| None | adapters/ecommerce/python/settings.py:57-68 | validate_schema:99, resolve:180, apply_revision:218 |
| `_applies` | def (private) | (spec: dict, mode: str \| None) -> bool | adapters/ecommerce/python/settings.py:119-121 | describe:130, for_mode:257 |
| `_hash` | def (private) | (resolved: dict) -> str | adapters/ecommerce/python/settings.py:192-194 | resolve:188, apply_revision:235 |

## contracts

**resolve(overrides, preset)** — adapters/ecommerce/python/settings.py:159-189
- in: preset applied first, overrides applied second (overrides win) — :168-169 [DERIVED]
- pre: preset must be a key of `load_presets()` — :166-167; every patch key must exist in schema — :173-174; `SYSTEM_LOCKED` keys refused — :176-178; values must pass `_check_value` — :180 [DERIVED]
- out: `{"resolved", "hash", "preset": preset or None, "revisions": []}` — :188-189; `resolved` = defaults of all non-`SYSTEM_LOCKED` keys + patch — :185-187 [DERIVED]
- post: on any violation raises `ValueError("; ".join(errors))` listing every violation — :183-184 [DERIVED]

**apply_revision(state, patch, requested_by)** — adapters/ecommerce/python/settings.py:198-238
- in: `state["settings"]` optional; defaults to fresh `resolve()` — :203 [DERIVED]
- pre: each patch key in schema and not `SYSTEM_LOCKED` ("not settable") — :207-209; `mutability != "INIT_ONLY"` — :211-213; `BEFORE_PORTFOLIO` keys rejected only when `state["node"]` ∈ `_PORTFOLIO_LOCKED_NODES` — :214-216; value valid — :218 [DERIVED]
- out: revision `{"revision": len(revisions)+1, "previous_hash", "patch": changes, "requested_by", "effective_from_node": state.get("node"), "retroactive": False, "at": models.now()}` — :228-232 [DERIVED]
- post: `state["settings"]` replaced with merged resolved + new hash + appended revision — :233-237; raises `ValueError("; ".join(errors))` otherwise — :221-222 [DERIVED]
- note: `changes` records only keys whose value differs — :224-225 [DERIVED]

**validate_schema()** — adapters/ecommerce/python/settings.py:71-115
- out: list of `"settings_schema.<key>: ..."` / `"presets.<pname>: ..."` error strings; empty = valid [DERIVED]
- checks: authority in `_AUTHORITIES` — :77-79; `default` present — :80-81; `SYSTEM_LOCKED` requires `reason` and skips the rest — :82-85; non-locked require `label`+`description` — :86-87; enum requires `allowed[]` — :89-91; integer requires `min`/`max` — :92-94; `mutability` in `_MUTABILITIES` — :97-98; `cannot_affect` declared — :102-103; presets reference known, non-locked keys with valid values — :104-114 [DERIVED]

**describe(mode)** — adapters/ecommerce/python/settings.py:124-148
- out: `{"adjustable": [...], "locked": [...], "presets": sorted(...)}` — :127, :147; adjustable rows carry `type/allowed/range/mutability/cost_effect/description` — :139-145; locked rows carry `reason` — :136 [DERIVED]

**effective(state, key, fallback)** — adapters/ecommerce/python/settings.py:247-250
- out: `state.settings.resolved.get(key, fallback)` — :250; `SYSTEM_LOCKED` values never appear here because `resolve()` excludes them — :185-186, :249 [DERIVED]

**main() / CLI apply** — adapters/ecommerce/python/settings.py:262-310
- pre: refuses when `state["status"] == "stopped"` — :294-296 [DERIVED]
- post: on success saves state, records `memory.record_event(state["run_id"], "SETTINGS_REVISED", revision)`, prints revision + hash + `"law": "non-retroactive — effective from the next action"`, exit 0 — :304-310 [DERIVED]

## effect surface
- File read: `graph/settings_schema.yaml` via `SCHEMA_PATH = os.path.join(graphmod.ROOT, "graph", "settings_schema.yaml")` and `graphmod.load_yaml_file` — adapters/ecommerce/python/settings.py:36, :45; top-level keys `"settings_schema"` — :49, `"presets"` — :53 [DERIVED]
- File read: JSON `--file` for resolve overrides — :283-284 and apply patch — :297-298 [DERIVED]
- File read/write: run-state JSON via `models.load_state` — :293 / `models.save_state` — :304 [DERIVED]
- Event-log write: `memory.record_event(run_id, "SETTINGS_REVISED", revision)` — :305 [DERIVED]
- Import mechanism: `sys.path.insert(0, dirname(__file__))` — :32 enables `import graph as graphmod` — :34 and function-local `import models`/`import memory` — :227, :291-292 [DERIVED]
- Postgres tables: none (FACTS `tables_read`/`tables_written` empty). Qdrant/network/subprocess/env flags: none.

## invariants
INVARIANT: len(hash) == 16 hex chars (`hexdigest()[:16]`) — adapters/ecommerce/python/settings.py:193-194 [DERIVED]
  fails-if: `previous_hash` chaining (:229) and init-pinning (:213) become incomparable across runs.
INVARIANT: revision["retroactive"] == False — adapters/ecommerce/python/settings.py:232 [DERIVED]
  fails-if: earlier steps' settings meaning silently changes mid-run, violating law at :15-16.
INVARIANT: revision["revision"] == len(settings["revisions"]) + 1 — adapters/ecommerce/python/settings.py:228 [DERIVED]
  fails-if: duplicate revision numbers break the audit trail.
INVARIANT: count(SYSTEM_LOCKED keys in resolve()["resolved"]) == 0 — adapters/ecommerce/python/settings.py:185-186 [DERIVED]
  fails-if: evidence/authority ceilings become per-run settable, violating law at :11-13.
INVARIANT: presets ∩ SYSTEM_LOCKED == ∅ (enforced by validate_schema) — adapters/ecommerce/python/settings.py:109-110 [DERIVED]
  fails-if: a preset smuggles a locked override past `resolve()`.
INVARIANT: `_check_value` integer branch rejects bool — adapters/ecommerce/python/settings.py:63 [DERIVED] (`not isinstance(val, int) or isinstance(val, bool)`)
  fails-if: `True`/`False` accepted as `1`/`0`, bypassing min/max intent.
INVARIANT: BEFORE_PORTFOLIO mutation blocked iff `state["node"]` ∈ `{"portfolio", "community_skeptic", "apply_skeptic", "loadout_gate", "stop"}` — adapters/ecommerce/python/settings.py:40-41, :214 [DERIVED]
  fails-if: pre-portfolio settings change after portfolio selection.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `models.now()` stamped into every revision — adapters/ecommerce/python/settings.py:227, :232; file inputs: schema YAML — :45, state/patch JSON — :283, :293, :297). `_hash` itself is deterministic: sha256 over `json.dumps(resolved, sort_keys=True, default=str)` — :193-194 [DERIVED]
idempotency: UNSAFE — `apply_revision` appends a revision on every accepted call even when the patch equals current values (`changes` may be `{}` at :224-225, revision still appended at :236); repeated CLI `apply` re-saves state and re-records the `SETTINGS_REVISED` event — :304-305 [DERIVED]

## failure behaviour
- `resolve` and `apply_revision` raise `ValueError` with all violations joined by `"; "` — adapters/ecommerce/python/settings.py:184, :222 [DERIVED]
- CLI catches `ValueError` for `resolve` and `apply`, prints `{"ok": false, "error": "SETTINGS_REJECTED", "detail": ...}`, exit 1 — :287-289, :301-303 [DERIVED]
- Unknown preset: `ValueError("unknown preset {preset!r} (known: ...)")` — :166-167 [DERIVED]
- `explain` does not raise: returns `{"ok": False, "error": "unknown setting ..."}` — :154 [DERIVED]
- CLI apply on stopped run prints `{"ok": false, "error": "terminal run — settings frozen forever"}`, exit 1 — :294-296 [DERIVED]
- No handlers around file reads (:283-284, :297-298) or `models.load_state` (:293): IO/JSON errors propagate uncaught to the CLI caller [DERIVED]

## dumb-code flags
- Dual-key lookup duplicated 6x with flipped precedence: `spec.get("authority") or spec.get("level")` at :77 vs `spec.get("level") or spec.get("authority")` at :132, :170, :186, :208, :303 — if a spec ever sets both keys, the winner differs by call site [DERIVED]
- Mixed error styles: `_check_value` returns error strings/None (:57-68) while callers raise `ValueError` (:184, :222) [DERIVED]
- Shallow copy then shared mutation: `settings = dict(settings)` at :233, but `setdefault("revisions", []).append(revision)` at :236 mutates the list object shared with the pre-copy dict [INFERRED] (list identity survives `dict()` copy)
- Magic number: hash truncated to `[:16]` — :194 [DERIVED]
- CLI `resolve` prints rejection without `indent=1` while success uses `indent=1` — :286 vs :288 [DERIVED]
- `apply_overrides_mid_run` discards `apply_revision`'s return and returns `state["settings"]` — legacy callers never see the revision — :243-244 [DERIVED]
- Deferred `import models`/`import memory` inside function bodies — :227, :291-292; reason (circular-avoidance?) undocumented [DERIVED]

## refactor notes
- `_PORTFOLIO_LOCKED_NODES` literals must match graph node names written into `state["node"]` by the run engine — adapters/ecommerce/python/settings.py:40-41, :214-216 [DERIVED]
- Schema YAML shape is a hard contract: top keys `settings_schema`/`presets` (:49, :53); per-spec keys `authority`|`level`, `default`, `label`, `description`, `reason`, `type` (`enum`|`integer`), `allowed`, `min`/`max`, `mutability`, `cannot_affect`, `modes`, `cost_effect` (:77-103, :119-121, :139-145) [DERIVED]
- State keys `"settings"`, `"resolved"`, `"hash"`, `"revisions"`, `"node"`, `"run_id"`, `"status"` are read/written here and persisted via `models` (:203-204, :237, :293-295, :304); renaming breaks saved runs [DERIVED]
- Event name `"SETTINGS_REVISED"` is a literal contract with the memory/event log — :305 [DERIVED]
- `apply_overrides_mid_run` must stay until pre-docs/16 callers/tests are removed — :241-244 [DERIVED]
- `resolve()` return shape `{"resolved","hash","preset","revisions"}` is consumed by `apply_revision` (:203-204) and CLI apply (:307) [DERIVED]
- `sys.path.insert` sibling-import trick (:32) means moving/renaming this file breaks `import graph`/`models`/`memory` [DERIVED]

## VERIFY
```verify
grep -Fq '"INIT_ONLY", "DURING_RUN", "BEFORE_PORTFOLIO"' adapters/ecommerce/python/settings.py
grep -Fq 'terminal run — settings frozen forever' adapters/ecommerce/python/settings.py
grep -Fq 'settings_schema.yaml' adapters/ecommerce/python/settings.py
grep -Eq 'retroactive.: False' adapters/ecommerce/python/settings.py
test "$(grep -c -F 'SETTINGS_REJECTED' adapters/ecommerce/python/settings.py)" -ge 2
! grep -Fq 'import requests' adapters/ecommerce/python/settings.py
```
