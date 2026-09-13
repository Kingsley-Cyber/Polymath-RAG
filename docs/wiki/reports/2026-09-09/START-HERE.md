---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — session bootstrap / zero-context entry point
supersedes_for_operating_state: docs/wiki/reports/2026-09-08/START-HERE.md
---

# START HERE — Polymath RAG execution bootstrap (2026-09-09)

Zero-context entry point. Trust the repository, not chat history. Evidence order:
current source → durable DB/artifacts → migration authority → work-logs → commits → older docs.

## BLUF

Polymath is a document→knowledge RAG pipeline being migrated to a **vNext retrieval substrate**
(`document profile → parent-MAP → child`, plus legacy latent/enrichment on a dual-run→retire path).
The current active phase is **RETRIEVAL-MIGRATION-DEPENDENCY-V1 S12** (existing-corpus backfill) under a
**FORENSIC HOLD**. This session **landed the Groq Parent-MAP control-plane repair** (offline, no provider
spend) — the limiter/map accounting is now an instrumented conservation chain. Cinema parent-MAP
backfill remains **STOPPED**; the only remaining gate item before resume is a **bounded, owner-authorized
live Groq probe** (quota topology) + a MAP-batch benchmark → bounded canary → owner review.

## Repo truth (CONFIRMED)

```
branch : architecture/evidence-first-v5
HEAD   : f1112ce   (4 commits AHEAD of origin — control-plane repair is LOCAL/unpushed)
remote : github.com/Kingsley-Cyber/Polymath-RAG
worktree: clean
guards : agent_preflight ok · repo_guard ok · wiki_worm --check ok
```

This session's 4 unpushed commits: `eba6889` (limiter reasoned admission + header split), `68708a0`
(per-account groq family), `0bbf160` (map-backfill observability + retry), `f1112ce` (offline replay + docs).

## Execution authority (DISPUTED point corrected)

The bootstrap directive referenced `RAG_PIPELINE_FINISH_PLAN.md` / `RAG_PIPELINE_AGENT_BOOTSTRAP_PROMPT.md`
— **these do NOT exist in the repo.** The real authorities are:
1. `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` — the migration/retirement authority (S-slices S1–S18).
2. `docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` — retrieval/routing/synthesis phases (P0–P13).
3. `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — the completion contract / register (…11.185).
4. `docs/wiki/plans/CONTINUITY-REPORT.md` — living bootstrap.
`PLAN.md` (root) exists but is old (Aug 13) — not the current authority.

## Read order (this folder)

1. `START-HERE.md` (this) → 2. `01_CURRENT_STATE.md` → 3. `02_FROZEN_ARCHITECTURE.md` →
4. `04_PROVIDER_AND_FUNCTION_POOLS.md` → 5. `05_UNFINISHED_WORK.md` → 6. `06_CANARY_STATUS.md` →
7. `07_NEXT_ACTION.md` → 8. `08_DEPENDENCIES_AND_BLOCKERS.md` → 9. `09_DECISION_LEDGER.md` →
`03_RUNTIME_GRAPH.md` for FILE:SYMBOL paths.

Also: `docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md` (the audit this session executed).

## Next action (one)

Present/execute the **bounded Groq live-probe** (Phase 1 quota topology: is compound / compound-mini RPD
shared per account? real per-account RPD?) — see `07_NEXT_ACTION.md`. **Owner-gated: it spends provider
quota, so do not run without an explicit go.** Backfill stays STOPPED until the probe + benchmark pass.
