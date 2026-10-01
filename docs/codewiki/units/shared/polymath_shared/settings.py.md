# unit: shared/polymath_shared/settings.py
anchor: shared/polymath_shared/settings.py:1-286

## purpose
Typed pydantic-settings configuration for every Polymath process (control, orchestrator, workers, shared clients). Policy lives here so the compose file stays topology-only; secrets stay in the environment and are never logged. — settings.py:1-6 [DERIVED]
Single config source: the environment, seeded from the repo `.env`, resolved absolutely from this file's location (`parents[2] / ".env"`) because pydantic-settings resolves a relative `env_file` against the working directory — the documented cause of past silent fallback to built-in defaults. — settings.py:17-33 [DERIVED]

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `get_settings` | function | `() -> Settings` (lru_cached) | settings.py:283-285 | module imported by 30 files: control/control/main.py, orchestrator/orchestrator/api/retrieve.py, workers/workers/extract_worker.py, shared/polymath_shared/clients.py, … (FACTS.importers) |
| `Settings` | class | `BaseSettings`; composes all sub-settings via `default_factory` | settings.py:272-281 | via `get_settings` |
| `PostgresSettings` | class | `BaseSettings`, prefix `POLYMATH_PG_` | settings.py:35-40 | — (module importers) |
| `SidecarSettings` | class | `BaseSettings`, prefix `POLYMATH_`; 2 model validators | settings.py:44-146 | — (module importers) |
| `WorkerSettings` | class | `BaseSettings`, prefix `POLYMATH_WORKER_` | settings.py:148-225 | — (module importers) |
| `ControlSettings` | class | `BaseSettings`, prefix `POLYMATH_CONTROL_` | settings.py:227-253 | — (module importers) |
| `StoreSettings` | class | `BaseSettings`, prefix `POLYMATH_` | settings.py:255-270 | — (module importers) |

## contracts

`get_settings()` — settings.py:283-285
- in: none
- out: one `Settings` instance per process (`@lru_cache`)
- pre: env vars and/or repo `.env` at `parents[2]` supply values; validators must pass
- post: repeated calls return the identical instance

`SidecarSettings.validate_llm_extraction_endpoints()` — settings.py:111-126
- in: `self.llm_local_extract_url`, `self.llm_cloud_url`
- out: `self` or raises
- pre: fields populated (defaults exist)
- post: both URLs have scheme in `("http", "https")` and hostname in `_LOOPBACK_HOSTS`, else `ValueError("... must be a loopback URL ...")` — settings.py:119-126

`SidecarSettings.validate_local_llm_connection()` — settings.py:128-146
- in: `self.local_llm_provider`, `self.local_llm_model`, `self.local_llm_url`
- out: `self` or raises
- pre: provider set
- post: provider in `("disabled", "ollama_local")`; if enabled, model non-empty and `local_llm_url` loopback — settings.py:130-146

## effect surface
No DB tables, no Qdrant/Neo4j calls, no subprocesses (FACTS: `tables_read: []`, `tables_written: []`). No network calls — validators only `urlparse`. — settings.py:121, 139 [DERIVED]
File read: repo `.env` = `Path(__file__).resolve().parents[2] / ".env"` — settings.py:33 [DERIVED]

Env flags read (field = default; env var = prefix + field name per pydantic-settings [INFERRED]):

