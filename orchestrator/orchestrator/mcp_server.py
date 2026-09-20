"""POLYMATH-MCP-V2 — the v4 MCP server (streamable-http).

An agent (Hermes, the claude.ai connector) drives the WHOLE document
lifecycle through this surface: upload → status until queryable → ask.
Every tool is a thin, trimmed call to the orchestrator API on
127.0.0.1:7200, so MCP can never bypass the pipeline's own gates.

Tools
  list_corpora()                       scope discovery
  list_documents(corpus_id)            documents + recent runs of a corpus
  upload_document(path, corpus_id)     ingest a local file (md/txt/html/pdf/epub/docx)
  upload_text(text, corpus_id, name)   ingest raw text/markdown
  document_status(corpus_id, …)        run status, stages, enrichment, open stalls
  corpus_status(corpus_id)             corpus row + semantic readiness verdict
  retrieve(query, corpus_id, …)        raw evidence chunks
  ask(question, corpus_id, …)          grounded, cited answer (the chat path)

Auth: Authorization: Bearer $POLYMATH_MCP_API_KEY on every /mcp request.
FAIL-CLOSED (V2): with no key configured the server answers 503 on /mcp
instead of running open — measured 2026-09-02: the V1 process had booted
without the key and the public mirror answered tools/call to anyone.
Scope (V2): retrieve/ask REQUIRE corpus_id — the unscoped all-corpora
path took 20 s and abstained on a question the scoped path answered in
3 s with 16 citations.

Env:  POLYMATH_MCP_PORT (8930)  POLYMATH_MCP_API_KEY (bearer)
      POLYMATH_ORCH_URL (http://127.0.0.1:7200)
      POLYMATH_MCP_PUBLIC_HOST (mcp.kingsleylab.xyz)
"""
from __future__ import annotations

import json

import re


import tempfile


import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

log = logging.getLogger("polymath.mcp")

ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/")
PORT = int(os.environ.get("POLYMATH_MCP_PORT", "8930"))
API_KEY = os.environ.get("POLYMATH_MCP_API_KEY", "")
PUBLIC_HOST = os.environ.get("POLYMATH_MCP_PUBLIC_HOST", "mcp.kingsleylab.xyz")
UPLOAD_EXTENSIONS = {".md", ".txt", ".html", ".pdf", ".epub", ".docx"}

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
        "Polymath v4 — evidence-first RAG over King's corpora. Workflow: "
        "list_corpora() to pick a corpus_id; upload_document(path, corpus_id) "
        "or upload_text(...) to ingest; poll document_status(corpus_id, "
        "source_name=...) every ~30 s until query_ready is true (a 300 KB "
        "book takes ~5 minutes; 'stalls' lists anything the control plane "
        "sees stuck, with a diagnosis). To query: submit the ORIGINAL "
        "information need — do NOT pre-decompose it into subqueries; Polymath "
        "owns retrieval planning + grounded expansion. Pick a tool: "
        "polymath_search = quick q0-only evidence; polymath_explore = full "
        "planning + Corpus Explore returning validated EVIDENCE (no answer) "
        "that you reason over yourself; polymath_answer = Polymath writes the "
        "grounded, cited answer (humans/UI). Prefer search/explore for agent "
        "work and synthesize yourself. corpus_id is REQUIRED. Modes: FAST "
        "(cheap baseline), HYBRID (default; includes the latent cross-domain "
        "lane), GRAPH (adds fact relationships)."),
)


async def _orch(method: str, path: str, **kw: Any) -> Any:
    timeout = kw.pop("timeout", 180)
    async with httpx.AsyncClient(timeout=timeout) as client:
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


# ------------------------------------------------------------------ scope

@mcp.tool()
async def list_corpora() -> dict:
    """List every corpus: id, name, purpose, document count, and
    whether it is currently queryable (has a converged run)."""
    return await _orch("GET", "/corpora")


@mcp.tool()
async def list_documents(corpus_id: str) -> dict:
    """Documents of a corpus (name, bytes, chunk/parent counts,
    enrichment progress) plus its recent ingestion runs and their
    last error, if any."""
    return await _orch("GET", "/documents", params={"corpus_id": corpus_id})


# ----------------------------------------------------------------- ingest

