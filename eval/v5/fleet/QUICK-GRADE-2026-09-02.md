# QUICK-MODEL-GRADE — 2026-09-02 (owner: "a quick test… 2 chunks with an answer key… all in 5 mins")

Tool: `eval/v5/fleet/quick_model_grade.py` · key: `quick_grade_answer_key.json`
(chunk A = OnStar/Jobs Theory, 212 tok; chunk B = Tata Nano, 194 tok;
enrichment = chunk B's 2-child parent, 8 must-cover terms). All models
concurrently through the PRODUCTION client (json mode), gate and enrichment
compiler; 120 s budget per model. Whole run: **76 s wall** for seven models.

Rubric: extraction = 0.40·ent recall + 0.20·ent precision + 0.30·rel recall
+ 0.10·(1−hallucination); enrichment = 0.50·READY + 0.35·term coverage +
0.15·gist_coverage; overall = mean; A ≥ 0.80, B ≥ 0.65, C ≥ 0.50, else F;
over budget or an invalid packet on either chunk = F.

## Pass 1 — as-is (json mode, no reasoning override)

| model | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | halluc A/B | envelope | terms | gist | total s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistralai/mistral-small-2603 (reference) | **A** | 0.82 | 0.684 | 0.956 | 0.67/1.0 | 1.0/1.0 | 0.12/0.3 | 0.25/0.0 | READY | 7/8 | 1.0 | 10.9 |
| ibm-granite/granite-4.0-h-micro | **B** | 0.731 | 0.506 | 0.956 | 0.17/0.75 | 1.0/1.0 | 0.0/0.3 | 0.0/0.45 | READY | 7/8 | 1.0 | 57.0 |
| meta-llama/llama-3.1-8b-instruct | **F** | 0.249 | 0.498 | 0.0 | 0.67/0.38 | 1.0/1.0 | 0.25/0.0 | 0.44/0.5 | INVALID: ENRICH_EMPTY | 0/8 | 0 | 30.0 |
| ibm-granite/granite-4.1-8b | **F** | 0.236 | 0.398 | 0.075 | 0.5/0.25 | 1.0/1.0 | 0.0/0.0 | 0.38/0.68 | INVALID: GISTS_BELOW_FLOOR | 0/8 | 0.5 | 17.1 |
| qwen/qwen3.7-flash | **F** | 0.0 | 0.0 | 0.0 | ERR | ERR | ERR | ERR | INVALID: UNPARSEABLE | 0/8 | 0 | 76.2 |
| inclusionai/ling-3.0-flash | **F** | 0.0 | 0.0 | 0.0 | ERR | ERR | ERR | ERR | INVALID: HTTP_429 | 0/8 | 0 | 4.1 |
| thinkingmachines/inkling-small:free | **F** | 0.0 | 0.0 | 0.0 | ERR | ERR | ERR | ERR | INVALID: HTTP_403 | 0/8 | 0 | 0.5 |

## Why each failed (diagnosed, not guessed)

- **qwen/qwen3.7-flash** — a REASONING model: it spent the whole 2,500-token
  output budget on `reasoning` (2,500 reasoning tokens, empty content,
  finish=length) on every call. With thinking turned off
  (`reasoning_effort: none` or `reasoning: {enabled: false}`) the same call
  returns valid contract JSON in 5–6 s. Re-graded in pass 2.
- **inclusionai/ling-3.0-flash** — ALSO a reasoning model (2,661 reasoning
  tokens, empty content) AND slow (130 s for one chunk on DeepInfra ≈ 19
  tok/s) AND rate-limited upstream ("temporarily rate-limited upstream",
  HTTP 429 on 4 of 5 calls, the Novita pool member declares no JSON mode).
  Capacity event by the owner's rule, so re-tried in pass 2 with thinking
  off — but 130 s per chunk cannot meet the five-minute test regardless.
- **thinkingmachines/inkling-small:free** — HTTP 403: "only available on
  agentic harnesses. Try plugging it into a coding agent…" Not callable
  from an API client on this key. Access, not capability; final.
- **meta-llama/llama-3.1-8b-instruct** — capability: entity recall
  0.67/0.38, no relations on chunk B, hallucination 44–50 % of proposals
  (unattested quotes/endpoints), enrichment envelope EMPTY. Same profile
  as the 2026-09-01 campaign.
- **ibm-granite/granite-4.1-8b** — capability: entity recall 0.5/0.25,
  zero relations, hallucination 38–68 %, enrichment gists below the
  coverage floor. Strict `structured_outputs` support on its provider does
  not help a model that invents grounding.
- **ibm-granite/granite-4.0-h-micro** — the surprise: enrichment READY,
  7/8 must-cover terms, gist 1.0 — the only candidate that matched the
  reference on enrichment. Extraction is weak (entity recall 0.17 on the
  OnStar chunk, relation recall 0/0.3) and it is slow for a micro model
  (57 s total, single provider Cloudflare). B overall; an enrichment-only
  candidate at $0.02/$0.11 per M if ever a cheap gist lane is wanted.

## Pass 2 — thinking off (`QUICK_REASONING=none`, the client sends `reasoning_effort: none`)

| model | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | halluc A/B | envelope | terms | gist | total s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen/qwen3.7-flash | **B** | 0.787 | 0.619 | 0.956 | 0.67/0.75 | 1.0/1.0 | 0.0/0.4 | 0.22/0.27 | READY | 7/8 | 1.0 | 15.2 |
| inclusionai/ling-3.0-flash | **F** | 0.0 | – | – | ERR | ERR | ERR | ERR | INVALID: HTTP_429 (upstream rate-limited, both passes) | 0/8 | 0 | 4.1 |

## Verdicts

| model | verdict | one line |
|---|---|---|
| qwen/qwen3.7-flash | **B — the only candidate worth a canary**, thinking OFF is mandatory | 15 s for both chunks + enrichment; enrichment matches the reference (7/8, gist 1.0); extraction recall 0.67/0.75 with 22–27 % unattested proposals; relation recall weak (0/0.4). Single provider (Alibaba). Next step if wanted: 8-chunk canary with `CANARY_REASONING=none`, then a receipt run |
| ibm-granite/granite-4.0-h-micro | **B — enrichment-only curiosity** | enrichment READY 7/8 gist 1.0 at $0.02/$0.11; extraction too weak (recall 0.17 on chunk A, relations 0/0.3) and 57 s total on a single provider |
| meta-llama/llama-3.1-8b-instruct | **F — capability** | 44–50 % hallucinated proposals, no relations on B, enrichment envelope EMPTY (matches the 2026-09-01 campaign) |
| ibm-granite/granite-4.1-8b | **F — capability** | recall 0.5/0.25, zero relations, 38–68 % hallucination, gists below floor |
| inclusionai/ling-3.0-flash | **F — capacity now, latency regardless** | upstream 429 on 6 of 7 calls across two passes; the one answered call took 130 s (≈19 tok/s, reasoning model) — cannot meet a five-minute test even when the throttle lifts |
| thinkingmachines/inkling-small:free | **F — not callable** | HTTP 403 "only available on agentic harnesses"; not an API model on this key |
| mistralai/mistral-small-2603 (reference) | **A** | 0.82–0.827 across two runs in 11–12 s; calibrates the key's ceiling |

Reproduce: `.venv/bin/python eval/v5/fleet/quick_model_grade.py` (defaults to these seven; `QUICK_MODELS=`, `QUICK_REASONING=none`, `QUICK_BUDGET_S=`).

## Canary — qwen/qwen3.7-flash, json mode, reasoning OFF (`CANARY_REASONING=none`, 8 chunks + 8 parents, 180 s budget)

- Extraction 8/8 answered, walls 3.1–9.4 s (mean 5.3 s), **103–130 output tok/s** (fastest lane measured to date), limiter wait 0.0 s, finish=stop ×8, one nudge retry; facts 15.4/1Kw, entities 50.5/1Kw, 17 gate rejections.
- Enrichment 8/8 READY, gist 1.00, per-call 12.6–21.8 s (mean 16.3 s).
- **VERDICT PASS, total 70 s** (budget 180). Density sits between gemini-3.1-flash-lite (12.1) and ministral-14b (23.7); the model is unusable without the reasoning-off flag (as-is it burns the entire output budget on reasoning tokens).

## Pass 3 — owner: failures removed; three free slugs added; qwen with thinking off

| model | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | halluc A/B | envelope | terms | gist | total s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistralai/mistral-small-2603 (reference) | **A** | 0.837 | 0.762 | 0.912 | 0.83/1.0 | 0.94/1.0 | 0.38/0.3 | 0.0/0.0 | READY | 6/8 | 1.0 | 11.8 |
| qwen/qwen3.7-flash@none | **B** | 0.766 | 0.576 | 0.956 | 0.5/0.75 | 1.0/1.0 | 0.0/0.4 | 0.33/0.36 | READY | 7/8 | 1.0 | 14.6 |
| ibm-granite/granite-4.0-h-micro | **B** | 0.731 | 0.506 | 0.956 | 0.17/0.75 | 1.0/1.0 | 0.0/0.3 | 0.0/0.45 | READY | 7/8 | 1.0 | 57.5 |
| liquid/lfm-2.5-2.6b:free | **F** | 0.456 | 0.0 | 0.912 | ERR | ERR | ERR | ERR | READY | 6/8 | 1.0 | 89.8 |
| google/gemma-4-31b-it:free (OpenRouter) | **F** | 0.0 | – | – | ERR | ERR | ERR | ERR | INVALID: HTTP_400 | 0/8 | 0 | 0.7 |
| google/gemma-4-26b-a4b-it:free (OpenRouter) | **F** | 0.0 | – | – | ERR | ERR | ERR | ERR | INVALID: HTTP_400 | 0/8 | 0 | 0.9 |

Diagnoses (raw calls, five payload variants each):
- **Gemma-4 :free on OpenRouter** — every variant (as-is, no response_format, reasoning off, merged system role) returns the SAME upstream error from Google AI Studio: `API key not valid. Please pass a valid API key.` OpenRouter's free Gemma-4 route is broken on their side, not our payload. Both models ARE listed on Google AI Studio under the owner's own Gemini keys (`gemma-4-31b-it`, `gemma-4-26b-a4b-it`) — graded there directly in pass 4.
- **liquid/lfm-2.5-2.6b:free** — reasoning is MANDATORY on this endpoint (`reasoning: {enabled: false}` → 400 "cannot be disabled"). Under the production output budget (2,500) it spends all 2,500 tokens reasoning and returns empty content (finish=length, both chunks, both attempts). With max_tokens 10,000 it does produce valid contract JSON: 4,160 reasoning + 538 content tokens in 31 s — i.e. it needs a ≥8k output budget per chunk and ~3× the reference's latency. Enrichment (900-token envelope) worked: READY 6/8, gist 1.0. F under the production contract; a contract change, not a model fix.
- **qwen/qwen3.7-flash@none** — B again (0.766 vs 0.787 earlier; the usual run-to-run spread). Production canary with reasoning off: PASS in 70 s (section above).

## Pass 4 — Gemma-4 graded DIRECTLY on Google AI Studio (our gemini lane endpoint, owner's Gemini key)

| model | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | halluc A/B | envelope | per-chunk wall | total s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma-4-26b-a4b-it | **F** (enrichment) | 0.392 | **0.784** | 0.0 | 0.83/0.88 | 1.0/1.0 | 0.75/0.2 | 0.0/0.0 | INVALID: UNPARSEABLE | 13.3 s / 27.2 s | 59.8 |
| gemma-4-31b-it | **F** (enrichment) | 0.387 | **0.773** | 0.0 | 0.67/0.88 | 1.0/1.0 | 0.5/0.6 | 0.0/0.0 | INVALID: UNPARSEABLE | 16.8 s / 42.9 s | 85.3 |

Read this carefully: on EXTRACTION both Gemma-4 models beat the reference (0.784 / 0.773 vs mistral-small's 0.762) with ZERO hallucinated proposals and the best relation recall of any candidate. The F is enrichment, and it is structural: Gemma-4 always thinks first and Google does not allow it to be turned off for these models (`reasoning_effort: none`, `thinking_config`, native `thinkingBudget: 0` → 400 "Thinking budget is not supported for this model"; `includeThoughts: false` still returns a thought part). Through the OpenAI-compatible endpoint our client uses, that thought arrives INSIDE `content` as `<thought>…</thought>` and consumes the whole 900-token enrichment envelope (3,700–3,900 chars of thought, finish=length, no JSON). Extraction survived only because its 2,500 budget left room for the JSON after the thought — which is also why its per-chunk walls are 13–43 s (16–28 tok/s effective, the thought is invisible work). Through the native `generateContent` API the thought is a separate part (`thought: true`) that an adapter could drop.

Verdict: **HOLD — not wireable through the current client**. Becomes a serious extraction candidate the day a Google-native adapter (drop thought parts, keep the JSON part) exists; enrichment would additionally need a larger envelope or the same adapter. Pool is Google's free Gemma tier: per-model quotas, occasional 503s (one seen).

## Pass 5 — owner's second OpenRouter key (paid tier, no limit) on the free slugs

Same result as with the first key: `google/gemma-4-31b-it:free` and `gemma-4-26b-a4b-it:free` → HTTP 400 in < 1 s (Google upstream: "API key not valid" — OpenRouter's own Google credential for the free Gemma-4 route, not the owner's account); `liquid/lfm-2.5-2.6b:free` → UNPARSEABLE / ENRICH_EMPTY again (mandatory reasoning). The route is broken on OpenRouter's side regardless of which of our keys calls it. The second key is stored as `OPENROUTER_API_KEY_2` (production lanes still use `OPENROUTER_API_KEY`); it could back a second OpenRouter lane pair if more OpenRouter capacity is ever wanted.

## Pass 6 — owner pricing question: mistral-small-24b-2501, ministral-3b-2512, mistral-nemo

| model | list price in/out per M | grade | overall | extract | enrich | ent recall A/B | ent prec A/B | rel recall A/B | halluc A/B | envelope | terms | total s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistralai/mistral-small-24b-instruct-2501 | $0.05 / $0.08 | **A** | 0.83 | 0.705 | 0.956 | 0.5/0.75 | 1.0/1.0 | 0.38/0.7 | 0.0/0.13 | READY | 7/8 | 15.8 |
| mistralai/ministral-3b-2512 | $0.10 / $0.10 | **B** | 0.796 | 0.591 | 1.0 | 0.5/0.75 | 1.0/0.83 | 0.25/0.2 | 0.0/0.19 | READY | 8/8 | 8.8 |
| mistralai/mistral-nemo | $0.019 / $0.030 | **F** | 0.218 | 0.436 | 0.0 | 0.17/0.62 | 0.5/0.8 | 0.0/0.4 | 0.11/0.14 | INVALID: UNPARSEABLE | 0/8 | 77.8 |

Tokens per $1 at our measured extraction mix (~1,200 in : 600 out per call): mistral-small-2501 ≈ 16.7M tokens (≈ 9,300 calls, ≈ 50 five-hundred-KB books); ministral-3b ≈ 10M tokens (≈ 5,600 calls, ≈ 35 books); mistral-nemo ≈ 44M tokens (≈ 24,600 calls, ≈ 150 books). Price is not the constraint for this pipeline; latency and grounding are. mistral-nemo confirms its 2026-09-01 campaign result (1.0 f/1Kw, 2/8 answered, 32 s/call): 78 s for two chunks, half its entities off-key, enrichment unparseable. mistral-small-2501 passes cleanly (superseded in the pool by 2603, a valid fallback). ministral-3b is the surprise: 8/8 enrichment terms, gist 1.0, 8.8 s — a cheap enrichment-lane candidate pending the 8-chunk canary.

## Pass 7 — tool hardening: enrichment now graded on TWO parents packed in ONE microbatch (production shape)

Why: ministral-3b scored B here on a single 2-child parent, then failed 4/8 and 1/8 real parents in the canary. Two fixes: (1) a second, hard enrichment case (the 8-child OnStar parent, 1,052 tokens, 10 must-cover terms); (2) both parents go through ONE `compile_parents_microbatched` call so the compiler packs them the way the worker does (up to 8 parents per call under a 6,000-token ceiling, split ladder on envelope failure). One-parent-per-call had hidden the multi-parent envelope failure.

| model | grade | overall | enrich | envelope (easy / hard) | terms | total s |
|---|---|---|---|---|---|---|
| mistralai/mistral-small-2603 (reference) | **A** | 0.836 | 0.89 | READY / READY | 7/8 / 5/10 | 16.8 |
| mistralai/ministral-3b-2512 | **C** | 0.531 | 0.482 | **INVALID: ENRICH_NO_RESPONSE** / READY | 0/8 / 9/10 | 12.1 |

The grade now agrees with the canary's direction (ministral-3b: empty envelope on a multi-parent batch). It is still a 5-minute screen: the canary (8 chunks, 8 parents, 180 s) stays the gate before any lane is wired.
