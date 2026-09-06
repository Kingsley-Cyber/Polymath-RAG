---
title: "WORK LOG — CHAT-MODEL-CATALOG-V1: the chat model list is OpenCode Zen's free models plus Ollama's free cloud tier, nothing else"
change_id: CHAT-MODEL-CATALOG-V1
date: 2026-09-06
owner: governance (owner decision 2026-09-06)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.101
package: orchestrator/orchestrator/api/ui.py, scripts/chat_models_setup.py, config/chat_models/opencode_free.json, tests/determinism/test_chat_model_catalog.py, .env.example
architecture_impact: "The synthesizer dropdown (`GET /synthesizers`) no longer mirrors whatever the local Ollama daemon has pulled. Ollama entries are a fixed allowlist of the daemon's FREE cloud tier (gemma4:31b, gpt-oss:120b, gpt-oss:20b, nemotron-3-nano:30b, nemotron-3-super, nemotron-3-ultra, as `<name>-cloud` / `<name>:cloud`; env POLYMATH_OLLAMA_MODELS overrides), each flagged `available` by whether the daemon has it registered — local models and paid cloud models are not offered. OpenCode Zen's free models enter through the existing LLM-PROVIDER-LAYER-V1 row (`opencode-free`: LiteLLM provider `openai`, api_base https://opencode.ai/zen/v1) whose api_key is the indirection `env:OPENCODE_API_KEY` — resolved from the process environment at call time, never stored in the table nor sent to the browser (the providers endpoint shows the variable NAME and whether it is set). A provider whose env key is unset is hidden from the dropdown instead of offered and failing. New chats take the first entry: POLYMATH_DEFAULT_SYNTHESIZER (default `litellm:openai/glm-5-free`), else the first offered model. Generation paths are unchanged (Ollama /api/chat; LiteLLM OpenAI-compatible streaming)."
---

# WORK LOG — CHAT-MODEL-CATALOG-V1

Owner decision (2026-09-06): remove Ollama's local/paid models from the chat dropdown, keep only Ollama's free cloud tier, and set up OpenCode's free models as the chat models — only the free ones showing.

## Contract

