"""MCP-RETRIEVAL-MODES-V1 (the owner, 2026-10-01: "tools are stale and outdated. polymath has different types of retrieval").

The ONE description of Polymath's retrieval for both MCP surfaces — Server A (`orchestrator/orchestrator/mcp_server.py`,
streamable-http, bearer key) and Server B (`mcp_server/polymath_mcp.py`, stdio) — so the two cannot drift again: the five
public retrieval modes the app offers, the request each tool sends, and how each answer is cut down for an agent.

Before this, `polymath_search` sent no mode, so `/retrieve` served it from the frozen LEGACY lane route (retrieval_modes.
DEFAULT_MODE) that the app itself no longer uses. Every tool here runs the app's own chat retrieval for the chosen mode:
search = one query with planning off, explore = planning on, answer = the full turn.

Pure: no I/O and no orchestrator import (Server B runs outside the orchestrator package)."""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

#: the app's public modes: frontend-v2 `PUBLIC_MODES` = retrieval_modes.EXPOSED_MODES minus LEGACY (pinned by tests)
RETRIEVAL_MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")
DEFAULT_MODE = "HYBRID"
MODE_GUIDE = {
    "FAST": "semantic (dense-vector) search over the passages; the quickest. Good for a direct lookup.",
    "HYBRID": "FAST plus keyword matching; the default and the best all-round choice.",
    "GRAPH": "HYBRID plus the knowledge graph: the entities in the evidence and how they relate. Returns graph facts "
             "beside the passages. Use it for how things connect.",
    "WILDCARD": "the normal evidence plus a separate WILDCARD lane of surprising, still source-grounded passages from "
                "elsewhere in the library (it never displaces the evidence). Use it for ideas, analogies and lateral angles.",
    "GNN": "experimental: a graph-neural model picks the sections, their original passages prove it, the reranker judges.",
}
_ALIASES = {"VECTOR": "FAST"}                       # the old name of FAST, still accepted

#: the reasoning styles the app's answer offers (orchestrator api/reasoning.py CURATED_MODES; pinned by a test)
REASONING_STYLES = ("none", "step_by_step", "branching", "creative", "analytical", "self_correct", "atomic", "planning",
                    "graph_reason", "debate", "deep_research", "concise", "meta")

#: deep research depths (orchestrator api/deep_research.py presets): research goals x rounds
DEPTHS = {"quick": "3 goals x 1 round, the fastest (minutes)", "standard": "3 goals x 2 rounds",
          "thorough": "4 goals x 2 rounds, the slowest"}
DEFAULT_DEPTH = "quick"

#: tools kept for old callers but hidden from tools/list, so an agent is never offered them
HIDDEN_TOOLS_A = frozenset({"retrieve", "retrieve_evidence", "compile_plan", "ask"})
HIDDEN_TOOLS_B = frozenset({"polymath_query", "polymath_retrieve"})

MAX_TEXT = 1200            # an evidence row's text (D-02: a cut row says so)
WILDCARD_MAX = 8
WILDCARD_TEXT = 600
GRAPH_FACTS_MAX = 20
COMPARE_ROWS = 6
REPORT_CITATION_TEXT = 400


def mode_lines() -> str:
    return " ".join(f"{m}: {MODE_GUIDE[m]}" for m in RETRIEVAL_MODES)


def normalize_mode(mode: Any) -> str | None:
    """The canonical mode name, or None when `mode` is not one of the five public modes."""
    m = str(mode or DEFAULT_MODE).strip().upper()
    m = _ALIASES.get(m, m)
    return m if m in RETRIEVAL_MODES else None


def mode_error(mode: Any) -> dict:
    return {"error": f"unknown retrieval mode {mode!r}; use one of {list(RETRIEVAL_MODES)}", "status": 422,
            "modes": dict(MODE_GUIDE)}


def normalize_reasoning(style: Any) -> str | None:
    s = str(style or "none").strip().lower()
    return s if s in REASONING_STYLES else None


