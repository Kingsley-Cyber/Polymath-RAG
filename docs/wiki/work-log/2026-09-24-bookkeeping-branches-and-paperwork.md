---
change_id: BOOKKEEPING-2026-09-24
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "Documents + git refs only; no runtime change. Group 4: 21 unmerged, superseded branches archived as local tags and deleted. Group 5: every open work-log and refactor record closed with an evidence note; leftovers moved into the gap register as owned rows."
last_reviewed: 2026-09-24
---

# Bookkeeping: branches (group 4) and paperwork (group 5)

## Contract
- The owner, 2026-09-24: "clear groups 4 and 5 then go batch 1". Group 4 = the 22 unmerged branches; group 5 = the 5
  open refactor records and the 123 work-logs the wiki checker lists as open.

## Changes
**Group 4 (git refs, local only; nothing pushed):**
- 21 branches archived as `archive/<branch>` tags at their exact tips (each tag verified against the tip before
  `git branch -D`): `architecture/evidence-first-v5`, `feat/idea-doors`, 18 × `handoff/*`,
  `harness-research-hr4-portfolio-consumer`, `readme-run-and-handoff-refresh`. The clean worktree
  `polymath-v4-handoff` was removed first. `review/m1-reproductions` stays (a review branch by design).
- Evidence they were superseded: 10 were patch-equivalent in production (`git cherry`); the two big lines from
  2026-09-13 have 271 / 311 and 282 / 344 changed files byte-identical in production and none missing; every small
  handoff branch's work is in production under other commits (the Trail connector as `trail_client.py`, migration
  0063 renumbered 0064, the R5 audit-fix code lines all present, register rows 11.270–11.276).
- `feat/idea-doors`: its record (work-log + `replay.json`) was never in production; both are restored from the tag
  and the work-log now points at `archive/feat/idea-doors`.

**Group 5 (documents):**
- 73 finished work-logs that used another word (`shipped`, `done`, `complete (…)`) → `status: complete`, the old wording
  kept in `status_note`.
- 49 work-logs judged from evidence by three read-only classification runs (register rows, production code, read-only
  SQL): 45 complete / superseded, 1 + 6 with leftovers → closed with a note naming the gap-register row that now owns
  each leftover.
- Refactors: 0013, 0014 done; 0011, 0012 superseded; 0015 done with leftovers → T-01, T-02.
- Stale lines fixed: AGENTS.md item 00 (marked historical; two wrong facts corrected), the status front matter of
  WLK2C-RETRIEVAL-LINEAGE-V1, LATENT-QUERY-FUSION-V2, CORPUS-EXPLORER-V1, REASONING-BOUNDARY-V1 (all DONE), the P11 row
  of HARNESS-RESEARCH-MIGRATION-V1-PLAN §7, `docs/migration/CONTINUATION.md` (D1 was repaired in 11.382),
  `architecture/contract-dependencies.yaml` (migration 0065 applied), a CONTINUITY history line (the lifecycle writer
  and reconcile never ran), and the two 2026-08-25 retrieval contract docs marked HISTORICAL.
- Gap register: + L-19, D-03..D-09, O-01..O-03, T-01..T-02 (62 rows).

## Proof
- `wiki_worm --check`: 0 open refactors, 0 open work-logs (was 5 and 123); exit 0.
- Live facts behind the new rows were read-only: control-tick phases (census receipt checks 51.3 s median of the last
  200 ticks), `runs` (63 + 6 reconciling, 1 intake), attempt ledger and receipt counts.

## Rejected claims
- "The unmerged branches hold unmerged work": none does; every one is superseded or patch-equivalent, and the tags keep
  them recoverable.
- "Marking a work-log complete hides its leftover": every leftover now has its own gap-register row.

## Open contract gaps
- The new rows (D-03..D-09, O-01..O-03, T-01, T-02, L-19) wait for their slices or the owner's decisions.
