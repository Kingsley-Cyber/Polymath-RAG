"""QUERY-RECEIPTS-V1 — one durable row per served query.

Before this, a query left an access-log line and `runtime_signals.last_query`
(a timestamp for the autopilot) and nothing else: no latency, scope, mode,
verdict, citations or error survived the request. Every /chat, /ask and
/retrieve now writes ONE row to `query_receipts` (migration 0047) after the
response is composed — best effort, its own short transaction, never on the
request's critical path, failures logged and swallowed. The MCP tool
`recent_queries`, `GET /queries` and `scripts/query_log.py` read it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

log = logging.getLogger("polymath.query_receipts")


def _head(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n]


def summarize_response(kind: str, out: Any) -> dict:
    """Pull the trackable facts out of a handler's response (pure)."""
    d: dict = {"status": "ok", "verdict": None, "citations": None,
               "claims": None, "evidence": None, "source_docs": [], "meta": {}}
    if not isinstance(out, dict):
        return d
    meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
    d["meta"] = {k: v for k, v in meta.items()
                 if k in ("mode", "latent", "corpus_ids", "plan", "verdict", "reranker",
                          "rerank_degraded", "lanes", "timings", "admission",
                          "answerability", "trace_id")}
    cits = out.get("citations")
    if isinstance(cits, list):
        d["citations"] = len(cits)
        docs: set[str] = set()
        for c in cits:
            if isinstance(c, dict):
                for x in (c.get("source_document_ids") or []):
                    docs.add(str(x))
                for x in (c.get("human_locators") or []):
                    docs.add(str(x))
        d["source_docs"] = sorted(docs)[:32]
    claims = out.get("claims")
    if isinstance(claims, list):
        d["claims"] = len(claims)
    for key in ("evidence", "hits", "selected_children", "child_dense_lane"):
        v = out.get(key)
        if isinstance(v, list):
            d["evidence"] = len(v)
            if not d["source_docs"]:
                d["source_docs"] = sorted({str(h.get("source_name") or h.get("doc_id") or h.get("document_id"))
                                           for h in v if isinstance(h, dict)
                                           and (h.get("source_name") or h.get("doc_id") or h.get("document_id"))})[:32]
            break
    if kind == "ask":
        # /ask returns stored objects, not prose: route, objects, cited documents, grounded
        objs = out.get("objects")
        cited = out.get("cited_document_ids")
        if isinstance(objs, list):
            d["evidence"] = len(objs)
        if isinstance(cited, list):
            d["citations"] = len(cited)
            d["source_docs"] = sorted(str(x) for x in cited)[:32]
        for k in ("route", "grounded", "latency_ms"):
            if k in out:
                d["meta"][k] = out.get(k)
        if out.get("grounded") is False or (isinstance(objs, list) and not objs):
            d["status"] = "abstained"
        d["verdict"] = str(out.get("route")) if out.get("route") is not None else None
        return d
    verdict = meta.get("verdict") or out.get("verdict")
    answer = out.get("answer")
    if kind in ("chat", "ask"):
        if isinstance(answer, str) and answer.strip().lower().startswith(
                ("i don't have enough grounded evidence", "i cannot answer", "insufficient evidence")):
            d["status"] = "abstained"
        elif isinstance(verdict, str) and "insufficient" in verdict.lower():
            d["status"] = "abstained"
    d["verdict"] = str(verdict) if verdict is not None else None
    return d


