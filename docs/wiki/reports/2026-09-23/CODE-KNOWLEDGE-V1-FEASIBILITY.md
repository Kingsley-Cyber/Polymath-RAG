---
title: "CODE-KNOWLEDGE-V1 — feasibility review mapped to the repository (production 1d91593)"
date: 2026-09-23
last_reviewed: 2026-09-23
status: "REVIEW — the plan is feasible; phased MVP recommended; 13 owner decisions open before slice C1 (8 in §8 + 5 from the addendum §10)"
owner: "@king"
scope: "Read-only review of the owner's execution packet (docs/code-knowledge-v1/) against the live repository. No code changed."
---

# CODE-KNOWLEDGE-V1 — feasibility review

**Inputs:** the owner's packet `docs/code-knowledge-v1/` (planned 2026-09-18). I read it in full; three read-only repository
mappings (ingestion / semantic layers / query) followed it slice by slice at production `9aa265e`, and every anchor below was
re-checked in the real repository. Owner constraint for this review: *change as little as possible in backend ingestion and
extraction; build on the current infrastructure.*

## 1. Verdict

**Feasible, and well aligned with the system as it is.** Most of the plan lands as small additions at seams that already
exist (EXTEND). The genuinely new code is the language adapters and chunk providers, the structure store, the `code_task`
overlay, the structure lane's store and the generation validators.

**Recommended: a phased MVP.**
- **Phase 1:** Python + generic YAML, end to end.
- **Phase 2:** Luau.
- **Phase 3:** Power Apps / Power Fx, which needs a .NET sidecar.

Also recommended: **defer the Neo4j code projection (C8)** and do bounded structural traversal in Postgres first. Thirteen
owner decisions (§8 + §10) should be settled before C1.

## 2. What the plan gets right (keep as written)

- **One retrieval architecture:** no CODE mode; code adds representations plus one nomination lane to the existing modes.
  `MODE_LANES` / `chat_retrieve_mode` (`orchestrator/orchestrator/api/chat_retrieval.py:682-689`) makes this
  straightforward.
- **Exact source is evidence:** intake's `_validate` already enforces exact substring / no overlap / child-in-parent
  (`workers/workers/tier_chunker.py:709-724`), and chunk ids hash `(doc_id, index, text)` (`identity.py:55-56`).
- **Structure is deterministic; pMAP / profile / atoms only route:** matches the existing laws (atoms never evidence,
  pMAP → parent → original children).
- **pMAP output DSL and compiler unchanged:** the compiler already maps aliases to parents through
  `alias_to_parent` (`shared/polymath_shared/document_profile/map_compiler.py:162-176, 217`).
- **Postgres authority, Qdrant / Neo4j rebuildable; additive migrations; blue/green for identity changes:** all existing
  practice (`stores/postgres/migrations/`, `scripts/reingest_corpus.py --blue-green`).
- **Reuse mature parsers:** correct, and PyYAML is already installed (`shared/pyproject.toml:11`). Its `compose()` marks
  give character offsets, so generic YAML needs no new dependency.

## 3. Drift since 2026-09-18 (repository truth wins)