def normalize_depth(depth: Any) -> str | None:
    d = str(depth or DEFAULT_DEPTH).strip().lower()
    return d if d in DEPTHS else None


# ---------------------------------------------------------------- requests (one body per tool, the same on both servers)

def search_body(query: str, corpus_id: str, mode: str) -> dict:
    """ONE query on the app's retrieval for `mode`: the chat runtime's evidence route with the query compiler OFF (no
    planning, no Corpus Explore) and `evidence` on, so the answer carries RETRIEVE-EVIDENCE-ROWS-V1 rows."""
    return {"message": query, "corpus_id": corpus_id, "mode": mode, "compiler": "off", "corpus_explorer": False,
            "evidence": True}


def explore_body(query: str, corpus_id: str, mode: str, corpus_explorer: bool) -> dict:
    return {"message": query, "corpus_id": corpus_id, "mode": mode, "corpus_explorer": bool(corpus_explorer)}


def answer_body(question: str, corpus_id: str, mode: str, *, reasoning: str | None = None, model: str | None = None,
                latent: bool | None = None) -> dict:
    body: dict[str, Any] = {"message": question, "corpus_id": corpus_id, "mode": mode}
    if reasoning and reasoning != "none":
        body["reasoning"] = reasoning
    if model:
        body["synthesizer"] = model
    if latent is not None:
        body["latent"] = bool(latent)
    return body


def compare_body(question: str, corpus_id: str, modes: Iterable[str]) -> dict:
    return {"message": question, "corpus_id": corpus_id, "modes": list(modes)}


def deep_body(question: str, corpus_id: str, depth: str, mode: str, model: str | None = None) -> dict:
    body: dict[str, Any] = {"question": question, "corpus_id": corpus_id, "preset": depth, "mode": mode}
    if model:
        body["synthesizer"] = model
    return body


# ---------------------------------------------------------------- answers, cut down for an agent

def trim_rows(rows: Iterable[dict] | None, max_chars: int = MAX_TEXT) -> list[dict]:
    """Contract rows with `text` / `text_clean` cut at `max_chars`. D-02: a cut row says so — `truncated: true` +
    `full_length` (the untrimmed `text`, else `text_clean`, in characters); a row that fits is unchanged."""
    out = []
    for r in rows or []:
        r = dict(r)
        full = {k: len(r[k]) for k in ("text", "text_clean") if isinstance(r.get(k), str) and len(r[k]) > max_chars}
        for k in full:
            r[k] = r[k][:max_chars]
        if full:
            r["truncated"] = True
            r["full_length"] = full.get("text", full.get("text_clean"))
        out.append(r)
    return out


def _clip(text: Any, n: int) -> tuple[str, bool]:
    s = str(text or "")
    return (s[:n], True) if len(s) > n else (s, False)


def shape_wildcard(items: Any) -> list[dict]:
    """The WILDCARD lane, at most WILDCARD_MAX items: identity + why it was offered + a bounded excerpt."""
    out = []
    for it in (items if isinstance(items, list) else [])[:WILDCARD_MAX]:
        if not isinstance(it, dict):
            continue
        keep = {k: it[k] for k in ("chunk_id", "doc_id", "source_name", "title", "heading_path", "score", "kind", "label",
                                   "insight", "bridge", "reason", "facet_id", "arrival") if it.get(k) not in (None, "", [], {})}
        text, cut = _clip(it.get("text") or it.get("text_clean") or it.get("insight") or "", WILDCARD_TEXT)
        if text:
            keep["text"] = text
            if cut:
                keep["truncated"] = True
        sources = it.get("sources") or it.get("children")
        if isinstance(sources, list):
            keep["sources"] = [{k: s.get(k) for k in ("chunk_id", "doc_id", "source_name") if isinstance(s, dict) and s.get(k)}
                               for s in sources[:4]]
        out.append(keep)
    return out


def _executed_mode(out: dict) -> str | None:
    """The mode that ran, in the public name: the runtime stamps FAST as VECTOR (its internal name; seen live 2026-10-01)."""
    mode = (out.get("meta") or {}).get("mode")
    return _ALIASES.get(mode, mode) if isinstance(mode, str) else mode


