---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R4 live proof: production runs main b81fa2c; the 2.0.0 adapter is live and ends honestly at the first planned Trail operation"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R4-LIVE-PROOF
date: 2026-09-14
owner: king
last_reviewed: 2026-09-14
status: complete
register: 11.269
architecture_impact: "None (proof record for 11.267/11.268): production fast-forwarded to b81fa2c and bounced; receipts of two official-MCP-client runs on the live fleet."
---

## Contract
AGENTS.md §9 completion proof for R2 + R4 on the production path: a public entrypoint (the Polymath MCP server, bearer-gated), runtime wiring
(orchestrator → adapter service → supervised `adapter_step` worker), a durable outcome (adapter runs, steps, receipts, hypotheses rows), and a
verifier traversing the same path (the official `mcp` client). This entry links the proof to the R2/R4 work-logs; nothing else changes.

## Changes
- None in code. Production worktree `production` = origin/main b81fa2c (PR #11 d79f88e + PR #12 b81fa2c merged); migrations 0062 + 0063 applied;
  fleet bounced with the documented procedure: 24 healthy, ONE hash `a9f0a7d8c0a2`, `adapter_step` up, 7 adapter tools, 0 quarantines.

## Proof
| run | adapter | receipt |
|---|---|---|
| `adr_d5e544c490205da878e54bec3c1732ad` | `polymath.knowledge_brief` 1.0.0 | `scripts/adapter_mcp_acceptance.py`: 43 evidence refs; supervised worker SIGKILL 85244 → respawned 86130, run resumed; invented submission refused (422: schema + citation); completed, 2 receipt hashes, lineage cites the submitted ids |
| `adr_eb118ed875ed241afdb7dc183f79bebd` | `trail.product_discovery` 2.0.0 | `adapter_list` shows 28 steps / 11 planned Trail ops; `C_hypotheses` issued as `theta_op=generate_hypotheses` with 97 real evidence refs; invented citation refused; two hypotheses accepted → durable rows `hyp_37df3483…`, `hyp_b3aef241…` (revision 0, `proposed`) with GENERATE transitions by θ (2 cause refs each); the run ended `terminal_gap` `TRAIL_CAPABILITY_PLANNED` at `D_project` ("registry.project is not yet a TrailSignal production capability (graph node HR3)"); `adapter_result` carries `lineage.hypothesis_ids`, 6 receipt hashes, no external operations |

## Rejected claims
- That the product-discovery loop is live end to end: it is not — every Trail operation is `planned` until Trail HR3; the run stops at the first one
  with a typed gap, which is the honest state the plan requires until R3 lands.

## Open contract gaps
- R3 (Trail HR1–HR4) and R5 (live acceptance with a real harness; retire `research/`).
