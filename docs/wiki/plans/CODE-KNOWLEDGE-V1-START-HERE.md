---
title: "CODE-KNOWLEDGE-V1 — START HERE: the implementation bootstrap for a new session"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "ACTIVE — the single entry point for implementing multi-language code RAG. Planning is complete; implementation starts at C0 once the owner's real-code inputs (§3) are in."
owner: "@king"
scope: "Documents only. Consolidates the decided design (11.452–11.456) into one bootstrap: what to build, in what order, what is already decided, where the code lives, how every slice is run, and the traps."
---

# CODE-KNOWLEDGE-V1 — START HERE

**Owner, 2026-09-24:**
- "i dont want to mess with the backend that works instead build upon it in a proper manner, where it detects and makes
  the code go through the rag pipeline, its graph can be made determisniticaly, we can use the same llm to power meaninign
  and routing layers";
- "i hope you are bootstrapping idea in a md for a new session implemnetations".

This file is that bootstrap. Everything below is decided unless §3 says otherwise. **Do not re-ask a decided item.**

## 0. What you are building (one paragraph)

Code (Python, YAML / TOML, Luau / Roblox, Power Fx) goes through the SAME Polymath pipeline as documents. Only the front
door is new:
1. detection;
2. a parser per language that cuts files into exact-source parents / children;
3. a deterministic graph of symbols and links in Postgres, projected to Neo4j;
4. the SAME `doc_profile` / `doc_parent_map` workers and LLM lanes write file-level profiles and class-level pMAP routes
   with a code prompt variant;
5. retrieval uses the existing lanes and the ONE reranker, plus a structure lane that walks the graph;
6. answers cite exact code (`[S#]`). Summaries are orientation only.

Document ingestion stays byte-identical, and every slice ships behind a flag, default off.

## 1. Bootstrap (the first 15 minutes of a session)

1. Run the `polymath-bootstrap` skill steps: guards, fleet truth, `git worktree list`, CONTINUITY's CURRENT block.
2. Read, in order. Stop when you have what the current slice needs.
   1. **This file.**
   2. **`docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md`,** the contract:
      - §1 the five layers + rules;
      - §2–§6 one card per language;
      - §7 cross-language links;
      - §8 C0 checks;
      - §9 slice mapping;
      - §10 the code answer + MCP contract;
      - §11 enrichment requests;
      - §12 large files.
   3. **`docs/wiki/plans/CODE-KNOWLEDGE-V1-SOURCES.md`:** the GitHub sources to pull / evaluate / study / reject, with
      licences and versions.
   4. **`docs/wiki/reports/2026-09-23/CODE-KNOWLEDGE-V1-FEASIBILITY.md`** §3 (repo drift that overrides the packet) and
      §5 (per-slice code anchors).
   5. **The packet `docs/code-knowledge-v1/`,** only for the slice at hand: `05_…CONTRACT_ARCHITECTURE.md`,
      `03_…CONTROL_MAP_SCHEMA.md` (the table schemas), `01_…IMPLEMENTATION_PLAN.md` (§35 slice text).
   6. **The owner's notes, only when a question traces back to them:**
      - `ADDENDUM_2026-09-23_OWNER_NOTE.md`;
      - `…_2026-09-24_OWNER_NOTE_3.md`;
      - `…_NOTES_4_5.md`;
      - `…_NOTES_6_7.md`.

      The reconciliations: `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTE-3-RECONCILIATION.md` and
      `…-NOTES-4-5-RECONCILIATION.md`.
3. Check the owner inputs in §3. Without them, only C0's repository-internal checks and C1 / C2 can run.

## 2. Decided (never re-ask)

| Topic | Decision | Source |
|---|---|---|
| Scope of the first version | Python, YAML + TOML, Luau / Roblox, Power Fx (Power Fx is the LAST language slice) | owner 2026-09-24 (11.452) |
| Project isolation | project = corpus; a project's reference documents join its corpus ("same corpus for now"). Multi-corpus search comes later | owner 2026-09-24 |
| Meaning layer | file level (Document Profile) + every class / parent (pMAP), code prompt variants of the existing prompts (§11), fed exact code + graph context. Per-function enrichment only after a measured miss | owner 2026-09-24 |
| Evidence | only exact source is evidence; profile / pMAP / atoms route and appear to the answer model only as labelled ORIENTATION | plan + owner |
| Structure | parsers / analyzers only. Never LLM language detection, never LLM-made graph links | owner defaults 2026-09-24 |
| Graph storage | Postgres authority + a deterministic **Neo4j projection in the first version** (C8 right after C2) | owner 2026-09-24 (11.455) |
| Graph honesty | every link carries resolution + confidence + provenance + `source_revision` / `span` / `rule` / `tool` / `tool_version`; a re-extraction reproduces it; remotes pair only by the same resolved instance; config strings are `ambiguous` unless a schema defines the field | reviews A + B (11.455) |
| Diagnostics | real analyzer findings are facts (layer 3b); AI "failure modes" are labelled hypotheses | 11.455 |
| `.txt` files | promoted to YAML / TOML only by a strict parser + structure markers; versioned, receipted | owner defaults |
| Ingestion runtime | the existing fleet and control plane; no Celery / RQ, no second scheduler | owner defaults |
| Ranking | one reranker judges code and documents together; no fixed weights; discovery paths reach the path-aware judge | owner defaults + 11.455 |
| Modes | no new public mode; code tasks (LOCATE / EXPLAIN / DEBUG / IMPACT / COMPARE / GENERATE) are an overlay | owner defaults |
| Answers | three labelled parts: observed implementation / relevant principles / proposed changes; a book never proves a bug | 11.455 |
| Tooling | mature open source per the sources list. No hand-written parser or resolver where a maintained one exists | owner 2026-09-23 / 24 |
| Contracts | per document (`chunk_contract_version` + receipt-level prompt versions), never fleet-wide `worker_contracts()` keys | review decision 2 |
| Materialization | code stored as `format: "text"`, no schema change; code must NEVER reach tier_v3 (it turns `# comments` into headings) | review decision 3 + §4 |

