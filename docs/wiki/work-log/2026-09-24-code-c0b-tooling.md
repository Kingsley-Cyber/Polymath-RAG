---
change_id: CODE-KNOWLEDGE-V1-C0B-TOOLING
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Experiments + documents + one third-party fixture (MIT); no runtime change. The download-dependent half of C0: LibCST on this repository, the official Luau toolchain vs tree-sitter-luau on one real Roblox file, tree-sitter-toml spans. Tools ran in a throwaway venv under the session scratchpad, never the fleet .venv."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1 C0b: the parser runs

## Contract
- The owner, 2026-09-24: "you can downlaod the parsers, you can get a luaua roblox code file from github i dont have a
  roblox donwload file, just use 1 file." Roadmap `LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md` §3 row 1.
- Downloads: PyPI `libcst==1.9.0`, `tree-sitter==0.26.0`, `tree-sitter-toml==0.7.0`, `tree-sitter-luau==1.2.0` (+ PyYAML
  6.0.3 as LibCST's dependency) into a throwaway venv; GitHub release `luau-lang/luau` 0.739 `luau-macos.zip`
  (5,757,113 bytes, sha256 `f66cabc7…3ff3`, verified); one file from `Sleitnick/Knit` (MIT) at a pinned commit.

## Changes
`docs/wiki/experiments/code-knowledge-c0b-2026-09-24/`: `libcst_eval.py` → `libcst_eval.json`, `luau_eval.py` →
`luau_eval.json`, `toml_eval.py` → `toml_eval.json`, `fixtures/KnitServer.luau` + `Knit-LICENSE.txt` + `SOURCE.md`.

## Proof
- **Luau (EXECUTED):** the official zip ships `luau-ast` (6.96 MB) and `luau-analyze` (7.1 MB), native arm64: no source
  build needed. `luau-ast` parses the typed Knit file (exit 0; 42 node kinds; 11 functions = 10 `KnitServer.*` methods +
  1 local; 7 type aliases; 7 typed parameters; 2 type assertions; 6 interpolated strings; spans as 0-based
  `line,col - line,col`). Its 4 `require` calls: 2 index chains (`KnitServer.Util.Promise`, `KnitServer.Util.Comm`, which
  need the instance tree to resolve) and 2 computed (`require(v)` over children: stored `unresolved`). `luau-analyze`
  without Roblox definitions: exit 1, 10 diagnostics, all unknown Roblox globals / types (`Instance`, `script`, `task`,
  `Player`): Roblox validation needs luau-lsp's Roblox type definitions (C13). tree-sitter-luau 1.2.0 (fallback): 0 ERROR,
  0 MISSING, 11 functions, 7 type definitions on the same file.
- **Python (EXECUTED):** LibCST 1.9.0 parses all 944 tracked Python files with 0 errors in 84.8 s (parse +
  QualifiedNameProvider + PositionProvider). Top-level spans vs stdlib `ast`: 7,843 compared, start = the `def` / `class`
  line in 7,843 (NOT the first decorator: 7,357), end line equal in 7,843. Product-code callees: 4,292 resolve to a
  repository definition (C0a stdlib estimate: 4,287 without `self.` dispatch), 7,358 builtins, 2,451 external, 9,273
  named but not a repository definition (attribute calls on objects), 5 ambiguous, 2 unresolved.
- **TOML (EXECUTED):** tree-sitter-toml 0.7.0 on the 10 TOML files: 28 explicit headers with line spans, all 28 present
  in tomllib's structure, 0 ERROR, 0 MISSING.

**Decisions (C0 closed):**
| Question | Decision |
|---|---|
| Luau parser | the official `luau-ast` (release zip, checksum-pinned); tree-sitter-luau stays a fallback (it parsed this file too) |
| Luau validator | `luau-analyze` needs Roblox definitions: C13 uses luau-lsp's Roblox types (+ Rojo when a real project exists) |
| Python | LibCST for structure + names; the adapter adds `self.` dispatch by enclosing class; `obj.m()` stays `unresolved` |
| Python unit spans | the chunk provider extends a unit to its first decorator (LibCST starts at `def`) |
| TOML | tree-sitter-toml for spans, tomllib for values |

## Rejected claims
- "The macOS Luau release might need a source build": it ships `luau-ast`.
- "LibCST adds cross-file resolution beyond the import table": it matches the stdlib estimate (4,292 vs 4,287).

## Open contract gaps
- Rojo + luau-lsp wait for a real multi-file Roblox project (one file has no instance tree).
- LibCST joins the fleet `.venv` only in C3 (a dependency change); the Luau binaries get a checksum-pinned fetch script
  in C4.