@mcp.tool()
async def upload_document(path: str, corpus_id: str) -> dict:
    """Ingest a LOCAL file (md, txt, html, pdf, epub, docx) into a corpus
    through the full evidence-first pipeline. Returns run_id (content-
    addressed: the same bytes return the existing run, already_exists
    true). A file whose content already lives in ANOTHER corpus is
    refused (409 CROSS_CORPUS_CONTENT_COLLISION) — content belongs to
    one corpus. Then poll document_status(corpus_id, source_name)."""
    p = Path(path).expanduser()
    if not p.is_file():
        return {"error": f"file not found: {path}", "status": 404}
    if p.suffix.lower() not in UPLOAD_EXTENSIONS:
        return {"error": f"unsupported extension {p.suffix!r}; accepted: "
                         f"{sorted(UPLOAD_EXTENSIONS)}", "status": 422}
    async with httpx.AsyncClient(timeout=600) as client:
        with p.open("rb") as fh:
            r = await client.post(f"{ORCH}/upload", data={"corpus_id": corpus_id},
                                  files={"file": (p.name, fh)})
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        return {"error": detail, "status": r.status_code}
    out = r.json()
    out["next"] = (f"document_status(corpus_id={corpus_id!r}, "
                   f"source_name={out.get('source_name')!r}) until query_ready")
    return out


@mcp.tool()
async def upload_text(text: str, corpus_id: str,
                      source_name: str = "agent_upload.md") -> dict:
    """Ingest raw text/markdown as a document named source_name (keep
    the .md/.txt extension). Same pipeline and same rules as
    upload_document."""
    if Path(source_name).suffix.lower() not in UPLOAD_EXTENSIONS:
        return {"error": f"source_name needs one of {sorted(UPLOAD_EXTENSIONS)}",
                "status": 422}
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post(f"{ORCH}/upload", data={"corpus_id": corpus_id},
                              files={"file": (source_name, text.encode("utf-8"),
                                              "text/markdown")})
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        return {"error": detail, "status": r.status_code}
    out = r.json()
    out["next"] = (f"document_status(corpus_id={corpus_id!r}, "
                   f"source_name={source_name!r}) until query_ready")
    return out


# ----------------------------------------------------------------- status

@mcp.tool()
async def document_status(corpus_id: str, source_name: Optional[str] = None,
                          run_id: Optional[str] = None) -> dict:
    """Where a document is in the pipeline: run status and query_ready,
    every stage ticket (intake → extract → projections → verify →
    summaries/enrichment), enrichment progress, the last error, and
    any OPEN stall trace with the control plane's diagnosis. Pass
    source_name (the uploaded file name) or run_id."""
    params: dict[str, Any] = {"corpus_id": corpus_id}
    if run_id:
        params["run_id"] = run_id
    if source_name:
        params["source_name"] = source_name
    return await _orch("GET", "/status", params=params)


@mcp.tool()
async def corpus_status(corpus_id: str) -> dict:
    """Corpus-level view: document count and query_ready (control
    contract) plus the semantic-readiness verdict (SEMANTIC_COMPLETE /
    INCOMPLETE with pending lanes / FAILED)."""
    corpora = await _orch("GET", "/corpora")
    row = None
    if isinstance(corpora, dict):
        for c in corpora.get("corpora") or []:
            if c.get("corpus_id") == corpus_id or c.get("name") == corpus_id:
                row = c
                break
    readiness = await _orch("GET", "/semantic_readiness",
                            params={"corpus_id": corpus_id})
    if row is None:
        return {"error": f"corpus {corpus_id!r} not found", "status": 404,
                "semantic_readiness": readiness}
    return {"corpus": row, "semantic_readiness": readiness}


# ------------------------------------------------------------------ query

