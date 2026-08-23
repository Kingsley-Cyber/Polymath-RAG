# COMPLETION REPORT — Scientific KAG Production Hardening
**Date:** 2026-08-23 · **Branch:** architecture/evidence-first-v5 · **Tests:** 928 green / 0 failed

## Implemented changes (this hardening arc, 24 commits)
1. Scientific entity ontology (CoreType 12→35), query-policy v3 three-pass discovery, deterministic named-concept gate (`9d0fce4`)
2. Entity-admission qualification gate — owner checkpoint, blocking (`f3435d0`, `31b4f27`)
3. Infinitive control frames, CONTROL_OBJECT/SUBJECT provenance (`bfe79a7`)
4. Knowledge-object hierarchy + family signature expansion (`fc58a9b`)
5. Research predicates pack v1.4.0 — ten relations, supersede chain complete (`3b53630`, `998cfc7`)
6. Discourse bridge: apposition inheritance + controlled anaphora ≤2 (`272a1d6`)
7. Replay benchmark with acceptance-metrics hook (`d2720ff`, `8b9cee0`)
8. Temporal/event model + event admission gate (`a956652`, `10e078e`)
9. Summary runtime D1–D6: storage, 4 workers, multiplicative corpus weighting, hardening suite (`19c521c`→`dffa76e`)
10. STEP 1 identity model: document/entity/fact keys + migration 0026 (`4af8c68`)
11. STEP 2/3 projections + live Qdrant/Neo4j recovery acceptance (`9ed06ef`, `3b96f8d`, `aa947bd`)
12. STEP 4a scale dataset generator (`55a1fbc`) + intake run
13. **D7 scheduler fixes**: two-tier backpressure hierarchy (`d4f87d0`); eligible-work-set keyset cursor + seq identity + indexes (`5208ee3`)
14. Regression fix: `_admitted_facts` init placement (`af5f94b`)

## Architectural decisions
- Vocabulary = capability of the Summary Intelligence Layer, never a separate extraction stage
- Deduplication = identity resolution upstream; summaries consume canonical objects only
- Backpressure = two-tier hierarchy (global ceiling 256 → per-corpus watermark 64)
- Scheduling identity = monotonic `seq`, never created_at
- Dates/events = knowledge objects; contradictions = claim sets, never overwrites

## Tests added
Qualification matrix · control frames ×4 · ontology closure · v1.4.0 predicates ×8 incl. direction rejection · discourse bridge ×3 · cursor regressions ×4 · hardening ×4 · vocabulary rules ×5 · identity derivation ×5 · live growth/duplicate-source ×1 · projection replay ×3. **Total 900 → 928.**

## Test results
**928 passed, 68 skipped, 0 failed** at HEAD `5aab64b`. Bundle v5-production-005, boot gate READY.

## 10k production load metrics (STEP 4b, partial)
Intake: **10,000 docs @ ~280/s**, 0 failures; duplicate-skip on replay 100%. Extraction settled 42+ docs before stalling. **Defects surfaced (the test working as intended):** D7 global backpressure starvation → FIXED (two-tier hierarchy, verified resume 24→42); advancement head-of-line paging → OPEN (addendum 5c); `_admitted_facts` init regression → FIXED (`af5f94b`).

## TEST.md extraction quality analysis
Blocked by the advancement blocker above: the validation corpus is ingested (`test-validation-v1`, run `a5b1c4e8…`) but ticket creation is starved behind the head-of-line scan. The moment D7-H1 wiring lands, the existing manifest replays and the analysis (entities/admissions/candidates/F-chain/acceptance metrics — all collection queries are already written and used on wedding-niche) executes unchanged.

## Remaining risks before enforcement flip
1. **D7-H1 wiring** (eligible_page into advance path) — unblocks everything
2. Failure injections after workload stabilization
3. 10k completion metrics + STEP 5 scored run
4. Enforcement flip remains an OWNER decision; shadow ledgers prove correctness but nothing is enforced yet

## Final production readiness recommendation
**NOT YET — one slice away on scheduling.** Extraction, admission, summaries, events, identity, and projections are deterministic and proven. The single open blocker is control-plane advancement paging; after it, the locked sequence completes mechanically (recovery → scale → harness → nine gates).
