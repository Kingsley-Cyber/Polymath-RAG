---
change_id: FAMILY-INTERLEAVE-V1 + OPENROUTER-LANES-V1
owner: governance
date: 2026-09-01
status: complete (live receipt below)
architecture_impact: shard ring order (pool.cloud_ring), provider roster (+2 lanes), enrichment pin (+2)
last_reviewed: 2026-09-01
---

# WORK LOG — FAMILY-INTERLEAVE-V1 + OPENROUTER-LANES-V1

## Contract
Owner: "bless interleave and wire the two openrouter lanes"
(2026-09-01), on the equivalence bench (pairwise fact agreement
0.01–0.10 across provider families) and the provider-pool campaign
(mistral-small-2603 and ministral-14b-2512 PASS both production
gates). Family-interleaved slices were the CONDITIONAL item of
EXTRACTION-FLEET-V3 — the condition is met.

## Changes
1. FAMILY-INTERLEAVE-V1 (pool.py): `interleave_by_family()` — smooth
   weighted round-robin over provider families (family = URL host, the
   same key the bench and the semantic-escape host rule use). The 8
   gemini lanes spread evenly; nvidia2, primary and the two openrouter
   lanes land at even intervals. `cloud_ring()` now returns this order,
   so every contiguous THROUGHPUT-V2 rank slice carries a family mix and
   the worker's round-robin over slice lanes sends consecutive batches
   of one document to different families. Pure function of config →
   RANK-STABILITY unchanged.
   Live ring (12): gemini1, gemini1b, openrouter1, gemini2, primary,
   gemini2b, gemini3, nvidia2, gemini3b, gemini4, openrouter2, gemini4b.
   Two-doc slices: {gemini, primary, openrouter} / {gemini, nvidia,
   openrouter}.
2. OPENROUTER-LANES-V1 (config only): `openrouter1` =
   mistralai/mistral-small-2603, `openrouter2` =
   mistralai/ministral-14b-2512; url `https://openrouter.ai/api` (client
   appends /v1/chat/completions); structured "schema"; ring members;
   both added to the parent_enrichment pin (now 7 lanes). Limiter seeds
   family `openrouter`, rpm 60 / tpm 500K / conc 4 (no published
   ceiling; header adoption grows them). Key = OPENROUTER_API_KEY in
   the gitignored .env only.
