---
change_id: FRIENDS-ACCESS-F1
owner: "@king"
date: 2026-09-26
status: complete
status_note: "Web accounts + sessions core built and unit-proven on feat/friends-access; nothing is wired to a route yet (F2)."
architecture_impact: "orchestrator/orchestrator/web_accounts.py (new: scrypt passwords, signed session cookies with a CSRF token, a login throttle, friend / owner web credentials and self-service keys in the existing principal registry) + scripts/web_accounts.py (new CLI). The registry schema is unchanged: new fields (`owner_web`, a principal's `web`, a key's `label`) are ignored by Server A's loader."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F1: accounts and sessions

## Contract
- FRIENDS-ACCESS-V1 D1, D2, D7, D10: one identity store (the principal registry); scrypt; signed cookies whose version dies on a
  password change, reset or disable; at most 3 active keys per friend; 5 failed logins per username and per address in 15 minutes.

## Changes
- `web_accounts.py`: `hash_password` / `verify_password` (scrypt n=2^14, r=8, p=1; random salt; constant time; a dummy hash for
  unknown users), `password_problem` (10+ characters, 4+ distinct), `update_registry` (an exclusive `flock` around read-modify-write
  with mcp_principals' atomic writer), `set_owner_password`, `add_friend` (friend scopes = "everything" but admin; read corpora +
  a private writable `fr-<username>`), `set_friend_enabled`, `reset_friend_password`, `set_friend_corpora`, `change_password`,
  `authenticate_password`, `make_session` / `read_session` / `resolve_session` / `csrf_ok`, `LoginThrottle`, `create_key` (max 3,
  raw bearer returned once) / `revoke_key` / `list_keys`.
- `scripts/web_accounts.py`: `set-owner-password` (hidden prompt, typed twice), `add-friend` / `reset-password` (a generated first
  password written to a NEW 0600 file; printed only with `--print-password`), `enable` / `disable`, `list` (no hashes).

## Proof
- UNIT_PROVEN: `tests/contracts/test_web_accounts.py` 13 tests + `test_mcp_principals_registry.py` still green (16 passed), with the
  worktree PYTHONPATH (origins verified inside `pmv4-friends`). Server A's own `PrincipalStore` loads a friend written here and
  authenticates a self-service key; a revoked key stops authenticating.

## Rejected claims
- "Take the password as a command-line argument": it would land in shell history; the owner's is typed at a hidden prompt.
- "A second accounts file": one identity store keeps web logins and MCP keys revocable together.

## Open contract gaps
- F2 wires the web boundary; the old `scripts/mcp_principals.py` writes without the lock (rare owner use; noted).
