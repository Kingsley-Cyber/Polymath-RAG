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

PRODUCT-SEARCH-E2E — the same product_search (POST /product/search) and
supplier_parse (POST /supplier/parse) as Server A; the playbook (instructions)
and every product / supplier / adapter description come from ONE shared copy
(polymath_shared/mcp_retrieval.py), pinned by tests/contracts/test_mcp_agent_playbook.py.

PRODUCT-DECISION-REPORT-V1 — the same four report tools as Server A:
  product_report_start / product_report_status / product_report_compile /
  product_report_list (POST /product/report/start, GET /product/report/{id}/status,
  POST /product/report/{id}/compile, GET /product/reports), same shared texts.

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
from polymath_shared import mcp_retrieval as MR
from polymath_shared.adapter import harness_guide as HG  # noqa: E402

BASE = os.environ.get("POLYMATH_API", "http://127.0.0.1:7200")

class _ListedMCPServer(MCPServer):
    """MCP-RETRIEVAL-MODES-V1: the deprecated tools stay callable for old callers but are never LISTED."""

    async def list_tools(self):
        return [t for t in await super().list_tools() if t.name not in MR.HIDDEN_TOOLS_B]


server = _ListedMCPServer(
    name="polymath",
    title="Polymath",
    description="Evidence-first RAG/KAG: grounded answers with exact "
                "source spans, typed abstention, corpus management.",
    version="1.0.0",
    # PRODUCT-SEARCH-E2E: the same ordered playbook Server A serves (MR.playbook), with this server's corpus tool names
    instructions=MR.playbook(
        list_tool="polymath_list_corpora",
        add_documents=("To add a document: polymath_upload_text(text, corpus_id, source_name) or polymath_upload_file(path, "
                       "corpus_id), then call polymath_list_corpora until its query_ready is true (a 300 KB book takes ~5 "
                       "minutes).")),
)

_DEFAULT_MODEL = MR.DefaultModel()


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


def _app_default_model() -> str | None:
    """The model the app's chat writes with when none is named (Server A's `_app_default_model`, the same shared rule)."""
    cached = _DEFAULT_MODEL.cached()
    if cached:
        return cached
    try:
        return _DEFAULT_MODEL.remember(_get("/synthesizers"))
    except httpx.HTTPError:
        return None


@server.tool(description=MR.list_corpora_description(
    "List the user's libraries (knowledge corpora): id, name, purpose and document count."))
def polymath_list_corpora() -> dict:
    return _get("/corpora")


_MODE_ARG = "mode: " + " | ".join(MR.RETRIEVAL_MODES) + f" (default {MR.DEFAULT_MODE}). " + MR.mode_lines()


@server.tool(description=(
    "ONE direct search of one library in the retrieval mode you choose: no query planning, no Corpus Explore, no answer. "
    "Returns contract evidence rows (passages with their source, utility_role and ca4_grade; GRAPH adds attested graph "
    "facts) and, in WILDCARD, the separate wildcard lane. Pass the ORIGINAL question; Polymath owns retrieval planning "
    "(use polymath_explore for that). " + _MODE_ARG))
def polymath_search(query: str, corpus_id: str, mode: str = MR.DEFAULT_MODE, max_evidence: int = 10) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    return MR.shape_search(_post("/chat/evidence", MR.search_body(query, corpus_id, m)), max_evidence)


@server.tool(description=(
    "Full retrieval PLANNING + grounded expansion (+ optional Corpus Explore) in the mode you choose -> a versioned "
    "EvidencePacket (evidence with roles DIRECT/COMPLEMENTARY/DIVERGENT, CA4 grades, provenance, receipts) with NO "
    "Polymath answer, plus graph facts (GRAPH) and the wildcard lane (WILDCARD). Discover hidden/adjacent corpus knowledge, "
    "then do your OWN final reasoning. Do NOT pre-decompose. corpus_explorer=true runs the concept-activation explorer. "
    + _MODE_ARG))
def polymath_explore(query: str, corpus_id: str, corpus_explorer: bool = True,
                     mode: str = MR.DEFAULT_MODE) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    return MR.shape_explore(_post("/chat/evidence", MR.explore_body(query, corpus_id, m, corpus_explorer)))


@server.tool(description=MR.ANSWER + _MODE_ARG + " (Also accepted here: ASK = an answer from stored knowledge objects.)")
def polymath_answer(question: str, corpus_id: str, mode: str = MR.DEFAULT_MODE, reasoning: str = "none",
                    model: str | None = None, latent: bool | None = None) -> dict:
    if str(mode).strip().upper() == "ASK":
        return _post("/ask", {"question": question, "corpus_id": corpus_id})
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    style = MR.normalize_reasoning(reasoning)
    if style is None:
        return {"error": f"unknown reasoning style {reasoning!r}", "status": 422, "styles": list(MR.REASONING_STYLES)}
    model = model or _app_default_model()
    return _post("/chat", MR.answer_body(question, corpus_id, m, reasoning=style, model=model, latent=latent))


