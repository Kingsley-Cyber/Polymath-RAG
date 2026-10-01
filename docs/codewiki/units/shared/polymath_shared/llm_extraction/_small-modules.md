# unit: shared/polymath_shared/llm_extraction/_small-modules
anchor: shared/polymath_shared/llm_extraction/__init__.py:1-15

## purpose
Support modules of the LOCAL-LLM-EXTRACTION-V1 shadow lane: package version doc, Cloudflare Workers AI error classification, effective-capacity precedence resolution, the owner relation ontology + predicate normalization, the cloud/local lane policy, and the durable Postgres store for adaptive controllers (limiter). Consumers: scheduler, limiter, gate, transports. — shared/polymath_shared/llm_extraction/__init__.py:1-15 [DERIVED]

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `classify` | def | (status, body_text) -> str \| None | cloudflare_errors.py:61-78 | — |
| `is_cloudflare_host` | def | (url) -> bool | cloudflare_errors.py:81-89 | — |
| `seconds_to_daily_reset` | def | (now=None) -> int | cloudflare_errors.py:92-97 | — |
| `load_seed` | def | () -> dict | effective_capacity.py:42-48 | — |
| `seed_for` | def | (provider_host, model, seed) -> dict \| None | effective_capacity.py:69-85 | — |
| `EffectiveCapacity` | class | frozen dataclass; to_dict() -> dict | effective_capacity.py:88-97 | — |
| `resolve` | def | (lane, observed=None, seed=None) -> EffectiveCapacity | effective_capacity.py:100-126 | — |
| `resolve_all` | def | (registry, observed=None) -> list[EffectiveCapacity] | effective_capacity.py:129-133 | — |
| `normalize_predicate` | def | (raw) -> tuple[str, str] | ontology.py:80-100 | — |
| `prompt_block` | def | () -> str | ontology.py:135-142 | — |
| `check_relation` | def | (rel) -> tuple[str, str] | ontology.py:145-147 | — |
| `effective_threshold` | def | (threshold) -> int | policy.py:64-71 | — |
| `select_lane` | def | (source_bytes, threshold=CLOUD_MIN_BYTES, affinity=None) -> LaneDecision | policy.py:74-97 | — |
| `require_cloud_eligible` | def | (source_bytes, threshold=CLOUD_MIN_BYTES, *, assist=False) -> LaneDecision | policy.py:100-117 | — |
| `LaneDecision` | class | frozen dataclass; property assist -> bool | policy.py:52-61 | — |
| `CloudBoundaryViolation` | class | RuntimeError | policy.py:47-49 | — |
| `PostgresControllerStore` | class | (dsn, *, connect_timeout=3.0); load(key)->dict\|None; save(key, state)->None | state_store.py:26-62 | — |
| `RELATION_ONTOLOGY` | const | dict id -> definition | ontology.py:19-38 | — |
| `CLOUD_MIN_BYTES` | const | 0 | policy.py:42 | — |
| `TABLE` | const | "llm_controller_state" | state_store.py:23 | — |

Package-level importers (FACTS.importers, symbol attribution unknown): orchestrator/orchestrator/api/retrieve.py, shared/polymath_shared/conformance/attempts.py, discovery.py, control_plane_status.py, llm_extraction/client.py, gate.py, limiter.py, worker_runtime.py, sidecars/local_extractor/json_mask.py, workers/workers/llm_direct.py, llm_provider.py, verify_worker.py.

## contracts

**classify(status, body_text)** — cloudflare_errors.py:61-78
- in: HTTP status int or None, body text str or None.
- out: exactly one of `"DAILY_FREE_QUOTA_EXHAUSTED"`, `"OUT_OF_CAPACITY"`, `None`.
- post: code 3036 in body -> DAILY (cloudflare_errors.py:67-68); 3040 -> OUT_OF_CAPACITY (:69-70); lowercase text containing "daily" plus "allocation"/"quota" -> DAILY (:73-74); bare status 429 -> OUT_OF_CAPACITY (:75-77); else None (:78).
- pre: only for Cloudflare-host lanes; no-op (None) for unrecognized input (:63-65).

**normalize_predicate(raw)** — ontology.py:80-100
- in: any emitted predicate string.
- out: (predicate, method); predicate always a key of RELATION_ONTOLOGY; method ∈ {"enum","alias","related_fallback"}.
- post: exact uppercase hit -> "enum" (:88-89); alias table on lowercased, space->underscore key -> "alias" (:90-92); token-bounded phrasal regex pass -> "alias" (:96-99); else ("RELATED_TO", "related_fallback") (:100).

