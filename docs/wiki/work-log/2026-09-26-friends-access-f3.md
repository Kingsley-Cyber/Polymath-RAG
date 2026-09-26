---
change_id: FRIENDS-ACCESS-F3
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Self-service API keys, the connect prompt and the owner's friend admin are built and proven on feat/friends-access; not merged (the Settings UI is F4)."
architecture_impact: "orchestrator/orchestrator/api/web_settings.py (new: /keys, /keys/prompt, /admin/friends*); web_boundary.py gains `/keys/prompt`; main.py includes the router. Keys are principal keys in the registry Server A reads."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F3: keys, the connect prompt, the friend admin

## Contract
- FRIENDS-ACCESS-V1 D6–D8: each friend makes up to 3 API keys (shown once) and copies a prompt for their agent harness; the owner
  creates friends, disables them, resets passwords and chooses their libraries; a friend's private library is never shared.

## Changes
- `/keys` GET (the caller's keys, never raw), POST (friend only; 201 with the raw key ONCE and the connect prompt filled in; 409
  KEY_LIMIT at 3 active; 409 OWNER_USES_ENV_KEY for the owner), DELETE `/keys/{key_id}` (own keys only), GET `/keys/prompt` (the
  prompt with `<YOUR_KEY>`).
- `connect_prompt`: the MCP URL (`POLYMATH_PUBLIC_MCP_URL`, default `https://mcp.kingsleylab.xyz/mcp`), the header, one setup line per
  harness (the forms in `mcp_server/CONNECTORS.md`), the Cloudflare user-agent caveat, the tool order, the governed-research guide,
  the libraries open to the user, and that research needs the harness's own web tools (the `research_acquire` lock).
- `/admin/friends` GET (friends, the shareable libraries = every library except `fr-*`, the adapters), POST (a friend with "everything"
  by default: all shareable libraries + all adapters; a generated first password returned ONCE), POST
  `/admin/friends/{name}/enable|disable|reset-password`, PUT `/admin/friends/{name}/libraries`, GET / DELETE a friend's keys. A
  friend's private library is created by their first upload (the intake worker's `INSERT … ON CONFLICT DO NOTHING`).

## Proof
- UNIT_PROVEN: `tests/contracts/test_web_settings.py` 6 tests (3 keys then KEY_LIMIT; the raw key only in the create response and
  in its prompt; Server A's store authenticates exactly the created keys and not a revoked one; CSRF; the owner key never shown;
  the admin flow end to end, a disabled friend's session dies, a reset password must be changed; `fr-*` never shared; friends
  refused the admin).
- `tests/contracts` whole + `test_mcp_principals_gate.py`: 264 passed, 0 failed.

## Contract dispositions
- ADAPTER_RUNTIME, EVIDENCE_BOUNDARY_API: TESTED_UNCHANGED (no route of theirs touched in F3). MCP_SURFACE: TESTED_UNCHANGED (the key
  format and Server A's loader unchanged; web-made keys authenticate through it).

## Rejected claims
- "Show the owner's admin key in Settings": it would put the admin credential in a browser; the owner's prompt uses a placeholder.
- "Give new friends every library": never another friend's private one.

## Open contract gaps
- F4: the Settings UI; F5: the Caddy change, the session secret, the owner password step, the live check.
