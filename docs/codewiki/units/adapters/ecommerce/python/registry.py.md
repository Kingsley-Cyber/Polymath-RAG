# unit: adapters/ecommerce/python/registry.py
anchor: adapters/ecommerce/python/registry.py:1-373

## purpose
Compiles TrailSignal CSV registry tables into ONE immutable, hash-pinned `RegistrySnapshot` the runtime consumes for a whole run; live CSV edits never silently change runtime behavior — a new build does (adapters/ecommerce/python/registry.py:1-20) [DERIVED]. CLI subcommands: `build`, `status`, `candidates`, `diversity`, `query` (adapters/ecommerce/python/registry.py:285-292) [DERIVED]. Consumers: the adapter runtime via `load_snapshot` (governed binding, AUTO_DECISIONS M-014, adapters/ecommerce/python/registry.py:32-33) and maintainers via the CLI [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `_split` | def | `(v: str) -> list[str]` | adapters/ecommerce/python/registry.py:58-66 | — |
| `_read` | def | `(name: str) -> list[dict]` | adapters/ecommerce/python/registry.py:69-71 | — |
| `_sha` | def | `(name: str) -> str` | adapters/ecommerce/python/registry.py:74-76 | — |
| `compile_registry` | def | `() -> tuple[dict \| None, list[str]]` | adapters/ecommerce/python/registry.py:79-253 | — |
| `load_snapshot` | def | `() -> dict \| None` | adapters/ecommerce/python/registry.py:256-279 | — |
| `main` | def | `() -> int` (returns `0`/`1`) | adapters/ecommerce/python/registry.py:282-368 | entry `__main__` at adapters/ecommerce/python/registry.py:371-372 |

No FACTS importers listed; used by is "—" for all [DERIVED].

## contracts

**`compile_registry`** (adapters/ecommerce/python/registry.py:79-253)
- in: CSVs from `SRC` — six `SOURCES` tables plus all `*_activity_niche_seed.csv` packs via sorted glob (adapters/ecommerce/python/registry.py:85-95) [DERIVED]
- out: `(snapshot, [])` on success; `(None, errors)` on any validation error (adapters/ecommerce/python/registry.py:258) [DERIVED]
- pre: each seed row's `fact_status` ∈ `{"hypothesis", "seed", "observed", "validated"}`; `task`/`context` non-empty; `friction_family` (if set) must exist in `friction_library` (adapters/ecommerce/python/registry.py:120-126) [DERIVED]
- post: `snapshot["build_id"] == "reg_" + sha256(content)[:12]` where content is the JSON dump with `build_id` still `None` (adapters/ecommerce/python/registry.py:223, 251-252) [DERIVED]

**`load_snapshot`** (adapters/ecommerce/python/registry.py:256-279)
- in: env `OPPORTUNITY_RESEARCH_REGISTRY`; file `OUT` = `registry/compiled/registry_snapshot.json` (adapters/ecommerce/python/registry.py:35, 257) [DERIVED]
- out: snapshot dict or `None` [DERIVED]
- pre: if env == `"compile"` → governed mode, never reads or writes the build cache (adapters/ecommerce/python/registry.py:257-261) [DERIVED]
- post: corrupt `OUT` (`json.JSONDecodeError`) → returns `None`, file left in place; missing `OUT` (fresh checkout) → compiles and persists first build; stale snapshot never rebuilt here (adapters/ecommerce/python/registry.py:262-278) [DERIVED]

**`_split`** (adapters/ecommerce/python/registry.py:58-66)
- in: any string; out: split on `;` only, trimmed, empties dropped, order kept, case-insensitive dedupe preserving first-seen casing (adapters/ecommerce/python/registry.py:61-66) [DERIVED]

## effect surface

| kind | target | anchor |
|---|---|---|
| env read | `OPPORTUNITY_RESEARCH_REGISTRY_SRC` = `null` → falls back to `os.path.join(ROOT, "registry", "trailsignal")` | adapters/ecommerce/python/registry.py:34 |
| env read | `OPPORTUNITY_RESEARCH_REGISTRY` = `null` (compared `== "compile"`) | adapters/ecommerce/python/registry.py:257 |
| file read | `{SRC}/{name}.csv` × 6 (`SOURCES`) | adapters/ecommerce/python/registry.py:37-38, 69-71 |
| file read | `SRC/*_activity_niche_seed.csv` (sorted glob) | adapters/ecommerce/python/registry.py:85 |
| file read | `ROOT/registry/niche_scopes.yaml` (optional overlay) | adapters/ecommerce/python/registry.py:216 |
| file write | `ROOT/registry/compiled/registry_snapshot.json` (`OUT`) | adapters/ecommerce/python/registry.py:35, 277-278, 301-302 |
| table read | `work_nodes` where `node_type='REGISTRY_CANDIDATE'` (cols `payload_json`, `run_id`) via `memory.connect()` | adapters/ecommerce/python/registry.py:313-317 |
| subprocess / network | none visible | — |

`tables_written` is empty per FACTS; the only SQL is a `SELECT` (adapters/ecommerce/python/registry.py:315-317) [DERIVED].

## invariants

INVARIANT: `len(SOURCES) == 6` — adapters/ecommerce/python/registry.py:37-38 [DERIVED]
  fails-if: a 7th table compiles only if added to `SOURCES`, otherwise it gets no entry in `source_hashes` (adapters/ecommerce/python/registry.py:224).
INVARIANT: every seed has `authority == "SEED_HYPOTHESIS"` — adapters/ecommerce/python/registry.py:144 [DERIVED]
  fails-if: registry rows could satisfy an EvidenceRole, breaking the law string at adapters/ecommerce/python/registry.py:346-349.
INVARIANT: every candidate prior has `authority == "WORKING_HYPOTHESIS"` and `score_basis == "SEED_PRIOR"` — adapters/ecommerce/python/registry.py:212 [DERIVED]
  fails-if: seed priors would masquerade as observations, violating adapters/ecommerce/python/registry.py:13-15.
INVARIANT: `len(VALID_FACT_STATUS) == 4` (`hypothesis`, `seed`, `observed`, `validated`) — adapters/ecommerce/python/registry.py:55 [DERIVED]
  fails-if: any other `fact_status` yields a compile error (adapters/ecommerce/python/registry.py:120-121).
INVARIANT: `len(known_ph) == 8` template placeholders — adapters/ecommerce/python/registry.py:159-160 [DERIVED]
  fails-if: a template using any other `{ph}` errors out (adapters/ecommerce/python/registry.py:162-163).
INVARIANT: `expected_roles` of `community` == `expected_roles` of `seasonality` == `[]` — adapters/ecommerce/python/registry.py:156-157 [DERIVED]
  fails-if: non-evidence goals would start proving demand, contradicting adapters/ecommerce/python/registry.py:40-42.
INVARIANT: `compile_registry` never returns snapshot and errors together — `(None, errors) if errors else (snapshot, [])` — adapters/ecommerce/python/registry.py:258 [DERIVED]
  fails-if: a partially valid snapshot could reach the runtime.
INVARIANT: `_sha` suffix length == 16 vs `build_id` suffix length == 12 — adapters/ecommerce/python/registry.py:76, 252 [DERIVED]
  fails-if: changing either length changes every recorded hash/build_id consumers compare against.

## determinism & idempotency
determinism: DETERMINISTIC — inputs are files at env-selected `SRC` (adapters/ecommerce/python/registry.py:34), glob sorted (adapters/ecommerce/python/registry.py:85), `build_id` hashed from `json.dumps(snapshot, sort_keys=True)` (adapters/ecommerce/python/registry.py:251); no clock/random/network in the build path. The `candidates` subcommand is db-state-dependent via `work_nodes` (adapters/ecommerce/python/registry.py:315-317) [DERIVED].
idempotency: SAFE — repeated `build` over identical CSVs writes byte-identical `OUT` (adapters/ecommerce/python/registry.py:301-302); governed mode never writes the cache (adapters/ecommerce/python/registry.py:257-261) [DERIVED].

## failure behaviour
- `OSError` reading `niche_scopes.yaml` → swallowed, `scopes = {}` (adapters/ecommerce/python/registry.py:219-220) [DERIVED].
- `json.JSONDecodeError` on `OUT` → returns `None`; corrupt build left on disk as a visible doctor error, never silently replaced (adapters/ecommerce/python/registry.py:265-266) [DERIVED].
- `OSError` (missing `OUT`, fresh checkout) → compile and persist first build (adapters/ecommerce/python/registry.py:267-278) [DERIVED].
- Compile errors → `build` prints `{"ok": False, "build": "INVALID", "errors": errors[:30]}`, exit code `1` (adapters/ecommerce/python/registry.py:296-299) [DERIVED].
- `import yaml as _y` sits inside the try but only `OSError` is caught — a missing PyYAML raises `ImportError` out of `compile_registry` (adapters/ecommerce/python/registry.py:217-220) [INFERRED: except clause lists OSError only].
- `import memory` in `candidates` — missing module aborts that subcommand at runtime (adapters/ecommerce/python/registry.py:313) [INFERRED: top-level import inside command branch].

## dumb-code flags
- Module docstring CLI list `registry.py build | status | query --predicate X [--friction Y]` omits the registered `candidates` and `diversity` subcommands (adapters/ecommerce/python/registry.py:19 vs 285-288) [DERIVED].
- `errors[:30]` truncation cap in the build error print (adapters/ecommerce/python/registry.py:298) [DERIVED].
- `--limit` default `8` in `query` (adapters/ecommerce/python/registry.py:291) [DERIVED].
- Snapshot-write block duplicated verbatim (`makedirs` + `json.dump(snap, f, indent=1, ensure_ascii=False)`) in `load_snapshot` and `main/build` (adapters/ecommerce/python/registry.py:276-278 vs 300-302) [DERIVED].
- Two different hash truncation lengths: `hexdigest()[:16]` in `_sha`, `hexdigest()[:12]` in `build_id` (adapters/ecommerce/python/registry.py:76, 252) [DERIVED].
- `non_dim` hardcodes 18 `niche_candidates` column names inline, duplicating the CSV schema (adapters/ecommerce/python/registry.py:179-183) [DERIVED].

## refactor notes
- Snapshot keys are consumed by sibling subcommands: `status` (`build_id`, `counts`), `query` (`index_by_predicate`, `index_by_predicate_friction`, `index_by_friction`, `seeds`), `diversity` (`seed_packs`, `seeds[].domain`, `index_by_predicate`) — renaming any key breaks them (adapters/ecommerce/python/registry.py:308-315, 343-346, 355-367) [DERIVED].
- `build_id` hashes the whole snapshot dict; adding/removing any field changes every `build_id` (adapters/ecommerce/python/registry.py:251-252) [DERIVED].
- `candidates` couples this unit to `memory.connect()` and the `work_nodes` columns `payload_json`, `run_id`, `node_type` (adapters/ecommerce/python/registry.py:313-317) [DERIVED].
- Env flag names `OPPORTUNITY_RESEARCH_REGISTRY_SRC` and `OPPORTUNITY_RESEARCH_REGISTRY` are the governed-binding contract (AUTO_DECISIONS M-014) — renames break external wiring (adapters/ecommerce/python/registry.py:32-34, 257) [DERIVED].
- Governed `load_snapshot` must stay read/write-free on the cache; the only permitted cache write is the fresh-checkout first build (adapters/ecommerce/python/registry.py:257-278) [DERIVED].

## VERIFY
```verify
grep -Fq 'OPPORTUNITY_RESEARCH_REGISTRY_SRC' adapters/ecommerce/python/registry.py
grep -Fq 'SEED_HYPOTHESIS' adapters/ecommerce/python/registry.py
grep -Fq 'registry_snapshot.json' adapters/ecommerce/python/registry.py
grep -Eq 'node_type=.REGISTRY_CANDIDATE.' adapters/ecommerce/python/registry.py
test "$(grep -c -F 'add_parser' adapters/ecommerce/python/registry.py)" -ge 5
! grep -Fq 'INSERT INTO' adapters/ecommerce/python/registry.py
```