## 3. Open (resolve before the slice that needs it)

1. **Owner inputs** (needed for C0's real-code checks and C4 / C5b / C14):
   - the Roblox game's folder, and whether it is **Rojo / Argon files** (`.luau` + `default.project.json`) or a
     **place file** (`.rbxl` / `.rbxlx`);
   - the Python repository to qualify on (the owner was offered this Polymath repository);
   - YAML / TOML config sets;
   - a Power Apps app as source (`.pa.yaml`, via Power Platform Git integration);
   - the reference documents for each project's corpus.
2. **Decision 6, profile / pMAP capacity:** C0 measures parents per repository × seconds per call on the existing lanes,
   then proposes a cap or extra lanes to the owner.
3. **Tool choices C0 makes** (sources list group B):
   - the Luau resolver: rojo sourcemap + luau-lsp;
   - the Python resolver: scip-python vs jedi vs LibCST-only;
   - single tree-sitter grammars vs the language pack;
   - YAML: tree-sitter-yaml / ruamel vs PyYAML;
   - CodeGraphContext's extraction vs ours;
   - whether Qwen3-Embedding suffices on enriched code text.
4. **.NET for Power Fx:** ask the owner before installing anything (C5b).

## 4. Slice order (each slice = its own worktree branch, flag default off, tests, work-log, register row, guards)

| # | Slice | Delivers | Proof |
|---|---|---|---|
| 1 | **C0** baseline + tooling evaluation | the fleet / receipts baseline; the §3.3 comparisons on real files (this repository for Python / YAML / TOML); capacity numbers (decision 6) | an experiments JSON + a work-log; each candidate judged: exists · fixture run · real-input run · useful output |
| 2 | **C1** detection + importer | extension + strict-parser content detection (YAML / TOML `.txt` promotion; skips with receipts), the repo importer (repo-relative paths, sync by path, a path → hash ledger), routing code away from tier_v3 | detection tests per card; an importer test on a fixture repo; documents byte-identical with the flag off |
| 3 | **C2** structure manifest + Postgres | `code_symbols` / `code_edges` / `code_symbol_parent_links` (schema `03_…` §4–§6) with the controlled vocabularies + the reproducibility attributes | migration on a throwaway Postgres first; the re-extraction reproducibility test |
| 4 | **C8** Neo4j projection | `CodeDocument` / `CodeSymbol` / `CodeConfigPath` + `CODE_*` relationships, projection receipts, reconciliation | desired = actual counts; no collision with the Entity / Fact graph |
| 5 | **C3** Python | the Python card: units, symbols, relations, the chunk provider (`ast_code_v1`) | this repository parsed; spans exact; `CALLS` / `IMPORTS` spot-checked |
| 6 | **C5a** YAML + TOML | the YAML and TOML cards (dialects, key paths, anchors, entrypoints) | the fixtures + real configs |
| 7 | **C4** Luau / Roblox | the Luau card (Rojo script kinds, metatable classes, requires via sourcemap, remotes paired by instance) | the owner's game: typed syntax parses, requires resolve, remote pairs correct |
| 8 | **C6** code pMAP | the §11 pMAP variant for every class / parent + the language addenda; the relationships copied from the graph | MAP contract intact (every alias exactly once); hash-gated reuse |
| 9 | **C7** code profile | the §11 profile variant; large files per §12 (built upward, never from hooks) | labels intact; the §12 acceptance checks |
| 10 | **C9–C11** retrieval | the code-task overlay, the structure lane (the graph walk from strong hits, with readable paths into the path-aware judge), candidate roles, ORIENTATION for code summaries, the §10 answer contract | owner-style questions per card (in-process replay first, then the owner's live words) |
| 11 | **C12** readiness | code corpora in control / readiness | readiness receipts |
| 12 | **C13** validators + diagnostics | per-card validation; layer 3b diagnostics (Ruff, pyright, luau-analyze, selene) | findings stored with rule / severity / span / tool version |
| 13 | **C5b** Power Fx | two passes (YAML structure → PowerFx.Core binder fed pass 1's symbol table) in a .NET sidecar | the owner's app: formulas bound; the navigation / data links correct |
| 14 | **C14** qualification | every card's test questions on the owner's real code, incl. a code + book question | the §12 acceptance + cited exact source + revision updates |

## 5. Where the code lives today (verified 2026-09-24, production `eb93d24`)

| What | Where |
|---|---|
| intake (the upload event → materialize) | `workers/workers/intake_worker.py` `process_event` (L151; `media_type` at L156) |
| materializer (media type → text / markdown) | `shared/polymath_shared/materializer.py` `materialize` (L143), `TEXT_MEDIA_TYPES` (L38) |
| chunking | `workers/workers/chunker.py` `materialize_chunks` (L510); tier chunker `workers/workers/tier_chunker.py` (tier_v3: code must never reach it) |
| Document Profile prompt | `shared/polymath_shared/document_profile/prompt.py` (`doc-profile-v3.2`, labels from L20) |
| pMAP prompt | `shared/polymath_shared/document_profile/map_prompt.py` (`map-prompt-v2`, the MAP contract near L48) |
| parent skeleton / grounding | `…/document_profile/parent_skeleton.py` (`ParentSkeleton` L271, `build_parent_skeletons` L401); `…/grounding.py` (`DocumentGroundingContextV1` L160) |
| profile / pMAP workers | `workers/workers/doc_profile_worker.py`; `workers/workers/doc_parent_map_stage_worker.py` (the live pMAP process) |
| candidate engine | `shared/polymath_shared/candidate_engine.py` (`retrieve_candidates` L674); skeleton routes `shared/polymath_shared/skeleton_routes.py` |
| chat retrieval | `orchestrator/orchestrator/api/chat_retrieval.py` (`chat_retrieve_mode` L767) |
| chat runtime / answer prompt | `orchestrator/orchestrator/api/ui.py` (`chat_events`, `_grounded_messages`; S8's `_LEARNING_CONTRACT_BLOCK`) |
| MCP servers | `orchestrator/orchestrator/mcp_server.py` (Server A: `upload_document` L179, `retrieve`, `ask` …); `mcp_server/polymath_mcp.py` (Server B) |
| scaffold registry (every new file) | `scripts/scaffold_polymath_v4.py` `TREE` |

Per-slice anchors in more depth: the feasibility review §5. Use graft first (`graft grep` / `graft callers` /
`graft skeleton` in `../_graft_polymath`; refresh with `git checkout -q --detach <production-sha> && graft build .`).

## 6. How every slice is run (the owner's standing rules)

- **Isolate.** `git worktree add ../pmv4-<slug> -b <branch> production`. In the worktree, always
  `export PYTHONPATH=$PWD/shared:$PWD/orchestrator:$PWD/workers:$PWD/control` and verify the import origins. A worktree
  has no `.env`: database-backed tests time out there, which is not a regression. Compare with production code from a bare
  worktree.
- **Tests.** Run the IMPACTED files only, always with `-k "not test_live_"`. **Never run the whole `tests/determinism`
  directory:** `test_incremental_census.py` and others write to the LIVE fleet database through a hard-coded DSN.
  `tests/integration/test_cross_domain_routing.py` deletes rows.
- **Flags.** New behaviour is default off. Document ingestion stays byte-identical with the flag off, and a test proves
  it.
- **Record.** A work-log with front matter + the 5 sections, a register row (next number after 11.456), `TREE` entries,
  CONTINUITY's CURRENT block updated.
- **Guards,** each exit code on its own line: `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`.
  Lint neutral (ruff counts vs production).
- **Merge + bounce.** The owner asked the agent to run them. The permission classifier may still block one: say so
  immediately, and give the owner ONE Run-button command per step (the owner is not terminal-savvy), in click order.
  The restart is `bash scripts/bounce_fleet.sh`: it prints READY on 24 workers / 13 types / one bundle, and refuses a
  second concurrent run. After a `shared/` merge the supervisor fence quarantines workers for about 90 s, then heals them.
  The orchestrator (chat) loads new code only after a bounce.
- **Push** only on the owner's per-push word; tags stay local.
- **Live questions** (the owner's chat turns) only on the owner's word. Prefer an in-process replay that writes no
  receipt.
- **Talk in plain words;** answer first.

## 7. Traps seen on this mission

- **Code in tier_v3** corrupts it (`# comments` become headings). Route code to its chunk provider before the document
  chunker.
- **YAML starting with `---`** is harvested as front matter today (review §4). C1 must route it first.
- **The profile / pMAP output formats are parsed by existing compilers.** A code prompt variant may add instructions, never
  change the labels or the MAP line.
- **Chat modes FAST / HYBRID / GRAPH / WILDCARD / GNN are single-corpus** (`mode_requires_single_corpus`). A project's code
  and its books therefore share one corpus in V1.
- **The planner's own targets can repeat a user's wrong premise** (S8 round 1). Treat the planner's fields as hypotheses
  in any code prompt too.
- **Graphify (the owner's installed 0.9.53)** reads `.luau` with its plain-Lua extractor: it is not a Luau parser.
- **The permission classifier** has denied production merges and bounces inconsistently. Check before stopping anything.