@mcp.tool()
async def retrieve(query: str, corpus_id: str, mode: str = "HYBRID",
                   limit: int = 10, latent: Optional[bool] = None,
                   explore: bool = False) -> dict:
    """Retrieve evidence chunks for a query within ONE corpus. mode:
    FAST | HYBRID | GRAPH | EXPLORE. latent=false disables the cross-domain
    latent lane for this call (HYBRID/GRAPH run it by default).
    explore=true (or mode=EXPLORE) returns contract-ready `evidence_rows`
    (id, verbatim text, title, auditable source, timecodes, document
    summaries, attested graph facts) with breadth across documents — the
    ideation view an agent consumes directly."""
    if explore:
        mode = "EXPLORE"
    body: dict[str, Any] = {"query": query, "mode": mode, "limit": limit,
                            "corpus_id": corpus_id}
    if latent is not None:
        body["latent"] = latent
    out = await _orch("POST", "/retrieve", json=body)
    if "error" in out:
        return out
    if out.get("evidence_rows") is not None:
        rows = []
        for r in out["evidence_rows"]:
            r = dict(r)
            for k in ("text", "text_clean"):
                if isinstance(r.get(k), str) and len(r[k]) > 1200:
                    r[k] = r[k][:1200]
            rows.append(r)
        return {"evidence_rows": rows, "evidence_contract": out.get("evidence_contract"),
                "graph_facts": len(out.get("graph_facts") or [])}
    hits = out.get("evidence") or out.get("hits") or []
    return {
        "evidence": [_trim_hit(h) for h in hits],
        "meta": {k: v for k, v in (out.get("meta") or {}).items()
                 if k in ("latent", "mode", "corpus_ids", "plan")},
    }


@mcp.tool()
async def capabilities() -> dict:
    """What this Polymath serves (CAPABILITIES-V1): version and the contracts
    an agent or skill can switch on — retrieve-evidence-rows, corpus-plan,
    explore, typed-rows, field-evidence-corpus. Probe once, then decide."""
    return await _orch("GET", "/capabilities")


def _trim_rows(rows: list) -> list:
    out = []
    for r in rows or []:
        r = dict(r)
        for k in ("text", "text_clean"):
            if isinstance(r.get(k), str) and len(r[k]) > 1200:
                r[k] = r[k][:1200]
        out.append(r)
    return out


@mcp.tool()
async def compile_plan(signal: str, corpus_id: str, limit: int = 24, explore: bool = True,
                       communities: Optional[list[str]] = None) -> dict:
    """CORPUS-PLAN-V1: send ONE signal; Polymath compiles 3-5 deterministic
    reformulations (seed / tension / communities / invariant / contrast),
    runs each through the EXPLORE evidence view and returns the merged rows
    stamped with the query ids that found them, plus the plan itself."""
    body: dict[str, Any] = {"signal": signal, "corpus_id": corpus_id, "limit": limit, "explore": explore,
                            "communities": list(communities or [])}
    out = await _orch("POST", "/retrieve/plan", json=body)
    if "error" in out:
        return out
    return {"plan": out.get("plan"), "plan_contract": out.get("plan_contract"),
            "evidence_rows": _trim_rows(out.get("evidence_rows")), "evidence_contract": out.get("evidence_contract"),
            "per_query": out.get("per_query"), "errors": out.get("errors")}


@mcp.tool()
async def retrieve_evidence(query: str, corpus_id: str, limit: int = 12, explore: bool = False) -> dict:
    """RETRIEVE-EVIDENCE-ROWS-V1: contract-ready evidence rows for one query
    (id, verbatim text, title, auditable source, timecodes, document
    summaries, attested graph facts). explore=true = breadth across documents."""
    body: dict[str, Any] = {"query": query, "corpus_id": corpus_id, "limit": limit, "evidence": True}
    if explore:
        body["mode"] = "EXPLORE"
    out = await _orch("POST", "/retrieve", json=body)
    if "error" in out:
        return out
    return {"evidence_rows": _trim_rows(out.get("evidence_rows")), "evidence_contract": out.get("evidence_contract"),
            "graph_facts": len(out.get("graph_facts") or [])}


@mcp.tool()
async def ask(question: str, corpus_id: str, mode: str = "HYBRID",
              latent: Optional[bool] = None, evidence: bool = False) -> dict:
    """Ask a question of ONE corpus and get the grounded RAG answer with
    citations (the same path the Polymath chat UI uses). Prefer this
    over retrieve() when you want an answer, not raw evidence."""
    body: dict[str, Any] = {"message": question, "mode": mode,
                            "corpus_id": corpus_id, "evidence": bool(evidence)}
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


