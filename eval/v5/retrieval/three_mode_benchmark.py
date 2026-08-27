"""THREE-MODE-BENCHMARK-V1: same query set through VECTOR / HYBRID / GRAPH.

Stage J harness. Honest by construction:
  - one fixed query set (10 classes) per corpus;
  - every mode reads the SAME stores under the SAME embedding contract;
  - per-query x mode capture: rankings, ids, latency, route notes;
  - no ground truth exists yet => this measures BEHAVIOR, not accuracy;
    accuracy claims wait for a sealed judged set.

Usage:
  POLYMATH_PG_DSN=... .venv/bin/python \
    eval/v5/retrieval/three_mode_benchmark.py --corpus release-books-v1 \
      [--contract neural-embed-v1] [--k 10]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"

QUERY_SET = [
    # (query_id, class, query)
    ("q01", "exact_fact",
     "What did Paul Graziani do before founding MathWorks?"),
    ("q02", "identifier", "SOC analysts and Wazuh deployment"),
    ("q03", "procedure", "How to deploy Splunk on AWS?"),
    ("q04", "concept", "What is event-driven microservice communication?"),
    ("q05", "semantic_paraphrase",
     "keeping services reliable when everything is on fire"),
    ("q06", "broad_exploration", "distributed systems architecture patterns"),
    ("q07", "relationship",
     "How does Kubernetes relate to container orchestration patterns?"),
    ("q08", "cross_domain",
     "security monitoring lessons applicable to data engineering"),
    ("q09", "ambiguous", "release it"),
    ("q10", "no_answer", "the mating habits of Antarctic penguins"),
]


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for pos, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + pos + 1)
    return [i for i, _ in sorted(scores.items(),
                                 key=lambda kv: (-kv[1], kv[0]))]


def tokens(text: str) -> set[str]:
    import re
    return {w.lower() for w in re.findall(r"[a-z0-9_]+", text.lower())
            if len(w) > 2}


class Bench:
    def __init__(self, corpus: str, contract_short: str, k: int):
        self.corpus = corpus
        self.k = k
        from polymath_shared.embedding_contracts import SHORT_NAMES
        self.contract = SHORT_NAMES[contract_short]
        self.collection = None
        self.conn = psycopg.connect(DSN, connect_timeout=10)

    def qdrant(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(host="127.0.0.1", port=6334,
                                        timeout=15)
        return self._client

    _client = None

    def setup(self):
        from polymath_shared.projection_contracts import (
            qdrant_collection_name)
        name = qdrant_collection_name(self.corpus,
                                      self.contract.contract_id)
        info = self.qdrant().get_collection(name)
        self.collection = name
        print(f"collection {name}: {info.points_count} points")

    def embed_query(self, text: str) -> list[float]:
        c = self.contract
        prefixed = (c.query_prefix + text) if c.query_prefix else text
        if c.embed_fn is not None:
            return c.embed(prefixed, "query")
        from polymath_shared.clients import EmbedderClient
        cl = EmbedderClient()
        out = cl.embed([prefixed], "query")
        vectors = out.get("vectors") or out.get("embeddings")
        if not vectors:
            raise RuntimeError(f"embedder returned no vectors: "
                               f"{list(out)[:6]}")
        return vectors[0]

    def dense(self, text: str, kinds: list[str], limit: int):
        vec = self.embed_query(text)
        flt = {"must": [{"key": "representation_kind",
                         "match": {"any": kinds}},
                        {"key": "corpus_id",
                         "match": {"value": self.corpus}}]}
        res = self.qdrant().search(
            collection_name=self.collection, query_vector=vec,
            query_filter=flt, limit=limit, with_payload=True)
        return [{"id": (p.payload or {}).get("chunk_id")
                 or (p.payload or {}).get("summary_id") or str(p.id),
                 "kind": (p.payload or {}).get("representation_kind"),
                 "doc": (p.payload or {}).get("doc_id"),
                 "parent": (p.payload or {}).get("parent_id"),
                 "text": ((p.payload or {}).get("text") or "")[:200],
                 "score": p.score} for p in res]

    def children_rows(self):
        if self._children is None:
            rows = self.conn.execute(
                """SELECT c.chunk_id, c.doc_id, c.parent_id, c.text
                     FROM chunks c JOIN documents d ON d.doc_id=c.doc_id
                    WHERE d.corpus_id=%s AND c.tier='child'
                    ORDER BY c.chunk_index""", (self.corpus,)).fetchall()
            self._children = [
                {"id": r[0], "doc": r[1], "parent": r[2], "text": r[3]}
                for r in rows]
        return self._children

    _children = None

    def lexical(self, query: str, limit: int):
        qt = tokens(query)
        scored = []
        for row in self.children_rows():
            rt = tokens(row["text"])
            if not rt:
                continue
            overlap = len(qt & rt)
            if overlap:
                scored.append((overlap / (len(qt) or 1), row))
        scored.sort(key=lambda sr: (-sr[0], sr[1]["id"]))
        return [{**row, "score": s} for s, row in scored[:limit]]

    def graph_facts(self, doc_ids: list[str], limit: int):
        if not doc_ids:
            return []
        rows = self.conn.execute(
            """SELECT DISTINCT f.fact_id,
                      subj.normalized_surface, f.predicate,
                      obj.normalized_surface, ev.doc_id
                 FROM facts f
                 JOIN evidence ev ON ev.fact_id = f.fact_id
                 LEFT JOIN entities subj ON subj.entity_id = f.subject_id
                 LEFT JOIN entities obj ON obj.entity_id = f.object_id
                WHERE ev.doc_id = ANY(%s)
                ORDER BY f.fact_id LIMIT %s""",
            (doc_ids, limit)).fetchall()
        return [{"fact_id": r[0], "s": r[1], "p": r[2], "o": r[3],
                 "doc": r[4]} for r in rows]

    # ---- modes ---------------------------------------------------------
    def mode_vector(self, query: str):
        t0 = time.perf_counter()
        docs = self.dense(query, ["routing_document_summary"], self.k)
        parents = self.dense(query, ["routing_section_summary"], self.k)
        children = self.dense(query, ["routing_child", "child_chunk"],
                              self.k)
        ms = (time.perf_counter() - t0) * 1000
        fused = rrf([[h["id"] for h in children],
                     [h["id"] for h in parents]])
        return {
            "documents": [h["doc"] for h in docs][:self.k],
            "child_ids": [h["id"] for h in children][:self.k],
            "fused_evidence": fused[:self.k],
            "latency_ms": round(ms, 1),
        }

    def mode_hybrid(self, query: str):
        t0 = time.perf_counter()
        dense = self.dense(query, ["routing_child", "child_chunk"], self.k)
        lex = self.lexical(query, self.k)
        fused = rrf([[h["id"] for h in dense], [h["id"] for h in lex]])
        by_id = {h["id"]: h for h in dense + lex}
        docs = self.dense(query, ["routing_document_summary"], 5)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "documents": [h["doc"] for h in docs],
            "dense_ids": [h["id"] for h in dense],
            "lexical_ids": [h["id"] for h in lex],
            "fused_evidence": fused[:self.k],
            "evidence_text": [(by_id[i]["text"][:120] if i in by_id else "")
                              for i in fused[:3]],
            "latency_ms": round(ms, 1),
        }

    def mode_graph(self, query: str):
        t0 = time.perf_counter()
        hyb = self.mode_hybrid(query)
        seed_docs = list(dict.fromkeys(
            [h["doc"] for h in self.children_rows()[:0]] or []))
        # seeds = top fused child -> their docs
        by_id = {c["id"]: c for c in self.children_rows()}
        seed_docs = []
        for cid in hyb["fused_evidence"][:5]:
            row = by_id.get(cid)
            if row and row["doc"] not in seed_docs:
                seed_docs.append(row["doc"])
        facts = self.graph_facts(seed_docs, 20)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "seed_documents": seed_docs,
            "facts": facts,
            "hybrid_fused": hyb["fused_evidence"][:self.k],
            "latency_ms": round(ms, 1),
        }

    def close(self):
        self.conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="release-books-v1")
    ap.add_argument("--contract", default="neural-embed-v1")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    b = Bench(args.corpus, args.contract, args.k)
    b.setup()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    for qid, cls, query in QUERY_SET:
        row = {"query_id": qid, "class": cls, "query": query}
        for mode, fn in (("VECTOR", b.mode_vector),
                         ("HYBRID", b.mode_hybrid),
                         ("GRAPH", b.mode_graph)):
            try:
                row[mode] = fn(query)
            except Exception as exc:
                row[mode] = {"error": f"{type(exc).__name__}: {exc}"}
        results.append(row)
        v = row["VECTOR"].get("latency_ms")
        h = row["HYBRID"].get("latency_ms")
        g = row["GRAPH"].get("latency_ms")
        print(f"{qid} {cls:20s} v={v}ms h={h}ms g={g}ms")
    b.close()

    outdir = ROOT / "eval" / "v5" / "retrieval"
    outdir.mkdir(parents=True, exist_ok=True)
    jpath = outdir / f"THREE-MODE-BENCHMARK-{stamp}.json"
    jpath.write_text(json.dumps({
        "corpus": args.corpus, "contract": args.contract, "k": args.k,
        "captured_at": stamp, "results": results}, indent=1))

    lines = [
        "# THREE-MODE BENCHMARK V1 (behavioral, MEASURED)", "",
        f"- corpus: {args.corpus} · contract: {args.contract}",
        f"- captured: {stamp} · k={args.k}", "",
        "| query | class | VECTOR ms | HYBRID ms | GRAPH ms | "
        "top fused (HYBRID) |", "|---|---|---|---|---|---|",
    ]
    for row in results:
        h = row["HYBRID"]
        top = ",".join(h.get("fused_evidence", [])[:3])
        lines.append(
            f"| {row['query_id']} | {row['class']} | "
            f"{row['VECTOR'].get('latency_ms','ERR')} | "
            f"{h.get('latency_ms','ERR')} | "
            f"{row['GRAPH'].get('latency_ms','ERR')} | {top[:48]} |")
    lines += ["", "Full captures: " + jpath.name,
              "", "NOTE: behavioral measurements only — no accuracy claim "
              "without a sealed judged set."]
    (outdir / "THREE-MODE-BENCHMARK-V1.md").write_text("\n".join(lines) + "\n")
    print(f"written: {jpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