def record_query_receipt(tx_factory, *, kind: str, question: str, req: Any,
                         scope_corpora: list[str] | None, scope_kind: str | None,
                         wall_ms: float, out: Any = None, error: str | None = None,
                         client: str | None = None) -> str | None:
    """Write the receipt. `tx_factory` is polymath_shared.db.tx (a context
    manager yielding a connection); everything is wrapped so a receipt
    failure can never turn into a request failure."""
    qid = "q_" + uuid.uuid4().hex[:24]
    try:
        summ = summarize_response(kind, out) if error is None else {
            "status": "error", "verdict": None, "citations": None, "claims": None,
            "evidence": None, "source_docs": [], "meta": {}}
        mode = getattr(req, "mode", None)
        latent = getattr(req, "latent", None)
        if summ["meta"].get("mode") and not mode:
            mode = summ["meta"].get("mode")
        with tx_factory() as conn:
            conn.execute(
                """INSERT INTO query_receipts
                   (query_id, kind, received_at, client, corpus_ids, scope, mode, latent,
                    question_sha256, question_head, wall_ms, status, verdict,
                    citations, claims, evidence, source_docs, meta, error)
                   VALUES (%s,%s,clock_timestamp(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (qid, kind, _head(client or "", 120) or None,
                 list(scope_corpora or []), scope_kind,
                 (str(mode).upper() if mode else None), latent,
                 hashlib.sha256((question or "").encode("utf-8")).hexdigest(),
                 _head(question), int(round(wall_ms)), summ["status"], summ["verdict"],
                 summ["citations"], summ["claims"], summ["evidence"], summ["source_docs"],
                 json.dumps(summ["meta"], default=str)[:8000], _head(error or "", 500) or None))
        return qid
    except Exception as exc:  # noqa: BLE001 — receipts never break a query
        log.warning("query receipt not written: %s", str(exc)[:200],
                    extra={"error_code": "QUERY_RECEIPT_FAILED"})
        return None


def _row(cur, r) -> dict:
    d = dict(zip([c.name for c in cur.description], r))
    ra = d.get("received_at")
    if ra is not None and hasattr(ra, "isoformat"):
        d["received_at"] = ra.isoformat()
    for k in ("p50_ms", "p95_ms", "avg_citations"):
        if d.get(k) is not None:
            d[k] = round(float(d[k]), 1)
    return d


def _where(corpus_id: str | None, kind: str | None, since_h: float) -> tuple[str, list]:
    sql = ["received_at >= now() - make_interval(secs => %s)"]
    args: list = [float(since_h) * 3600.0]
    if corpus_id:
        sql.append("%s = ANY(corpus_ids)"); args.append(corpus_id)
    if kind:
        sql.append("kind = %s"); args.append(kind)
    return " AND ".join(sql), args


def recent_queries(conn, *, corpus_id: str | None = None, kind: str | None = None,
                   limit: int = 20, since_h: float = 24.0) -> list[dict]:
    where, args = _where(corpus_id, kind, since_h)
    cur = conn.execute(
        f"""SELECT query_id, kind, received_at, client, corpus_ids, scope, mode, latent,
                   question_head, wall_ms, status, verdict, citations, claims, evidence,
                   source_docs, error
              FROM query_receipts WHERE {where}
             ORDER BY received_at DESC LIMIT %s""", (*args, int(limit)))
    return [_row(cur, r) for r in cur.fetchall()]


def query_summary(conn, *, corpus_id: str | None = None, kind: str | None = None,
                  since_h: float = 24.0) -> list[dict]:
    """Per (kind, mode): count, p50/p95/max wall, abstained, errors, avg citations."""
    where, args = _where(corpus_id, kind, since_h)
    cur = conn.execute(
        f"""SELECT kind, COALESCE(mode, '-') AS mode, count(*) AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY wall_ms) AS p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY wall_ms) AS p95_ms,
                   max(wall_ms) AS max_ms,
                   count(*) FILTER (WHERE status = 'abstained') AS abstained,
                   count(*) FILTER (WHERE status = 'error') AS errors,
                   avg(citations) AS avg_citations
              FROM query_receipts WHERE {where}
             GROUP BY kind, COALESCE(mode, '-') ORDER BY kind, mode""", tuple(args))
    return [_row(cur, r) for r in cur.fetchall()]


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter(); return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self.t0) * 1000.0
        return False