# REASONING-BOUNDARY-V1 canonical surface (search / explore / answer) — mirrors Server B.
@mcp.tool()
async def polymath_search(query: str, corpus_id: str, max_evidence: int = 12) -> dict:
    """Canonical EVIDENCE search: q0-only contract evidence rows (no planning, no Corpus Explore, no
    answer). Pass the ORIGINAL question; do NOT pre-decompose it — Polymath owns retrieval planning."""
    out = await _orch("POST", "/retrieve", json={"query": query, "corpus_id": corpus_id,
                                                 "limit": max_evidence, "evidence": True})
    if "error" in out:
        return out
    return {"evidence_rows": _trim_rows(out.get("evidence_rows")),
            "evidence_contract": out.get("evidence_contract"),
            "graph_facts": len(out.get("graph_facts") or [])}


@mcp.tool()
async def polymath_explore(query: str, corpus_id: str, corpus_explorer: bool = True,
                           mode: str = "HYBRID") -> dict:
    """Full retrieval PLANNING + grounded expansion (+ optional Corpus Explore) -> a versioned
    EvidencePacket (evidence with roles DIRECT/COMPLEMENTARY/DIVERGENT, CA4 grades, provenance, receipts)
    with NO Polymath answer (synthesis_performed=false). Discover hidden/adjacent corpus knowledge, then do
    your OWN final reasoning over the evidence. Do NOT pre-decompose — Polymath owns retrieval planning; you
    own the answer. corpus_explorer=true runs the concept-activation explorer."""
    out = await _orch("POST", "/chat/evidence",
                      json={"message": query, "corpus_id": corpus_id, "mode": mode,
                            "corpus_explorer": bool(corpus_explorer)})
    return out


@mcp.tool()
async def polymath_answer(question: str, corpus_id: str, mode: str = "HYBRID",
                          latent: Optional[bool] = None) -> dict:
    """Polymath's OWN grounded, cited answer (humans/UI, or when you explicitly want Polymath's answer
    rather than raw evidence). For agent work prefer polymath_search / polymath_explore and synthesize
    yourself (avoids a nested synthesis pass). verdict=insufficient_evidence means the corpus cannot support
    the question — relay it, do not fill the gap."""
    body: dict[str, Any] = {"message": question, "mode": mode, "corpus_id": corpus_id}
    if latent is not None:
        body["latent"] = latent
    out = await _orch("POST", "/chat", json=body)
    if "error" in out:
        return out
    slim = dict(out)
    for key in ("evidence", "chunks", "bundle"):
        val = slim.get(key)
        if isinstance(val, list):
            slim[key] = [_trim_hit(h, 600) if isinstance(h, dict) else h for h in val[:12]]
    return slim


# -------------------------------------------------------------------- app

@mcp.tool()
async def recent_queries(corpus_id: str, limit: int = 20, since_h: float = 24.0,
                         kind: Optional[str] = None) -> dict:
    """What was asked of this corpus recently and how it went (QUERY-RECEIPTS-V1):
    each served /chat, /ask or /retrieve with its latency (wall_ms), mode,
    status (ok / abstained / error), citation count and error text, plus a
    per-mode summary (count, p50/p95 ms, abstained, errors). Use it to verify
    a question you just asked was served, or to spot slow/abstaining modes."""
    if not corpus_id or not corpus_id.strip():
        raise ValueError("corpus_id is required")
    params: dict[str, Any] = {"corpus_id": corpus_id, "limit": int(limit), "since_h": float(since_h)}
    if kind:
        params["kind"] = kind
    return await _orch("GET", "/queries", params=params)



# ------------------------------------------------------- cognitive adapter (ADR-0018)

@mcp.tool()
async def adapter_list() -> dict:
    """COGNITIVE-ADAPTER-V1: the admitted adapters (id, versions, description, input_schema, step counts, which
    TrailSignal operations are working vs planned). One MCP connection, one adapter run — see adapter_start."""
    return await _orch("GET", "/adapter/list")


@mcp.tool()
async def adapter_start(adapter_id: str, input: dict, request_options: Optional[dict] = None) -> dict:
    """Start ONE durable adapter run (AdapterRunRefV1). `input` must satisfy the adapter's input_schema
    (adapter_list). request_options: corpus_ids, idempotency_key, agent_identity, retrieval_mode, deadline_s.
    Polymath executes retrieval/graph/validation/compile steps itself; when a step needs YOUR reasoning,
    adapter_next returns a typed AGENT_REASON step — answer it with adapter_submit."""
    return await _orch("POST", "/adapter/start", json={"adapter_id": adapter_id, "input": input, "request_options": request_options or {}})


