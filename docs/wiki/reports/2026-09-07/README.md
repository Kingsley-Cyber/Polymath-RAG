---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# 2026-09-07 HANDOFF — successor bootstrap

**STOP.**

Do not begin implementation based solely on the user's newest request.

This repository contains architectural decisions and unfinished dependency chains that are not obvious from isolated source files: a document is served by five stores that must agree, six supervised worker kinds that restart themselves when you edit shared code, and a retrieval pipeline whose composition rules are the owner's design rather than engineering defaults. Read the documents below in order before modifying architecture. Then re-read `docs/wiki/plans/CONTINUITY-REPORT.md`, which remains the living bootstrap that this dated folder snapshots.

## Next-phase plan of record (admitted 2026-09-07, slice S0)

The owner's finalized next-phase plan is installed and is the plan of record for
the document-semantic-index phase:

- **`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`** — two-scale semantic
  index (global document profile vNext + deterministic `ParentSkeleton` and
  compact routing `MAP` per eligible parent in packed Compound-Mini calls +
  deterministic Vocabulary Bridge). Slices S0–S16 in §40.
- **`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-START-HERE.md`** — the coding-agent
  bootstrap hook for it.

State: **S0 (admission) DONE (11.129); S1 (deterministic ParentSkeleton) DONE
(11.130); S2 (parent-map compiler) DONE (11.131); S3 (token packer / capacity
model) is the next executable slice.** The U1–U12 inventory below still holds —
U1 folds into slice S12, U2 into slice S15; S3–S11/S13/S14 are the remaining
prerequisite slices.

## Reading sequence

| # | Document | Read it to answer |
|---|---|---|
| 1 | [CONTINUATION_REPORT.md](CONTINUATION_REPORT.md) | What the system is today, what this cycle built, what state each piece is in |
| 2 | [BE_AWARE.md](BE_AWARE.md) | What a new model will get wrong; every rule classified as owner preference, operational constraint, invariant, experiment or compromise |
| 3 | [ARCHITECTURE_STATE.md](ARCHITECTURE_STATE.md) | How data flows: intake → stages → stores → retrieval → answer; process boundaries; invariants per subsystem |
| 4 | [DECISION_REGISTER.md](DECISION_REGISTER.md) | Why the architecture is the way it is, with evidence, and what "reason cannot be verified" |
| 5 | [UNFINISHED_WORK.md](UNFINISHED_WORK.md) | Every open item with objective, remaining work, tests, files, risk |
| 6 | [DEPENDENCY_MAP.md](DEPENDENCY_MAP.md) | Which unfinished item must precede which; what is parallel-safe |
| 7 | [NEXT_ACTIONS.md](NEXT_ACTIONS.md) | The ordered continuation sequence (P0 → P4) with verification checkpoints |
| 8 | [VERIFICATION.md](VERIFICATION.md) | Exactly what was executed to validate this state and what it means |
| 9 | [WORKTREE_AND_BRANCH_CLOSEOUT.md](WORKTREE_AND_BRANCH_CLOSEOUT.md) / [COMMITS_AND_MERGES.md](COMMITS_AND_MERGES.md) | Git state found and left; every commit and fast-forward of the cycle |

Earlier drafts written the same day — [BE-AWARE-REPORT.md](BE-AWARE-REPORT.md) and [UNFINISHED-WORK.md](UNFINISHED-WORK.md) — are retained for their measurements and are marked `superseded` by the two files above.

## Which document is authoritative for which question

| Question | Authority |
|---|---|
| Is X complete, implemented-but-unverified, or planned? | `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` (rows never deleted; status vocabulary: DONE / IMPLEMENTED / CLOSED / QUEUED) — summarised in CONTINUATION_REPORT §3 |
| What does the owner want next, in what order? | `docs/wiki/plans/OWNER-BACKLOG.md` and `IMPLEMENTATION-TODO-2026-09-07.md`; ordered in NEXT_ACTIONS.md |
| Is this rule a preference or a constraint? | BE_AWARE.md (classification per item) |
| What is the plan of record for the profile work? | `docs/wiki/plans/DOCUMENT-PROFILE-V1.md` (owner's architecture, verbatim invariants) |
| What is the plan of record for the NEXT phase (document semantic index + parent map + vocabulary bridge)? | `docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` (slices S0–S16); hook `...-START-HERE.md` |
| What happened, with numbers? | `docs/wiki/work-log/2026-09-07-*.md` (append-only) |
| Which files may exist in the repo? | `scripts/scaffold_polymath_v4.py` (declarations) + `scripts/README.md` (script registry) — `scripts/repo_guard.py` enforces both |
| How do agents operate here? | `AGENTS.md` (contract), `CLAUDE.md` (working style) |

## Model operating contract for future sessions

**Before changing code**, answer in writing (work-log or plan):
1. What invariant does this affect? (BE_AWARE.md §"Safety / data-integrity invariants")
2. What existing decision does this interact with? (DECISION_REGISTER.md)
3. Is this owner preference or operational necessity? (BE_AWARE.md tag)
4. What upstream / downstream components depend on it? (ARCHITECTURE_STATE.md per-subsystem tables; DEPENDENCY_MAP.md)
5. What test proves correctness? Name the file; run it green before committing (`feedback: assert before commit`).

**Before replacing architecture**: show, with a measurement on this corpus (frozen fixtures B / M, the owner's punch question, 10-question loops), that the existing architecture fails the intended requirement. Quotas, blocklists and multi-score fusion have already been rejected by the owner; do not reintroduce them under new names.

**Before adding new infrastructure**: the repo already has a stage DAG, tickets with leases, receipts, artifacts, outbox events, an autopilot, a limiter, a pool with fallbacks, Qdrant, Neo4j, Postgres and two MLX sidecars. Add a stage, a lane, an artifact — not a new mechanism.

**Before introducing another LLM stage**: the hydration waterfall, dedup, region exclusion, ranking and composition are deterministic on purpose. An LLM is used where meaning must be produced (extraction, enrichment, the profile, the query compiler, the synthesizer) and nowhere else without the owner's go (plan §3.23 gate).

**Before changing persistence identities or schemas**: chunk ids, parent/child identity, projection identity and graph receipts are frozen (owner invariant). New data = new artifact / new collection / new migration under `stores/postgres/migrations/` (53 today) — never a rewrite of an existing identity. Inspect `receipts`, `artifacts`, `projection_receipts`, `outbox_events` and the Qdrant collections for downstream references first.

**While the fleet runs**: every edit under `control/`, `shared/`, `workers/` triggers a ~2-minute self-quarantine + restart of every slot. Do not edit those paths while the owner is testing in the UI; never hand-start a second orchestrator on :7200; a `FLEET` table change needs a supervisor boot (`scripts/run_fleet_supervised.sh` under `POLYMATH_AUTOPILOT=1` with `.env` sourced).
