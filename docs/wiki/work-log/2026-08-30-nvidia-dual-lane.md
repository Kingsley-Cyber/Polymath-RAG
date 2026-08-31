---
change_id: NVIDIA-DUAL-LANE-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: config (registry nvidia2 twin, limiter block, .env key 2) + pool stage-pin GROUPS; both NVIDIA accounts live
last_reviewed: 2026-08-30
---

# WORK LOG — NVIDIA-DUAL-LANE-V1 (two unlinked accounts, one pin group)

## Contract
Owner 2026-08-30: two separate NVIDIA accounts (bought with the two
business GPUs, unlinked, each with its own individual rate limit) —
"setup dual lanes… same model and config and they spawn and work and
churn through jobs."

## Changes
- `nvidia2` endpoint in config/cloud_providers.json: identical url /
  model (nemotron-3.5-lightning-30b-a3b) / quirks (reasoning "none",
  json), keyed by `NVIDIA_API_KEY_2` (owner-provided, gitignored .env).
- `stage_pins.parent_enrichment` = `["nvidia", "nvidia2"]` — stage_pin
  now returns a GROUP (single string stays a group of one; fully
  backward compatible). `select_endpoint_for_stage` shards the stage's
  docs deterministically (blake2b) across the group's ACTIVE members.
- Degradation semantics: one account dark → the other carries the whole
  stage, logged once ("reduced capacity"), never rerouted outside the
  group; ALL dark → PinnedProviderUnavailable (loud, unchanged).
- limiter.yaml `nvidia2:` block — its OWN rate bucket (36 RPM / conc 4
  seeds), because the accounts are unlinked: each AIMD lane climbs and
  backs off against its own provider edge. Combined enrichment
  capacity ≈ 72 RPM at seed.

## Proof
- Probe: all four endpoints OK (groq 318 ms, nvidia 442 ms, nvidia2
  8070 ms first-call cold start, primary 1594 ms) — second account
  auth verified live.
- 200-doc shard: nvidia 103 / nvidia2 97, deterministic on repeat.
- `_lane_limit("cloud","nvidia2")` seeds rpm 36 / conc 4 independently.
- test_extraction_pool.py 14/14 (new group test: both lanes churn,
  replay-stable, reduced-not-rerouted, all-dark raises); determinism
  suite at the 8-failure pre-existing baseline.

## Open contract gaps
- Both accounts share one Postgres AIMD state namespace keyed by
  limiter lane name — correct as long as endpoint names stay unique.
- nvidia2 cold-start latency (8 s first call) is provider-side; the
  enrichment worker's per-call timeout (180 s) absorbs it.
