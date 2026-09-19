---
change_id: WLK2C-LIVE-PLUMBING-C6
owner: wildcard-investigation
date: 2026-09-18
status: complete
architecture_impact: "WLK2C C4-live/C5-live/C6 live wiring (orchestrator + shared, IMPLEMENTED — live proof deferred to C7; flag `POLYMATH_CHAT_LATENT_SELECTION` default-off ⇒ byte-identical by construction). `chat_retrieval.py`: exposes a BOUNDED `latent_pool` (the judged-prefix candidates dropped from final, with their q0 rerank score) — flag-gated, a small slice not the whole union. `ui.py`: `_apply_latent_selection` runs an ADDITIVE second portfolio pass after retrieval + before CA3/CA4 — grades the bridge pool (C4) + re-seats [q0 evidence + latent] (C5) gated by the q0 grounding (establishes_need + n_direct≥1), then REASSIGNS `fast['evidence']` to a NEW list (q0 rows copied, never mutated in place). q0 stays primary; the FINAL CA4 grade + answerability gate still run downstream (C5 never bypasses CA4). Persists the winning bridge lineage on each latent seat (not just seat_role). C6 receipt on `retrieval.latent_selection` records every graded candidate incl. REJECTS (bridge_invalid / local_subfloor) + bridge_q0 scores + seating counts + latency. Fail-open throughout; `latent_selection.py` trace gains `graded` for C6."
last_reviewed: 2026-09-18
---

## Contract
WLK2C live plumbing (owner watch-points): expose a bounded pool (not the universe); do not mutate q0
evidence in place (additive second pass ⇒ flag-off byte-identical + trivial rollback); keep lineage on
the final evidence object; C6 records rejects too; per-stage latency; and the ordering q0 retrieval →
judged pool → C4 → C5 → CA4 grading/gating → synthesis, with C5 NOT bypassing CA4.

## Changes
- `orchestrator/orchestrator/api/chat_retrieval.py`: after selection, build `latent_pool` (flag-gated) =
  `result.union` candidates in the judged prefix (`pre_g3_order`) but not in `final`, each `{chunk_id,
  doc_id, parent_id, source_name, text, query_ids, q0_score=rerank_score}`; add `"latent_pool"` to the
  return (None when off). Bounded (prefix minus final); the graph/wildcard wrappers preserve it.
- `orchestrator/orchestrator/api/ui.py`: `_apply_latent_selection(fast, plan, q0_text)` (+ `_bridge_role`,
  `_selected_lineage`). Builds `bridges` from the plan's BRIDGE subqueries; grounding from a preliminary
  `grade_evidence` on the q0 evidence; `grade_and_seat_latent(pool=q0_ev+latent_pool, rerank=
  _rerank_children, capacity=len(q0_ev), establishes_need, has_direct_grounding=n_direct≥1)`; rebuilds
  `fast['evidence']` (copy q0 rows, add latent rows with `latent_role` + `latent_lineage`). Called after
  P10 resolution, before `evidence_rows`. Receipt `retrieval.latent_selection` (init `_latent_receipt`).
- `shared/polymath_shared/latent_selection.py`: the returned trace gains `graded` (every candidate's C4
  state + eligibility) for the C6 rejects.
- Register row 11.325; this work-log.

## Proof
`IMPLEMENTED` — orchestrator is NOT worktree-unit-testable (editable `.pth` → MAIN); honest proof is
py_compile + preflight clean now + the C7 live qualification. `ui.py` + `chat_retrieval.py` py_compile OK;
`agent_preflight`=0. Flag off ⇒ `latent_pool=None` + `_apply_latent_selection` early-returns ⇒
`fast['evidence']` untouched ⇒ evidence IDs/order byte-identical BY CONSTRUCTION (the owner's pre-bounce
check is a C7 live re-verification). The pure grade+seat logic it drives is UNIT_PROVEN (latent_selection
7 + latent_portfolio 13 green after the `graded` addition).

## Rejected claims
- NOT proven live yet (C7). No latency/quality numbers. The bridge pool is bounded (judged prefix minus
  final), never the whole union. q0 evidence rows are copied, never mutated; flag-off is a strict no-op.

## Open contract gaps
`contract_impact` (ui.py + chat_retrieval.py touch QUERY_PLANNER/CANDIDATE_ENGINE/RETRIEVAL_RECEIPT/…):
additive + flag-gated; off-flag **TESTED_UNCHANGED** (byte-identical by construction; shared latent
modules green), on-flag **DEFERRED** to the C7 live qualification. Remaining: C7 = merge + port-gated
bounce + the pre-bounce flag-off identity check + WLK2C qual (WLK-10 + survival + main harness) + full
CA5 64×4 vs the frozen baselines. Latency stages captured: bridge_compile (C3 diag) + portfolio_seating
(here); bridge_retrieval is inside chat_retrieve_mode.