| Packet assumption | Repository today | What to do |
|---|---|---|
| Public modes are HYBRID / GRAPH / WILDCARD (`03a` laws) | FAST and GNN are public too (since 2026-09-22). FAST = lanes A + B only: no depth lanes and **no sparse lane**, so exact-symbol lookups there are dense-only. GNN = its own route only. | The structure lane joins HYBRID / GRAPH / WILDCARD. Add its flag to `_DEPTH_LANES_OFF` (`chat_retrieval.py:707`) and to the `_retrieve_gnn` override (`:765`). |
| "One cross-encoder call per turn" (FUS-03) | Already false: WILDCARD validations (`chat_retrieval.py:980`) and the WLK2C bridge pass (`ui.py:2180`, 1 + n_bridges judge calls). | Restate FUS-03 as "one relevance judgement surface; extra judge calls only in declared passes". |
| Code profile built from `DocumentFingerprint` (§16, contracts §10) | The live profile path is the legacy lean context + prompt v3.2 (`POLYMATH_DOC_PROFILE_VNEXT=0`, because vNext produced thin profiles). `fingerprint.py` is unused. | C7 feeds the live prompt slots (TITLE / HEADINGS / EVIDENCE) from a deterministic code builder at `workers/workers/doc_profile_worker.py:237-253`. No new prompt at first. |
| pMAP process = `doc_parent_map_worker` | The live process is `doc_parent_map_stage_worker` (4 slots). `doc_parent_map_worker.py` is the library (`run_document_mapping` :344-547). | Dispatch at the 3 skeleton call sites (§5, C6). |
| New reconciliation keys in `worker_contracts()` (§31.5) | Any change there makes a successor for EVERY open run (`reconciliation.py:102-171`) and flags every live corpus stale on re-ingest (`reingest_corpus.py:66-68`). pMAP / profile are not in `STAGE_CONTRACT_DEPENDENCIES` (`:55-78`). | Carry the code contract in each code document's `chunk_contract_version`, and version code prompts at the receipt level. No fleet-wide keys. |
| A materializer "registry" to extend (§5.1) | Two dicts + an if-chain (`materializer.py:38-57, 152-168`). The record schema is strict (`format` enum, `additionalProperties:false`), and version 1.1.0 is pinned by a test. | Map the code extensions to `text` so they reuse `_materialize_text`; no schema or version change. |
| Chunk provider chosen per document (§2.1) | One global setting, `settings.worker.chunker` (tier_v3), read at `intake_worker.py:194-219`. | Add a per-document branch there, behind a flag. |
| Field name `source_family` | Already a frontmatter key with a different vocabulary (`frontmatter.py:18`). | Name the new field differently (e.g. `source_kind`) or namespace it. |
| Subqueries / fusion as of 09-18 | Up to 10 typed subqueries now search, including PROFILE and BRIDGE (11.408). The WLK2C portfolio can seat up to ~10 of 15 complementary chunks. The owner's q0 top-k floor is unbuilt. | CRITIQUE / GENERATE bundles need an implementation floor, so bridges cannot displace the code under review. |

## 4. What happens to code files TODAY (why a flag gate is mandatory)

- **`/upload`** accepts only .md / .txt / .html / .pdf / .epub / .docx. `.py` / `.lua` / `.luau` / `.yaml` / `.yml` get a 422
  (`orchestrator/orchestrator/api/ui.py:457, 478-481`). The same allowlist lives in `frontend-v2/src/screens/Files.tsx:9`
  and `manifest.py:38-47`.
- **`/intake`** (`api/intake.py:33-47`) has no extension check. A `.py` sent as `text/plain` is materialized as text and
  **tier_v3 damages it**:
  - every `# comment` becomes a Markdown heading (lines are stripped before the heading regex, `tier_chunker.py:52,
    103-104`);
  - short sections holding `class X:` or imports are dropped as stubs.
- **Region roles** can mark code `index` or YAML `noise_ocr`, which excludes it from pMAP (`chunk_kind.py:118, 174-183`;
  `document_region.py:79-80`). `ROLE_CODE` is not noise, so **LLM fact extraction runs on code today**
  (`llm_provider.py:102`).

## 5. Per-slice map

Verdicts: REUSE = exists; EXTEND = small additive change at a named seam; NEW = new module; RISK = conflicts with an invariant
or needs a decision.

