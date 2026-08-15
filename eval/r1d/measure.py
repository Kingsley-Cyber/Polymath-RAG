"""R1D HYBRID qualification: FAST baseline vs +lexical vs +MMR vs FULL,
lexical contribution classification, diversity metrics, composition
readiness, isolation, determinism, performance. Frozen query set.
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
from polymath_shared.hybrid import (  # noqa: E402
    ARRIVAL_LEXICAL_RESCUE,
    HybridRetrievalPlan,
    MMR_LAMBDA_GRID,
    hybrid_retrieve,
)
from polymath_shared.pass1 import Pass1RetrievalPlan, pass1_retrieve  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.retrieval import lexical_score  # noqa: E402
from polymath_shared.rerank import apply_rerank  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"
ISO_CORPUS = "i2-isolation-corpus"
EMBEDDER = "http://127.0.0.1:8742"


def embed_query(q):
    r = httpx.post(f"{EMBEDDER}/infer", json={"texts": [q], "representation_kind": "query"}, timeout=120)
    r.raise_for_status()
    return r.json()["vectors"][0]


class Searcher:
    def __init__(self, client):
        self.client = client
        self.lat = {"doc": [], "section": [], "child": [], "deep": []}
        self.collections = {}
        for cid in (CORPUS, ISO_CORPUS):
            self.collections[cid] = qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)

    def __call__(self, collection, vector, filters):
        must = [FieldCondition(key="representation_kind", match=MatchValue(value=filters["representation_kind"]))]
        if filters.get("corpus_id"):
            must.append(FieldCondition(key="corpus_id", match=MatchValue(value=filters["corpus_id"])))
        if filters.get("doc_id"):
            must.append(FieldCondition(key="doc_id", match=MatchValue(value=filters["doc_id"])))
        if filters.get("parent_id"):
            must.append(FieldCondition(key="parent_id", match=MatchValue(value=filters["parent_id"])))
        key = "doc" if filters["representation_kind"] == "routing_document_summary" else "deep" if filters.get("parent_id") else "child" if filters["representation_kind"] == "routing_child" else "section"
        t0 = time.time()
        out = []
        targets = [collection] if collection else list(self.collections.values())
        for target in targets:
            hits = self.client.query_points(collection_name=target, query=vector,
                                            query_filter=Filter(must=must), limit=50,
                                            with_payload=True, with_vectors=(filters["representation_kind"] == "routing_document_summary")).points
            out.extend({"payload": p.payload, "score": p.score,
                        "vector": p.vector if filters["representation_kind"] == "routing_document_summary" else None}
                       for p in hits)
        self.lat[key].append((time.time() - t0) * 1000)
        out.sort(key=lambda r: -(r["score"] or 0.0))
        return out


def summary_vectors(query, doc_ids):
    """Qualified DOCUMENT_RETRIEVAL_SUMMARY vectors for MMR similarity."""
    searcher = summary_vectors.searcher
    out = {}
    for did in doc_ids:
        rows = searcher("", [0.0] * 1024, {
            "representation_kind": "routing_document_summary",
            "corpus_id": CORPUS,
            "doc_id": did,
        })
        if rows and rows[0].get("vector"):
            out[did] = rows[0]["vector"]
    return out


def rerank_children(query, children):
    _, reranked = apply_rerank(query, [], children)
    return reranked


def main():
    frozen = json.loads((ROOT / "eval" / "r1d" / "queries.json").read_text())
    queries = frozen["queries"]

    conn = psycopg.connect(DSN)
    doc_of_source = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_rows = conn.execute(
        """SELECT ch.chunk_id, ch.doc_id, ch.parent_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='child'""",
        (CORPUS,)).fetchall()
    iso_doc_ids = {r[0] for r in conn.execute(
        "SELECT doc_id FROM documents WHERE corpus_id=%s", (ISO_CORPUS,)).fetchall()}
    conn.close()
    chunk_text = {r[0]: (r[1], r[2], r[3]) for r in chunk_rows}

    def gold_child(q):
        for cid, (doc_id, _p, text) in chunk_text.items():
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
    searcher = Searcher(client)
    summary_vectors.searcher = searcher

    def lexical_search(query, top_k):
        rows = [{"chunk_id": cid, "doc_id": d, "parent_id": p, "text": t}
                for cid, (d, p, t) in chunk_text.items()]
        scored = [(r, lexical_score(query, r["text"])) for r in rows]
        scored = [s for s in scored if s[1] > 0]
        scored.sort(key=lambda s: (-s[1], s[0]["chunk_id"]))
        from polymath_shared.pass1 import LaneHit
        return [LaneHit(
            representation_kind="child_lexical", rank=i,
            raw_similarity=s[1], corpus_id=CORPUS, doc_id=s[0]["doc_id"],
            parent_id=s[0]["parent_id"], chunk_id=s[0]["chunk_id"],
            summary_id="", source_name="", text=s[0]["text"],
        ) for i, s in enumerate(scored[:top_k])]

    def metrics(pred_docs, pred_secs, pred_children, fev, gold_docs, gold_secs, gold_children):
        def rm(pred, gold, ks=(1, 3, 5, 10)):
            ranks = []
            for p, g in zip(pred, gold):
                try:
                    ranks.append(p.index(g) + 1)
                except ValueError:
                    ranks.append(10**9)
            out = {f"R@{k}": round(sum(1 for r in ranks if r <= k) / len(ranks), 3) for k in ks}
            out["MRR"] = round(sum(1.0 / r for r in ranks if r < 10**9) / len(ranks), 3)
            return out
        return {
            "doc": rm(pred_docs, gold_docs, (1, 3, 5)),
            "section": rm(pred_secs, gold_secs, (1, 3, 5)),
            "child": rm(pred_children, gold_children, (1, 3, 5, 10)),
            "final_evidence_recall": round(sum(fev) / len(fev), 3),
        }

    def run_fast():
        pred_docs, pred_secs, pred_child, fev = [], [], [], []
        for q in queries:
            res = pass1_retrieve(
                q["query"], plan=Pass1RetrievalPlan(),
                embed_query=embed_query, routing_search=searcher,
                rerank_children=rerank_children)
            pred_docs.append([d.doc_id for d in res.documents])
            pred_secs.append([s["parent_id"] for s in res.selected_sections])
            pred_child.append([h.chunk_id for h in res.global_child_lane])
            gc = gold_child(q)
            fev.append(any(c["chunk_id"] == gc for c in res.final_evidence))
        return pred_docs, pred_secs, pred_child, fev

    def run_hybrid(plan, label, gold_sections_arg):
        pred_docs, pred_secs, pred_child, fev = [], [], [], []
        arrivals = {"LEXICAL_RESCUE": 0, "GLOBAL_CHILD_RESCUE": 0, "MULTI_REPRESENTATION": 0}
        lexical_only_children = neural_only_children = overlap = 0
        t0 = time.time()
        for q in queries:
            res = hybrid_retrieve(
                q["query"], plan=plan,
                embed_query=embed_query, routing_search=searcher,
                lexical_search=lexical_search if plan.lexical_enabled else None,
                rerank_children=rerank_children if plan.rerank_enabled else None,
                summary_vectors=summary_vectors if plan.mmr_enabled else None,
            )
            pred_docs.append([d.doc_id for d in res.documents])
            pred_secs.append([s["parent_id"] for s in res.selected_sections])
            pred_child.append([h.chunk_id for h in res.result.global_child_lane])
            gc = gold_child(q)
            fev.append(any(c["chunk_id"] == gc for c in res.final_evidence))
            for c in res.final_evidence:
                arrivals[c.get("arrival", "")] = arrivals.get(c.get("arrival", ""), 0) + 1
            if plan.lexical_enabled:
                lex_ids = {h.chunk_id for h in res.lexical_lane}
                neural_ids = {h.chunk_id for h in res.result.global_child_lane}
                if gc in lex_ids and gc not in neural_ids:
                    lexical_only_children += 1
                elif gc in neural_ids and gc not in lex_ids:
                    neural_only_children += 1
                elif gc in lex_ids and gc in neural_ids:
                    overlap += 1
        total = (time.time() - t0) * 1000 / len(queries)
        return metrics(pred_docs, pred_secs, pred_child, fev, gold_docs,
                       gold_sections_arg, gold_children), arrivals, total, {
            "lexical_only_children": lexical_only_children,
            "neural_only_children": neural_only_children,
            "overlap": overlap,
        }

    results = {}
    a_docs, a_secs, a_child, a_fev = run_fast()
    gold_sections = [next((p for cid, (d, p, _) in chunk_text.items() if cid == gc), "")
                     for gc in gold_children]
    gold_sections_arg = gold_sections
    results["A_fast"] = metrics(a_docs, a_secs, a_child, a_fev, gold_docs, gold_sections, gold_children)

    results["B_lexical"], arr_b, lat_b, contrib_b = run_hybrid(
        HybridRetrievalPlan(mmr_enabled=False), "B", gold_sections)
    results["B_arrivals"] = arr_b
    results["B_lexical_contribution"] = contrib_b
    results["B_latency_ms"] = round(lat_b, 1)

    results["C_mmr_no_lexical"] = {}
    for lam in MMR_LAMBDA_GRID:
        m, _, _, _ = run_hybrid(
            HybridRetrievalPlan(lexical_enabled=False, mmr_enabled=True, mmr_lambda=lam),
            f"C_l{lam}", gold_sections)
        results["C_mmr_no_lexical"][str(lam)] = m

    results["D_full"] = {}
    for lam in MMR_LAMBDA_GRID:
        m, arr_d, lat_d, contrib_d = run_hybrid(
            HybridRetrievalPlan(mmr_enabled=True, mmr_lambda=lam), f"D_l{lam}", gold_sections)
        results["D_full"][str(lam)] = {"metrics": m, "arrivals": arr_d,
                                       "latency_ms": round(lat_d, 1),
                                       "contribution": contrib_d}

    # composition readiness: multi-doc gold queries — do both docs appear?
    comp = {}
    for q in queries:
        if "gold_docs_extra" not in q:
            continue
        plan = HybridRetrievalPlan(mmr_enabled=False)
        res = hybrid_retrieve(q["query"], plan=plan, embed_query=embed_query,
                              routing_search=searcher, lexical_search=lexical_search,
                              rerank_children=rerank_children)
        selected = {d.doc_id for d in res.selected_documents}
        comp[q["query_id"]] = {
            "required_docs": [doc_of_source[x] for x in [q["gold_doc"], *q["gold_docs_extra"]]],
            "selected": sorted(selected),
            "all_required": all(doc_of_source[x] in selected for x in [q["gold_doc"], *q["gold_docs_extra"]]),
            "evidence_docs": sorted({c["doc_id"] for c in res.final_evidence}),
        }

    # determinism + isolation
    plan = HybridRetrievalPlan(mmr_enabled=True, mmr_lambda=0.8)
    d1 = hybrid_retrieve("What is STRIDE used for in threat modeling?", plan=plan,
                         embed_query=embed_query, routing_search=searcher,
                         lexical_search=lexical_search, rerank_children=rerank_children,
                         summary_vectors=summary_vectors)
    d2 = hybrid_retrieve("What is STRIDE used for in threat modeling?", plan=plan,
                         embed_query=embed_query, routing_search=searcher,
                         lexical_search=lexical_search, rerank_children=rerank_children,
                         summary_vectors=summary_vectors)
    deterministic = (
        [x.doc_id for x in d1.selected_documents] == [x.doc_id for x in d2.selected_documents]
        and [c["chunk_id"] for c in d1.final_evidence] == [c["chunk_id"] for c in d2.final_evidence]
        and d1.trace["post_g3_order"] == d2.trace["post_g3_order"]
    )
    iso_plan = HybridRetrievalPlan(corpus_ids=(ISO_CORPUS,))
    iso = hybrid_retrieve("How does the system work?", plan=iso_plan,
                          embed_query=embed_query, routing_search=searcher,
                          lexical_search=lambda q, k: [], rerank_children=rerank_children)
    iso_leaks = [c for c in iso.final_evidence if c["doc_id"] not in iso_doc_ids]

    print(json.dumps({
        "A_fast": results["A_fast"],
        "B_lexical": results["B_lexical"],
        "B_arrivals": arr_b,
        "B_contribution": contrib_b,
        "C_mmr_no_lexical": results["C_mmr_no_lexical"],
        "D_full": {k: {kk: vv for kk, vv in v.items() if kk != "contribution"}
                   for k, v in results["D_full"].items()},
        "composition_readiness": comp,
        "deterministic": deterministic,
        "iso_leaks": len(iso_leaks),
    }, indent=1))
    out = {
        "queries_sha256": "c91ab40c5069e4c85dc6d6f5ae54b7764785b0358c5fae62517d6f8fa516512e",
        "results": results,
        "composition_readiness": comp,
        "deterministic": deterministic,
        "iso_leaks": len(iso_leaks),
    }
    (ROOT / "eval" / "r1d" / "result.json").write_text(json.dumps(out, indent=2, default=str))
    print("wrote eval/r1d/result.json")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
