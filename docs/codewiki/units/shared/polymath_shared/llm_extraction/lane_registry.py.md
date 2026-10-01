# unit: shared/polymath_shared/llm_extraction/lane_registry.py
anchor: shared/polymath_shared/llm_extraction/lane_registry.py:1-376

## purpose
Builds the LANE-REGISTRY-V1 inventory: every configured account/model lane with its functional pool, credential presence, and declared capacity, read from `config/cloud_providers.json` + `config/extraction_models/limiter.yaml` — shared/polymath_shared/llm_extraction/lane_registry.py:1-18 [DERIVED]. Secret-free policy layer: resolves credential PRESENCE (bool), never the key value; no network, no provider call, so the offline acceptance gate can print it — shared/polymath_shared/llm_extraction/lane_registry.py:13-18, 349-351 [DERIVED]. Substrate for the Phase-3 effective-capacity table and query views (`by_function`, `by_account`, `by_model`, health, dark-pool detection) — shared/polymath_shared/llm_extraction/lane_registry.py:268, 298-331 [DERIVED].

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| functional_pool_of | def | (stage: str) -> str \| None | shared/polymath_shared/llm_extraction/lane_registry.py:73-76 | — |
| pmap_pool_batch_cap | def | (registry: LaneRegistry \| None = None, default: int = 15) -> int | shared/polymath_shared/llm_extraction/lane_registry.py:84-95 | — |
| build_lanes | def | () -> list[LaneInfo] | shared/polymath_shared/llm_extraction/lane_registry.py:194-260 | — |
| build_registry | def | () -> LaneRegistry | shared/polymath_shared/llm_extraction/lane_registry.py:344-345 | — |
| sanitized_inventory | def | (reg: LaneRegistry \| None = None) -> str | shared/polymath_shared/llm_extraction/lane_registry.py:348-375 | — |
| LaneCapacity | class | frozen dataclass (kind, rpm, tpm, rpd, conc_cap, family, request_char_budget) + to_dict | shared/polymath_shared/llm_extraction/lane_registry.py:137-150 | — |
| LaneInfo | class | frozen dataclass (name, function, api_key_env, account_id, model, provider_host, dedicated, role, reachability, credential_present, enabled, capacity, map_batch_cap) + to_dict | shared/polymath_shared/llm_extraction/lane_registry.py:154-175 | — |
| LaneRegistry | class | frozen dataclass (version, lanes) + by_function/by_account/by_model/shared_accounts/pool_lane_health/reachability/unreachable_pins/to_dict | shared/polymath_shared/llm_extraction/lane_registry.py:264-341 | — |

Module-level importers (symbol-to-importer mapping not in FACTS): shared/polymath_shared/conformance/attempts.py, shared/polymath_shared/conformance/discovery.py, shared/polymath_shared/control_plane_status.py, shared/polymath_shared/document_status.py, shared/polymath_shared/llm_extraction/client.py, workers/workers/doc_parent_map_stage_worker.py [DERIVED].

Exported constants: `LANE_REGISTRY_VERSION = "lane-registry-v1"` (44); `CHAT = "CHAT"` (47); `GRAPH_EXTRACTION = "GRAPH_EXTRACTION"` (48); `DOCUMENT_PROFILE = "DOCUMENT_PROFILE"` (49); `PMAP = "PMAP"` (50); `PARENT_ENRICHMENT = "parent_enrichment"` (51); `PMAP_DEFAULT_BATCH_CAP = 15` (81); `ACTIVE = "active"` (99); `CREDENTIAL_ABSENT = "configured_credential_absent"` (100); `DISABLED = "disabled"` (101) — shared/polymath_shared/llm_extraction/lane_registry.py:44-101 [DERIVED].

## contracts
**functional_pool_of(stage)**
- out: `STAGE_TO_FUNCTION.get(stage)` with exact map `extract`→`GRAPH_EXTRACTION`, `doc_profile`→`DOCUMENT_PROFILE`, `doc_parent_map`→`PMAP`, `parent_enrichment`→`PARENT_ENRICHMENT`, `chat_compiler`→`CHAT` — shared/polymath_shared/llm_extraction/lane_registry.py:64-70 [DERIVED]
- out: `None` for stages with no LLM pool (intake/projection/summary) — shared/polymath_shared/llm_extraction/lane_registry.py:74-76 [DERIVED]

