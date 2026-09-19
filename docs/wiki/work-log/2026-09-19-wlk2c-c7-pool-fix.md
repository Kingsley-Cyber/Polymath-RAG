---
change_id: WLK2C-C7-POOL-FIX
owner: wildcard-investigation
date: 2026-09-19
status: complete
architecture_impact: "WLK2C C7 live-integration fix (orchestrator, MERGED to production; flag `POLYMATH_CHAT_LATENT_SELECTION` default-off). Found by the C7 causal probe: the latent pool was built from the JUDGED PREFIX, but BRIDGE-origin candidates rarely survive the doc-fair 32-seat prefix, so the pool never contained them (0 bridge candidates) → 0 latent seats. FIX: `chat_retrieval.py` builds the latent pool from the fused UNION filtered to a passed `latent_bridge_ids` set (bridge candidates included regardless of fused rank; falls back to subquery-retrieved-drops capped at 60 when no ids); `ui.py` passes the plan's BRIDGE subquery ids. RESULT: the full causal chain fires live (wc01: bridge br0 [FACS doc] → bridge_q0 +4.76 VALID → origin_chunk +2.21 → COMPLEMENTARY_ELIGIBLE → SEATED a facial-expression handbook chunk q0 dropped). KNOWN LIMIT: for abstract bridges run as low-K subqueries (wc07), the bridge subqueries contribute ZERO candidates to the q0-dominated union (WLK2A's bridge-PRIMARY surfaced 46; as a subquery, 0) → no latent seats — a bridge-candidate-reach / retrieval-depth issue, not a mechanism bug."
last_reviewed: 2026-09-19
---

## Contract
C7 live integration. The additive latent pass needs the bridge candidates that q0-only selection drops.
The plumbing must expose them without exploding the pool.

## Changes
- `orchestrator/orchestrator/api/chat_retrieval.py`: `chat_retrieve_v2` gains `latent_bridge_ids`; the
  `latent_pool` (flag-gated) is built from the fused `result.union` (best-first) minus `final`, keeping
  candidates whose `query_ids` intersect `latent_bridge_ids` (the bridge candidates — included regardless
  of fused rank, naturally bounded by what the bridges retrieved); when no ids are passed it falls back to
  any non-primary-subquery drop capped at `POLYMATH_LATENT_POOL_MAX` (60). Was: judged-prefix only (the bug).
- `orchestrator/orchestrator/api/ui.py`: the chat handler passes
  `latent_bridge_ids=(BRIDGE subquery ids)` to `chat_retrieve_mode`.
- Register row 11.326; this work-log.

## Proof
`LIVE_PATH_PROVEN` (in-process, deployed checkout). The causal probe (flags on, live sidecars + gemma)
shows the end-to-end chain for wc01: 2 grounded bridges generated (FACS/expression), bridge_q0 valid
(+4.76), a bridge candidate scored strong local (+2.21), C4 COMPLEMENTARY_ELIGIBLE, C5 seated it
COMPLEMENTARY (a handbook.html expression chunk) — evidence q0-only retrieval dropped. Rejects show
`local_subfloor` (the floor working). py_compile + preflight clean. Flag-off remains a strict no-op
(unchanged early returns).

## Rejected claims
- REJECTED the judged-prefix pool source (it structurally excludes bridge candidates). NOT a mechanism
  bug — C0–C5 unit-proven; this was a pool-plumbing bug caught only live.
- NOT claimed: broad coverage. wc07-class (abstract bridges) still gets 0 seats because the bridge
  SUBQUERIES surface no distinct union candidates — a retrieval-depth issue (owner decision below).

## Open contract gaps
`contract_impact` = orchestrator additive + flag-gated (off = no-op). Deferred / OWNER DECISION: bridge-
candidate REACH — abstract bridges as low-K B+C subqueries don't reach the q0-dominated union. Options:
(a) give BRIDGE subqueries a higher dedicated retrieval K; (b) expose the bridge subqueries' raw lane
hits (pre-fusion-truncation) into the latent pool; (c) accept v1 (helps where bridge candidates reach
the union, harmless otherwise). Then the qualification (WLK-10 + survival + main harness + CA5 64×4)
quantifies coverage. Intent classification is also non-deterministic run-to-run (APPLICATION vs
PROCEDURE) → the compiler sometimes skips bridges for a creative query (separate robustness note).
