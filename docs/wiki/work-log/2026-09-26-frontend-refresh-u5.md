---
change_id: FRONTEND-REFRESH-U5
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Files, Overview, Graph, Compare: loading never looks like failure, real empty/error states, opt-in pipeline columns, a delete dialog, readable status words, keyboard-usable Graph rows."
architecture_impact: "frontend-v2 only: src/screens/Files.tsx, Overview.tsx, Graph.tsx, Compare.tsx, ControlPlane.tsx, src/App.tsx, src/components/Pill.tsx, src/lib/readiness.ts, src/styles/app.css, src/__tests__/files-states.test.tsx (new)."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U5: Files, Overview, Graph, Compare

## Contract
- FRONTEND-REFRESH-V1 §6 / slice U5 (plan of record 11.504); problems P2 (developer language), P4 (loading looks like failure),
  P7 (wide tables), P12 (browser pop-ups), P14 (mouse-only Graph rows, unlabelled searches).

## Changes
- **Loading is not failure.**
  - `readiness.settled(async, verdict)` returns `CHECKING` while nothing has answered and nothing failed. It is used on every
    readiness display (Files, Overview, Control Plane) and in the top bar.
  - Files shows a `Skeleton` and "loading documents…" instead of "0 documents" and "UNKNOWN — /control_plane not reachable".
- **Errors and empties.**
  - A failed document load shows an `ErrorState` with Retry.
  - An empty library shows an `EmptyState`. It invites the first file (with Add files) only to someone who can add one.
- **Columns.** Files shows File · Type · Added · Size · Status (+ actions). The 8 pipeline columns appear only when the owner turns on "Pipeline details".
- **Deleting one file** asks in a dialog; `window.confirm` is gone from Files.
- **Status words.**
  - `Pill.readable()` keeps the backend's own words but formats them: SEMANTIC_INCOMPLETE → "Semantic incomplete", VNEXT READY → "vNext ready".
  - The exact code stays in the tooltip and in `data-verdict`. This respects FRONTEND-V2-PLAN §7's rule that the pill never paraphrases the verdict.
- **Overview.** The note on the old `query_ready` badge is a closed "Details" section.
- **Graph and Compare.** Graph entities are buttons (keyboard-usable, `aria-pressed` for the selection), with skeletons while
  loading. The Graph and Compare searches have labels.

## Proof
- `files-states.test.tsx`, 6 tests:
  - while nothing has answered: a skeleton and "Checking", never "0 documents" or "not reachable";
  - a failed load retries;
  - an empty library invites a first file only for writers;
  - the pipeline columns are opt-in;
  - a file delete asks first, and Cancel deletes nothing;
  - the readable status words.
- The first run of the loading test found the "not reachable" leftover on the owner's status cards; `settled()` fixes it.
- vitest 73 passed; `tsc --noEmit` clean. Seen on the dev server: Overview, and Files with 67 documents in 5 columns.

## Rejected claims
- "Plain-language labels must replace the backend's verdict words": FRONTEND-V2-PLAN §7 forbids paraphrasing a verdict, so
  the words are formatted, not replaced.

## Open contract gaps
- U6: the owner screens (Control Plane, Models) on the shared pieces; remove the legacy variable aliases and the remaining
  inline styles; the final screenshots and the live contract check.
