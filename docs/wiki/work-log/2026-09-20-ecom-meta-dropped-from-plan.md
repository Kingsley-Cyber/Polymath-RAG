---
change_id: GOVERNED-CONVERGENCE-V1-ECOM-META-DROPPED
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — docs only. The plan of record no longer proposes ecom-meta-v1 as a corpus; the current corpus is cinema. No code, no contract, no bounce, no run, nothing ingested, nothing deleted from disk."
last_reviewed: 2026-09-20
---

## Contract
Owner word 2026-09-20: "DELETE ECOM META ITS NOT PART OF MY CURRENT CORPUS. DROP IT FROM PLAN."

- Authority: the owner's live instruction beats the plan text and the amendment recorded under register 11.358.
- Verifier: the plan names `ecom-meta-v1` only in the record of this direction; CONTINUITY's live section no longer
  carries an ecommerce-corpus path; guards = 0.
- Rollback: `git revert` of this commit (the removed report is also recoverable at tag `v4-governed-convergence-tg4`).

## Changes
- `docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md`: status, execution ledger and TG5 no longer propose `ecom-meta-v1`; the
  corpus is the current corpus, `cinema`; the TG5 section records both owner directions of the day (cinema = mechanical
  smoke only; ecom-meta dropped). No product corpus is named by the plan.
- REMOVED `docs/wiki/reports/2026-09-20/ECOM-CORPUS-INGESTIBILITY.md` (+ its scaffold `TREE` entry). It existed only to
  feed the dropped plan branch.
- `docs/wiki/plans/CONTINUITY-REPORT.md` CURRENT: finding 1, Next Action, Do Not Do and Deferred Architecture rewritten
  without the ecommerce-corpus path; Repository State names the real HEAD / tag relation.
- `docs/wiki/work-log/2026-09-20-governed-convergence-tg4.md`: two pointer lines (the report was removed; the
  ecommerce-corpus decisions are closed). Register row 11.359.

## Proof
Docs only. `agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY.
`grep -c ecom-meta docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md` = 1 (the record of the direction).

## Rejected claims
- "The corpus was deleted." It did not exist: Polymath v4 already held only `cinema`. Nothing was deleted from disk
  either — leftover source files outside the repo were not touched.
- "Every mention of the corpus is gone from the repo." No. Historical checkpoints, frozen eval baselines and old
  defaults still name it (`eval/v5/*`, `scripts/chat_baseline.py --corpora` default, `eval/v5/fleet/provider_canary.py`
  `CANARY_CORPUS` default; the skill repo's usage examples). They are history, not plan, and were left alone.

## Open contract gaps
Dispositions: no contract changed or impacted — everything NOT_AFFECTED.

- TG5 / R2 still needs the owner's word. By the owner's own rule a cinema-backed run is a mechanical / integration
  smoke, so the plan currently has no corpus for a product-discovery-quality result. That is the owner's to name.
- Old defaults that point at a corpus that does not exist (`CANARY_CORPUS`, `chat_baseline.py --corpora`) fail or skip
  when run without an override. Not changed here (not asked).
