# PROVIDER + KEY SCRUB — 2026-09-02 (owner: "what models are actually worth keeping, and at which level")

Evidence window: last 30 h of production (ecom-meta-v1, 9 books), the
40-chunk equivalence bench (PROVIDER-EQUIVALENCE-RESULTS.md), and the
14-model canary campaign (work-log 2026-09-01-provider-pool-campaign).
Decision levels: **model@host** (keep/cut one lane), **host** (keep/cut a
provider account), **key** (a specific API key).

## Inventory (config/cloud_providers.json + limiter.yaml)
| lane(s) | host | model | keys | role |
|---|---|---|---|---|
| gemini1–4, 1b–4b | generativelanguage.googleapis.com | 3.1-flash-lite + 3.5-flash-lite | GEMINI_API_KEY_1–4 | extraction ring (8) |
| gemini5/5b/6/6b | same | same | GEMINI_API_KEY_5–6 | enrichment pin (4) |
| nvidia2 | integrate.api.nvidia.com | nemotron-3-super-120b | NVIDIA_API_KEY_2 | ring |
| nvidia | same | nemotron-3.5-lightning-30b | NVIDIA_API_KEY | enrichment pin |
| openrouter1/2 | openrouter.ai | mistral-small-2603 / ministral-14b-2512 | OPENROUTER_API_KEY | ring + pin |
| primary | 127.0.0.1:11434 (ollama cloud) | qwen3.5:397b-cloud | — | ring |
| local | MLX sidecar | Qwen3.5-4B-MLX-4bit | — | ALL docs ≤ cloud_min_bytes |
| ~~groq1–5~~ | api.groq.com | qwen3.8-27b | ~~GROQ_API_KEY_1–5~~ | REMOVED (owner 2026-09-02): lanes, limiter blocks, keys and AIMD rows deleted |

## Evidence
**Extraction, per run today (artifact stats):** every cloud-lane run: 0–2
quarantined calls, 0–1 dropped neighborhoods (e.g. Blue Ocean 33 calls /
0 / 0; Alchemy 41 / 2 / 1). The one LOCAL-lane run (Netnography, 43 KB):
17 calls, **13 quarantined, 6 of 10 neighborhoods dropped** → held back by
the coverage barrier. Bench density (facts/1Kw): qwen3.5-397b 28.6 ·
mistral-small-2603 23.7–25.7 · ministral-14b 23.7 · groq qwen3.8 19.6 (13/40
quarantined) · nvidia nemotron 16.3 (28.8 s/call) · gemini-3.1-flash-lite
12.1 (3.9 s/call). Pairwise fact agreement 0.01–0.10 → families are
complementary, not interchangeable (interleave is live).

**Enrichment, per parent (latest row, 30 h):** gemini5/5b/6/6b 100 % READY
(190–197 parents each, gist 0.95–0.97); openrouter1 136/136 and
openrouter2 112/112 at gist 0.98 with ZERO transient failures; nvidia
172/173 (one typed hard case). All seven lanes reliable; differentiators
are speed, quota and first-pass cleanliness.

**Receipt `accepted_count`:** 0 on all 495 receipts today — the metric is
dead (summed packet fields that do not exist under those names); FIXED
this session (RECEIPT-ACCEPTED-COUNT-FIX, 13 tests green) — receipts from
the next worker spawn onward carry proposal counts. Tiering below therefore uses bench + artifact stats, not
receipts.

