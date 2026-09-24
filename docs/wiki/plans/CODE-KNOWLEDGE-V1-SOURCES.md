---
title: "CODE-KNOWLEDGE-V1 — GitHub sources: what we pull, what we only study, what we reject, and why"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "PLAN — verified against the GitHub API on 2026-09-24 (licence, archived flag, last push, latest release); CodeGraphContext, Graphify and Ruff added the same day from reviews A + B (register 11.455). Nothing is installed by this document; each slice pins and records what it adds (PAR-05)."
owner: "@king"
scope: "Documents only. The external source list for CODE-KNOWLEDGE-V1 and CODE-LANGUAGE-REPRESENTATIONS-V1."
---

# CODE-KNOWLEDGE-V1 — GitHub sources

**Owner, 2026-09-24:** "you need github soruces list to reference to pull and reason why".

**Rule** (the owner's, 2026-09-23 and 2026-09-24): no parser, grammar or resolver is written from scratch where a
maintained open-source one exists. Thin adapters wrap mature tooling.

How a source is used:
- **PULL:** a pinned dependency (pip wheel, a checksummed binary release, or NuGet). The slice that adds it records the
  version, licence and contract.
- **STUDY:** we read it for ideas. No code is copied; any reuse of a file happens only under its licence, with
  attribution, decided in the slice.
- **REJECT:** not used, with the reason.

**Licences:**
- MIT / Apache-2.0: fine to pull.
- MPL-2.0 tools are used as unmodified external binaries (file-level copyleft only binds modified files).
- GPL, no-licence and archived repositories are not pulled.

**Verified 2026-09-24** with the GitHub API (`gh api repos/…`): licence (LICENSE text read where GitHub reports
NOASSERTION), stars, archived flag, last push, latest release.

## A. Reading code (parsers) — PULL

| Repository | Licence | Version (2026-09-24) | Why this one | How pulled | Slice |
|---|---|---|---|---|---|
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) + [tree-sitter/py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter) | MIT | 0.27.0 / bindings 0.26.0 | One incremental, error-tolerant parser engine for every grammar, with exact byte / line spans; the industry standard for editors and code navigation (27k★). One engine means one adapter pattern for Luau, YAML, TOML and chunk boundaries | pip wheels | C1, C4, C5a |
| [tree-sitter-grammars/tree-sitter-luau](https://github.com/tree-sitter-grammars/tree-sitter-luau) | MIT | v1.2.0 (last push 2026-09-13) | The maintained Luau grammar (types, generics, `--!strict`). The only mature Luau parser usable from Python; gives the units and spans of the Luau card | pip wheel | C4 |
| [tree-sitter-grammars/tree-sitter-yaml](https://github.com/tree-sitter-grammars/tree-sitter-yaml) | MIT | v0.7.2 | YAML with spans, comments, anchors and aliases, which PyYAML's compose does not keep. C0 compares it with PyYAML | pip wheel | C5a |
| [tree-sitter-grammars/tree-sitter-toml](https://github.com/tree-sitter-grammars/tree-sitter-toml) | MIT | v0.7.0 | TOML with spans; stdlib `tomllib` has values but no positions | pip wheel | C5a |
| [xberg-io/tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) | MIT | v1.20.0 (moved from Goldziher/) | An ALTERNATIVE to the four single grammars: one wheel with 100+ grammars (fewer pins, easy new languages). C0 picks single grammars or the pack | pip wheel | C0 decision |
| [Instagram/LibCST](https://github.com/Instagram/LibCST) | MIT (small parts PSF) | v1.9.0 | Python's lossless syntax tree + metadata providers (qualified names, scopes, positions): exact spans and deterministic names, the core of the Python card | pip wheel | C3 |
| [yaml/pyyaml](https://github.com/yaml/pyyaml) | MIT | 6.0.3 | Already installed; `compose()` gives node positions. The YAML baseline | installed | C5a |
| [python-poetry/tomlkit](https://github.com/python-poetry/tomlkit) | MIT | 0.15.1 | Style-preserving TOML read / write, for generation validators that must edit TOML without reformatting it | pip wheel | C13 (optional) |
| [luau-lang/luau](https://github.com/luau-lang/luau) | MIT | 0.739 (2026-09-18) | The official Luau toolchain: `luau-analyze` type-checks and lints, and gives the Luau validation and type facts | checksummed binary release, pinned setup script | C4, C13 |
| [microsoft/Power-Fx](https://github.com/microsoft/Power-Fx) | MIT | NuGet `Microsoft.PowerFx.Core` 1.8.1 (GitHub releases stop at 1.2.0; NuGet is the release channel) | The same Power Fx parser / binder Power Apps uses, so formula links come from a real binder, never a regex | NuGet inside a small .NET sidecar (.NET install needs the owner's OK) | C5b |
| [microsoft/PowerApps-Tooling](https://github.com/microsoft/PowerApps-Tooling) | MIT | no releases; active | ONLY its `schemas/`, the Power Apps YAML schema, to validate `.pa.yaml`. Its PASopa `.msapp` unpacker is "legacy … no longer supported" (its README); source comes from Power Platform Git integration instead | files pinned by commit | C5b |

## B. Linking code precisely (resolvers, indexers, validators) — PULL or EVALUATE in C0

| Repository | Licence | Version | Why | How | Slice |
|---|---|---|---|---|---|
| [rojo-rbx/rojo](https://github.com/rojo-rbx/rojo) | MPL-2.0 | v7.7.0 | Roblox's standard file ↔ instance mapping. `rojo sourcemap` builds the instance tree that resolves `require(script.Parent.X)`, and its naming convention gives script kinds (server / client / module) | unmodified binary | C0, C4 |
| [JohnnyMorganz/luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) | MIT | 1.70.0 (2026-09-20) | The standard Luau language server. With a Rojo sourcemap it resolves requires and Roblox types; the candidate Luau resolver for the REQUIRES / CALLS links | unmodified binary | C0 (evaluate), C4 |
| [lune-org/lune](https://github.com/lune-org/lune) + [rojo-rbx/rbx-dom](https://github.com/rojo-rbx/rbx-dom) | MPL-2.0 / MIT | v0.10.5 / active | ONLY if the game lives in a place file (`.rbxl` / `.rbxlx`): Lune's roblox library (built on rbx-dom) reads place files to export the scripts as files | unmodified binary | C0 (conditional) |
| [Kampfkarren/selene](https://github.com/Kampfkarren/selene) | MPL-2.0 | 0.31.0 | Roblox-aware Luau linter, a validator where the project configures it | unmodified binary | C13 |
| [sourcegraph/scip-python](https://github.com/sourcegraph/scip-python) | MIT | no GitHub releases (npm) | Precise cross-file Python definitions / references (pyright-based) in the SCIP format. C0 compares it with LibCST-only resolution on this repository | npm package | C0 (evaluate) |
| [scip-code/scip](https://github.com/scip-code/scip) | Apache-2.0 | v0.10.0 (moved from sourcegraph/) | The SCIP index format + CLI to read scip-python's output | binary / proto | C0 (with scip-python) |
| [microsoft/pyright](https://github.com/microsoft/pyright) | MIT | 1.1.414 | The type checker behind scip-python, and a Python validator where the repository configures it | npm / pip wrapper | C0, C13 |
| [davidhalter/jedi](https://github.com/davidhalter/jedi) | MIT | active | A lighter Python resolver: the fallback if scip-python is too heavy | pip | C0 (evaluate) |
| [astral-sh/ruff](https://github.com/astral-sh/ruff) | MIT | 0.16.8 (2026-09-16) | The standard Python linter: its findings are real diagnostics (layer 3b), the facts behind "issue identification" (review A). It is already the repository's own linter | pip wheel | C13 |
| [CodeGraphContext/CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | MIT | v0.5.7 (2026-08-08), 4.2k★ | "An MCP server plus a CLI tool that indexes local code into a graph database" (Neo4j support, optional SCIP). We evaluate its EXTRACTION components against our adapters on the same files before writing equivalents. Its pipeline is not adopted (it would be a second system), and its Lua support is not Luau support (review A) | pip, evaluation only | C0 (evaluate) |
| [microsoft/multilspy](https://github.com/microsoft/multilspy) | MIT | v0.1.0 | A Python client that drives language servers for definition / reference queries, used only if C0 chooses LSP-based resolution. Its luau-lsp support is unverified | pip | C0 (evaluate) |

## C. Code-RAG implementations — STUDY (ideas, no code pulled)

| Repository | Licence | Status | What we take from it |
|---|---|---|---|
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | Apache-2.0 | 49k★; last push 2026-05, release v0.86.0 (2025-08) | **The repo map:** tree-sitter tag queries (definitions / references) + PageRank over the reference graph rank the important symbols. We use the idea to order which classes get enrichment first, and to answer "big picture" questions. Its per-language tag queries may be reusable under Apache-2.0 with attribution (decided in C4 / C5a) |
| [vitali87/code-graph-rag](https://github.com/vitali87/code-graph-rag) | MIT | 5.2k★, active (v0.0.945, 2026-09-16) | The closest open-source analogue of this plan: tree-sitter → code knowledge graph → natural-language queries across languages. Compare its node / edge schema and multi-language adapters with our cards before C2 freezes the vocabularies |
| [zilliztech/claude-context](https://github.com/zilliztech/claude-context) | MIT | 12.5k★ | Code search over MCP for agents: AST chunking, hybrid search, incremental re-indexing by file hashes. Reference for the later MCP code tools and for the importer's sync-by-path |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | Apache-2.0 | 121k★, v0.9.67 (the owner has `graphifyy` 0.9.53 installed) | Its MCP access and Neo4j export / push are patterns to study for C8 and the MCP phase (review B). **Not a Luau parser:** the installed `extract.py` maps `.luau` to its plain-Lua extractor (lines 2327, 5400, verified 2026-09-24), which does not read Luau type syntax |
| [oraios/serena](https://github.com/oraios/serena) | MIT per component | 29.7k★, v1.7.0 | Symbol-level retrieval for agents through language servers (find a symbol, find referencing symbols). Reference for the later `get_symbol` / references MCP tools |
| [run-llama/llama_index](https://github.com/run-llama/llama_index) | MIT | active | Its tree-sitter `CodeSplitter`: reference for splitting an oversized function on syntax boundaries |
| [continuedev/continue](https://github.com/continuedev/continue) | Apache-2.0 | active | Codebase indexing (tree-sitter chunks + embeddings + a repo map): reference |
| [SylphxAI/locus](https://github.com/SylphxAI/locus) | MIT | 12★ (the packet's `SylphxAI/coderag`, renamed) | The packet's reference; small, low priority |
| [einad5/codegraph](https://github.com/einad5/codegraph) | Apache-2.0 | 0★ | The packet's reference; negligible adoption; ideas only |

## D. Rejected

| Repository | Reason |
|---|---|
| [github/stack-graphs](https://github.com/github/stack-graphs) | ARCHIVED (2025) |
| [universal-ctags/ctags](https://github.com/universal-ctags/ctags) | GPL-2.0; tree-sitter tag queries do the same job under MIT |
| [ian000/graphify-go](https://github.com/ian000/graphify-go) | no licence (all rights reserved), so its code cannot be reused; the packet's idea reference only |
| sourcegraph/cody | the repository is no longer public (404 on 2026-09-24) |
| PowerApps-Tooling's PASopa unpacker | legacy and unsupported per its own README; use Power Platform Git integration exports |

## E. Not on GitHub, measured in C0

- **A code embedding model:** only if Qwen3-Embedding on enriched code text misses (CODE-LANGUAGE-REPRESENTATIONS-V1 §8
  item 6).
- **ruamel.yaml** (hosted on SourceForge, MIT): a comment- and anchor-preserving YAML alternative to compare with
  tree-sitter-yaml.
