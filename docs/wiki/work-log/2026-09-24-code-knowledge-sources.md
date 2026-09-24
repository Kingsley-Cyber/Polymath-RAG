---
change_id: CODE-KNOWLEDGE-V1-SOURCES
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. A verified list of the GitHub sources CODE-KNOWLEDGE-V1 pulls, evaluates, studies or rejects, with the licence, version, reason and slice of each. Nothing installed."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1: the GitHub sources list, verified

## Contract
- The owner, 2026-09-24: "you need github soruces list to reference to pull and reason why".
- The standing rule (2026-09-23, 2026-09-24): no parser or resolver written from scratch where a maintained open-source
  one exists; thin adapters; each slice records the version, licence and contract of what it adds (PAR-05).

## Changes
- `docs/wiki/plans/CODE-KNOWLEDGE-V1-SOURCES.md` (new). Four groups, each row with the licence, version, reason, how it is
  brought in and the slice:
  - A: PULL parsers;
  - B: resolvers / indexers / validators (pull or evaluate in C0);
  - C: code-RAG implementations to study;
  - D: rejected.

  Plus E: what is not on GitHub.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`: read-order item 5 + a status row.
- `docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md` §8 points to the list.
- The register (11.454) and the scaffold TREE.

## Proof
- **36 candidates** were queried with `gh api repos/<owner>/<repo>` and `…/releases/latest` on 2026-09-24. For every
  repository GitHub reported as NOASSERTION (LibCST, scip-python, pyright, jedi, serena), the LICENSE text was read.
- **Findings that changed the list:**
  - SCIP moved to `scip-code/scip`.
  - The language pack moved to `xberg-io/tree-sitter-language-pack`.
  - The packet's `SylphxAI/coderag` is now `SylphxAI/locus`.
  - `sourcegraph/cody` returns 404.
  - `github/stack-graphs` is archived.
  - `universal-ctags` is GPL-2.0.
  - `ian000/graphify-go` has no licence.
  - PowerApps-Tooling's README calls its PASopa unpacker legacy and unsupported. Only its `schemas/` are kept.
  - Power-Fx's GitHub releases stop at 1.2.0 (2023); the maintained channel is NuGet (1.8.1, the 2026-09-23 review).
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "Adopt a whole open-source code-RAG system": each one brings its own index, ranking and answer path, i.e. a second
  pipeline beside Polymath. They are listed to STUDY (the repo map, schemas, MCP tool shapes), not to pull.

## Open contract gaps
- **The C0 evaluations** (group B) decide the Luau resolver (luau-lsp + Rojo sourcemap), the Python resolver
  (scip-python vs jedi vs LibCST-only) and single grammars vs the language pack.
- **multilspy's luau-lsp support** is unverified.
- **Aider's tag queries:** whether they cover Luau / YAML / TOML is checked in C4 / C5a.
