---
owner: "@king"
last_reviewed: 2026-09-08
status: handoff snapshot
architecture_impact: none (session continuation snapshot)
---

# SESSION CONTINUATION — 2026-09-08 (FINAL RETRIEVAL / ROUTING / SYNTHESIS phase)

> **⚠️ FORENSIC HOLD (2026-09-08/09) — read `START-HERE.md` first.** The CURRENT operating state is
> `CINEMA PARENT-MAP BACKFILL = STOPPED` and the prior "Groq RPD exhausted" conclusion is DISPUTED.
> This README remains accurate for the routing/synthesis phase narrative, but the next session's task is
> the **Groq Parent-MAP forensic audit** — see `START-HERE.md` → `GROQ-FORENSIC-AUDIT.md`. Also note the
> `main` SHA below is stale (`a17e4d6`); current `main` includes the SiliconFlow lanes — verify with
> `git rev-parse HEAD`.

**Newest handoff snapshot. Supersedes `2026-09-07T1828/` for the retrieval/routing/synthesis
phase** (the document-semantic-index substrate it describes is this phase's P1, still valid).

## Repository truth (verify, don't trust this file for live fleet state)

- branch `architecture/evidence-first-v5`; **`main` = `a17e4d6`** (the whole phase landed +
  CI-green). `git rev-list --count origin/main..HEAD` = 0.
- Bootstrap: `.venv/bin/python scripts/agent_preflight.py` → ok; `scripts/repo_guard.py` +
  `scripts/wiki_worm.py --check` green. Use `.venv/bin/python` (the Mac `python3` is 3.9, no
  `tomllib`).
- Sidecars move ports: embedder/reranker/orchestrator were on 8081/8082/8000, now **8742 /
  8743 / 7200** after a stack restart (`launchctl kickstart -k gui/$(id -u)/com.polymath.v5`).
  The reranker may be down — retrieval degrades to fusion order (union is pre-judge, so
  qualifications are unaffected). Query live ports with `lsof -nP -iTCP -sTCP:LISTEN`.

## Plan of record (the living ledger — READ THIS FIRST)

**`docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md`** is the single living execution
ledger for this phase. Its top block (LIVING EXECUTION LEDGER) is the control point: the
phase table (P0–P14) + primitive table (R1–R10) + the DEFERRED register (D-5…D-14). §0–§64
below it are the frozen owner SPEC. The register (`PLAN-AUTHORITY-REGISTER.md` 11.155–11.167)
and the work-logs are EVIDENCE the ledger rows cite — not a parallel ledger. The migration
ledger `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` still owns the substrate (P1) safe-migration +
the retirement zero-reader gate (D-14).

Read order: this file → `DIRECTORY_MAP.md` (next to this) → the FINAL-PLAN ledger block →
`PLAN-AUTHORITY-REGISTER.md` 11.155–11.167 → the two newest work-logs.

## What landed this phase (all reversible, default-off, flag-off byte-identical, additive)

| Phase | What | Flag |
|---|---|---|
| P0 | FINAL plan frozen as the living ledger | — |
| P1.spine / S9 | DOCUMENT_PROFILE→PARENT_MAP→CHILD dual-read lane E | `POLYMATH_CHAT_DUALREAD_ENABLED` |
| P2a/b | Intent classifier (no new LLM) + intent→budget→fields policy | `POLYMATH_CHAT_INTENT_POLICY` |
| R4 | PROFILE_ATOM — table `document_profile_atoms` (0055) + collection (1847 cinema atoms, reconcile TRUE) + retrieval lane | (via intent policy) |
| R6 | RESOLUTION_LIFT — ranker + gatherer + probe lane F | `resolution_lift_enabled` (intent policy) |
| P4 | Micro-latent per intent (lane D) | (via intent policy) |
| P6 | Intent-conditioned graph assist on HYBRID (no 4th mode, Neo4j fail-open) | (intent policy → `policy.graph`) |
| P8 | Synthesis evidence-role bundle (DIRECT/PRECISION/RELATIONAL/LATENT) | always-on tag (additive) |
| P9 | Task-conditioned breadth (no quotas) | (via intent policy) |
| P10 | Production routing qualification — **NON-REGRESSION PASS** (L 15/15, B 13/15, 0 regressions) | — |

**Nothing changes in the live query path until a flag is set.** The intent policy
(`POLYMATH_CHAT_INTENT_POLICY=1`) is the master switch that activates the whole intent-aware
stack; it is default-off and non-regressive (P10).

## What is DEFERRED (see the FINAL-PLAN DEFERRED register D-5…D-14 — nothing dropped)

- **D-5** P5 BRIDGE/ANCHOR fan-out — GATED on vNext atom regen (those atom kinds = 0).
- **D-7** P7 graph→children — BLOCKED on the graph-before-judge flow reorder.
- **D-8b** P8b synthesizer-presents-by-role — BLOCKED on the `answer_synthesis.py` claim-system change.
- **D-10** P10 *uplift* (not just non-regression) — GATED on parent-MAP backfill coverage + vNext atoms.
- **D-11/D-12/D-13** GRAPH/Wildcard measurement — GATED on D-7 / atom regen.
- **D-14** legacy retirement — BLOCKED on the migration ledger's zero-reader proof.

## Live substrate state (query, don't guess)

- parent-MAP backfill is paced by Groq RPD; cinema mapped cohort growing (Blain ~185/264 at
  handoff). `POLYMATH_GROQ_ROUTER=1 .venv/bin/python scripts/parent_map_backfill.py --corpus cinema --project`
  is resumable/idempotent — run it as accounts free up (this unblocks D-10 uplift).
- Profile atoms: THEORY/CONCEPT/SEEALSO generated (1847 cinema); the relational/rediscovery
  kinds need vNext profile regeneration (unblocks D-5/D-12).

## Exact next action

Pick the next non-DONE/non-BLOCKED row from the FINAL-PLAN phase table. The unblockable-now
work is the **parent-MAP backfill** (paced; unblocks D-10 uplift) and **vNext profile
regeneration** (unblocks D-5/D-12 atoms). The BLOCKED rows (D-7, D-8b) each need a scoped
re-architecture slice designed in their phase row. Do NOT mass-reindex or retire legacy before
the migration ledger's gates permit it.
