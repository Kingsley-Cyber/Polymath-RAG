---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 04 — Provider & Function Pools

Disk-truth from `config/cloud_providers.json` (stage_pins + providers) and `config/extraction_models/limiter.yaml`.
Config legend: **rpm / tpm / rpd / conc_cap**. No secret values here (env-var names only).

## FUNCTION → ACCOUNT(key) → MODEL

### GRAPH_EXTRACTION (unpinned ring — every `dedicated:false`/absent lane shards here; 15 lanes)
| lane | model | key | family | limits |
|---|---|---|---|---|
| gemini1–4 | gemini-3.1-flash-lite | GEMINI_API_KEY_1–4 | gemini | 15/250k/500/3 |
| gemini1b–4b | gemini-3.5-flash-lite | GEMINI_API_KEY_1–4 | gemini | 15/250k/500/3 |
| openrouter1 | mistral-small-2603 | OPENROUTER_API_KEY | openrouter | 60/500k/–/4 |
| openrouter2 | ministral-14b-2512 | OPENROUTER_API_KEY | openrouter | 60/500k/–/4 |
| openrouter3 | qwen3.7-flash | OPENROUTER_API_KEY_2 | openrouter | 60/500k/–/4 |
| nvidia2 | nemotron-3-super-120b | NVIDIA_API_KEY_2 | nvidia | 36/150k/–/4 |
| siliconflow1–3 | Qwen3-8B | SILICONFLOW_API_KEY_1–3 | none | kind=**concurrency** max 24 |
| (local primary) | Ollama/MLX daemon | — | — | concurrency |

### DOCUMENT_PROFILE (`doc_profile` pin — tiered; 9 lanes)
| tier | lane | model | key | family | limits |
|---|---|---|---|---|---|
| 0 | profile_groq1–6 | groq/**compound** | GROQ_API_KEY_1–6 | groq_acct_1–6 | 2/60k/**230**/1 |
| 1 | profile_fallback_gemini1/2 | gemini-3.1-flash-lite | GEMINI_API_KEY_5/6 | gemini | 8/200k/400/2 |
| 2 | profile_fallback_openrouter | mistral-small-2603 | OPENROUTER_API_KEY_2 | openrouter | 20/300k/–/1 |

### PMAP (`doc_parent_map` pin — 6 lanes)
| lane | model | key | family | limits |
|---|---|---|---|---|
| map_groq1–6 | groq/**compound-mini** | GROQ_API_KEY_1–6 | groq_acct_1–6 | 2/60k/**230**/1 |

### CHAT (`chat_compiler` pin — 5 lanes; latency-oriented, not a backlog drainer)
| lane | model | key | family |
|---|---|---|---|
| compiler1–4 | gemini-3.1-flash-lite | GEMINI_API_KEY_1–4 | gemini |
| compiler_alt | mistral-small-2603 | OPENROUTER_API_KEY | openrouter |

### parent_enrichment (LEGACY, dual-run→retire — 8 lanes)
gemini5/5b/6/6b (keys 5/6) + openrouter1/2/3/5. microbatch 6–8 parents/call.

## ACCOUNT(key) → FUNCTIONS → MODELS  (contention map — watch these)
| key | functions | note |
|---|---|---|
| **GROQ_API_KEY_1–6** | doc_profile (compound) + pMAP (compound-mini) | ⚠ two stages, one account. Local RPD is **per-lane** (2×230=460 admissions) against a real ~250 account/day → local can over-admit ~1.8×. Family now per-account (correlated failure circuit); RPD cap NOT merged. This is the intentional free-account exception (§8) — do not generalize. |
| GEMINI_API_KEY_1–4 | extract + chat_compiler | geminiN(3.1) + compilerN(3.1) hit the SAME per-key 3.1 quota; geminiNb(3.5) own quota |
| GEMINI_API_KEY_5–6 | doc_profile(fallback) + parent_enrichment | gemini5(3.1 enrich) + profile_fallback_gemini1(3.1 profile) share the 3.1 quota |
| OPENROUTER_API_KEY | extract + parent_enrichment + chat_compiler | one account, 3 functions |
| OPENROUTER_API_KEY_2 | extract + parent_enrichment + doc_profile(fallback) | one account, 3 functions |

## Families / breakers (circuit scope)
- **breakers are per-lane** (per provider+key+model) — good.
- **family circuits** span functions: `gemini` (14 lanes across 4 functions) and `openrouter` (6 lanes across 4 functions) are each ONE correlated-backoff circuit — the same class of coupling that the groq fix just removed. `groq_acct_N` is now per-account (6 isolated). `siliconflow` = no family (independent).

## Google models actually callable (probed live 2026-09-09)
`gemini-3.1-flash-lite` ✅, `gemini-3.5-flash-lite` ✅, `gemini-3.7-flash` ✅, `gemini-flash-lite-latest` ✅.
`gemini-2.5-flash` / `gemini-2.5-flash-lite` = **404 "not available to new users"** (listed by /models but NOT callable). `gemini-3.6-flash` = transient 503. All 8 gemini extract lanes passed a live graph-extraction schema test (entities+relations, quotes attested).

## Known config gap
Gemini extract lanes omit `reasoning_effort` and set no thinking-budget → thinking may run by default (token-efficiency risk; unverified, `finish=stop` on the probe was reassuring). SiliconFlow/OpenRouter reasoning models explicitly disable thinking; gemini extract does not.
