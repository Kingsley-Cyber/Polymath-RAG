# unit: shared/polymath_shared/conformance/discovery.py
anchor: shared/polymath_shared/conformance/discovery.py:1-289

## purpose
Topology discovery for the conformance audit: reads what the system actually is right now, writes nothing. Four sources ranked by authority: lane registry (`config/cloud_providers.json` + limiter seeds), Postgres, running processes / supervisor state, repo file graph — shared/polymath_shared/conformance/discovery.py:1-11 [DERIVED]. Aggregated into one `snapshot()` dict for conformance tooling — shared/polymath_shared/conformance/discovery.py:272-288 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `Lane` | dataclass | 12 fields: name, function, provider, model, account_env, enabled, dedicated, reachability, role, stage_pin, fallback_tier, capacity | shared/polymath_shared/conformance/discovery.py:28-40 | — |
| `configured_lanes` | def | `() -> list[Lane]` | shared/polymath_shared/conformance/discovery.py:56-80 | — |
| `configured_functions` | def | `(lanes: list[Lane]) -> dict[str, list[str]]` | shared/polymath_shared/conformance/discovery.py:83-87 | — |
| `running_processes` | def | `() -> list[dict]` | shared/polymath_shared/conformance/discovery.py:92-110 | — |
| `supervisor_state` | def | `() -> dict` | shared/polymath_shared/conformance/discovery.py:113-123 | — |
| `live_workers` | def | `(conn) -> dict` | shared/polymath_shared/conformance/discovery.py:126-136 | — |
| `api_routes` | def | `() -> list[dict]` | shared/polymath_shared/conformance/discovery.py:141-157 | — |
| `worker_modules` | def | `() -> list[dict]` | shared/polymath_shared/conformance/discovery.py:160-164 | — |
| `durable_tables` | def | `(conn) -> list[dict]` | shared/polymath_shared/conformance/discovery.py:167-197 | — |
| `qdrant_collections` | def | `() -> list[dict]` | shared/polymath_shared/conformance/discovery.py:200-216 | — |
| `neo4j_summary` | def | `() -> dict` | shared/polymath_shared/conformance/discovery.py:219-232 | — |
| `legacy_scan` | def | `(probes: tuple[str, ...] = LEGACY_PROBES) -> list[dict]` | shared/polymath_shared/conformance/discovery.py:244-269 | — |
| `snapshot` | def | `(conn=None) -> dict` | shared/polymath_shared/conformance/discovery.py:272-288 | — |
| `_provider_of` (private) | def | `(model: str, host: str) -> str` | shared/polymath_shared/conformance/discovery.py:43-53 | `configured_lanes` — shared/polymath_shared/conformance/discovery.py:70 [DERIVED] |

## contracts
`configured_lanes` — shared/polymath_shared/conformance/discovery.py:56-80
- in: lane registry via `LR.build_registry()`; `config/cloud_providers.json`; `stage_pins` mapping — shared/polymath_shared/conformance/discovery.py:57-63
- out: one `Lane` per registry lane; `account_env` = `l.api_key_env` (ENV NAME ONLY) — shared/polymath_shared/conformance/discovery.py:71,33
- post: `fallback_tier` = `"primary"` when pin idx == 0 else `f"fallback{idx}"`; unpinned lanes get `stage_pin=None, fallback_tier=None` — shared/polymath_shared/conformance/discovery.py:66,75

`_provider_of` — shared/polymath_shared/conformance/discovery.py:43-53
- in: host token match against `("groq","openrouter","googleapis","gemini","nvidia","siliconflow","aliyuncs","openai","anthropic","localhost","127.0.0.1")`; remap `googleapis->google`, `aliyuncs->alibaba`, `localhost->local`, `127.0.0.1->local` — shared/polymath_shared/conformance/discovery.py:47-51
- out: else second-level domain `h.split(".")[-2]`; no host -> `model.split("/", 1)[0]` or `"unknown"` — shared/polymath_shared/conformance/discovery.py:52-53

