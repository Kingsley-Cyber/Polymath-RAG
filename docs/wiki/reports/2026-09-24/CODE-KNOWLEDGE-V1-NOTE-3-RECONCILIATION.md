---
title: "CODE-KNOWLEDGE-V1 — the owner's third design note reconciled; owner answers of 2026-09-24"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "RECONCILED — note admitted; 4 owner answers recorded; phases revised (Python, YAML/TOML, Luau/Roblox and Power Fx in the first version); next: C0 once the owner points to the real code"
owner: "@king"
scope: "Documents only. Maps the owner's third note (docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_3.md) onto the packet, the second note and the 2026-09-23 feasibility review, against production a7e3e38. No code changed."
---

# CODE-KNOWLEDGE-V1 — the third design note, reconciled

## 1. The owner's request and answers (2026-09-24)

- **Request:** "now since the rag for regular retrieval works i want to implement multi code langauge rag. theirs alreayd a
  md plan i beleive and i want to add upon it". The note is stored verbatim in
  `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_3.md`.
- **Mission:** CODE-KNOWLEDGE-V1 becomes the active mission. Document RAG is live; its open slices (S5–S7, S9; the S4 / S8
  flags are off) are paused, not dropped.
- **Answers,** asked once with a recommendation each, and recorded as given:

| Question | Owner's answer | What it settles |
|---|---|---|
| Which code does the first working version handle? | "powerfx, python, yaml, luau roblox code" | All four languages are in the first version. The review's phase 1 (Python + YAML) / 2 (Luau) / 3 (Power Apps) split becomes an ORDER of slices inside one release (§6). Power Fx parsing moves forward from Phase 3 (overrides decision 4); the Power Apps write loop does not |
| How does a code project use the shared books? | "Same corpus for now" | A project's code and its reference documents share one corpus: the review's "mixed corpora" answer (§6 item 3), which works today because chat modes are single-corpus. Search across corpora is deferred (§6, later) |
| How rich are the code summaries? | "file, and of course each unique class level, i was thinking llm enrichment style similar to document pmap and profile but for code. ast tree sitters. i think uing a mature repo code infrastrucutre is importantns." | LLM enrichment at file level (the Document Profile) and at every class (a pMAP parent), in the documents' style with the note's fields. Structure comes from AST / tree-sitter. Mature, existing code tooling over hand-written parsers or resolvers (§5) |
| Accept the technical defaults? | "Accept all (Recommended)" | Parsers only, no LLM guessing of code facts (decision 1); the call graph in Postgres first, Neo4j later (decision 5); a `.txt` file becomes YAML / TOML only if a strict parser accepts it; the existing fleet runs ingestion (no Celery / RQ); one reranker judges code and documents together (no fixed weights); no new chat mode. The "Power Apps in phase 3" default is overridden by the first answer |

## 2. What Polymath already has for each idea (production `a7e3e38`)

Most of the note's infrastructure exists under other names.

| Note 3 idea | Polymath today |
|---|---|
| project_id, one per game / repo | **the corpus.** A `corpora` row (`corpus_id`, `name`, `profile` JSON, `purpose`, `query_enabled`, `embedding_contract_id`) with its own Qdrant collections (prefix `polymath_<sha12(corpus_id)>_`). This is the note's "collection per project" option, the strongest isolation it lists |
| list / stats / delete a project | MCP `list_corpora`, `corpus_status`, `polymath_readiness`, `polymath_delete_corpus` (with a typed confirmation) |
| upload_code | `upload_document` / `upload_text`, one file per call. There is no repository importer (decision 7) |
| set_active_project | none. The MCP tools take the corpus on every call |
| background workers | the supervised fleet: 13 worker types, 24 processes, control tick, medic, bundle fence |
| FastAPI / MCP SDK | FastAPI orchestrator (:7200), MCP Server A (hosted, :8930), MCP Server B (stdio) |
| hybrid dense + sparse + rerank | candidate engine lanes A (hierarchy) / B (dense) / C (sparse), RRF fusion, one cross-encoder reranker |
| graph expansion | the Neo4j entity graph, GRAPH mode (hop 1), the graph-destination lane H |
| parent maps + LLM enrichment | pMAP (`doc_parent_map_stage_worker`), Document Profile v3.2 + profile atoms, latent abstraction / transfer |
| route to parents first, then children | DUALREAD lane E (profile → pMAP → children) and the skeleton routes |
| several embedded representations | one collection per representation kind (children, section summaries, profile atoms, pMAP routing signatures) |
| an embedder that is not code-specialised | Qwen3-Embedding (general purpose). The note's advice (lean on structure + summaries) fits |
| log interactions for later tuning | `query_receipts` records every turn: plan, lanes, evidence, answer meta |
| several corpora in one question | only the legacy ASK path. FAST / HYBRID / GRAPH / WILDCARD / GNN require exactly one corpus (`ui.py` `mode_requires_single_corpus`) |

