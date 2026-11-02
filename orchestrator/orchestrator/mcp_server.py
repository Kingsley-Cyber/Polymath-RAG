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
  polymath_search(query, corpus_id, mode)       one direct search in a mode -> evidence rows (no planning)
  polymath_explore(query, corpus_id, mode, …)   planning + Corpus Explore -> EvidencePacket (no answer)
  polymath_answer(question, corpus_id, mode, …) the app's own grounded, cited answer (reasoning style, model)
  polymath_compare(question, corpus_id, modes)  one question through several modes, side by side
  polymath_deep_research(question, corpus_id, depth, mode)  the app's deep research -> a cited report (minutes)
  polymath_models()                    the model ids `model` may name
  product_search(message, corpus_id, …)  PRODUCT-SEARCH-E2E: the ONE entry point for product questions -> Polymath's answer
                                       with corpus product hypotheses + CJ finds + the local Agent Reach fallback + the offer of
                                       the full governed run (POST /product/search)
  supplier_parse(site, raw_text)       raw local Agent Reach output -> supplier listings (POST /supplier/parse)
  product_report_start(message, …)     PRODUCT-DECISION-REPORT-V1: start a private HTML decision report (POST /product/report/start)
  product_report_status(report_id)     its progress and the round's fetch script (GET /product/report/{id}/status)
  product_report_compile(report_id, …) the decision model + HTML -> the report link (POST /product/report/{id}/compile)
  product_report_list()                the caller's own reports (GET /product/reports)
  Modes (MCP-RETRIEVAL-MODES-V1, polymath_shared/mcp_retrieval.py): FAST | HYBRID | GRAPH | WILDCARD | GNN.
  retrieve / retrieve_evidence / compile_plan / ask: DEPRECATED, still callable, no longer listed.
  What an agent is told (the playbook in `instructions`, the product / supplier / adapter descriptions) lives ONCE in
  polymath_shared/mcp_retrieval.py, shared with Server B.

Auth: Authorization: Bearer <key> on every /mcp request, or the key in the URL (/k/<key>/mcp: claude.ai's custom connector
cannot send a header; KeyInPath turns it into the same header). $POLYMATH_MCP_API_KEY is the OWNER (admin) key; every other
caller is a PRINCIPAL from $POLYMATH_MCP_PRINCIPALS_FILE (mcp_principals.py): default-deny action + resource scopes,
private adapter runs, 401 unknown/revoked key, 403 not permitted, 429 over its rate.
FAIL-CLOSED (V2): with no key configured the server answers 503 on /mcp
instead of running open — measured 2026-09-02: the V1 process had booted
without the key and the public mirror answered tools/call to anyone.
Scope (V2): every query tool REQUIRES corpus_id — the unscoped all-corpora
path took 20 s and abstained on a question the scoped path answered in
3 s with 16 citations.

