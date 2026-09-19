---
change_id: LATENT-QUERY-FUSION-V2-F3
owner: wildcard-investigation
date: 2026-09-19
status: worktree_integration_proven
architecture_impact: "LATENT-QUERY-FUSION-V2 F3 — the live SELECTION seam (shared, worktree `fusion/latent-query`, UNMERGED; flag `POLYMATH_CHAT_LATENT_FUSION` default-off ⇒ retrieval byte-identical). `candidate_engine.py:1066`: when flag-on, `_latent_fused_union(fused, ranked_lanes, budget, union)` replaces the flatten's `union = fused[:merged_candidate_max]` with the F2 query-stratified fused ordering + bounded local-winner preservation — reusing the SAME CandidateEvidence (one physical candidate per chunk, provenance intact), NEVER expanding the cap, fail-open. `SubQuery` gains `origin` (default '') so a plan-provided lineage class reaches the RankedLane; the orchestrator population (chat_retrieval sub_specs → SubQuery.origin) + the ui.py live path + C4→C5→CA4 are F4 (live-only). Output still flows into the EXISTING C4→C5→CA4 spine unchanged. No weight/K/preserve_top_n tuning (F2 defaults); calibration = F4."
last_reviewed: 2026-09-19
---

## Contract
F3 makes query-stratified fusion decide WHO survives the real truncation seam. Owner-authorized with
constraints (2026-09-19): replace only the flag-on l.1066 behavior; flag-off exactly the existing path;
no tuning of preserve_top_n / weights / K (F2 defaults as implementation defaults); preserve the existing
`merged_candidate_max` (change who survives, not the ceiling); enrich lane origins from existing plan
provenance only; output flows into the existing C4→C5→CA4 unchanged.

## Changes
- `shared/polymath_shared/candidate_engine.py`:
  - NEW `_latent_fused_union(fused, ranked_lanes, budget, fallback)` — `fuse_ranked_lanes(ranked_lanes,
    k=budget.rrf_k, cap=budget.merged_candidate_max)` (F2 defaults), maps chunk_id→existing
    CandidateEvidence (noise survivors = physical candidates), builds the union in fused order,
    overwrites `fused_score` for coherence, backfills by fused score so the union stays as full as the
    flatten's, and NEVER exceeds the cap. Fail-open (any error → the `fallback` flatten union).
  - l.1066: `if ranked_lanes is not None: union = _latent_fused_union(...)` (flag-gated; `ranked_lanes`
    is only built when the flag is on, so flag-off is the unchanged path).
  - `SubQuery.origin: str = ""` + the F1 capture meta now carries `origin` → the RankedLane's lineage
    class (fusion weight). Populated live from plan provenance at F4; unset here = behavior unchanged.
- `shared/polymath_shared/ranked_fusion.py`: `_apply_cap` tightened to a STRICT ceiling (preserved take
  seats first, but the output never exceeds `cap`) — honors "do not expand merged_candidate_max".
- Tests: NEW `tests/determinism/test_latent_fusion_seam.py` (5, adapter/seam); `test_candidate_engine.py`
  +4 (flag-off flatten-prefix, flag-on end-to-end bridge survival, origin flow) and the F1 no-selection
  test relaxed to set-equality (F3 now reorders flag-on); `test_ranked_fusion.py` +1 (strict ceiling).
  Register 11.330; scaffold TREE; this work-log.

## Proof
`WORKTREE_INTEGRATION_PROVEN` (executed path = worktree copy; `candidate_engine`/`ranked_fusion` are
`shared/`). The owner's F3 checklist, all green:
- **FLAG OFF** — `test_flag_off_union_is_exactly_the_flatten_prefix`: union == `funnel_union[:cap]` (the
  old fused-order prefix) and no `ranked_lanes` key; plus the entire pre-existing candidate_engine +
  impacted-consumer suites pass flag-off (byte-identical path).
- **FLAG ON** — q0 local winners survive; a bridge local winner receives bounded exposure; a duplicate
  chunk in multiple lanes stays ONE physical candidate (same object reused); lineage/lane memberships
  remain attached; `merged_candidate_max` unchanged (len == cap everywhere); `preserve_top_n=0`
  degenerates to ordinary fusion (F2 control drops the bridge winner); malformed lane data fails open.
- **THE actual failure** — `test_bridge_local_winner_preserved_inside_unchanged_cap` (100 q0 flood + 1
  bridge rank-1 expert, cap 50): the flatten truncates EXPERT; V2 preserves it INSIDE the unchanged cap.
  And end-to-end through `retrieve_candidates` (`test_flag_on_preserves_a_truncated_bridge_winner_end_to_end`,
  cap 6): EXPERT absent flag-off, present flag-on, cap unchanged, `query_ids==['bA']`, count==1.
- 68 V2 tests + 51 impacted-consumer tests green.

Checkpoint answer: **YES** — query-stratified fusion alters candidate survival at the real truncation
seam (a bridge's local winner now reaches C4/C5) while remaining a strict no-op when disabled.

## Rejected claims
- NOT `LIVE_PATH_PROVEN`: the orchestrator population of `SubQuery.origin` (chat_retrieval sub_specs) +
  the flag-on live path (C4→C5→CA4 on the fused union) are F4 — orchestrator resolves to MAIN under the
  editable-.pth, so live proof needs merge+bounce. Do NOT claim wc01/wc05/wc07 behavior here (F4).
- NOT tuned: weights / preserve_top_n / K are F2 defaults; calibration is F4.
- NOT a cap change: the ceiling is preserved; only who survives it changed.

## Open contract gaps
`contract_impact.py` → CANDIDATE_ENGINE changed; consumers ACCEPTANCE / PROFILE_YIELD_RECEIPT /
RESOLUTION_STATE / RETRIEVAL_RECEIPT. Dispositions:

| contract | disposition | evidence |
|---|---|---|
| CANDIDATE_ENGINE | UPDATED (flag-gated selection) | flag-off byte-identical (union == flatten prefix; all suites green); flag-on = V2 survival, proven end-to-end |
| RETRIEVAL_RECEIPT | UPDATED (additive) | `trace['ranked_lanes']` only when flag-on (F1); union receipts reflect the fused order |
| PROFILE_YIELD_RECEIPT | TESTED_UNCHANGED | `test_profile_yield.py` green (flag-off) |
| RESOLUTION_STATE | TESTED_UNCHANGED | `test_evidence_resolution.py` green (flag-off) |
| ACCEPTANCE | DEFERRED (live) | flag-off unaffected; flag-on acceptance (C4→C5→CA4, CA5-safety) is F4 |

DEFERRED to F4 (owner authorizes separately): orchestrator `SubQuery.origin` population from plan
provenance; the flag-on live path (merge + port-gated bounce); A/B (V2 vs WLK2C V1 vs pre-WLK2C) on
WLK-10 + 4-mode survival + main harness + CA5 64×4; calibrate weights + preserve_top_n from data.
