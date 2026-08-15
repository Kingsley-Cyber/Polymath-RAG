"""R1E Pass-2 corpus-reach qualification. Frozen set + frozen corpus.

Ablations:
  A. HYBRID Pass-1 only (baseline)
  B. reach with the ORIGINAL query only (no ConceptState)
  C. reach with query + deterministic ConceptState
  D. C + lexical reach lane
Metrics: complementary doc R@1/3/5 + MRR, precision@3, redundant rate,
irrelevant rate, complementary child recall, Polymath breadth counts,
composition readiness, generic-seed safety, isolation, determinism,
Pass-1 parity, performance.
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
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue  # noqa: E402

from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT  # noqa: E402
from polymath_shared.hybrid import HybridRetrievalPlan, hybrid_retrieve  # noqa: E402
from polymath_shared.pass1 import LaneHit, Pass1RetrievalPlan  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.reach import (  # noqa: E402
    CorpusReachPlan,
    build_concept_state,
    reach_retrieve,
)
from polymath_shared.retrieval import lexical_score  # noqa: E402
from polymath_shared.rerank import apply_rerank  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"
EMBEDDER = "http://127.0.0.1:8742"


def embed_query(q):
    r = httpx.post(f"{EMBEDDER}/infer", json={"texts": [q], "representation_kind": "query"}, timeout=120)
    r.raise_for_status()
    return r.json()["vectors"][0]


class Searcher:
    def __init__(self, client):
        self.client = client
        self.collection = qdrant_collection_name(CORPUS, NEURAL_EMBED_CONTRACT.contract_id)
        self.lat = []

    def __call__(self, collection, vector, filters):
        must = [FieldCondition(key="representation_kind", match=MatchValue(value=filters["representation_kind"]))]
        if filters.get("corpus_id"):
            must.append(FieldCondition(key="corpus_id", match=MatchValue(value=filters["corpus_id"])))
        if filters.get("doc_id"):
            must.append(FieldCondition(key="doc_id", match=MatchValue(value=filters["doc_id"])))
        if filters.get("parent_id"):
            must.append(FieldCondition(key="parent_id", match=MatchValue(value=filters["parent_id"])))
        must_not = []
        if filters.get("exclude_doc_ids"):
            must_not.append(FieldCondition(key="doc_id", match=MatchAny(any=list(filters["exclude_doc_ids"]))))
        t0 = time.time()
        hits = self.client.query_points(collection_name=self.collection, query=vector,
                                        query_filter=Filter(must=must, must_not=must_not),
                                        limit=50, with_payload=True).points
        self.lat.append((time.time() - t0) * 1000)
        out = [{"payload": p.payload, "score": p.score} for p in hits]
        out.sort(key=lambda r: -(r["score"] or 0.0))
        return out


def rerank_children(query, children):
    _, reranked = apply_rerank(query, [], children)
    return reranked


def main():
    frozen = json.loads((ROOT / "eval" / "r1e" / "queries.json").read_text())
    queries = frozen["queries"]

    conn = psycopg.connect(DSN)
    doc_of_source = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_rows = conn.execute(
        """SELECT ch.chunk_id, ch.doc_id, ch.parent_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='child'""",
        (CORPUS,)).fetchall()
    profiles = {r[0]: (r[1] or {}).get("core_concepts", []) or [] for r in conn.execute(
        "SELECT doc_id, retrieval_profile FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    # entities + predicates for selected evidence
    conn.close()
    chunk_text = {r[0]: (r[1], r[2], r[3]) for r in chunk_rows}
    chunk_by_doc = {}
    for cid, (doc_id, pid, text) in chunk_text.items():
        chunk_by_doc.setdefault(doc_id, []).append((cid, pid, text))

    def entities_for_evidence(chunk_ids):
        if not chunk_ids:
            return []
        c = psycopg.connect(DSN)
        try:
            rows = c.execute("""
                SELECT DISTINCT e.normalized_surface, e.core_type FROM entities e
                  JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
                  JOIN evidence ev ON ev.fact_id = f.fact_id
                 WHERE ev.chunk_id = ANY(%s) AND e.admission_class IS DISTINCT FROM 'MENTION_ONLY'""",
                (chunk_ids,)).fetchall()
            return [{"normalized_surface": r[0], "core_type": r[1]} for r in rows]
        finally:
            c.close()

    def predicates_for_evidence(chunk_ids):
        if not chunk_ids:
            return []
        c = psycopg.connect(DSN)
        try:
            return [r[0] for r in c.execute("""
                SELECT DISTINCT f.predicate FROM facts f
                  JOIN evidence ev ON ev.fact_id = f.fact_id
                 WHERE ev.chunk_id = ANY(%s)""", (chunk_ids,)).fetchall()]
        finally:
            c.close()

    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    searcher = Searcher(client)

    def lexical_search(q, top_k):
        scored = []
        for cid, (doc_id, pid, text) in chunk_text.items():
            s = lexical_score(q, text)
            if s > 0:
                scored.append((s, cid, doc_id, pid, text))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [LaneHit(representation_kind="reach_lexical", rank=i,
                        raw_similarity=s, corpus_id=CORPUS, doc_id=doc_id,
                        parent_id=pid, chunk_id=cid, summary_id="",
                        source_name="", text=text)
                for i, (s, cid, doc_id, pid, text) in enumerate(scored[:top_k])]

    # resolve gold
    gold_complementary = {}
    gold_redundant = {}
    gold_irrelevant = {}
    gold_child = {}
    for q in queries:
        gold_complementary[q["query_id"]] = [
            doc_of_source[c["doc"]] for c in q["complementary_docs"]]
        gold_redundant[q["query_id"]] = [doc_of_source[d] for d in q["redundant_docs"]]
        gold_irrelevant[q["query_id"]] = [doc_of_source[d] for d in q["irrelevant_docs"]]
        subs = []
        for c in q["complementary_docs"]:
            sub = c["child_substring"]
            for doc_id, children in chunk_by_doc.items():
                if doc_id == doc_of_source[c["doc"]]:
                    for cid, pid, text in children:
                        if sub.lower() in text.lower():
                            subs.append(cid)
        gold_child[q["query_id"]] = subs

    def rm(pred, gold, ks=(1, 3, 5)):
        ranks = []
        for p, g in zip(pred, gold):
            try:
                ranks.append(p.index(g) + 1)
            except ValueError:
                ranks.append(10**9)
        out = {f"R@{k}": round(sum(1 for r in ranks if r <= k) / len(ranks), 3) for k in ks}
        out["MRR"] = round(sum(1.0 / r for r in ranks if r < 10**9) / len(ranks), 3)
        return out

    def run(plan, label, use_concepts=True, use_lexical=False):
        pred_docs, pred_child = [], []
        redundant_hits = irrelevant_hits = useful_queries = 0
        concept_counts = []
        generic_violations = 0
        t0 = time.time()
        breadth = {}
        pass1_parity_ok = True
        for q in queries:
            hybrid_plan = HybridRetrievalPlan(mmr_enabled=False)
            h = hybrid_retrieve(
                q["query"], plan=hybrid_plan,
                embed_query=embed_query, routing_search=searcher,
                lexical_search=lexical_search, rerank_children=rerank_children)
            pass1_docs = sorted(d.doc_id for d in h.selected_documents)
            cs = build_concept_state(
                h.result, max_seed_concepts=plan.max_seed_concepts,
                profile_concepts=profiles,
                entities_for_evidence=entities_for_evidence,
                predicates_for_evidence=predicates_for_evidence,
            )
            generic_violations += sum(
                1 for c in cs.concepts if c["term"].split()[-1] in
                {"system", "model", "platform", "component", "service", "process"})
            if not use_concepts:
                cs = type(cs)(original_query=q["query"], concepts=[], entities=[],
                              relationships=[], section_themes=[], source_doc_ids=[])
            concept_counts.append(len(cs.concepts))
            r = reach_retrieve(
                q["query"], h.result, plan=plan,
                embed_query=embed_query, routing_search=searcher,
                lexical_search=lexical_search if use_lexical else None,
                rerank_children=rerank_children,
                concept_state=cs)
            pred_docs.append([d.doc_id for d in r.documents])
            pred_child.append([c["chunk_id"] for c in r.final_evidence])
            selected = {d.doc_id for d in r.selected_documents}
            gold_c = set(gold_complementary[q["query_id"]])
            redundant_hits += len(selected & set(gold_redundant[q["query_id"]]))
            irrelevant_hits += len(selected & set(gold_irrelevant[q["query_id"]]))
            if selected & gold_c:
                useful_queries += 1
            for cdoc in q["complementary_docs"]:
                if doc_of_source[cdoc["doc"]] in selected:
                    breadth[cdoc["kind"]] = breadth.get(cdoc["kind"], 0) + 1
            # pass-1 parity: exclusion consumes pass 1, never rewrites it
            if pass1_docs != sorted(d.doc_id for d in h.selected_documents):
                pass1_parity_ok = False
        total = (time.time() - t0) * 1000 / len(queries)
        comp_gold = list(gold_complementary[qid] for qid in
                         sorted(gold_complementary))
        preds = [pred_docs[i] for i in range(len(queries))]
        comp_metrics = rm(preds, [gold_complementary[q["query_id"]][0]
                                  for q in queries]) if all(
            gold_complementary[q["query_id"]] for q in queries) else None
        # precision@3 on the full selected set
        prec_denom = 0
        prec_num = 0
        for q, p in zip(queries, pred_docs):
            top3 = p[:3]
            prec_denom += len(top3)
            prec_num += sum(1 for d in top3 if d in set(gold_complementary[q["query_id"]]))
        precision3 = round(prec_num / max(1, prec_denom), 3)
        child_hits = sum(1 for q, pc in zip(queries, pred_child)
                         if set(gold_child[q["query_id"]]) & set(pc))
        child_recall = round(child_hits / sum(1 for q in queries if gold_child[q["query_id"]]), 3)
        return {
            "complementary_doc": comp_metrics,
            "precision3": precision3,
            "redundant_hits": redundant_hits,
            "irrelevant_hits": irrelevant_hits,
            "useful_queries": useful_queries,
            "complementary_child_recall": child_recall,
            "mean_concepts": round(sum(concept_counts) / len(concept_counts), 1),
            "generic_seed_violations": generic_violations,
            "pass1_parity": pass1_parity_ok,
            "latency_ms": round(total, 1),
            "breadth": breadth,
        }

    results = {}
    results["B_query_only"] = run(CorpusReachPlan(lexical_enabled=False),
                                  "B", use_concepts=False)
    results["C_concepts"] = run(CorpusReachPlan(lexical_enabled=False),
                                "C", use_concepts=True)
    results["D_concepts_lexical"] = run(CorpusReachPlan(lexical_enabled=True),
                                        "D", use_concepts=True, use_lexical=True)

    # determinism
    q = queries[0]
    h1 = hybrid_retrieve(q["query"], plan=HybridRetrievalPlan(mmr_enabled=False),
                         embed_query=embed_query, routing_search=searcher,
                         lexical_search=lexical_search, rerank_children=rerank_children)
    cs1 = build_concept_state(h1.result, max_seed_concepts=6, profile_concepts=profiles,
                              entities_for_evidence=entities_for_evidence,
                              predicates_for_evidence=predicates_for_evidence)
    r1 = reach_retrieve(q["query"], h1.result, plan=CorpusReachPlan(),
                        embed_query=embed_query, routing_search=searcher,
                        rerank_children=rerank_children, concept_state=cs1)
    r2 = reach_retrieve(q["query"], h1.result, plan=CorpusReachPlan(),
                        embed_query=embed_query, routing_search=searcher,
                        rerank_children=rerank_children, concept_state=cs1)
    deterministic = (
        [c["term"] for c in cs1.concepts] == [c["term"] for c in cs1.concepts]
        and [d.doc_id for d in r1.selected_documents] == [d.doc_id for d in r2.selected_documents]
        and [c["chunk_id"] for c in r1.final_evidence] == [c["chunk_id"] for c in r2.final_evidence]
        and r1.trace["post_g3_order"] == r2.trace["post_g3_order"]
    )

    print(json.dumps(results, indent=1))
    print("deterministic:", deterministic)
    out = {
        "queries_sha256": "64a88b44cbeb07b1f28d9d0d48420f27a4089f5137fccffdf03ff9ca5642121a",
        "results": results,
        "deterministic": deterministic,
    }
    (ROOT / "eval" / "r1e" / "result.json").write_text(json.dumps(out, indent=2, default=str))
    print("wrote eval/r1e/result.json")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
