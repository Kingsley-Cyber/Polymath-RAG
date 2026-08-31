---
change_id: CROSS-PROVIDER-FAILOVER-V1
owner: control-plane
date: 2026-08-30
status: complete
architecture_impact: fenced (pool ring selection, llm_provider failover pass) + registry swap (nvidia2<->groq5 roles)
last_reviewed: 2026-08-30
---

# WORK LOG — CROSS-PROVIDER-FAILOVER-V1 (lane swap + ring failover)

## Contract
Owner 2026-08-30: "they need error handling for jobs if a lane fails
its picked up etc. and i think switching 1 groq lane with 1 nvidia lane
is ideal for error handling. cross provider. ensuring the job is always
getting done."

## Changes
- CROSS-PROVIDER SWAP: `nvidia2` leaves the enrichment group and joins
  EXTRACTION sharding (model re-pinned to
  `nvidia/nemotron-3-super-120b-a12b` — lightning scored 0 entities on
  the extraction schema; super canaried 4 entities + 4 relations,
  sanitize ok). `groq5` becomes `dedicated:true` and joins the
  enrichment pin group: `parent_enrichment = ["nvidia", "groq5"]`.
  Result: BOTH stages survive a whole-provider outage — extraction has
  Groq+NVIDIA+local, enrichment has NVIDIA+Groq.
- LANE-FAILOVER-V1 (`_ring_pick`): endpoint selection is a
  deterministic RING — hash(doc) is the home lane, `ring_offset` walks
  forward, so attempt N of a doc always lands on the same Nth fallback
  (replay-stable). Extraction rings over non-dedicated lanes only;
  pinned stages ring WITHIN their group.
- Dispatch failover in `run_proposals` (cloud path): a batch whose home
  lane dies — `ExtractionTransportError` after the client's own
  retries, or a LIMITER_REFUSED (breaker open / Retry-After hold) — is
  retried ONCE on the ring_offset=1 client, logged + counted
  (`EXTRACTION_LANE_FAILOVER`), never silent. Ticket-level retry stays
  the outer loop; the gap this closes is a dead lane failing whole
  stages repeatedly because doc-hash re-picked the same endpoint every
  ticket attempt.

## Proof
- Sharding after swap (live): extraction 300 docs → groq1-4 + nvidia2 +
  primary (50/54/44/58/48/46), no dedicated leak; enrichment 100 docs →
  nvidia 50 / groq5 50.
- Ring: `primary->groq1` (extraction), `nvidia->groq5` (enrichment,
  cross-provider inside the group), stable on repeat.
- nvidia2 extraction canary (super-120b, reasoning none): sanitize ok,
  4 entities + 4 relations, 489 out tokens, 17.7 s.
- test_extraction_pool.py 16/16 (ring determinism, dedicated lanes
  excluded from the failover ring, group-internal failover); suite back
  at the 8-failure pre-existing baseline (one interim failure was the
  narrowed-test-double class again — make_client lambda without
  ring_offset — guarded, not test-edited).

## Rejected claims
- "Failover should try every lane until one succeeds" — rejected: one
  ring step per stage execution; unbounded walking under a provider-side
  incident turns one outage into N accounts of 429 storm. The ticket
  retry ladder provides the additional attempts with backoff.
- "Keep lightning on nvidia2 for extraction" — rejected on the measured
  0-entity canary; extraction quality gates lane membership.

## Open contract gaps
- Failover changes the serving model for that batch (cross-provider =
  cross-model); receipts/raw contracts record the actual model, so
  provenance holds, but corpus-level model mix now varies under
  incidents — visible in raw_evidence provider contracts.
- Enrichment failover (groq5 runs qwen3.8-27b, not nemotron): Phase B
  qualification must canary the enrichment schema on BOTH group members.
