---
change_id: OPENROUTER-ENRICHMENT-LANES-V1 + ENRICHMENT-CONCURRENCY-SETTING
owner: governance
date: 2026-09-02
status: complete
architecture_impact: parent_enrichment pin +1 dedicated lane (9); WorkerSettings gains enrichment_batch_concurrency (declared; .env = pin size); third OpenRouter key
last_reviewed: 2026-09-02
---

# WORK LOG — enrichment lanes on the third OpenRouter key; the enrichment concurrency knob was dead

## Contract
Owner (2026-09-02): "add this key as a separate OpenRouter API key … they
both will be for enrichment lane since enrichment is slow" — the two picks
from the pricing question (ministral-3b-2512, mistral-small-24b-2501) as
enrichment-only lanes on a third key. Production rule: canary on that key
first; a lane that fails the enrichment floor is not wired.

## Changes
1. `.env`: OPENROUTER_API_KEY_3 (owner-supplied; pasted twice in the
   message, one key). Keys 1/2 unchanged.
2. `openrouter5` = mistralai/mistral-small-24b-instruct-2501, dedicated:true
   (enrichment pin only, excluded from extraction sharding), json, key 3;
   in `stage_pins.parent_enrichment` (now 9 lanes); limiter block family
   openrouter (rpm 60 / tpm 500k / conc 4).
3. `openrouter4` (ministral-3b-2512) NOT wired — see Proof.
4. ENRICHMENT-CONCURRENCY-SETTING: `summary_worker_impl` read
   `getattr(settings, "enrichment_batch_concurrency", 5)` but the field was
   never declared on WorkerSettings, so no env value could ever change it —
   with 8 lanes pinned only 5 batches were ever in flight. Declared
   (default 5, ge 1, le 32, env POLYMATH_WORKER_ENRICHMENT_BATCH_CONCURRENCY);
   `.env` sets 9 = the pin size. That, not more lanes alone, is the lever
   for "enrichment is slow".

## Proof
- Canary on key 3, json, 180 s: mistral-small-24b-2501 — extraction 8/8,
  24.7 facts/1Kw (equal to 2603), mean 10.2 s, 50 tok/s, 0 limiter wait;
  enrichment 8/8 READY, gist 1.00, 17.9–31.8 s per call; **PASS 121 s**.
- Canary on key 3, twice: ministral-3b-2512 — extraction 8/8 at 2.9–4.1 s
  and 212 tok/s but enrichment **4/8 then 1/8** (ENRICH_NO_RESPONSE ×3/×5,
  gists below floor ×1/×2). Capability, not capacity (no 429/5xx, two
  runs). The quick grade's single 2-child parent had passed it — the
  8-child parents of the canary did not. FAIL; not wired.
- Pool load after the edit: openrouter5 dedicated, absent from the
  extraction ring, present in the pin; live enrichment-style call through
  the pool's endpoint object answered clean JSON in 1.0 s.
- tests/determinism/test_enrichment_concurrency_setting.py 4 green
  (declared default 5; env sizes it; bounds; worker reads the field).
  Setting read back live: 9.

## Rejected claims
- Wiring ministral-3b on the strength of the 2-chunk grade — the grade's
  enrichment section uses one small parent and is optimistic; the canary
  is the production truth (recorded as a tool gap below).
- Raising concurrency above the pin size — batches beyond the lane count
  queue on the same lanes' AIMD limiters; nothing is gained.

## Open contract gaps
- ~~QUICK-MODEL-GRADE enrichment optimism~~ — CLOSED same day: second hard
  parent + both parents in one microbatch call; ministral-3b now grades C
  with ENRICH_NO_RESPONSE, matching the canary.
- Receipt run for openrouter5 on the next ingest (extraction_call_receipts
  will not show it — enrichment writes parent_enrichments; check the lane
  column there).
