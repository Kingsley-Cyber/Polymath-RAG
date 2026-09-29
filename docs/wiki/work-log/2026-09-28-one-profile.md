---
change_id: ONE-PROFILE
owner: "@king"
date: 2026-09-28
status: complete
status_note: "One profile (King): a redesigned sign-in page (username + password with Show, no sign-up), Settings as one column (profile, website password, connect Claude Code and Codex with one command + one key-free prompt, appearance, deep research); sign-ups closed by default; a clear answer when King's password was never set. The owner's admin key never reaches a browser."
architecture_impact: "orchestrator/orchestrator/api/web_auth.py (signups_open / POLYMATH_WEB_SIGNUPS, OWNER_PASSWORD_NOT_SET); orchestrator/orchestrator/api/web_settings.py (connect_command, owner_prompt, usage_lines; /keys/prompt for the owner); scripts/connect_agents.sh (new); frontend-v2 Login.tsx, Settings.tsx, lib/auth.ts, ui/CopyField.tsx (new), ui/PasswordInput.tsx (new), ui/icons.tsx, styles/app.css; tests: test_connect_agents.py (new, 11), test_web_settings.py, test_web_invite_signup.py, test_web_owner_password.py, one-profile-signin.test.tsx (new, 6), friends-access / shell tests; invite-signup.test.tsx removed with its UI."
last_reviewed: 2026-09-28
---

# ONE-PROFILE: one sign-in, one Settings page, copy-paste agent setup

## Contract
- The owner, 2026-09-28: "YOU HAVENT FIXED THE DESIGN OF THE LOGIN AND USERNAME, and prompt and api. its not designed well and
  i cant login ... rn just for simplicity universal log in is King ... just keep it 1 profile and copy and paste should work
  without creating a api, logging in should be good enough".
- Why the sign-in failed (live, read-only): the registry had no `owner_web` record, so King had no website password; every
  sign-in as King answered "wrong username or password". The only place to set it was a card lower on the Mac's Settings page.
- The password the owner typed in chat is NOT set by the agent (a standing safety rule: the agent never enters or stores a
  person's password). The owner sets it once on the Mac: Settings, Website password (the card now comes first while unset).

## Changes
- **Sign-in page** (`Login.tsx`): a centred panel (mark, "Polymath", one line), a card with Username and Password (a Show / Hide
  eye), a full-width Sign in, "Private site · one account". No "Create your account". Every refusal in words, including the new
  OWNER_PASSWORD_NOT_SET ("set it on the Mac: Settings, Website password"). A wrong password keeps the username and clears the
  password.
- **Settings** (`Settings.tsx`), one column of cards:
  1. Profile: avatar, name, where you are ("On this Mac: no sign-in needed here" / "Signed in as king"), Sign out on the website.
  2. Website password (on the Mac): "Username: King", ONE field with Show, Save; a Set / Not set pill; while unset the card is
     marked and comes before everything else. On the website: change my password (current + new).
  3. Connect Claude Code and Codex (the owner): step 1, one command with a visible Copy button
     (`bash <repo>/scripts/connect_agents.sh`); step 2, "Restart the app, then paste this into it" with a primary Copy prompt
     button and a preview. Nothing to create.
  4. Appearance, deep research (unchanged).
  - Gone from the page: the owner's API-keys note, the placeholder prompt, Invite, the Friends table (probe accounts included).
    Their server routes stay (existing accounts still sign in; a friend's page keeps their own key card).
- **Backend**: `/auth/register` answers 403 SIGNUPS_CLOSED unless `POLYMATH_WEB_SIGNUPS=1` (counts nothing); `/auth/login` as
  King before any password exists answers 409 OWNER_PASSWORD_NOT_SET (counts nothing; any other refusal is unchanged);
  `/keys/prompt` for the owner returns `connect_command` + a key-free `owner_prompt` (the libraries listed); a friend's prompt
  keeps the placeholder and now gives the replace-safe commands (Claude Code user scope; Codex `http_headers`).
- **`scripts/connect_agents.sh`** (new): reads `POLYMATH_MCP_API_KEY` from `.env` on the Mac, checks it with one MCP `initialize`
  (the header through a file descriptor, never on curl's command line), then replaces the `polymath` entry in Claude Code
  (`claude mcp add -s user -t http`) and Codex (`codex mcp remove`, then ONE `[mcp_servers.polymath]` section with
  `http_headers = { Authorization = "Bearer …" }`, the config chmod 600). Never prints the key. Refused key = exit 2, nothing
  changed; a Codex config that still holds the section = exit 3, nothing appended. The default URL is the local Server A
  (`http://127.0.0.1:8930/mcp`): the Mac's agents do not depend on the tunnel.
  - Why a fixed header for Codex: the owner's Codex had `bearer_token_env_var = "POLYMATH_MCP_KEY"`; the Codex app never sees
    a shell's exports, so it sent no key (the "blocked" the owner pasted on 2026-09-27). Codex 0.157.1 reads `http_headers`
    (checked in its binary).

## Contract dispositions
- "copy and paste should work without creating a api": the owner copies one command (no secret in it) and one prompt; no key is
  created. The first design put the admin key itself into the Settings prompt; the harness refused that change as credential
  leakage, and it was NOT pursued another way. The command reads the key on the Mac, so the key never reaches a browser, a page
  or this chat.
- "just keep it 1 profile": sign-ups closed by default; the Friends / Invite admin left the page; nothing was deleted or disabled
  in the registry (the acceptance principals `prn_accept_a/b/e2e`, the disabled probes and `ugo` remain; a clean-up is the
  owner's call).
- "universal log in is King": the website signs in `King` in any capitalisation (the backend already lower-cases); the password is
  the one the owner sets on the Mac.

## Proof
- Backend: `test_connect_agents.py` 11 passed (a sandbox: stub `claude` / `codex` on a PATH without the real ones, HOME and
  CODEX_HOME in tmp, a fake key, a stub MCP server; the resulting Codex config parses with `tomllib`; the key never appears in
  the output). Web tests (`test_web_settings`, `test_web_invite_signup`, `test_web_owner_password`, `test_web_boundary`,
  `test_friends_access_go_live`, `test_connect_agents`) 118 passed. **Fail first**: the new tests against the deployed code
  (`git archive production` in the scratchpad, the new test files copied in): 23 failed, 31 passed.
- Frontend: `tsc --noEmit` clean; `vitest run` 24 files, 163 passed, 7 skipped (the live-contract tests).
- Visual (dev preview of this branch against the live :7200): the sign-in panel on desktop and at 375 px; Settings with the
  password card first while unset. The connect command box stays empty until the backend change is deployed (the live
  orchestrator answers the old prompt shape).
- Live checks (read-only, no key used): the public MCP URL answers 401 (the server, not Cloudflare) to Claude Code's, Codex's,
  node's, curl's and httpx's User-Agents; the local `http://127.0.0.1:8930/mcp` answers 401 without a key.

## Rejected claims
- "Showing the admin key in Settings is the simplest way to make copy-paste work": refused by the harness as credential leakage;
  the connect command meets the owner's goal without it.
- "The owner cannot sign in because the password rule is wrong": the rule was already "any non-empty password" (11.543); no
  password had ever been saved.

## Open contract gaps
- The owner sets King's website password on the Mac (Settings, Website password); the agent never types it.
- An agent on ANOTHER computer still needs a key: the connect command reads `.env`, which exists only on the Mac.
- The registry keeps the acceptance principals (named "revoke after"), two disabled probes and `ugo`: disable or keep, the
  owner's call.
