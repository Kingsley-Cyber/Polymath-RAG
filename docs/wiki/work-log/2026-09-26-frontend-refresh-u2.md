---
change_id: FRONTEND-REFRESH-U2
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The shell: a top bar, a phone drawer, the icon rail on tablets, the Dialog piece; Delete library moved to Files behind a typed confirmation; friends' Files shows only usable controls."
architecture_impact: "frontend-v2 only: src/App.tsx (shell), src/screens/Files.tsx (props, gating, danger zone), src/ui/Dialog.tsx (new), src/styles/app.css (top bar, drawer, dialog, media queries), src/__tests__/shell.test.tsx (new), src/__tests__/friends-access.test.tsx (the delete label)."
last_reviewed: 2026-09-26
---

# FRONTEND-REFRESH U2: the shell

## Contract
- FRONTEND-REFRESH-V1 §4 / slice U2 (plan of record 11.504); problems P3, P5, P9, P12 (library delete).

## Changes
- **Top bar.** The library picker (a labelled select), the owner's control-plane status (a link to Control Plane), a light/dark
  toggle, and an account menu (name, Settings, Sign out; no Sign out on the server itself). The sidebar keeps brand, New chat,
  navigation and Recent chats.
- **Screen sizes (the app had no media queries).**
  - Under 760 px the sidebar is a drawer, opened from the top bar. Esc, the scrim or choosing a screen closes it.
  - Tablets (< 1100 px) start on the icon rail when there is no stored choice.
  - Screen padding shrinks on small screens.
- **`ui/Dialog.tsx`.** A modal on the native `<dialog>`, mounted only while open, plus `ConfirmByName` for destructive actions.
- **Delete library** moved from the sidebar into Files → "Delete this library" (owner), behind a dialog that asks for the name.
  It replaces `window.prompt` / `alert`.
- **Found on the way (friend-facing, since FRIENDS-ACCESS-V1):**
  - Files called the owner-only `/control_plane` for friends. The route refused it, and the screen showed "not reachable".
  - Friends saw Continue, Add Files and Delete buttons that the server refuses.
  - Files now takes `isOwner` and `canWrite` (the owner everywhere; a friend only in their private library). A shared library
    says it is read-only for them.

## Proof
- `shell.test.tsx`, 8 tests:
  - the picker is in the top bar and not in the sidebar;
  - the light/dark toggle, including storage;
  - the account menu opens Settings and closes, and has no Sign out on the server itself;
  - the drawer opens, and Esc and navigation close it;
  - an owner deletes a library only after typing its exact name (the DELETE carries `confirm=<name>`);
  - a friend's Files in a shared library shows no owner or write controls and never requests `/control_plane`;
  - in their private library, a friend can add and delete files.
- The friends test now checks that a friend never sees "Delete library".
- Totals: vitest 62 passed; `tsc --noEmit` clean; build green.
- Seen on a dev server from this worktree against :7200 (the live `dist` untouched):
  - desktop 800 px: the top bar;
  - phone 375 px: full-width content, and the drawer over a scrim;
  - the delete dialog, opened and cancelled; nothing typed, nothing deleted.

## Rejected claims
- "A closed native dialog is invisible, so its text does not matter": its text stays in the DOM, and tests reading page text saw
  it. The Dialog renders nothing while closed.

## Open contract gaps
- U3 (icons and the remaining pieces), U4 (Chat), U5 (Files states and columns, Graph, Compare, Overview wording), U6.
