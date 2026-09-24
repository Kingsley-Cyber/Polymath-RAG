---
change_id: CODE-KNOWLEDGE-V1-HYDRATION-LUAU-ORDER
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. Three owner decisions written into the CODE-KNOWLEDGE-V1 plan: (1) code is ranked by its descriptions and hydrated deterministically (exact code + bounded graph neighbourhood), never scored as text; two doors (semantic descriptions / exact symbol lookup); (2) Luau uses the official toolchain (luau-ast + luau-analyze) + Rojo, with tree-sitter-luau as fallback only; (3) the slice order becomes a walking skeleton (Python on this repository answers questions by step 6)."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1: deterministic hydration, the official Luau toolchain, a walking-skeleton order

## Contract
- **The owner, 2026-09-24:** "code should be treated as determinsitic hydration dont you thunk?we need to use the official
  luau rojo. if the semantic llm generation part win it is determinsitically retrieved with contexts, so the embedder and
  reranker not trained on code still work, i imagine this workflow with elite index and ingestions."
- **Agreed**, with four conditions:
  - keep an exact-name door;
  - coverage safety nets;
  - a hydration budget;
  - score balance through roles.
- The owner answered "yes write it into the plan", which also accepted the proposed Python-first reorder.

## Changes
- `docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md`:
  - new §13 (the rule; the two doors; the hydration rules per code task with a token budget; the coverage safety nets;
    the score balance; what C9 / C10 must measure);
  - layer 5 of §1 rewritten;
  - the Luau card's tooling (the official `luau-ast` + `luau-analyze`, Rojo + luau-lsp; tree-sitter-luau as fallback);
  - §8 item 1 (check `luau-ast` in the macOS release).
- `docs/wiki/plans/CODE-KNOWLEDGE-V1-START-HERE.md`:
  - the build paragraph (hydration);
  - two new rows in the decided table;
  - the slice table reordered into a walking skeleton (C0 → C1 → C2 → C3 → C6 + C7 → C9 + C10 = first answers → C4 → C5a →
    C8 → C11 → C12 → C13 → C5b → C14), with the reason.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1-SOURCES.md`:
  - luau-lang/luau is the Luau parser of record (`luau-ast`, CMake target `Luau.Ast.CLI`);
  - tree-sitter-luau is fallback / comparison;
  - Rojo is required for Luau.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`, `CONTINUITY-REPORT.md`: the decisions + "Next action: C0".
- The register (11.457) and the scaffold TREE.

## Proof
- **`luau-ast` exists** in the official build: `gh api repos/luau-lang/luau/contents/CMakeLists.txt` shows
  `add_executable(Luau.Ast.CLI)` (L66) with `OUTPUT_NAME luau-ast` (L74). The 0.739 release assets are `luau-macos.zip`,
  `luau-ubuntu.zip`, `luau-windows.zip` and `Luau.Web.js`. Whether the zip contains `luau-ast` is a C0 check.
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "The reranker must learn to judge code": under hydration it never judges raw code. It judges descriptions (English),
  and the code is attached by rule.
- "Descriptions alone are enough": an exact-name door and the plain code-search fallback stay, so a missed description
  never makes code unreachable.

## Open contract gaps
- **C0:** `luau-ast` availability on macOS; the hydration token budget method; the capacity measurement.
- **The owner's Roblox game** (folder + format) before C4.
