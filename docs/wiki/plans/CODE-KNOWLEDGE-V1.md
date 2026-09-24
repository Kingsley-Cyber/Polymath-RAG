---
title: "CODE-KNOWLEDGE-V1 — first-class code knowledge (Python, Luau/Roblox, YAML/TOML, Power Fx) inside the existing retrieval architecture"
date: 2026-09-23
last_reviewed: 2026-09-24
status: "ACTIVE (owner 2026-09-24: 'i want to implement multi code langauge rag'). Reconciled with the third design note; 4 owner answers recorded. Next: C0 once the owner points to the real code (report 2026-09-24 §7)."
owner: "@king"
scope: "Source-family extension of ingestion (detection, exact-source chunk providers, structure store, code pMAP / profile enrichment) and retrieval (code_task overlay, one structure nomination lane, candidate roles, validators). No new public mode; document ingestion stays byte-identical."
---

# CODE-KNOWLEDGE-V1

**Plan of record = the owner's execution packet, admitted byte-identical at `docs/code-knowledge-v1/`** (planned 2026-09-18;
`PACKET_MANIFEST.json` sha256 verified on admission). Two reviews override it where they conflict. Read in this order:

1. The packet, in its own order: `04_…GOAL_MODE.md` → `05_…CONTRACT_ARCHITECTURE.md` → `03_…CONTROL_MAP_SCHEMA.md` →
   `01_…IMPLEMENTATION_PLAN.md` → `02_…ACCEPTANCE_MATRIX.md` → `03a_code_control_map_v1.yaml`.
2. The feasibility review `docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md`. Its drift table (§3) overrides
   the packet:
   - FAST and GNN are public modes;
   - no fleet-wide `worker_contracts()` keys;
   - the live profile path is prompt v3.2;
   - the live pMAP process is `doc_parent_map_stage_worker`;
   - "one cross-encoder call" is already false.

   Its §10 reconciles the second note; its §11 names the open-source parsers.
3. The owner's third note `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_3.md`, and its reconciliation
   `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTE-3-RECONCILIATION.md`. This report holds the owner's answers of
   2026-09-24, the status of all 13 review decisions, and the **revised phases, which supersede the review's §7 / §10
   phases.**

## One-sentence architecture (from the packet)

Detect and parse code deterministically, preserve exact source as canonical evidence, use the existing pMAP and Document Profile
layers for semantic routing, add structural code relationships as one deterministic nomination lane, fuse through the existing
candidate funnel and reranker, and always resolve the winning route back to exact source chunks.

## Owner decisions of 2026-09-24 (report §1, §4)

- **Languages:** the first version handles all four: Python, YAML (+ TOML), Luau / Roblox and Power Fx. Power Fx is the
  last language slice and needs a .NET sidecar; the owner is asked before installing .NET. The Power Apps write loop
  (Canvas MCP) stays later.
- **Project isolation:** project = corpus. A project's reference documents join its corpus ("same corpus for now"). Search
  across corpora (shared documents, scope strict / with_references / global) comes later.
- **Code enrichment:** file level (the Document Profile) and every class (a pMAP parent), in the documents' style. Code
  prompt variants carry the note's fields: summary, aliases, patterns and mechanics, questions answered, assumptions,
  failure modes, search phrases. The enrichment routes, and reaches the answer model as labelled ORIENTATION, never as
  evidence. Structure comes from AST / tree-sitter via mature tooling. Per-function enrichment only after a measured miss.
- **Technical defaults accepted:**
  - parsers only, no LLM guessing of code facts;
  - the call graph in Postgres first, Neo4j later;
  - `.txt` becomes YAML / TOML only if a strict parser accepts it;
  - the existing fleet runs ingestion;
  - one reranker, no fixed weights;
  - no new chat mode.
- **Still open:** decision 6 (profile capacity). C0 measures it on the real code.

## Status

| Item | State |
|---|---|
| Packet admitted | 2026-09-23 (register 11.413) |
| Feasibility review | done: feasible |
| Owner's second design note | admitted 2026-09-23, reconciled in the review §10 |
| Owner's third design note | admitted 2026-09-24, reconciled in the 2026-09-24 report (register 11.452) |
| Owner decisions (13) | 12 settled 2026-09-24 (answered or following the review by the accepted defaults); decision 6 open |
| Slices C0–C14 | not started. Order: report §6 |
| Owner input before C0 | the real code locations and formats (report §7) |
