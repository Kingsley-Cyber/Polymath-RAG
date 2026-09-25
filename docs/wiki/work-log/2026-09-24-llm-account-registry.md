---
change_id: LLM-BACKEND-L1-ACCOUNT-REGISTRY
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "config + one shared module + one script + tests. No runtime behaviour change: the runtime still reads config/cloud_providers.json and config/extraction_models/limiter.yaml, which the new registry compiles to exactly (a test fails on any drift). A new module under shared/ changes the bundle hash (fence heal / bounce)."
last_reviewed: 2026-09-24
---

# LLM-BACKEND L1: the provider account registry

## Contract
- The owner, 2026-09-24: "it shouldnt be 18 or 11 api keys, it should be like 4-6 api keys with multiple models
  configured … the backend llm api seems messy. it doesnt seem indexed and treated with care and proper identification
  and ownership architecture" → roadmap `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §1.1 and §3 row 2; gap L-01.
- Then: "push it then go L1". The push of 27 commits was blocked by the permission classifier and handed to the owner as
  one Run-button command (no retry).
- L1 changes no behaviour: the registry must reproduce today's runtime configuration exactly.

## Changes
- `config/llm_accounts.yaml` (new): one entry per ACCOUNT (one API key = one account) — 6 Groq, 6 Cloudflare, 6 Gemini,
  3 OpenRouter, 3 SiliconFlow, 2 NVIDIA, 1 Alibaba, 1 Ollama = 28. Under each: `provider`, `key_env` (+ `account_id_env`
  for Cloudflare), the provider's `quota` per model where known (Groq: 30 RPM / 1K RPD / 8K TPM / 200K TPD per key per
  model, owner 2026-09-23; groq_5 qwen3.8-27b OTPM 1000, canary 2026-09-23), and its `lanes` (56) with every provider
  field and the lane's `limiter` entry verbatim. Plus `slots` (worker processes per stage, from `process_supervisor.py`
  FLEET), `stage_pins`, `local_limiters` (`mlx_local`, `ollama_cloud`) and `docs` (the old `_doc` list).
- `shared/polymath_shared/llm_extraction/accounts.py` (new): `load_registry`, `compile_runtime` (→ the two runtime
  structures), `runtime_drift` (field-by-field; provider order ignored because the runtime sorts its roster and pins name
  their lanes), `validate` (errors: unknown pinned lane; warnings: `FAMILY_SPANS_ACCOUNTS`, `PAIR_SHARED_BY_SLOTS`,
  `IDLE_PAIR`, `KEY_UNSET`, `ACCOUNT_ID_UNSET`, `LANE_UNUSED`), `ownership_rows` (one row per account × model: lanes,
  stages, slots, quota, key SET?, account id SET?, state active / parked / idle).
- `scripts/llm_accounts.py report | validate | diff` (declared in `scripts/README.md`).
- `tests/determinism/test_llm_accounts.py`: 10 tests.

## Proof
- `scripts/llm_accounts.py diff` → no drift; `test_the_registry_compiles_to_the_runtime_files_with_no_drift` passes.
- `validate` against the live environment (booleans only): 0 errors, 31 warnings, each a known problem:
  - `FAMILY_SPANS_ACCOUNTS`: `gemini` spans 6 accounts, `nvidia` 2 → new gap L-20;
  - `PAIR_SHARED_BY_SLOTS`: groq_1 × gpt-oss-120b by 6 profile slots; each pMAP pair by 4 slots; two OpenRouter pairs;
  - `IDLE_PAIR`: the audit's 7 idle Groq pairs (key 1: 20b + qwen; keys 2–6: 120b);
  - `ACCOUNT_ID_UNSET`: cloudflare_1, 3, 4, 5, 6;
  - `LANE_UNUSED`: `compiler_alibaba_qwen` (unpinned by Batch 1, kept defined for rollback).
- `report`: 28 accounts, 56 lanes, 50 account × model pairs, 32 active (5 Cloudflare pairs show `parked`: key set,
  account id missing).
- Tests: `test_llm_accounts.py` 10 pass; with `test_llm_backend_batch1.py` 24 pass; ruff clean on the new files.

## Rejected claims
- "Generate the runtime files from the registry now": that is L3's switch; L1 proves the model first (zero drift) so the
  switch cannot change behaviour silently.
- "Every provider's quota is known": only Groq's is recorded (owner figures); the others stay unrecorded until measured.

## Open contract gaps
- L3: generate the runtime files from the registry (marked GENERATED), apply ownership (all 18 Groq pairs, one owner per
  dedicated pair, 6 pMAP slots with offsets), per-account Gemini families (L-20), the Cloudflare account ids.
- L2: real-token admission and a rolling daily-token budget read their limits from the registry's `quota`.
