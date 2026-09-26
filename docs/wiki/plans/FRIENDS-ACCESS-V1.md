---
title: "FRIENDS-ACCESS-V1 — friends use rag.kingsleylab.xyz and its MCP with their own logins, their own API keys and a copy-paste connect prompt"
date: 2026-09-26
last_reviewed: 2026-09-26
status: "ACTIVE — plan of record (register 11.497); slices F0–F6 below"
owner: "@king"
scope: "The public web UI (rag.kingsleylab.xyz → Caddy :8794 → orchestrator :7200, frontend-v2), the orchestrator's HTTP routes, the per-friend principal registry (orchestrator/mcp_principals.py, scripts/mcp_principals.py), MCP Server A (mcp.kingsleylab.xyz). Not in scope: Trail, the adapters' reasoning, retrieval quality."
---

# FRIENDS-ACCESS-V1

## 0. The owner's request (2026-09-26)
- "rag.kingsleylab.xyz is the website always on for me and others to use the latest code of the rag tool and all its tools … i want
  my friends to use the website rag, tools, mcps … i want a login so its not accessible to anyone. and a copy and paste settings tab
  where users can generate up to [N] random generated api key[s] and a prompt to send to their agent harness to connect and use it
  for queries and all its tools."
- The owner's answers (AskUserQuestion, 2026-09-26):
  - login = username + password; **each friend gets their OWN login**; King is the admin account;
  - friends may do **everything** (search the owner's libraries, their own private library, product research);
  - **3 API keys** per friend;
  - **no daily cap** on AI-written answers.
- The owner typed a password in chat. It is NOT recorded anywhere: the owner sets King's password privately at go-live (F5).

## 1. Baseline (what exists; REUSE before building)
| Capability | Where | State |
|---|---|---|
| Per-friend MCP principals: hashed keys (sha256, key id), profiles (`friend`), scopes, corpus + adapter scoping, writable corpora, per-minute rate limit, revoke / rotate / disable | `orchestrator/orchestrator/mcp_principals.py`; admin CLI `scripts/mcp_principals.py`; registry `~/PolymathRuntime/polymath-v4-mcp-principals.json` (0600, outside the repo; Server A re-reads it on change) | LIVE (owner decision 2026-09-21); 3 acceptance principals, no real friend |
| The MCP authorization boundary: Server A verifies the bearer, authorizes the tool + arguments, forwards only `X-Polymath-Principal` | `orchestrator/orchestrator/mcp_server.py`, `shared/polymath_shared/principal_context.py` | LIVE |
| Principal context behind the boundary: adapter-run ownership, query receipts | `principal_context.py` ("no header = trusted local caller") | LIVE, narrow |
| The web login | Caddy `~/.hermes/rag-proxy/Caddyfile`: ONE basic-auth user (King) → `reverse_proxy 127.0.0.1:7200` | LIVE; everything behind it runs as the owner (gap S-15) |
| Web accounts, sessions, a Settings tab, self-service keys, a connect prompt | — | MISSING |

## 2. Decisions
- **D1 Accounts:** one identity store = the principal registry. A friend = a principal (`prn_<username>`, profile `friend`) with a
  `web` credential (username, scrypt password hash via the standard library, created / changed times, a session version). King =
  the owner principal (admin) with its own `web` credential. No new dependency; no database migration.
- **D2 Sessions:** a signed cookie (HMAC-SHA256, secret `POLYMATH_WEB_SESSION_SECRET` in `.env`, never printed) carrying principal
  id + session version + expiry; `HttpOnly`, `Secure`, `SameSite=Strict`. Logout, password change and disabling bump the session
  version (every old cookie dies). State-changing requests also need the header `X-Polymath-CSRF` matching a cookie value
  (double submit).
- **D3 The web boundary** (mirrors Server A for MCP): a request that reached the orchestrator THROUGH the proxy (`X-Forwarded-For` /
  `Forwarded` present) must carry a valid session, else 401 (the UI shows the login screen). The boundary resolves the principal
  and sets the principal context. Direct loopback callers (Server A with its header, Hermes, the workers) are unchanged. Caddy
  strips any incoming `X-Polymath-Principal`.
- **D4 Route policy** (§3): every route is classified; a proxied request to an unclassified route is refused (fail closed; a test
  lists every route).
- **D5 Library scoping inside the routes:** a helper checks the principal's corpora (read) and writable corpora (write) at the top
  of each corpus-taking route, and filters list responses (corpora, documents, graph entities, query history). The owner is
  unrestricted.
- **D6 A friend's private library:** creating a friend creates `fr-<username>` (writable, private: the friend and the owner). Read
  access to the owner's libraries = all of them by default ("everything"); the owner can narrow per friend.
- **D7 API keys:** Settings → create (max 3 ACTIVE per friend; shown ONCE with a copy button), list (key id, created, last used),
  revoke. Keys are principal keys in the registry (same format the CLI writes); Server A picks them up without a bounce.
- **D8 The connect prompt:** Settings → "Connect your agent": a copy-paste block with the MCP URL, the user's key (inserted only in
  the browser, never logged), the operating-guide pointers (`run_governed_research`, `polymath://adapter/guide`) and one setup line
  per harness (Claude Code, Codex, Gemini CLI, OpenCode, Hermes, Claude.ai / ChatGPT connectors) from `mcp_server/CONNECTORS.md`.