**pmap_pool_batch_cap(registry=None, default=15)**
- pre: `registry=None` → `build_registry()` built fresh — shared/polymath_shared/llm_extraction/lane_registry.py:91 [DERIVED]
- out: `min(l.map_batch_cap or default)` over lanes with `function == PMAP` and `reachability == ACTIVE` — shared/polymath_shared/llm_extraction/lane_registry.py:92-95 [DERIVED]
- out: `default` when no active PMAP lane exists — shared/polymath_shared/llm_extraction/lane_registry.py:93-94 [DERIVED]

**build_lanes()**
- post: primary lane always present: `name="primary"`, `function=GRAPH_EXTRACTION`, `api_key_env=""`, `account_id="local:primary"`, `reachability=ACTIVE`, `credential_present=True`, `enabled=True` — shared/polymath_shared/llm_extraction/lane_registry.py:216-221 [DERIVED]
- post: cloud-lane reachability = `DISABLED` if `enabled is False`; else `ACTIVE` if credential present; else `CREDENTIAL_ABSENT` — shared/polymath_shared/llm_extraction/lane_registry.py:240-245 [DERIVED]
- post: result sorted by key `(l.function, l.name)` — shared/polymath_shared/llm_extraction/lane_registry.py:259 [DERIVED]

**LaneRegistry views**
- by_function / by_account / by_model group lanes by that field; by_model substitutes `"(unset)"` for empty model — shared/polymath_shared/llm_extraction/lane_registry.py:269-288 [DERIVED]
- shared_accounts returns only account_ids where `len(fns) > 1` — shared/polymath_shared/llm_extraction/lane_registry.py:291-296 [DERIVED]
- pool_lane_health keys per pool: `total`, `active`, `credential_absent`, `disabled`, `active_lanes` (sorted names) — shared/polymath_shared/llm_extraction/lane_registry.py:298-312 [DERIVED]
- unreachable_pins emits a function only when it has lanes and zero active; skips `"dedicated_unpinned"` — shared/polymath_shared/llm_extraction/lane_registry.py:320-331 [DERIVED]

**sanitized_inventory(reg=None)**
- post: renders only the `api_key_env` NAME and a `yes`/`NO` presence flag; never a key value — shared/polymath_shared/llm_extraction/lane_registry.py:353, 359-360 [DERIVED]
- post: appends the CROSS-FUNCTION SHARING and FULLY-DARK pools sections only when non-empty — shared/polymath_shared/llm_extraction/lane_registry.py:363-374 [DERIVED]

## effect surface
- files read: `config/cloud_providers.json` — shared/polymath_shared/llm_extraction/lane_registry.py:40, 123 [DERIVED]
- files read: `config/extraction_models/limiter.yaml` (top-level key `providers`) — shared/polymath_shared/llm_extraction/lane_registry.py:41, 131 [DERIVED]
- files read: repo `.env`, parsed line-by-line for `NAME=value` — shared/polymath_shared/llm_extraction/lane_registry.py:42, 112-115 [DERIVED]
- all paths resolved from `_REPO_ROOT = Path(__file__).resolve().parents[3]` — shared/polymath_shared/llm_extraction/lane_registry.py:39 [DERIVED]
- env read: `os.environ.get(env_name)` where the variable NAME comes from config `api_key_env` / `account_id_env` — no fixed env names in this module — shared/polymath_shared/llm_extraction/lane_registry.py:109, 230, 235-236 [DERIVED]
- lazy imports: `yaml` (130), `urllib.parse.urlparse` (179), `polymath_shared.settings.get_settings` (213); eager: `json`, `os`, `dataclasses`, `pathlib` (34-37) [DERIVED]
- no network/provider calls; no Postgres tables, no Qdrant, no subprocess (FACTS: `tables_read: []`, `tables_written: []`) — shared/polymath_shared/llm_extraction/lane_registry.py:17-18 [DERIVED]