`running_processes` — shared/polymath_shared/conformance/discovery.py:92-110
- in: `ps -Ao pid,lstart,command`, timeout=15 — shared/polymath_shared/conformance/discovery.py:95-96
- pre: line must contain `str(ROOT)` and must not contain `"grep"` — shared/polymath_shared/conformance/discovery.py:101
- out: `{pid, command[:200], module}`; module via regex `r"(-m |/)([A-Za-z0-9_./]+)$"` — shared/polymath_shared/conformance/discovery.py:107-109

`supervisor_state` — shared/polymath_shared/conformance/discovery.py:113-123
- in: `$POLYMATH_FLEET_DIR/supervisor_state.json` — shared/polymath_shared/conformance/discovery.py:114
- out: `{available, path, slots, alive, parked, quarantined}` — shared/polymath_shared/conformance/discovery.py:120-123

`live_workers` — shared/polymath_shared/conformance/discovery.py:126-136
- in: requires live `conn`
- out: `{by_type, total, bundles, bundle_uniform}`; `bundles` = distinct `LEFT(execution_bundle_hash,16)` with heartbeat in last `'60 seconds'` — shared/polymath_shared/conformance/discovery.py:128-133
- post: `bundle_uniform` is `len(bundles) <= 1` — shared/polymath_shared/conformance/discovery.py:136

`api_routes` — shared/polymath_shared/conformance/discovery.py:141-157
- in: `GET {POLYMATH_BASE_URL}/openapi.json`, timeout=8 — shared/polymath_shared/conformance/discovery.py:144-146
- out: `{path, methods, source}`; `source` = `"live"` or `"static:{filename}"` from regex scan of `@router.(get|post|put|delete|patch)` in `orchestrator/orchestrator/api/*.py` — shared/polymath_shared/conformance/discovery.py:148-156

`durable_tables` — shared/polymath_shared/conformance/discovery.py:167-197
- in: requires live `conn`
- pre: only `information_schema.tables` rows with `table_type='BASE TABLE'` (VIEWS excluded) — shared/polymath_shared/conformance/discovery.py:176-178
- out: `{table, rows, last_activity}`; timestamp column prefers `'updated_at'` over `'created_at'` via `CASE column_name WHEN 'updated_at' THEN 0 ELSE 1 END` — shared/polymath_shared/conformance/discovery.py:185-188,196

`qdrant_collections` — shared/polymath_shared/conformance/discovery.py:200-216
- in: `GET {POLYMATH_QDRANT_URL}/collections` then per-collection detail, both timeout=8 — shared/polymath_shared/conformance/discovery.py:202-209
- out: `{collection, points}`; points from `["result"].get("points_count")` — shared/polymath_shared/conformance/discovery.py:210-211

`neo4j_summary` — shared/polymath_shared/conformance/discovery.py:219-232
- out: `{entities, relationships, labels}`; counts `MATCH (e:Entity)` and `MATCH ()-[r:REL]->()` — shared/polymath_shared/conformance/discovery.py:224-228

`legacy_scan` — shared/polymath_shared/conformance/discovery.py:244-269
- in: default probes = `LEGACY_PROBES` tuple — shared/polymath_shared/conformance/discovery.py:239-241
- pre: `git grep -n -- <probe>` over tracked files, cwd=ROOT, timeout=60 — shared/polymath_shared/conformance/discovery.py:249-251
- out: `{probe, total_hits, files, code_files, test_only, docs_only}`; code files = `.py/.ts/.tsx/.sql` not under `tests/` — shared/polymath_shared/conformance/discovery.py:259-268

`snapshot` — shared/polymath_shared/conformance/discovery.py:272-288
- out: keys `lanes, functions, routes, workers_on_disk, processes, supervisor, qdrant, neo4j, legacy_scan`; `live_workers` and `tables` added only when `conn is not None` — shared/polymath_shared/conformance/discovery.py:274-287
- post: lanes serialized via `asdict` — shared/polymath_shared/conformance/discovery.py:275