Env:  POLYMATH_MCP_PORT (8930)  POLYMATH_MCP_API_KEY (bearer)
      POLYMATH_ORCH_URL (http://127.0.0.1:7200)
      POLYMATH_MCP_PUBLIC_HOST (mcp.kingsleylab.xyz)
"""
from __future__ import annotations

import contextvars
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

from orchestrator import mcp_principals as P
from polymath_shared import mcp_retrieval as MR
from polymath_shared.adapter import harness_guide as HG

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
                     f"http://localhost:{PORT}",
                     # CLAUDE-CONNECTOR-URL: in case the claude.ai connector's client sends its Origin (not observed; an absent
                     # Origin already passes). Harmless: every /mcp request still needs a key.
                     "https://claude.ai", "https://claude.com"])

# HOSTED-SURFACE ISOLATION (migration Phase 13): this ONE process serves Hermes on the loopback listener AND the public
# hostname through the tunnel. A tool that reads the HOST filesystem is lawful only for a caller that addressed the
# loopback listener directly; everything that came through the edge carries the public Host and the edge's headers.
# The gate decides per request; the default is NOT local, so a lost context refuses (fail closed) instead of serving.
_LOOPBACK_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
_EDGE_HEADERS = (b"cf-connecting-ip", b"cf-ray", b"cdn-loop", b"x-forwarded-for", b"forwarded")
_CALLER_IS_LOCAL: contextvars.ContextVar[bool] = contextvars.ContextVar("polymath_mcp_caller_is_local", default=False)
REMOTE_PATH_UPLOAD_DISABLED = {
    "error": "REMOTE_PATH_UPLOAD_DISABLED: upload_document reads a path on the Polymath HOST, and a remote caller has no "
             "host paths. Send the content instead: upload_text(text, corpus_id, source_name).",
    "status": 403}


# HOSTED-MCP PRINCIPALS (owner decision 2026-09-21): the gate authenticates the bearer to ONE principal per request and
# authorizes every tools/call before the MCP layer sees it. Tools read the principal only to FILTER results and to stamp
# what the principal creates (run ownership, query receipts). No gate = no principal = NOBODY (fail closed).
NOBODY = P.Principal(principal_id="prn_nobody")
_PRINCIPAL: contextvars.ContextVar[P.Principal] = contextvars.ContextVar("polymath_mcp_principal", default=NOBODY)
_CALLER_AGENT: contextvars.ContextVar[str] = contextvars.ContextVar("polymath_mcp_caller_agent", default="polymath-mcp")
_STORE = P.store_from_env(API_KEY)
_LIMITER = P.RateLimiter()
MAX_GATED_BODY = 2 * 1024 * 1024


def _is_local_caller(headers: dict) -> bool:
    host = (headers.get(b"host") or b"").decode("latin-1").strip().lower()
    return host in _LOOPBACK_HOSTS and not any(h in headers for h in _EDGE_HEADERS)


class _ListedMCPServer(MCPServer):
    """MCP-RETRIEVAL-MODES-V1: the deprecated tools stay callable for old callers but are never LISTED, so no agent is
    offered them (polymath_search used to reach the frozen LEGACY route through them)."""

    async def list_tools(self):
        return [t for t in await super().list_tools() if t.name not in MR.HIDDEN_TOOLS_A]


mcp = _ListedMCPServer(
    name="polymath",
    # PRODUCT-SEARCH-E2E: an ordered playbook any model can follow (the one text both servers serve, MR.playbook)
    instructions=MR.playbook(
        list_tool="list_corpora",
        add_documents=("To add a document: upload_text(text, corpus_id, source_name) (upload_document(path, corpus_id) reads a "
                       "path on the Polymath host, local callers only), then poll document_status(corpus_id, source_name=...) "
                       "every ~30 s until query_ready is true (a 300 KB book takes ~5 minutes; 'stalls' lists anything the "
                       "control plane sees stuck, with a diagnosis).")),
)

NO_PRINCIPAL = {"error": "NO_PRINCIPAL: this call carries no authenticated principal (fail closed)", "status": 401}


def _trusted_headers(extra: Optional[dict] = None) -> Optional[dict]:
    """TRUSTED CONTEXT to the loopback orchestrator: WHO the request is for (a non-admin principal only — the owner key stays the
    legacy / trusted-local caller) and WHICH SOFTWARE is calling (the caller's own User-Agent -> receipt.client). None = no gate
    ran for this call: nothing goes out under the sentinel, whose id a friend could hold (fail closed). Every call to the
    orchestrator carries it — FRIEND-JOURNEY F15: upload_text used to send none, so a friend's upload ran as the owner."""
    who = _PRINCIPAL.get()
    if who is NOBODY:
        return None
    headers = {"User-Agent": _CALLER_AGENT.get(), **(extra or {})}
    if not who.is_admin:
        headers[P.PRINCIPAL_HEADER] = who.principal_id
    return headers


async def _orch(method: str, path: str, **kw: Any) -> Any:
    timeout = kw.pop("timeout", 180)
    headers = _trusted_headers(kw.pop("headers", None))
    if headers is None:
        return dict(NO_PRINCIPAL)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        r = await client.request(method, f"{ORCH}{path}", **kw)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = r.text[:400]
            return {"error": detail, "status": r.status_code}
        return r.json()


async def _orch_events(path: str, body: dict, timeout: float = 1800.0) -> list[tuple[str, dict]]:
    """POST `body` to a text/event-stream route and collect its frames, with the same trusted context as `_orch`. A
    refusal before the stream starts comes back as one ("error", {...}) frame."""
    headers = _trusted_headers({"Accept": "text/event-stream"})
    if headers is None:
        return [("error", {"error_code": "NO_PRINCIPAL", "message": "this call carries no authenticated principal (fail closed)"})]
    frames: list[tuple[str, dict]] = []
    async with (httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0), headers=headers) as client,
                client.stream("POST", f"{ORCH}{path}", json=body) as r):
        if r.status_code >= 400:
            raw = await r.aread()
            try:
                detail = json.loads(raw).get("detail")
            except Exception:  # noqa: BLE001
                detail = raw[:400].decode("utf-8", "replace")
            d = detail if isinstance(detail, dict) else {"message": str(detail)}
            return [("error", {"error_code": d.get("error_code") or f"HTTP_{r.status_code}", "message": d.get("message") or str(d)})]
        lines = [line async for line in r.aiter_lines()]
    frames.extend(MR.parse_sse([ln + "\n" for ln in lines] + ["\n"]))
    return frames