## invariants
INVARIANT: pmap_pool_batch_cap == min(`map_batch_cap` or 15) over ACTIVE PMAP lanes — shared/polymath_shared/llm_extraction/lane_registry.py:92-95 [DERIVED]
  fails-if: a planned batch exceeds some lane's reliable cap; pool-drain invariant broken.
INVARIANT: PMAP_DEFAULT_BATCH_CAP == 15 — shared/polymath_shared/llm_extraction/lane_registry.py:81 [DERIVED]
  fails-if: silent default change shifts pMAP batch sizing with no config edit.
INVARIANT: cloud-lane `account_id` == `api_key_env`, or `anon:{name}` when keyless; primary == `local:primary` — shared/polymath_shared/llm_extraction/lane_registry.py:249, 217 [DERIVED]
  fails-if: one-key-one-account audit (`by_account`, `shared_accounts`) keys on the wrong identity.
INVARIANT: reachability ∈ {"active", "configured_credential_absent", "disabled"} (exactly 3 states; runtime breaker excluded) — shared/polymath_shared/llm_extraction/lane_registry.py:97-101 [DERIVED]
  fails-if: offline gate output becomes nondeterministic or unparseable.
INVARIANT: a lane with `account_id_env` is ACTIVE only when BOTH token and account id resolve — shared/polymath_shared/llm_extraction/lane_registry.py:232-236 [DERIVED]
  fails-if: Cloudflare lane counted active with a missing account id; dispatch would fail.
INVARIANT: no secret value ever stored/rendered — `api_key_env` is a name, `credential_present` is a bool — shared/polymath_shared/llm_extraction/lane_registry.py:13-14, 105-106 [DERIVED]
  fails-if: key strings leak into the gate printout or `to_dict()`.
INVARIANT: build_lanes output order == sort key `(function, name)` — shared/polymath_shared/llm_extraction/lane_registry.py:259 [DERIVED]
  fails-if: inventory-table diffs flap between runs.
INVARIANT: unreachable_pins non-empty only for pools with ≥1 lane and 0 active — shared/polymath_shared/llm_extraction/lane_registry.py:329-330 [DERIVED]
  fails-if: dark-pool detector misses (or false-alarms on) PinnedProviderUnavailable risk.
INVARIANT: LaneCapacity, LaneInfo, LaneRegistry are `@dataclass(frozen=True)` — shared/polymath_shared/llm_extraction/lane_registry.py:136, 153, 263 [DERIVED]
  fails-if: mutable lane rows let callers corrupt the shared registry.

## determinism & idempotency
determinism: NONDETERMINISTIC (env + config-file contents: `os.environ.get` at shared/polymath_shared/llm_extraction/lane_registry.py:109, `.env` presence at :112, `cloud_providers.json` at :123, `limiter.yaml` at :131 all drive `reachability`/`credential_present`; output ORDER itself is deterministic via the sort at :259)
idempotency: SAFE (read-only; no writes, no network; frozen dataclasses at shared/polymath_shared/llm_extraction/lane_registry.py:136, 153, 263)

## failure behaviour
- `_load_limiter`: `except Exception` → `return {}` — shared/polymath_shared/llm_extraction/lane_registry.py:132 [DERIVED]; caller sees lanes with no capacity seeds (caps render `-` in inventory).
- `build_lanes` primary block: `except Exception` → `pass` — shared/polymath_shared/llm_extraction/lane_registry.py:222 [DERIVED]; the `primary` lane silently disappears from the roster when settings fail to load.
- `_load_providers`: `FileNotFoundError, json.JSONDecodeError` → `{}` — shared/polymath_shared/llm_extraction/lane_registry.py:124-125 [DERIVED]; registry reduces to the primary lane only.
- `_credential_present`: `OSError` reading `.env` swallowed → returns False — shared/polymath_shared/llm_extraction/lane_registry.py:116-117 [DERIVED].
- This module raises nothing itself; a fully-dark pinned pool is reported via `unreachable_pins` and would raise `PinnedProviderUnavailable` in consumers — shared/polymath_shared/llm_extraction/lane_registry.py:321-323 [INFERRED: docstring names the consumer-side error, not a raise here].

