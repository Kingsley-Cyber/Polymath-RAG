# POLYMATH CODE-KNOWLEDGE-V1 — Execution Packet

**Purpose:** implementation-ready handoff for adding first-class YAML/Power Apps, Luau/Roblox, and Python code knowledge to Polymath without creating a parallel RAG architecture.

**Planning date:** 2026-09-18  
**Target execution agent:** Opus 4.8 in Goal Mode  
**Repository:** `Kingsley-Cyber/Polymath-RAG`

## Read order

1. `04_CODE_KNOWLEDGE_V1_GOAL_MODE.md`
2. `05_CODE_KNOWLEDGE_V1_CONTRACT_ARCHITECTURE.md`
3. `03_CODE_KNOWLEDGE_V1_CONTROL_MAP_SCHEMA.md`
4. `01_CODE_KNOWLEDGE_V1_IMPLEMENTATION_PLAN.md`
5. `02_CODE_KNOWLEDGE_V1_ACCEPTANCE_MATRIX.md`
6. `03a_code_control_map_v1.yaml` — machine-readable companion

## One-sentence architecture

> Detect and parse code deterministically, preserve exact source as canonical evidence, use the existing pMAP and Document Profile LLM layers to create semantic/abstract routing representations, add structural code relationships as a deterministic nomination lane, fuse everything through the existing HYBRID/GRAPH/WILDCARD candidate funnel and reranker, and always resolve the winning route back to exact source chunks.

## What MUST remain true

- There is **no new public CODE retrieval mode**.
- Public semantic modes remain `HYBRID`, `GRAPH`, and `WILDCARD`; FAST/VECTOR remain internal/rollback.
- Existing document ingestion remains byte-compatible unless a contract is explicitly bumped and blue/green migration is used.
- Existing `tier_v3` document chunking is not rewritten to understand code.
- Code uses source-family-specific structure adapters/chunk providers that emit the same canonical parent/child row semantics.
- pMAP/Profile/Profile Atom are **routing abstractions, never code evidence**.
- AST/Power Fx/YAML structure is **routing and dependency truth, not quoted source evidence**.
- Original source chunks remain the final evidence used to critique, explain, refactor, or generate code.
- Postgres remains workflow/state authority. Qdrant and Neo4j remain rebuildable projections.
- No new parser grammar is written where a mature parser already exists.
- No LLM is used to discover syntax, symbol identity, exact dependencies, or arithmetic that deterministic tooling can establish.

## Current repository seams this packet assumes

Verified against current GitHub `main` during planning:

- `shared/polymath_shared/materializer.py`
- `workers/workers/intake_worker.py`
- `workers/workers/tier_chunker.py`
- `shared/polymath_shared/execution.py`
- `control/control/tickets.py`
- `control/control/scheduler.py`
- `control/control/reconciliation.py`
- `workers/workers/doc_profile_worker.py`
- `workers/workers/doc_parent_map_worker.py`
- `shared/polymath_shared/document_profile/parent_skeleton.py`
- `shared/polymath_shared/document_profile/map_prompt.py`
- `shared/polymath_shared/document_profile/map_compiler.py`
- `shared/polymath_shared/document_profile/fingerprint.py`
- `shared/polymath_shared/document_profile/profile_atom.py`
- `shared/polymath_shared/document_profile/parent_map_projection.py`
- `shared/polymath_shared/query_intent.py`
- `orchestrator/orchestrator/api/chat_retrieval.py`

The execution agent MUST re-bootstrap from repository state because local HEAD may differ.

## Existing projects to reuse / study instead of recreating

| Need | Existing implementation to inspect/use |
|---|---|
| Power Fx lexer/parser/AST/binding/type analysis | `microsoft/Power-Fx` |
| Power Apps source representation / Canvas tooling | `microsoft/PowerApps-Tooling` |
| Official Luau parser/analyzer/tooling | `luau-lang/luau` |
| Tree-sitter Luau spans | `tree-sitter-grammars/tree-sitter-luau` |
| Python concrete syntax, qualified names, scope metadata | `Instagram/LibCST` |
| AST-aware code retrieval reference | `SylphxAI/coderag` / Locus |
| Repo-map definition/reference ranking reference | `Aider-AI/aider` |
| Dependency/dataflow/impact/hybrid structural search reference | `einad5/codegraph` |
| Lightweight AST→architecture graph reference | `ian000/graphify-go` |

**Rule:** reuse parser/analyzer capability, not somebody else's entire architecture. Polymath remains the composition root.

## Desired user experience

A query such as:

> Review this Power Apps screen against the advanced responsive-layout material in my corpus and tell me what should change.

must retrieve:

1. the exact screen/control/formula implementation;
2. the relevant structural dependencies and variables;
3. the applicable Power Apps technical-book evidence;
4. optional related patterns/atoms;
5. then synthesize a critique that cites source evidence and can generate a validated patch.

A query such as:

> Generate a Roblox ammo system using the game-design theories in my corpus, but make it conform to my current weapon architecture.

must retrieve:

1. existing Luau firing/reload/config/UI/remote code;
2. callers/callees and repository architecture;
3. game-design/resource-scarcity theory;
4. Luau/Roblox documentation in the corpus;
5. then generate code matching actual project names and validate it with Luau tooling before presenting it as a proposed implementation.
