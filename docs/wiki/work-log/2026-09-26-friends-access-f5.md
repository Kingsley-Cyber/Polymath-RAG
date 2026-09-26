---
change_id: FRIENDS-ACCESS-F5
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The go-live kit is built and tested: ONE Run-button script (merge, session secret, UI build, bounce, King's password, Caddy) and a $0 read-only live check. F6 = the owner runs it."
architecture_impact: "scripts/friends_access_caddy.py (new), scripts/friends_access_go_live.sh (new), docs/wiki/experiments/friends-access-2026-09-26/live_check.py (new), mcp_server/CONNECTORS.md (friends' path), scripts/README.md; callers of the public site: docs/wiki/experiments/autoresearch-e2e-2026-09-25/live_check.py, scripts/verify_final_state.py."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F5: the go-live kit

## Contract
- FRIENDS-ACCESS-V1 F5/F6: one Run button for the owner; Caddy stops asking for the shared password and strips any principal
  header a browser sends; King's password set privately; a live check through the public site.

## Changes
- `scripts/friends_access_caddy.py`: `transform` removes the `basic_auth { … }` block from the `:8794` site and adds
  `request_header -X-Polymath-Principal`, keeping everything else; `--apply` backs up, runs `caddy validate`, writes; idempotent.
- `scripts/friends_access_go_live.sh`: (1) `git merge --ff-only feat/friends-access` on `production` (stops if the checkout is on
  another branch), (2) `POLYMATH_WEB_SESSION_SECRET` added to `.env` once (generated inline, never printed), (3) `npm run build`,
  (4) `scripts/bounce_fleet.sh`, (5) `web_accounts.py set-owner-password` at a hidden prompt unless already set (no terminal → stop
  with the command to run), (6) the Caddy change + `launchctl kickstart -k …/com.hermes.rag-caddy`.
- `live_check.py`: app shell + /health open without a basic-auth challenge; `/corpora` answers the app's LOGIN_REQUIRED (with and
  without a forged principal header); `/llm/providers` closed; ONE wrong password → BAD_LOGIN; on the server itself `/auth/me` = the
  owner and a proxied-looking request gets LOGIN_REQUIRED (the boundary is loaded); MCP Server A answers the owner key.
- `CONNECTORS.md` §4: the friends' path (sign in → Settings → Create key → copy the prompt).
- Callers of rag.kingsleylab.xyz, checked before go-live (MCP Server A never forwards X-Forwarded-* headers, so every MCP call stays a
  direct loopback caller the boundary leaves alone; no Hermes config names the site):
  - `autoresearch-e2e-2026-09-25/live_check.py`: its proxied `/adapter/{run}/acquire` probe now meets the web boundary first, so it
    accepts 401 LOGIN_REQUIRED (no session) as well as 403 PROXIED_CALLER (the route's own refusal, still what a signed-in owner gets),
    and reads the code from `code` or `error_code`.
  - `verify_final_state.py`: `/v2/` answering 200 is still PASS; the message now says the sign-in lives inside the app.
  - `friends_access_go_live.sh`: steps 5 read the accounts file from `.env` (`POLYMATH_MCP_PRINCIPALS_FILE`, falling back to the
    CLI's default) and pass it as `--file`, so King's password lands in the file the orchestrator reads. `list` on the live file
    (read-only) answered `owner_login: NOT SET`, `friends: []`.

## Proof
- UNIT_PROVEN: `tests/contracts/test_friends_access_go_live.py` 5 tests (the transform on the current Caddyfile shape; idempotence;
  a missing site refused; no write without --apply; `bash -n` + step order + ff-only + no secret echo; the live check compiles and
  imports without network).
- EXECUTED on a scratch COPY of the real Caddyfile: the dry run names the two changes; `--apply` on the copy passed
  `caddy validate` ("Valid configuration"). The real Caddyfile is untouched until the owner's Run button.

## Rejected claims
- "Reload Caddy through its admin API": the Caddyfile turns the admin API off; the service is restarted instead (KeepAlive).
- "Switch Caddy before King has a password": the script stops at step 5 until the password exists, so the owner can always sign in.

## Open contract gaps
- F6: the owner's Run button, then the live check, then the first friend.
