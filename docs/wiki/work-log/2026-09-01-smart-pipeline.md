---
change_id: SMART-PIPELINE-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: dispatch granularity (enrichment per-parent, extraction depth-aware), enrichment trigger point moves up the pipeline, fleet visibility endpoint + UI
last_reviewed: 2026-09-01
---

# WORK LOG — SMART-PIPELINE-V1 (churn, awareness, smart enrichment)

## Contract
Owner 2026-09-01: lanes "should churn through jobs essentially making
files extract quick", the control plane "should be aware of whats
happening whoses doing what, and how many jobs, and move smart", and
enrichment "should auto start in the pipeline and it should be
smart". Design reviewed WITH the owner before build ("is this the
right design?" → assessment → "i agree"): four pieces, with blind
round-robin extraction explicitly REJECTED in favor of depth-aware
spread, and a central scheduler brain explicitly NOT built (the
decentralized AIMD/ring/steal design has no single wedge point — and
this session saw twice what a wedged control tick costs).

## Changes
1. ENRICH-PARENT-SHARD (summary_worker_impl.py): the enrichment lane
   is chosen per PARENT (shard key parent_id, deterministic), not per
   document — all four pin-group lanes churn even on a one-document
   job. Thread width = SUM of the involved lanes' conc caps (each
   lane still self-gates through its own AIMD limiter). Enrichment
   identity (input_hash) and persist provenance now carry the
   parent's own lane. 429 ladder unchanged: backoff → same lane →
   the parent's ring-adjacent lane.
2. ENRICH-EARLY-KICK (scheduler.auto_enrich_on_chunks + control tick
   phase "auto_enrich_early"): the mint fires the tick a run's intake
   lands — parents exist then, and enrichment is post-hoc/additive
   (§0b), so it overlaps extraction and projection instead of waiting
   for promotion. FIRST-mint-only (NOT EXISTS guard: the mint re-arms
   on conflict, so sweeping ticket-holders would re-open finished
   work every tick). Promotion mint stays as backstop. PLUS the
   RESCUE clause: a 'ready'/'failed' enrichment ticket whose event
   was already consumed is unreachable forever — re-mint re-opens it
   (found live, see Proof).
3. FLEET-BOARD (api/fleet.py + FleetView.tsx + Fleet tab): GET /fleet
   aggregates the roster with roles, per-lane AIMD limiter state
   (effective/ceiling/↑/↓), live workers (status, processed, current
   ticket, heartbeat age), the ticket queue by stage×status, and
   enrichment coverage. Read-only: visibility, never scheduling
   authority.
4. EXTRACT-DEPTH-SPREAD (llm_provider.spread_decision + spread branch;
   extract_worker passes queue depth): WORK-CONSERVING dispatch — a
   deep queue keeps per-doc lane affinity (fleet saturated; one doc =
   one model keeps extraction style consistent); only when no other
   extract doc waits does a single document spread its batches
   round-robin across the shard ring. Unknown depth NEVER spreads
   (safe default = the frozen single-endpoint test shape; the call
   site keeps the TypeError guard for narrowed test doubles).

## Proof
- tests: test_auto_enrich_early.py (mint at intake-done mid-pipeline,
  first-mint-only, never before intake, rescue re-opens consumed
  events, DONE never re-armed) ×3 green; test_depth_spread.py
  decision table ×3 green; extraction pool + reconciliation suites
  green; all touched modules compile.
- LIVE FIND during rollout: the two tier_v3 runs' enrichment events
  were consumed by the earlier `_client` NameError crash-loop while
  their tickets sat 'ready' — a shape NOTHING healed (early sweep
  fires only when no ticket exists; the promotion backstop had
  already fired). The rescue clause closes it and is regression-
  pinned; applied live by the control tick after the bounce.
- Live receipts (fleet board + watcher): enrichment re-opened and
  compiled across the widened pin group post-fix; per-lane provenance
  visible in parent_enrichments.provider.

## Rejected claims
- "Round-robin extraction batches unconditionally" — rejected in the
  owner design review: it silently trades away per-doc model
  consistency even when the fleet is already saturated.
- "Build a central smart scheduler" — rejected: adds a single wedge
  point to a decentralized design that already moves smart.
- "BUNDLE_STALE_CODE_DRIFT during the build was a fence gap" — my
  own misread, corrected from code: it is the stale-PROCESS guard
  doing exactly its job (code changed on disk under a running
  worker); the remedy is a bounce, not an exemption.

## Open contract gaps
- The fleet board's failover counts are log-derived only
  (*_LANE_FAILOVER warnings); persisting per-lane failover counters
  would let the board show them — cosmetic, logs remain the receipt.
- Depth spread's queue signal is the extract ticket count at dispatch
  time (racy by a tick, fail-safe toward affinity).