## effect surface
| effect | detail | anchor |
|---|---|---|
| Postgres read | `worker_registrations` (heartbeat window, bundle hash) | shared/polymath_shared/conformance/discovery.py:127-133 |
| Postgres read | `information_schema.tables`, `information_schema.columns`, per-table `COUNT(*)`/`MAX(ts)` | shared/polymath_shared/conformance/discovery.py:176-193 |
| Postgres write | none (FACTS `tables_written: []`) | shared/polymath_shared/conformance/discovery.py:126-197 [DERIVED] |
| Qdrant | read-only listing + point counts via HTTP | shared/polymath_shared/conformance/discovery.py:204-211 |
| Neo4j | read-only counts via `polymath_shared.stores.neo4j_driver` | shared/polymath_shared/conformance/discovery.py:221-228 |
| Network | 3× `urllib.request.urlopen` (openapi.json, collections list, collection detail) | shared/polymath_shared/conformance/discovery.py:146,204,209 |
| Subprocess | `ps -Ao pid,lstart,command`; `git grep -n --` | shared/polymath_shared/conformance/discovery.py:95,249 |
| Files read | `config/cloud_providers.json`; `supervisor_state.json`; `orchestrator/orchestrator/api/*.py`; `workers/workers/*worker*.py` | shared/polymath_shared/conformance/discovery.py:59,114,153,162 |
| Env | `POLYMATH_BASE_URL` = `'http://127.0.0.1:7200'`; `POLYMATH_QDRANT_URL` = `'http://127.0.0.1:6334'`; `POLYMATH_FLEET_DIR` = `'/tmp/polymath_fleet'` | shared/polymath_shared/conformance/discovery.py:144,202,114 |

## invariants
INVARIANT: `account_env` holds env var name only, never a secret value — shared/polymath_shared/conformance/discovery.py:33 [DERIVED]
  fails-if: API key material leaks into the snapshot dict.
INVARIANT: `durable_tables` output ⊆ `table_type='BASE TABLE'` rows — shared/polymath_shared/conformance/discovery.py:177-178 [DERIVED]
  fails-if: views (e.g. zero-storage views like `entity_knowledge_refusals`) get flagged RETIRE_CANDIDATE — shared/polymath_shared/conformance/discovery.py:169-175 [DERIVED]
INVARIANT: `bundle_uniform` == (`len(bundles) <= 1`) — shared/polymath_shared/conformance/discovery.py:136 [DERIVED]
  fails-if: mixed `execution_bundle_hash` fleet reports as uniform.
INVARIANT: `running_processes` rows ⊆ lines containing `str(ROOT)` — shared/polymath_shared/conformance/discovery.py:101 [DERIVED]
  fails-if: unrelated processes counted as polymath workers.
INVARIANT: live worker window == `heartbeat_at > now() - interval '60 seconds'` — shared/polymath_shared/conformance/discovery.py:129 [DERIVED]
  fails-if: stale registrations counted as live.
INVARIANT: `api_routes[].source` ∈ {"live", `static:{filename}`} — shared/polymath_shared/conformance/discovery.py:149,156 [DERIVED]
  fails-if: consumers can't tell scanned routes from serving ones.
INVARIANT: snapshot keys `live_workers`/`tables` present ⟺ `conn is not None` — shared/polymath_shared/conformance/discovery.py:285-287 [DERIVED]
  fails-if: consumers assuming the keys always exist crash on no-conn snapshots.

## determinism & idempotency
determinism: NONDETERMINISTIC (network shared/polymath_shared/conformance/discovery.py:146,204,209; subprocess shared/polymath_shared/conformance/discovery.py:95,249; db shared/polymath_shared/conformance/discovery.py:127-133,176-193; env shared/polymath_shared/conformance/discovery.py:114,144,202; wall-clock heartbeat cutoff shared/polymath_shared/conformance/discovery.py:129)
idempotency: SAFE (read-only module: "Everything here READS the current system" shared/polymath_shared/conformance/discovery.py:1; no table writes in SOURCE) [DERIVED]

