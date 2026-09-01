"""POLYMATH-MCP-V1 — the v4 MCP server (streamable-http).

Fronts the orchestrator HTTP API so agents (Hermes, Claude
connectors, Claude Code) can query and retrieve. The API is the
contract: this process holds NO retrieval logic of its own — every
tool is a thin, trimmed call to 127.0.0.1:7200, so MCP can never
drift from what the UI serves (the v33 alignment lesson).

Three tools, agent-shaped:
  list_corpora            what exists and what is queryable
  retrieve                evidence chunks (FAST/HYBRID/GRAPH, latent)
  ask                     the full grounded RAG answer with citations

Auth: Authorization: Bearer $POLYMATH_MCP_API_KEY on every /mcp
request when the key is set (REQUIRED for any public exposure; the
kingsleylab tunnel terminates TLS and forwards here). /health is
open. Host allowlist mirrors the v33 DNS-rebinding fix.

Run:  .venv/bin/python -m orchestrator.mcp_server
Env:  POLYMATH_MCP_PORT (8930)  POLYMATH_MCP_API_KEY (bearer)
      POLYMATH_ORCH_URL (http://127.0.0.1:7200)
      POLYMATH_MCP_PUBLIC_HOST (extra allowed Host header)
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/")
PORT = int(os.environ.get("POLYMATH_MCP_PORT", "8930"))
API_KEY = os.environ.get("POLYMATH_MCP_API_KEY", "")
PUBLIC_HOST = os.environ.get("POLYMATH_MCP_PUBLIC_HOST",
                             "mcp.kingsleylab.xyz")

_ALLOWED_HOSTS = [f"127.0.0.1:{PORT}", f"localhost:{PORT}",
                  PUBLIC_HOST, f"{PUBLIC_HOST}:443"]

# DNS-rebinding allowlist (the v33 gotcha)
_SECURITY = TransportSecuritySettings(
    allowed_hosts=_ALLOWED_HOSTS,
    allowed_origins=[f"https://{PUBLIC_HOST}",
                     f"http://127.0.0.1:{PORT}",
                     f"http://localhost:{PORT}"])

mcp = MCPServer(
    name="polymath",
    instructions=(
        "Polymath v4 — evidence-first RAG over King's corpora. "
        "Use list_corpora first when unsure of scope; retrieve() for "
        "raw evidence chunks; ask() for a grounded, cited answer. "
        "Modes: FAST (cheap baseline), HYBRID (default; includes the "
        "latent cross-domain lane), GRAPH (adds fact relationships)."),
)


async def _orch(method: str, path: str, **kw: Any) -> Any:
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.request(method, f"{ORCH}{path}", **kw)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = r.text[:400]
            return {"error": detail, "status": r.status_code}
        return r.json()


def _trim_hit(h: dict, max_chars: int = 1400) -> dict:
    return {k: v for k, v in {
        "text": (h.get("text") or "")[:max_chars],
        "source_name": h.get("source_name"),
        "heading_path": h.get("heading_path"),
        "doc_id": h.get("doc_id"),
        "chunk_id": h.get("chunk_id"),
        "score": h.get("score"),
        "tier": h.get("tier"),
        "arrival": h.get("arrival"),
    }.items() if v is not None}


@mcp.tool()
async def list_corpora() -> dict:
    """List every corpus: id, name, purpose, document count, and
    whether it is currently queryable (has a converged run)."""
    return await _orch("GET", "/corpora")


@mcp.tool()
async def retrieve(query: str, corpus_id: Optional[str] = None,
                   mode: str = "HYBRID", limit: int = 10,
                   latent: Optional[bool] = None) -> dict:
    """Retrieve evidence chunks for a query. mode: FAST | HYBRID |
    GRAPH. latent=false disables the cross-domain latent lane for
    this call (HYBRID/GRAPH run it by default). Omit corpus_id to
    search every query-enabled corpus (FAST/HYBRID only)."""
    body: dict[str, Any] = {"query": query, "mode": mode, "limit": limit}
    if corpus_id:
        body["corpus_id"] = corpus_id
    else:
        body["all_authorized"] = True
    if latent is not None:
        body["latent"] = latent
    out = await _orch("POST", "/retrieve", json=body)
    if "error" in out:
        return out
    hits = out.get("evidence") or out.get("hits") or []
    return {
        "evidence": [_trim_hit(h) for h in hits],
        "meta": {k: v for k, v in (out.get("meta") or {}).items()
                 if k in ("latent", "mode", "corpus_ids", "plan")},
    }


@mcp.tool()
async def ask(question: str, corpus_id: Optional[str] = None,
              mode: str = "HYBRID",
              latent: Optional[bool] = None) -> dict:
    """Ask a question and get the full grounded RAG answer with
    citations (the same path the Polymath chat UI uses). Prefer this
    over retrieve() when you want an answer, not raw evidence."""
    body: dict[str, Any] = {"message": question, "mode": mode}
    if corpus_id:
        body["corpus_id"] = corpus_id
    else:
        body["all_authorized"] = True
    if latent is not None:
        body["latent"] = latent
    out = await _orch("POST", "/chat", json=body)
    if "error" in out:
        return out
    # pass the rendered answer through; trim only the bulky evidence
    # bodies (citations keep their identity + locator fields)
    slim = dict(out)
    for key in ("evidence", "chunks", "bundle"):
        val = slim.get(key)
        if isinstance(val, list):
            slim[key] = [_trim_hit(h, 600) if isinstance(h, dict) else h
                         for h in val[:12]]
    return slim


def build_app():
    """ASGI app: FastMCP streamable-http + bearer gate + open /health."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route

    inner = mcp.streamable_http_app(
        stateless_http=True, transport_security=_SECURITY)

    async def health(_request):
        return JSONResponse({"service": "polymath-mcp", "ok": True})

    class BearerGate:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if API_KEY and scope["type"] == "http":
                headers = dict(scope.get("headers") or [])
                auth = (headers.get(b"authorization") or b"").decode()
                if auth != f"Bearer {API_KEY}":
                    resp = Response("unauthorized", status_code=401)
                    await resp(scope, receive, send)
                    return
            await self.app(scope, receive, send)

    app = Starlette(routes=[
        Route("/health", health),
        Mount("/", app=BearerGate(inner)),
    ])
    # the inner app manages the streamable-http session lifecycle
    app.router.lifespan_context = inner.router.lifespan_context
    return app


def main() -> None:
    import uvicorn
    uvicorn.run(build_app(), host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
