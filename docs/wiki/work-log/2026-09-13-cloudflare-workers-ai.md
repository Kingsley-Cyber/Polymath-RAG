---
title: "WORK LOG — CLOUDFLARE-WORKERS-AI-V1: add Cloudflare Workers AI as a supplemental provider family (extraction helpers 1-4, doc_profile helpers 5-6)"
change_id: CLOUDFLARE-WORKERS-AI-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.254
architecture_impact: "Adds six Cloudflare Workers AI lanes over the EXISTING lane/pool/limiter abstraction — cloudflare1-4 join the unpinned graph-extraction ring (dedicated:false), cloudflare_summary1-2 pin to doc_profile (dedicated:true). Smallest clean mechanism: url_template+account_id_env URL resolution, a per-lane think_suffix (Qwen /no_think), a 3036-park/3040-backoff classifier, and an /infer_batch 400->fallback fix. No existing provider changed; Parent-MAP untouched. shared/ changed -> live after a fleet bounce; 5/6 lanes park until their account ids are supplied."
---

> Owner: add Cloudflare Workers AI as an ADDITIONAL provider family using six credentials —
> CF 1-4 assist the existing graph-extraction pool, CF 5-6 dedicated to document summary/profile.
> Do not replace existing providers, do not make Cloudflare the sole extractor, do not touch
> Parent-MAP. Qualify with the real extraction/profile prompt+schema+compiler; promote only if it
> passes. Never commit tokens. Six accounts = six capacity domains.

## Contract
Cloudflare's OpenAI-compat URL embeds the account id (`…/accounts/<id>/ai/v1/chat/completions`),
which the existing schema (literal `url` + `api_key_env`) cannot express without hardcoding a
secret. The provider must plug into the EXISTING abstraction (dedicated:false → unpinned ring;
dedicated:true + stage pin → that stage), track each account independently, and treat Free-plan
daily exhaustion (3036) differently from momentary out-of-capacity (3040).

## Changes
- **pool.py**: `CloudEndpoint.think_suffix`; `_configured_providers` resolves `url` from
  `url_template` + `account_id_env` (a lane with an unset account id parks like an unset key);
  `cloud_opts` carries `think_suffix`.
- **client.py**: `_chat` appends `think_suffix` to the prompt (Qwen `/no_think`); `complete_one`
  and `_extract_prompt` classify Cloudflare 3036 (park the day) vs 3040/429 (bounded backoff) via
  the new module; `_infer_batch_call` treats 400/404/405 to `/infer_batch` as "no batch endpoint
  → per-neighborhood fallback" (Cloudflare answers 400, not 404).
- **limiter.py**: `park_provider_day(reset_secs)` — a BODY error (3036) declares the day spent via
  the existing provider-RPD-exhausted gate (admit → REFUSE_PROVIDER_RPD, 0 HTTP).
- **cloudflare_errors.py** (new): pure classifier (3036/3040/429) + seconds-to-UTC-reset.
- **lane_registry.py**: `credential_present` requires BOTH token AND account id; host from url_template.
- **config/cloud_providers.json**: 6 lanes (cloudflare1-4 dedicated:false json; cloudflare_summary1-2
  dedicated:true text, pinned to doc_profile); **config/extraction_models/limiter.yaml**: 6 isolated
  families (cloudflare_acct_1..6). **.env.example**: 12 empty placeholders. **.env** (gitignored):
  the 6 tokens + the one supplied account id — never committed.

## Proof
- **Model finding**: `@cf/qwen/qwen3-30b-a3b-fp8` is reasoning-burn (empty content at small budgets);
  only Qwen's `/no_think` disables it on Cloudflare (reasoning_effort / enable_thinking /
  chat_template_kwargs all ignored — measured).
- **Extraction (production prompt+schema+sanitize, 3 real neighborhoods)**: 100% valid; thinking-on
  22 ent/23 rel vs /no_think 79/8 → **PROMOTE cloudflare1-4, thinking ON**.
- **Profile (production fingerprint+prompt+compiler, TEXT mode, 3 real docs)**: 100% `ok=True`;
  /no_think faster (0.7 s) + richer (up to 36 fields) → **PROMOTE cloudflare_summary1-2, /no_think**.
- **12 regression tests green** (`test_cloudflare_provider.py`) + extraction/pool/registry/limiter
  suites unbroken. **Live pool**: only cloudflare2 active (the sole account id), url ends `/ai`,
  think_suffix null, dedicated:false; the other five `configured_credential_absent`; summary lanes
  in the doc_profile pin. **Credential scan clean** on every committed file.
- Evidence: `docs/wiki/experiments/cloudflare-workers-ai-2026-09-13/`; report:
  `docs/wiki/plans/CLOUDFLARE-WORKERS-AI-QUALIFICATION.md`.

## Rejected claims
- **"Use a fabricated reasoning parameter"** — REJECTED: reasoning_effort/enable_thinking are
  ignored by this model on Cloudflare; the verified switch is the `/no_think` prompt string.
- **"Force json_object for the profile lanes"** — REJECTED: doc_profile is TAGGED LINES; json mode
  made the model return a JSON error blob (the first profile canary's false-negative).
- **"Cloudflare returns 404 for /infer_batch like other clouds"** — REJECTED: it returns **400**;
  the fallback trigger was widened to 400/404/405.
- **"Six tokens = six independent capacities regardless"** — NOT ASSUMED: a same-account-id check
  is wired; it needs the ids to fire (only 1 of 6 supplied).

## Open contract gaps
- **5/6 lanes parked** — supply `CLOUDFLARE_ACCOUNT_ID_{1,3,4,5,6}` (the AI-scoped tokens cannot
  self-report their account). Duplicate account ids (shared free allocation) reported once present.
- **Live only after `scripts/boot_polymath.sh`** — shared/ changed; owner-timed (a bounce also puts
  cloudflare2 into live extraction).
- **Qualification sample n=3** — the schema/compiler PASS is unambiguous; yield-parity vs the primary
  is not established. A ≥20-doc confirmation is recommended before volume reliance.
- **One 400 pre-flight per cloud extraction batch** before the fallback — a follow-up could skip
  `/infer_batch` for cloud lanes entirely.