def _trim_hit(h: dict, max_chars: int = 1400) -> dict:
    """A slim hit. D-02: a cut text says so — `truncated: true` + `full_length` (characters before the cut); a hit that
    fits keeps exactly its old keys."""
    text = h.get("text") or ""
    cut = len(text) > max_chars
    return {k: v for k, v in {
        "text": text[:max_chars],
        "source_name": h.get("source_name"),
        "heading_path": h.get("heading_path"),
        "doc_id": h.get("doc_id"),
        "chunk_id": h.get("chunk_id"),
        "score": h.get("score"),
        "tier": h.get("tier"),
        "arrival": h.get("arrival"),
        "truncated": True if cut else None,
        "full_length": len(text) if cut else None,
    }.items() if v is not None}


# ------------------------------------------------------------------ scope

#: the wildcard grant ("every library"), the same token as polymath_shared.query_scope.ALL_LIBRARIES (pinned by a test)
ALL_LIBRARIES = "*"


@mcp.tool(description=MR.list_corpora_description(
    "List every library (corpus) open to you: id, name, purpose and document count; a non-admin key sees only the libraries it "
    "may use."))
async def list_corpora() -> dict:
    out = await _orch("GET", "/corpora")
    who = _PRINCIPAL.get()
    # The orchestrator already answers per caller (the forwarded principal) and adds `notes`, which pass through. This filter is
    # defence in depth for a key that lists its libraries; a wildcard grant keeps everything the orchestrator returned (it never
    # returns another person's private library), or a "*" friend would see nothing but their own.
    if (not who.is_admin and ALL_LIBRARIES not in who.corpus_ids and isinstance(out, dict)
            and isinstance(out.get("corpora"), list)):
        out["corpora"] = [c for c in out["corpora"] if isinstance(c, dict) and c.get("corpus_id") in who.corpus_ids]
    return out


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
    one corpus. Then poll document_status(corpus_id, source_name).
    LOCAL callers only (the loopback listener): a remote caller gets REMOTE_PATH_UPLOAD_DISABLED — use upload_text."""
    if not _CALLER_IS_LOCAL.get() or not _PRINCIPAL.get().is_admin:
        return dict(REMOTE_PATH_UPLOAD_DISABLED)             # before ANY filesystem access: no existence oracle either
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
    headers = _trusted_headers()                          # F15: the upload is stamped with the principal it is for
    if headers is None:
        return dict(NO_PRINCIPAL)
    async with httpx.AsyncClient(timeout=600, headers=headers) as client:
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
    """DEPRECATED for agent work — use polymath_search (q0-only evidence rows) or polymath_explore (full planning +
    Corpus Explore -> EvidencePacket, no answer). Kept for existing callers. Retrieve evidence chunks for a query within ONE corpus. mode:
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
        return {"evidence_rows": _trim_rows(out["evidence_rows"]), "evidence_contract": out.get("evidence_contract"),
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
    """Contract rows with `text` / `text_clean` cut at 1,200 characters (D-02; the shared rule, MR.trim_rows)."""
    return MR.trim_rows(rows)


@mcp.tool()
async def compile_plan(signal: str, corpus_id: str, limit: int = 24, explore: bool = True,
                       communities: Optional[list[str]] = None) -> dict:
    """DEPRECATED for agent work — use polymath_explore (Polymath's full retrieval planning; submit the ORIGINAL need
    once). Kept for existing callers. CORPUS-PLAN-V1: send ONE signal; Polymath compiles 3-5 deterministic
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
    """DEPRECATED — use polymath_search (the same contract rows under the canonical name). Kept for existing callers.
    RETRIEVE-EVIDENCE-ROWS-V1: contract-ready evidence rows for one query
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
    """DEPRECATED — use polymath_answer when a HUMAN wants Polymath's own answer; for agent work use polymath_search /
    polymath_explore and reason over the evidence yourself (never nest a second synthesis). Kept for existing callers.
    Ask a question of ONE corpus and get the grounded RAG answer with
    citations (the same path the Polymath chat UI uses)."""
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
_MODE_ARG = "mode: " + " | ".join(MR.RETRIEVAL_MODES) + f" (default {MR.DEFAULT_MODE}). " + MR.mode_lines()


@mcp.tool(description=(
    "ONE direct search of one library in the retrieval mode you choose: no query planning, no Corpus Explore, no answer. "
    "Returns contract evidence rows (passages with their source, utility_role and ca4_grade; GRAPH adds attested graph "
    "facts) and, in WILDCARD, the separate wildcard lane. Pass the ORIGINAL question; Polymath owns retrieval planning "
    "(use polymath_explore for that). " + _MODE_ARG))
async def polymath_search(query: str, corpus_id: str, mode: str = MR.DEFAULT_MODE, max_evidence: int = 12) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    out = await _orch("POST", "/chat/evidence", json=MR.search_body(query, corpus_id, m))
    return MR.shape_search(out, max_evidence)


@mcp.tool(description=(
    "Full retrieval PLANNING + grounded expansion (+ optional Corpus Explore) in the mode you choose -> a versioned "
    "EvidencePacket (evidence with roles DIRECT/COMPLEMENTARY/DIVERGENT, CA4 grades, provenance, receipts) with NO "
    "Polymath answer, plus graph facts (GRAPH) and the wildcard lane (WILDCARD). Discover hidden/adjacent corpus knowledge, "
    "then do your OWN final reasoning. Do NOT pre-decompose. corpus_explorer=true runs the concept-activation explorer. "
    + _MODE_ARG))
async def polymath_explore(query: str, corpus_id: str, corpus_explorer: bool = True,
                           mode: str = MR.DEFAULT_MODE) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    out = await _orch("POST", "/chat/evidence", json=MR.explore_body(query, corpus_id, m, corpus_explorer))
    return MR.shape_explore(out)


_DEFAULT_MODEL = MR.DefaultModel()


async def _app_default_model() -> Optional[str]:
    """PRODUCT-SEARCH-E2E: the model the app's chat writes with when none is named (the /synthesizers row marked `default`, the
    web UI's rule), asked at most once per MR.DEFAULT_MODEL_TTL_S. /chat on its own answers with its deterministic template, so
    without this polymath_answer was not "the app's answer" at all. None = the catalog is unavailable: nothing is sent."""
    return _DEFAULT_MODEL.cached() or _DEFAULT_MODEL.remember(await _orch("GET", "/synthesizers"))


@mcp.tool(description=MR.ANSWER + _MODE_ARG)
async def polymath_answer(question: str, corpus_id: str, mode: str = MR.DEFAULT_MODE,
                          reasoning: str = "none", model: Optional[str] = None,
                          latent: Optional[bool] = None) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    style = MR.normalize_reasoning(reasoning)
    if style is None:
        return {"error": f"unknown reasoning style {reasoning!r}", "status": 422, "styles": list(MR.REASONING_STYLES)}
    model = model or await _app_default_model()
    out = await _orch("POST", "/chat", json=MR.answer_body(question, corpus_id, m, reasoning=style, model=model, latent=latent))
    if "error" in out:
        return out
    slim = dict(out)
    for key in ("evidence", "chunks", "bundle"):
        val = slim.get(key)
        if isinstance(val, list):
            slim[key] = [_trim_hit(h, 600) if isinstance(h, dict) else h for h in val[:12]]
    return slim


@mcp.tool(description=(
    "Run ONE question through several retrieval modes of one library, side by side (retrieval only, no answer; the app's "
    "Compare screen). Per mode: latency, evidence count, the documents it reached and its top rows; plus the chunks every "
    "mode found and how many only one mode found. Use it to pick a mode before polymath_search / polymath_explore. "
    "modes = any of " + ", ".join(MR.RETRIEVAL_MODES) + " (default: all five; they run one after another)."))
async def polymath_compare(question: str, corpus_id: str, modes: Optional[list[str]] = None) -> dict:
    wanted = list(modes or MR.RETRIEVAL_MODES)
    normal = [MR.normalize_mode(x) for x in wanted]
    if None in normal:
        return MR.mode_error(wanted[normal.index(None)])
    out = await _orch("POST", "/compare", json=MR.compare_body(question, corpus_id, list(dict.fromkeys(normal))), timeout=600)
    return MR.shape_compare(out)


@mcp.tool(description=(
    "The app's DEEP RESEARCH on one library: Polymath plans research goals, searches in rounds, follows leads and writes a "
    "cited report (report text with [cid] markers, the citations, the run's counts and stop reason). It takes MINUTES and "
    "spends model calls; one run per caller at a time. depth = " + "; ".join(f"{k}: {v}" for k, v in MR.DEPTHS.items())
    + f" (default {MR.DEFAULT_DEPTH}). mode = the retrieval mode every search uses (default {MR.DEFAULT_MODE}). model = a "
    "model id from polymath_models (default: the app's default)."))
async def polymath_deep_research(question: str, corpus_id: str, depth: str = MR.DEFAULT_DEPTH,
                                 mode: str = MR.DEFAULT_MODE, model: Optional[str] = None) -> dict:
    m = MR.normalize_mode(mode)
    if m is None:
        return MR.mode_error(mode)
    d = MR.normalize_depth(depth)
    if d is None:
        return {"error": f"unknown depth {depth!r}", "status": 422, "depths": dict(MR.DEPTHS)}
    frames = await _orch_events("/research/deep", MR.deep_body(question, corpus_id, d, m, model))
    return MR.shape_deep(frames, depth=d, mode=m)


@mcp.tool(description="The models Polymath can write with (ids for polymath_answer / polymath_deep_research / product_search "
                      "`model`); `default` is the one used when you name none.")
async def polymath_models() -> dict:
    return MR.shape_models(await _orch("GET", "/synthesizers"))


# PRODUCT-SEARCH-E2E (the owner, 2026-11-01: "the trail agent os and or product search tools the agents must know how to use it, how it
# works, e2e"): the ONE entry point for a product question, and the way raw local Agent Reach output comes back in. Both are plain
# proxies (the routes decide everything); the same names, parameters and descriptions on Server B.
@mcp.tool(description=MR.PRODUCT_SEARCH)
async def product_search(message: str, corpus_id: Optional[str] = None, geography: Optional[str] = None,
                         model: Optional[str] = None, hypotheses: Optional[list[dict]] = None,
                         limit_per_hypothesis: Optional[int] = None) -> dict:
    model = model or await _app_default_model()
    out = await _orch("POST", "/product/search", json=MR.product_body(message, corpus_id, geography=geography, model=model,
                                                                      hypotheses=hypotheses,
                                                                      limit_per_hypothesis=limit_per_hypothesis), timeout=600)
    return MR.shape_product(out)


@mcp.tool(description=MR.SUPPLIER_PARSE)
async def supplier_parse(site: str, raw_text: str) -> dict:
    return await _orch("POST", "/supplier/parse", json=MR.parse_body(site, raw_text))


# PRODUCT-DECISION-REPORT-V1 (B5): one private HTML decision report per product search, for any agent. Plain proxies onto
# /product/report/* (the routes decide everything, a report's privacy included); the same names, parameters, descriptions and
# timeouts on Server B. The loop and the subagent recipe live once, in MR.
def _upload_base() -> str:
    """Where the agent's fetch script will run, so the route's upload URL works there: `local` for a caller that addressed the
    loopback listener with no edge headers (an agent on this host: `_is_local_caller`, decided by the gate per request),
    `public` for every other caller (another machine: the public web door). A lost context says public, which works anywhere."""
    return "local" if _CALLER_IS_LOCAL.get() else "public"


#: each report's upload token, per principal and report (contract C1): sent back as X-Upload-Token on every status call, so a
#: report keeps one live upload link instead of one per status call; memory only, at most MR.REPORT_TOKEN_CACHE_MAX reports.
#: C1-C10 are the review-fix contracts recorded in docs/wiki/work-log/2026-11-02-product-decision-report.md (the capability is
#: ADR-0023, docs/wiki/decisions/0023-report-upload-capability.md).
_REPORT_TOKENS = MR.ReportTokens()


def _token_key(report_id: str) -> tuple[str, str]:
    return (_PRINCIPAL.get().principal_id, report_id)


@mcp.tool(description=MR.PRODUCT_REPORT_START)
async def product_report_start(message: Optional[str] = None, corpus_id: Optional[str] = None,
                               products: Optional[list[dict]] = None, channels: Optional[list[str]] = None,
                               ship_to: str = "US", max_products: int = MR.REPORT_DEFAULT_PRODUCTS) -> dict:
    body = MR.report_start_body(message, corpus_id, products=products, channels=channels, ship_to=ship_to,
                                max_products=max_products, upload_base=_upload_base())
    out = await _orch("POST", MR.REPORT_START_PATH, json=body, timeout=MR.REPORT_TIMEOUT_S["start"])
    rid = MR.normalize_report_id(out.get("report_id")) if isinstance(out, dict) else None
    if rid:
        _REPORT_TOKENS.remember(_token_key(rid), out, rid)
    return MR.shape_report(out)


@mcp.tool(description=MR.PRODUCT_REPORT_STATUS)
async def product_report_status(report_id: str) -> dict:
    rid = MR.normalize_report_id(report_id)
    if rid is None:
        return MR.report_id_error(report_id)
    key = _token_key(rid)
    out = await _orch("GET", MR.report_status_path(rid, _upload_base()), headers=_REPORT_TOKENS.headers(key),
                      timeout=MR.REPORT_TIMEOUT_S["status"])
    _REPORT_TOKENS.remember(key, out, rid)
    return MR.shape_report(out)


@mcp.tool(description=MR.PRODUCT_REPORT_COMPILE)
async def product_report_compile(report_id: str, verdicts: Optional[dict[str, str]] = None) -> dict:
    rid = MR.normalize_report_id(report_id)
    if rid is None:
        return MR.report_id_error(report_id)
    return await _orch("POST", MR.report_path(rid, "compile"), json=MR.report_compile_body(verdicts),
                       timeout=MR.REPORT_TIMEOUT_S["compile"])


@mcp.tool(description=MR.PRODUCT_REPORT_LIST)
async def product_report_list() -> dict:
    return await _orch("GET", MR.REPORT_LIST_PATH, timeout=MR.REPORT_TIMEOUT_S["list"])


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
    return await _orch("GET", "/queries", params=params)      # a principal's context narrows it to its OWN receipts



# ------------------------------------------------------- cognitive adapter (ADR-0018)

@mcp.tool(description=MR.ADAPTER_LIST)
async def adapter_list() -> dict:
    out = await _orch("GET", "/adapter/list")
    who = _PRINCIPAL.get()
    if not who.is_admin and isinstance(out, dict) and isinstance(out.get("adapters"), list):
        out["adapters"] = [a for a in out["adapters"] if isinstance(a, dict) and a.get("adapter_id") in who.adapter_ids]
    return out


@mcp.tool(description=MR.ADAPTER_START)
async def adapter_start(adapter_id: str, input: dict, request_options: Optional[dict] = None) -> dict:
    # RUN OWNERSHIP is the runtime's: the forwarded principal context becomes adapter_runs.owner_principal_id
    return await _orch("POST", "/adapter/start", json={"adapter_id": adapter_id, "input": input, "request_options": request_options or {}})


@mcp.tool(description=MR.ADAPTER_NEXT)
async def adapter_next(run_id: str) -> dict:
    return await _orch("GET", f"/adapter/{run_id}/next")


@mcp.tool()
async def adapter_submit(run_id: str, step_id: str, payload: dict, agent_identity: str = "connected-agent",
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


# AUTORESEARCH-SOURCES-AND-HARNESS-V1 R8: Polymath-hosted research reads. NOT in the principals' TOOL_POLICY on purpose: the host
# browser holds the owner's sign-ins, so the gate keeps this tool owner-only (and the orchestrator refuses any principal too).
@mcp.tool(description=MR.RESEARCH_ACQUIRE)
async def research_acquire(run_id: str, operation: str, target: str = "", site: Optional[str] = None,
                           search_intent_id: Optional[str] = None, limit: Optional[int] = None) -> dict:
    return await _orch("POST", f"/adapter/{run_id}/acquire", json={"operation": operation, "target": target, "site": site,
                                                                  "search_intent_id": search_intent_id, "limit": limit})


# SUPPLIER-APIS (owner-approved 2026-09-27; PRODUCT-SEARCH-E2E 2026-11-01): READ-ONLY supplier tools over CJ's official REST API on
# the host's CJ account, paced for every caller. Who may call them is the principals' TOOL_POLICY (mcp_principals.py); Alibaba is
# never read from the host: it, and every CJ failure, answers with a local Agent Reach `fallback` whose raw output comes back
# through supplier_parse. CJ's own MCP server is not used: its token also reaches orders, payments, disputes and store listings.
@mcp.tool(description=MR.SUPPLIER_SEARCH)
async def supplier_search(query: str, source: str = "cj", limit: int = 10) -> dict:
    return await _orch("POST", "/supplier/search", json={"query": query, "source": source, "limit": limit})


@mcp.tool(description=MR.SUPPLIER_PRODUCT)
async def supplier_product(product_id: str) -> dict:
    return await _orch("POST", "/supplier/product", json={"product_id": product_id})


@mcp.tool(description=MR.SUPPLIER_FREIGHT)
async def supplier_freight(variant_id: str, country: str, quantity: int = 1, from_country: str = "CN") -> dict:
    return await _orch("POST", "/supplier/freight", json={"variant_id": variant_id, "country": country, "quantity": quantity,
                                                          "from_country": from_country})


@mcp.tool(description=MR.SUPPLIER_WAREHOUSES)
async def supplier_warehouses() -> dict:
    return await _orch("GET", "/supplier/warehouses")


# ------------------------------------------------------- the operating guide for any agent harness
# AUTORESEARCH-SOURCES-AND-HARNESS-V1 (gaps H-01, H-02, H-04): ONE guide, published identically by both MCP servers as a prompt
# and resources (polymath_shared.adapter.harness_guide); the files are read per request, so a re-pinned Trail source table is live.
_GUIDE_ROOT = Path(__file__).resolve().parents[2]


def _guide_resources() -> dict:
    return HG.resources({uri: (_GUIDE_ROOT / rel).read_text(encoding="utf-8") for uri, rel in HG.FILES.items()})


def _guide_reader(uri: str):
    def read() -> str:
        return _guide_resources()[uri][1]
    return read


for _uri in HG.RESOURCE_URIS:
    mcp.resource(_uri, name=_uri.rsplit("/", 1)[-1], title=HG.TITLES[_uri], description=HG.TITLES[_uri], mime_type=HG.MIME[_uri])(_guide_reader(_uri))


@mcp.prompt(name=HG.PROMPT_NAME, title="Run a governed adapter end to end", description=HG.PROMPT_DESCRIPTION)
def run_governed_research(adapter_id: str = "", seed: str = "") -> str:
    """The operating guide, then where to begin (optionally a given adapter and seed)."""
    return HG.prompt_text(adapter_id, seed)


# CLAUDE-CONNECTOR-URL (the owner, 2026-10-01: "how do i connect polymath mcp to claude connector i need the url"): claude.ai's
# custom connector sends no headers, only a URL. https://<host>/k/<key>/mcp carries the key in the path; the OUTERMOST layer moves
# it into the Authorization header and rewrites the path to /mcp in place, so the access log and every layer below see /mcp, never
# the key, and the bearer gate judges it exactly like a header key (owner or principal, same scopes, same rate limit).
_KEY_PATH = re.compile(r"^/k/([A-Za-z0-9._~+=-]{16,256})(/mcp(?:/.*)?)$")
# the same key form further down a path: claude.ai's OAuth discovery appends the connector's resource path, key included, to
# /.well-known/oauth-protected-resource (seen live 2026-10-01: the access log printed the key)
_KEY_SEGMENT = re.compile(r"/k/[A-Za-z0-9._~+=-]{16,256}(?=/mcp(?:/|$))")


class KeyInPath:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            m = _KEY_PATH.match(scope.get("path") or "")
            if m:
                key, rest = m.group(1), m.group(2)
                scope["path"] = rest                         # in place: uvicorn's access log reads this same dict
                scope["raw_path"] = rest.encode()
                scope["headers"] = [(k, v) for k, v in scope.get("headers") or [] if k.lower() != b"authorization"] + [
                    (b"authorization", b"Bearer " + key.encode())]
            elif _KEY_SEGMENT.search(scope.get("path") or ""):
                # not a connector call: drop the key so no layer and no log line holds it (that path is a 404 anyway)
                scope["path"] = _KEY_SEGMENT.sub("/k/redacted", scope["path"])
                scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


def build_app():
    """ASGI app: FastMCP streamable-http + FAIL-CLOSED bearer gate +
    open /health; the key-in-path form for connectors that cannot send a header (KeyInPath)."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route

    inner = mcp.streamable_http_app(
        stateless_http=True, transport_security=_SECURITY)

    async def health(_request):
        return JSONResponse({"service": "polymath-mcp", "ok": True,
                             "auth": "configured" if API_KEY else "MISSING",
                             "tools": sorted(t for t in _TOOL_NAMES)})

    class BearerGate:
        """401 no / unknown / revoked / expired key · 429 over the principal's rate · 403 a tools/call the principal may
        not make (action scope, corpus, adapter, another principal's run, anything without a policy) · else the MCP app.
        The OWNER key passes through untouched. A non-admin request is read ONCE here, judged, and replayed."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            if not API_KEY:
                await JSONResponse({"error": "MCP bearer key not configured (POLYMATH_MCP_API_KEY); refusing to serve"},
                                   status_code=503)(scope, receive, send)
                return
            headers = dict(scope.get("headers") or [])
            auth = (headers.get(b"authorization") or b"").decode("latin-1")
            who = _STORE.authenticate(auth[7:] if auth.startswith("Bearer ") else "")
            if who is None:
                await Response("unauthorized", status_code=401)(scope, receive, send)
                return
            _CALLER_IS_LOCAL.set(_is_local_caller(headers))
            _PRINCIPAL.set(who)
            _CALLER_AGENT.set(((headers.get(b"user-agent") or b"").decode("latin-1").strip() or "polymath-mcp")[:120])
            if who.is_admin:
                await self.app(scope, receive, send)
                return
            ok, retry_after = _LIMITER.allow(who)
            if not ok:
                await JSONResponse({"error": "rate limit exceeded", "status": 429}, status_code=429,
                                   headers={"Retry-After": str(retry_after)})(scope, receive, send)
                return
            if scope.get("method") != "POST":
                await self.app(scope, receive, send)
                return
            body = await _read_body(receive)
            if body is None:
                await JSONResponse({"error": "request body too large", "status": 413}, status_code=413)(scope, receive, send)
                return
            try:
                msg = json.loads(body) if body else None
            except ValueError:
                msg = None                                   # not JSON: the MCP app answers the protocol error itself
            except RecursionError:                           # nested past what the gate can judge: never passed on unjudged
                await JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: nested too deeply"}},
                                   status_code=400)(scope, receive, send)
                return
            try:
                denial = await _judge(who, msg)
            except (httpx.HTTPError, ValueError):            # the run check could not reach the orchestrator: refuse, in JSON-RPC
                log.warning("mcp run check unavailable principal=%s", who.principal_id)
                await JSONResponse({"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None,
                                    "error": {"code": -32003, "message": "UNAVAILABLE: Polymath could not check this run; try again",
                                              "data": {"status": 503, "reason": "orchestrator_unavailable"}}},
                                   status_code=503)(scope, receive, send)
                return
            if denial is not None:
                log.info("mcp deny principal=%s tool=%s reason=%s", who.principal_id, denial[2], denial[0].reason)
                await JSONResponse({"jsonrpc": "2.0", "id": denial[1],
                                    "error": {"code": -32003, "message": f"FORBIDDEN: {denial[0].message}",
                                              "data": {"status": 403, "reason": denial[0].reason}}},
                                   status_code=403)(scope, receive, send)
                return
            replay = _replay(body, receive)
            if isinstance(msg, dict) and msg.get("method") == "tools/list":
                await _filtered_tools_list(self.app, scope, replay, send, who)
                return
            await self.app(scope, replay, send)

    async def _read_body(receive):
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return b"".join(chunks)
            chunks.append(message.get("body", b""))
            size += len(chunks[-1])
            if size > MAX_GATED_BODY:
                return None
            if not message.get("more_body"):
                return b"".join(chunks)

    def _replay(body, receive):
        state = {"sent": False}

        async def replayed():
            if not state["sent"]:
                state["sent"] = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        return replayed

    async def _judge(who, msg):
        """None = let it through; else (Decision, jsonrpc id, tool name). JSON-RPC batches are refused for a non-admin
        principal: a batch would let a call ride past a per-message judgement."""
        if isinstance(msg, list):
            return P.Decision(False, "batch_not_permitted", "send one JSON-RPC message per request"), None, "<batch>"
        if not isinstance(msg, dict) or msg.get("method") != "tools/call":
            return None
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        tool, args = params.get("name"), params.get("arguments")
        decision = P.authorize(who, tool if isinstance(tool, str) else "", args)    # product_search: CORPUS_OPTIONAL (owner R11)
        if decision.allowed and P.TOOL_POLICY.get(tool, ((), ""))[1] == P.RUN:
            run_id = args.get("run_id") if isinstance(args, dict) else None
            # the adapter runtime owns the answer (adapter_runs.owner_principal_id); it gives ONE answer for "not yours"
            # and "no such run", so a private run's existence is not disclosed. Anything but a clean status = denied.
            status = await _orch("GET", f"/adapter/{run_id}/status") if isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_]{1,80}", run_id) else None
            if not isinstance(status, dict) or "error" in status:
                decision = P.Decision(False, "run_not_accessible", "no such run for this principal")
        return None if decision.allowed else (decision, msg.get("id"), tool)

    async def _filtered_tools_list(app, scope, receive, send, who):
        """A principal's tools/list shows only the tools its scopes can call (calls are judged regardless)."""
        start, chunks = {}, []

        async def capture(message):
            if message["type"] == "http.response.start":
                start.update(message)
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
        await app(scope, receive, capture)
        raw = b"".join(chunks)
        try:
            text = raw.decode()
            if b"text/event-stream" in dict(start.get("headers") or []).get(b"content-type", b""):
                text = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")][-1]
            doc = json.loads(text)
            doc["result"]["tools"] = [t for t in doc["result"]["tools"]
                                      if set(P.TOOL_POLICY.get(t.get("name"), ((), ""))[0]) & who.scopes]
            await JSONResponse(doc, status_code=start.get("status", 200))(scope, receive, send)
        except (ValueError, KeyError, IndexError, TypeError, UnicodeDecodeError):
            await send({**start, "type": "http.response.start"})
            await send({"type": "http.response.body", "body": raw, "more_body": False})

    app = Starlette(routes=[
        Route("/health", health),
        # no OAuth here: a connector probing for it gets a plain 404, not the gate's 401 (which reads as "OAuth required")
        Route("/.well-known/{rest:path}", lambda _request: JSONResponse({"error": "not found"}, status_code=404)),
        Mount("/", app=BearerGate(inner)),
    ], middleware=[Middleware(KeyInPath)])                   # before routing: the key leaves the path before anything logs it
    # the inner app manages the streamable-http session lifecycle
    app.router.lifespan_context = inner.router.lifespan_context
    return app


_TOOL_NAMES = ("polymath_compare", "polymath_deep_research", "polymath_models",
               "adapter_list", "adapter_start", "adapter_next", "adapter_submit", "adapter_status",
               "adapter_result", "adapter_cancel", "research_acquire",
               "supplier_search", "supplier_product", "supplier_freight", "supplier_warehouses",
               "product_search", "supplier_parse",
               "product_report_start", "product_report_status", "product_report_compile", "product_report_list",
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
