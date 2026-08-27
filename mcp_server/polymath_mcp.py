"""POLYMATH-MCP-V1 — Model Context Protocol server over the Polymath
query product.

A thin client of the orchestrator HTTP API (127.0.0.1:7200 by
default): agents get the same fail-closed, evidence-first product the
web UI uses — nothing is re-implemented here.

Tools:
  polymath_list_corpora     corpus inventory (docs, readiness)
  polymath_query            grounded question answering
                            (VECTOR|HYBRID|GRAPH|ASK) with citations,
                            abstention, and the retrieved-chunk list
  polymath_retrieve         raw retrieval trace (no synthesis)
  polymath_list_documents   file-manager listing for one corpus
  polymath_upload_file      ingest a local file into a corpus
  polymath_upload_text      ingest raw text/markdown into a corpus
  polymath_readiness        semantic-completion verdict for a corpus
  polymath_delete_corpus    destructive: remove a corpus everywhere
                            (requires confirm=<corpus_id>)

Transports:
  stdio (default)  — Claude Code / Claude Desktop / local agents:
      claude mcp add polymath -- <repo>/.venv/bin/python \
          <repo>/mcp_server/polymath_mcp.py
  --http [PORT]    — streamable HTTP for remote use (claude.ai custom
      connectors need a public URL: tunnel this port, e.g. cloudflared).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer

BASE = os.environ.get("POLYMATH_API", "http://127.0.0.1:7200")

server = MCPServer(
    name="polymath",
    title="Polymath",
    description="Evidence-first RAG/KAG: grounded answers with exact "
                "source spans, typed abstention, corpus management.",
    version="1.0.0",
    instructions=(
        "Query the user's Polymath knowledge corpora. Always pass an "
        "explicit corpus_id (list them first) — missing scope fails "
        "closed by design. Answers labeled verdict=insufficient_evidence "
        "mean the corpus does not support the question; report that "
        "honestly instead of substituting your own knowledge."
    ),
)


def _get(path: str, **params: Any) -> dict:
    r = httpx.get(f"{BASE}{path}", params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def _post(path: str, payload: dict, timeout: float = 300) -> dict:
    r = httpx.post(f"{BASE}{path}", json=payload, timeout=timeout)
    if r.status_code >= 400:
        try:
            return {"error": r.json().get("detail", r.text)}
        except Exception:
            return {"error": r.text[:400]}
    return r.json()


@server.tool()
def polymath_list_corpora() -> dict:
    """List the user's knowledge corpora with document counts and
    query-readiness."""
    return _get("/corpora")


@server.tool()
def polymath_query(
    question: str,
    corpus_id: str,
    mode: str = "HYBRID",
) -> dict:
    """Ask a grounded question against one corpus.

    mode: VECTOR (dense hierarchical), HYBRID (dense+lexical, default),
    GRAPH (hybrid + canonical fact graph), ASK (stored knowledge
    objects: facts/procedures/concepts).

    The answer carries citations with exact chunk@start:end locators.
    verdict=insufficient_evidence means the corpus cannot support the
    question — relay that, do not fill the gap yourself."""
    mode = mode.upper()
    if mode == "ASK":
        return _post("/ask", {"question": question, "corpus_id": corpus_id})
    m = "FAST" if mode == "VECTOR" else mode
    return _post("/chat", {"message": question, "corpus_id": corpus_id,
                           "mode": m})


@server.tool()
def polymath_retrieve(
    query: str,
    corpus_id: str,
    mode: str = "HYBRID",
) -> dict:
    """Raw retrieval trace (documents, sections, evidence chunks, graph
    relationships) without answer synthesis. Useful when the agent
    wants source material to work with directly."""
    m = "FAST" if mode.upper() == "VECTOR" else mode.upper()
    return _post("/retrieve", {"query": query, "corpus_id": corpus_id,
                               "mode": m})


@server.tool()
def polymath_list_documents(corpus_id: str) -> dict:
    """List documents (name, size, chunk count) and recent ingestion
    runs for a corpus."""
    return _get("/documents", corpus_id=corpus_id)


@server.tool()
def polymath_upload_file(path: str, corpus_id: str) -> dict:
    """Ingest a local file (md/txt/html/pdf/epub/docx) into a corpus
    through the full evidence-first pipeline. Returns the run id;
    check polymath_readiness for completion."""
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": f"file not found: {path}"}
    with p.open("rb") as fh:
        r = httpx.post(
            f"{BASE}/upload",
            data={"corpus_id": corpus_id},
            files={"file": (p.name, fh)},
            timeout=300,
        )
    if r.status_code >= 400:
        return {"error": r.text[:400]}
    return r.json()


@server.tool()
def polymath_upload_text(
    text: str,
    corpus_id: str,
    source_name: str = "agent_upload.md",
) -> dict:
    """Ingest raw text/markdown content into a corpus."""
    r = httpx.post(
        f"{BASE}/upload",
        data={"corpus_id": corpus_id},
        files={"file": (source_name, text.encode(), "text/markdown")},
        timeout=300,
    )
    if r.status_code >= 400:
        return {"error": r.text[:400]}
    return r.json()


@server.tool()
def polymath_readiness(corpus_id: str) -> dict:
    """Semantic-completion verdict for a corpus: SEMANTIC_COMPLETE /
    SEMANTIC_INCOMPLETE (with pending lanes) / SEMANTIC_FAILED, plus
    fact/procedure/concept counts."""
    return _get("/semantic_readiness", corpus_id=corpus_id)


@server.tool()
def polymath_delete_corpus(corpus_id: str, confirm: str) -> dict:
    """DESTRUCTIVE: delete a corpus and everything derived from it
    (documents, chunks, facts evidenced only there, summaries, vector
    collection, graph substrate). `confirm` must equal corpus_id."""
    r = httpx.delete(f"{BASE}/corpora/{corpus_id}",
                     params={"confirm": confirm}, timeout=300)
    if r.status_code >= 400:
        try:
            return {"error": r.json().get("detail", r.text)}
        except Exception:
            return {"error": r.text[:400]}
    return r.json()


def main() -> None:
    if "--http" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--http") + 1])
        except (IndexError, ValueError):
            port = 7300
        import uvicorn

        uvicorn.run(server.streamable_http_app(), host="127.0.0.1",
                    port=port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
