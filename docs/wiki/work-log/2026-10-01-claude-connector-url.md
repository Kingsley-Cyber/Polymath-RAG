---
change_id: CLAUDE-CONNECTOR-URL
owner: "@king"
date: 2026-10-01
status: complete
status_note: "claude.ai's custom connector reaches MCP Server A at https://mcp.kingsleylab.xyz/k/<key>/mcp (the key moves from the path into the Authorization header before anything logs it); Settings → Copy Claude connector URL. LIVE (3aa82e01) and proven from claude.ai: the owner's connector works ("it worked"), Claude's calls answer 200. Follow-up 11.561: a key further down a path (claude.ai's OAuth discovery probe) is dropped before logging."
architecture_impact: "orchestrator/orchestrator/mcp_server.py (KeyInPath middleware, /.well-known 404, claude.ai origins); orchestrator/orchestrator/api/web_settings.py (connector_url in GET /keys/owner); frontend-v2 Settings (Copy Claude connector URL) + lib/auth.ts; mcp_server/CONNECTORS.md §4; tests/contracts/test_mcp_connector_url.py (new); scripts/scaffold_polymath_v4.py (TREE)."
last_reviewed: 2026-10-01
---

# CLAUDE-CONNECTOR-URL: Polymath MCP as a claude.ai custom connector

## Contract
- The owner, 2026-10-01: "how do i connect polymath mcp to claude connector i need the url".
- claude.ai's "Add custom connector" takes a URL (plus optional OAuth client fields) and cannot send a header. Server A accepted
  only `Authorization: Bearer <key>`, so no URL could work.

## Changes
- **`KeyInPath`** (Starlette middleware on Server A, before routing): `/k/<key>/mcp[/…]` becomes `/mcp[/…]` (`path` and
  `raw_path`) with `Authorization: Bearer <key>` replacing any header the request carried. The scope dict is changed in place, so
  uvicorn's access log prints `/mcp`, never the key. Key pattern `[A-Za-z0-9._~+=-]{16,256}`; any other `/k/…` path is not a key
  path and gets the gate's 401 like any keyless call. It is middleware (not a wrapper) so `build_app()` stays a Starlette app:
  the hosted acceptance harness drives its router's lifespan.
- The bearer gate is unchanged: the owner key = full access; a friend's key = that friend's scopes, libraries and rate limit.
- `/.well-known/*` answers 404: there is no OAuth here, and the gate's 401 on those probes reads as "OAuth required".
- Allowed origins + `https://claude.ai`, `https://claude.com`, in case the connector's client sends one (not observed; an absent
  Origin already passes; every `/mcp` call still needs a key).
- `GET /keys/owner` adds `connector_url` (`web_settings.connector_url(key)`, built from `POLYMATH_PUBLIC_MCP_URL`). Settings →
  "API key for another computer" adds **Copy Claude connector URL** and a one-line how-to.
- `mcp_server/CONNECTORS.md` §4: the claude.ai steps (it had said "auth header", which that dialog does not have).
- **Follow-up (11.561), seen live:** after a successful `POST /mcp`, claude.ai's dialog still probes OAuth discovery at
  `/.well-known/oauth-protected-resource` + the connector's resource path, i.e. `…/k/<key>/mcp`. `KeyInPath` matched only a
  path that STARTS with `/k/`, so that line printed the key in Server A's access log (`/private/tmp/polymath_fleet/mcp.log`,
  once). Now a key segment anywhere in a path (`/k/<key form>` before `/mcp`) becomes `/k/redacted` in place, with no
  Authorization header added (it is not a connector call); the path stays a 404.

## Proof
- `tests/contracts/test_mcp_connector_url.py` (6): the owner key in the path initializes like the header; a friend key in the path
  is judged as that friend; a wrong, missing or too-short key → 401; a path key replaces a stale header key; the layer rewrites
  `path` + `raw_path` in place and sets the header; `/.well-known/*` → 404 while `/health` stays 200. `test_web_settings.py`: the
  exact `connector_url`. `friends-access.test.tsx`: the button copies exactly the connector URL, with one fetch.
- Fail first on the deployed code (`git archive 43ca3092` + the new tests): the 5 path tests and the web-settings test failed (the
  refusal test passed, as it should); the UI test failed on the deployed UI.
- MCP + web suites (connector, hardening, supplier tools, hosted acceptance, determinism `test_mcp_server_v2`, web settings, web
  boundary): 114 passed. UI: `tsc` clean, vitest 163 passed in 23 files (the live contract check excluded).
- Over a real socket (uvicorn on a spare port, this worktree's module, a test key, Host = the public host): initialize 200,
  tools/list 200 with the tools, a wrong key 401, the OAuth probe 404; the access log shows `POST /mcp` and never the key.
- **Live (after the owner deployed `3aa82e01`).** Through `https://mcp.kingsleylab.xyz` from the Mac, the key read from `.env`
  and never printed: initialize 200, tools/list 200 with the tools, a wrong key 401, the OAuth probe 404, the header form still
  200, the key in no response body. From claude.ai (Anthropic's 160.79.106.x): the first attempts sent the message's placeholder
  `<your main key>` (401, then OAuth probes and a `POST /register` 401, with "Sign in now" pre-selected); with the copied URL and
  "No sign-in", `POST /mcp` answers 200 (34 Claude-side calls, the newest all 200), and the owner confirmed "it worked".
- The one logged key was overwritten in place (same length, the running server's file handle untouched): 1 → 0; 34 other fleet,
  tunnel and user log files searched: none held it.
- Follow-up test `test_a_key_further_down_a_path_never_reaches_any_layer`: fails on the deployed `3aa82e01`, passes now; the MCP
  suites (connector, hardening, supplier tools, hosted acceptance, adapter parity, principals registry, determinism
  `test_mcp_server_v2` + `test_mcp_principals_gate`): 70 passed, the orchestrator URL pointed at a dead port. Real socket: the
  probe `/.well-known/oauth-protected-resource/k/<key>/mcp` answers 404 and the key is absent from the log.

## Contract impact (pre-commit)
- MCP_SURFACE [live] (`orchestrator/orchestrator/mcp_server.py`): UPDATED — one more way to present the same key (the URL
  form) and a 404 for `/.well-known/*`; tools, scopes and refusals unchanged. TESTED_UNCHANGED: `test_hosted_mcp_acceptance`,
  `test_mcp_server_v2` (in the 114 above), `test_mcp_adapter_parity`, `test_mcp_principals_registry`, determinism
  `test_mcp_principals_gate`: 24 passed, the orchestrator URL pointed at a dead port.
- 11.561: MCP_SURFACE UPDATED — a key-shaped segment elsewhere in a path is redacted before routing; every response is
  unchanged (that path was and is a 404). TESTED_UNCHANGED: the 70 MCP tests listed under Proof.

## Rejected claims
- none.

## Open contract gaps
- The URL is the key: whoever holds it has that key's access, and claude.ai stores it in the account. Rotation = a new
  `POLYMATH_MCP_API_KEY`, a bounce, then a fresh copy everywhere (as for the key itself).
- Until 11.561 is deployed, each time a connector dialog probes, the live log can hold the key again: overwrite it the same way.
- In claude.ai, pick "No sign-in" (or "Sign in when needed"): "Sign in now" runs an OAuth flow this server does not offer.
- The Grok / ChatGPT rows in CONNECTORS.md §4 remain unverified.
