"""POLYMATH-MCP-V1 — Model Context Protocol server over the Polymath
query product.

A thin client of the orchestrator HTTP API (127.0.0.1:7200 by
default): agents get the same fail-closed, evidence-first product the
web UI uses — nothing is re-implemented here.

Tools (REASONING-BOUNDARY-V1 canonical surface):
  polymath_list_corpora     corpus inventory (docs, readiness)
  polymath_search           q0-only EVIDENCE (contract rows, no plan/answer)
  polymath_explore          full planning + Corpus Explore -> EvidencePacket
                            (roles/CA4/provenance, NO Polymath answer)
  polymath_answer           Polymath's own grounded, cited answer (humans/UI)
  polymath_query            DEPRECATED -> polymath_answer (kept for callers)
  polymath_retrieve         DEPRECATED -> polymath_search (kept for callers)
  polymath_list_documents   file-manager listing for one corpus
  polymath_upload_file      ingest a local file into a corpus
  polymath_upload_text      ingest raw text/markdown into a corpus
  polymath_readiness        semantic-completion verdict for a corpus
  polymath_delete_corpus    destructive: remove a corpus everywhere
                            (requires confirm=<corpus_id>)

Cognitive adapter (ADR-0018; GOVERNED-CONVERGENCE-V1 TG1) — the SAME seven
tools MCP Server A serves (orchestrator/orchestrator/mcp_server.py), as plain
proxies over the orchestrator's /adapter/* routes (parity pinned by
tests/contracts/test_mcp_adapter_parity.py):
  adapter_list / adapter_start / adapter_next / adapter_submit /
  adapter_status / adapter_result / adapter_cancel

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

_SHARED = Path(__file__).resolve().parents[1] / "shared"
if _SHARED.is_dir() and str(_SHARED) not in sys.path:          # the repository's shared package (normally already on the path)
    sys.path.insert(0, str(_SHARED))
from polymath_shared.adapter import harness_guide as HG  # noqa: E402

BASE = os.environ.get("POLYMATH_API", "http://127.0.0.1:7200")

server = MCPServer(
    name="polymath",
    title="Polymath",
    description="Evidence-first RAG/KAG: grounded answers with exact "
                "source spans, typed abstention, corpus management.",
    version="1.0.0",
    instructions=(
        "Query the user's Polymath knowledge corpora. Always pass an explicit corpus_id (list them "
        "first) — missing scope fails closed by design. Submit the user's ORIGINAL information need; do "
        "NOT pre-decompose it into speculative retrieval subqueries — Polymath owns corpus retrieval "
        "planning and grounded query expansion. Choose a tool by what you need: polymath_search = quick "
        "q0-only corpus evidence; polymath_explore = full planning + Corpus Explore, returns validated "
        "EVIDENCE (no answer) that you reason over yourself; polymath_answer = have Polymath write the "
        "grounded answer (humans/UI). Prefer search/explore for agent work and synthesize yourself. "
        "verdict=insufficient_evidence / an empty evidence set means the corpus does not support the "
        "question; report that honestly instead of substituting your own knowledge. "
        "Governed research (e.g. product research): adapter_list -> adapter_start -> loop adapter_next / adapter_submit -> adapter_result; the operating guide for any agent harness and any tools is the prompt run_governed_research and the resource polymath://adapter/guide."
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
def polymath_search(query: str, corpus_id: str, max_evidence: int = 10) -> dict:
    """Lightweight EVIDENCE retrieval for one corpus — q0-only, no planning, no Corpus Explore, no answer.
    Returns contract evidence rows (human source, timecodes, attested facts). Use when you just need corpus
    facts quickly. Pass your ORIGINAL question; do NOT pre-decompose it — Polymath owns retrieval planning.
    Reason over the returned evidence yourself."""
    return _post("/retrieve", {"query": query, "corpus_id": corpus_id,
                               "evidence": True, "limit": max_evidence})


@server.tool()
def polymath_explore(query: str, corpus_id: str, corpus_explorer: bool = True,
                     mode: str = "HYBRID") -> dict:
    """Full Polymath retrieval PLANNING + grounded query expansion (+ optional Corpus Explore) returning a
    versioned EvidencePacket: evidence with roles (DIRECT/COMPLEMENTARY/DIVERGENT), CA4 grades
    (DIRECT/PARTIAL/RELATED), provenance and receipts — and NO Polymath answer (synthesis_performed=false).
    Use this to discover hidden/adjacent corpus knowledge, then do your OWN final reasoning over the
    evidence. Pass your ORIGINAL information need; do NOT pre-decompose it — Polymath owns retrieval
    planning; you own the answer. corpus_explorer=true runs the concept-activation explorer."""
    m = "FAST" if mode.upper() == "VECTOR" else mode.upper()
    return _post("/chat/evidence", {"message": query, "corpus_id": corpus_id, "mode": m,
                                    "corpus_explorer": bool(corpus_explorer)})


@server.tool()
def polymath_answer(question: str, corpus_id: str, mode: str = "HYBRID",
                    latent: bool | None = None) -> dict:
    """Have POLYMATH write a grounded, cited answer (its OWN synthesis) — for humans/UI, or when you
    explicitly want Polymath's answer rather than raw evidence. For agent-to-agent work prefer
    polymath_search / polymath_explore and synthesize yourself (avoids a nested synthesis pass).
    verdict=insufficient_evidence means the corpus cannot support the question — relay it, do not fill the
    gap. mode: VECTOR (dense) | HYBRID (default) | GRAPH (+ fact graph) | ASK (stored knowledge objects)."""
    mode = mode.upper()
    if mode == "ASK":
        return _post("/ask", {"question": question, "corpus_id": corpus_id})
    m = "FAST" if mode == "VECTOR" else mode
    body = {"message": question, "corpus_id": corpus_id, "mode": m}
    if latent is not None:
        body["latent"] = latent
    return _post("/chat", body)


@server.tool()
def polymath_query(
    question: str,
    corpus_id: str,
    mode: str = "HYBRID",
    latent: bool | None = None,
) -> dict:
    """DEPRECATED — use polymath_answer (identical behaviour: Polymath's own grounded answer) or, for
    agent work, polymath_search / polymath_explore (evidence you reason over yourself). Kept for existing
    callers. Ask a grounded question against one corpus. mode: VECTOR|HYBRID|GRAPH|ASK. The answer carries
    citations with exact chunk@start:end locators. verdict=insufficient_evidence means the corpus cannot
    support the question — relay that, do not fill the gap yourself."""
    mode = mode.upper()
    if mode == "ASK":
        return _post("/ask", {"question": question, "corpus_id": corpus_id})
    m = "FAST" if mode == "VECTOR" else mode
    body = {"message": question, "corpus_id": corpus_id, "mode": m}
    if latent is not None:
        body["latent"] = latent
    return _post("/chat", body)


@server.tool()
def polymath_retrieve(
    query: str,
    corpus_id: str,
    mode: str = "HYBRID",
    latent: bool | None = None,
) -> dict:
    """DEPRECATED — use polymath_search (contract evidence rows) or polymath_explore (full planning +
    EvidencePacket). Kept for existing callers. Raw retrieval trace (documents, sections, evidence chunks,
    graph relationships) without answer synthesis."""
    m = "FAST" if mode.upper() == "VECTOR" else mode.upper()
    body = {"query": query, "corpus_id": corpus_id, "mode": m}
    if latent is not None:
        body["latent"] = latent
    return _post("/retrieve", body)


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


@server.tool()
def polymath_delete_document(doc_id: str, confirm: str) -> dict:
    """Delete ONE document from its corpus everywhere (vectors, graph,
    facts evidenced only by it, summaries, runs). confirm must equal
    doc_id. The same file becomes re-ingestable afterward."""
    r = httpx.delete(f"{BASE}/documents/{doc_id}",
                     params={"confirm": confirm}, timeout=300)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------- cognitive adapter (ADR-0018)
# GOVERNED-CONVERGENCE-V1 TG1: plain proxies over the orchestrator's /adapter/* routes — the same names,
# parameters and semantics as MCP Server A (orchestrator/orchestrator/mcp_server.py), so a stdio agent
# (Claude Code / Codex) drives the same governed run Hermes drives over HTTP. Nothing is decided here.

def _adapter(method: str, path: str, payload: dict | None = None) -> Any:
    """Server A's `_orch` error mapping: a 4xx/5xx becomes {"error": detail, "status": code} so the agent
    sees a rejected submission's errors (422) or a not-yet-terminal run (409) instead of a transport error."""
    r = httpx.request(method, f"{BASE}{path}", json=payload, timeout=180)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        return {"error": detail, "status": r.status_code}
    return r.json()


@server.tool()
def adapter_list() -> dict:
    """COGNITIVE-ADAPTER-V1: the admitted adapters (id, versions, description, input_schema, step counts, which
    TrailSignal operations are working vs planned). One MCP connection, one adapter run — see adapter_start. The PREFERRED
    adapter says so in its description. How to run any adapter end to end with any tools you have: the prompt
    run_governed_research and the resource polymath://adapter/guide."""
    return _adapter("GET", "/adapter/list")


@server.tool()
def adapter_start(adapter_id: str, input: dict, request_options: Optional[dict] = None) -> dict:
    """Start ONE durable adapter run (AdapterRunRefV1). `input` must satisfy the adapter's input_schema (adapter_list): at
    least `seed` and `corpus_ids`; optional research limits (geography, language, freshness_days, constraints, exclusions,
    category) reach every research step. request_options: idempotency_key (a retry never starts a second run),
    agent_identity ("<harness>/<label>"), corpus_ids (REQUIRED for a non-admin key), retrieval_mode, deadline_s.
    Polymath executes retrieval/graph/validation/compile steps itself; adapter_next hands you AGENT_REASON steps (your
    reasoning) and HARNESS_ACTION steps (your live research) — answer each with adapter_submit."""
    return _adapter("POST", "/adapter/start", {"adapter_id": adapter_id, "input": input, "request_options": request_options or {}})


@server.tool()
def adapter_next(run_id: str) -> dict:
    """What the run needs from you now: {kind:"step", step: AdapterStepV1} when a step awaits you — an AGENT_REASON
    step (reason over objective, bounded evidence_refs, hypotheses, constraints, output_schema, acceptance_rules) or a
    HARNESS_ACTION step (step.harness_action = HarnessActionV1: go research with YOUR OWN tools — web search, browser,
    APIs — within its search intents, source roles, freshness, independence and budget, then submit a
    HarnessResearchReceiptV1 of structured observations; TrailSignal decides what is admitted as evidence). An awaiting
    step travels with a sibling `evidence` key: READABLE rows (text, source, utility_role, ca4_grade; admitted field
    evidence with its claim, url, role and polarity) for exactly the ids in step.context.evidence_refs, capped at 60 rows x
    600 chars, plus `receipts` (how each knowledge step retrieved) and `coverage`. REASON OVER evidence.rows; CITE ids
    from context.evidence_refs. Else {kind:"status", status: AdapterRunStatusV1} (running = Polymath is executing;
    terminal = fetch adapter_result)."""
    return _adapter("GET", f"/adapter/{run_id}/next")


@server.tool()
def adapter_submit(run_id: str, step_id: str, payload: dict, agent_identity: str = "connected-agent",
                   model: Optional[str] = None, kind: Optional[str] = None) -> dict:
    """Submit your answer for the awaiting step. AGENT_REASON: kind="reasoning" (default) — validated against the step's
    output_schema and acceptance rules; cite ONLY ids from context.evidence_refs (never a trail_prior); hypotheses you
    generate become durable state with lineage. HARNESS_ACTION: kind="receipt" — exactly the step's output_schema, a
    HarnessResearchReceiptV1: action_id, run_id, harness_id, started_at, completed_at, sources[{source_id, url (canonical
    permalink), source_class, retrieved_at, published_at_if_known}], observations[{observation_id, source_id, claim,
    paraphrase_or_excerpt, metric_if_present, context, evidence_role_claimed, hypothesis_ids}], tool_trace, limitations; no
    score field exists. A rejection returns the errors and the step stays open for a corrected submission. Returns
    AdapterRunStatusV1."""
    return _adapter("POST", f"/adapter/{run_id}/submit",
                    {"step_id": step_id, "payload": payload, "agent_identity": agent_identity, "model": model,
                     **({"kind": kind} if kind else {})})


@server.tool()
def adapter_status(run_id: str) -> dict:
    """AdapterRunStatusV1 for a run (status, current step, counters, typed failure/gap)."""
    return _adapter("GET", f"/adapter/{run_id}/status")


@server.tool()
def adapter_result(run_id: str) -> dict:
    """AdapterResultV1 of a TERMINAL run: the domain output plus lineage (Polymath evidence ids, step receipt
    hashes, TrailSignal operation/record ids), surviving contradictions/unknowns, and the typed gap if any.
    409 while the run is still running or awaiting you."""
    return _adapter("GET", f"/adapter/{run_id}/result")


@server.tool()
def adapter_cancel(run_id: str) -> dict:
    """Cancel a run (terminal, idempotent; accepted work is kept). Returns AdapterRunStatusV1."""
    return _adapter("POST", f"/adapter/{run_id}/cancel")


# AUTORESEARCH-SOURCES-AND-HARNESS-V1 R8: Polymath-hosted research reads (the same name, parameters and description as Server A)
@server.tool()
def research_acquire(run_id: str, operation: str, target: str = "", site: Optional[str] = None,
                     search_intent_id: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """Polymath reads the web FOR you at a HARNESS_ACTION step, for a harness with no browser or web tools of its own (owner key
    only: the host's browser holds the owner's sign-ins). operation: `catalog` (what this host can read), `web_search` (target =
    a query, optional site = one host name; results are leads, never evidence), `comments` (target = a content permalink; every
    comment keeps its OWN date and says how precise it is: exact, relative or none), `listings` (target = a query, site = a
    supported listing site). Returns receipt-ready `sources` (one per page and publish date), verbatim `items` bound to them,
    `completeness` (read vs available), `limitations` and a `tool_trace` row for your receipt (pass the step's search_intent_id).
    status HUMAN_ACTION_REQUIRED = the host's browser needs a person (a sign-in or a human check): call again after, or record
    the limitation. Read-only: it never posts, likes, follows or buys. Each call spends one query of the step's budget."""
    return _adapter("POST", f"/adapter/{run_id}/acquire", {"operation": operation, "target": target, "site": site,
                                                            "search_intent_id": search_intent_id, "limit": limit})


# ------------------------------------------------------- the operating guide for any agent harness
# AUTORESEARCH-SOURCES-AND-HARNESS-V1 (gaps H-01, H-02, H-04): ONE guide, published identically by both MCP servers as a prompt
# and resources (polymath_shared.adapter.harness_guide); the files are read per request, so a re-pinned Trail source table is live.
_GUIDE_ROOT = Path(__file__).resolve().parents[1]


def _guide_resources() -> dict:
    return HG.resources({uri: (_GUIDE_ROOT / rel).read_text(encoding="utf-8") for uri, rel in HG.FILES.items()})


def _guide_reader(uri: str):
    def read() -> str:
        return _guide_resources()[uri][1]
    return read


for _uri in HG.RESOURCE_URIS:
    server.resource(_uri, name=_uri.rsplit("/", 1)[-1], title=HG.TITLES[_uri], description=HG.TITLES[_uri], mime_type=HG.MIME[_uri])(_guide_reader(_uri))


@server.prompt(name=HG.PROMPT_NAME, title="Run a governed adapter end to end", description=HG.PROMPT_DESCRIPTION)
def run_governed_research(adapter_id: str = "", seed: str = "") -> str:
    """The operating guide, then where to begin (optionally a given adapter and seed)."""
    return HG.prompt_text(adapter_id, seed)


def _auth_wrapped(app):
    """MCP-CONNECTOR-AUTH-V1: fixed API key in request headers, the
    scheme Claude custom connectors / Grok remote tools / ChatGPT
    connectors all support. Set POLYMATH_MCP_API_KEY to require
    `Authorization: Bearer <key>` (or `X-API-Key: <key>`) on every MCP
    request; unset = local-trusted mode (stdio or localhost HTTP)."""
    key = os.environ.get("POLYMATH_MCP_API_KEY", "").strip()
    if not key:
        return app

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode()
                       for k, v in scope.get("headers", [])}
            presented = headers.get("authorization", "")
            if presented.startswith("Bearer "):
                presented = presented[len("Bearer "):]
            if presented != key and headers.get("x-api-key", "") != key:
                from starlette.responses import JSONResponse
                await JSONResponse({"error": "unauthorized"},
                                   status_code=401)(scope, receive, send)
                return
        await app(scope, receive, send)

    return guarded


def main() -> None:
    if "--http" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--http") + 1])
        except (IndexError, ValueError):
            port = 7300
        import uvicorn

        # stateless_http: MCP 2026-07-28 stateless core — each request
        # self-contained, no session pinning, safe behind tunnels and
        # scale-to-zero hosting. Bind localhost; expose via an HTTPS
        # tunnel (cloudflared) so TLS terminates outside this process.
        from mcp.server.transport_security import TransportSecuritySettings

        app = server.streamable_http_app(
            stateless_http=True,
            # DNS-rebinding host pinning is deliberately OFF: the server
            # binds localhost and is exposed only through an HTTPS tunnel
            # with Bearer-key auth — the tunnel hostname is dynamic, and
            # a rebinding attacker without the key gets 401 regardless.
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False),
        )
        uvicorn.run(_auth_wrapped(app), host="127.0.0.1", port=port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
