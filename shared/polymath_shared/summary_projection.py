"""SUMMARY-LAYER STEP 2: retrieval projections for derived intelligence.

Projects settled summary artifacts into Qdrant collections
(summary_documents, summary_parents, concept_families) and Neo4j
navigation relationships (HAS_SUMMARY, SUPPORTED_BY).

Rules (owner): summaries are NAVIGATION objects — they never create
knowledge and never link as facts. Point ids are content-derived
(idempotent upserts); embeddings come from an injected embed function
(production wires the embedder sidecar; tests wire a deterministic
fake). Replay after delete reproduces identical points.
"""
from __future__ import annotations

from polymath_shared.identity import content_hash


def point_id(*, corpus_id: str, artifact_id: str) -> str:
    """Stable UUID-shaped point id for Qdrant."""
    h = content_hash({"c": corpus_id, "a": artifact_id})
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


SUMMARY_COLLECTIONS = {
    "document": "summary_documents",
    "parent": "summary_parents",
    "concept": "concept_families",
}


def project_summary_points(qdrant_client, *, corpus_id: str,
                           items: list[dict], embed,
                           collection_for_type=None) -> list[str]:
    """items: [{artifact_id, artifact_hash, summary_type, text}].
    Upserts one point per item into its type collection. Returns the
    point ids in input order."""
    collection_for_type = collection_for_type or (
        lambda t: SUMMARY_COLLECTIONS.get(t))
    ids: list[str] = []
    for item in items:
        coll = collection_for_type(item["summary_type"])
        pid = point_id(corpus_id=corpus_id, artifact_id=item["artifact_id"])
        vec = embed(item["text"])
        qdrant_client.upsert(
            collection_name=coll,
            points=[{
                "id": pid,
                "vector": vec,
                "payload": {
                    "corpus_id": corpus_id,
                    "artifact_id": item["artifact_id"],
                    "artifact_hash": item["artifact_hash"],
                    "summary_type": item["summary_type"],
                },
            }],
        )
        ids.append(pid)
    return ids


NEO4J_NAVIGATION = [
    # (source_label, relation, target_label)
    ("Document", "HAS_SUMMARY", "DocumentSummary"),
    ("Concept", "SUPPORTED_BY", "DocumentSummary"),
    ("Fact", "SUPPORTED_BY", "Evidence"),
]


def project_navigation_edges(neo4j_session, *, corpus_id: str,
                             edges: list[dict]) -> int:
    """edges: [{source_label, source_key, target_label, target_key,
    relation}]. Deterministic MERGE on key properties only; never
    creates knowledge. Returns count written."""
    written = 0
    for edge in edges:
        sl = edge["source_label"]
        tl = edge["target_label"]
        rel = edge["relation"]
        if (sl, rel, tl) not in NEO4J_NAVIGATION:
            continue  # navigation-only vocabulary, fail-closed
        neo4j_session.run(
            f"MERGE (a:{sl} {{key:$sk}}) "
            f"MERGE (b:{tl} {{key:$tk}}) "
            f"MERGE (a)-[:{rel}]->(b)",
            sk=f"{corpus_id}:{edge['source_key']}",
            tk=f"{corpus_id}:{edge['target_key']}",
        )
        written += 1
    return written


def snapshot_projections(qdrant_client, collections: list[str],
                         neo4j_session, nav_query: str) -> dict:
    """Recovery snapshot: point ids + hashes per collection, plus
    relationship keys. Delete-and-replay must reproduce this exactly."""
    snap: dict = {}
    for coll in collections:
        points, _offset = qdrant_client.scroll(
            collection_name=coll, limit=10_000, with_payload=True)
        snap[coll] = sorted(
            (p["id"], p["payload"].get("artifact_hash"))
            for p in points)
    rels = [tuple(r.values()) for r in neo4j_session.run(nav_query)]
    snap["neo4j_navigation"] = sorted(rels)
    return snap