| Slice | Verdict | Seam and smallest-change path | Risks / notes |
|---|---|---|---|
| **C0** baseline | REUSE | Frozen-plan replay harnesses (`docs/wiki/experiments/…/replay_owner_plans.py`), determinism suites, the live contract check (`frontend-v2/src/__tests__/live-contract.test.ts`). | Run suites with `-k "not test_live_"`: `test_live_*` calls :7200 with real model calls. |
| **C1** detection / materialization | EXTEND + RISK | Widen 3 allowlists; `EXTENSION_FALLBACK` → text; new pure `source_detection.py`; additive columns in migration 0067; a flag so admitted code never falls into tier_v3. | Frontmatter harvesting of YAML that starts with `---`; the `source_family` name clash; no repo importer (§6.2). |
| **C2** structure store | NEW | Tables patterned on `0054_document_parent_maps.sql`: content-hash PK, document FK with CASCADE, partial "one active" unique index. Migrations are replayed on every `make db-migrate` (`Makefile:28-32`), so they must be idempotent (`IF NOT EXISTS`). Next number: 0067. | `chunks` has no per-chunk metadata column, so symbol ↔ chunk links need their own table. |
| **C3** Python | NEW | LibCST (not installed; declare it in `shared/pyproject.toml`). Provider `ast_code_v1` at `intake_worker.py:194`. It writes its own `chunk_contract_version` (purge and blue/green visibility key on it) and skips or versions the region-role recompute (`:350-365`). | Parser install; the exact-substring validator reused as-is. |
| **C4** Luau | NEW | tree-sitter + tree-sitter-luau for spans; `luau-analyze` for validation. | None of it is installed; check wheel availability first. |
| **C5** YAML | EXTEND | PyYAML `compose()` offsets; provider `structured_yaml_v1`. | — |
| **C5** Power Apps / Power Fx | RISK | Needs .NET + `microsoft/Power-Fx` (not installed; `node` / `npm` present) → a small .NET CLI or sidecar. | Defer to Phase 3. |
| **C6** code pMAP | EXTEND | A family dispatcher wrapping `build_parent_skeletons` at its 3 call sites (`doc_parent_map_worker.py:366`, stage worker `:181`, `scripts/parent_map_backfill.py:238`). An optional `facts` field is rendered, counted and hashed only when non-empty (`map_prompt.py:76-90`, `map_batches.py:96-110`, `parent_skeleton.py:375-398`), so documents stay byte-identical. A `family` argument on `build_map_prompt` (`map_prompt.py:117`), bound in `_make_pmap_infer` (stage worker `:125`). | Prose assumptions break on code: the compiler splits fields on `\|` and `;` (`map_compiler.py:236, 185`), so `int \| None` corrupts a map; it strips `_` (`:78`), so `__init__` → `init`; the compact heading keeps only 80 characters (`parent_map_projection.py:34, 60-61`); excerpts are sentence-centric; the word regex splits snake_case. The code prompt must forbid `\|` and `;` inside fields, and the heading must keep the leaf symbol. |
| **C7** code profile / atoms | EXTEND | A deterministic code builder feeds the live prompt slots, dispatched at `doc_profile_worker.py:237-253`. No compiler or surface-registry change. | **Capacity:** one profile call per file (~40 s, 250 per day per Groq key; only `profile_groq1` + OpenRouter are pinned). 1,000 files ≈ 4 days on one key, so more profile lanes or a per-corpus cap are needed. v3.2 produces only THEORY / CONCEPT / SEEALSO atoms. |
| **C8** structure projection | NEW (existing patterns) | Auto-mint like `map_trigger.py:45-62` + `control/control/scheduler.py:301-367`, registered in `NON_BLOCKING_STAGES` (`tickets.py:63-77`; **mandatory**, or `generation_barrier` blocks promotion). Free-text receipt kinds; the unused `projection_reconcile.py:44-61`. | `reconcile_neo4j` (`verify_worker.py:392-523`) will not prune `Code*` nodes, so a separate reconcile is needed. **Recommend deferring** the Neo4j part: the lane can traverse Postgres edges with a bounded recursive query. |
| **C9** `code_task` | EXTEND | Pure `code_task.py` beside intent, set where the plan is built (`chat_plan.py:233, 499`), with an additive `ChatPlan.code_task`, receipted through `plan_receipt` (`:642-653`). Its own flag, not the intent-policy flag. | Exact-term regexes miss CamelCase / dotted / snake_case / backticked names (`chat_plan.py:109-115`; `query_intent.py:58` needs a digit). Code phrasing misfires ("configured" → PROCEDURE, "between…and" → RELATIONSHIP). |
| **C10** structure lane | EXTEND | Copy lane E's shape (the H / I lane recipe: arrival constant, `*_enabled` flag + env knob, closure in `chat_retrieve_v2`, fail-open trace, funnel keys, test pin). Return only `{doc_id, parent_id, symbol_id, route_reason}`; the engine hydrates the original children (`candidate_engine.py:836-847`). | The extra lanes D–I run **sequentially, outside `lane_deadline_s`** (`candidate_engine.py:793-925`), so wrap this one in a deadline. `CandidateEvidence` has no metadata field (`:398-432`): a route reason needs a field, a union merge and a `to_row` change. |
| **C11** candidate roles | EXTEND | Typed subqueries ("implementation", "reference") plus the existing aspect prefix seats (`candidate_engine.py:1434-1441`) already give pre-rerank class floors with no engine change. The role goes beside `synthesis_role` (`chat_retrieval.py:626`). | **Existing bug to fix first:** `ui.py:3519-3523` rebuilds evidence rows as `{chunk_id, doc_id, parent_id}`, then `:3631` reads `role` from them, so evidence-role labels never reach the prompt in live chat. The composer's slot names are pinned by `test_u1_intent_routing_contract.py:89-100`, so floors go before the rerank. |
| **C12** readiness / control | EXTEND | Add a sibling `"code"` verdict in `semantic_readiness.py` (`:218`) and per-document blockers in `document_status.py`; the legacy verdict stays untouched. Blue/green needs the code contract label passed through (`reingest_corpus.py:82, 93` hardcode tier_v3). | — |
| **C13** validators | NEW | Python: `ast` / `compile` + ruff; YAML: PyYAML. Attach after `answer_text` (`ui.py:3878`) and receipt under `generation`, which is already whitelisted (`query_receipts.py:50`). | Luau / Power Fx report VALIDATION_DEGRADED until their tools exist. |
| Frontend | EXTEND | A code view in `EvidenceInspector` (monospace, line numbers, symbol path; backend previews are 220 chars today, `ui.py:3685`), plus a `LaneTable` alias. Answer code blocks already render in monospace; there is no syntax highlighting. | Keep the structure lane out of `ROUTING_LANES` (`EvidenceInspector.tsx:17`): its rows are real source. |

