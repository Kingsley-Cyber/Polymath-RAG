"""E5B part 2 — frozen routing A/B.

A = existing qualified routing representation (retrieval-summary-v2,
production Qdrant points, UNTOUCHED).
B = retrieval-summary-v2 + bounded concept-inventory-v1 serialization
under routing-concept-enriched-v1, projected ONLY into the disposable
experimental collections routing_document_summary_concept_e5b /
routing_section_summary_concept_e5b with the frozen embedder pin.

No production collection is written. No summary/candidate/ranking/
budget/embedding policy is changed. Child evidence points, reranking,
and all Pass-1 logic are identical in both arms.
"""
from __future__ import annotations

import hashlib
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
from qdrant_client.models import (  # noqa: E402
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from polymath_shared.concept_inventory import (  # noqa: E402
    document_inventory,
    enriched_representation,
    section_inventory,
)
from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT  # noqa: E402
from polymath_shared.pass1 import Pass1RetrievalPlan, pass1_retrieve  # noqa: E402
from polymath_shared.projection_contracts import (  # noqa: E402
    qdrant_collection_name,
    qdrant_point_uuid,
)
from polymath_shared.retrieval_summaries import (  # noqa: E402
    DOC_SUMMARY_KIND,
    SECTION_SUMMARY_KIND,
)
from polymath_shared.rerank import apply_rerank  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "i2-qualification-corpus"
ISO_CORPUS = "i2-isolation-corpus"
ALL_CORPORA = (CORPUS, ISO_CORPUS)
EMBEDDER = "http://127.0.0.1:8742"
RERANKER = "http://127.0.0.1:8743"

E5B_DOC_COLLECTION = "routing_document_summary_concept_e5b"
E5B_SEC_COLLECTION = "routing_section_summary_concept_e5b"

REP_DOC = "routing_document_summary"
REP_SEC = "routing_section_summary"
REP_CHILD = "routing_child"


def embed_query(q: str) -> list[float]:
    r = httpx.post(f"{EMBEDDER}/infer",
                   json={"texts": [q], "representation_kind": "query"},
                   timeout=120)
    r.raise_for_status()
    return r.json()["vectors"][0]


def embed_docs(texts: list[str]) -> tuple[list[list[float]], float]:
    out: list[list[float]] = []
    total_ms = 0.0
    for i in range(0, len(texts), 32):
        t0 = time.time()
        r = httpx.post(f"{EMBEDDER}/infer",
                       json={"texts": texts[i:i + 32], "representation_kind": "child_chunk"},
                       timeout=300)
        r.raise_for_status()
        total_ms += (time.time() - t0) * 1000
        out.extend(r.json()["vectors"])
    return out, total_ms


class Searcher:
    """Kind-aware routing search with an experimental-collection override
    map. Child lanes always hit the production collections. Mirrors the
    R1B Searcher (both corpus collections searched when the caller
    passes an empty collection)."""

    def __init__(self, client: QdrantClient, prod: list[str],
                 override: dict[str, str] | None = None):
        self.client = client
        self.prod = prod
        self.override = override or {}
        self.lat = {"doc": [], "sec": [], "child": []}

    def __call__(self, collection: str, vector: list[float], filters: dict) -> list[dict]:
        kind = filters["representation_kind"]
        if kind in self.override:
            targets = [self.override[kind]]
        elif collection:
            targets = [collection]
        else:
            targets = self.prod
        must = [FieldCondition(key="representation_kind", match=MatchValue(value=kind))]
        for key in ("corpus_id", "doc_id", "parent_id"):
            if filters.get(key):
                must.append(FieldCondition(key=key, match=MatchValue(value=filters[key])))
        t0 = time.time()
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
        key = "doc" if kind == REP_DOC else "sec" if kind == REP_SEC else "child"
        self.lat[key].append((time.time() - t0) * 1000)
        out.sort(key=lambda r: -(r["score"] or 0.0))
        return out


def recall_metrics(predicted: list[str], gold: list[str], ks=(1, 3, 5)) -> dict:
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


def build_concept_points(client: QdrantClient, conn) -> dict:
    """Build the two experimental collections from authoritative
    retrieval_summaries rows + child chunks. Returns build stats."""
    doc_rows = conn.execute(
        """SELECT rs.summary_id, rs.summary_text, rs.corpus_id, rs.doc_id, rs.parent_id,
                  d.source_name
             FROM retrieval_summaries rs JOIN documents d ON d.doc_id = rs.doc_id
            WHERE rs.corpus_id = ANY(%s) AND rs.kind = %s ORDER BY rs.doc_id""",
        (list(ALL_CORPORA), DOC_SUMMARY_KIND)).fetchall()
    sec_rows = conn.execute(
        """SELECT rs.summary_id, rs.summary_text, rs.corpus_id, rs.doc_id, rs.parent_id,
                  d.source_name
             FROM retrieval_summaries rs JOIN documents d ON d.doc_id = rs.doc_id
            WHERE rs.corpus_id = ANY(%s) AND rs.kind = %s ORDER BY rs.doc_id, rs.parent_id""",
        (list(ALL_CORPORA), SECTION_SUMMARY_KIND)).fetchall()
    children = conn.execute(
        """SELECT c.chunk_id, c.doc_id, c.parent_id, c.text, c.summary
             FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
            WHERE d.corpus_id = ANY(%s) AND c.tier = 'child' ORDER BY c.chunk_index""",
        (list(ALL_CORPORA),)).fetchall()

    children_by_doc: dict[str, list[dict]] = {}
    children_by_sec: dict[str, list[dict]] = {}
    for chunk_id, doc_id, parent_id, text, summary in children:
        row = {"chunk_id": chunk_id, "text": text, "summary": summary or ""}
        children_by_doc.setdefault(doc_id, []).append(row)
        children_by_sec.setdefault(parent_id, []).append(row)

    stats = {"docs": len(doc_rows), "sections": len(sec_rows),
             "children": len(children), "extraction_ms_total": 0.0,
             "chars_baseline": 0, "chars_enriched": 0}

    def upsert(collection: str, points: list[PointStruct]) -> None:
        client.recreate_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=NEURAL_EMBED_CONTRACT.dimension,
                                        distance=Distance.COSINE))
        client.upsert(collection_name=collection, points=points, wait=True)

    doc_rows_enriched = []
    doc_texts: list[str] = []
    for row in doc_rows:
        summary_id, summary_text, corpus_id, doc_id, parent_id, source_name = row
        t0 = time.time()
        concepts = document_inventory(children_by_doc.get(doc_id, []))
        stats["extraction_ms_total"] += (time.time() - t0) * 1000
        enriched = enriched_representation(summary_text or "", concepts)
        stats["chars_baseline"] += len(summary_text or "")
        stats["chars_enriched"] += len(enriched)
        doc_texts.append(enriched)
        doc_rows_enriched.append((summary_id, corpus_id, doc_id, parent_id,
                                  source_name, enriched))
    doc_vectors, embed_ms_doc = embed_docs(doc_texts)
    doc_points = [
        PointStruct(
            id=qdrant_point_uuid(f"concept-e5b-v1:{summary_id}"),
            vector=vec,
            payload={
                "summary_id": summary_id,
                "chunk_id": None,
                "representation_kind": REP_DOC,
                "corpus_id": corpus_id,
                "doc_id": doc_id,
                "parent_id": parent_id or "",
                "source_name": source_name,
                "embedding_contract": NEURAL_EMBED_CONTRACT.contract_id,
                "representation": "routing-concept-enriched-v1",
                "text": enriched,
            })
        for (summary_id, corpus_id, doc_id, parent_id, source_name, enriched), vec
        in zip(doc_rows_enriched, doc_vectors)
    ]
    upsert(E5B_DOC_COLLECTION, doc_points)

    sec_rows_enriched = []
    sec_texts: list[str] = []
    for row in sec_rows:
        summary_id, summary_text, corpus_id, doc_id, parent_id, source_name = row
        t0 = time.time()
        concepts = section_inventory(children_by_sec.get(parent_id, []),
                                     section_summary=summary_text or "")
        stats["extraction_ms_total"] += (time.time() - t0) * 1000
        enriched = enriched_representation(summary_text or "", concepts)
        stats["chars_baseline"] += len(summary_text or "")
        stats["chars_enriched"] += len(enriched)
        sec_texts.append(enriched)
        sec_rows_enriched.append((summary_id, corpus_id, doc_id, parent_id,
                                  source_name, enriched))
    sec_vectors, embed_ms_sec = embed_docs(sec_texts)
    sec_points = [
        PointStruct(
            id=qdrant_point_uuid(f"concept-e5b-v1:{summary_id}"),
            vector=vec,
            payload={
                "summary_id": summary_id,
                "chunk_id": None,
                "representation_kind": REP_SEC,
                "corpus_id": corpus_id,
                "doc_id": doc_id,
                "parent_id": parent_id or "",
                "source_name": source_name,
                "embedding_contract": NEURAL_EMBED_CONTRACT.contract_id,
                "representation": "routing-concept-enriched-v1",
                "text": enriched,
            })
        for (summary_id, corpus_id, doc_id, parent_id, source_name, enriched), vec
        in zip(sec_rows_enriched, sec_vectors)
    ]
    upsert(E5B_SEC_COLLECTION, sec_points)

    # baseline-length embedding for comparison (same texts minus concepts)
    base_texts = [r[1] for r in doc_rows] + [r[1] for r in sec_rows]
    _, embed_ms_base = embed_docs(base_texts)
    stats["embed_ms_enriched"] = round(embed_ms_doc + embed_ms_sec, 1)
    stats["embed_ms_baseline"] = round(embed_ms_base, 1)
    stats["enriched_texts"] = len(doc_texts) + len(sec_texts)
    return stats