def _degraded(out: dict) -> Any:
    retrieval = out.get("retrieval") if isinstance(out.get("retrieval"), dict) else {}
    return retrieval.get("degraded") or (out.get("meta") or {}).get("degraded") or None


def shape_search(out: dict, max_evidence: int) -> dict:
    """polymath_search's answer: the executed mode, the evidence rows (chunk rows first, graph facts after), and the
    WILDCARD lane when the mode has one. `graph_facts` stays the count it always was."""
    if "error" in out:
        return out
    rows = [r for r in out.get("evidence_rows") or [] if isinstance(r, dict)]
    chunks = [r for r in rows if r.get("kind") != "graph_fact"][:max(1, int(max_evidence))]
    facts = [r for r in rows if r.get("kind") == "graph_fact"][:GRAPH_FACTS_MAX]
    shaped: dict[str, Any] = {"mode": _executed_mode(out),
                              "evidence_rows": trim_rows(chunks + facts),
                              "evidence_contract": out.get("evidence_contract"),
                              "graph_facts": len(facts)}
    wildcard = shape_wildcard((out.get("retrieval") or {}).get("wildcard"))
    if wildcard:
        shaped["wildcard"] = wildcard
    for key in ("evidence_rows_error", "latency_ms", "scope"):
        if out.get(key) is not None:
            shaped[key] = out[key]
    deg = _degraded(out)
    if deg:
        shaped["degraded"] = deg
    return shaped


def shape_explore(out: dict) -> dict:
    """polymath_explore's answer: the EvidencePacket (already bounded), the executed mode, the graph facts and the
    WILDCARD lane; the runtime's full retrieval inventory and phase list stay out (diagnostics, tens of KB)."""
    if "error" in out:
        return out
    retrieval = out.get("retrieval") if isinstance(out.get("retrieval"), dict) else {}
    shaped: dict[str, Any] = {"mode": _executed_mode(out),
                              "evidence_packet": out.get("evidence_packet"),
                              "synthesis_performed": out.get("synthesis_performed", False)}
    facts = [f for f in out.get("graph_facts") or [] if isinstance(f, dict)][:GRAPH_FACTS_MAX]
    if facts:
        shaped["graph_facts"] = facts
    wildcard = shape_wildcard(retrieval.get("wildcard"))
    if wildcard:
        shaped["wildcard"] = wildcard
    for key in ("latency_ms", "scope"):
        if out.get(key) is not None:
            shaped[key] = out[key]
    deg = _degraded(out)
    if deg:
        shaped["degraded"] = deg
    return shaped


def shape_compare(out: dict, max_rows: int = COMPARE_ROWS) -> dict:
    """polymath_compare's answer: per mode the latency, counts, documents and its top rows, plus what every mode found
    and what only one mode found (chunk ids)."""
    if "error" in out:
        return out
    arms = []
    found: dict[str, set] = {}
    for arm in out.get("arms") or []:
        if not isinstance(arm, dict):
            continue
        mode = arm.get("mode")
        if not arm.get("ok"):
            arms.append({"mode": mode, "ok": False, "latency_ms": arm.get("latency_ms"), "error": arm.get("error")})
            continue
        r = arm.get("retrieval") or {}
        rows = [x for x in r.get("rows") or [] if isinstance(x, dict)]
        found[mode] = {str(x.get("chunk_id")) for x in rows if x.get("chunk_id")}
        arms.append({"mode": mode, "ok": True, "latency_ms": arm.get("latency_ms"),
                     "evidence_count": r.get("evidence_count"), "documents": (r.get("documents") or [])[:12],
                     "top_rows": [{k: x.get(k) for k in ("chunk_id", "doc_id", "source_name", "score", "arrival")}
                                  for x in rows[:max(1, int(max_rows))]],
                     **({"degraded": r["degraded"]} if r.get("degraded") else {})})
    shared = set.intersection(*found.values()) if found else set()
    return {"contract": out.get("contract"), "corpus_id": out.get("corpus_id"), "question": out.get("question"),
            "arms": arms, "found_by_every_mode": sorted(shared),
            "only_this_mode": {m: len(ids - set().union(*(o for k, o in found.items() if k != m))) for m, ids in found.items()},
            **({"scope": out["scope"]} if out.get("scope") is not None else {})}


