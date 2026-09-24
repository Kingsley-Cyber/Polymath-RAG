---
change_id: CODE-KNOWLEDGE-V1-NOTE-3
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. The owner's third code-RAG design note is admitted verbatim and reconciled against the CODE-KNOWLEDGE-V1 packet, the second note and the feasibility review. The owner's 4 answers of 2026-09-24 are recorded. The plan pointer, the phase order and CONTINUITY are updated: CODE-KNOWLEDGE-V1 becomes the active mission and document RAG's open slices are paused. No code, no fleet change."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1: the owner's third design note admitted and reconciled

## Contract
- The owner, 2026-09-24: "now since the rag for regular retrieval works i want to implement multi code langauge rag.
  theirs alreayd a md plan i beleive and i want to add upon it". A long design note was pasted with the request.
- The polymath-bootstrap rule: a plan that lives only outside the repository is admitted first (documents only), then
  reconciled, before any slice executes.
- The owner's answers were asked once, with a recommendation each (reconciliation §1):
  - languages: "powerfx, python, yaml, luau roblox code";
  - shared documents: "Same corpus for now";
  - summaries: "file, and of course each unique class level … llm enrichment style similar to document pmap and profile
    but for code. ast tree sitters. i think uing a mature repo code infrastrucutre is importantns.";
  - defaults: "Accept all (Recommended)".

## Changes
- `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTE_3.md`: the note, verbatim, with formatting normalized to
  Markdown (as the second note was).
- `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTE-3-RECONCILIATION.md` (new):
  - the owner's answers;
  - what Polymath already has for each idea (project = corpus; the corpus MCP tools; the fleet; lanes + reranker; pMAP +
    profile; receipts);
  - the 20 ideas against the plan: 3 covered, 8 partial, 7 conflicts (each resolved by an answer or by the plan's
    standing rule), 2 new;
  - the status of all 13 review decisions;
  - the mature-tooling rule;
  - the revised phases (all four languages in the first version, Power Fx last);
  - the owner's next inputs.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`: status ACTIVE, read order incl. the third note, the owner's decisions, status
  table.
- `docs/wiki/plans/CONTINUITY-REPORT.md`:
  - a new CURRENT block (CODE-KNOWLEDGE-V1 active; the next action; the owner decisions; document RAG paused; repository
    state; do not do);
  - the previous block renamed PREVIOUS;
  - its CODE-KNOWLEDGE-V1 line updated.
- The register (11.452) and the scaffold TREE (3 new files).

## Proof
- **Coverage map:** the plan documents were read in full (packet 01–05 + 03a + README, the second note, the review). All
  20 ideas were classified, with file / section / line anchors. Six anchors were spot-checked verbatim:
  - P04 L93 "Do NOT create a parallel Code-RAG subsystem.";
  - P01 L764 "Do not add a "code summarization LLM" unless evaluation proves…";
  - P01 L307 "LLM detection is forbidden.";
  - P05 L823;
  - P03 L25 "…prevent an implementation agent from creating a second scheduler…";
  - REV L107 "Chat is single-corpus…".
- **Repository facts** (read-only, production `a7e3e38`):
  - `corpora` has `purpose` / `query_enabled` / `profile`; each corpus has its own Qdrant collections;
  - MCP Server A / B list their corpus tools;
  - chat modes FAST / HYBRID / GRAPH / WILDCARD / GNN reject more than one corpus (`mode_requires_single_corpus`); only ASK
    takes several;
  - two corpora exist (`cinema` 67 documents, `commerce-v1` 10);
  - no document was profiled in the last 5 days, so profile capacity cannot be measured from recent runs (decision 6
    stays open for C0).
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "Two parallel indexes with 0.6 / 0.4 weights": code and documents share one corpus and one engine; one reranker judges;
  no fixed weights (the plan's rule, the owner's defaults).
- "An LLM classifier for unsure files": LLM detection stays forbidden. A `.txt` is promoted only by a strict parser.
- "Celery / RQ": the existing fleet and control plane run ingestion; no second scheduler.

## Open contract gaps
- **Decision 6 (profile capacity):** measured in C0 on the real code.
- **Owner inputs before C0** (reconciliation §7):
  - the Roblox game's folder + format;
  - the Python repo + YAML / TOML configs;
  - a Power Apps source export;
  - the reference documents per project.
- **Power Fx needs .NET:** the owner is asked before anything is installed.
- **Mature tooling to evaluate in C0,** not yet verified:
  - tree-sitter YAML / TOML grammars and tags queries;
  - a SCIP Python indexer;
  - Rojo sourcemaps + luau-lsp.