def main() -> int:
    frozen = json.loads((ROOT / "eval" / "r1b" / "queries.json").read_text())
    queries = frozen["queries"]
    frozen_sha = hashlib.sha256(
        (ROOT / "eval" / "r1b" / "queries.json").read_bytes()).hexdigest()
    print(f"frozen queries sha256: {frozen_sha}")

    conn = psycopg.connect(DSN)
    doc_of_source = {r[0]: r[1] for r in conn.execute(
        "SELECT source_name, doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
    chunk_rows = conn.execute(
        """SELECT ch.chunk_id, ch.doc_id, ch.parent_id, ch.text FROM chunks ch
           JOIN documents d ON d.doc_id=ch.doc_id WHERE d.corpus_id=%s AND ch.tier='child'""",
        (CORPUS,)).fetchall()
    chunk_text = {r[0]: (r[1], r[2], r[3]) for r in chunk_rows}

    def gold_child(q):
        for cid, (doc_id, _pid, text) in chunk_text.items():
            if doc_id == doc_of_source[q["gold_doc"]] and q["gold_child_substring"].lower() in text.lower():
                return cid
        return None

    gold_docs = [doc_of_source[q["gold_doc"]] for q in queries]
    gold_children = [gold_child(q) for q in queries]
    missing = [q["query_id"] for q, g in zip(queries, gold_children) if g is None]
    assert not missing, f"unresolved gold: {missing}"
    gold_sections = [next((pid for cid, (_, pid, _) in chunk_text.items() if cid == gc), "")
                     for gc in gold_children]

    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
    prod = [qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)
            for cid in ALL_CORPORA]
    print(f"production collections: {prod}")

    def run_plan(search) -> tuple[list[str], list[str], list[int], list[int]]:
        doc_preds, sec_preds, doc_ranks, sec_ranks = [], [], [], []
        for i, q in enumerate(queries):
            res = pass1_retrieve(
                q["query"], plan=Pass1RetrievalPlan(),
                embed_query=embed_query, routing_search=search,
                rerank_children=lambda query, children: apply_rerank(query, [], children)[1],
            )
            doc_preds.append([d.doc_id for d in res.documents])
            sec_preds.append([s["parent_id"] for s in res.selected_sections])
            try:
                doc_ranks.append([d.doc_id for d in res.documents].index(gold_docs[i]) + 1)
            except ValueError:
                doc_ranks.append(99)
            try:
                sec_ranks.append([s["parent_id"] for s in res.selected_sections].index(gold_sections[i]) + 1)
            except ValueError:
                sec_ranks.append(99)
        return doc_preds, sec_preds, doc_ranks, sec_ranks

    baseline_search = Searcher(client, prod)
    cand_search = Searcher(client, prod, override={
        REP_DOC: E5B_DOC_COLLECTION, REP_SEC: E5B_SEC_COLLECTION})

    # build experimental collections
    build_stats = build_concept_points(client, conn)
    conn.close()
    print("concept point build:", json.dumps(build_stats, default=str))

    # point-id determinism: rebuild and compare ids
    conn = psycopg.connect(DSN)
    ids_first = {c: sorted(p.id for p in client.scroll(
        collection_name=c, limit=1000, with_payload=False)[0])
        for c in (E5B_DOC_COLLECTION, E5B_SEC_COLLECTION)}
    build_concept_points(client, conn)
    conn.close()
    ids_second = {c: sorted(p.id for p in client.scroll(
        collection_name=c, limit=1000, with_payload=False)[0])
        for c in (E5B_DOC_COLLECTION, E5B_SEC_COLLECTION)}

    b_doc, b_sec, b_doc_ranks, b_sec_ranks = run_plan(baseline_search)
    c_doc, c_sec, c_doc_ranks, c_sec_ranks = run_plan(cand_search)

    # determinism: second candidate run
    c2_doc, c2_sec, _, _ = run_plan(cand_search)

    out = {
        "queries_sha256": frozen_sha,
        "production_collections": prod,
        "e5b_collections": [E5B_DOC_COLLECTION, E5B_SEC_COLLECTION],
        "build": build_stats,
        "doc": {
            "baseline": recall_metrics(b_doc, gold_docs),
            "candidate": recall_metrics(c_doc, gold_docs),
        },
        "sec": {
            "baseline": recall_metrics(b_sec, gold_sections),
            "candidate": recall_metrics(c_sec, gold_sections),
        },
        "query_level": [
            {
                "query_id": q["query_id"],
                "query": q["query"],
                "gold_doc": q["gold_doc"],
                "baseline_doc_rank": b_doc_ranks[i],
                "candidate_doc_rank": c_doc_ranks[i],
                "baseline_sec_rank": b_sec_ranks[i],
                "candidate_sec_rank": c_sec_ranks[i],
            }
            for i, q in enumerate(queries)
        ],
        "determinism": {
            "candidate_two_runs_identical": c_doc == c2_doc and c_sec == c2_sec,
            "point_ids_rebuild_identical": ids_first == ids_second,
        },
        "search_latency_ms": {
            "baseline": {k: round(sorted(v)[len(v) // 2], 1) for k, v in baseline_search.lat.items() if v},
            "candidate": {k: round(sorted(v)[len(v) // 2], 1) for k, v in cand_search.lat.items() if v},
        },
    }
    (ROOT / "eval" / "e5b" / "routing_ab.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({"doc": out["doc"], "sec": out["sec"], "determinism": out["determinism"]}, indent=1))
    print("wrote eval/e5b/routing_ab.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
