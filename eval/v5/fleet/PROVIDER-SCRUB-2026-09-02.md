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
| groq1–5 | api.groq.com | qwen3.8-27b | GROQ_API_KEY_1–5 | PARKED (dedicated, no pin) |

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
| groq host (qwen3.8-27b, 5 keys) | host | **CUT from production; keep ONE key for the escape rep** | 8 K TPM ceiling + 32 % quarantine; gpt-oss-20b on groq is the only groq model that passed (escape-only) |
| local Qwen3.5-4B (MLX) | model@host | **DEMOTED (CLOUD-FIRST-V1 blessed, floor 0)** | 76 % quarantine on its only run today vs 0–5 % cloud; owner rule "≤300 KB never cloud" (2026-08-29) predates the free 12-lane cloud fleet — **owner decision** |
| mistral-nemo, ling-3.0-flash, llama-3.1-8b, granite ×2, lunaris, mythomax | model@host | **CUT** | campaign FAIL (capacity or capability) |
| gemma-3-4b-it @ OpenRouter | model@host | **HOLD** | 26.8 f/1Kw extraction but single provider + 0/8 enrichment; paced extraction-only lane if wanted |
| Qwen2.5-7B-Instruct @ SiliconFlow serverless | model@host | **DROP THE ENDPOINT** | decomposed 2026-09-02 (work-log 2026-09-02-siliconflow-decomposition): ~30 s queue before the first token on EVERY call, 16–18 tok/s, and degenerate output (token corruption, runs to the 2,500 cap) — the "150–158 s/call" was the endpoint, not the Mac, not our limiter, not the model |
| Qwen2.5-7B-Instruct @ OpenRouter (same weights) | model@host | **EVALUATE** (canary result in the work-log) | identical payload: TTFT 0.5 s, 52–55 tok/s, valid sane JSON in 4–10 s per call; the model stays in the pool evaluation |

## Owner decisions this scrub asks for
1. ~~Local-lane rule~~ — DECIDED 2026-09-02: CLOUD-FIRST-V1 blessed
   (floor 0; every document rides the cloud ring; local no longer
   size-selected). Receipts in work-log 2026-09-02-residuals-cloud-first.
2. Groq: reduce to one key (escape rep = gpt-oss-20b) or drop the host.
3. gemma-3-4b: wire as paced extraction-only lane, or leave out.