@server.tool(description=(
    "Run ONE question through several retrieval modes of one library, side by side (retrieval only, no answer; the app's "
    "Compare screen). Per mode: latency, evidence count, the documents it reached and its top rows; plus the chunks every "
    "mode found and how many only one mode found. modes = any of " + ", ".join(MR.RETRIEVAL_MODES) + " (default: all five)."))
def polymath_compare(question: str, corpus_id: str, modes: list[str] | None = None) -> dict:
    wanted = list(modes or MR.RETRIEVAL_MODES)
    normal = [MR.normalize_mode(x) for x in wanted]
    if None in normal:
        return MR.mode_error(wanted[normal.index(None)])
    return MR.shape_compare(_post("/compare", MR.compare_body(question, corpus_id, list(dict.fromkeys(normal))), timeout=600))


@server.tool(description=(
    "The app's DEEP RESEARCH on one library: Polymath plans research goals, searches in rounds, follows leads and writes a "
    "cited report. It takes MINUTES and spends model calls; one run at a time. depth = "
    + "; ".join(f"{k}: {v}" for k, v in MR.DEPTHS.items()) + f" (default {MR.DEFAULT_DEPTH}). mode = the retrieval mode "
    f"every search uses (default {MR.DEFAULT_MODE}). model = a model id from polymath_models."))
def polymath_deep_research(question: str, corpus_id: str, depth: str = MR.DEFAULT_DEPTH, mode: str = MR.DEFAULT_MODE,
                           model: str | None = None) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    d = MR.normalize_depth(depth)
    if d is None:
        return {"error": f"unknown depth {depth!r}", "status": 422, "depths": dict(MR.DEPTHS)}
    with httpx.stream("POST", f"{BASE}/research/deep", json=MR.deep_body(question, corpus_id, d, m, model),
                      headers={"Accept": "text/event-stream"}, timeout=httpx.Timeout(1800.0, connect=10.0)) as r:
        if r.status_code >= 400:
            r.read()
            try:
                detail = r.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = r.text[:400]
            d_ = detail if isinstance(detail, dict) else {"message": str(detail)}
            return {"error": f"{d_.get('error_code') or r.status_code}: {d_.get('message') or d_}", "status": r.status_code}
        lines = [ln + "\n" for ln in r.iter_lines()] + ["\n"]
    return MR.shape_deep(MR.parse_sse(lines), depth=d, mode=m)


@server.tool(description="The models Polymath can write with (ids for polymath_answer / polymath_deep_research / product_search "
                         "`model`); `default` is the one used when you name none.")
def polymath_models() -> dict:
    try:
        return MR.shape_models(_get("/synthesizers"))
    except httpx.HTTPError as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}


# PRODUCT-SEARCH-E2E: the same two tools, names, parameters and descriptions as Server A (plain proxies; the routes decide)
@server.tool(description=MR.PRODUCT_SEARCH)
def product_search(message: str, corpus_id: Optional[str] = None, geography: Optional[str] = None,
                   model: Optional[str] = None, hypotheses: Optional[list[dict]] = None,
                   limit_per_hypothesis: Optional[int] = None) -> dict:
    model = model or _app_default_model()
    return MR.shape_product(_post("/product/search", MR.product_body(message, corpus_id, geography=geography, model=model,
                                                                    hypotheses=hypotheses,
                                                                    limit_per_hypothesis=limit_per_hypothesis), timeout=600))


@server.tool(description=MR.SUPPLIER_PARSE)
def supplier_parse(site: str, raw_text: str) -> dict:
    return _adapter("POST", "/supplier/parse", MR.parse_body(site, raw_text))


# PRODUCT-DECISION-REPORT-V1 (B5): the same four report tools, names, parameters, descriptions and timeouts as Server A (plain
# proxies onto /product/report/*; the routes decide everything, a report's privacy included)
#: stdio: the agent, and so the fetch script it runs, are on the Polymath host: the upload URL is the local one (Server A decides
#: per request instead; this server's --http mode for a remote agent still gets the local URL: use Server A for other machines)
UPLOAD_BASE = "local"
#: each report's upload token (contract C1; one user per stdio process, so keyed by report): sent back as X-Upload-Token on every
#: status call; memory only, at most MR.REPORT_TOKEN_CACHE_MAX reports
_REPORT_TOKENS = MR.ReportTokens()


@server.tool(description=MR.PRODUCT_REPORT_START)
def product_report_start(message: Optional[str] = None, corpus_id: Optional[str] = None,
                         products: Optional[list[dict]] = None, channels: Optional[list[str]] = None,
                         ship_to: str = "US", max_products: int = MR.REPORT_DEFAULT_PRODUCTS) -> dict:
    body = MR.report_start_body(message, corpus_id, products=products, channels=channels, ship_to=ship_to,
                                max_products=max_products, upload_base=UPLOAD_BASE)
    out = _adapter("POST", MR.REPORT_START_PATH, body, timeout=MR.REPORT_TIMEOUT_S["start"])
    rid = MR.normalize_report_id(out.get("report_id")) if isinstance(out, dict) else None
    if rid:
        _REPORT_TOKENS.remember(rid, out, rid)
    return MR.shape_report(out)