**select_lane(source_bytes, threshold, affinity)** — policy.py:74-97
- pre: source_bytes >= 0, else ValueError (:83-84).
- post: threshold replaced by effective_threshold(threshold) (:85); source_bytes > threshold -> lane "cloud", reason "source N B > T B throughput floor" (:87-89); affinity == "cloud" -> lane "cloud", reason starts "assist:" (:90-94); else lane "local" (:95-97).

**require_cloud_eligible(source_bytes, threshold, *, assist)** — policy.py:100-117
- post: re-runs select_lane with affinity "cloud" iff assist (:111-112); decision.lane != "cloud" -> raises CloudBoundaryViolation with decision.reason and decision.threshold in the message (:113-116); returns the LaneDecision otherwise (:117).

**resolve(lane, observed, seed)** — effective_capacity.py:100-126
- in: a lane_registry.LaneInfo, optional observed mapping, optional pre-loaded seed.
- post: per field in ("rpm","tpm","rpd","conc_cap"): observed wins, then lane.capacity config, then seed limits, else None + SRC_UNKNOWN (:113-124); no provider call, no secret read (:100, module doc :16-19).

**PostgresControllerStore.load/save** — state_store.py:38-62
- load: SELECT state FROM llm_controller_state WHERE key = %s on a short autocommit connection; returns dict or None (:41-48).
- save: INSERT ... VALUES (%s, %s::jsonb, now()) ON CONFLICT (key) DO UPDATE, payload json.dumps(state, sort_keys=True) (:55-60).
- post: both swallow any Exception after one warning (:46-47, :61-62).

## effect surface
- Postgres table `llm_controller_state`: read state_store.py:43-44; write state_store.py:55-59 (upsert). Connections autocommit, own short connection, never inside a stage transaction — state_store.py:6-9, 41-42, 53-54.
- File read: `config/rate_limit_seed/catalog.v1.json` resolved from repo root parents[3] — effective_capacity.py:28-29, 46.
- Clock: `time.time()` when now is None — cloudflare_errors.py:95.
- Network: none in-module except the Postgres connect above; no Qdrant, no subprocess. [INFERRED: psycopg.connect is the only socket path in SOURCE]
- Env: no env var is read anywhere in the unit; policy.py:116 only *names* `POLYMATH_CLOUD_MIN_BYTES` inside an error string. [INFERRED: full SOURCE shown, no os.environ/getenv present]

## invariants
INVARIANT: len(RELATION_ONTOLOGY) == 18 keys — 17 canonical + RELATED_TO — ontology.py:19-38 [DERIVED]
  fails-if: prompt_block and normalize_predicate drift out of sync; enum acceptance silently changes.
INVARIANT: per-field precedence observed > config > seed > unknown — effective_capacity.py:117-124 [DERIVED]
  fails-if: scheduler optimizes against a guessed catalog number instead of live header truth.
INVARIANT: a limit found nowhere stays None (SRC_UNKNOWN), never 0 — effective_capacity.py:124, 16 [DERIVED]
  fails-if: unknown limit masquerades as 0; a healthy lane is treated as zero-capacity.
INVARIANT: effective_threshold(x) >= CLOUD_MIN_BYTES (= 0) for every input — policy.py:64-71 [DERIVED]
  fails-if: config lowers the owner floor and small work is forced local.
INVARIANT: select_lane -> source_bytes > threshold implies lane == "cloud" — policy.py:87-89 [DERIVED]
  fails-if: large work crawls the local lane.
INVARIANT: classify output ∈ {"DAILY_FREE_QUOTA_EXHAUSTED", "OUT_OF_CAPACITY", None} — cloudflare_errors.py:61-78 [DERIVED]
  fails-if: another provider's error gets reclassified; 3036/3040 behaviours conflated (day park vs backoff).
INVARIANT: normalize_predicate always returns a predicate ∈ RELATION_ONTOLOGY keys — ontology.py:88-100 [DERIVED]
  fails-if: an off-enum string reaches persistence ungated.
INVARIANT: 1 <= seconds_to_daily_reset(now) <= 86400 — cloudflare_errors.py:95-97 [INFERRED: now % 86400 ∈ [0,86400), so day − r ∈ (0,86400]; `or day` lifts the int-truncated 0 to 86400]
  fails-if: park window of 0 (instant retry-loop) or > 1 day.
