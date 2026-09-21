# Polymath MCP — agents and connectors

Two MCP servers share one canonical tool surface (REASONING-BOUNDARY-V1):
- **Server B** (`mcp_server/polymath_mcp.py`, stdio / `--http`) — what local Claude Code and Codex use: spawned by the
  client over stdio, no credential, proxies the orchestrator on `:7200`.
- **Server A** (`orchestrator/orchestrator/mcp_server.py`, streamable-http) — the supervised `mcp` slot on `:8930`
  (Bearer key; `/health` open). **Hermes uses Server A** (`http://127.0.0.1:8930/mcp`); it is also the public
  `mcp.kingsleylab.xyz`.

Canonical query tools (prefer these): **polymath_search** (q0-only evidence rows), **polymath_explore**
(full planning + Corpus Explore → EvidencePacket, NO answer — you reason over it yourself), **polymath_answer**
(Polymath writes the grounded answer; humans/UI). Submit the ORIGINAL question — do NOT pre-decompose it;
Polymath owns retrieval planning. DEPRECATED, kept working for existing callers: Server B `polymath_query` /
`polymath_retrieve`; Server A `ask` / `retrieve` / `compile_plan` / `retrieve_evidence`. Agent work never goes through
an answer tool (`polymath_answer`, `ask`, `polymath_query`) — that nests a second synthesis under the agent's own.
Plus corpus ops: list_corpora, list_documents, upload_file, upload_text, readiness, delete_corpus,
delete_document (Server A also: capabilities). Both servers serve the seven cognitive-adapter tools
`adapter_list / adapter_start / adapter_next / adapter_submit / adapter_status / adapter_result / adapter_cancel`
with identical names, parameters and descriptions (pinned by `tests/contracts/test_mcp_adapter_parity.py`).

## 1. Local agents over stdio (Claude Code, Codex) — Server B

```bash
claude mcp add polymath -- /path/to/.venv/bin/python /path/to/mcp_server/polymath_mcp.py
```

Any stdio MCP client (`mcpServers` block — same shape as `~/.claude.json`; Codex takes the same command / args / env
under `[mcp_servers.polymath]` in `~/.codex/config.toml`):

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

## 2. Agents over Streamable HTTP (Hermes, remote and custom agents)

**Hermes on this machine → Server A.** Nothing to start: the fleet supervisor (`scripts/boot_polymath.sh`) runs it as
the `mcp` slot. Hermes registers `url: http://127.0.0.1:8930/mcp` with an `Authorization: Bearer <key>` header through
its own MCP tooling (never by hand-editing `~/.hermes/config.yaml`). A changed Server A tool description or schema
reaches Hermes only after a fleet bounce AND one Hermes MCP reload.

**The hosted surface (`https://mcp.kingsleylab.xyz/mcp`) is the SAME Server A**, reached through the named tunnel. A caller that
did not address the loopback listener directly is REMOTE: `upload_document(path, …)` answers it
`REMOTE_PATH_UPLOAD_DISABLED` (403) before any filesystem access — a remote agent has no host paths; it sends content with
`upload_text`. Hermes on this machine (loopback) is unchanged. Surface acceptance, read-only by default:

```bash
.venv/bin/python scripts/hosted_mcp_acceptance.py --url https://mcp.kingsleylab.xyz --key-file ~/PolymathRuntime/polymath-v4-mcp.key --vantage host
```

Run it from ANOTHER machine with `--vantage external:<label>` for external-access proof. The adapter lifecycle over the hosted
surface is `scripts/adapter_mcp_acceptance.py --mcp-url https://mcp.kingsleylab.xyz/mcp --no-restart`.

**Friends get their OWN key, never the owner key (ADR-0022).** `$POLYMATH_MCP_API_KEY` is the owner / admin credential. A friend is a
PRINCIPAL in the registry file `$POLYMATH_MCP_PRINCIPALS_FILE` (outside the repository, 0600):

```bash
.venv/bin/python scripts/mcp_principals.py add --id prn_fred --name "Fred" --corpus commerce-v1 \
    --adapter ecommerce.product_research --key-out ~/PolymathRuntime/keys/prn_fred.key     # the bearer is written there ONCE, never printed
```

Default deny: profile `friend` = search / explore / answer + adapter list / start / next / submit / status / result, on the listed
corpora and adapters only. 401 = unknown / revoked / expired key · 403 = a tool, corpus, adapter or RUN the principal may not reach
(another principal's run and a missing run answer identically) · 429 = over its rate. A friend's Claude Code connects with
`claude mcp add --transport http polymath https://mcp.kingsleylab.xyz/mcp --header "Authorization: Bearer <their key>"`.
Revoking (`revoke`, `revoke-key`, `disable`) takes effect on the next request — no bounce.

**Remote / custom agents → Server B over HTTP.** Start it (stateless HTTP, MCP 2026-07-28 core; Bearer-key auth):

```bash
export POLYMATH_MCP_API_KEY="$(cat ~/PolymathRuntime/polymath-v4-mcp.key)"
.venv/bin/python mcp_server/polymath_mcp.py --http 7300
```

Remote registration (any HTTP MCP client):

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
            # ONE call, the ORIGINAL need, never pre-decomposed. Returns an EvidencePacket (no answer): reason over it.
            await s.call_tool("polymath_explore", {"query": "<the original need>", "corpus_id": "<corpus id>"})
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
