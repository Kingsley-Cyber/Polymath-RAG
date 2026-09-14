---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R5 prep: the acceptance driver answers the harness-executed loop (scripted receipts or a real harness), proven live up to the planned Trail gap"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R5-DRIVER
date: 2026-09-14
owner: king
last_reviewed: 2026-09-14
status: complete
register: 11.270
architecture_impact: "Script only: `scripts/adapter_mcp_acceptance.py` gains `--adapter trail.product_discovery` (scripted θ answers citing only supplied ids), `--harness wait` (a REAL harness answers HARNESS_ACTION steps through its own MCP connection while the driver prints the action and polls) and `--harness-receipts DIR` (scripted HarnessResearchReceiptV1 files per action kind, ids bound by the driver); exit 3 = the honest TRAIL_CAPABILITY_PLANNED state. Plan §10 D1 refined (cohort nuance). No runtime change."
---

## Contract
Plan §8 R5 + §9 test B (harness independence at the acceptance surface) + prompt §17: the same driver must serve Hermes, Claude Code and Codex.
The driver never executes research itself: with `--harness wait` it shows the HarnessActionV1 and waits for the run to leave `awaiting_harness`
(the harness submits with `kind=receipt` through its own connection); with `--harness-receipts` it submits pre-recorded receipts (a scripted
harness for repeatable acceptance). Until Trail HR3 is WORKING the run ends at the first planned operation and the driver exits 3 with the gap.

## Changes
- `scripts/adapter_mcp_acceptance.py`: `answer_product_discovery` (C_hypotheses / G_mechanisms / K_revise / N_jobs / W_interpret; citations only from
  context; `trail_score_refs` from V_score), `load_receipt`, `--harness {receipts,wait}`, `--harness-receipts`, `--harness-id`, receipt submission with
  `kind=receipt`, planned-gap exit path (3) outside the async context, `product_opportunity` output check; registry note in `scripts/README.md`.
- `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md` §10 D1: doc-08 ranks within a cohort; a single run's score = rubric dimensions derived from
  admitted evidence; doc-08 for cross-run portfolio ranking (recommendation, owner decision).

## Proof
- Live on production (b79cf37, fleet a9f0a7d8c0a2): `--adapter trail.product_discovery --corpus cinema --no-restart --harness wait` → run
  `adr_2ffbed8221dacd3261c3d9fcbee2b231`: C_hypotheses issued with 93 evidence refs, invented submission refused, scripted hypotheses accepted, run ended
  `terminal_gap TRAIL_CAPABILITY_PLANNED` at `D_project`; driver exit 3 with clean JSON receipts + the gap on stderr.
- `python -c "import ast; ast.parse(...)"` clean; the R4 stub-daemon loop test remains the hermetic proof of the full loop.

## Rejected claims
- That the driver should fabricate receipts: it never does; `--harness-receipts` submits files the operator recorded, `--harness wait` defers to a real harness.

## Open contract gaps
- The full live loop and the `awaiting_harness` restart proof wait for Trail HR3 (R3) and the owner actions O1/O4.
