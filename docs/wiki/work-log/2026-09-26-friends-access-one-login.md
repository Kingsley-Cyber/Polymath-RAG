---
change_id: FRIENDS-ACCESS-ONE-LOGIN
owner: "@king"
date: 2026-09-26
status: complete
status_note: "One login on the website: King's web password is set from Settings on the server itself, and Caddy's shared basic-auth is removed."
architecture_impact: "orchestrator/orchestrator/api/web_auth.py (/auth/owner-password, web_password_set), orchestrator/orchestrator/web_boundary.py (one rule), frontend-v2 Settings (Website sign-in card) + auth client, tests."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS: one login

## Contract
- The owner, 2026-09-26: "I DONT LIKE the login logic if i enter my username and password a 2nd one is dumb."

## Changes
- **The cause.** The website asked twice: Caddy's shared basic-auth popup, then the app's own sign-in. Go-live step 6
  (remove basic-auth) runs only after step 5, and step 5 is King's password at a hidden terminal prompt that was never
  answered. So King's app password was never set, and the popup stayed.
- **`POST /auth/owner-password`.** It sets King's web password from the server itself (http://127.0.0.1:7200, where no
  sign-in exists).
  - Through the proxy it is refused: 401 without a session, 403 `LOCAL_ONLY` even with an owner session (a signed-in owner
    changes a password with `/auth/password`).
  - A friend is refused with 403 `OWNER_ONLY` (OWNER class in the web boundary). A short password gets 422.
- **`/auth/me` on the server** now reports `web_password_set`.
- **Settings → "Website sign-in"** on the server shows set / change, with two password fields and the rule "10+ characters".
  It needs no terminal.
- **Then Caddy's basic-auth is removed** with the same validated, backed-up `friends_access_caddy.py --apply`, and the
  waiting go-live script is stopped. Its remaining steps (5 and 6) are covered by the card and the Caddy switch.

## Proof
- `test_web_owner_password.py`, 3 tests:
  - on the server: set, `/auth/me` flips, and the website then signs King in with it;
  - refused through the proxy, with or without an owner session;
  - a friend is refused, a short password is refused, and the boundary class is OWNER.
- `shell.test.tsx` +2 tests: the local owner's card posts the password; a friend never sees the card.

## Rejected claims
- None.

## Open contract gaps
- FRIENDS-ACCESS F6 close-out: the live check once the owner has set the password.
