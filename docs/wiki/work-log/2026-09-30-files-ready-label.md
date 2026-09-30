---
change_id: FILES-READY-LABEL
owner: "@king"
date: 2026-09-30
status: complete
status_note: "The Files screen stops calling a searchable file 'Blocked' (live 80d7cf62). The 10 new cinema files' vNext profiles were built and the index REFUSED them as far thinner (kept the base profiles), so the vNext pin stays. An atom rebuild switched off 3,133 live cinema atoms; the agent restored 120, the owner ran the restore of the other 3,013 and the batched index sync: reconcile 3,723 = 3,723, every file back to its pre-incident atoms (CLOSED 2026-09-30)."
architecture_impact: "frontend-v2/src/lib/readiness.ts (docSearchable; docVnext: Ready / Ready · basic profile / Blocked); frontend-v2/src/screens/Files.tsx (ready count, Continue only for files that are not searchable); tests: files-states.test.tsx (+3). Live data: 10 doc_profile artifacts (vNext, kept last-known-good); cinema document_profile_atoms + the atom collection (see Changes)."
last_reviewed: 2026-09-30
---

# FILES-READY-LABEL: why the new files said "Blocked"

## Contract
- The owner, 2026-09-29: "why are files blocked?", then "go" to: (1) upgrade the 10 new cinema files to the vNext profile and
  score it; (2) stop calling a searchable file "Blocked".
- Diagnosis (read-only): the 10 animation files added on 2026-09-30 05:00 UTC were fully processed (parents mapped, 0 unresolved,
  a profile, graph entities) and searchable (3 live HYBRID searches: 7-11 of 24 passages from them). The per-file verdict
  required a vNext profile; the fleet has written the base profile for new files since 2026-09-17 (`POLYMATH_DOC_PROFILE_VNEXT=0`,
  the "vNext pin" of the wiring-gap close-out: vNext collapsed Murch to one line per label). "Continue" re-runs parent
  enrichment, never the profile, so it could not clear the label.

## Changes
- **Label** (branch): `docSearchable(d)` = vNext ready, or 0 unresolved parents and a profile. The pill reads "Ready" (vNext),
  "Ready · basic profile" (amber: searchable, the richer profile not built) or "Blocked" (unresolved parents or no profile, with
  the reason in the tooltip). The header counts searchable files as ready ("77 ready (10 with a basic profile)"); Continue
  (per file and corpus) is offered only for files that are not searchable.
- **The 10 profiles** (live): `scripts/rebuild_profile.py --execute --vnext`, one call each, 10 of 10 exit 0. Every one was
  REFUSED by the index's own guard, `kept_last_known_good`, reason `regression_direct_thinned`: incoming 2-3 direct / 3
  discovery surfaces against the existing ~30 / 30. The index still serves the base profiles; the summary counts the files
  vNext-ready (the latest artifact is vNext). The coverage audit (`profile_audit.py`) did not see the thinning: its headline
  score was unchanged (0.66 mean) and the LLM part rose (0.397 → 0.449, better on 8 of 10), because it scores term and title
  coverage, not the number of retrieval surfaces.
- **The atom incident** (live, the agent's mistake): to give the 10 files the full index-entry kinds, the agent ran
  `scripts/profile_atom_canary.py --corpus cinema --project`. That 2026-09-08 tool supersedes a document's atoms WHOLE (no
  families; it predates ATOM-REPAIR-V1 and F4) and purges + re-projects the corpus's points. In one transaction
  (2026-09-30 05:55:03.664213 UTC) it switched off 3,133 live cinema atoms (the base family on every file, the 10 new files'
  base atoms, and the handbook / VES section atoms from F4), created 119 (99 from the 10 refused thin vNext profiles, 20 on older
  files) and re-used 590 that already existed, leaving 709 active (reconcile true). Found by comparing kinds per file before and after.
  - Restored by the agent: the 120 atoms of the 12 file/kind groups that had vanished entirely (re-activated + projected;
    reconcile 829 = 829).
  - NOT restored: the other 3,013. The agent's restore (re-activate them, switch off the 120 tool-made rows, upsert / delete the
    points, reconcile) was refused by the harness as a write to shared live resources. It is a script for the owner:
    `restore_cinema_atoms.py` in the session scratchpad (exact timestamp match; stops unchanged if the counts differ; says so
    if it already ran). Until then cinema's atom lane (routing / expansion only, never evidence) holds 829 of its 3,723 entries.
  - The owner's first run STOPPED with nothing changed: the script expected 120 tool-made rows, the database holds 119 (the
    first count had included one pre-existing row the tool re-used). Recounted (read-only): 119 made, 3,013 still off, 590
    re-used, 0 off for any other reason, 3,723 rows existed before the tool; the script now expects 119.

  - **CLOSED (2026-09-30, the owner's runs).** `restore_cinema_atoms.py`: the database step committed (3,013 back on, 119
    tool-made off), then its ONE upsert of all 3,013 points timed out (`httpx.WriteTimeout`, qdrant `ResponseHandlingException`)
    after embedding them all, so the index kept 829 (119 stale). `sync_cinema_atom_index.py` (read-only `--check` run by the
    agent first: 710 present, 3,013 missing, 119 stale) removed the 119 and added the 3,013 in upserts of 32 with retries:
    **reconcile 3,723 = 3,723**. Kinds per file equal the pre-incident counts (older 67: 3,423 atoms; the 10 new files: their
    300 base atoms); a live WILDCARD search: 24 passages from 12 files.

## Proof
- `files-states.test.tsx` 9 passed (+3: basic profile reads "Ready · basic profile" with no Continue and counts as ready; vNext
  reads "Ready"; unresolved parents / no profile read "Blocked" with the reason and offer Continue). Fail first: the first two
  fail on the old code (scratch copy with `git show HEAD:` of the two files), the third holds on both.
- UI: `tsc --noEmit` clean; `vitest run` 24 files, 166 passed, 7 skipped.
- Live: the rebuild artifacts' `doc_profile_qdrant.selection` (10 of 10 `regression_direct_thinned`); `document_profile_atoms`
  counts before / after (kinds per file; the single transaction stamp); `/documents/summary` 0 of 77 not vNext-ready; orchestrator
  0 Traceback; `/retrieve` GRAPH 200; a WILDCARD search still returns 24 passages from 19 files.

## Contract dispositions
- (1) done, and it answered the owner's question the other way: vNext is still too thin for these files, so the fleet pin
  (`POLYMATH_DOC_PROFILE_VNEXT=0`) stays. (2) done on the branch.

## Rejected claims
- "The coverage score shows vNext is fine": it measures words, not surfaces; the index guard's surface counts are the evidence.
- "profile_atom_canary.py is the way to give a file the full atom kinds": it is corpus-wide and whole-document; the families rule
  lives in the worker path (`PAP.ingest_document_atoms` with a `source`). The tool should not be run on a corpus with families.

## Open contract gaps
- `scripts/profile_atom_canary.py` should refuse a corpus whose atoms carry families (or take a `--source`), so it cannot do
  this again; and `PAP.project_atoms` upserts every point in ONE request, which times out past a few thousand points (batch it).
- vNext thinness on small files (2-3 direct surfaces) is the 2026-09-17 collapse, still open; the label no longer depends on it.
