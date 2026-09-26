---
change_id: FRIENDS-ACCESS-F0
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The owner's live instruction (friends on rag.kingsleylab.xyz with their own logins, self-service API keys and a connect prompt) admitted as plan of record FRIENDS-ACCESS-V1, ahead of the ideation worker pack."
architecture_impact: "none (documents only: the plan, the register, CONTINUITY, the scaffold)"
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F0: the plan admitted

## Contract
- The owner (2026-09-26): friends use the website, its tools and its MCP; "a login so it's not accessible to anyone"; a Settings tab
  where each user generates API keys and copies a prompt for their agent harness.
- The owner's answers: own logins per friend (King = admin), friends may do everything, 3 keys each, no daily cap.

## Changes
- `docs/wiki/plans/FRIENDS-ACCESS-V1.md`: the baseline (per-friend MCP principals already exist), decisions D1–D10, the route policy,
  slices F0–F6.
- Register 11.497; CONTINUITY's CURRENT block names FRIENDS-ACCESS-V1 as the active mission (the worker pack moves after it).

## Proof
- READ: `orchestrator/mcp_principals.py`, `scripts/mcp_principals.py`, `shared/polymath_shared/principal_context.py`, the route list
  (55 routes in `orchestrator/api/*.py`), the Caddyfile (one basic-auth user), the principal registry (3 acceptance principals).

## Rejected claims
- "Share King's login with friends": the owner chose own logins; a shared login would give every friend owner power (S-15).
- "Store the password the owner typed": never; the owner sets it privately at go-live.

## Open contract gaps
- S-15 closes with F2 + F5. The three locks (D9) stay unless the owner says otherwise.
