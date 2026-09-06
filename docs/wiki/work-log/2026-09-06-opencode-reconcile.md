---
title: "WORK LOG — OPENCODE-RECONCILE-V1: the OpenCode row offers only the free ids the endpoint serves; the default never points at an unserved model"
change_id: OPENCODE-RECONCILE-V1
date: 2026-09-06
owner: governance (found the moment the owner's OPENCODE_API_KEY went live: the first-preference default answered "Model glm-5-free is not supported")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.108
package: scripts/chat_models_setup.py (served_model_ids, reconcile_with_endpoint, --reconcile), config/chat_models/opencode_free.json (reconciled snapshot), orchestrator/orchestrator/api/ui.py (_PREFERRED_DEFAULTS order), .env.example, tests/determinism/test_chat_model_catalog.py
architecture_impact: "Catalog hygiene. models.dev's zero-cost list for the `opencode` provider (31 ids, fetched 2026-09-06) is not what https://opencode.ai/zen/v1 serves: GET /models lists 70 ids of which 8 are in the free list (big-pickle, deepseek-v4-flash-free, ling-3.0-flash-fin-free, mimo-v2.5-free, muse-spark-1.2/1.3-contributor-free, nemotron-3-ultra-free, nemotron-3.5-lightning-free); the other 23 answer `Model <id> is not supported`. The setup script now reconciles: `--reconcile` (and `--opencode-free` whenever the key is set) fetches /models with the key from .env (never printed; a browser-like User-Agent — Cloudflare answers Python's default UA with 403 / error 1010) and keeps only snapshot ∩ served, recording `unserved`, `served_total`, `reconciled` and the original `models_snapshot` in the config. The default preference list leads with the proven, citing, fast model (Alibaba deepseek-v4-flash-0731), then OpenCode's served free models (big-pickle, mimo-v2.5-free, nemotron-3.5-lightning-free), then Ollama gemma4. The empty-synthesizer rule (first OFFERED preference) is unchanged."
---

# WORK LOG — OPENCODE-RECONCILE-V1

## Contract

A model in the dropdown is one the endpoint lists; the new-chat default is a model proven live with citations. Free-only stays the rule (paid ids the endpoint also serves are never added — the reconcile only removes).

## Changes

- `chat_models_setup.py`: `served_model_ids(api_base, key)` (GET /models), `reconcile_with_endpoint(cfg, served)` (pure), `--reconcile` flag; `--opencode-free` reconciles automatically when the key is set and prints served / unserved counts.
- `config/chat_models/opencode_free.json`: `models` = the 8 served free ids; `models_snapshot` / `names_snapshot` keep models.dev's 31; `unserved` 23; `served_total` 70; `reconciled` 2026-09-06.
- `ui.py` / `.env.example`: `POLYMATH_DEFAULT_SYNTHESIZER` default order `litellm:anthropic/deepseek-v4-flash-0731, litellm:openai/big-pickle, litellm:openai/mimo-v2.5-free, litellm:openai/nemotron-3.5-lightning-free, ollama:gemma4:31b-cloud`.
- Tests: `test_reconcile_keeps_only_the_free_ids_the_endpoint_serves` (pure function; paid served ids never added; input untouched); the snapshot test now asserts offered ⊆ snapshot.

## Proof

- Key live (owner added it to .env 2026-09-06; respawn): `/synthesizers` 46 models in 3 groups before the reconcile → 23 after (OpenCode 8, Alibaba 9, Ollama 6); `/llm/providers` shows `opencode-free` key `env:OPENCODE_API_KEY` set, ready.
- Failure that triggered this: first-preference `litellm:openai/glm-5-free` → `AuthenticationError … Model glm-5-free is not supported` (the key authenticates; the id is not served).
- Canary of the 8 served free ids (direct, 16-token "Reply OK", browser UA): big-pickle OK 1.5 s (reasoning model, finish=length at 16 tokens), mimo-v2.5-free OK 1.1 s (reasoning), nemotron-3-ultra-free OK 74.3 s, nemotron-3.5-lightning-free OK 5.1 s (thinks inline); deepseek-v4-flash-free 400 "Model is unavailable", ling-3.0-flash-fin-free 503 "Endpoint is unavailable", muse-spark-1.2 / 1.3 500 — availability fluctuates, so served ids stay offered and failures surface as typed `litellm_error` frames.
- Live RAG turn through the orchestrator, `litellm:openai/big-pickle`: wall 26.1 s, first token 18.0 s, 1,448 reasoning chars, 2,562 answer chars, 8 citation tags, `generation {finish_reason: stop, max_tokens: 16000}`, `presentation-v1`, no degradation — the OpenCode live proof 11.101 was waiting for.
- Offline: catalog tests 10 green (boundary test included); default falls to the proven model when the first preference is unoffered (already covered by `_default_synthesizer` tests).

## Rejected claims

- "Offer all 70 served ids" — rejected: the owner's rule is free models only; the endpoint's list carries no cost, so free-ness comes from models.dev and served-ness from the endpoint — the intersection is the catalog.
- "Probe availability at catalog time and hide down models" — rejected: availability changed within minutes during the canary; a hidden-then-visible model is more confusing than a typed error on a visible one.

## Open contract gaps

- The reconcile runs when the setup script runs; a model the endpoint drops later stays in the row until the next `--reconcile` (a typed `not supported` error, never silent).
- OpenCode's free models are slow or thinking-heavy today (first token 18 s on big-pickle; 74 s on nemotron-3-ultra-free); the proven default remains Alibaba until an OpenCode model measures comparably on the 10-question probe.
