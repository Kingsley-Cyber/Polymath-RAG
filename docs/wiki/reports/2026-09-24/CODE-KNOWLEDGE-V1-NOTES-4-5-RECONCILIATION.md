---
title: "CODE-KNOWLEDGE-V1 — two design reviews (notes 4 + 5) reconciled; Neo4j moves into the first version"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "RECONCILED — both reviews admitted verbatim; the representation spec and the sources list updated; decision 5 changed by the owner (Neo4j projection in the first version)"
owner: "@king"
scope: "Documents only. Maps docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTES_4_5.md onto CODE-KNOWLEDGE-V1, CODE-LANGUAGE-REPRESENTATIONS-V1 and CODE-KNOWLEDGE-V1-SOURCES, against production a47d0ba."
---

# CODE-KNOWLEDGE-V1 — reviews A and B, reconciled

## 1. The one decision they reopened

**Review A:** "Your current plan explicitly defers Neo4j; that deferral conflicts with the outcome you've requested here."

- **Put to the owner:** "Both reviews say the code graph should also be loaded into Neo4j in the first version, not
  later. Should it?"
- **Owner, 2026-09-24:** "Yes, in the first version (Recommended)".
- **Decision 5** (feasibility review §8) becomes: **Postgres stays the authority, and a deterministic Neo4j projection
  (C8, `CodeDocument` / `CodeSymbol` / `CodeConfigPath` + `CODE_*` relationships, schema §9) ships in the first version,
  right after C2.** Code can then join GRAPH mode's hops and the graph views.

## 2. Verification (2026-09-24)

- **CodeGraphContext/CodeGraphContext:** MIT, 4.2k★, v0.5.7 (2026-08-08), active. It describes itself as "An MCP server
  plus a CLI tool that indexes local code into a graph database".
- **Graphify-Labs/graphify:** Apache-2.0, 121k★, v0.9.67 (2026-09-23), active.
  - **The owner's install is `graphifyy 0.9.53`.** Its `extract.py` maps `".luau": "lua"` (line 2327) and
    `".luau": extract_lua` (line 5400), confirming the review. Typed Luau goes through the plain-Lua extractor, which does
    not know Luau's type syntax.
- **astral-sh/ruff:** MIT, 49.7k★, 0.16.8 (2026-09-16).
- **ian000/graphify-go:** no licence (already REJECTED in the sources list). Review B adds that it lists no Luau.

## 3. Point by point

| Point | Verdict | Where it lands |
|---|---|---|
| Flow: parse / resolve → chunks + graph → AI routing → combined retrieval → cited synthesis | agrees | CODE-LANGUAGE-REPRESENTATIONS-V1 §1 (unchanged) |
| CodeGraphContext: evaluate its extraction before writing equivalents; its Lua ≠ Luau | new | sources list group B: EVALUATE in C0, extraction components only (its whole pipeline would be a second system) |
| Graphify as a component (MCP, Neo4j export / push); its Luau is partial | new, verified | sources list group C: STUDY its MCP and Neo4j export patterns; not a Luau parser |
| Python: LibCST + scip-python; Luau: tree-sitter-luau + luau-lsp + rbx-dom; YAML / TOML: PyYAML + tree-sitter-toml; Power Fx: Power-Fx | agrees | already in the sources list |
| Power Fx resolution needs the app's controls, variables and data sources | sharpened | Power Fx card: pass 1 builds the symbol table the pass-2 binder is given |
| Syntax ≠ resolved meaning; unresolved / ambiguous kept explicit | agrees | spec §1 (already) |
| Provenance on every link: project, source revision, file, span, rule; a pinned re-run reproduces the graph | partial → **added** | spec §1 layer 3: required edge attributes (`source_revision`, `span`, `rule`, `tool`, `tool_version`) + a reproducibility test in C2 |
| Roblox remotes matched by resolved instance identity, not names | sharpened | Luau card + §7: pairing by the remote's resolved instance path; a name-only match is `ambiguous` |
| A config string matching a function name is a possible reference, not proof | sharpened | YAML / TOML cards + §7: `ambiguous`, except where the dialect defines the field as an entrypoint (e.g. `[project.scripts]`) |
| Postgres authority → Neo4j projection now | **changed by the owner** | §1 above; spec §1 layer 3 + §9; the phase order (note-3 reconciliation §6) |
| Profile / pMAP descriptions embedded, linked to exact source | agrees | spec §1 layers 4–5 |
| Keep each discovery path through ranking | agrees → **added** | spec §1 layer 5: structure-lane candidates carry a readable path ("handles the remote fired by X") into the same path-aware judge as documents (SKELETON-ROUTING-V1.1) |
| Ingest real analyzer diagnostics (Ruff, Luau) as facts; AI failure modes are hypotheses | new → **added** | spec §1: a diagnostics layer (tool findings with rule, severity, span, tool version) + the meaning field "failure modes" labelled as hypotheses; sources: Ruff (PULL) |
| pMAP parents per language (incl. Luau event-handler groups) + routing descriptions | mostly agrees → **merged** | cards: Luau event-handler group parent; the added description terms (Python inputs / outputs; Luau state transitions + timing; YAML conditions; TOML affected tooling) |
| The pMAP entry carries the graph's resolved relationships; the LLM never invents callers, pairings or bugs | agrees → **added** | spec §1: relationships are copied from layer 3 into the entry, never written by the LLM |
| pMAP = where to look; graph = what is connected; source = what it does | agrees | spec §1 (wording added) |
| MCP: search, source, traversal, diagnostics; return source revision + resolution status | new → **added** | spec §10 (the later MCP phase contract) |
| Code + book answers: observed implementation / design principles / proposed changes, separate; a book cannot prove a bug | new → **added** | spec §10: the code answer contract |
| Qualification starts on the Polymath Python repository; then a real Roblox module with its callers + a book connection | agrees | spec §8 / C14 |
