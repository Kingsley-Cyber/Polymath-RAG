---
change_id: LATENT-QUERY-FUSION-V2-F4
owner: wildcard-investigation
date: 2026-09-19
status: in_progress
architecture_impact: "LATENT-QUERY-FUSION-V2 F4 — live cutover + A/B qualification (owner-authorized 2026-09-19). Step 1 (orchestrator provenance wiring): `ui.py` carries the plan's EXISTING per-query origin into the subquery spec (now a 5-tuple id/type/text/weight/origin); `chat_retrieval.py` pads legacy 4-tuples, threads origin into `SubQuery.origin` → the RankedLane lineage class. No inference/new roles. Live-only (orchestrator resolves to MAIN under the editable-.pth); proven from receipts at step 4. Steps 2–7 (merge + port-gated bounce + flag-off smoke + targeted wc01/05/07 seam proof + A/B vs WLK2C V1 vs pre-WLK2C + calibration + one CA5 64×4) recorded here as they complete."
last_reviewed: 2026-09-19
---

## Contract
F4 turns the F1–F3 structural correction into live librarian behavior and qualifies it. Owner order
(2026-09-19): (1) wire orchestrator provenance from EXISTING plan origin only; (2) merge + controlled
port-gated bounce; (3) flag-off live identity smoke; (4) enable V2 + prove the runtime path from
receipts on wc01/wc05/wc07 BEFORE spend (record the Laban-style expert's V1 vs V2 survival through
local-rank → judged-prefix → C4 → C5 → CA4); (5) A/B (pre-WLK2C vs V1 vs V2) on WLK-10 + 4-mode
survival + main harness; (6) calibrate lane weights + preserve_top_n from A/B data only (never global K,
never to wc01/05/07, must generalize + config-driven); (7) one full CA5 64×4 if V2 is materially
healthier and safe. Acceptance: the improvement must actually become behavior (a subquery/bridge's
genuine local winner survives premature truncation, lineage intact, C4 validates, C5 seats only when
useful, q0 stays primary) AND CA5 stays healthy (unsupported hallucination 0, q0_preserved 1,
provenance_complete 1, no material named-source / success@10 regression, all CA cases intact).

## Changes
- STEP 1 (orchestrator provenance, live-only):
  - `orchestrator/orchestrator/api/ui.py`: the v2 subquery spec is now
    `(q.id, q.type, q.query, q.weight, getattr(q, "origin", ""))` — the plan's existing origin
    (USER/PROFILE/GRAPH/BRIDGE/WILDCARD), no inference.
  - `orchestrator/orchestrator/api/chat_retrieval.py`: `sub_specs` padded to 5 fields (legacy 4-tuples
    → origin ""); the three unpack sites take the 5th field; `SubQuery(..., origin=str(sorigin or ""))`.
  - q0 origin is not carried as a subquery (it is PRIMARY); the engine's F1 capture already tags the
    primary lane origin=USER/role=q0.
- STEPS 2–7: appended below as executed.

## Proof
STEP 1 = `IMPLEMENTED` (live-only; orchestrator resolves to MAIN under pytest, so not worktree-unit-
testable). The shared half — `SubQuery.origin` → RankedLane lineage class → fusion weight — is already
WORKTREE_INTEGRATION_PROVEN (F3, `test_subquery_origin_flows_into_lane_provenance`). Live receipt proof
of q0→USER / subquery→origin / BRIDGE→BRIDGE / WILDCARD→WILDCARD is STEP 4 (before any A/B spend).

STEP 2 (merge + bounce) — DONE. Merged `fusion/latent-query` (`0a6b1b2`) → production `ae10f5a`
(no-ff, clean; only overlapping file was none). 124 impacted+V2 determinism tests green on the merged
checkout (the orchestrator wiring, unprovable in the worktree, validated at MAIN). `bundle_integrity
--strict` READY on merged code. Port-gated bounce (SIGTERM supervisor → ports 7200/8742/8743/8755 free
→ boot autopilot): fleet back **10 worker types healthy, ONE bundle `7694e627a7bb`** (was
`0702df186a4b` → confirms the fleet runs the merged lineage), `/ready` true, embedder+reranker up.

STEP 3 (flag-off smoke) — DONE. `POLYMATH_CHAT_LATENT_FUSION=0`: wc01/05/07 in-process retrieval →
`has_ranked_lanes=false` (V2 receipt absent), 15 evidence each, deep families where expected (wc01
Facial Action, wc07 Laban Workbook). Flag-off is a live no-op; the deploy did not break retrieval.

STEP 4 (targeted seam proof, BEFORE spend) — DONE, wiring HEALTHY. Full in-process path on wc01/05/07
(V2 vs V1), 5-tuple origin + latent_bridge_ids, live sidecars + gemma. Proven:
- **origin flows live**: lanes carry BRIDGE/PROFILE/USER (step-1 wiring works).
- **wc01 = full-chain proof**: `br0` (BRIDGE) ranks *Facial Action coding 3.0* at LOCAL RANK 0 → V2
  preserves it → latent pool → **C5 COMPLEMENTARY seat** → **CA4 RELATED** → reaches FINAL evidence
  (absent from the plain retrieval evidence). The bridge's local winner became librarian behavior.
- **wc07**: `q1` (USER subquery) ranks Laban docs at local rank 0/1/2; under V2 Laban reaches FINAL
  evidence, under V1 (one run) it did not — SUGGESTIVE but confounded by retrieval non-determinism.
- **wc05**: deep family (*Timing*) is local-rank-0 in the PROFILE lane but dies at the reranker
  (sub-floor relevance), NOT a preservation break (matches WLK2B).
Gate PASSED: neither origin population nor lane preservation is broken. Caveat recorded: single-run
per-query traces are noisy (non-deterministic retrieval); the A/B aggregates to compensate.

STEP 5 (A/B pre-WLK2C / V1 / V2) — IN PROGRESS. Full-path deep-survival harness (all 10 WLK queries ×
3 flag conditions, end-to-end retrieval→C4/C5→CA4) measuring deep lane-winner / retrieval reach /
latent-seat / FINAL reach / q0 preservation / latency; plus the owner-named `harness.py` (WLK-10) and
4-mode survival, run sequentially (Metal GPU is shared — no parallel rerank). Results appended here.
<!-- STEP 6 calibration (from A/B only, generalizing, config-driven): TBD -->
<!-- STEP 7 CA5 64×4: TBD -->

## Rejected claims
- STEP 1 does NOT infer or invent roles; it carries the plan's existing origin only.
- NOT proven live yet — no A/B, no bounce at step 1. No calibration until A/B data (step 6).

## Open contract gaps
`contract_impact` — CHAT_RETRIEVAL (orchestrator) gains an additive origin field on the subquery spec;
default-off flag path unchanged (the v2 subqueries are only built when `_flag==on and _rflag==v2`, and
`SubQuery.origin` only affects fusion when `POLYMATH_CHAT_LATENT_FUSION=1`). CANDIDATE_ENGINE selection
change is F3 (11.330). Full live disposition (ACCEPTANCE / RETRIEVAL_RECEIPT / CA5 safety) resolves at
steps 4–7 below.