| prefix | field = default | anchor |
|---|---|---|
| `POLYMATH_PG_` | `dsn = "postgresql://polymath:polymath@127.0.0.1:5432/polymath"` | settings.py:38 |
| `POLYMATH_` | `embedder_url = "http://127.0.0.1:8742"` | settings.py:46 |
| `POLYMATH_` | `reranker_url = "http://127.0.0.1:8743"` | settings.py:47 |
| `POLYMATH_` | `local_llm_provider = "disabled"` | settings.py:49 |
| `POLYMATH_` | `local_llm_url = "http://127.0.0.1:11434"` | settings.py:55 |
| `POLYMATH_` | `local_llm_model = ""` | settings.py:59 |
| `POLYMATH_` | `llm_local_extract_url = "http://127.0.0.1:8755"` | settings.py:63 |
| `POLYMATH_` | `llm_local_extract_model = "mlx-community/Qwen3.5-4B-MLX-4bit"` | settings.py:68 |
| `POLYMATH_` | `llm_cloud_url = "http://127.0.0.1:11434"` | settings.py:72 |
| `POLYMATH_` | `llm_cloud_model = "qwen3.5:397b-cloud"` | settings.py:78 |
| `POLYMATH_` | `llm_cloud_primary = True` | settings.py:83 |
| `POLYMATH_` | `llm_cloud_extra_endpoints = ""` | settings.py:90 |
| `POLYMATH_` | `g3_reranker = True` | settings.py:99 |
| `POLYMATH_` | `sidecar_timeout_s = 60.0` | settings.py:105 |
| `POLYMATH_` | `sidecar_pin_required = True` | settings.py:107 |
| `POLYMATH_WORKER_` | `poll_interval_s = 2.0` | settings.py:150 |
| `POLYMATH_WORKER_` | `batch_size = 8` | settings.py:151 |
| `POLYMATH_WORKER_` | `enrichment_batch_concurrency = 5` (ge 1, le 32) | settings.py:153 |
| `POLYMATH_WORKER_` | `claim_ttl_s = 300` | settings.py:157 |
| `POLYMATH_WORKER_` | `extraction_provider = "llm_live"` | settings.py:160 |
| `POLYMATH_WORKER_` | `enrichment_auto = True` | settings.py:165 |
| `POLYMATH_WORKER_` | `enrichment_provider = "llm"` | settings.py:170 |
| `POLYMATH_WORKER_` | `enrichment_profile = "qualification"` | settings.py:175 |
| `POLYMATH_WORKER_` | `enrichment_input_token_ceiling = 6000` | settings.py:179 |
| `POLYMATH_WORKER_` | `evidence_utility_enabled = False` (alias `POLYMATH_EVIDENCE_UTILITY`) | settings.py:183-184 |
| `POLYMATH_WORKER_` | `latent_retrieval_enabled = True` | settings.py:191 |
| `POLYMATH_WORKER_` | `cloud_min_bytes = 0` (ge 0) | settings.py:197 |
| `POLYMATH_WORKER_` | `llm_concurrency_local = 2` | settings.py:206 |
| `POLYMATH_WORKER_` | `llm_concurrency_cloud = 6` | settings.py:208 |
| `POLYMATH_WORKER_` | `llm_max_neighborhood_chars = 60_000` | settings.py:210 |
| `POLYMATH_WORKER_` | `chunker = "tier_v3"` (alias `POLYMATH_CHUNKER`) | settings.py:217-218 |
| `POLYMATH_CONTROL_` | `tick_interval_s = 10.0` | settings.py:229 |
| `POLYMATH_CONTROL_` | `lease_ttl_s = 30` | settings.py:230 |
| `POLYMATH_CONTROL_` | `max_attempts = 3` | settings.py:231 |
| `POLYMATH_CONTROL_` | `stall_threshold_s = 180` (ge 30) | settings.py:233 |
| `POLYMATH_CONTROL_` | `extraction_drop_tolerance = 0.10` (ge 0.0, le 1.0) | settings.py:237 |
| `POLYMATH_CONTROL_` | `extraction_coverage_floor = 0.0` (ge 0.0, le 1.0) | settings.py:244 |
| `POLYMATH_CONTROL_` | `medic_enabled = True` | settings.py:250 |
| `POLYMATH_CONTROL_` | `medic_rearm_per_tick = 20` (ge 0) | settings.py:251 |
| `POLYMATH_CONTROL_` | `medic_deadlock_wait_s = 120` (ge 30) | settings.py:252 |
| `POLYMATH_CONTROL_` | `medic_per_ticket_daily_cap = 5` (ge 1) | settings.py:253 |
| `POLYMATH_` | `qdrant_url = "http://127.0.0.1:6334"` | settings.py:257 |
| `POLYMATH_` | `neo4j_uri = "bolt://127.0.0.1:7688"` | settings.py:258 |
| `POLYMATH_` | `neo4j_user = "neo4j"` | settings.py:259 |
| `POLYMATH_` | `neo4j_password = "polymath-dev"` | settings.py:260 |
| `POLYMATH_` | `embedding_contract_id = "neural-embed-v1"` | settings.py:262 |
| `POLYMATH_` | `env = "local"`, `log_level = "INFO"` | settings.py:274-275 |

## invariants
INVARIANT: `_ENV_FILE` == `Path(__file__).resolve().parents[2] / ".env"` — settings.py:33 [DERIVED]
  fails-if: process resolves `.env` against cwd; classes silently use built-in defaults (documented incident, settings.py:27-31).
INVARIANT: count of `model_config` with `env_file=_ENV_FILE` == 6 (36, 45, 149, 228, 256, 273) — settings.py:36-273 [DERIVED]
  fails-if: a new settings class without `env_file` re-introduces the silent-default bug.
INVARIANT: extraction endpoint hostnames ∈ `_LOOPBACK_HOSTS` == `("127.0.0.1", "localhost", "::1")` — settings.py:42, 122 [DERIVED]
  fails-if: a non-loopback host would move ≤300 KB documents off-machine under the "local" label.
INVARIANT: `cloud_min_bytes >= 0` and 300,000 is a raise-only floor ("may be raised, never lowered") — settings.py:197-204 [DERIVED]
  fails-if: lowering it lets small documents select/dispatch a cloud provider.
