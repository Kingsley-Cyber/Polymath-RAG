---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE — session bootstrap / zero-context entry point
supersedes_for_operating_state: docs/wiki/reports/2026-09-09/START-HERE.md
---

# START HERE — Polymath RAG execution bootstrap (2026-09-09T2039, session end)

Zero-context entry point. **Trust the repository, not chat history.** Evidence order:
current source → durable DB/artifacts → migration authority → work-logs → commits → older docs.
This snapshot supersedes `docs/wiki/reports/2026-09-09/` (that folder was THIS session's START,
at HEAD `f1112ce`; the session then landed RAG-pipeline-finish Phases 15–18 + the operational-UI
and verified the chat-retrieval runtime).

## BLUF

Polymath is a document→knowledge RAG pipeline migrating to a **vNext retrieval substrate**
(`document profile → parent-MAP → child`). This session delivered two things and discovered one
critical truth:

1. **Fresh-document pipeline is COMPLETE + PROVEN LIVE** (RAG-PIPELINE-FINISH-V1, register 11.186).
   A new `/upload` reaches per-document `vnext_ready` in < 4 min: auto-minted grounded pMAP (Groq
   compound-mini) + early doc_profile → source-grounded retrieval. **3/3 consecutive canaries** on
   `rag-canary` (215.9s → 169.3s → 107.7s).
2. **Operational-UI (control-plane visibility) SHIPPED + proven** (OPERATIONAL-UI-V1, register 11.187):
   Files health columns + document diagnostic drawer; a new **Control Plane** screen (functional pools
   + model/account lanes, secret-free); a read-only chat intent badge. §13 acceptance **16/16** live.
3. **CRITICAL FINDING (verified this session):** the planned **INTENT × FIELD × TECHNIQUE × BUDGET**
   retrieval routing (`FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1`) is **built but flag-gated OFF at runtime.**
   Live chat runs **baseline HYBRID** (dense + sparse + document-profile → cross-encoder → synthesis).
   The compiler classifies the intent but **does not route on it** because `POLYMATH_CHAT_INTENT_POLICY`
   is unset. See BE_AWARE.md item 1 and UNFINISHED_WORK.md U-1.

**Nothing new is broken.** Guards green. The migration is at "fresh-document indexing COMPLETE" — it is
NOT "retrieval migrated," NOT "production default," NOT "legacy retired." Those are four different states
(see BE_AWARE item 2).

## Repo truth (CONFIRMED 2026-09-09T2039)

```
branch  : architecture/evidence-first-v5
HEAD    : dbfb91c
remote  : github.com/Kingsley-Cyber/Polymath-RAG
origin/architecture/evidence-first-v5 : 1dc67c0   (HEAD is 32 commits AHEAD — LOCAL/unpushed)
origin/main                           : 1c61a6f   (HEAD is 37 commits ahead, 0 behind)
open PR for this branch               : NONE  (PR #2 is the docs-only rag-finish-plan branch, 4/8 checks failing)
worktree: clean (0 dirty, 0 untracked)
guards  : agent_preflight ok · repo_guard ok · wiki_worm --check ok · bundle_integrity READY
```

This session's commits (newest first): `dbfb91c` op-ui Slice 5 (acceptance 16/16 + relations parity) ·
`72b359a` op-ui Slice 4 (chat intent badge) · `72d6261` op-ui Slice 3 (Control Plane screen) · `1924b84`
op-ui Slice 2 (Files columns + drawer) · `53c444a` op-ui Slice 1 (backend status contract) · `75a5e19…8b31e8d`
RAG-pipeline-finish (Phases 7–18 + Phase 15 live canary). Full arc since the session-start snapshot = `f1112ce → dbfb91c`.

## Execution authority (order of precedence)

1. `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` — **MIGRATION AUTHORITY** (S-slices: eliminate
   readers → stop writers → delete state; the zero-reader retirement gate).
2. `docs/wiki/plans/FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md` — **ACTIVE AUTHORITY** for query-time
   architecture (P0–P14 phase table + R1–R10 primitives + DEFERRED D-5…D-14). **This is the plan the
   chat-retrieval runtime is measured against.**
2b. `RAG_PIPELINE_FINISH_PLAN.md` — the fresh-document runbook adopted from PR #2 (register 11.186).
    **NOTE: this file is NOT committed in the repo** (PR #2 is a separate docs branch); its phases are
    tracked in the register + work-logs `2026-09-09-rag-*`.
3. `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — the completion contract (rows never deleted). Latest:
   **11.186** (RAG-finish, GOAL ACHIEVED) and **11.187** (OPERATIONAL-UI-V1, DONE).
4. `docs/wiki/plans/CONTINUITY-REPORT.md` — the living bootstrap (read it first; this folder is its snapshot).

## Read in this order (also mirrored in CONTINUITY-REPORT § NEXT SESSION)

1. `AGENTS.md`
2. `docs/wiki/plans/CONTINUITY-REPORT.md`
3. this folder's `START-HERE.md`
4. `BE_AWARE.md`
5. `UNFINISHED_WORK.md`
6. `DEPENDENCY_MAP.md`
7. `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` (rows 11.184–11.187)
8. `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` + `FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1.md`
9. the two newest work-logs (`2026-09-09-operational-ui-acceptance.md`, `2026-09-09-chat-retrieval-runtime-audit.md`)

## Exact next action next session

**Decision required from the owner, not a code change:** choose the next lane —
(A) **retrieval migration** — decide whether to enable the built-but-off intent routing
(`POLYMATH_CHAT_INTENT_POLICY`), which is gated on parent-MAP corpus coverage (cinema behind the forensic
hold); or (B) **forensic-hold clearance** — the bounded, owner-authorized Groq live probe (quota topology)
that unblocks the cinema pMAP backfill. **Do NOT flip either without owner authorization.** If just
continuing verification, the first executable action is the live A/B in UNFINISHED_WORK.md U-1
(`POLYMATH_CHAT_INTENT_POLICY` off vs on in a throwaway probe on `rag-canary`, no default change, no spend).

## Active forensic holds (UNCHANGED this session)

- **CINEMA pMAP BACKFILL — STOPPED (forensic hold, register 11.184/11.185).** Do not resume on a quota reset;
  do not spend Groq quota to gather evidence. See DEPENDENCY_MAP.md and `docs/wiki/reports/2026-09-08/GROQ-FORENSIC-AUDIT.md`.
