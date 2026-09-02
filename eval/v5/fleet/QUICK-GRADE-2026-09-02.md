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
