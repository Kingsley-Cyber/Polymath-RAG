---
title: "WORK LOG — RETRIEVAL-MIGRATION-DEPENDENCY-V1 admitted as the living migration ledger"
change_id: RETRIEVAL-MIGRATION-DEPENDENCY-V1
date: 2026-09-07
owner: governance (repository-only: plans + register + scaffold)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.138
package: docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md, docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md, scripts/scaffold_polymath_v4.py, docs/wiki/plans/CONTINUITY-REPORT.md
architecture_impact: "Makes the owner-supplied FINAL RETRIEVAL MIGRATION / DEPENDENCY PLAN repository truth (it lived only in ~/Downloads, which the repo bootstrap law does not treat as authoritative). The plan body is admitted verbatim; a REPO EXECUTION STATUS LEDGER is prepended and maintained in place. No code, schema, fleet, or provider-spend change; docs/ does not trip the execution-bundle fence."
---

# WORK LOG — RETRIEVAL-MIGRATION-DEPENDENCY-V1 living ledger

## Contract

The owner set a session goal (2026-09-07) making the FINAL RETRIEVAL MIGRATION /
DEPENDENCY PLAN the live execution document, to be executed end-to-end and **amended
in place as a living ledger** ("Do not create a replacement plan"). Repository law
(`AGENTS.md` §0) is explicit that repository bootstrap files — not chat, not
`~/Downloads` — are authoritative project state. So the plan must be in the repo to
be amendable and to survive compaction/handoff.

Owner: `governance` (repository-only change: a plan doc, the register, the scaffold
TREE, and a CONTINUITY reference). Public-contract change: none (no code/schema).
Rollback: delete the file + revert the three doc/scaffold edits. Verifier:
`scripts/wiki_worm.py --check` + `scripts/repo_guard.py`.

Explicitly OUT of scope: no rewrite/summarization of the plan (admitted verbatim);
no code, migration, worker, fleet, or provider-spend change; no chunker change.

## Changes

- **`docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md`** (new): the plan copied
  verbatim from `~/Downloads/POLYMATH_FINAL_RETRIEVAL_MIGRATION_DEPENDENCY_PLAN_2026-09-07.md`
  (§1–§30 body, classification vocabulary, GAP-01..GAP-12, S0–S18), with:
  - YAML front-matter (`change_id`/`owner`/`date`/`status: living`/`last_reviewed`) so
    `wiki_worm` passes;
  - a prepended **REPO EXECUTION STATUS LEDGER**: every slice keyed by capability,
    cross-mapped to the repo build-slice numbers, state-tracked with the goal's
    vocabulary (NOT STARTED / IN PROGRESS / IMPLEMENTED / VERIFIED / LANDED / GATED /
    BLOCKED / SUPERSEDED), plus the generation invariant, the live-dependency
    do-not-retire list, and the exact next executable dependency.
- **`scripts/scaffold_polymath_v4.py`**: TREE line for the new plan (repo_guard
  requires every file declared).
- **`docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md`**: register row 11.138.
- **`docs/wiki/plans/CONTINUITY-REPORT.md`**: a one-line pointer to the new ledger
  in the latest checkpoint (the living bootstrap references it).

## Proof

```
.venv/bin/python scripts/wiki_worm.py --check   -> wiki: ok
.venv/bin/python scripts/repo_guard.py          -> repo guard: ok
.venv/bin/python scripts/agent_preflight.py     -> preflight: ok
```

The ledger's status column was reconciled against HEAD `93a16c0` and registers
11.129–11.137: S0/S2(repo S1+S2)/S4 = LANDED; S7-independence (repo S5 fingerprint)
= IN PROGRESS; S3/S12–S18 = GATED; S1 census = IN PROGRESS/PARTIAL (only
`scripts/semantic_lane_census.py` exists, covering concept/procedure lane liveness).

## Rejected claims

- **Not** a new plan hierarchy: this is one authoritative plan admitted into the
  existing `docs/wiki/plans/`, exactly as `DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` was.
  The two are cross-mapped, not duplicated; this file owns migration/retirement/
  generation-invariant authority, the other owns build-slice detail.
- **Not** a supersession of `DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md`: it remains the
  executable build-slice plan; the commit history's "slice S#" numbers are its
  numbers, distinct from this plan's §30 S0–S18 (hence a capability-keyed ledger).
- **Not** the routing/synthesis plan the CONTINUITY-REPORT anticipated
  (`POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN`) — that file is
  still absent from `~/Downloads`; admit it when supplied.

## Open contract gaps

- The migration plan's **S1 automated dependency census** is only PARTIAL in-repo.
  The full legacy-symbol census (retrieval_summaries / parent_summaries /
  document_summaries / corpus_summaries / summary_artifacts / summary_jobs /
  compile_objects / parent_enrichment / latent / LATENT-TRANSFER /
  REPRESENTATION_KIND_*_SUMMARY / POLYMATH_CHAT_COMPILER_TITLES_RANK, each classified
  reader/writer/producer/config/test/migration) is the hard gate for all retirement
  slices (S15–S18) and is not yet built.
- **GAP-04** live reader confirmed: `workers/workers/doc_profile_worker.py:102`
  (`SELECT major_concepts FROM document_summaries`). The next slice (profile vNext
  fingerprint) makes the profile input self-sufficient so this reader can retire in
  the worker refactor — not in this slice.
- Live-spend/fleet-config slices (local-model tournament, Groq live wiring, canary,
  backfill, cutover) stay GATED pending the owner.
