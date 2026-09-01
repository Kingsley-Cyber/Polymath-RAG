---
change_id: FLEET-HARDENING-0901
owner: governance
date: 2026-09-01
status: complete
architecture_impact: extract_worker rank derivation; fixture hygiene (data purge, no code); provider ring membership (config only)
last_reviewed: 2026-09-01
---

# WORK LOG — FLEET-HARDENING-0901 (rank stability, zombie purge, groq ring parking)

## Contract
Owner directive "OK DELETE CORPUS AND RETEST EXTRACTION AND
ENRICHMENT SPEED" — the cold retest exposed three live defects that
THROUGHPUT-V2/FLEET-V3 testing had not: a rank race, fixture zombies
inflating the active-doc count, and a sorted-ring family block. All
three fixed under the standing "MAKE THIS PRODUCTION READY" order.

## Changes
1. RANK-STABILITY (ac0a128; capacity-seed edit landed as e91c5de —
   ac0a128's message overstated that part, recorded honestly): rank
   slicing derived active_rank/active_docs from the LEASED ticket set,
   which is observation-timing dependent — workers observing at
   different instants each concluded rank 0 → every doc drew the SAME
   lane slice → one-lane convoy → 429 storm → strike exhaustion.
   Rank now comes from the timing-stable OPEN set: tickets in
   (pending, ready, leased) of live (non-superseded) runs, ordered by
   ticket_id. Every worker computes the identical ordered list no
   matter when it looks.
2. GEMINI SEEDS TO DASHBOARD TRUTH (e91c5de): rpm 15 / tpm 250K /
   rpd 500 per lane — the owner's AI Studio dashboard is the quota
   ground truth, replacing my optimistic 2000-RPD seed.
3. ZOMBIE PURGE (data fix): 111 stage tickets + 13 runs from
   committed test fixtures (reconv-*, d7-h1-test) sat permanently
   open, inflating active_docs so real books got 1-lane slices.
   Purged live. DEBT RECORDED: determinism fixtures that commit rows
   must roll back — fixture hygiene is now a standing test-review
   item, not yet an enforced harness rule.
4. GROQ PARKED FROM THE EXTRACTION RING (3153ca3): groq's declared
   x-ratelimit-limit-tokens is 8000 TPM — under rank slicing a
   sorted ring handed one doc an ALL-groq slice (family-adjacent
   names), i.e. a doc whose whole slice cannot carry a real packet.
   groq* lanes now dedicated:true with no stage pin: reachable by
   escapes, never a slice member. Ring = 8 gemini variant lanes +
   nvidia2 + primary(ollama).

## Proof
- test_throughput_v2.py rank-slices-disjoint green against the OPEN-set
  derivation (suite re-run post-fix, 10/10).
- Live: post-fix cold retest ran 4 books on disjoint slices — extract
  done for all 4 (chain query_ready 05:13:08Z), zero 429 convoys in
  worker logs after the 05:02:35 reset; before the fix the same corpus
  struck out two books inside 10 minutes.
- Zombie purge receipt: open-ticket count for live runs dropped
  124 → 13 (the 13 = the real corpus tickets then in flight).

## Rejected claims
- "Buy more API keys" as the fix for the 429 storm — the storm was
  self-inflicted collision, not capacity. Rejected until granularity
  fixes proved out (they did).
- Keeping groq in-ring with a tiny char budget — a slice member that
  cannot carry a packet is dead weight even budgeted; parking is
  structural, budget was cosmetic.

## Open contract gaps
- Fixture-rollback enforcement (harness-level) — recorded debt, not
  built.
- Mid-run deploy discipline: two mid-run worker bounces each cost a
  book to stale-guard strike exhaustion before retry_failed_stage.py
  existed; rule of operation now "no deploys while a run is open"
  unless paired with a strike reset. Tooling exists; the discipline
  is procedural, not enforced.