## dumb-code flags
- `PMAP_DEFAULT_BATCH_CAP = 15` justified only by a comment citing `11.178 / MAP_RELIABILITY_CAP` — a doc pointer, not an imported shared constant — shared/polymath_shared/llm_extraction/lane_registry.py:79-81 [DERIVED]
- sentinel function `"dedicated_unpinned"` is an inline literal assigned at :239 and special-cased again at :326; every other pool has a module constant — shared/polymath_shared/llm_extraction/lane_registry.py:239, 326 [DERIVED]
- `LaneInfo.role` comment lists `primary | fallback | ring | pinned` but `_role_for` can also return `"dedicated"` — shared/polymath_shared/llm_extraction/lane_registry.py:164, 189-190 [DERIVED]
- `_role_for` precedence: `"fallback" in low` is checked before `in_pin`, so a pinned lane whose name contains `fallback` reports role `fallback`, hiding its pin — shared/polymath_shared/llm_extraction/lane_registry.py:184-188 [DERIVED]
- `PARENT_ENRICHMENT = "parent_enrichment"` is lowercase while sibling pool constants are uppercase strings — shared/polymath_shared/llm_extraction/lane_registry.py:47-51 [DERIVED]
- `_PIN_FUNCTION` and `STAGE_TO_FUNCTION` duplicate the same four stage keys with parallel values — shared/polymath_shared/llm_extraction/lane_registry.py:55-59, 64-70 [DERIVED]

## refactor notes
- Six importers depend on this module (FACTS.importers): renaming/re-typing `LaneInfo`, `LaneRegistry`, `build_registry`, or the reachability string literals breaks conformance/attempts.py, conformance/discovery.py, control_plane_status.py, document_status.py, llm_extraction/client.py, workers/doc_parent_map_stage_worker.py — shared/polymath_shared/llm_extraction/lane_registry.py:264-345 [INFERRED: importers listed in FACTS; per-symbol usage unknown].
- `_credential_present` "Mirrors pool._resolve_key" — its resolution order (process env, then repo `.env`) must change in lockstep with `pool.py` or active/parked classification diverges from actual dispatch — shared/polymath_shared/llm_extraction/lane_registry.py:105-106 [DERIVED]
- `sanitized_inventory` column layout is the Phase-2/Phase-3 offline-gate printout — reformatting the fixed-width columns changes gate output — shared/polymath_shared/llm_extraction/lane_registry.py:349-362 [DERIVED]
- `STAGE_TO_FUNCTION` keys must equal live DAG stage names (`extract`, `doc_profile`, `doc_parent_map`, `parent_enrichment`, `chat_compiler`); the pMAP stage worker is an importer — shared/polymath_shared/llm_extraction/lane_registry.py:61-70 [DERIVED]
- `LANE_REGISTRY_VERSION` literal `"lane-registry-v1"` travels in `to_dict()["version"]`; bumping it is a wire-format change for consumers — shared/polymath_shared/llm_extraction/lane_registry.py:44, 335 [DERIVED]

## VERIFY
```verify
grep -Fq 'LANE_REGISTRY_VERSION = "lane-registry-v1"' shared/polymath_shared/llm_extraction/lane_registry.py
grep -Fq 'PMAP_DEFAULT_BATCH_CAP = 15' shared/polymath_shared/llm_extraction/lane_registry.py
grep -Fq 'CREDENTIAL_ABSENT = "configured_credential_absent"' shared/polymath_shared/llm_extraction/lane_registry.py
grep -Fq 'return min((l.map_batch_cap or default) for l in active)' shared/polymath_shared/llm_extraction/lane_registry.py
grep -Fq 'lanes.sort(key=lambda l: (l.function, l.name))' shared/polymath_shared/llm_extraction/lane_registry.py
grep -Fq 'account_id=api_key_env or f"anon:{name}"' shared/polymath_shared/llm_extraction/lane_registry.py
test "$(grep -c -F 'to_dict' shared/polymath_shared/llm_extraction/lane_registry.py)" -ge 3
! grep -Fq 'import requests' shared/polymath_shared/llm_extraction/lane_registry.py
```