## 6. Gaps the packet does not cover

1. **LLM fact extraction on code.** The packet is silent; today `extract` would run on code, which costs money and puts
   code "facts" into the semantic graph. Recommendation: skip `extract` for code documents, or run it on docstrings only.
   That is one guard in the extract path.
2. **Getting a repository in.** Upload is per-file with a 6-extension allowlist, and there is no folder / zip / repo import.
   `source_name` is a bare filename, so the repository-relative paths the packet's heading paths depend on
   (`api → auth.py → AuthService`) are lost. A repo importer (CLI or API) that preserves relative paths belongs in C1.
3. **Mixed corpora.** Chat is single-corpus, so "code + my books" means code and books in the same corpus. Supported;
   document it.
4. **Embedding / reranker fit for code.** Qwen3-Embedding-0.6B and Qwen3-Reranker-0.6B are general models; the reranker
   truncates pairs at 384 tokens, and code chunks can be longer. Measure in C0 / C3 before promising the EXACT / STR gates.
5. **The q0 top-k floor** (owner design, still unbuilt) matters more for code. Without it, bridge seating can crowd out
   the implementation under review.

## 7. Recommended execution (next session, after compaction)

- **Phase 1 — Python + generic YAML, end to end:**
  - C0;
  - C1 (flag + repo importer);
  - C2;
  - C3;
  - C5-YAML;
  - C6;
  - C7 (live prompt slots);
  - C9;
  - C10 (Postgres traversal);
  - the role-bug fix, then C11;
  - C12;
  - C13 (Python / YAML).

  Qualify on a real Python repository plus a real YAML config set. Roughly 12–15 slices, each with its own work-log and
  tests.
- **Phase 2 — Luau:** tree-sitter-luau + `luau-analyze`, Roblox idioms (GetService, RemoteEvent, `require`).
- **Phase 3 — Power Apps / Power Fx:** a .NET sidecar, and the C8 Neo4j projection if the structural queries need it.

## 8. Owner decisions needed before C1

1. Skip LLM fact extraction for code documents? *(recommended: yes)*
2. Carry code contracts per document (`chunk_contract_version` + receipt-level prompt versions) instead of fleet-wide
   `worker_contracts()` keys? *(recommended: yes; the alternative marks every live corpus stale)*
3. Materialize code as `format: "text"` (no schema change)? *(recommended: yes)*
4. Power Fx: install .NET and a sidecar now, or defer Power Apps to Phase 3? *(recommended: defer)*
5. Neo4j code projection: defer, with bounded Postgres traversal first? *(recommended: yes)*
6. Profile capacity: add profile lanes (Groq keys / Cloudflare), or cap files per corpus for the first code corpus?
7. Build a repository importer that preserves relative paths as part of C1? *(recommended: yes)*
8. Which real code for qualification: the Roblox project, a Power Apps export, a Python repository?

## 9. Independent findings (not part of this plan)

