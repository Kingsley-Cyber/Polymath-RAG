---
title: "WORK LOG — First corpus to VNEXT_COMPLETE: d7-h1-test end-to-end data-regen chain"
change_id: FIRST-VNEXT-COMPLETE-V1
date: 2026-09-08
owner: governance (data regeneration; migration readiness)
last_reviewed: 2026-09-08
last_touched: 2026-09-08
status: complete
register: 11.176
package: scripts/parent_map_backfill.py, scripts/backfill_document_profiles.py, scripts/profile_atom_canary.py, docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md
architecture_impact: "RETRIEVAL-MIGRATION-DEPENDENCY-V1 S12. `d7-h1-test` is the FIRST corpus driven through the entire data-regen chain to its terminal readiness verdict: parent-MAP backfill (78/78 eligible parents mapped, 0 unresolved) → vNext doc profiles (3/3 under POLYMATH_DOC_PROFILE_VNEXT=1) → Profile Atoms (30 across all 10 kinds, reconciled) → `semantic_completion('d7-h1-test').vnext` = VNEXT_COMPLETE. This proves the migration substrate reaches completion AUTONOMOUSLY (no owner gate, no paid fallback — sanctioned Groq map/profile lanes at trivial spend) and that the S11-proper verdict transitions INCOMPLETE→COMPLETE exactly at the §19 floor (unresolved==0 ∧ profiles==docs). It does NOT perform a cutover: serving-generation cutover (S13/S14) remains the owner's QUERY_READY flip (BE-AWARE §7). The real-corpus quality uplift (P10) still needs cinema (its fixtures) at coverage — a multi-session capacity campaign."
---

> **Ledger row:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12** (first corpus complete) + **S11** (verdict transition proven). The migration ledger's status table is the control point; this work-log is the evidence.

# WORK LOG — First corpus to VNEXT_COMPLETE

## Contract

Execute the FINAL-plan data-regen chain to completion on a real corpus, obeying the migration
ledger: coverage backfill → vNext profiles → full Profile Atom kinds → readiness verdict. Prove the
chain is autonomously completable and the S11-proper verdict fires correctly. Do NOT cut over
(owner-gated), do NOT add paid fallbacks (owner spend), keep every step resumable/idempotent.

`d7-h1-test` (3 docs, 78 eligible parents) was chosen because it is small enough to reach full
parent-MAP coverage within a single session's Groq capacity — unlike cinema (11,993 eligible
parents, a multi-session RPD-paced campaign). The plan is per-corpus, so one corpus completing is a
valid end-to-end demonstration of the mechanism.

## Changes (steps — exact commands + evidence)

1. **Capacity canary** (preflight before batch spend — silent-fallback accounting):
   `POLYMATH_GROQ_ROUTER=1 parent_map_backfill.py --corpus d7-h1-test --limit 1 --project` →
   mapped 26/26, complete, projected 26, 0 errors, 16.3s, lane_spread across 3 accounts
   (map_groq1/2/3) — the CONCURRENCY-SPREAD-V1 reservation working live. **PASS** ⇒ capacity available.
2. **Full parent-MAP backfill:** `... --corpus d7-h1-test --project` → 3/3 docs, 26/26 each =
   **78/78 mapped, 0 unresolved**, all projected. PASS.
3. **vNext doc profiles:** `backfill_document_profiles.py --corpus d7-h1-test` minted 3 tickets; the
   running supervised `profile_worker` (POLYMATH_DOC_PROFILE_VNEXT=1) generated **3/3 vNext
   profiles** (quality p50 0.823; relational surfaces present: seealso/theories/questions/concepts).
   One ticket's lease expired mid-call and requeued (attempt=0, no error) → re-leased → done; a
   latency blip, not a defect.
4. **Profile Atoms:** `profile_atom_canary.py --corpus d7-h1-test --project` → **30 atoms across all
   10 kinds** (3 each incl. the 5 relational kinds SEEALSO/BRIDGE/ANCHOR/TENSION/INVERSION),
   projected + **reconciled 30==30**.

## Proof

- **`semantic_completion('d7-h1-test').vnext` = VNEXT_COMPLETE** — `{verdict: VNEXT_COMPLETE,
  pending: [], parents: {eligible: 78, mapped: 78, excluded: 0, unresolved: 0}, vnext_profiles: 3,
  documents: 3}`. The first corpus to read COMPLETE; validates the S11-proper floor.
- Substrate is complete AND reconciled (atoms 30==30), so P5 fan-out (G) and P12 wildcard-over-atoms
  now have a fully-covered corpus to qualify against (atom→parent→child two-hop VALIDATES here,
  unlike the reverted S10 title-bridge ablation on uncovered cinema).

## Rejected claims

- **Not a cutover.** VNEXT_COMPLETE is the coverage PREREQUISITE for cutover, not the cutover. S13
  (QUERY_READY-requires-vNext blocking gate) and S14 (serve from vNext) remain the owner's
  QUERY_READY flip (BE-AWARE §7) — a production, hard-to-reverse control-plane decision not taken
  autonomously, on any corpus including this test one.
- **Not a real-corpus quality result.** d7-h1-test is a 3-doc synthetic test corpus with no P10
  fixture set. It proves the MECHANISM end-to-end; the quality UPLIFT (P10/P11/P13) needs cinema
  (which owns `chat_baseline_L/B.json`) at coverage — the multi-session capacity wall.
- **No paid fallback, no owner spend beyond the running campaign.** Maps used `groq/compound-mini`,
  profiles `groq/compound` — the same sanctioned lanes as the cinema campaign; ~12 routed calls total.

## Open contract gaps (unchanged, honestly gated)

- **cinema parent-MAP coverage:** 551/11,993 eligible parents; 11,074 unresolved. Resume
  `parent_map_backfill.py --corpus cinema --project --concurrency 6` as RPD capacity recovers
  (multi-session). This gates P10 uplift, P12 real value, and cinema's S14 cutover.
- **P12 Wildcard over atoms:** substrate now PROVEN complete on d7 (30 atoms/10 kinds). Still the
  lowest-value/highest-complexity routing slice; the atom→parent resolution (atoms are doc-scoped;
  `divergent_finish` needs parent-scoped `children_of`) is the design work. Exact-next documented in
  FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 P12. Deferred, not blocked.
- **S13/S14 cutover:** owner QUERY_READY flip (BE-AWARE §7). d7-h1-test now satisfies the
  VNEXT_COMPLETE prerequisite — the earliest corpus the owner could choose to cut over.