@mcp.tool()
async def adapter_next(run_id: str) -> dict:
    """What the run needs from you now: {kind:"step", step: AdapterStepV1} when a step awaits you — an AGENT_REASON
    step (reason over objective, bounded evidence_refs, hypotheses, constraints, output_schema, acceptance_rules) or a
    HARNESS_ACTION step (step.harness_action = HarnessActionV1: go research with YOUR OWN tools — web search, browser,
    APIs — within its search intents, source roles, freshness, independence and budget, then submit a
    HarnessResearchReceiptV1 of structured observations; TrailSignal decides what is admitted as evidence). Else
    {kind:"status", status: AdapterRunStatusV1} (running = Polymath is executing; terminal = fetch adapter_result)."""
    return await _orch("GET", f"/adapter/{run_id}/next")


@mcp.tool()
async def adapter_submit(run_id: str, step_id: str, payload: dict, agent_identity: str = "connected-agent",
                         model: Optional[str] = None, kind: Optional[str] = None) -> dict:
    """Submit your answer for the awaiting step. AGENT_REASON: kind="reasoning" (default) — validated against the step's
    output_schema and acceptance rules; cite ONLY ids from context.evidence_refs (never a trail_prior); hypotheses you
    generate become durable state with lineage. HARNESS_ACTION: kind="receipt" — a HarnessResearchReceiptV1
    (action_id, harness_id, sources, observations, tool_trace, limitations; no score field exists). A rejection returns
    the errors and the step stays open for a corrected submission. Returns AdapterRunStatusV1."""
    return await _orch("POST", f"/adapter/{run_id}/submit",
                       json={"step_id": step_id, "payload": payload, "agent_identity": agent_identity, "model": model,
                             **({"kind": kind} if kind else {})})


@mcp.tool()
async def adapter_status(run_id: str) -> dict:
    """AdapterRunStatusV1 for a run (status, current step, counters, typed failure/gap)."""
    return await _orch("GET", f"/adapter/{run_id}/status")


@mcp.tool()
async def adapter_result(run_id: str) -> dict:
    """AdapterResultV1 of a TERMINAL run: the domain output plus lineage (Polymath evidence ids, step receipt
    hashes, TrailSignal operation/record ids), surviving contradictions/unknowns, and the typed gap if any.
    409 while the run is still running or awaiting you."""
    return await _orch("GET", f"/adapter/{run_id}/result")


@mcp.tool()
async def adapter_cancel(run_id: str) -> dict:
    """Cancel a run (terminal, idempotent; accepted work is kept). Returns AdapterRunStatusV1."""
    return await _orch("POST", f"/adapter/{run_id}/cancel")


def build_app():
    """ASGI app: FastMCP streamable-http + FAIL-CLOSED bearer gate +
    open /health."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route

    inner = mcp.streamable_http_app(
        stateless_http=True, transport_security=_SECURITY)

    async def health(_request):
        return JSONResponse({"service": "polymath-mcp", "ok": True,
                             "auth": "configured" if API_KEY else "MISSING",
                             "tools": sorted(t for t in _TOOL_NAMES)})

    class BearerGate:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                if not API_KEY:
                    resp = JSONResponse(
                        {"error": "MCP bearer key not configured "
                                  "(POLYMATH_MCP_API_KEY); refusing to serve"},
                        status_code=503)
                    await resp(scope, receive, send)
                    return
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


_TOOL_NAMES = ("adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status",
               "adapter_result", "adapter_cancel",
               "list_corpora", "list_documents", "upload_document", "upload_text",
               "document_status", "corpus_status", "retrieve", "ask",
               "recent_queries",
    "capabilities", "compile_plan", "retrieve_evidence",
    "polymath_search", "polymath_explore", "polymath_answer",
)


def main() -> None:
    import uvicorn
    if not API_KEY:
        log.error("POLYMATH_MCP_API_KEY is not set: /mcp will answer 503 "
                  "until the key is configured (fail-closed)")
    uvicorn.run(build_app(), host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