- **D9 The three locks stay** (the owner was told 2026-09-26): `research_acquire` stays owner-only (it reads through the owner's
  signed-in Chrome); host-path uploads stay owner-only; admin (LLM providers, control plane, fleet, corpus settings of the owner's
  libraries, deleting the owner's documents) stays owner-only.
- **D10 Spending:** no daily cap (the owner). Abuse protection only: the existing per-minute MCP rate limit, and a login throttle
  (5 failed attempts per username and per address in 15 minutes).

## 3. Route policy (the web boundary; F2 pins it in a test)
| Class | Routes |
|---|---|
| public | `/health`, `/ready`, the login page and `/auth/login` |
| any signed-in user (scoped to their libraries) | `/chat`, `/chat/stream`, `/chat/evidence`, `/ask`, `/retrieve`, `/retrieve/plan`, `/evidence`, `/compare`, `/review`, `/corpora` (GET, filtered), `/documents` (GET, filtered), `/documents/summary`, `/documents/{id}/sections`, `/documents/{id}/status`, `/graph/entities`, `/graph/entity/{id}/relationships`, `/semantic_readiness`, `/capabilities`, `/synthesizers`, `/reasoning_modes`, `/queries` (own), `/adapter/list`, `/adapter/start`, `/adapter/{run}/next|submit|status|result|cancel` (own runs), `/ui_pulse`, `/health/pipeline`, `/auth/*`, `/keys/*` |
| writable libraries only | `/upload` (to a writable corpus), `DELETE /documents/{id}` (in a writable corpus), `/generated` |
| owner only | `/llm/providers` (all methods), `/llm/test`, `/control_plane*`, `/fleet`, `/sidecars`, `/health/semantic`, `/intake`, `/runs/{id}`, `/status`, `PATCH /corpora/{id}*`, `POST /corpora/{id}/enrich`, `POST /documents/{id}/enrich`, `DELETE /corpora/{id}`, `/adapter/{run}/acquire` (already refuses proxied callers), `/admin/*` |

## 4. Slices
| Slice | What | Proof |
|---|---|---|
| F0 | Admit this plan (documents) | register 11.497; CONTINUITY |
| F1 | Accounts + sessions core: scrypt hashing, the signed session cookie, registry `web` fields (read / write through the existing atomic writer), the login throttle; CLI `scripts/web_accounts.py` (set the owner's password from a hidden prompt; create / disable / reset a friend) | unit tests (hash verify, tamper, expiry, version bump, throttle, no raw secret on disk or in output) |
| F2 | The web boundary middleware + `/auth/login|logout|me|password` + the route policy + the library helper wired into every corpus-taking route + list filtering | contract tests: proxied without a session → 401; every route classified; friend → owner-only 403; corpus outside scope 403; direct loopback unchanged |
| F3 | Self-service keys (`/keys` list / create / revoke, max 3) + owner admin (`/admin/friends` create / disable / reset password / libraries) + the private library on friend creation | contract tests (limit, show-once, revoke stops Server A auth, admin refused to friends) |
| F4 | frontend-v2: login screen, 401 → login, Settings (account, API keys, connect prompt; owner: friends) | vitest + `npm run build`; the live contract test still green |
| F5 | Go-live kit: the Caddy change (drop basic auth, strip the principal header) as ONE Run-button script, the `.env` secret line, the owner-password step, a live check through `https://rag.kingsleylab.xyz` | the script is idempotent and backs up the Caddyfile |
| F6 | Live: the owner's Run button (merge + bounce + Caddy reload + frontend build), the owner sets King's password, the live check, one friend account created by the owner | live check exit 0 |

## 5. Out of scope / owner questions (not blocking)
Sign-in with Google or email codes (the owner chose username + password) · a daily spend cap (the owner: none) · friends using the
owner's Chrome through `research_acquire` (a lock; only the owner's word changes it) · per-friend billing · password reset by email.