## Verdicts (level → decision)
| target | level | verdict | why |
|---|---|---|---|
| qwen3.5-397b via ollama cloud | model@host | **KEEP, weight up** | top density, 0 waste, 5 s |
| mistral-small-2603 @ OpenRouter | model@host | **KEEP** | top-3 density, fastest quality lane, 100 % enrich, multi-provider pool |
| ministral-14b-2512 @ OpenRouter | model@host | **KEEP** | strong both contracts, first-party Mistral endpoints |
| OpenRouter as a host | host | **KEEP (this key)** | judged per model pool; slugs with 1 provider (gemma-3-4b, mistral-small-2501, granite) stay out |
| gemini flash-lites (both) | model@host | **KEEP as bulk/speed carrier** | free, 15 RPM × 12 lanes, thinnest extraction — never the quality anchor |
| gemini non-lite flashes, 2.5 family | model@host | **CUT (already out)** | schema FAIL / 20 RPD / retired |
| GEMINI keys 1–6 | key | **KEEP all six** | each key = 2 lanes × 500 RPD; capacity, not quality |
| nvidia nemotron-3-super-120b (ring) | model@host | **KEEP, overflow tier** | clean but 28.8 s/call |
| nvidia nemotron-3.5-lightning (pin) | model@host | **KEEP** | 99 % READY enrichment |
| groq host (qwen3.8-27b, 5 keys) | host | **OUT (owner 2026-09-02)** | 8 K TPM ceiling + 32 % quarantine; the gpt-oss-20b escape rep goes with it — no groq key remains |
| local Qwen3.5-4B (MLX) | model@host | **DEMOTED (CLOUD-FIRST-V1 blessed, floor 0)** | 76 % quarantine on its only run today vs 0–5 % cloud; owner rule "≤300 KB never cloud" (2026-08-29) predates the free 12-lane cloud fleet — **owner decision** |
| mistral-nemo, ling-3.0-flash, llama-3.1-8b, granite ×2, lunaris, mythomax | model@host | **CUT** | campaign FAIL (capacity or capability) |
| gemma-3-4b-it @ OpenRouter | model@host | **OUT (owner 2026-09-02)** | 26.8 f/1Kw extraction but single provider + 0/8 enrichment; owner declined the paced extraction-only lane — never wired |
| Qwen2.5-7B-Instruct @ SiliconFlow serverless | model@host | **OUT (owner 2026-09-02)** | decomposed (work-log 2026-09-02-siliconflow-decomposition): ~30 s queue before the first token on every call, 16–18 tok/s, degenerate output to the 2,500 cap — the endpoint, not the Mac, not our limiter, not the model. Key removed from .env (no consumer) |
| Qwen2.5-7B-Instruct @ OpenRouter (same weights) | model | **OUT (owner 2026-09-02)** | passes the format gate (canary PASS, 8/8, 97 s) but the A/B vs mistral-small-2603 on the same chunks: half the facts, a third–half of the entities, rejections dominated by fabricated grounding (UNATTESTED_RELATION_QUOTE 32 / ENDPOINT 19), zero Person entities, 4 predicate types, 2× run-to-run swing at temp 0 on a single-provider pool (Phala), slower per kept fact. Never wired; removed from evaluation |
| meta-llama/llama-3.1-8b-instruct @ OpenRouter | model@host | **OUT (owner 2026-09-02, "remove all failures")** | quick grade F: 44–50 % hallucinated proposals, no relations on chunk B, enrichment envelope EMPTY (matches the 09-01 campaign) |
| ibm-granite/granite-4.1-8b @ OpenRouter | model@host | **OUT (owner 2026-09-02)** | quick grade F: recall 0.5/0.25, zero relations, 38–68 % hallucination, gists below floor |
| inclusionai/ling-3.0-flash @ OpenRouter | model@host | **OUT (owner 2026-09-02)** | quick grade F: upstream 429 on 6/7 calls across two passes; the one answer took 130 s (reasoning model, ≈19 tok/s) |
| thinkingmachines/inkling-small:free @ OpenRouter | model@host | **OUT (owner 2026-09-02)** | HTTP 403 "only available on agentic harnesses" — not an API model on this key |
| qwen/qwen3.7-flash @ OpenRouter | model@host | **WIRED 2026-09-02 as openrouter3 (ring + enrichment pin), reasoning OFF mandatory** | canary PASS 70 s (8/8 extraction 5.3 s mean, 103–130 tok/s; enrichment 8/8 gist 1.00; facts 15.4/1Kw); on the owner's second OpenRouter key; structured json; single provider (Alibaba). Receipt run pending |
| ibm-granite/granite-4.0-h-micro @ OpenRouter | model@host | **HOLD — enrichment-only curiosity (quick grade B)** | enrichment READY 7/8 gist 1.0 at $0.02/$0.11; extraction too weak; 57 s on a single provider |
| mistralai/mistral-nemo @ OpenRouter | model@host | **OUT (confirmed twice)** | 09-01 canary: 1.0 f/1Kw, 2/8 answered, 32 s/call; 09-02 quick grade F 0.218: 78 s for two chunks, entity precision 0.5/0.8, enrichment unparseable. Cheapest list price ($0.019/$0.030) and it does not matter |
| mistralai/mistral-small-24b-instruct-2501 @ OpenRouter | model@host | **WIRED 2026-09-02 as openrouter5 — enrichment pin only (dedicated), third key** | canary on key 3: extraction 8/8 at 24.7 f/1Kw, enrichment 8/8 gist 1.00, PASS 121 s; quick grade A 0.83. $0.05/$0.08 |
| mistralai/ministral-3b-2512 @ OpenRouter | model@host | **OUT — enrichment fails on real parents** | canary on key 3 twice: extraction 8/8 (212 tok/s!) but enrichment 4/8 then 1/8 (ENRICH_NO_RESPONSE, gists below floor). The quick grade's B (one 2-child parent) was a false positive of the smoke test. Not wired |
| liquid/lfm-2.5-2.6b:free @ OpenRouter | model@host | **OUT (quick grade F)** | reasoning mandatory and cannot be disabled; empties the 2,500 output budget on reasoning; only answers with ≥8k max_tokens (31 s/chunk). Contract mismatch |
| google/gemma-4-31b-it:free, gemma-4-26b-a4b-it:free @ OpenRouter | host route | **BROKEN UPSTREAM (HTTP 400 "API key not valid" from Google via OpenRouter)** | not the models — both are live on Google AI Studio under our Gemini keys; graded there directly (QUICK-GRADE-2026-09-02.md pass 4) |
| gemma-4-26b-a4b-it, gemma-4-31b-it @ Google AI Studio (direct, our Gemini keys) | model@host | **HOLD — best extraction measured, enrichment structurally blocked** | extraction score 0.784 / 0.773 (> reference 0.762), 0 % hallucination, relation recall up to 0.75; but Gemma-4 thinking cannot be disabled on Google and the compat endpoint inlines `<thought>…</thought>` into content, eating the 900-token enrichment envelope (UNPARSEABLE both models). Needs a Google-native adapter that drops thought parts. 13–43 s per chunk today |

## Owner decisions this scrub asks for
1. ~~Local-lane rule~~ — DECIDED 2026-09-02: CLOUD-FIRST-V1 blessed
   (floor 0; every document rides the cloud ring; local no longer
   size-selected). Receipts in work-log 2026-09-02-residuals-cloud-first.
2. ~~Groq: reduce to one key (escape rep = gpt-oss-20b) or drop the host.~~ DECIDED 2026-09-02: host REMOVED.
3. ~~gemma-3-4b: wire as paced extraction-only lane, or leave out.~~ DECIDED 2026-09-02: REMOVED.
