---
change_id: OWNER-KEY-VISIBLE
owner: "@king"
date: 2026-09-30
status: complete
status_note: "Settings shows the owner's main MCP key for agents on other computers: hidden until Show, Copy key, Copy prompt with key, Copy server address; fetched only on click, owner only, never cached."
architecture_impact: "orchestrator/orchestrator/api/web_settings.py (GET /keys/owner; connect_prompt(owner=True)); orchestrator/orchestrator/web_boundary.py (/keys/owner = OWNER); frontend-v2 Settings.tsx (OwnerKeyCard), lib/auth.ts (ownerKey, OwnerKey), ui/icons.tsx (key), styles/app.css (.keyrow, .settings__warn); tests: test_web_settings.py (+2), test_web_boundary.py (+2 rows), friends-access.test.tsx (+2), shell.test.tsx (card order)."
last_reviewed: 2026-09-30
---

# OWNER-KEY-VISIBLE: the main key, visible to copy in Settings

## Contract
- The owner, 2026-09-30, asked whether someone else signing in needs a key for their Codex, was offered a separate guest key,
  and answered: "no i need them to have access to main key. so in the settings have a api key visibility settings, to copy and
  paste to get key".
- ONE-PROFILE (11.553) had kept the main key out of every browser; the harness had refused an earlier, unrequested change that
  put it into the everyday prompt. This change is the owner's explicit decision: the main key, shown to the one profile on
  request.

## Changes
- `GET /keys/owner` (owner only: a signed-in King or the server itself; the boundary classifies it OWNER, so a friend gets 403
  and an unsigned caller 401): `{key, mcp_url, prompt}`, `cache-control: no-store`; 404 OWNER_KEY_NOT_SET when `.env` has no
  `POLYMATH_MCP_API_KEY`. The prompt is `connect_prompt(key, libraries, None, owner=True)`: the public URL, the replace-safe
  setup commands (Claude Code user scope, Codex `http_headers`), the owner's usage lines (supplier tools included) and "whoever
  holds it has my full access".
- The everyday prompt (`GET /keys/prompt`) is unchanged: it never carries the key.
- Settings, the owner: a card "API key for another computer" under "Connect Claude Code and Codex": the key masked (24 dots)
  until **Show** (Hide again), **Copy key**, **Copy prompt with key**, **Copy server address**, and a one-line warning (full
  access, including the CJ supplier account). The key is requested on the first Show or Copy only, then kept for the page's
  life; a friend's Settings has no such card and never asks.

## Proof
- Backend: `test_web_settings.py` +2 (King through the proxy and the server itself get the key, the public URL and the prompt with
  the key; a friend 403 and an unsigned caller 401 with no key in the body; the everyday prompt still has no key; no key on the
  server = 404 OWNER_KEY_NOT_SET); `test_web_boundary.py` +2 rows (GET = OWNER, POST unclassified). The web + connect tests:
  117 passed. Fail first on the deployed code (`git archive production`): 3 failed.
- UI: `friends-access.test.tsx` +2 (hidden and unfetched until Show; Show reveals, Hide hides; Copy key / Copy prompt with key
  copy exactly the key / the prompt; one fetch; a friend never sees it); `shell.test.tsx` card order. `tsc` clean, vitest 167
  passed + 7 skipped (the live contract's GNN check timed out once, cold after the bounce, then passed alone in 1.5 s). Fail
  first on the deployed UI: 2 failed.

## Rejected claims
- "A guest key is safer, so build that instead": the owner chose the main key; a guest key stays available as a later option.

## Open contract gaps
- Rotating the main key is manual: a new `POLYMATH_MCP_API_KEY` in `.env`, a bounce, then `scripts/connect_agents.sh` on the Mac
  and a fresh copy for every other computer (and Hermes, which uses the same key).
