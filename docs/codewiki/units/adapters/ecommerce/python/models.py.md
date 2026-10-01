# unit: adapters/ecommerce/python/models.py
anchor: adapters/ecommerce/python/models.py:1-198

## purpose
Deterministic data layer for the ecommerce skill: schema-lite JSON validation driven directly by the `schemas/` files, plus work-state IO (`load_state`/`save_state`) with one-time legacy-key migration on load. Docstring claims no third-party deps beyond PyYAML and that `schemas/` stays the single source of truth. Comments reference a "controller" as the caller. [DERIVED] models.py:1-6, models.py:54, models.py:114

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| now | def | () -> str | models.py:18-19 | — |
| stable_id | def | (*parts: str) -> str | models.py:22-23 | — |
| load_schema | def | (name: str) -> dict | models.py:26-28 | — |
| validate | def | (obj: dict, schema_name: str) -> list[str] | models.py:98-107 | — |
| new_state | def | (run_id: str, signal: str = "") -> dict | models.py:110-164 | — |
| load_state | def | (path: str) -> dict | models.py:189-191 | — |
| save_state | def | (state: dict, path: str) -> None | models.py:194-198 | — |

Private helpers: `_type_ok` (31-46), `_walk` (49-95), `_migrate_legacy` (174-186). FACTS lists no importers.

## contracts

**validate(obj, schema_name)** models.py:98-107
- in: any `obj`; `schema_name` resolving to `schemas/<name>.json` models.py:26-28
- out: `list[str]` of violations; empty list = valid models.py:98-99, 106
- pre: schema file exists and parses as JSON models.py:26-28
- post: non-dict `obj` returns exactly `[f"{schema_name}: not an object"]` models.py:103-104
- supported subset: type (incl. list-of-types and `{"enum": [...]}` shorthand), enum, required, properties, items, additionalProperties, minItems/maxItems, minimum/maximum models.py:50-54
- error shape: `"{path}: ..."`, `"{path}.{key}: required"`, `"{path}[{i}]"` for array items models.py:60, models.py:73, models.py:85

**new_state(run_id, signal="")** models.py:110-164
- out: dict with `"run_id"`, `"created_at": now()`, `"node": None`, `"status": "running"`, `"rounds": {"research": 0}`, `"history": []`, `"verdict": None` models.py:111-119
- post: `data` dict initialized with ~40 empty keys, incl. `corpus_packets` (docs/22 v2.2.0 comment), `population_leads`..`provenance` (LIVED-WORLD-V2, docs/25), `latent_structures`/`corpus_observations`/`row_relevance` (docs/26) models.py:120-163

**load_state(path)** models.py:189-191
- out: parsed state dict after `_migrate_legacy` models.py:174-186
- post: data key `"polymath_evidence"` renamed to `"corpus_evidence"` via `setdefault` models.py:177-179; observations' `source_identity.source_family` `"polymath_evergreen"` → `"corpus_evergreen"` models.py:180-183; top-level `"node"` `"polymath"` → `"corpus"` models.py:184-185

**save_state(state, path)** models.py:194-198
- post: writes `path + ".tmp"` with `indent=1`, `ensure_ascii=False`, then `os.replace(tmp, path)` (atomic swap)

**stable_id(*parts)** models.py:22-23
- out: `hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]`

**now()** models.py:18-19
- out: `datetime.now(timezone.utc).isoformat(timespec="seconds")` (UTC, second precision)

**_type_ok(value, t)** models.py:31-46
- `bool` rejected for both `"integer"` and `"number"`; unknown type words return `True` (fail-open) models.py:41-43, models.py:46

## effect surface
| kind | item | anchor |
|---|---|---|
| file read | `schemas/<name>.json` (via `SCHEMAS = os.path.join(ROOT, "schemas")`, ROOT = two dirs above `__file__`) | models.py:14-15, models.py:26-28 |
| file read | state JSON at caller-supplied `path` | models.py:189-191 |
| file write | `path + ".tmp"`, then renamed onto `path` via `os.replace` | models.py:195-198 |
| clock | `datetime.now(timezone.utc)` | models.py:19 |
| Postgres / network / subprocess / env flags | none (FACTS `tables_read: []`, `tables_written: []`; no such calls in source) | models.py:1-198 |

## invariants
INVARIANT: stable_id output length == 12 — `hexdigest()[:12]` models.py:23 [DERIVED]
  fails-if: persisted 12-char IDs no longer match regenerated ones.
INVARIANT: bool is not an `"integer"` and not a `"number"` — models.py:41-43 [DERIVED]
  fails-if: `True` accepted as `1` by validation.