@server.tool(description=MR.PRODUCT_REPORT_STATUS)
def product_report_status(report_id: str) -> dict:
    rid = MR.normalize_report_id(report_id)
    if rid is None:
        return MR.report_id_error(report_id)
    out = _adapter("GET", MR.report_status_path(rid, UPLOAD_BASE), timeout=MR.REPORT_TIMEOUT_S["status"],
                   headers=_REPORT_TOKENS.headers(rid))
    _REPORT_TOKENS.remember(rid, out, rid)
    return MR.shape_report(out)


@server.tool(description=MR.PRODUCT_REPORT_COMPILE)
def product_report_compile(report_id: str, verdicts: Optional[dict[str, str]] = None) -> dict:
    rid = MR.normalize_report_id(report_id)
    if rid is None:
        return MR.report_id_error(report_id)
    return _adapter("POST", MR.report_path(rid, "compile"), MR.report_compile_body(verdicts),
                    timeout=MR.REPORT_TIMEOUT_S["compile"])


@server.tool(description=MR.PRODUCT_REPORT_LIST)
def product_report_list() -> dict:
    return _adapter("GET", MR.REPORT_LIST_PATH, timeout=MR.REPORT_TIMEOUT_S["list"])


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

def _adapter(method: str, path: str, payload: dict | None = None, timeout: float = 180, headers: dict | None = None) -> Any:
    """Server A's `_orch` error mapping: a 4xx/5xx becomes {"error": detail, "status": code} so the agent
    sees a rejected submission's errors (422) or a not-yet-terminal run (409) instead of a transport error."""
    r = httpx.request(method, f"{BASE}{path}", json=payload, timeout=timeout, headers=headers or None)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        return {"error": detail, "status": r.status_code}
    return r.json()


@server.tool(description=MR.ADAPTER_LIST)
def adapter_list() -> dict:
    return _adapter("GET", "/adapter/list")


@server.tool(description=MR.ADAPTER_START)
def adapter_start(adapter_id: str, input: dict, request_options: Optional[dict] = None) -> dict:
    return _adapter("POST", "/adapter/start", {"adapter_id": adapter_id, "input": input, "request_options": request_options or {}})


@server.tool(description=MR.ADAPTER_NEXT)
def adapter_next(run_id: str) -> dict:
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
    score field exists. A rejection returns the errors and the step stays open for a corrected submission: a step-rule
    refusal answers at once (HTTP 422 with the reasons) and the open step then carries `last_rejection`; fix exactly those
    and resubmit (each refusal costs one repair loop). Returns AdapterRunStatusV1."""
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
@server.tool(description=MR.RESEARCH_ACQUIRE)
def research_acquire(run_id: str, operation: str, target: str = "", site: Optional[str] = None,
                     search_intent_id: Optional[str] = None, limit: Optional[int] = None) -> dict:
    return _adapter("POST", f"/adapter/{run_id}/acquire", {"operation": operation, "target": target, "site": site,
                                                            "search_intent_id": search_intent_id, "limit": limit})


# SUPPLIER-APIS (owner-approved 2026-09-27; PRODUCT-SEARCH-E2E 2026-11-01): the READ-ONLY supplier tools, the same names, parameters
# and descriptions as Server A (plain proxies onto the orchestrator's /supplier/* routes, which decide who may call them)
@server.tool(description=MR.SUPPLIER_SEARCH)
def supplier_search(query: str, source: str = "cj", limit: int = 10) -> dict:
    return _adapter("POST", "/supplier/search", {"query": query, "source": source, "limit": limit})


@server.tool(description=MR.SUPPLIER_PRODUCT)
def supplier_product(product_id: str) -> dict:
    return _adapter("POST", "/supplier/product", {"product_id": product_id})


@server.tool(description=MR.SUPPLIER_FREIGHT)
def supplier_freight(variant_id: str, country: str, quantity: int = 1, from_country: str = "CN") -> dict:
    return _adapter("POST", "/supplier/freight", {"variant_id": variant_id, "country": country, "quantity": quantity,
                                                  "from_country": from_country})


@server.tool(description=MR.SUPPLIER_WAREHOUSES)
def supplier_warehouses() -> dict:
    return _adapter("GET", "/supplier/warehouses")


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

        if os.environ.get("POLYMATH_MCP_API_KEY", "").strip():
            # WITH a key, DNS-rebinding host pinning is deliberately OFF: the
            # server is exposed only through an HTTPS tunnel whose hostname
            # is dynamic, and a caller without the key gets 401 regardless.
            security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        else:
            # WITHOUT a key (local-trusted), the server answers only this
            # machine's own names: a DNS-rebound page or a tunnel gets 421.
            local = [f"127.0.0.1:{port}", f"localhost:{port}"]
            security = TransportSecuritySettings(
                allowed_hosts=local, allowed_origins=[f"http://{h}" for h in local])
        app = server.streamable_http_app(stateless_http=True, transport_security=security)
        uvicorn.run(_auth_wrapped(app), host="127.0.0.1", port=port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
