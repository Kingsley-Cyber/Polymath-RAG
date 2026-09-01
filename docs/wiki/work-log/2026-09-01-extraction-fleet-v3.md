---
change_id: EXTRACTION-FLEET-V3
owner: governance
date: 2026-09-01
status: complete (equivalence bench running; tiering = owner gate)
architecture_impact: limiter (RPD, family circuit, ceiling adoption), dispatch (semantic escape, truncation split), receipts (accepted_count), bench
last_reviewed: 2026-09-01
---

# WORK LOG — EXTRACTION-FLEET-V3 (semantic health + capacity contracts)

## Contract
Owner-blessed 2026-09-01 (outside fleet review reconciled; owner
added: "does it handle individual provider and model rate limit,
where the api calls find each individual rate limit to optimize
speed?" → item 5). Five items: provider-equivalence bench, receipt
gate-status (PARSED ≠ ACCEPTED), provider-family circuit, family-
interleaved slices (CONDITIONAL on the bench), header-declared
ceiling adoption + RPD budgets.

## Changes
1. CEILING ADOPTION (limiter): when a provider's OWN headers declare
   x-ratelimit-limit-requests/-tokens ABOVE the configured seed, the
   bucket adopts theirs — grow-only, clamped to seed×4, persisted,
   restored. Zero probing: a 429 response carries these headers at
   exactly the moment the edge is found. Closes the owner's
   "find each individual limit" caveat #1.
2. RPD BUDGETS (limiter): `rpd` per lane (gemini* seeded 2000);
   acquire refuses once the UTC day's budget is spent (the ladder
   routes around), rolls at midnight, restores same-day across
   restarts. Caveat #2 closed.
3. PROVIDER-FAMILY CIRCUIT (limiter): lanes carry `family` (groq /
   gemini / nvidia in limiter.yaml); ≥8 failures across a family in
   30 s open a 45 s family cooldown, shared cross-process through the
   controller store, fail-open without one. A boolean gate with a
   cooldown — deliberately NOT a scheduler. Caveat #3 closed.
4. SEMANTIC ESCAPE (dispatch): a quarantined call (valid transport,
   unusable output) gets EXACTLY ONE retry on a different HOST — the
   enrichment hard-case pattern ported to extraction; keep whichever
   parses. Ordering fixed so output-truncation SPLITS before escape.
5. RECEIPT GATE-STATUS (migration 0045): receipts record
   accepted_count (packet proposal count) — PARSED ≠ ACCEPTED made
   queryable for replay policy and lane tiering; quarantines were
   never cached and never will be.
6. PROVIDER-EQUIVALENCE BENCH (eval/v5/fleet/provider_equivalence.py):
   same deterministic chunk sample, one representative lane per
   provider family, compared AFTER validate_and_normalize — accepted
   facts/entities per 1K words, quarantine/rejection rates, pairwise
   fact-agreement Jaccard. Tiering and family-interleaved slices are
   the OWNER's gate on its numbers.

## Proof
- test_fleet_v3_limits.py — 7 green: adoption grows/clamps/persists/
  restores; RPD refuses when spent, restores same-day, rolls at
  midnight; family gate opens on correlated failures, cools, damps
  sibling lanes' acquire, leaves other families and family-less lanes
  untouched.
- test_throughput_v2.py grown to 10 green: semantic escape exactly
  once and cross-host; truncation splits BEFORE escape (ordering
  pinned); prior 8 mechanics unchanged.
- LIVE receipt-replay receipt (from the V2 benchmark): 195 cached
  calls; after the V3-era bounce the two remaining books completed
  40–90 s later (replays + only the missing tail paid), and the
  strike-reset book finished <60 s after its reset.

## Rejected claims
- LiteLLM as control plane / Ray / Instructor as dependency — the
  review's own conclusion, adopted: patterns, not imports.
- PyrateLimiter in front of AIMD — already structurally present:
  limiter.yaml seeds ARE the deterministic ceilings; AIMD discovers
  the usable fraction inside them; adoption now raises them from
  provider-declared truth.
- Family-interleaved slices NOW — explicitly conditional on the
  equivalence bench showing meaningful model variance (the review's
  own caveat).

## Open contract gaps
- Equivalence bench results pending → owner tiering decision.
- Adoption reads limit headers only on paths that pass headers into
  the limiter (failure paths today — which is where they matter);
  plumbing success-path headers is a later nicety.
- The V2/V3 benchmark confirmed the review's downstream warning:
  extraction stopped being the bottleneck and ~50 min sat in
  canonicalize/compile/projection for 4 books — the NEXT throughput
  target lives downstream of extraction.