3. LANE-AUTH-QUARANTINE-V1 (llm_provider.py `_dispatch`; found by the
   first receipt run): a lane answering HTTP 401/403 is quarantined for
   the run (`_dead` set, one EXTRACTION_LANE_AUTH_DEAD log) and its
   batch escapes to the next live lane on a different host — the 413
   terminal-path pattern. Before: one openrouter 401 (stale key in the
   fleet's env snapshot) spent all 3 attempts and struck Blue Ocean's
   extract stage to FAILED. Auth failure is a lane property, never a
   document property.
4. TRANSPORT-FAILOVER-CROSS-HOST (llm_provider.py `_dispatch`; found by
   the retry of that same run): the transport failover picked
   `lane_i + n_lanes`, and a LONE document owns the whole ring
   (n_lanes == ring) — the pick wrapped onto the SAME lane, so one
   transient gemini 503 raised straight out and failed the attempt.
   Failover now walks the ring to the first live lane on a DIFFERENT
   host (the 413/401 pattern); a 5xx is a host condition.
5. EXTRACT-SCALE-OUT-V1 (fleet_autopilot.py): the autopilot woke ONE
   extract worker regardless of backlog — a GLiNER-era measurement
   ("workers don't scale") that llm_live cloud rank-slicing was built
   to invert. Live: Alchemy's extract sat `ready` while Blue Ocean's
   ran. Now one worker per open extract ticket, capped at 3
   (extract/extract2/extract3, all pre-existing slots). Count uses
   extract tickets only (the lane's demand also counts
   profile_document, which would have spawned extract2 for a lone doc).
6. RERANKER-DURING-INGEST-V1 (fleet_autopilot.py + rerank.py wording;
   found by the owner's "double check" pass): the autopilot only kept
   the reranker warm when there was NO extract demand — the GLiNER
   memory-ceiling rule — and `_await_reranker`'s no-wait shortcut only
   fired when GLiNER was resident. GLiNER is retired, so during any
   ingest the reranker was parked, no shortcut fired, and every query
   waited the full 90 s wake budget before degrading (measured 91–95 s
   per FAST/HYBRID query with the sidecar parked; the fail-fast breaker
   itself was verified at 0.02 s, so this was the wait, not the retry
   ladder). Fix: extract demand no longer excludes the reranker; only a
   resident GLiNER does; the budget gate still drops it first if a set
   does not fit (serve set = 15.75/18.5 GB). The extract lane's slot
   set also dropped sidecar_gliner/sidecar_spacy (retired with llm_live
   2026-08-30) — while they sat there, "gliner desired" was true during
   every ingest and would have kept blocking the reranker.
   Deployed 07:17Z (fleet bounce, no leases held). Post-deploy: first
   FAST query 27.1 s (autopilot woke the parked reranker 12 s after the
   query; ~15 s cold start), second 3.1 s, degraded=[] — wake-on-query
   restored; during-ingest behavior receipted with the 2-doc upload
   below.

## Proof
- tests/determinism/test_family_interleave.py — 5 green: permutation +
  deterministic under input order; every half-slice mixes >=2
  families; minority lanes never adjacent nor clumped at the tail;
  single-family ring degenerates to plain sort; family key = host.
- test_throughput_v2.py 12 green (10 prior + auth-quarantine: a 401
  family's batches all complete on other hosts, document never fails;
  + lone-doc 503 on the home family fails over to another host)
  + test_fleet_v3_limits.py 7 green on the interleaved ring (rank
  slices still disjoint; seeds parse).
- test_fleet_autopilot_demand.py 5 green (+ scale-out: 1 ticket → extract;
  2 → +extract2; 5 → capped at extract3).
- FULL determinism suite (owner: "double check your work"): 6 failures,
  all reproduced IDENTICALLY on a clean worktree at HEAD before today's
  edits — pre-existing, unrelated modules (killchain child-span gaps;
  sval doc01 predicate bindings ×3; test_llm_audit_fixes test_3 assumes
  a 300 KB cloud threshold while POLYMATH_CLOUD_MIN_BYTES=450000;
  test_llm_controller batched-client fake has a stale hook signature).
  Zero regressions from this change set; the six are logged as debt.
- Live roster probe: ring above; `_lane_limit` resolves both lanes
  (family openrouter); enrichment pin observed over 40 parents = 7
  lanes including openrouter1/2.
- OPS LESSON captured live: the first receipt upload ran on a fleet
  whose env snapshot predated the key swap — openrouter lanes were
  silently absent (pool skips lanes whose key env is missing). Fleet
  bounced onto the current .env after that run's extract completed;
  the acceptance receipt is the NEXT upload (filled in below).
- LIVE RECEIPT, interleave + lanes (Blue Ocean retry, fleet on the
  current key): one document's extraction served by mistral-small-2603
  (8 calls), ministral-14b-2512 (2), gemini-3.5-flash-lite (5),
  gemini-3.1-flash-lite (3) — three families on one doc; enrichment
  rows landed via openrouter1 (11) and openrouter2 (4) beside the
  gemini/nvidia pin.
- LIVE RECEIPT, EXTRACT-SCALE-OUT + RERANKER-DURING-INGEST (2-doc
  upload after the 07:17Z deploy — Netnography 43 KB + Psychology of
  Gambling 47 KB): supervisor log 07:19:36 "waking extract (extract:
  2 open)", 07:20:08 "waking extract2" — both extract tickets LEASED
  concurrently with TWO extract workers alive (extract + extract2); reranker listener stayed
  up throughout (same pid); FAST query during the extraction answered
  in 11.8 s with degraded=[] (vs 91–95 s degraded before the fix).

## Rejected claims
- Interleaving by lane NAME order — a name sort is exactly the
  family-block ring that produced the all-groq slice; the ring must be
  built from the family key.
- Round-robin across families (one lane per family per cycle) —
  front-loads all minorities into the first slice and leaves later
  slices single-family; SWRR spreads them.
- gpt-oss-20b via OpenRouter as a third lane — its provider lottery
  failed the production rule for extraction; it stays groq's escape
  candidate (not wired here).

## Open contract gaps
- 40-chunk equivalence pass with openrouter1/2 as bench families
  (canaries were 8-chunk) — run once traffic has produced receipts.
- Key rotation ops rule: a .env key change requires a fleet bounce
  (supervisor env snapshot); no automation yet — recorded.
- enrichment_batch_concurrency stays 5 with a 7-lane pin; raise after
  measuring the new lanes' sustained rate.
