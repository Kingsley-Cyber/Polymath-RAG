# Polymath MCP — agents and connectors

One MCP server, three consumption shapes. All tools (9): list_corpora,
query, retrieve, list_documents, upload_file, upload_text, readiness,
delete_corpus, delete_document.

## 1. Local agents over stdio (Claude Code, Hermes on this machine)

```bash
claude mcp add polymath -- /path/to/.venv/bin/python /path/to/mcp_server/polymath_mcp.py
```

Hermes (`mcpServers` block — same shape as `~/.claude.json`):

```json
{
  "mcpServers": {
    "polymath": {
      "command": "/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python",
      "args": ["/Users/king/Documents/polymath-rebuild/polymath-v4/mcp_server/polymath_mcp.py"],
      "env": { "POLYMATH_API": "http://127.0.0.1:7200" }
    }
  }
}
```

## 2. Remote agents over Streamable HTTP (Hermes remote, custom agents)

Start the server (stateless HTTP, MCP 2026-07-28 core; Bearer-key auth):

```bash
export POLYMATH_MCP_API_KEY="$(cat ~/PolymathRuntime/polymath-v4-mcp.key)"
.venv/bin/python mcp_server/polymath_mcp.py --http 7300
```

Hermes remote registration:

```json
{
  "mcpServers": {
    "polymath": {
      "url": "https://<your-host>/mcp",
      "headers": { "Authorization": "Bearer <key>" }
    }
  }
}
```

Custom agent (official python-sdk) — live-verified pattern:

```python
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {KEY}"}) as hc:
    async with streamable_http_client("https://<host>/mcp",
                                      http_client=hc) as ctx:
        async with ClientSession(ctx[0], ctx[1]) as s:
            await s.initialize()
            await s.call_tool("polymath_query", {...})
```

## 3. Product connectors (Claude.ai / Grok / ChatGPT)

All three ingest the same remote MCP URL:

1. Run the HTTP server (above) and expose it over public HTTPS:
   quick test: `cloudflared tunnel --url http://127.0.0.1:7300`
   production: a named cloudflared tunnel on your own domain.
2. **Claude.ai / Desktop** → Settings → Connectors → Add custom
   connector → URL `https://<host>/mcp`, auth header
   `Authorization: Bearer <key>`. (Messages-API alternative: the MCP
   connector feature calls the same URL server-side with allow/deny
   tool lists.)
3. **Grok**: xAI Remote MCP Tools / Connectors — same URL + header.
4. **ChatGPT**: OpenAI connector flow — same URL + header.

Auth is a fixed API key (`Authorization: Bearer` or `X-API-Key`);
without `POLYMATH_MCP_API_KEY` set the server runs local-trusted
(stdio / localhost only — never tunnel an unauthenticated server).
The key lives at `~/PolymathRuntime/polymath-v4-mcp.key` (0600).

Abstention semantics carry through every shape: `insufficient_evidence`
is an honest verdict the agent must relay, not an error to retry.