## failure behaviour
- `running_processes`: any `ps` exception swallowed -> `[]`; caller cannot distinguish "no processes" from "ps broken" — shared/polymath_shared/conformance/discovery.py:97-98 [DERIVED]
- `supervisor_state`: read/parse failure swallowed -> `{"available": False, "error": ...}` — shared/polymath_shared/conformance/discovery.py:117-118 [DERIVED]
- `api_routes`: live fetch failure handled -> static regex fallback, routes tagged `static:{f.name}` — shared/polymath_shared/conformance/discovery.py:151-157 [DERIVED]
- `durable_tables`: `COUNT(*)` failure -> `rows: None`; `MAX(ts)` failure -> `last_activity: None` — shared/polymath_shared/conformance/discovery.py:183-184,194-195 [DERIVED]
- `qdrant_collections`: list failure swallowed -> `[{"error": ...}]`; per-collection failure -> `points: None` — shared/polymath_shared/conformance/discovery.py:212-213,215-216 [DERIVED]
- `neo4j_summary`: any exception swallowed -> `{"error": ...}` — shared/polymath_shared/conformance/discovery.py:231-232 [DERIVED]
- `legacy_scan`: `git grep` exception -> `hits = []`, probe reported with zero hits — shared/polymath_shared/conformance/discovery.py:253-254 [DERIVED]
- No exceptions raised to callers anywhere in the module; all failures degrade to error dicts / None / empty lists.

## dumb-code flags
- Docstring claims provider identity comes "not from a hardcoded list of vendor names" while the body iterates a hardcoded 11-token vendor tuple — shared/polymath_shared/conformance/discovery.py:44 vs 47-48 [DERIVED]
- `import urllib.request` duplicated locally in two functions — shared/polymath_shared/conformance/discovery.py:143,201 [DERIVED]
- Magic timeouts: `15`, `8` (×3), `60` — shared/polymath_shared/conformance/discovery.py:96,146,204,251 [DERIVED]
- Heartbeat window literal `'60 seconds'` duplicated across two queries — shared/polymath_shared/conformance/discovery.py:129,132-133 [DERIVED]
- Module-extraction regex is `$`-anchored but `command` is truncated to first 200 chars, so long commands yield `module: ""` — shared/polymath_shared/conformance/discovery.py:107-108 [INFERRED: `$` anchor checks the tail of a head-truncated string]
- Layout-coupled literals: `parents[3]`, `config/cloud_providers.json`, `orchestrator/orchestrator/api` glob, `workers/workers` glob — shared/polymath_shared/conformance/discovery.py:22,59,153,162 [DERIVED]

## refactor notes
- `snapshot()` key set (`lanes, functions, routes, workers_on_disk, processes, supervisor, qdrant, neo4j, legacy_scan, live_workers, tables`) is the external contract; renaming any key breaks snapshot consumers — shared/polymath_shared/conformance/discovery.py:274-287
- `Lane` fields serialize via `asdict`; renaming a field renames it in every snapshot — shared/polymath_shared/conformance/discovery.py:275,28-40
- BASE TABLE-only filter is locked by PRODUCTION-CONFORMANCE-AUDIT-V1 follow-up (2026-09-12); reintroducing views resurrects the RETIRE_CANDIDATE misclassification — shared/polymath_shared/conformance/discovery.py:169-178
- Provider strings `"google"`, `"alibaba"`, `"local"` from `_provider_of` land in `Lane.provider`; downstream grouping depends on them — shared/polymath_shared/conformance/discovery.py:50-51,70
- `LEGACY_PROBES` is the default probe set; editing it changes `snapshot()["legacy_scan"]` for all default callers — shared/polymath_shared/conformance/discovery.py:239-241,244
- Env names `POLYMATH_BASE_URL`, `POLYMATH_QDRANT_URL`, `POLYMATH_FLEET_DIR` are deployment contract; renaming them orphans existing installs — shared/polymath_shared/conformance/discovery.py:114,144,202

## VERIFY
```verify
grep -Fq 'BASE TABLE' shared/polymath_shared/conformance/discovery.py
grep -Fq 'http://127.0.0.1:7200' shared/polymath_shared/conformance/discovery.py
grep -Eq 'heartbeat_at > now\(\) - interval' shared/polymath_shared/conformance/discovery.py
test "$(grep -c -F 'urllib.request.urlopen' shared/polymath_shared/conformance/discovery.py)" -ge 3
grep -Fq 'PRODUCTION-CONFORMANCE-AUDIT-V1' shared/polymath_shared/conformance/discovery.py
! grep -Fq 'INSERT INTO' shared/polymath_shared/conformance/discovery.py
```
