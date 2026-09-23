---
title: "CODE-KNOWLEDGE-V1 — first-class code knowledge (Python, Luau, YAML, Power Apps) inside the existing retrieval architecture"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "ADMITTED — not started. Execution waits on the 8 owner decisions in the feasibility report §8."
owner: "@king"
scope: "Source-family extension of ingestion (detection, exact-source chunk providers, structure store) and retrieval (code_task overlay, one structure nomination lane, candidate roles, validators). No new public mode; document ingestion stays byte-identical."
---

# CODE-KNOWLEDGE-V1

**Plan of record = the owner's execution packet, admitted byte-identical at `docs/code-knowledge-v1/`** (planned 2026-09-18;
`PACKET_MANIFEST.json` sha256 verified on admission). Read it in the packet's own order:
`04_…GOAL_MODE.md` → `05_…CONTRACT_ARCHITECTURE.md` → `03_…CONTROL_MAP_SCHEMA.md` → `01_…IMPLEMENTATION_PLAN.md` →
`02_…ACCEPTANCE_MATRIX.md` → `03a_code_control_map_v1.yaml`.

**Then read the feasibility review:** `docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md`. It maps every slice
to today's code with anchors, and it lists:
- the drift since 2026-09-18 that overrides the packet: FAST and GNN are public modes; no fleet-wide `worker_contracts()`
  keys; the live profile path is prompt v3.2, not the fingerprint; the live pMAP process is `doc_parent_map_stage_worker`;
  the "one cross-encoder call" gate is already false;
- the gaps the packet does not cover: LLM extraction on code, repository import, reranker fit for code, the q0 floor;
- the recommended phased MVP;
- the owner decisions to settle before C1.

## One-sentence architecture (from the packet)

Detect and parse code deterministically, preserve exact source as canonical evidence, use the existing pMAP and Document Profile
layers for semantic routing, add structural code relationships as one deterministic nomination lane, fuse through the existing
candidate funnel and reranker, and always resolve the winning route back to exact source chunks.

## Status

| Item | State |
|---|---|
| Packet admitted | 2026-09-23 (register 11.413) |
| Feasibility review | done — feasible; phased MVP (Python + YAML → Luau → Power Apps) |
| Owner decisions (report §8) | OPEN |
| Slices C0–C14 | not started |
