---
change_id: OPENROUTER-LANE-3
owner: governance
date: 2026-09-02
status: complete
architecture_impact: extraction ring +1 lane (13), parent_enrichment pin +1 (8); second OpenRouter key in .env
last_reviewed: 2026-09-02
---

# WORK LOG — OPENROUTER-LANE-3: qwen/qwen3.7-flash (reasoning off) wired

## Contract
Owner (2026-09-02): "which ones work well and should be wired." Of every
candidate graded today, one cleared the production gates on the
production client path: qwen/qwen3.7-flash with thinking turned off.
Wire it; keep the rest out or on HOLD with their reasons on record.

## Changes
1. `config/cloud_providers.json`: provider `openrouter3` — model
   qwen/qwen3.7-flash, url https://openrouter.ai/api, api_key_env
   OPENROUTER_API_KEY_2 (the owner's second OpenRouter key: separate
   account, separate limits), `reasoning_effort: "none"` (MANDATORY — a
   reasoning model that otherwise spends its entire output budget on
   reasoning tokens and returns empty content), structured `json` (strict
   schema not canaried), dedicated false, request_char_budget 100000.
   Added to `stage_pins.parent_enrichment` (now 8 lanes).
2. `config/extraction_models/limiter.yaml`: `openrouter3` block, family
   openrouter, rpm 60 / tpm 500000 / conc 4 (seeded like openrouter1; its
   own account = its own bucket).
3. `.env`: OPENROUTER_API_KEY_2 (owner-supplied 2026-09-02). Production
   lanes openrouter1/2 keep OPENROUTER_API_KEY.

## Proof
- Canary (production client, json mode, CANARY_REASONING=none, 8 chunks
  + 8 parents, 180 s budget): extraction 8/8, walls 3.1–9.4 s (mean
  5.3 s), 103–130 output tok/s, limiter wait 0, finish=stop ×8, one nudge
  retry; facts 15.4/1Kw, entities 50.5/1Kw; enrichment 8/8 READY, gist
  1.00 (12.6–21.8 s per call). VERDICT PASS, total 70 s.
- Quick grade (answer-keyed): B 0.766–0.787 with thinking off; F as-is
  (2,500 reasoning tokens, empty content).
- Pool load after the edit: openrouter3 present with reasoning_effort
  none, in the ring and in the enrichment pin; live extract + enrichment-
  style call through the pool's own endpoint object (receipt in the
  commit's terminal output). Pool / interleave / throughput tests 34 green.
- Not yet: a receipt run (a real document through the pipeline). The lane
  takes its interleaved share of the next ingest; extraction_call_receipts
  will show `openrouter3` calls. Watch the first ones.

## Why the others were NOT wired
- Gemma-4 (26b-a4b, 31b) direct on Google: best extraction measured
  (0.784/0.773, 0 hallucination) but thinking cannot be disabled and the
  compat endpoint inlines `<thought>` into content — enrichment is
  structurally unparseable, extraction pays 13–43 s per chunk. HOLD for a
  Google-native adapter.
- granite-4.0-h-micro: enrichment READY but extraction weak and 57 s per
  pass; the pin already has 8 faster lanes.
- Qwen2.5-7B, gemma-3-4b, llama-3.1-8b, granite-4.1-8b, ling-3.0-flash,
  inkling-small:free, lfm-2.5-2.6b:free: removed by the owner today, each
  with a measured reason in PROVIDER-SCRUB-2026-09-02.md.

## Rejected claims
- Wiring qwen3.7-flash with `structured: schema` — never canaried in
  schema mode; json passed. Schema can be canaried later.
- Putting the new key on the existing lanes instead — a second account is
  independent capacity; splitting lanes across accounts is the point.

## Open contract gaps
- Receipt run pending (first live ingest on the 13-lane ring).
- Single provider behind the slug (Alibaba): one throttle from a storm;
  the interleave and cross-host failover contain it to one lane.
