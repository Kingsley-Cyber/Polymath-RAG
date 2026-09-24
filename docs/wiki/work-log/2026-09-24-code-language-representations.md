---
change_id: CODE-LANGUAGE-REPRESENTATIONS-V1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. A new plan document gives each code language (Python, YAML, TOML, Luau/Roblox, Power Fx) a representation card that CODE-KNOWLEDGE-V1 slices C1–C7, C10, C13 and C14 implement: detection, tooling, units and addresses, the symbol / relation vocabulary with resolution rules, file- and parent-level meaning fields, search vocabulary, validation and test questions. No schema change, no code, no fleet change."
last_reviewed: 2026-09-24
---

# CODE-LANGUAGE-REPRESENTATIONS-V1: one representation card per code language

## Contract
- The owner, 2026-09-24: "i dont want to mess with the backend that works instead build upon it in a proper manner, where
  it detects and makes the code go through the rag pipeline, its graph can be made determisniticaly, we can use the same
  llm to power meaninign and routing layers … but we need to plan it so that each coding language has proper
  representations, idk if theirs a plan for that".
- CODE-KNOWLEDGE-V1 (11.452): the packet's §6 / §8 and the schema §4–§6, plus the owner's decisions of 2026-09-24:
  - the first version covers Python, YAML / TOML, Luau / Roblox and Power Fx;
  - enrichment at file + class level in the pMAP / profile style;
  - parsers only;
  - one pipeline.

## Changes
- `docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md` (new):
  - §1: five layers for every language (exact source, units, deterministic graph, meaning, routing), with the shared
    rules: evidence only from exact source; summaries as ORIENTATION; no graph guessing; the meaning layer fed the unit's
    links; the owner's common fields; selection; search vocabulary; no LLM detection.
  - §2–§6: the cards for Python, YAML, TOML, Luau / Roblox and Power Fx.
  - §7: links across languages.
  - §8: what C0 verifies.
  - §9: the slice mapping.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`: read-order item 4 + a status row.
- `docs/wiki/plans/CONTINUITY-REPORT.md`: the CURRENT block names the spec.
- The register (11.453) and the scaffold TREE.

## Proof
- **Grounded in the packet, read directly:**
  - P01 §6 (the parser lists per language, the `SourceAdapterPlan` registry);
  - P01 §8 (the parent / child rules, `heading_path` examples, the chunk providers);
  - P01 §34 (validation);
  - P03 §4–§6 (`code_symbols` with free `symbol_kind` + `attributes` JSONB; `code_edges` with free `relation` +
    `resolution` / `confidence` / `provenance`; `code_symbol_parent_links`) and §9 (the `CODE_*` Neo4j names);
  - P03a (the source plans per extension, the Lua / Luau policy, the Power Apps detector).
- **No schema change:** every new symbol kind, relation and attribute fits the existing free-text / JSONB columns as a
  controlled vocabulary.
- **Tool status is marked honestly.**
  - Verified by the 2026-09-23 review (§11): LibCST, tree-sitter + tree-sitter-luau, luau-analyze, PyYAML,
    Microsoft.PowerFx.Core.
  - "Evaluate in C0": scip-python / pyright-class resolution, Rojo sourcemap + luau-lsp, span-preserving TOML readers,
    ruamel.yaml / tree-sitter-yaml, the Power Apps export format, a code embedding model.
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "Each language needs its own pipeline": one pipeline; only the front door (detection + parsing) and the meaning prompt
  addendum are per language.
- "An LLM can fill graph gaps": links come from parsers and analyzers only. What they cannot resolve is stored as
  `unresolved` / `ambiguous`.

## Open contract gaps
- **The owner's real-code inputs** (reconciliation 2026-09-24 §7), above all the Roblox project format: Rojo files or a
  place file.
- **The C0 verifications** (§8 of the spec) decide the tool choices that are still marked "evaluate".