INVARIANT: PostgresControllerStore emits at most one warning per instance lifetime (load and save share `_warned`) — state_store.py:30, 33-36 [DERIVED]
  fails-if: silent permanent in-memory mode after the first transient DB hiccup.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.time()` cloudflare_errors.py:95; Postgres reads/writes state_store.py:41, 53; seed file read effective_capacity.py:46). Everything else in the unit is pure. [DERIVED]
idempotency: SAFE — classify/normalize_predicate/select_lane are pure; save is an upsert (ON CONFLICT DO UPDATE, state_store.py:55-59); load is a read. [DERIVED]

## failure behaviour
- cloudflare_errors.py:88 — Exception in `is_cloudflare_host` SWALLOWED: `return False`; classification never breaks a dispatch. [DERIVED]
- state_store.py:46-47 — Exception in `load` SWALLOWED: log once, `return None`; caller continues in-memory. [DERIVED]
- state_store.py:61-62 — Exception in `save` SWALLOWED: log once, return; controller halving not persisted. [DERIVED]
- effective_capacity.py:47-48 — (FileNotFoundError, json.JSONDecodeError) on seed -> `{}`; seed optional by design. [DERIVED]
- Raised, not swallowed: `CloudBoundaryViolation` policy.py:114-116; `ValueError` negative threshold policy.py:69-70; `ValueError` negative source_bytes policy.py:83-84.

## dumb-code flags
- Stale doc: `__init__.py:12` says "the cloud boundary (300 KB)" while `CLOUD_MIN_BYTES = 0` — policy.py:42, supersession comment policy.py:37-41. [DERIVED]
- Dead disjunct: cloudflare_errors.py:73 `_CODE_DAILY in codes or` — line 67 already returned when true, so this operand is always False here. [INFERRED: control flow 67→73]
- Host match without dot boundary: `urlparse(url).netloc.endswith("api.cloudflare.com")` also matches hosts like `notapi.cloudflare.com`. cloudflare_errors.py:87 [INFERRED: suffix match, no leading-dot guard]
- Doc-vs-code: effective_capacity.py:70-71 docstring "exact model match first" but code is substring containment `em in model_l` — effective_capacity.py:81. [INFERRED: comparison of the two lines]
- With `CLOUD_MIN_BYTES = 0` as the default threshold, select_lane's `source_bytes > threshold` sends every nonzero document to cloud; the "prefers local" reason at policy.py:97 is reachable by default only at source_bytes == 0. [INFERRED]
- Reason-string API: `LaneDecision.assist` is `reason.startswith("assist")` — policy.py:60-61; any reword of the reason at policy.py:93-94 silently disables assist detection. [DERIVED]
- Magic number `day = 86400` inline — cloudflare_errors.py:96. [DERIVED]
- Error message cites env var `POLYMATH_CLOUD_MIN_BYTES` that this unit never reads — policy.py:116. [INFERRED: no env access in SOURCE]

## refactor notes
- Changing `CLOUD_MIN_BYTES` (0) re-flips lane routing for every document; package importers include workers/workers/llm_direct.py, workers/workers/llm_provider.py, workers/workers/verify_worker.py, orchestrator/orchestrator/api/retrieve.py (FACTS.importers; policy.py:42).
- RELATION_ONTOLOGY / PREDICATE_ALIASES / prompt_block define the persisted canonical predicate vocabulary; gate.py is an importer (FACTS.importers); alias edits change normalize_predicate results — ontology.py:44-77, 90-99.
- `_ALIAS_PATTERNS` is compiled at import time — ontology.py:112; mutating PREDICATE_ALIASES afterwards has no effect on the phrasal pass.
- `TABLE = "llm_controller_state"` is coupled to migration 0040 — state_store.py:11-12, 23; rename requires the migration.
- Seed path `config/rate_limit_seed/catalog.v1.json` resolved via `parents[3]` — effective_capacity.py:28-29; moving the file silently degrades every lane to config/unknown (load_seed -> {} at 47-48).
- `resolve` reloads the seed from disk on every direct call; `resolve_all` loads it once — effective_capacity.py:107 vs 133. [DERIVED]

## VERIFY
```verify
grep -Fq '_CODE_DAILY = 3036' shared/polymath_shared/llm_extraction/cloudflare_errors.py
grep -Fq 'CLOUD_MIN_BYTES = 0' shared/polymath_shared/llm_extraction/policy.py
grep -Fq 'TABLE = "llm_controller_state"' shared/polymath_shared/llm_extraction/state_store.py
grep -Fq 'LAST_RESORT = "RELATED_TO"' shared/polymath_shared/llm_extraction/ontology.py
grep -Fq 'catalog.v1.json' shared/polymath_shared/llm_extraction/effective_capacity.py
grep -Eq 'ON CONFLICT \(key\) DO UPDATE' shared/polymath_shared/llm_extraction/state_store.py
test "$(grep -c -F 'SRC_' shared/polymath_shared/llm_extraction/effective_capacity.py)" -ge 4
```
