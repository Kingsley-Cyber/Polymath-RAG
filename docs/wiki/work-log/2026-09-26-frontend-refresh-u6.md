---
change_id: FRONTEND-REFRESH-U6
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Owner screens and polish: the last browser pop-ups become dialogs, Models' unstyled classes styled, the legacy variable aliases removed, and a guard test keeps the refresh's fixes. FRONTEND-REFRESH-V1 complete except U4b."
architecture_impact: "frontend-v2 only: src/ui/Dialog.tsx (useConfirm), src/screens/Models.tsx, src/screens/Settings.tsx, src/styles/tokens.css (aliases removed), src/styles/app.css (Models), four files migrated off the aliases, src/__tests__/refresh-guards.test.ts (new), src/__tests__/node-fs.d.ts."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U6: owner screens and polish

## Contract
- FRONTEND-REFRESH-V1 slice U6 (plan of record 11.504); problems P12 (browser pop-ups) and P13 (unstyled classes, legacy names).

## Changes
- **`useConfirm()`** on the Dialog: `if (!(await confirm({title, body, action, danger})))`. It replaces the last
  `window.confirm`s: delete a provider (Models), revoke a key and reset a friend's password (Settings).
- **Models.** The nine classes it used without any CSS (`models__form`, `models__form-title`, `models__form-actions`,
  `models__models`, `models__enabled`, `models__chips`, `models__test`, `ok`, `bad`) are styled. The add/update form is a
  responsive grid; model chips and test results read clearly.
- **Retired color names.** The pre-refresh aliases (`--fg`, `--line`, `--bg-sunken`, …) are removed from `tokens.css` after
  migrating their last four uses (Graph, QueryTrace, EvidenceInspector, AnswerReview).
- **`refresh-guards.test.ts`** reads every source file under `src/` and fails on:
  - `window.prompt` / `confirm` / `alert`;
  - a retired color name;
  - a hex color outside `tokens.css`;
  - a Google Fonts URL.

## Proof
- vitest 78 passed (5 new guard tests); `tsc --noEmit` clean.
- The live contract check against :7200 (`npx vitest run src/__tests__/live-contract.test.ts`) passed:
  - 5 read-only checks, including /compare over all five modes (retrieval only) and the GNN route;
  - the 7 paid live-chat checks stay skipped (the owner's word).
- Seen on the dev server: Models' form and provider table.

## Rejected claims
- None.

## Open contract gaps
- **U4b: citation hover cards in chat answers.** Not built.
- **The frontend-v2 `node_modules` link.** The worktree has a local symlink to the main checkout's `node_modules`; it is untracked and never committed.