## 3. The note's 20 ideas against the plan

The plan documents were read in full: the packet, the second note, the review. Anchors: P01–P05 are the packet files,
ADD is the second note, REV is the review.

| # | Idea | Verdict | Resolution |
|---|---|---|---|
| 1 | Deterministic code graph, LLM only for abstractions | PARTIAL: modules / classes / functions, static calls, imports / requires, definitions / references, reads / writes, spans, provenance and confidence per edge (P01 §6–7, §11) | Add, as later structural edges: inheritance / composition and Luau metatables, and Luau type-checker facts (§6, Luau slice). Control-flow edges are not needed for retrieval V1. Edges keep symbol-level spans. LLM-made edges stay routing-only (decision 11) |
| 2 | Uniform graph with cross-language edges | PARTIAL: the language-agnostic manifest, Code* node / edge types, Neo4j as a projection (P01 §7, §11; P03 §9) | The graph lives in Postgres first (decision 5). Cross-language references (a YAML key naming a Python entrypoint or a Luau RemoteEvent) become a deterministic, confidence-tagged resolution pass inside one corpus, later (§6) |
| 3 | Two parallel indexes fused at query time; 0.6 / 0.4 weights; LLM rerank | CONFLICT: "Do NOT create a parallel Code-RAG subsystem" (P04 L93); one candidate pool + one cross-encoder, no quotas | Resolved by the defaults answer: code and documents share one corpus and one engine. RRF fusion and one reranker, **no fixed weights**. The 1-hop walk from top code hits is the planned structural nomination lane (P01 L1106–1113) |
| 4 | Doc↔code links: deterministic, then offline `implements_concept` | COVERED (REV §10 L177, decision 11) | Keep: name-match links first; inferred links stay routing-only, after evaluation |
| 5 | Agent response shape: code_context / document_context / cross_links | PARTIAL: role-tagged evidence rows with symbol, path and line span (P01 §28, §33) | The MCP code tools (later) return this shape as a VIEW over the same evidence rows, keeping the `[S#]` ids |
| 6 | project_id everywhere; shared global docs; upload_code(…, overwrite) | CONFLICT: "Chat is single-corpus" (REV L107) | Resolved by the shared-docs answer: project = corpus, and its docs join the same corpus. `upload_code` = the repository importer with sync-by-path (decisions 7, 13). Shared cross-corpus docs come later with multi-corpus search |
| 7 | list / create / delete / set_active / stats project tools | NEW | Map onto the existing corpus tools (§2). `set_active_project` is a client-side default (the agent passes the corpus); no server session state |
| 8 | Scope modes strict / with_references / global; visibility | CONFLICT: single-corpus modes; no new public mode (P01 §1.1) | Deferred with multi-corpus search. When built, it is a SCOPE setting next to HYBRID / GRAPH / WILDCARD (never a mode), with a per-corpus `visibility` in `corpora.profile` (no schema change) |
| 9 | Multi-level LLM enrichment with 7 fields | CONFLICT: "Do not add a code summarization LLM unless evaluation proves…" (P01 L764) | Resolved by the summaries answer. No separate summarization layer: the existing pMAP (class level) and Document Profile (file level) stages get code prompt variants that carry the note's fields. Fed the unit's code, its children's signatures, its parent context and 1-hop neighbours from the structure store. Hash-gated, batched, selected units only. Per-function enrichment only after a measured miss |
| 10 | Hierarchical parent map; parents first, then children | COVERED (P01 §8, §15, §18.2) | Keep. The class is a parent; module-level code outside classes gets a module parent |
| 11 | Several embedded forms; filters; lean on structure; exact span | PARTIAL: exact source, pMAP, profile and atom vectors; dense + sparse; language / symbol / path filters; exact spans (P01 §18, §25) | Keep the plan's rule: add a vector level (e.g. signature + docstring) only after a measured miss. No score boosts: structure nominates, and the one reranker judges |
| 12 | Detection: extension, then content; YAML saved as .txt; LLM when unsure; unknown files as text | CONFLICT: "LLM detection is forbidden" (P01 L307); `.txt` keeps its document path (P01 L353) | Resolved by the defaults answer: **never an LLM**. A `.txt` / extensionless file becomes YAML / TOML only when a strict parser accepts it AND it carries structural markers. It is a versioned detection change, receipted. Unknown code-like files are skipped with a receipt; they never fall into tier_v3, which damages code (REV §4) |
| 13 | Luau, Python, YAML, TOML, Power Fx; pluggable parse(file) | PARTIAL: the parser registry + manifest; libcst, tree-sitter-luau, luau-analyze, PyYAML, PowerFx.Core (P01 §6; REV §11) | TOML is added (not in the plan). Power Fx moves into the first version. Roblox path resolution and metatables are added to the Luau slice. Tooling is chosen per §5 |
| 14 | SQL: registry, file hashes, enrichment cache, jobs / versions | PARTIAL: Postgres authority, source / manifest hashes, supersession, runs / tickets (P03 §3–7) | The importer's path → hash ledger is specified in C1 (decision 13). The enrichment cache = the existing hash-keyed pMAP / profile artifacts |
| 15 | MCP search_code / get_enriched_symbol / compare_implementations | PARTIAL: "code tools on MCP" in Phase 4 (REV L204–206) | Later phase. Signatures are fixed when built; `mode` maps onto the existing modes |
| 16 | Debugging: stack trace → functions → callers / callees + docs | PARTIAL: a DEBUG code task (P01 L1016) | Add a deterministic stack-trace parser (file:line → symbol through the stored spans) to the DEBUG task. Roblox traces carry the `Script '…', Line N` form. Later phase |
| 17 | implement_from_theory | COVERED: the GENERATE bundle + ANALOG role (P01 §20, §33) | Keep. A named tool comes later |
| 18 | Return raw code + LLM subsystem summaries | CONFLICT: profile / pMAP / atoms only route (P05 §24) | Resolved as the documents do it: summaries reach the answer model as a labelled ORIENTATION block (the documents' ELITE block), never as cited evidence |
| 19 | Log successful interactions as tuning data | NEW | Later. `query_receipts` already holds the raw material; no training loop until an evaluation set exists |
| 20 | FastAPI / FastMCP; Celery / RQ; auth | CONFLICT (Celery / RQ only): "…prevent … creating a second scheduler" (P03 L25) | Resolved by the defaults answer: the existing fleet runs ingestion. FastAPI and MCP already exist. Auth stays the MCP principal model |

## 4. The 13 review decisions after 2026-09-24

| # | Decision | Status |
|---|---|---|
| 1 | Skip LLM fact extraction for code | **ANSWERED yes** (defaults) |
| 2 | Per-document code contracts, not fleet-wide keys | follows the review's recommendation (defaults); the alternative marks every live corpus stale |
| 3 | Code as `format: "text"`, no schema change | follows the recommendation (defaults) |
| 4 | Power Fx now or Phase 3 | **ANSWERED: in the first version** (first answer). It needs a .NET SDK + a small sidecar; the owner is asked before anything is installed |
| 5 | Neo4j code projection deferred; Postgres traversal first | **CHANGED later on 2026-09-24:** the Neo4j projection ships in the first version, right after C2; Postgres stays the authority (notes 4–5 reconciliation §1, register 11.455) |
| 6 | Profile capacity for code | OPEN. File + class enrichment raises the LLM volume; C0 measures it on the real code and proposes a cap or extra lanes |
| 7 | Repository importer keeping relative paths, in C1 | **ANSWERED yes** (the note's upload flow) |
| 8 | Which real code qualifies | **ANSWERED in scope:** a Python repository, YAML / TOML configs, a Roblox game, a Power Apps app. The owner still has to point to them (§7) |
| 9 | IMPACT as a `code_task`, not a mode | follows the recommendation (defaults: no new chat mode) |
| 10 | FAST: exact-symbol lookup only | follows the recommendation |
| 11 | Doc↔code links: deterministic first | follows the recommendation (the note agrees) |
| 12 | Power Apps write validation through the Canvas MCP | stays LATER (the write loop needs .NET 10 + an open Studio session); parsing moves into V1 (decision 4) |
| 13 | Sync importer by path | **ANSWERED yes** (the note's `overwrite` / re-upload flow) |

## 5. Mature code tooling (the owner's "use mature repo code infrastructure")

The rule is REV §11's rule, restated: thin adapters around maintained open-source tools; no hand-written parser or name
resolver where a maintained indexer exists.

- **Already checked** (REV §11): libcst 1.9.0; tree-sitter 0.26 + tree-sitter-luau 1.2.0; luau-analyze 0.739; PyYAML;
  Microsoft.PowerFx.Core 1.8.1. All MIT.
- **To evaluate in C0,** not yet checked (versions and licenses are recorded when a slice adds them, PAR-05):
  - tree-sitter grammars for YAML / TOML (spans), or stdlib `tomllib` + a span-preserving TOML reader;
  - tree-sitter "tags" queries (symbol extraction for any grammar);
  - a SCIP indexer for precise cross-file Python references (e.g. `scip-python`);
  - Rojo sourcemaps + luau-lsp for Roblox `require` / instance-path resolution.

  C0 compares each against the planned adapter on the real code (implementation · fixture run · real-input run · useful
  output) before a slice depends on it.

## 6. Revised phases

**First version** (one release; the slices run in this order; each has its own work-log, tests and flag, default off):
1. C0: baseline + tooling evaluation (§5) + profile-capacity measurement on the owner's real code.
2. C1: detection (extension → strict-parser content check for `.txt` / extensionless YAML and TOML; never an LLM) + the
   repository importer (repo-relative paths, sync by path, a path → hash ledger).
3. C2: structure manifest + Postgres tables (deterministic symbols, edges, spans, provenance, reproducibility attributes).
   C8: the deterministic Neo4j projection of those tables (added to the first version 2026-09-24, register 11.455).
4. C3: Python structure + exact-source chunk provider.
5. C5a: YAML + TOML structure (key paths as symbols, anchors).
6. C4: Luau / Roblox structure: modules, functions, metatables / OOP, `require` + ModuleScript / RemoteEvent / GetService,
   Roblox path resolution (per §5), luau-analyze validation.
7. C6: code pMAP: every class is a parent; module-level code gets a module parent; class-level enrichment with the note's
   fields.
8. C7: code Document Profile: file-level enrichment with the note's fields; atoms.
9. C9–C11: retrieval. The code-task overlay (LOCATE / EXPLAIN / DEBUG / IMPACT / COMPARE / GENERATE), the structural
   nomination lane over Postgres, candidate roles, and the ORIENTATION block for code summaries.
10. C12: readiness + control integration.
11. C13: validators (Python / YAML / TOML; Luau via luau-analyze).
12. C5b: Power Fx. Formulas from Power Apps source (YAML + embedded Power Fx, two passes) through a .NET sidecar around
    Microsoft.PowerFx.Core. Needs the owner's OK to install .NET.
13. C14: qualification on the owner's real code in all four languages.

**Later** (not in the first version):
- search across corpora (shared documents without copying; scope strict / with_references / global; per-corpus
  visibility);
- deterministic doc↔code links (decision 11). The Neo4j projection moved into the first version on 2026-09-24;
- MCP code tools (search_code, get_symbol with callers / callees, compare_implementations, the note's response shape) and
  stack-trace debugging;
- the Power Apps App Model + `.pa.yaml` contract + Canvas MCP write validation;
- per-function enrichment after a measured miss;
- a tuning loop from receipts.

## 7. What the owner provides next (before C0 can measure anything)

1. **The Roblox game:** the folder on this Mac, and whether it is a Rojo / Argon file project (`.luau` files +
   `default.project.json`) or lives inside a place file (`.rbxl` / `.rbxlx`). A place file needs an export step first.
2. **The Python repository and the YAML / TOML configs** to qualify on. This repository is a candidate.
3. **A Power Apps app as source files:** the unpacked canvas-app source (`.pa.yaml`), e.g. from Power Apps Git integration
   or `pac canvas unpack`.
4. **The reference documents** each project should search with its code (they join that project's corpus).
