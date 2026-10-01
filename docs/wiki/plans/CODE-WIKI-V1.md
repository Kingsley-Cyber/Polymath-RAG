---
title: "CODE-WIKI-V1 — a checkable, end-to-end code wiki that a weak coding agent can use for refactors and bug hunting"
date: 2026-09-30
last_reviewed: 2026-09-30
status: "ACTIVE — plan of record (register 11.557); the owner's go of 2026-09-30"
owner: "@king"
scope: "docs/codewiki/ (generated), scripts/codewiki/ (spine, pages, verify), the CI gate, the AGENTS.md pointer. No runtime change."
---

# CODE-WIKI-V1

## 1. The ask
The owner, 2026-09-30: "THIS REPO NEEDS DOCUMENTATION SO GOOD A DUMB LLM CODING AGENT CAN UNDERSTAND AND REFERENCE
RELATIONSHIP ... WE CAN USE GLM CODING PLAN AND OPENCODE ... AND GRAPHIFY, BUT WE NEED PROPER E2E DOCUMENTATIONS FOR FUTURE
REFACTORS AND BUG HUNTING TO THE MOST ELITE STANDARD", then "go", "ensure it's completed and committed to the repo on GitHub".
Constraint: spend as little of the owner's Claude quota as possible.

## 2. The standard (the owner's `repo-bug-wiki` skill)
Checkable claims, never intent-prose: every claim carries a `path:LINE` anchor and a provenance tag (DERIVED = visible in the
code; INFERRED = a hypothesis). Seven page types: unit/contract, invariant ledger (comparable value pairs), vocabulary (one
authority + every consumer), specimen (the real prompt / payload), runtime truth tables, failure-pattern ledger, index. Each
page ends with a `verify` block whose lines are re-checked against live code; a drift fails CI.

## 3. Who does what (the cost rule)
| layer | produces | done by | Claude cost |
|---|---|---|---|
| 0-1 spine | routes + web-boundary class, env flags + defaults, the fleet + sidecars + ports, DB tables + readers/writers, Qdrant collections, MCP tools (both servers), vocabularies (constants + consumers), prompt specimens, silent fallbacks, nondeterminism, the import graph, frontend → backend calls | `scripts/codewiki/spine.py` (static analysis, no model) | none |
| 2 unit pages | one page per product file >= 150 lines, one per directory for smaller files (~250) | GLM 5.3 on the owner's Z.ai coding plan, through OpenCode with a no-tools agent, 6 in parallel | none |
| 2 flows | 8 end-to-end traces (chat turn, upload to searchable, deep research, Trail adapter run, MCP call, web sign-in, supplier search, fleet boot / bounce) | GLM from the spine's static call chains | audit only |
| 2 ledger + glossary | failure patterns from the plan register and the runbooks; domain terms | GLM, chunked | none |
| 3 verify | every `verify` line (a SAFE grammar: `grep -Fq` / `grep -Eq` / `!` / `test "$(grep -c …)" -ge N`, run without a shell) and every anchor | `scripts/codewiki/verify.py` | none |
| 4 keep true | CI runs the verifier on every push; `pages.py` regenerates only the pages whose input hash changed | CI + the owner's command | none |

Claude writes the three scripts, pilots three units, audits the flows and a sample, and commits. It never writes or reads the
bulk pages.

## 4. Safety
- The GLM agent has every tool disabled and runs in a private directory: it cannot read, write or run anything.
- A `verify` line is parsed and run as an argument list, never through a shell; anything outside the grammar is rejected.
- A page whose `verify` lines or anchors fail after two retries keeps only its passing lines and is listed on the index dashboard.
- Repository text is data to the model, never instructions (stated in the agent prompt).

## 5. Done means
- `docs/codewiki/index.md` + unit pages for every product file, 8 flows, invariants, vocabularies, truth tables, the failure
  ledger, the glossary, the fact tables; `verify.py` green; the guards green; AGENTS.md sends every agent to the index first.
- Merged into `production` and pushed to GitHub (the owner's word, 2026-09-30).
