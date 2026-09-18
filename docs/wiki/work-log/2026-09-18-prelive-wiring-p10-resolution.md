---
title: "WORK LOG — Pre-live wiring 3/N: P10 bounded evidence-resolution round on the live path"
change_id: PRELIVE-WIRING-P10-RESOLUTION
date: 2026-09-18
owner: librarian
last_reviewed: 2026-09-18
status: implemented
architecture_impact: "Wires the P10 evidence-resolution core into the LIVE retrieval/synthesis path. ui.py: after round 1, if a REQUIRED (origin=USER) aspect reached no final evidence, _maybe_resolve runs ONE bounded round 2 through the same chat_retrieve_mode engine and MERGES its new source children into fast['evidence'] before the bundle is built, so SYNTHESIS uses the new evidence; the resolution_receipt (hop_2_fired/reason/round2) rides on retrieval.resolution. Flag POLYMATH_CHAT_RESOLUTION (default off), fail-open, explicit single-round stop. Reuses the planner/engine — no second RAG pipeline. orchestrator/ = not worktree-testable: live-qualified."
---

## Contract
Checklist P10 / owner runtime spec: `round 1 → evidence-gap assessment → targeted need ONLY when
materially needed → bounded round 2 (existing machinery) → merge source evidence → synthesis →
explicit stop`. Also prove a round-1-sufficient case with NO second round. Do not create another
retrieval engine; do not begin multi-hop graph.

## Changes
- `orchestrator/orchestrator/api/ui.py`:
  - `_maybe_resolve(plan, fast, aspects, weak, retrieve_fn)` — the material gap is a REQUIRED
    (`origin=USER`) aspect that reached NO final evidence (from the round-1 `weak_aspects` trace);
    exploratory PROFILE-expansion probes are excluded (a profile probe finding nothing is not an
    evidence gap). Builds `ClaimState`s → `plan_resolution_round`; if a material gap remains, runs
    ONE `chat_retrieve_mode` round 2 and merges its top-6 NEW children into `fast['evidence']`
    (→ `evidence_rows` → `assemble_evidence_bundle` → synthesis). Returns the `resolution_receipt`
    + a `round2` block. No gap ⇒ no round 2 (explicit stop).
  - Call site after round-1 retrieval (before `evidence_rows`): flag `POLYMATH_CHAT_RESOLUTION`,
    `ui_mode in (FAST, HYBRID)`, `_aspects` present; fail-open. `retrieval.resolution` = the receipt.

## Proof
`ast.parse(ui.py)` OK; `ruff --select F,E9` clean on the added functions (pre-existing ELITE
S-findings only). Shared core UNIT_PROVEN (`evidence_resolution.py`, 13 tests). **Live (flag-on,
bounced):**
- FIRST test caught a real bug: `weak_aspects` included the PROFILE probes → resolution fired
  spuriously even on `direct_180` (round 1 perfectly sufficient). FIXED: gap = required USER
  aspect only (`38d9b1f`).
- **Sufficient case (no round 2):** `direct_180`, `res_shutter`, `benesh_vs_laban` →
  `hop_2_fired=false, reason=stop:no_material_gap` (round 1's required aspects all reached evidence).
- **Material-gap case (round 2 fires + synthesis uses it):** `color_psych` ("psychology of color
  perception inform color grading") → required aspect `q2` reached no final evidence →
  `hop_2_fired=true, reason=gap:q2:UNSUPPORTED`, round 2 retrieved 6 NEW source children; **all 6
  reach the final legend, 5/6 are in `used_evidence` (synthesis cited them)**, and the answer
  reflects the color-perception evidence. `combat_vs_dance` likewise (`gap:q1`, 6 new). Single
  round each (explicit stop). This is P10 LIVE_PATH_PROVEN.

## Rejected claims
- Fire resolution on any weak aspect (rejected — exploratory profile probes are not required needs;
  that fires round 2 almost always, violating "only when materially needed").
- Restructure the evidence bundle / re-rank round 1+2 together (rejected for v1 — the smallest
  compatible merge is appending round-2's new children into `fast['evidence']` before the bundle
  is assembled; existing selection/synthesis consume it unchanged).

## Open contract gaps
- `RESOLUTION_STATE`: **UPDATED** — live call site added; qualified with the flag on.
- A quality gap (an aspect that found tangential-but-not-gold evidence, e.g. `res_shutter_motion`)
  is NOT a coverage gap and does not trigger this signal — recorded honestly; runtime has no gold,
  so the material-need signal is coverage (a required aspect with zero final evidence).
