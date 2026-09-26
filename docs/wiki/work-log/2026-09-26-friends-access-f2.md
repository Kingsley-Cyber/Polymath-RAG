---
change_id: FRIENDS-ACCESS-F2
owner: "@king"
date: 2026-09-26
status: complete
status_note: "The web boundary, the login routes and friend narrowing inside the routes are built and proven on feat/friends-access; not merged (the Settings UI, keys and admin follow)."
architecture_impact: "orchestrator/orchestrator/web_boundary.py (new ASGI middleware, outside PrincipalContextMiddleware), web_scope.py (new: registry cache, narrow_scope, require_corpus / require_document / require_adapter_start), api/web_auth.py (new: /auth/login|logout|me|password); guards in 8 route modules; main.py wiring. Direct loopback callers unchanged; a proxied caller needs a session."
last_reviewed: 2026-09-26
---

# FRIENDS-ACCESS F2: the web boundary

## Contract
- FRIENDS-ACCESS-V1 D2–D5, D9: proxied requests need a session (public routes excepted); friends never reach owner routes; CSRF on
  state-changing requests; a browser can never claim a principal; friends narrowed to their libraries inside the routes; a route
  the policy does not know is refused.

## Changes
- `web_boundary.py`: `RULES` (the plan's §3 route policy, first match wins; `/health/pipeline` moved to owner-only because it can name
  documents), `classify`, `WebBoundaryMiddleware` (drops any incoming `X-Polymath-Principal`; 401 LOGIN_REQUIRED / 403 CSRF_FAILED /
  PASSWORD_CHANGE_REQUIRED / OWNER_ONLY / ROUTE_NOT_ALLOWED / 503 LOGIN_NOT_CONFIGURED; forwards a friend's principal id; the owner
  is forwarded as no principal = full reach).
- `web_scope.py`: `RegistryCache` (re-read on change, fail closed when unreadable or group readable), `current_principal` (an unknown
  or inactive principal is refused), `narrow_scope` (explicit foreign library refused, broad scopes narrowed), `require_corpus`,
  `require_corpora`, `require_document`, `can_see`, `filter_by_corpus`, `require_adapter_start` (the SAME rule as Server A's START:
  libraries from `input.corpus_ids` and `request_options.corpus_ids`, at least one, all allowed).
- Guards: `resolve_http_scope` → `narrow_scope` (covers /chat, /chat/stream, /chat/evidence, /ask, /retrieve, /evidence), `/compare`,
  `/retrieve/plan`, both graph routes, `/queries` (a friend names a library), `/semantic_readiness`, `/adapter/start`, `/corpora`
  (filtered), `/documents`, `/documents/summary`, `/documents/{id}/sections|status`, `/upload` (writable), `DELETE /documents/{id}`
  (writable).
- `api/web_auth.py`: login (throttle per username and per address: Cloudflare's `CF-Connecting-IP` first), logout, me (a direct
  caller is the owner, as before), password (a fresh session after the change). Cookies: session HttpOnly + Secure + SameSite=Strict;
  CSRF cookie readable by the page.

## Proof
- UNIT_PROVEN + WORKTREE_INTEGRATION_PROVEN (PYTHONPATH origins inside `pmv4-friends`):
  - `tests/contracts/test_web_boundary.py` 46 tests: every orchestrator route classified (>50 seen, through FastAPI 0.141's nested
    routers and static mounts); the login flow and cookie flags; CSRF; owner-only; a forged principal dropped (owner and friend);
    the first-password gate and its session refresh; the throttle; fail closed without a secret; narrowing units; the guards pinned.
  - Mutation-checked: removing the CSRF check, keeping a forged header, or dropping the resolver's narrowing each fails a test.
  - `tests/contracts` whole: 245 passed, 0 failed. Impacted determinism files (the impact tool's list minus the fleet-DB files):
    491 + 213 tests, 0 new failures; the one failure (`test_chat_runtime::test_compiler_on…`) is the known pre-existing one;
    `tests/integration/test_cross_domain_routing.py` skips on production and fails to import only under the worktree PYTHONPATH
    (it imports `orchestrator.orchestrator…`).
- The existing MCP gate tests caught my first version of the adapter-start guard (it read only `input.corpus_ids`); fixed to Server
  A's rule before this commit.

## Contract dispositions
- ADAPTER_RUNTIME: TESTED_UNCHANGED (schemas untouched; the start route narrows principals; `test_adapter_contract_v1`,
  `test_mcp_adapter_parity`, `test_mcp_principals_gate` green).
- EVIDENCE_BOUNDARY_API: TESTED_UNCHANGED (the owner / local path is unchanged; principals narrowed; evidence packet contract green).
- PROFILE_SCOUT_WIRING: NOT_AFFECTED (no profile-scout code touched; its tests green).
- Transitive (ACCEPTANCE, CANDIDATE_ENGINE, EVIDENCE_PACKET, MCP_SURFACE, PROFILE_YIELD_RECEIPT, QUERY_PLANNER, RESOLUTION_STATE,
  RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE): TESTED_UNCHANGED.

## Rejected claims
- "Check libraries in the middleware by reading request bodies": fragile across JSON, forms and streams; the guards sit where the
  library is known, and a test pins them.
- "An unknown principal means no narrowing": fail open; it is refused.

## Open contract gaps
- F3: self-service keys + owner admin + the private library row; F4: the Settings UI; F5: the Caddy change and the secret line.