- `GET /synthesizers` → `[*_litellm_models(), *_ollama_models()]`, preferred default first, `default` flag on exactly one entry; every entry carries `id`, `label`, `description`, `kind`, `available`.
- `_ollama_models()`: `OLLAMA_FREE_CLOUD_MODELS` (six names) or `POLYMATH_OLLAMA_MODELS`; `available` = registered with the daemon (`/api/tags`, non-fatal); an unregistered name lists with `ollama pull <name>` in its description (a cloud pull registers a name, no weights).
- Provider rows: `api_key` may be `env:NAME`; `_resolve_api_key` reads the environment at call time; `_provider_ready` hides a row whose env key is unset; `/llm/providers` returns the NAME for env keys and `ready`.
- `scripts/chat_models_setup.py --opencode-free [--refresh] --ollama-free --show`: upserts the `opencode-free` row from `config/chat_models/opencode_free.json` (31 zero-cost models snapshotted from models.dev on 2026-09-06; `--refresh` re-fetches), pulls the six Ollama cloud names, prints the offered catalog.
- The OpenCode key: `OPENCODE_API_KEY=` in `.env` (get it at https://opencode.ai/auth); until it is set the OpenCode models stay hidden and the first free Ollama model is the default.
- **Alibaba Cloud Model Studio** (owner addition, same day): provider row `alibaba-model-studio` — LiteLLM provider `anthropic` against the Bailian token plan's Anthropic-messages app in ap-southeast-1 (`https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic/v1/messages`; LiteLLM 1.98 uses `api_base` as the complete messages URL, so the path is part of it), api_key `env:ALIBABA_MODEL_STUDIO_API_KEY`, nine models from the owner's plan config (`config/chat_models/alibaba_model_studio.json`: qwen3.8-max, qwen3.8-flash, qwen3.7-max, qwen3.7-plus, qwen3.6-flash, glm-5.2, deepseek-v4-pro, deepseek-v4-pro-0813, deepseek-v4-flash-0731); `scripts/chat_models_setup.py --alibaba`; hidden until the key is set, labelled `Alibaba Model Studio · <model>`.

## Changes

- `orchestrator/orchestrator/api/ui.py`: `OLLAMA_FREE_CLOUD_MODELS`, `_ollama_allowlist`, `_ollama_registered`, `_ollama_models` (allowlist + availability), `_PROVIDER_LABELS`, `_resolve_api_key`, `_provider_ready`, `_litellm_models` (readiness gate, display label), `_litellm_credentials` (env indirection), `llm_providers` (name-only masking + `ready`), `_PREFERRED_DEFAULT` → `litellm:openai/glm-5-free`.
- `scripts/chat_models_setup.py` (new; `scripts/README.md` row; `--opencode-free`, `--alibaba`, `--ollama-free`, `--show`), `config/chat_models/opencode_free.json` and `config/chat_models/alibaba_model_studio.json` (snapshots, never keys), `.env.example` (OPENCODE_API_KEY, ALIBABA_MODEL_STUDIO_API_KEY, POLYMATH_DEFAULT_SYNTHESIZER, POLYMATH_OLLAMA_MODELS).
- Tests: `tests/determinism/test_chat_model_catalog.py` (allowlist + availability + env override + daemon down; env-indirected keys resolve / hide / mask; default ordering with and without the key; the setup script's zero-cost filter and the snapshot's consistency).
- Ollama daemon on this Mac: the four missing free cloud names registered (`ollama pull gpt-oss:120b-cloud`, `gpt-oss:20b-cloud`, `nemotron-3-nano:30b-cloud`, `nemotron-3-super:cloud`); `gemma4:31b-cloud` and `nemotron-3-ultra:cloud` were already registered.

## Proof

**Offline:** `tests/determinism/test_chat_model_catalog.py` (4) with `test_chat_runtime.py` + `test_chat_hygiene.py`: 37 passed (2026-09-06 15:5xZ).

**Live catalog on the respawned orchestrator (`GET /synthesizers`, 2026-09-06 15:5xZ):** 6 entries, all `Ollama cloud (free) · …` (gemma4:31b-cloud, gpt-oss:120b-cloud, gpt-oss:20b-cloud, nemotron-3-nano:30b-cloud, nemotron-3-super:cloud, nemotron-3-ultra:cloud), all `available: true` after `scripts/chat_models_setup.py --ollama-free` registered the four missing names; default = `ollama:gemma4:31b-cloud` (the preferred `litellm:openai/glm-5-free` is not offered yet — see below). The pre-existing LiteLLM row `ollama` (paid `kimi-k2.7-code:cloud`, `deepseek-v4-flash:cloud`) was **disabled** by the same command (not deleted); no local model is offered. `GET /llm/providers`: `opencode-free` → provider openai, api_base https://opencode.ai/zen/v1, api_key `env:OPENCODE_API_KEY`, api_key_set false, ready false, 31 models — hidden from the dropdown until the key exists.

**Live generation:** a `/chat` turn with `synthesizer: ollama:gemma4:31b-cloud` returned the typed error `502 ollama_error` carrying the provider's message verbatim — *"you (…) have reached your weekly usage limit, upgrade for higher limits"* — and the daemon answers the same for every free cloud name directly (`ollama signin`: signed in). The free tier is exhausted for this account this week; the path is intact and the failure is observable, not silent. **OpenCode free models: not exercised** — `OPENCODE_API_KEY` is not in `.env`; the first turn through `openai/glm-5-free` is the pending live proof.

**Alibaba Model Studio (added after the first commit):** row upserted live (`GET /llm/providers`: provider anthropic, 9 models, key `env:ALIBABA_MODEL_STUDIO_API_KEY`, api_key_set false, ready false) — hidden until the key is in `.env`; six new offline tests cover the snapshot, the label and the env gate (`test_chat_model_catalog.py`: 6 passed). Its first live turn (`anthropic/qwen3.8-max`) is pending the key, exactly like OpenCode.

**Alibaba Model Studio, live (2026-09-06 16:2xZ, key added to `.env` by the owner, orchestrator respawned):** `GET /llm/providers` → `alibaba-model-studio` ready, 9 models offered; grounded `/chat` turns on the chroma-keyer question through the Anthropic-messages app: `deepseek-v4-flash-0731` 200 in 22.9 s and 15.8 s with [S#] tags resolving to 7 used-evidence chunks of a 28-entry legend; `qwen3.7-plus` 200 in 39.4 s with 6 tags; `qwen3.8-max` (reasoning) 200 in 42.4 s with NO citation tags (843-char prose answer, verdict `generated`). URL composition (`/apps/anthropic/v1/messages`), headers and streaming through LiteLLM's anthropic provider work as configured. Consequences: the row's model order puts the fast, citing models first; the new-chat default is now the FIRST OFFERED entry of a preference list (`POLYMATH_DEFAULT_SYNTHESIZER`, default `litellm:openai/glm-5-free, litellm:anthropic/deepseek-v4-flash-0731, ollama:gemma4:31b-cloud`) so a hidden provider never leaves a reasoning model as the accidental default. OpenCode: the owner's first paste left the placeholder `PASTE-OPENCODE-KEY` as the value — blanked again so the 31 models stay hidden until a real key exists (a fake key would list models that fail).

**Gate reading:** the dropdown offers only free models (verified live), paid and local models are gone, the key never leaves `.env`; live generation through either free provider is blocked by account state (Ollama weekly quota) or a missing key (OpenCode), not by code.

## Rejected claims

- "Filter the daemon's tag list down to free names." Rejected: the dropdown would then depend on what happens to be pulled on one Mac; the allowlist is the contract and the daemon state is reported as `available`.
- "Store the OpenCode key in the provider row like the other rows." Rejected: keys live in `.env` only (standing rule); the row stores the variable name and the endpoint never returns a value.
- "Offer the OpenCode models before the key is set." Rejected: a model that fails on first use is worse than an absent one; the providers endpoint says exactly what is missing.

## Open contract gaps

1. **Free-tier limits are the providers'.** Ollama's free cloud usage and OpenCode Zen's free models have rate/usage limits that the chat path does not account for; a 429 surfaces as the typed generation error. Counting them per provider is the next receipt.
2. **The snapshot ages.** `config/chat_models/opencode_free.json` is a dated list; `--refresh` re-fetches from models.dev, and a model that leaves the free tier will fail with the provider's error until the row is refreshed.
3. **Anthropic-messages compatibility of the Bailian app is assumed from the owner's working client config**, not yet exercised through LiteLLM from this codebase: the first turn after the key is set proves the URL composition (`/apps/anthropic/v1/messages`), the `x-api-key` / `anthropic-version` headers and streaming (reasoning blocks surface as `reasoning_content`). If the app rejects a header, the fix is a per-row header map, not a different provider.
4. **Default model quality is unmeasured.** `glm-5-free` is the default by the owner's "free models" rule, not by a measured comparison on B/L/M with the LLM synthesizer; the citation-precision run (case 14) still uses the configured default at the time of recording.
