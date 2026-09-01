---
change_id: POLYMATH-MCP-V1
owner: governance
date: 2026-08-31
status: complete
architecture_impact: new serve-side process (MCP streamable-http on :8930); no retrieval logic added
last_reviewed: 2026-08-31
---

# WORK LOG — POLYMATH-MCP-V1 (agents + Claude connectors query v4)

## Contract
Owner 2026-08-31: "mcp update for my agent to use like hermes and
for claude connector to work for me to query and retrieve." The v33
MCP at mcp.kingsleylab.xyz was found DEAD (Cloudflare 530 — its
origin tunnel is gone), so Hermes's `polymath` entry and any Claude
connector on that URL were already broken. The v33 alignment law
carries over: MCP must never hold its own retrieval logic — the
orchestrator API is the contract.

## Changes
- `orchestrator/orchestrator/mcp_server.py` — MCP server (SDK 2.1,
  MCPServer, streamable-http, stateless): three agent-shaped tools,
  each a thin trimmed call to 127.0.0.1:7200 —
  `list_corpora` (GET /corpora), `retrieve` (POST /retrieve; evidence
  trimmed to text/source/heading_path/score + latent meta), `ask`
  (POST /chat; the full grounded answer, bulky evidence bodies
  trimmed). Bearer gate (`POLYMATH_MCP_API_KEY`, 401 without; /health
  open) + DNS-rebinding host allowlist (the v33 gotcha,
  TransportSecuritySettings).
- Key: the v4 server REUSES the existing `POLYMATH_MCP_TOKEN` value
  from Hermes's env (stored in the gitignored v4 .env as
  POLYMATH_MCP_API_KEY) so existing client configs revive unchanged.
  NO secrets in the repo.
- Durability: LaunchAgent `com.polymath.mcp` (RunAtLoad+KeepAlive,
  sources the v4 .env, logs to /private/tmp/polymath_fleet/mcp.log).
- Exposure: `mcp.kingsleylab.xyz` ingress added to the LIVE
  hermes-files named tunnel (b20814b2) → :8930; DNS re-routed with
  --overwrite-dns off the dead v33 tunnel.
- Hermes: `mcp_servers.polymath.url` → `http://127.0.0.1:8930/mcp`
  (same box — no Cloudflare edge, immune to the edge's Python-UA
  403s); same bearer env; gateway restarted (restart half-failed —
  stop succeeded, start did not; explicit `gateway start`, PID
  verified changed 1922 → 57776, the known macOS-26 trap).

## Proof
- Local: /health 200; /mcp without bearer → 401; initialize
  handshake OK; tools/list → list_corpora, retrieve, ask;
  tools/call list_corpora → live corpora JSON (truthfully showing
  query_ready:false mid-Phase-0-re-ingest).
- Public: https://mcp.kingsleylab.xyz/health → 200;
  authorized tools/list through the tunnel → all three tools.
- `hermes mcp list` → polymath @ 127.0.0.1:8930 ✓ enabled.
- ask()/retrieve() end-to-end answer proof deferred only on the
  corpus being mid-re-ingest (Phase 0); /chat correctly returns
  typed corpus_not_ready until promotion.

## Rejected claims
- "Point Hermes at the public URL" — rejected: same box, and the
  Cloudflare edge has 403'd Python UAs before (kingsleylab memory);
  local URL is faster and immune.
- "Mint a new hostname (mcp4.…)" — rejected once the v33 origin was
  confirmed dead: reviving the SAME hostname keeps every existing
  client config (claude.ai connector, docs, muscle memory) valid.
- "Put the MCP under the process supervisor" — deferred, not done:
  the serve supervisor's slot set is another session's surface;
  LaunchAgent matches the apple-ml sidecar precedent and survives
  reboots independently of fleet profiles.

## Open contract gaps
- Claude connector needs the user-side add on claude.ai (Settings →
  Connectors → `https://mcp.kingsleylab.xyz/mcp` + the bearer token);
  cannot be done from this seat.
- The `ask` tool passes /chat's rendered answer through with generic
  trimming; if /chat's response shape gains fields agents shouldn't
  see (cost internals etc.), tighten the pass-through.
- retrieve() hit-shape depends on /retrieve's `evidence` list key; a
  response-contract change there needs a matching trim update.