- **The evidence-role labels never reach the answer prompt** in live chat (`ui.py:3519-3523` drops `role` before `:3631`
  reads it). The P8b feature has been inert; its test passes a hand-built bundle
  (`tests/determinism/test_chat_synthesis.py:318-332`).
- **The extra lanes D–I run one after another, outside `lane_deadline_s`** (`candidate_engine.py:793-925`), and
  `dualread_budget_ms` is never read (`:270`). This is the likely cause of the ~10 s the chat retrieval step spends beyond
  the search itself (17–20 s observed, against 5–8 s in the replay).

## 10. Addendum — the owner's second design note (2026-09-23)

The note is saved verbatim at `docs/code-knowledge-v1/ADDENDUM_2026-09-23_OWNER_NOTE.md`. It mostly **agrees** with the packet,
**conflicts** with it in three places, and **adds** six things the packet lacks.

### Agrees (no change to the plan)
- Extend the document RAG rather than build a second system.
- One universal code layer that every language parser feeds (the packet's StructureManifest).
- AST-bounded CodeUnits that keep the parent/child model (CODE-CHUNK-V1).
- Power Apps parsed twice: the YAML structure, then the embedded Power Fx with Microsoft's own parser and binder
  (POWERAPPS-STRUCTURE-V1 + POWERFX-ANALYSIS-V1).
- Deterministic parsing owns references; the LLM owns behavior / purpose (laws 1.3 / 1.4).
- Code and document branches fused before the LLM (C11 roles + typed subqueries).
- ASK / DEBUG / REFACTOR / DESIGN routing (the `code_task` vocabulary).

### Conflicts, with recommendations

| The note says | The packet says | Recommendation |
|---|---|---|
| Add an explicit **IMPACT retrieval mode** (a 4th mode). | No new public mode; IMPACT is a `code_task` that turns on reverse-caller traversal. | Keep IMPACT as an **auto-detected `code_task`**: same behavior ("what breaks if I change X"), no new mode or selector. *(Owner decision 9.)* |
| **FAST for code = symbol lookup**, no vector search. | FAST is lanes A + B, dense-only with no sparse lane, so exact symbols are weak in FAST today. | Let FAST use the structure lane's **exact-symbol lookup only**, not its traversal: deterministic and cheaper than dense search. *(Decision 10.)* |
| A **heterogeneous graph** with document↔code edges (Requirement IMPLEMENTS Screen, SOP ENFORCED_BY Formula, Doc DESCRIBES Function). | Keep code edges separate from semantic Fact / Entity edges. | Two tiers. **Deterministic identifier links first**: a formula calling `Patch` ↔ corpus entities / terms named Patch; needs the C8 projection, Phase 2. **Inferred links** (IMPLEMENTS / ENFORCED_BY) are LLM inference, so label them routing-only, never evidence, and gate them on evaluation. Phase 1 already gets the retrieval payoff (Patch documentation next to the formula) through typed REFERENCE subqueries and resolution lift from code identifiers, with no graph edges. *(Decision 11.)* |

### Additions — where they land

- **Multiple representations per CodeUnit** (source = evidence; structural + semantic = embedded). In this system the
  semantic form is the pMAP routing signature + hooks. The structural form can ride the same pMAP embedding: include the
  deterministic facts in the projection text for code families only (`parent_map_projection.py`; documents stay
  byte-identical). **Phase 1 (C6)**, measured with and without.
- **Power Apps App Model**: screens, controls, navigation, variables, collections, named formulas, data sources, forms,
  galleries, and the derived control / variable / navigation / data-flow graphs. It is an app-level aggregate over
  per-screen manifests and needs cross-file resolution (C8). **Phase 3.**
- **Living code corpora (re-index changed files).** A requirement the packet misses. `doc_id` = sha256 of the bytes, so
  an edited file becomes a NEW document while the old one stays. The repository importer must **sync by relative path**
  (add / replace / delete) and retire the old version through DOCUMENT-DELETE-V1. **Phase 1 (C1).** *(Decision 13.)*
- **Canvas Authoring MCP for write validation** (verified: Microsoft ships `Microsoft.PowerApps.CanvasAuthoring.McpServer`).
  It lists and describes controls, discovers data sources, validates / compiles `.pa.yaml` and syncs with Studio. It
  requires an open Power Apps Studio co-authoring session and the .NET 10 SDK. Use it in C13 for Power Apps writes. It
  cannot serve unattended ingestion, which still needs the Power Fx parser offline. Phase 3 needs .NET either way.
  **Phase 3.** *(Decision 12.)*
- **`.pa.yaml` contract** (add to POWERAPPS-STRUCTURE-V1):
  - detect the schema version;
  - preserve unknown nodes;
  - never rewrite destructively;
  - parse formulas separately;
  - require Canvas MCP validation for writes.

  `.fx.yaml` is retired. External edits are supported only through Power Platform Git integration. **Phase 3.**
- **Agent workflow**: detect → app model → retrieve → expand graph → retrieve target → retrieve docs → build delta →
  impact → plan → generate → validate → re-index → diff graph → report. It is a harness workflow over Polymath's MCP
  surface and needs code tools on MCP (locate / impact / validate) plus the sync importer. **Phase 4.**

### Five more owner decisions (with §8, 13 in total)

9. IMPACT: an auto-detected `code_task` *(recommended)*, or a public 4th mode?
10. FAST for code: allow exact-symbol lookup *(recommended)*?
11. Document↔code graph links: deterministic identifier links first, inferred links only after evaluation *(recommended)*?
12. Power Apps write validation through Microsoft's Canvas MCP (Studio session + .NET 10) in Phase 3 *(recommended)*?
13. A sync importer (replace by path) in Phase 1 *(recommended: code corpora change)*?

### Revised phases

- **Phase 1** (Python + generic YAML): §7, plus:
  - the sync importer;
  - structural facts in the code pMAP embedding (measured);
  - IMPACT as a `code_task` with bounded Postgres reverse traversal.
- **Phase 2** (Luau): plus deterministic document↔code identifier links, which needs the C8 projection.
- **Phase 3** (Power Apps):
  - .NET 10 for the Power Fx parser + Canvas MCP;
  - the App Model and derived graphs;
  - the `.pa.yaml` contract.
- **Phase 4** (agent workflow over MCP): code tools, re-index + graph diff, write validation loop.

Sources for the Canvas MCP facts:
- https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/create-canvas-external-tools
- https://libraries.io/nuget/Microsoft.PowerApps.CanvasAuthoring.McpServer
- https://github.com/microsoft/power-platform-skills/blob/main/plugins/canvas-apps/AGENTS.md

## 11. Parsers: existing open-source packages added to the repository, never written from scratch

Owner, 2026-09-23: "we are not building the parsers from scratch; repos already have it that are open source that we can add
into our repo." Every "NEW" parser item in §5 therefore means a THIN ADAPTER (source family → StructureManifest symbols /
edges / spans) around one of these packages. No grammar or parser code is written. Checked 2026-09-23:

