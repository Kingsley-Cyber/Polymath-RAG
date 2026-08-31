---
change_id: MULTI-PROVIDER-AUTH-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: fenced (llm_extraction client/pool) + supervisor FLEET (extract3) + committed provider registry config/cloud_providers.json; Groq LIVE in the pool
last_reviewed: 2026-08-30
---

# WORK LOG — MULTI-PROVIDER-AUTH-V1 (Groq + NVIDIA pre-config, Groq live)

## Contract
Owner 2026-08-30: "setup multiple cloud infrastructure rn to include
groq, and nvidia. i should have a repo or setup that already has the
setup for easy pre config setup for these providers."

## Changes
- `config/cloud_providers.json` (COMMITTED, no secrets): the provider
  registry. Groq + NVIDIA ship pre-configured (url, model, quirks,
  api_key_env). AUTO-GATE: a provider joins the pool the moment its key
  resolves (process env → repo `.env`, gitignored) and `enabled` is not
  false — setup for a new provider is pasting one key into `.env`.
  Parked providers are logged once, never silent.
- Client auth: `LLMExtractionClient(api_key=…)` sends
  `Authorization: Bearer` on `/v1/chat/completions` (extract + probe);
  loopback daemons keep sending no key. Per-endpoint `cloud_opts`:
  `reasoning_effort` (None = OMIT the field — strict APIs 400 on
  unsupported params) and `json_mode`; defaults reproduce the primary
  Ollama behavior byte-identically.
- Pool v2: roster = settings primary + registry providers (key-gated) +
  env-JSON extras; quirks ride into `pool_fingerprint()` (contract
  input); keys are `repr=False` and excluded from fingerprints/logs.
  `_resolve_key` reads the repo `.env` so fleet workers see a key drop
  without a supervisor env restart.
- `extract3` slot (FLEET + pipeline profile): a second cloud-affinity
  worker so a multi-provider pool gets cloud PARALLELISM, not just
  sharding. Budget inherits via the numbered-sibling rule.
- `scripts/probe_cloud_endpoints.py`: assertable preflight — one-token,
  no-document probe per roster endpoint; non-zero exit if any active
  endpoint fails (canary-before-batch-spend law).
- `.env` gained `GROQ_API_KEY` (copied from the owner's existing
  ~/.hermes/.env key) + a commented `NVIDIA_API_KEY` slot.

## Model pins (live-verified where possible)
- groq → `openai/gpt-oss-120b`, reasoning_effort "low". The first pin
  (llama-3.3-70b-versatile) 404'd — DECOMMISSIONED on Groq; the live
  roster was listed via /v1/models and re-pinned. gpt-oss-120b is a
  reasoning model: "low" caps the thinking-burn failure mode this
  codebase already measured on qwen/deepseek lanes.
- nvidia → `meta/llama-3.3-70b-instruct` (integrate.api.nvidia.com),
  PARKED until `NVIDIA_API_KEY` (nvapi-…) lands in `.env` — no NVIDIA
  key exists anywhere on this machine (searched env, dotfiles, hermes).
  Re-verify the pin with the probe script on activation.

## Proof
- Probe: `groq OK 307 ms auth=key`, `primary OK 1080 ms`; nvidia parked.
- REAL extraction canary through Groq (synthetic text, no corpus
  content): sanitize ok=True, no salvage, 6 typed entities with
  verbatim quotes, ontology-conform relations (IS_A, PART_OF), 1.5 s
  wall, 549 output tokens. Contract adherence proven end-to-end,
  not just liveness.
- tests/determinism/test_extraction_pool.py 11/11 — fixture now
  isolates the machine's real registry/.env; new tests pin the
  auto-gate (key drop = activation, keyless = parked, enabled:false =
  parked), .env resolution order, and that keys never leak into
  fingerprint or repr.
- Full determinism suite at the pre-existing 8-failure baseline.

## Rejected claims
- "Put keys in cloud_providers.json for one-file setup" — rejected: the
  registry is committed; keys live only in the gitignored `.env`.
- "Reuse the primary's limiter for all endpoints" — rejected (already):
  per-endpoint AIMD lanes; a throttled provider halves itself only.

## Open contract gaps
- NVIDIA activation is one paste away but UNVERIFIED until a key
  exists; run `python scripts/probe_cloud_endpoints.py` after pasting.
- Groq free-tier rate limits are real; the AIMD limiter + Retry-After
  handling govern, but a large corpus-wide run on free tier will
  throttle — watch the limiter lane on first big ingest.
- Roster changes shift blake2b doc→endpoint assignment (contract
  fingerprint changes with them — visible, by design).
