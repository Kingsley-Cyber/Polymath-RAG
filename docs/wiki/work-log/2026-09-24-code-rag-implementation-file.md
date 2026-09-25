---
change_id: CODE-RAG-IMPLEMENTATION-V1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. The code-RAG implementation contract: design rules, data contracts, module layout and per-slice integration points (file:line), tests and acceptance; K1 (knowledge roles + retrieval scope) added before C1; two new confirmed gaps K-01 / K-02."
last_reviewed: 2026-09-24
---

# Code RAG implementation file

## Contract
- The owner, 2026-09-24: "hey empahsis on implementation file for code rag. im expanding on current inocmplete
  implemntations," plus two pasted reviews: (1) knowledge_role + reference-only scope for Trail ideation; (2) keep profiles
  and pMAP, hand off from "sounds relevant" to "open the exact code and its necessary context", concrete bridges only,
  per-unit execution rules, context-aware freshness, the Trail boundary.

## Changes
- `docs/wiki/plans/CODE-RAG-IMPLEMENTATION-V1.md` (new).
- Gap register: K-01, K-02. Roadmap: K1 inserted before C1; points at the implementation file. START-HERE and CONTINUITY
  point at it.

## Proof
- Integration anchors re-read in source at production de611e2: intake chunker switch `intake_worker.py:193-219`, front
  matter `:328`, region roles `:346-365`, chunk insert `:388-411`; `settings.py:209` (`chunker`, default tier_v3); child
  payload `project_qdrant_worker.py:322-347`; Neo4j `_graph_rows` `:126-214`; stage DAG + `NON_BLOCKING_STAGES`
  `control/tickets.py:25-78`; corpus filters `fast.py:214`, `hybrid.py:70`, `retrieve.py:488`, `ask.py:117`,
  `projection.py:49`, `profile_atom_projection.py:172, 190`, `gnn_route.py:82`; the scout call `ui.py:1758`; dual-read
  `chat_retrieval.py:334, 377`; `_EVIDENCE_TEXT_CHARS` `ui.py:1522-1523`; `_resolve_chunk` `api/evidence.py:354`; MCP
  tools `mcp_server.py:395, 408`; `fast_retrieve` `api/fast.py:527`; `run_document_mapping` `doc_parent_map_worker.py:344`;
  `build_map_prompt` `map_prompt.py:117`; `build_context` `context.py:199`; `profile_nominate` `projection.py:40-61`;
  Trail `evidence_boundary.py:166`, `adapter_step_worker.py:172`; latest migration `0066_principal_ownership.sql`.
- Table and payload names follow the packet schema §3–§9; the feasibility review's drift table overrides packet §10 (no
  fleet-wide `worker_contracts()` keys).

## Rejected claims
- Replacing pMAP, one physical index, a new retrieval mode, an LLM retrieval judge, or new uppercase output fields in
  place of the existing profile labels / MAP line (the parsers expect them).

## Open contract gaps
- The owner's language JSON draft is not in the repository yet; §2.5 defines where it lands.
- Every slice in the file is OPEN; E2E-1 (C9 + C10) is the first end-to-end proof.
