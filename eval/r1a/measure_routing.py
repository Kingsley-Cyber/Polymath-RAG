"""R1A routing qualification: summary routes (doc + section) under the
frozen query set, current vs candidate representations.

A: current lexical document profile (score_profile over retrieval_profile)
B: current parent-summary lexical behavior (lexical_score over parent summary)
C: candidate DOCUMENT_RETRIEVAL_SUMMARY + qualified neural vectors
D: candidate SECTION_RETRIEVAL_SUMMARY + qualified neural vectors
+ global child control (neural child vectors) — recall safety only.

Metrics per level: Recall@1/3/5, MRR. MRR is evaluation only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

import psycopg  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from polymath_shared.retrieval import lexical_score, score_profile  # noqa: E402
from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT  # noqa: E402
from polymath_shared.projection_contracts import qdrant_collection_name  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"


def embed_query(q: str) -> list[float]:
    import httpx
    r = httpx.post("http://127.0.0.1:8742/infer",
                   json={"texts": [q], "representation_kind": "query"}, timeout=120)
    r.raise_for_status()
    return r.json()["vectors"][0]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def metrics_for(predictions: list[list[str]], gold: list[str]) -> dict:
    """predictions: ranked list of candidate ids per query; gold: target id."""
    ranks = []
    for pred, g in zip(predictions, gold):
        try:
            rank = pred.index(g) + 1
        except ValueError:
            rank = 10**9
        ranks.append(rank)
    def recall_at(k):
        return round(sum(1 for r in ranks if r <= k) / len(ranks), 3)
    mrr = round(sum(1.0 / r for r in ranks if r < 10**9) / len(ranks), 3)
    return {"R@1": recall_at(1), "R@3": recall_at(3), "R@5": recall_at(5), "MRR": mrr}


def main() -> int:
    frozen = json.loads(Path(ROOT / "eval" / "r1a" / "routing_queries.json").read_text())
    queries = frozen["queries"]

    conn = psycopg.connect(DSN)
    doc_of = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    target_doc_ids = [doc_of[q["doc"]] for q in queries]
    profiles = {r[0]: (r[1] or {}) for r in conn.execute(
        "SELECT doc_id, retrieval_profile FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    parent_doc = {r[0]: r[1] for r in conn.execute(
        """SELECT ch.chunk_id, d.source_name FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
           WHERE d.corpus_id=%s AND ch.tier='parent'""", (CORPUS,)).fetchall()}
    parent_summary = {r[0]: r[1] for r in conn.execute(
        """SELECT ch.chunk_id, ch.summary FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
           WHERE d.corpus_id=%s AND ch.tier='parent'""", (CORPUS,)).fetchall()}
    child_doc = {r[0]: r[1] for r in conn.execute(
        """SELECT ch.chunk_id, d.source_name FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
           WHERE d.corpus_id=%s AND ch.tier='child'""", (CORPUS,)).fetchall()}
    conn.close()

    # section-level gold: parent whose source_name == query doc
    target_parents = []
    for q in queries:
        parents = [p for p, d in parent_doc.items() if d == q["doc"]]
        target_parents.append(parents[0] if parents else "")

    # A: current lexical document profile
    a_preds = []
    for q in queries:
        ranked = sorted(
            ((doc_id, score_profile(q["query"], profiles.get(doc_id, {}))[0]) for doc_id in doc_of.values()),
            key=lambda x: (-x[1], x[0]))
        a_preds.append([d for d, _ in ranked])
    a = metrics_for(a_preds, target_doc_ids)

    # B: current parent-summary lexical
    b_preds = []
    for q in queries:
        ranked = sorted(
            ((p, lexical_score(q["query"], s)) for p, s in parent_summary.items()),
            key=lambda x: (-x[1], x[0]))
        b_preds.append([p for p, _ in ranked])
    b = metrics_for(b_preds, target_parents)

    # neural vectors for C / D / child control
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    collection = qdrant_collection_name(CORPUS, NEURAL_EMBED_CONTRACT.contract_id)
    points, _ = client.scroll(collection_name=collection, limit=500, with_payload=True, with_vectors=True)
    client.close()
    by_kind = {"routing_document_summary": {}, "routing_section_summary": {}, "routing_child": {}}
    for p in points:
        kind = p.payload.get("representation_kind")
        if kind in by_kind:
            by_kind[kind][p.id] = (p.payload, p.vector)

    c_preds, d_preds, child_preds = [], [], []
    qvecs = [embed_query(q["query"]) for q in queries]
    for qvec in qvecs:
        ranked_c = sorted(
            ((payload["doc_id"], cosine(qvec, vec)) for _, (payload, vec) in by_kind["routing_document_summary"].items()),
            key=lambda x: (-x[1], x[0]))
        c_preds.append([d for d, _ in ranked_c])
        ranked_d = sorted(
            ((payload["parent_id"], cosine(qvec, vec)) for _, (payload, vec) in by_kind["routing_section_summary"].items()),
            key=lambda x: (-x[1], x[0]))
        d_preds.append([p for p, _ in ranked_d])
        ranked_child = sorted(
            ((payload["doc_id"], cosine(qvec, vec)) for _, (payload, vec) in by_kind["routing_child"].items()),
            key=lambda x: (-x[1], x[0]))
        child_preds.append([d for d, _ in ranked_child])

    c = metrics_for(c_preds, target_doc_ids)
    d = metrics_for(d_preds, target_parents)
    child = metrics_for(child_preds, target_doc_ids)

    out = {
        "doc_routing_current_lexical_profile": a,
        "section_routing_current_parent_lexical": b,
        "doc_routing_candidate_neural": c,
        "section_routing_candidate_neural": d,
        "global_child_neural": child,
    }
    print(json.dumps(out, indent=1))
    (ROOT / "eval" / "r1a" / "routing_result.json").write_text(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