INVARIANT: `extraction_provider` default `"llm_live"` is the only extraction path (GLiNER/spaCy deleted 2026-09-03) — settings.py:160-163 [DERIVED]
  fails-if: another value routes to deleted code.
INVARIANT: `get_settings()` returns one instance per process (`@lru_cache`) — settings.py:283-285 [DERIVED]
  fails-if: multiple live `Settings` instances can disagree mid-process.

## determinism & idempotency
determinism: NONDETERMINISTIC (resolved values depend on process env + repo `.env` file, settings.py:33; construction itself is pure given inputs — no clock/random/uuid/network/db)
idempotency: SAFE (pure dataclasses of config; no writes, no network; repeated `get_settings()` returns the cached instance — settings.py:283-285)

## failure behaviour
- `ValueError` `f"{name} must be a loopback URL (got {url!r}); the 300 KB rule forbids extraction endpoints off this machine"` — settings.py:123-125 [DERIVED]
- `ValueError` `f"unknown local LLM provider: {provider}"` — settings.py:131-132 [DERIVED]
- `ValueError` `"POLYMATH_LOCAL_LLM_MODEL is required when the local LLM provider is enabled"` — settings.py:135-138 [DERIVED]
- `ValueError` `"POLYMATH_LOCAL_LLM_URL must be loopback for ollama_local"` — settings.py:143-145 [DERIVED]
- Callers see these as construction-time failures; nothing is swallowed or retried here. [INFERRED: pydantic wraps validator ValueErrors into a ValidationError at instantiation]
- Documented downstream consequence of a bad default: wrong Postgres password → every `/retrieve` returned HTTP 500 with 30s pool timeouts per request — settings.py:27-31 [DERIVED]
- `g3_reranker=True`: a missing reranker sidecar fails loudly while enabled — settings.py:101-103 [DERIVED]

## dumb-code flags
- Default credentials disagree: Postgres `dsn` password `polymath` (settings.py:38) vs `neo4j_password = "polymath-dev"` (settings.py:260), while the comment says the deployment Postgres password is `polymath-dev` (settings.py:27-29).
- Loopback tuple duplicated: `_LOOPBACK_HOSTS` constant (settings.py:42) vs inline `("127.0.0.1", "localhost", "::1")` in `validate_local_llm_connection` (settings.py:140-141).
- `llm_cloud_url` default `http://127.0.0.1:11434` is byte-identical to `local_llm_url` default (settings.py:55, 72) — intentional (Ollama proxies cloud, settings.py:73-76) but easy to misread as copy-paste.
- Comment `# Field name deliberately != "rescue": POLYMATH_RESCUE belongs to the` sits directly above `control: ControlSettings` (settings.py:280-281); it documents an absent field and reads orphaned next to `control`. [INFERRED: comment placement does not match what it explains]
- Retired values kept as documentation strings: `chunker` options `legacy_v1` / `semantic_v2 (retired qualification candidate)` — settings.py:216-225.
- Floor 300,000 for `cloud_min_bytes` exists only in the description; actual default is `0` with clamping delegated to `policy.effective_threshold` — settings.py:197-204.

## refactor notes
- 30 importer files (control/, orchestrator/api/, workers/, shared/) depend on this module — renaming classes, fields, or changing defaults ripples everywhere (FACTS.importers; settings.py:272-281).
- `@lru_cache` on `get_settings` (settings.py:283): tests and runtime reload need `cache_clear`; values are pinned per process.
- Env prefixes are deployment contract: `POLYMATH_PG_` (36), `POLYMATH_` (45, 256, 273), `POLYMATH_WORKER_` (149), `POLYMATH_CONTROL_` (228); alias literals `POLYMATH_EVIDENCE_UTILITY` (183-184) and `POLYMATH_CHUNKER` (217-218).
- `_ENV_FILE` resolution `parents[2]` (settings.py:33): moving this file or the `.env` silently reverts every class to defaults — the measured HTTP-500 incident (settings.py:27-31).
- `cloud_min_bytes` raise-only floor semantics (settings.py:197-204) must survive any refactor; enforcement is duplicated at selection AND dispatch elsewhere.

## VERIFY
```verify
grep -Fq 'postgresql://polymath:polymath@127.0.0.1:5432/polymath' shared/polymath_shared/settings.py
grep -Fq 'env_file=_ENV_FILE' shared/polymath_shared/settings.py
test "$(grep -c -F 'env_file=_ENV_FILE' shared/polymath_shared/settings.py)" -ge 6
test "$(grep -c -F 'default_factory=' shared/polymath_shared/settings.py)" -ge 5
grep -Fq 'mlx-community/Qwen3.5-4B-MLX-4bit' shared/polymath_shared/settings.py
grep -Fq 'neural-embed-v1' shared/polymath_shared/settings.py
grep -Fq 'def get_settings() -> Settings:' shared/polymath_shared/settings.py
! grep -Fq 'print(' shared/polymath_shared/settings.py
```