def shape_models(out: dict) -> dict:
    if "error" in out:
        return out
    entries = [e for e in out.get("synthesizers") or out.get("models") or [] if isinstance(e, dict)]
    offered = [e for e in entries if e.get("offered", True) is not False]
    models = [{k: e.get(k) for k in ("id", "label", "provider_label", "description") if e.get(k)} for e in offered]
    return {"default": models[0]["id"] if models else None, "models": models}


# ---------------------------------------------------------------- deep research: the server-sent events of /research/deep

def parse_sse(lines: Iterable[str]) -> Iterator[tuple[str, dict]]:
    """(event, data) for every frame of a text/event-stream; keep-alive comments and malformed frames are skipped."""
    event, data = None, []
    for raw in lines:
        line = raw.rstrip("\r\n") if isinstance(raw, str) else raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if event is not None and data:
                try:
                    yield event, json.loads("\n".join(data))
                except ValueError:
                    pass
            event, data = None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
    if event is not None and data:
        try:
            yield event, json.loads("\n".join(data))
        except ValueError:
            pass


def shape_deep(events: Iterable[tuple[str, dict]], *, depth: str, mode: str) -> dict:
    """polymath_deep_research's answer from the stream: the cited report, its citations, the coverage, the run's counts.
    A typed error frame becomes {"error", "status"}; a stream with no report says so."""
    answer, error, coverage, stages = None, None, None, []
    for kind, data in events:
        if kind == "answer":
            answer = data
        elif kind == "error" and error is None:
            error = data
        elif kind == "coverage":
            coverage = data
        elif kind == "phase" and isinstance(data, dict) and data.get("label"):
            stages.append(data.get("label"))
    if answer is None:
        if error is not None:
            code = str(error.get("error_code") or "DEEP_RESEARCH_FAILED")
            return {"error": f"{code}: {error.get('message') or ''}".strip(), "status": 409 if code == "DEEP_RESEARCH_BUSY" else 502,
                    "error_code": code, **({"summary": error["summary"]} if error.get("summary") else {})}
        return {"error": "the deep research stream ended without a report", "status": 502, "stages": stages[-6:]}
    result = answer.get("result") or {}
    meta = result.get("meta") or {}
    block = meta.get("deep_research") if isinstance(meta.get("deep_research"), dict) else {}
    counts = None
    model = block.get("report_model") if isinstance(block, dict) else None
    if isinstance(model, dict):
        findings = [f for goal in model.get("goals") or [] for f in goal.get("findings") or []]
        counts = {"goals": len(model.get("goals") or []), "findings": len(findings), "sources": len(model.get("sources") or []),
                  "open_questions": len(model.get("open_questions") or []),
                  "confidence": {c: sum(1 for f in findings if f.get("confidence") == c)
                                 for c in ("strong", "single_source", "contested")}}
    citations = []
    for c in result.get("citations") or []:
        if isinstance(c, dict):
            text, cut = _clip(c.get("text"), REPORT_CITATION_TEXT)
            citations.append({**{k: c.get(k) for k in ("cid", "id", "kind", "doc_id", "corpus_id", "title", "source") if c.get(k)},
                              "text": text, **({"truncated": True} if cut else {})})
    return {"depth": depth, "mode": mode, "report": result.get("text"), "model": result.get("model"),
            "verdict": meta.get("verdict"), "citations": citations,
            "unknown_citations": list(result.get("unknown_citations") or []),
            "counts": counts, "stop_reason": (block or {}).get("stop_reason"),
            "coverage": coverage, "latency_ms": answer.get("latency_ms")}
