---
change_id: PROVIDER-POOL-CAMPAIGN-0901
owner: governance
date: 2026-09-01
status: complete (lane wiring = owner gate)
architecture_impact: qualification method (provider_canary.py); no runtime change
last_reviewed: 2026-09-01
---

# WORK LOG — PROVIDER-POOL-CAMPAIGN-0901 (cheap-model pool qualification)

## Contract
Owner: "openrouter is interesting for taking this to the next level
with a cheap models pool... test quality and speed and throughput for
extraction and/or enrichment to talent-manage." Production rule set
mid-campaign: "if the model isn't working production-ready then I
can't use it and it fails." Owner correction that reshaped the method:
"429 is probably for concurrency and providers — there's a reason."

## Changes
- v1 canary: 8 body chunks through LLMExtractionClient +
  validate_and_normalize; 8 body parents through
  compile_parents_microbatched; production gates only. CONFLATED
  capacity failures with quality failures.
- v2 (eval/v5/fleet/provider_canary.py, standing tool): capacity events
  (429/5xx/transport) counted and paced separately from quality
  (judged over answered calls); hard 180 s budget per model; PASS =
  >=6/8 answered AND >=6/8 enriched inside budget. Proven on
  ministral-14b (PASS, 25.7 f/1Kw, 6/8, 159 s).

## Proof (14 models; 8-chunk canaries — directional, not the 40-chunk bench)
| model | facts/1Kw | ents/1Kw | enrich | wall | production |
|---|---|---|---|---|---|
| mistral-small-2603 (OR) | 25.7 | 83.4 | 7/8 · 0.98 | 4.5 s | PASS both — best OR model |
| ministral-14b-2512 (OR) | 23.7–25.7 | 60–74 | 6/8 · 0.98 | 12–15 s | PASS both |
| gemma-3-4b-it (OR) | 26.8 | 65.9 | 0/8 (gists below floor) | 6.6 s | PASS extraction only; single provider |
| mistral-small-24b-2501 (OR) | 18.5 | 75.2 | 8/8 · 1.00 | 23 s | PASS but single provider → superseded by 2603 |
| gpt-oss-20b (groq, reasoning low) | 19.6 | 60.8 | 5/8 · 1.00 | 12 s | escape rep only (8K TPM ceiling) |
| gpt-oss-20b (OR, incl. :nitro) | 4–11 | 10–37 | 6–7/8 | 6–45 s | FAIL extraction — provider-dependent garbage |
| mistral-nemo (OR) | 1.0 | 7 | 2/8 | 32 s | FAIL — pool effectively unhosted |
| ling-3.0-flash (OR) | 1.0 | 5 | — | 17–58 s | FAIL — no structured providers, throttled, slow |
| llama-3.1-8b (OR) | 5.1 | 50 | 0/8 | 5 s | FAIL |
| granite-4.1-8b / 4.0-h-micro (OR) | 4–7 | 18–44 | 0–5/8 | 11–33 s | FAIL |
| lunaris-8b / mythomax-13b (OR) | 3–6 | 9–30 | 0/8 | 6–10 s | FAIL (roleplay tunes) |

Acceptance of the in-repo tool (eval/v5/fleet/provider_canary.py, run
after commit): mistral-small-2603 PASS — 8/8 answered, 23.7 f/1Kw,
80.3 e/1Kw, 4.7 s/call, 7/8 enriched at gist 0.97, 59 s total, zero
capacity events — reproduces the scratchpad canary within noise.

## Lessons (production use of OpenRouter)
1. URL base is `https://openrouter.ai/api` — the client appends
   `/v1/chat/completions`; `/api/v1` doubles to 404 (the owner's
   long-standing "OpenRouter never works" symptom, reproduced).
2. THE POOL IS THE PRODUCT: one slug routes to N providers with
   different quantizations, speeds and limits. gpt-oss-20b is a top
   extractor on groq and garbage via OpenRouter's fastest hosts.
   Judge per pool; /models/{id}/endpoints lists providers and
   `supported_parameters` (structured_outputs) per provider.
3. `response_format: json_schema` narrows routing to structured-capable
   providers; single-provider slugs (gemma-3-4b, mistral-small-2501,
   granite) are one throttle away from a 429 storm. Prefer slugs with
   >=3 providers or first-party endpoints (Mistral family).
4. 429 "temporarily rate-limited upstream" = shared aggregate capacity
   on that provider across all OpenRouter users (BYOK lifts it). It is
   a CAPACITY event, not a quality verdict — pace it, never hammer it,
   and re-test quality on a quiet pass (gemma went FAIL→26.8 f/1Kw).
5. Sub-10B floor: every model <=8B scored 0/8 on the microbatch
   envelope regardless of family; ~14B is the enrichment floor.
6. `:nitro` (throughput sort) optimizes the wrong thing for extraction —
   it selected the hosts that produce unusable packets.

## Rejected claims
- "429 = dead pool" (my first read) — rejected by the owner's
  correction and by the controlled burst (8 concurrent → all 200).
- "gpt-oss-20b via OpenRouter escapes groq's 8K ceiling" — the
  provider lottery makes it unusable for extraction there.
- Wiring any lane from this campaign — owner gate, not taken.

## Open contract gaps
- Owner bless pending for: `openrouter1` = mistral-small-2603
  (extraction + enrichment pin), `openrouter2` = ministral-14b-2512,
  gemma-3-4b as a paced extraction-only lane, gpt-oss-20b as groq's
  escape representative; and family-interleaved slices (equivalence
  bench agreement 0.01–0.10).
- 40-chunk equivalence pass on mistral-small-2603 before it joins a
  slice rotation (8-chunk canaries are directional).
- Keys live only in the gitignored .env (OPENROUTER_API_KEY replaced
  once during the campaign at the owner's request).
