---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E0 (part 2): the two-repo evidence gap matrix"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0-GAP-MATRIX
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.258
architecture_impact: "Docs only: docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0-GAP-MATRIX.md (E0 deliverable) + AGENTS.md item 000 (current operating state; the 0a hold text is historical). No runtime change; names the smallest admissible E1/E2 slice and the Trail subgraph the E2E acceptance depends on."
---

> Plan §11 E0: "Deliverable: one evidence-backed gap matrix across both repositories. No runtime change yet."

## Contract
Before any adapter-runtime mutation, prove current truth in BOTH repositories with FILE:SYMBOL evidence: Polymath's MCP /
retrieval / graph / latent / provenance capabilities, the `research_*` implementation and persistence, the reusable
run/receipt/artifact/control primitives and their exact gaps, the admission machinery and frozen boundaries; TrailSignal's
working operations, missing nodes to a scored candidate, CSV-vs-v2 authority, lawful public contracts, blockers; and one
cross-system contract boundary with ownership, failure/cancel/retry/idempotency semantics and acceptance commands.

## Changes
- **`docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0-GAP-MATRIX.md`** (new, declared in TREE) — 7 sections: reconciliation,
  Polymath truth, TrailSignal truth (at `origin/main` 6d7ef2a), cross-system boundary, ranked gaps + Trail missing path + owner
  actions, the smallest admissible E1/E2 slice, verification commands.
- **`AGENTS.md`** item `000` (current operating state 2026-09-13): CONTINUITY is the single living bootstrap; audit done, hold lifted,
  backfill complete, tick repaired; the active owner goal; items 00/0a are historical.
- Register 11.258; CONTINUITY checkpoint updated in place (E0 complete → NEXT = E1).

## Proof
- Two read-only repository audits (Polymath at production 6b1edd5 = this branch's runtime; Trail at `origin/main` 6d7ef2a via a
  detached worktree because the owner's checkout `~/trail-signal-os` is 75 commits behind with uncommitted local edits — left
  untouched) plus a Trail delta re-audit; every matrix row cites FILE:SYMBOL or a ledger row.
- Decisive findings: (1) Polymath's `runs`/`stage_tickets`/`receipts` cannot host an adapter run without ONE new migration
  (corpus-scoped runs, no per-step payload, no branch, no external-operation ref) while `outbox_events` + `stage_transaction` +
  leasing are reusable as-is; (2) `research_*` is an out-of-process SQLite/JSON workflow bridged by subprocess with no MCP-level
  test — the §10 equivalence baseline does not exist yet; (3) Trail today lawfully offers discovery (P5, leads hard-typed as
  NON-evidence), static acquisition (P1R/P3), deterministic extraction (P2), paging and cancellation — **no v2 evidence promotion
  and no v2 deterministic score exist** (C1/C2 pending behind P9 ← P4W+P6R+P7R+P8R); the v1 CSV scorer is unreachable from v2;
  (4) no Polymath principal exists in Trail (owner/config action); (5) the OCP/"Polymath bridge" branches are local-only and are not
  authority.
- Guards: preflight ok, repo_guard ok, wiki_worm ok (this commit).

## Rejected claims
- **"Trail's local main is the authority"** — REJECTED: `origin/main` carries PR #1/#2 (the owner's correction) and A13–A29/P5; the
  local checkout is stale. Audited the remote head in a detached worktree instead of mutating the owner's checkout.
- **"Trail already has a Polymath bridge (OCP1–OCP8, ResearchOperationBindingV1, EvidenceIngressManifestV1)"** — REJECTED: those exist only
  on unpushed local `codex/*` branches; not found on `origin/main`, no ADR, no node.
- **"The forensic hold still freezes the adapter architecture"** — REJECTED with evidence: audit 11.253, owner lift + backfill 11.255;
  and the adapter slice touches none of the pMAP path anyway.
- **"Reuse `stage_tickets` for adapter steps without a migration"** — REJECTED: `UNIQUE(run_id, stage, generation)` and the missing
  step payload/external-ref columns each independently block it (matrix §2.3).

## Open contract gaps
- **Owner actions O1–O5** (matrix §5.3): Polymath principal + secret in Trail config; Trail node ordering (P6R vs P4W); LongCat credential
  rotation for P8R; external-service availability for a live E2E; merge PR #3 on green and accept ADR-0018 when proposed.
- **E3 is the long pole**: the plan's acceptance items 5–6 (real Trail evidence + deterministic score) are unreachable until Trail's
  graph reaches C2; E1/E2 (Polymath substrate) and E4's connector against the WORKING tools can proceed now.