INVARIANT: required means present AND `value[key] not in (None, "")` — models.py:71-73 [DERIVED]
  fails-if: empty-string required fields pass validation.
INVARIANT: `new_state["status"] == "running"` and `new_state["rounds"] == {"research": 0}` — models.py:115-116 [DERIVED]
  fails-if: controller expects a fresh run in a different initial status/round shape.
INVARIANT: save_state serializes with `indent=1, ensure_ascii=False` — models.py:197 [DERIVED]
  fails-if: state-file diffs/reads relying on that formatting break.
INVARIANT: `_walk` returns immediately after a type mismatch — at most one type error per path — models.py:64-66 [DERIVED]
  fails-if: callers counting errors per field see duplicates or gaps.
INVARIANT: unknown `"type"` word passes `_type_ok` (returns True) — models.py:46 [DERIVED]
  fails-if: schema typo silently validates anything.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `datetime.now` models.py:19 — FACTS nondeterminism entry; reachable via `new_state` → `"created_at": now()` models.py:113. All other functions use only hashlib/json/os.) [DERIVED]
idempotency: SAFE — `load_state` is a pure read + in-memory migration models.py:189-191; `save_state` on an unchanged state writes identical bytes and is atomic via tmp + `os.replace` models.py:194-198. `new_state` re-invocation differs only in `created_at` models.py:113. [INFERRED — same state in, same file out.]

## failure behaviour
No try/except anywhere in the file; all IO/JSON errors propagate raw to the caller. [DERIVED — visible absence over models.py:1-198]
`validate` never raises on bad data: violations come back as strings; non-dict returns a single-message list. models.py:98-107 [DERIVED]
`_type_ok` fails open on unrecognized type words rather than rejecting. models.py:46 [DERIVED]
If `json.dump` fails mid-write, `path + ".tmp"` can be left behind — `os.replace` at models.py:198 only runs after a successful dump. [INFERRED]

## dumb-code flags
- Docstring: "No third-party deps beyond PyYAML (already in the Hermes venv)" — yet this file imports no `yaml`; validation is stdlib-only. models.py:3 vs models.py:10-12 [DERIVED]
- Magic number `12` in `hexdigest()[:12]` — unexplained truncation. models.py:23 [DERIVED]
- Three parallel legacy maps hardcoded side by side; FACTS even mislabels two of their keys (`polymath_evidence`, `polymath_evergreen`) as "collections" — they are only dict keys here. models.py:169-171 [DERIVED]
- `_migrate_legacy` uses `data.setdefault(new, data.pop(old))`: if a state carries both old and new keys, the old value is popped and silently discarded. models.py:179 [INFERRED — setdefault keeps the existing new value]
- `minimum`/`maximum` enforced only in the numeric branch — a value passing as wrong-shape never reaches them. models.py:91-96 [DERIVED]

## refactor notes
- `SCHEMAS` is derived from `__file__` two levels up; moving this file breaks all schema loading. models.py:14-15 [DERIVED]
- The `data` key names inside `new_state` are a persisted state-file contract (~40 keys); any rename must extend `_LEGACY_DATA_KEYS` / `_LEGACY_NODES` / `_LEGACY_SOURCE_FAMILIES` or old run states break. models.py:120-163, models.py:169-171 [DERIVED]
- Atomic save depends on the `path + ".tmp"` + `os.replace` pattern; writing in place removes crash safety. models.py:195-198 [DERIVED]
- `validate` error-string shapes (`"{path}.{key}: required"`, `not in {enum}`) may be matched by callers/tests. models.py:60-96 [INFERRED — string API, external matchers unknown]
- `stable_id`'s 12-char format is embedded in any stored IDs; changing it desynchronizes history. models.py:23 [INFERRED]
- The `{"enum": [...]}` type shorthand is load-bearing for "two schemas" per the docstring. models.py:51-53, models.py:58-61 [DERIVED]

## VERIFY
```verify
grep -Fq 'return datetime.now(timezone.utc).isoformat(timespec="seconds")' adapters/ecommerce/python/models.py
grep -Fq '_LEGACY_DATA_KEYS = {"polymath_evidence": "corpus_evidence"}' adapters/ecommerce/python/models.py
grep -Fq 'os.replace(tmp, path)' adapters/ecommerce/python/models.py
grep -Fq 'hexdigest()[:12]' adapters/ecommerce/python/models.py
test "$(grep -c -F '"status": "running",' adapters/ecommerce/python/models.py)" -ge 1
test "$(grep -c -F '"rounds": {"research": 0},' adapters/ecommerce/python/models.py)" -ge 1
! grep -Fq 'import yaml' adapters/ecommerce/python/models.py
```
