---
change_id: FRIENDS-ACCESS-F4
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The web UI's sign-in, first-password change, friend-only navigation and the Settings screen (account, API keys shown once with the connect prompt, the owner's friend admin) are built and tested on feat/friends-access; not merged."
architecture_impact: "frontend-v2: App.tsx (a sign-in gate around the old App, now Workspace), lib/api.ts (the CSRF header on every state-changing request, a 401 event, error codes, PUT), lib/auth.ts (new), screens/Login.tsx + Settings.tsx (new), app.css, vite.config.ts (/auth, /keys, /admin proxied in dev)."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F4: the Settings UI

## Contract
- FRIENDS-ACCESS-V1 D7/D8 and the owner's ask: a login, and "a copy and paste settings tab where users can generate … api key[s]
  and a prompt to send to their agent harness".

## Changes
- The gate (`App`): `/auth/me` → the sign-in screen on 401; the first-password change when required (nothing else opens); the
  workspace otherwise. A 401 anywhere (the `polymath:auth-required` event from lib/api.ts) returns to sign-in. A backend without
  logins (a 404 on `/auth/me`: an older build, or the merge → bounce window) behaves as before: the owner.
- The workspace for a friend: Overview, Control Plane and Models hidden (their data is owner-only on the server); Chat is the start
  screen; no Delete corpus; no control-plane probe; the friend's private library `fr-<username>` is offered in the library picker
  even before its first upload (the upload creates it).
- Settings: account (change password: 10+ characters; sign out), API keys (create with a label; the key and the filled-in prompt
  shown ONCE with copy buttons; list; revoke; "N of 3"), the connect prompt with a placeholder, and for the owner: friends (add →
  the first password shown once; disable / enable; reset password → shown once; libraries as checkboxes; a friend's keys + revoke).
- lib/api.ts: `X-Polymath-CSRF` from the `polymath_csrf` cookie on POST / PUT / DELETE / multipart / the chat stream.

## Proof
- `npx tsc --noEmit` clean; `npm run build` builds; `npx vitest run`: 29 passed, 7 skipped (the live ones), including
  `src/__tests__/friends-access.test.tsx` 7 tests (sign-in → friend workspace without owner screens and without an owner-only
  request; 401 → sign-in; the forced password change; the CSRF header on writes; a friend's key shown once and gone after "I've
  saved it"; the owner's friend manager with a first password shown once; a backend without logins = the owner). The existing
  chat tests are unchanged and green.

## Rejected claims
- "Hide screens and call it security": the server enforces every rule (F2); the UI only avoids showing a friend what they cannot use.

## Open contract gaps
- F5: the Caddy change, the session secret, King's password, the live check through rag.kingsleylab.xyz.
