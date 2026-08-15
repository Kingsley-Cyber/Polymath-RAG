"""R1B Pass-1 retrieval qualification (frozen set, frozen corpus).

Metrics: document/section/child Recall@K + MRR; final-evidence
supporting-child recall; ablations A-F; hierarchy rescue accounting;
filter verification; cross-corpus isolation; determinism; latency.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import FieldCondition, Filter, MatchValue  # noqa: E402

from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT  # noqa: E402
from polymath_shared.pass1 import (  # noqa: E402
    Pass1RetrievalPlan,
    pass1_retrieve,
)
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.rerank import apply_rerank  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"
ISO_CORPUS = "i2-isolation-corpus"
EMBEDDER = "http://127.0.0.1:8742"


def embed_query(q: str) -> list[float]:
    r = httpx.post(f"{EMBEDDER}/infer", json={"texts": [q], "representation_kind": "query"}, timeout=120)
    r.raise_for_status()
    return r.json()["vectors"][0]


class Searcher:
    def __init__(self, client: QdrantClient):
        self.client = client
        self.lat = {"doc": [], "section": [], "child": [], "deep": []}
        self.collections: dict[str, str] = {}
        for cid in (CORPUS, ISO_CORPUS):
            self.collections[cid] = qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)

    def __call__(self, collection: str, vector: list[float], filters: dict) -> list[dict]:
        must = [FieldCondition(key="representation_kind", match=MatchValue(value=filters["representation_kind"]))]
        if filters.get("corpus_id"):
            must.append(FieldCondition(key="corpus_id", match=MatchValue(value=filters["corpus_id"])))
        if filters.get("doc_id"):
            must.append(FieldCondition(key="doc_id", match=MatchValue(value=filters["doc_id"])))
        if filters.get("parent_id"):
            must.append(FieldCondition(key="parent_id", match=MatchValue(value=filters["parent_id"])))
        kind = filters["representation_kind"]
        key = "doc" if kind == "routing_document_summary" else "section" if kind == "routing_section_summary" else "deep" if filters.get("parent_id") else "child"
        t0 = time.time()
        # collection="" means caller resolves: pick corpus collection(s)
        targets = [collection] if collection else list(self.collections.values())
        out = []
        for target in targets:
            hits = self.client.query_points(
                collection_name=target,
                query=vector,
                query_filter=Filter(must=must),
                limit=50,
                with_payload=True,
            ).points
            out.extend({"payload": p.payload, "score": p.score} for p in hits)
        self.lat[key].append((time.time() - t0) * 1000)
        out.sort(key=lambda r: -(r["score"] or 0.0))
        return out


def rerank_children(query: str, children: list[dict]) -> list[dict]:
    _, reranked = apply_rerank(query, [], children)
    return reranked


def recall_metrics(predicted: list[str], gold: list[str], ks=(1, 3, 5, 10)) -> dict:
    ranks = []
    for pred, g in zip(predicted, gold):
        try:
            ranks.append(pred.index(g) + 1)
        except ValueError:
            ranks.append(10**9)
    out = {}
    for k in ks:
        out[f"R@{k}"] = round(sum(1 for r in ranks if r <= k) / len(ranks), 3)
    out["MRR"] = round(sum(1.0 / r for r in ranks if r < 10**9) / len(ranks), 3)
    return out


def main() -> int:
    frozen = json.loads((ROOT / "eval" / "r1b" / "queries.json").read_text())
    queries = frozen["queries"]

    conn = psycopg.connect(DSN)
    doc_of_source = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_rows = conn.execute(
        """SELECT ch.chunk_id, ch.doc_id, ch.parent_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='child'""",
        (CORPUS,)).fetchall()
    conn.close()
    chunk_text = {r[0]: (r[1], r[2], r[3]) for r in chunk_rows}

    def gold_child(q):
        for cid, (doc_id, _pid, text) in chunk_text.items():
            if doc_id == doc_of_source[q["gold_doc"]] and q["gold_child_substring"].lower() in text.lower():
                return cid
        return None

    gold_docs = [doc_of_source[q["gold_doc"]] for q in queries]
    gold_children = [gold_child(q) for q in queries]
    missing = [q["query_id"] for q, g in zip(queries, gold_children) if g is None]
    if missing:
        print("UNRESOLVED GOLD:", missing)
        sys.exit(2)

    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    search = Searcher(client)

    def run_plan(plan, queries_list=queries):
        doc_preds, sec_preds, child_preds, final_evidence_hits = [], [], [], []
        arrivals = {"DOCUMENT_LED": 0, "SECTION_LED": 0, "GLOBAL_CHILD_RESCUE": 0, "MULTI_REPRESENTATION": 0}
        lat = {"total": []}
        for q in queries_list:
            t0 = time.time()
            res = pass1_retrieve(
                q["query"], plan=plan,
                embed_query=embed_query, routing_search=search,
                rerank_children=rerank_children if plan.rerank_enabled else None,
            )
            lat["total"].append((time.time() - t0) * 1000)
            doc_preds.append([d.doc_id for d in res.documents])
            sec_preds.append([s["parent_id"] for s in res.selected_sections])
            child_preds.append([h.chunk_id for h in res.global_child_lane])
            gold_child_id = gold_child(q)
            hit = any(c["chunk_id"] == gold_child_id for c in res.final_evidence)
            final_evidence_hits.append(hit)
            for c in res.final_evidence:
                arrivals[c.get("arrival", "DOCUMENT_LED")] += 1
        return doc_preds, sec_preds, child_preds, final_evidence_hits, arrivals, lat

    def report(plan, label):
        doc_preds, sec_preds, child_preds, fev, arrivals, lat = run_plan(plan)
        gold_sections = [next((pid for cid, (_, pid, _) in chunk_text.items() if cid == gc), "")
                         for gc in gold_children]
        doc_m = recall_metrics(doc_preds, gold_docs, (1, 3, 5))
        sec_m = recall_metrics(sec_preds, gold_sections, (1, 3, 5))
        child_m = recall_metrics(child_preds, gold_children, (1, 3, 5, 10))
        fev_recall = round(sum(fev) / len(fev), 3)
        total_lat = sorted(lat["total"])
        print(f"\n=== {label}")
        print(f"  DOC {doc_m}  SEC {sec_m}  CHILD {child_m}  final_evidence_supporting_recall={fev_recall}")
        print(f"  arrivals {arrivals}  total_lat_p50={total_lat[len(total_lat)//2]:.0f}ms p95={total_lat[int(len(total_lat)*0.95)]:.0f}ms")
        return {"doc": doc_m, "sec": sec_m, "child": child_m,
                "final_evidence_supporting_recall": fev_recall,
                "arrivals": arrivals,
                "total_lat_p50_ms": round(total_lat[len(total_lat)//2], 1),
                "total_lat_p95_ms": round(total_lat[int(len(total_lat)*0.95)], 1)}

    results = {}
    results["F_full"] = report(Pass1RetrievalPlan(), "F: hierarchy + global child + G3")
    results["A_document_only"] = report(
        Pass1RetrievalPlan(section_summary_enabled=False, global_child_enabled=False),
        "A: document summary only")
    results["B_section_only"] = report(
        Pass1RetrievalPlan(document_summary_enabled=False, global_child_enabled=False),
        "B: section summary only")
    results["C_child_only"] = report(
        Pass1RetrievalPlan(document_summary_enabled=False, section_summary_enabled=False),
        "C: global child only")
    results["D_hierarchy_no_rescue"] = report(
        Pass1RetrievalPlan(global_child_rescue_max=0),
        "D: hierarchy, no global child rescue")
    results["E_no_g3"] = report(
        Pass1RetrievalPlan(rerank_enabled=False),
        "E: hierarchy + global child, no G3")

    # determinism: two identical runs -> semantic equality
    plan = Pass1RetrievalPlan()
    a_preds = run_plan(plan)
    b_preds = run_plan(plan)
    deterministic = all(
        a_preds[i] == b_preds[i] for i in range(5)
    )
    print(f"\ndeterminism (lanes/docs/sections/children/final+arrivals+lat exempt): "
          f"{deterministic}")

    # filter verification: deepened children must belong to the selected
    # section (they came from filtered search; verify payload fields)
    plan = Pass1RetrievalPlan()
    t0 = time.time()
    res = pass1_retrieve(
        "What does zero trust abandon?", plan=plan,
        embed_query=embed_query, routing_search=search, rerank_children=rerank_children)
    filter_ok = all(
        c["doc_id"] in {d.doc_id for d in res.selected_documents}
        and c["parent_id"] in {s["parent_id"] for s in res.selected_sections}
        for c in res.final_evidence if c.get("arrival") == "SECTION_LED"
    )
    print(f"filter verification (deepened children within selected doc+section): {filter_ok}")

    # cross-corpus isolation
    iso_plan = Pass1RetrievalPlan(corpus_ids=(ISO_CORPUS,))
    iso_res = pass1_retrieve(
        "How does the system work?", plan=iso_plan,
        embed_query=embed_query, routing_search=search, rerank_children=rerank_children)
    iso_ok = all(
        (c.get("doc_id") or "") in set(doc_of_source.values()) or True  # payload corpus check below
        for c in iso_res.final_evidence
    ) and all(
        c.get("corpus_id", "") == "" for c in iso_res.final_evidence
    ) is False
    iso_evidence = iso_res.final_evidence
    iso_corpus_ok = all(
        (c.get("corpus_id") or "") == "" or True for c in iso_evidence
    )
    # authoritative check: iso corpus doc ids
    conn = psycopg.connect(DSN)
    iso_doc_ids = {r[0] for r in conn.execute(
        "SELECT doc_id FROM documents WHERE corpus_id=%s", (ISO_CORPUS,)).fetchall()}
    conn.close()
    iso_leak = [c for c in iso_evidence if c["doc_id"] not in iso_doc_ids]
    print(f"cross-corpus isolation: evidence={len(iso_evidence)} leaks={len(iso_leak)}")
    print(f"  filter_ok={filter_ok}")

    latency = {}
    for key, vals in search.lat.items():
        if vals:
            s = sorted(vals)
            latency[key] = {"p50_ms": round(s[len(s)//2], 1), "p95_ms": round(s[int(len(s)*0.95)], 1)}
    print("lane latency:", json.dumps(latency))

    out = {
        "queries_sha256": "0ec1b8724f7fbd712a2de660bbcbddf41905bb6a7bde595ef5b893cb40f9c83b",
        "ablations": results,
        "deterministic": deterministic,
        "filter_verification": filter_ok,
        "cross_corpus_isolation": {"leaks": len(iso_leak)},
        "lane_latency_ms": latency,
    }
    (ROOT / "eval" / "r1b" / "result.json").write_text(json.dumps(out, indent=2, default=str))
    print("wrote eval/r1b/result.json")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
