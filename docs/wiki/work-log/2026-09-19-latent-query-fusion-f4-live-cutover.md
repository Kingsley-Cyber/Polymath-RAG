---
change_id: LATENT-QUERY-FUSION-V2-F4
owner: wildcard-investigation
date: 2026-09-19
status: complete
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
`LIVE_PATH_PROVEN` + **QUALIFIED**. Steps 1–7 complete (details above): merged+bounced (fleet on new
bundle), flag-off live no-op, step-4 seam proof (origin flows + wc01 full chain), A/B (V2 materially
healthier, 3 repeats), config-driven no-tuning, CA5 subset gate CLEAN (0 flags, all invariants hold).
V2 is LIVE (`.env` FUSION+SELECTION+BRIDGE=1). Orchestrator edits were not worktree-unit-testable
(editable-.pth → MAIN); they were validated on the merged checkout (124 tests) + proven live.

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
STEP 5 (A/B) — RESULT: V2 materially healthier than V1. 10 WLK queries × 3 conditions × **3 repeats**
(retrieval non-determinism ⇒ single runs are noisy; aggregated). Means:
- deep_final_reach (end-to-end): pre 0.433 / V1 0.467 / **V2 0.667** — V2 ≥ V1 in ALL 3 runs
  (V2 [.6,.5,.9] vs V1 [.5,.5,.4]); +0.20 over V1.
- deep_retrieval_reach: pre 0.433 / V1 0.467 / **V2 0.600** (V2 ≥ V1 every run) — the candidate-engine
  preservation lifts reach, not only the latent seat.
- deep_latent_seated_rate: V2 0.067 (a deep family C5-seated that V1 never seats).
- q0_preservation: V1 0.983 / **V2 0.990** (no extra q0 cost; both < pre 1.0 from the additive latent pass).
- latency_ms: V1 15214 / **V2 12896** (faster; no regression).
Per-query pattern is churny (non-determinism) but the DIRECTION is consistent (V2 ≥ V1 both reach
metrics, every run). Combined with the step-4 mechanism proof ⇒ material, generalizing improvement.

STEP 6 (calibration) — DECISION: **do NOT tune.** The F2 defaults (weights 1.0/0.6/0.5/0.6/0.5/0.4,
preserve_top_n 5) already deliver the gain and are UNFITTED — tuning to these 10 queries is forbidden
(owner) and would not generalize. Made the values CONFIG-DRIVEN so future adjustment needs no code:
`FusionWeights.from_env()` (`POLYMATH_FUSION_W_<CLASS>`) + `POLYMATH_FUSION_PRESERVE_TOP_N`, all
defaulting to the validated values. Global K untouched. UNIT_PROVEN (`test_fusion_weights_from_env` +
60 fusion/seam/engine tests green); deployed at the step-7 bounce.
STEP 7 (CA5 safety gate) — PASSED. Owner scoped it down ("15-20 questions is good enough"): a
STRATIFIED 18-query subset (`gold_subset_f4_ca5.json` — all 4 unsupported + named-source/pmap/multi-
source/sensitivity/definition/relational/profile/low-lexical/distractor) × 4 modes = 72 live
`/chat/stream` turns through V2 (flags on). Result (`CA5-V2-FUSION-cinema-2026-09-19-subset.summary.json`):
every mode FAST/HYBRID/GRAPH/WILDCARD → **success@10 1.0, single-target MRR 1.0 (n=4), unsupported
hallucination 0.0, declined 1.0, q0_preserved 1.0, provenance_complete 1.0, 0 errors, FLAGS(0), 0 gold
misses, per-category success@10 1.0 across all 11**. The A/B's chunk-level q0 0.990 resolves to
ANSWER-level q0_preserved 1.0 (no regression). Subset (not the full 64) per owner scope; the invariants
are absolute and hold. resolution_trigger (the known 0.25 P10 limitation) is untouched by V2 and out of
this subset.

## VERDICT — V2 QUALIFIED (live, flags on)
The structural correction became librarian behavior AND the system stayed CA5-safe:
subquery/bridge local competition (ranked lanes) → genuine winner survives premature truncation
(A/B deep_final_reach 0.667 vs V1 0.467; wc01 FACS bridge local-rank-0 preserved) → lineage intact
(many-to-one contributions) → C4 validates (wc01 COMPLEMENTARY_ELIGIBLE) → C5 seats only when useful
(deep_latent_seated 0.067, selective) → q0 stays primary (CA5 q0_preserved 1.0). V2 remains LIVE.

## Rejected claims
- STEP 1 does NOT infer or invent roles; it carries the plan's existing origin only.
- NOT proven live yet — no A/B, no bounce at step 1. No calibration until A/B data (step 6).

## Open contract gaps
None blocking. Dispositions: CHAT_RETRIEVAL (orchestrator) — UPDATED (additive origin on the subquery
spec; only affects fusion when `POLYMATH_CHAT_LATENT_FUSION=1`). CANDIDATE_ENGINE — UPDATED (F3 seam +
step-6 config-driven weights). ACCEPTANCE / RETRIEVAL_RECEIPT — TESTED live (CA5 subset clean, 0 flags).
Follow-ups (non-blocking, owner's call): (a) V2 is LIVE with `LATENT_SELECTION`+`BRIDGE_COMPILER` now
also ON — the whole WLK2C+V2 latent stack is the live default (previously flagged off); (b) the CA5
gate was an 18-query subset per owner scope, not the full 64×4 — a full CA5 can be run later for
tighter MRR CIs but is not required to qualify; (c) `pmv4-fusion` worktree can be pruned; (d) weights/
preserve_top_n are config-driven (`POLYMATH_FUSION_*`) and untuned — future calibration is config-only.
REVERT path if a regression surfaces later: set the 3 `.env` flags to 0 + bounce (V2 → flagged-off).
