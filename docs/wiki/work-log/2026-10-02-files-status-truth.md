---
change_id: FILES-STATUS-TRUTH-V1
owner: "@king"
date: 2026-10-02
status: complete
status_note: "The Files list paints each file's real state: green Ready, blue Processing (its required steps still running), amber Needs retry (a step failed, with which step and why), red Not searchable; pMAP (mapped out of eligible), Profile (built AND in use by retrieval and routing) and Graph (nodes · relations) are always shown; the basic profile — the default card — is never a warning. Control ready no longer reads Degraded for a queue whose lane is busy on other stages (LANE-BUSY-ANY-STAGE-V1). Built and proven in the sealed CI reproduction; the deploy follows."
architecture_impact: "shared/polymath_shared/document_status.py (corpus_document_summaries: run_status, work_open, work_failed per file via _attach_run_work); control/control/stall_tracer.py (stage_busy_live counts a worker type's leases on any stage); frontend-v2 lib/readiness.ts (docStatus, docPmap, docProfile, stageWords; vnextReady green for the basic-profile library; ReadyState `working`), lib/contracts.ts, screens/Files.tsx (columns, header counts), styles/app.css (pill--working); tests."
last_reviewed: 2026-10-02
---

# FILES-STATUS-TRUTH-V1: the Files list says what each file's state is (+ LANE-BUSY-ANY-STAGE-V1)

## Contract
- The owner, 2026-10-02: "THE UI MAY NEED TO BE UPDATED ESPECIALLY FILES COLOR AND STATUSES IDK WHATS WRONG OR NOT SURE", then
  "I NEED TO KNOW PMAPS PER DOCUMENTS AND IF DOCUMENT PROFILE IS COMPELTED AND REGISTERED FOR RETRIEVAL AND ROUTING ALSO AND
  GRAPH NODES NUMBER PER FILE ALSO."

## Measured (the live app in the browser, the app's API, read-only Postgres)
- Cinema's Files list: all 77 files amber "Ready · basic profile" — the basic profile is the default card (vNext writing off
  since 2026-09-17; the selection guard keeps the richer basic cards), so the warning color said nothing. The five files whose
  `project_qdrant` failed on embedder 500s (2026-09-06/07) and were running again after the owner's retry read the same "Ready"
  — the list never looked at a file's run or tickets. Commerce's two books whose extraction failed on a provider 503
  (2026-09-21; 0 facts, passages searchable) read "Ready" too.
- pMAP, graph and profile were behind the owner-only "Pipeline details" toggle; the Profile column showed the card's writer, not
  whether search uses it; graph counts were blank for a file without a finished extraction.
- Control ready read amber "Degraded — 62 units traced as stalled (READY_UNCLAIMED×61 …)" while the summary lane drained 58
  enrichment tickets (13 done in 15 min): `stage_busy_live` counted only leases on the ticket's OWN stage, so a lane whose two
  workers were busy on vocabulary and enrichment read as half idle.

## Changes
- **`corpus_document_summaries`** (additive, two indexed reads, 138 ms for cinema's 77 files with the existing ones): each file's
  own run (the `document_status` rule: the newest live run that chunked it) — `run_status`, `work_open` (stages ready / leased /
  pending; the pending tickets of a run with a FAILED ticket wait on that failure and are not listed), `work_failed`
  ([{stage, note}], note ≤ 200 chars).
- **Status column** (`docStatus`), in the order a person acts on it: red **Not searchable** (unresolved parents / no profile) →
  amber **Needs retry** (which step failed and why; "the file is searchable meanwhile") → amber **Degraded / Failed** (run not
  promoted) → blue **Processing** (run not yet query_ready; the running steps in plain words) → green **Ready** (summaries
  still being written show in the title). A new `working` state paints blue (`--accent`, already in the contrast gate).
- **Always-visible columns**: **pMAP** "mapped + excluded / eligible" (red while any parent is unresolved; the counts in the
  title); **Profile** "Basic · in use" / "vNext · in use" (green: the profile index serves the card — what retrieval and routing
  read), "Not in index" (amber: built, not served), "None" (red), grey writer only when the index was not read; **Graph**
  "N nodes · M relations" ("—" without a finished extraction). "Pipeline details" keeps Parents / Children / excluded /
  unresolved. The header counts ready / processing / need retry / not searchable.
- **Library vNext card**: a library whose files are all searchable on basic profiles reads green "Searchable · basic profiles"
  (was amber); red stays for a library retrieval would miss part of.
- **Stall tracer** (`stage_busy_live`): a worker type's live leases on ANY stage count — one worker holds one lease at a time.

## Proof
- UI (vitest, jsdom): `files-states.test.tsx` 19 (10 new or rewritten: Processing / Needs retry / background Ready, pMAP red
  and green, Profile in use / not in index, Graph nodes and "—", green library card, header counts); the full suite 180 passed,
  7 skipped (25 files); `tsc` clean.
- Backend: `tests/contracts/test_files_status_truth.py` (2: open / failed work per file, a failed run's pending tickets not
  listed, the note bounded, no ticket read without a run); `test_control_plane_status` scripts the two reads and asserts the
  fields; `test_stall_tracer` +1 (a lane busy on two stages is saturated; an idle third worker makes the ticket traced).
- The new reads on the live data (read-only): cinema 72 query_ready + 5 reconciling (the retried files: `project_canonical`,
  `verify_projections`, `compile_objects` open), commerce 2 reconciling (extraction running after the owner's retry), taste 21
  query_ready with nothing open.
- Fail first on the deployed code (`92f570e2`): the 10 new UI tests fail, the 9 unchanged pass.
- Fail first on the deployed code for the backend (sealed container): the lane test and the summary-fields test fail, 16
  pass. Sealed CI reproduction on this tree: contracts **878 passed**, 5 skipped, 0 failed; determinism **3,294 passed**,
  35 skipped, 1 failed = the container's own trusted-login artifact (passes on GitHub). Code wiki 2,241 / 2,241; guards 0.

## Contract impact (pre-commit)
- `contract_impact.py --check --staged`: none (no changed file maps to an architecture contract).

## Rejected claims
- "Show whether every passage is in the index per file": a per-file count of indexed passages joins 72k chunk rows with 645k
  receipts — 1.3–1.8 s per load on cinema (EXPLAIN: a hash join with an external sort). The profile question the owner asked
  ("registered for retrieval and routing") is answered by the profile index itself (served cards), which the list already
  reads; per-file index projections stay in the file's details drawer.

## Open contract gaps
- The near-duplicate refusal still leaves its run at `intake` (harmless since DEAD-CHAIN-NOT-IN-FLIGHT-V1); it is not a
  document, so it does not appear in the Files list.
