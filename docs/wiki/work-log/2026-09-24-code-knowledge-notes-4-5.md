---
change_id: CODE-KNOWLEDGE-V1-NOTES-4-5
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents only. Two design reviews the owner pasted are admitted verbatim and reconciled. The representation spec gains: reproducible links; remote pairing by instance identity; config strings as possible references; a diagnostics layer; relationships copied into pMAP entries; path-preserving ranking; the three-part code answer and MCP contract. The sources list gains Ruff, CodeGraphContext and Graphify. Decision 5 changed by the owner: the Neo4j projection ships in the first version (C8 right after C2)."
last_reviewed: 2026-09-24
---

# CODE-KNOWLEDGE-V1: two design reviews reconciled; Neo4j in the first version

## Contract
- The owner pasted two reviews of the plan, from another assistant, with no further instruction. The standing workflow
  (register 11.452) applies: store the owner's design input verbatim, reconcile it, and put any decision it reopens to the
  owner.
- **Decision put to the owner:** "Both reviews say the code graph should also be loaded into Neo4j in the first version,
  not later. Should it?" The owner answered "Yes, in the first version (Recommended)".

## Changes
- `docs/code-knowledge-v1/ADDENDUM_2026-09-24_OWNER_NOTES_4_5.md`: both reviews, verbatim.
- `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTES-4-5-RECONCILIATION.md` (new): the reopened decision, the
  verification, and every point with its verdict and where it lands.
- `docs/wiki/plans/CODE-LANGUAGE-REPRESENTATIONS-V1.md`:
  - layer 3 = Postgres + a Neo4j projection in V1; a new layer 3b (diagnostics);
  - reproducibility attributes + test;
  - the three roles (where to look / what is connected / what it does);
  - relationships copied into pMAP entries; failure modes labelled as hypotheses; discovery paths into the path-aware
    judge;
  - card updates: Python inputs / outputs; YAML conditions + ambiguous string references; TOML entrypoints resolved only by
    schema; Luau event-handler groups + state transitions / timing + remote pairing by the same instance; Power Fx binder
    fed pass 1's symbol table;
  - §7 cross-language rules; §8 C0 items 7–8; §9 C8 in V1 + C13 diagnostics;
  - new §10: the code answer + MCP contract.
- `docs/wiki/plans/CODE-KNOWLEDGE-V1-SOURCES.md`: Ruff (PULL, C13), CodeGraphContext (EVALUATE extraction components in
  C0), Graphify (STUDY; not a Luau parser).
- `docs/wiki/reports/2026-09-24/CODE-KNOWLEDGE-V1-NOTE-3-RECONCILIATION.md`: decision 5 row + the phase order (C8 after C2
  in the first version).
- `docs/wiki/plans/CODE-KNOWLEDGE-V1.md`, `CONTINUITY-REPORT.md`: the Neo4j decision + read-order item 6.
- The register (11.455) and the scaffold TREE.

## Proof
- **GitHub API, 2026-09-24:**
  - CodeGraphContext/CodeGraphContext: MIT, 4.2k★, v0.5.7, active;
  - Graphify-Labs/graphify: Apache-2.0, 121k★, v0.9.67, active;
  - astral-sh/ruff: MIT, 49.7k★, 0.16.8.
- **Local:** the owner's Graphify is `graphifyy` 0.9.53 (uv tool). Its `graphify/extract.py` maps `".luau": "lua"`
  (L2327) and `".luau": extract_lua` (L5400), which confirms review B's claim.
- **Guards:** `agent_preflight`, `repo_guard`, `wiki_worm --check`, `bundle_integrity`, each exit code on its own line.

## Rejected claims
- "Adopt CodeGraphContext / Graphify as the pipeline": either would be a second system beside Polymath. Their extraction
  components and MCP / Neo4j patterns are evaluated or studied instead.
- "A config string equal to a function name proves a link": stored `ambiguous` unless a dialect schema defines the field.

## Open contract gaps
- **The owner's real-code inputs** before C0, above all the Roblox project format.
- **C0 comparisons:** CodeGraphContext extraction vs our adapters; the rest per the sources list.
