# unit: shared/polymath_shared/llm_extraction/pool.py
anchor: shared/polymath_shared/llm_extraction/pool.py:1-471

## purpose
EXTRACTION-POOL-V1 — the multi-provider cloud LLM endpoint pool. It decides WHICH cloud endpoint serves a cloud dispatch, never whether a document may go cloud (that is policy.py's alone) — pool.py:10-12. Endpoint choice is deterministic per document: `blake2b(doc_id)` over the name-sorted enabled roster, so crash/replay re-selects the same endpoint and N providers shard the backlog with zero coordination state — pool.py:13-16. A one-endpoint config reproduces the old single-provider behavior exactly — pool.py:17-18. Consumers: extraction/profile/summary/pMAP workers and orchestrator API modules (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `CloudEndpoint` | class (`@dataclass(frozen=True)`) | fields -> CloudEndpoint | pool.py:47-114 | — |
| `cloud_endpoints` | func | `() -> list[CloudEndpoint]` | pool.py:217-262 | — |
| `select_endpoint_for_stage` | func | `(stage: str, doc_id: str, ring_offset: int = 0) -> CloudEndpoint` | pool.py:331-354 | — |
| `select_cloud_endpoint` | func | `(doc_id: str, ring_offset: int = 0) -> CloudEndpoint` | pool.py:371-381 | — |
| `select_cloud_endpoint_abs` | func | `(index: int) -> CloudEndpoint` | pool.py:456-462 | — |
| `home_ring_index` | func | `(doc_id: str) -> int` | pool.py:465-471 | — |
| `cloud_ring` | func | `() -> list[CloudEndpoint]` | pool.py:449-453 | — |
| `pool_fingerprint` | func | `() -> list[dict]` | pool.py:384-399 | — |
| `interleave_by_family` | func | `(endpoints: list[CloudEndpoint]) -> list[CloudEndpoint]` | pool.py:409-446 | — |
| `stage_pin` | func | `(stage: str) -> list[str] \| None` | pool.py:277-290 | — |
| `stage_owners` | func | `(stage: str) -> list[list[str]] \| None` | pool.py:293-304 | — |
| `owned_lane_order` | func | `(pin, owners, offset, run_key, fallback_mark="fallback") -> list[str]` | pool.py:314-328 | — |
| `lane_max_tokens` | func | `(ep: CloudEndpoint, stage_max: int) -> int` | pool.py:271-274 | — |
| `PinnedProviderUnavailable` | class | `RuntimeError` subclass | pool.py:265-268 | — |

Module-level importers (FACTS.importers): `orchestrator/orchestrator/api/_small-modules`, `orchestrator/orchestrator/api/deep_research.py`, `orchestrator/orchestrator/api/ui.py`, `workers/workers/doc_parent_map_stage_worker.py`, `workers/workers/doc_profile_worker.py`, `workers/workers/extract_worker.py`, `workers/workers/llm_provider.py`, `workers/workers/summary_worker_impl.py`.

## contracts

**`CloudEndpoint`** — pool.py:47-114
- defaults: `api_key: str | None = None` (`repr=False`), `reasoning_effort: str | None = None`, `json_mode: bool = True`, `structured: str = "json"`, `dedicated: bool = False`, `request_char_budget: int = 60000`, `enable_thinking: bool | None = None`, `think_suffix: str | None = None`, `max_output_tokens: int | None = None` — pool.py:54-97.
- post: `limiter_key == "default"` iff `name == "primary"`, else `name` — pool.py:100-103.
- post: `cloud_opts["json_mode"]` is `True` iff `structured in ("schema", "json")` — pool.py:110-113.
- pre: `api_key` never appears in repr, fingerprints, or logs — pool.py:52-53.

**`cloud_endpoints()`** — pool.py:217-262
- in: settings sidecars (`llm_cloud_url`, `llm_cloud_model`, `llm_cloud_primary`, `llm_cloud_extra_endpoints`), `config/cloud_providers.json`, `.env`.
- pre: extras JSON (when non-empty) must be a list of `{name, url, model}` — pool.py:237-245.
- post: roster sorted by `ep.name` — pool.py:256; names unique — pool.py:257-259; composition logged once — pool.py:260-261.
- post: roster ≥ 1 endpoint unless primary parked (`llm_cloud_primary` falsy) while configured providers exist — pool.py:226-228.
- raises: `ValueError` on invalid providers JSON — pool.py:162-163; blank/reserved provider name — pool.py:167-168; missing url/model — pool.py:196-197; invalid `structured` — pool.py:145-147; malformed/non-list extras — pool.py:234-238; extras missing name+url+model — pool.py:244-245; extras name `"primary"` — pool.py:246-248; duplicate names — pool.py:258-259.

**`select_endpoint_for_stage(stage, doc_id, ring_offset=0)`** — pool.py:331-354
- in: `stage_pin(stage)`; `None` → delegates to `select_cloud_endpoint(doc_id)` — pool.py:340-342.
- post: returned endpoint's `name` is always inside the pin group when pinned — pool.py:343.
- post: partially-dark pin group runs on active members, dark names logged once — pool.py:349-353.
- raises: `PinnedProviderUnavailable` when no pin member is active — pool.py:344-348.

**`_ring_pick` / `select_cloud_endpoint(doc_id, ring_offset=0)`** — pool.py:357-368, 371-381
- post: single-member roster returns `roster[0]` — pool.py:364-365.
- post: `idx = (int.from_bytes(blake2b(doc_id, digest_size=8), "big") + ring_offset) % len(roster)` — pool.py:366-367.
- post: roster = non-dedicated endpoints; if all are dedicated, fails open to the full roster and logs once — pool.py:375-380.

**`cloud_ring()` / `select_cloud_endpoint_abs(index)` / `home_ring_index(doc_id)`** — pool.py:449-453, 456-462, 465-471
- post: ring = non-dedicated roster (or all) in `interleave_by_family` order — pool.py:451-453.
- post: absolute pick = `ring[index % len(ring)]` — pool.py:461-462.
- post: home index uses the same `blake2b(doc_id, digest_size=8)` digest as `_ring_pick` — pool.py:468-470 vs 366.

**`interleave_by_family(endpoints)`** — pool.py:409-446
- post: ≤ 1 family → plain name-sorted list — pool.py:430-431.
- post: nginx-style smooth weighted round-robin; family weight = its lane count; tie-break `max(live, key=lambda f: (current[f], -sorted(groups).index(f)))` — pool.py:432, 442.
- post: order is a pure function of config (RANK-STABILITY) — pool.py:425-426.

**`pool_fingerprint()`** — pool.py:384-399
- out: list of dicts with keys `name, url, model, reasoning_effort, structured, dedicated` — pool.py:396-398.
- post: covers the non-dedicated roster, or the whole roster when every lane is dedicated — pool.py:395.

**`stage_pin` / `stage_owners` / `owned_lane_order`** — pool.py:277-290, 293-304, 314-328
- post: string pin → single-element list; list pin → stripped non-empty names — pool.py:288-290.
- post: `owned_lane_order` returns `_rotated(own, run_key) + _rotated(tier, run_key) + last`; `own = owners[offset-1]` only when `1 <= offset <= len(owners)`, else `[]`; `last` = pin lanes whose name contains `"fallback"`, in pin order — pool.py:323-328.
- post: another slot's lanes are never included — pool.py:320-322, 324-325.

**`lane_max_tokens(ep, stage_max)`** — pool.py:271-274
- out: `min(int(stage_max), int(cap))` when `max_output_tokens` set, else `int(stage_max)` — pool.py:273-274.

**`_resolve_key(env_name)`** — pool.py:117-133
- out: process env first, then repo `.env` line `f"{env_name}="`, else `None`; `OSError` on `.env` swallowed — pool.py:121-132.

## effect surface
- Files read: `config/cloud_providers.json` (path built at pool.py:42-43; parsed at pool.py:158, 282, 298); repo `.env` (pool.py:44; parsed at pool.py:125).
- Env read: per-provider `api_key_env` — pool.py:171-177 via `_resolve_key` pool.py:121-133; per-provider `account_id_env` substituted into `url_template`'s `{account_id}` — pool.py:184-194.
- Settings flags: `llm_cloud_url` / `llm_cloud_model` (primary, pool.py:227); `llm_cloud_primary` = default `True` (pool.py:226); `llm_cloud_extra_endpoints` = `POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`, default empty (pool.py:220-221, 229).
- Postgres/Qdrant: none — FACTS `tables_read`/`tables_written` are empty.
- Network: none in this module; it only returns url/model, dispatch happens in callers — pool.py:10-12.
- Logging: `log.info` via `_log_once` (pool.py:211-214) with tokens `("parked", name)` pool.py:174, `("parked-acct", name)` pool.py:190, `("roster", names)` pool.py:260, `("pin-partial", stage, dark)` pool.py:351, `("all-dedicated",)` pool.py:378.

## invariants
INVARIANT: `limker_key` `limiter_key == "default"` ⇔ `name == "primary"` — pool.py:100-103 [DERIVED]
  fails-if: renaming the primary loses the historical AIMD limiter lane and its seeds.
INVARIANT: pick index = `(int.from_bytes(blake2b(doc_id, digest_size=8), "big") + ring_offset) % len(roster)` — pool.py:366-367 [DERIVED]
  fails-if: any change to hash/roster order re-homes every doc; replays pick different endpoints, receipts lose attribution.
INVARIANT: `home_ring_index` digest == `_ring_pick` digest (same `blake2b`, `digest_size=8`) — pool.py:468-470, 366 [DERIVED]
  fails-if: rank-less fallback base lands on a different lane than hash failover.
INVARIANT: roster sorted by name and duplicate-free — pool.py:256-259 [DERIVED]
  fails-if: unsorted/duplicated roster breaks ring determinism across worker processes.
INVARIANT: `len(cloud_endpoints()) >= 1` unless primary parked (`llm_cloud_primary` falsy) with ≥ 1 configured provider — pool.py:226-228 [DERIVED]
  fails-if: empty roster makes `ring[index % len(ring)]` divide by zero — pool.py:461-462 [INFERRED: `cloud_ring()` on an empty list returns `[]` via pool.py:430-431].
INVARIANT: a pinned stage never dispatches outside its pin group — pool.py:343-348 [DERIVED]
  fails-if: a dedicated lane's rate budget silently serves unpinned stages.
INVARIANT: `pool_fingerprint()` output contains no `api_key` — pool.py:52-53, 396-398 [DERIVED]
  fails-if: auth material leaks into `contract_identity()` and logs.
INVARIANT: `owned_lane_order` never includes another slot's lanes — pool.py:320-325 [DERIVED]
  fails-if: two calling processes share one (account, model) pair's limiter budget.
INVARIANT: `request_char_budget` default `60000` in both the dataclass and the config parser — pool.py:76, 204 [DERIVED]
  fails-if: divergent defaults silently change batch packing limits per lane source.

## determinism & idempotency
determinism: DETERMINISTIC given fixed (config/cloud_providers.json, .env, process env, settings) — `blake2b` doc hash pool.py:366, 469; `sha256(run_key)` rotation pool.py:310; ring is a pure function of config pool.py:425-426. Roster composition itself is env-gated (key presence) — pool.py:121-133, 171-177. [DERIVED]
idempotency: SAFE — no writes; file reads plus one process-global log-dedup set `_ROSTER_LOGGED: set[tuple]` — pool.py:136, 211-214. [DERIVED]

## failure behaviour
- Swallowed → caller sees `None`/skip: `_resolve_key` `OSError` on `.env` — pool.py:131-132; `_configured_providers` `FileNotFoundError` → `[]` — pool.py:159-160; `stage_pin`/`stage_owners` on `(FileNotFoundError, json.JSONDecodeError)` → `None` (stage silently unpins) — pool.py:282-284, 298-300.
- Parked, logged once, skipped: provider key unset — pool.py:173-177; account id unset for `url_template` — pool.py:189-193.
- Fail-open + one log line: every endpoint dedicated → general dispatch uses the full roster — pool.py:377-380.
- Raised loud: `ValueError` at pool.py:145-147, 162-163, 167-168, 196-197, 234-238, 244-245, 246-248, 258-259; `PinnedProviderUnavailable(RuntimeError)` at pool.py:345-348.

## dumb-code flags
- Duplicated literal `60000` for `request_char_budget` — pool.py:76 and pool.py:204.
- `"primary"` reserved-name literal repeated at pool.py:103, 167, 247.
- Contradictory comments on `structured: "schema"`: field comment says it is "currently DOWNGRADED to `json` at dispatch" — pool.py:63-66; `cloud_opts` comment says "`schema` now DISPATCHES level-1" (STRICT-SCHEMA-V1, verified Groq) — pool.py:107-109.
- Providers file re-read and re-parsed from disk on every call in three separate functions, no cache — pool.py:158, 282, 298.
- Env-extras construction (`POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS`) sets only name/url/model/api_key_env/reasoning_effort/json_mode/structured; `dedicated`, `request_char_budget`, `enable_thinking`, `think_suffix`, `max_output_tokens` are unreachable there and always default — pool.py:250-255.
- `fallback_mark` is a substring match: any lane name containing `"fallback"` sorts last — pool.py:314, 326-327.
- `_log_once` is called at pool.py:174 but defined at pool.py:211 (order-only; works after module init).
- Tie-break recomputes `sorted(groups).index(f)` inside the `max` key per element — pool.py:442.

## refactor notes
- Eight importer modules (FACTS.importers, incl. `workers/workers/llm_provider.py`, `extract_worker.py`, `doc_profile_worker.py`, `doc_parent_map_stage_worker.py`, `summary_worker_impl.py`, orchestrator `deep_research.py`/`ui.py`/`_small-modules`) — any change to `CloudEndpoint` fields or the `select_*`/`cloud_endpoints` signatures touches all of them.
- `pool_fingerprint()` feeds `contract_identity()` and the `llm_provider._key` extraction call cache; a roster/model change invalidates that cache — pool.py:385-393.
- Ring order must remain a pure function of config (RANK-STABILITY); any nondeterminism desynchronizes every worker's slice assignment — pool.py:425-426.
- Config keys `stage_pins` and `stage_owners` are read by three functions; renaming a key makes `stage_pin`/`stage_owners` return `None` and the stage silently falls back to whole-roster sharding — pool.py:282-290, 298-304, 340-342.
- Limiter lane `"default"` is reserved for the primary to carry over AIMD state; renaming it resets rate-limit history — pool.py:101-103.

## VERIFY
```verify
grep -Fq 'digest_size=8' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'request_char_budget: int = 60000' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'structured: str = "json"' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'class PinnedProviderUnavailable(RuntimeError):' shared/polymath_shared/llm_extraction/pool.py
grep -Fq 'POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS' shared/polymath_shared/llm_extraction/pool.py
test "$(grep -c -F 'raise ValueError' shared/polymath_shared/llm_extraction/pool.py)" -ge 7
! grep -Fq 'requests.post' shared/polymath_shared/llm_extraction/pool.py
```