| Language | Package (upstream) | Version | License | How it is added |
|---|---|---|---|---|
| Python | `libcst` (Instagram/LibCST) | 1.9.0 | MIT (small portions under the Python license) | pip wheel (macOS arm64 ✓); declare in `shared/pyproject.toml` |
| Luau (spans / AST) | `tree-sitter` + `tree-sitter-luau` (tree-sitter-grammars) | 0.26.0 + 1.2.0 | MIT | pip wheels ✓. Alternative: `tree-sitter-language-pack` 1.20.0 (MIT, many grammars) |
| Luau (validation) | `luau-lang/luau` release (`luau-analyze`, `luau`) | 0.739 | MIT | `luau-macos.zip` from GitHub releases, fetched by a pinned, checksummed setup script (not committed binaries) |
| YAML | PyYAML | installed (`shared/pyproject.toml:11`) | MIT | nothing to add (`compose()` gives offsets) |
| Power Fx | `Microsoft.PowerFx.Core` (microsoft/Power-Fx) | 1.8.1 | MIT | NuGet inside a small .NET CLI / sidecar (Phase 3; needs a .NET SDK) |
| Power Apps write validation | `Microsoft.PowerApps.CanvasAuthoring.McpServer` | NuGet | Microsoft | .NET 10 + an open Studio coauthoring session (Phase 3) |

The architecture references in the packet (SylphxAI/coderag, Aider-AI/aider, einad5/codegraph, ian000/graphify-go) are ideas
to study, not dependencies. PAR-05 still applies: record license, version and contract for each package in the slice that
adds it.

