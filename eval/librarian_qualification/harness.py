#!/usr/bin/env python3
"""LIBRARIAN-QUALIFICATION-V1 — real-user-path retrieval qualification (mission §10-§27).

Fires each gold query through the ACTUAL production `/chat/stream` endpoint (the same path a
user hits), captures the full receipt (chat_plan + scout + subquery_provenance + legend +
used_evidence + funnel/lane trace + answer), and scores retrieval against corpus-grounded gold
documents with deterministic IR metrics (Recall@K / Precision@K / MRR). No mocks: the orchestrator,
compiler, scout, candidate engine, reranker and synthesizer all run for real.

Usage:
    .venv/bin/python eval/librarian_qualification/harness.py --gold eval/librarian_qualification/gold_queries.json \
        --out eval/librarian_qualification/results --modes FAST HYBRID GRAPH WILDCARD
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
import urllib.request

BASE = "http://127.0.0.1:7200"
HERE = pathlib.Path(__file__).resolve().parent


def probe(question: str, corpus: str, mode: str, synthesizer: str = "deterministic-template-v3",
          timeout: int = 150) -> dict:
    """One real /chat/stream turn. Returns the parsed receipt, never raises (errors captured)."""
    body = json.dumps({"message": question, "corpus_id": corpus, "mode": mode,
                       "synthesizer": synthesizer}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json",
                                          "accept": "text/event-stream"})
    phases: list[str] = []
    answer_evt: dict = {}
    err = None
    cur = None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("event:"):
                    cur = line[6:].strip()
                elif line.startswith("data:"):
                    d = line[5:].strip()
                    if cur == "phase":
                        try:
                            phases.append(json.loads(d).get("stage"))
                        except Exception:
                            pass
                    elif cur == "answer":
                        try:
                            answer_evt = json.loads(d)
                        except Exception:
                            pass
                    elif cur == "error":
                        err = d
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:200]}"
    retrieval = answer_evt.get("retrieval") or {}
    result = answer_evt.get("result") or {}
    answer_text = result.get("answer") if isinstance(result, dict) else (result if isinstance(result, str) else "")
    return {
        "question": question, "mode": mode, "corpus": corpus, "error": err,
        "latency_s": round(time.time() - t0, 2), "phases": phases,
        "answer": answer_text, "answer_kind": (result or {}).get("kind") if isinstance(result, dict) else None,
        "retrieval": retrieval,
    }


def legend_doc_order(retrieval: dict) -> list[str]:
    """Unique doc_ids in final-evidence (legend) order — the reranked document ranking."""
    seen: list[str] = []
    for item in retrieval.get("legend") or []:
        did = item.get("doc_id")
        if did and did not in seen:
            seen.append(did)
    return seen


def used_doc_ids(retrieval: dict) -> list[str]:
    """doc_ids of the chunks actually USED in synthesis (via the legend chunk->doc map)."""
    chunk2doc = {it.get("chunk_id"): it.get("doc_id") for it in (retrieval.get("legend") or [])}
    out: list[str] = []
    for ch in retrieval.get("used_evidence") or []:
        did = chunk2doc.get(ch)
        if did and did not in out:
            out.append(did)
    return out


def recall_at_k(gold: set[str], ranked: list[str], k: int) -> float:
    if not gold:
        return 1.0
    return len(gold & set(ranked[:k])) / len(gold)


def precision_at_k(gold: set[str], ranked: list[str], k: int) -> float:
    if not ranked[:k]:
        return 0.0
    return len(gold & set(ranked[:k])) / len(ranked[:k])


def mrr(gold: set[str], ranked: list[str]) -> float:
    for i, d in enumerate(ranked, start=1):
        if d in gold:
            return 1.0 / i
    return 0.0


def evaluate_query(q: dict, corpus: str, modes: list[str], k: int = 10) -> dict:
    gold = set(q.get("gold_doc_ids") or [])
    unsupported = bool(q.get("unsupported"))
    per_mode = {}
    for mode in q.get("modes") or modes:
        rec = probe(q["query"], corpus, mode)
        retr = rec["retrieval"]
        ranked = legend_doc_order(retr)
        used = used_doc_ids(retr)
        plan = retr.get("chat_plan") or {}
        comp = plan.get("compiler") or {}
        answer = (rec.get("answer") or "")
        insufficient = any(s in answer.lower() for s in
                           ("insufficient", "cannot answer", "not establish", "no evidence",
                            "does not contain", "unable to")) or (not ranked and not answer.strip())
        per_mode[mode] = {
            "error": rec["error"], "latency_s": rec["latency_s"], "phases": rec["phases"],
            "n_legend": len(retr.get("legend") or []), "evidence_count": retr.get("evidence_count"),
            "ranked_docs": ranked, "used_docs": used,
            "recall_at_k": round(recall_at_k(gold, ranked, k), 3) if not unsupported else None,
            "recall_used": round(recall_at_k(gold, used, k), 3) if not unsupported else None,
            "precision_at_k": round(precision_at_k(gold, ranked, k), 3) if not unsupported else None,
            "mrr": round(mrr(gold, ranked), 3) if not unsupported else None,
            "gold_hit": bool(gold & set(ranked)) if not unsupported else None,
            "scout": comp.get("scout"),
            "subquery_provenance": plan.get("subquery_provenance"),
            "queries": [{"id": x.get("id"), "type": x.get("type"), "role": x.get("role"),
                         "origin": x.get("origin"), "query": x.get("query")} for x in plan.get("queries") or []],
            "graph_fact_count": retr.get("graph_fact_count"), "wildcard": retr.get("wildcard"),
            "lane_sizes": retr.get("lane_sizes"), "funnel": retr.get("funnel"),
            "answer_head": answer[:280], "insufficient_declared": insufficient,
            "unsupported_expected": unsupported,
            # a hallucination on an unsupported query = it produced evidence/answer instead of declining
            "hallucinated_evidence": bool(unsupported and ranked and not insufficient),
        }
    return {"id": q.get("id"), "query": q["query"], "category": q.get("category"),
            "gold_doc_ids": sorted(gold), "unsupported": unsupported, "per_mode": per_mode}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(HERE / "gold_queries.json"))
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--modes", nargs="+", default=["FAST", "HYBRID", "GRAPH", "WILDCARD"])
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="only first N gold queries (0=all)")
    ap.add_argument("--filter", default="", help="only queries whose id/category contains this")
    a = ap.parse_args()
    gold = json.loads(pathlib.Path(a.gold).read_text())
    queries = gold["queries"] if isinstance(gold, dict) else gold
    if a.filter:
        queries = [q for q in queries if a.filter in (q.get("id", "") + q.get("category", ""))]
    if a.limit:
        queries = queries[:a.limit]
    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    t0 = time.time()
    for i, q in enumerate(queries, 1):
        r = evaluate_query(q, a.corpus, a.modes, k=a.k)
        results.append(r)
        # progress line to stdout
        hb = {m: (r["per_mode"][m].get("gold_hit") if not q.get("unsupported")
                  else (not r["per_mode"][m].get("hallucinated_evidence")))
              for m in r["per_mode"]}
        print(f"[{i}/{len(queries)}] {q['id']:18s} {q.get('category','')[:16]:16s} hit={hb}", flush=True)
    stamp = time.strftime("%Y-%m-%dT%H%M%S")
    artifact = outdir / f"qualification-{a.corpus}-{stamp}.json"
    artifact.write_text(json.dumps({"corpus": a.corpus, "modes": a.modes, "k": a.k,
                                    "n_queries": len(results), "wall_s": round(time.time() - t0, 1),
                                    "results": results}, indent=1))
    print(f"\nARTIFACT {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
