"""DOCUMENT-SEMANTIC-INDEX-V1 slice S10 — the parent-map Qdrant projection contract.

Plan of record §9.2 (Qdrant projection), §14 (blue/green index migration), §36.6.
Migration authority RETRIEVAL-MIGRATION-DEPENDENCY-V1 §9.2, §14, §S6.

One point per eligible parent in its OWN contract-named collection
(`polymath_document_parent_maps_<embedding contract>`) — never mixed with the chunk
or profile collections, so re-embedding parent maps never invalidates other live
readers (§14 blue/green). Like the profile projector, this module is the deterministic
CONTRACT: it builds the collection name, the stable point id, the vector TEXT
(routing_signature + hooks + compact heading, §9.2) and the payload; the embedding and
the Qdrant upsert are INJECTED (`embed` + `client`), so production wires the embedder
sidecar + Qdrant while tests wire deterministic stubs. This module makes NO network
call itself.

Postgres remains the authority: a projected point is a rebuildable cache of an active
`document_parent_maps` row. `reconcile()` is the §14 gate — projected point count MUST
equal the authoritative active-map count for the contract.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from polymath_shared.document_profile.map_compiler import CompiledMap
from polymath_shared.document_profile.parent_skeleton import SkeletonManifest

PROJECTION_VERSION = "parent-map-projection-v1"
COLLECTION_PREFIX = "polymath_document_parent_maps"
VECTOR_NAME = "routing"
COMPACT_HEADING_MAX_CHARS = 80


def collection_name(embedding_contract_id: str) -> str:
    return f"{COLLECTION_PREFIX}_{embedding_contract_id}"


def point_id(doc_id: str, parent_id: str, map_contract: str) -> str:
    """Stable UUID per (doc, parent, contract) — one point per eligible parent."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:parent_map:{map_contract}:{doc_id}:{parent_id}"))


def search_parent_maps(client, collection: str, query_vec, doc_ids: Sequence[str], k: int = 24) -> list[dict]:
    """ONE routing-vector search filtered to the nominated docs (§17 performance rule:
    never one search per doc) → [{doc_id, parent_id, alias, score}] desc. Read-only — the
    reusable map-search contract the shadow canary and the live dual-read lane share."""
    from qdrant_client.http import models as qm
    if not doc_ids:
        return []
    flt = qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=list(doc_ids)))])
    res = client.query_points(collection, query=list(query_vec), using=VECTOR_NAME, query_filter=flt,
                              limit=k, with_payload=["doc_id", "parent_id", "alias"])
    return [{"doc_id": p.payload.get("doc_id"), "parent_id": p.payload.get("parent_id"),
             "alias": p.payload.get("alias"), "score": p.score} for p in res.points]


def compact_heading(heading_path: Sequence[str], *, max_chars: int = COMPACT_HEADING_MAX_CHARS) -> str:
    return " › ".join(str(h) for h in heading_path if str(h).strip())[:max_chars]


def vector_text(routing_signature: str, hooks: Sequence[str], heading_path: Sequence[str]) -> str:
    """The text embedded for one parent's routing point (§9.2): the compiled routing
    signature, its hooks, and a compact heading — deterministic, order-stable."""
    parts = [str(routing_signature or "").strip()]
    if hooks:
        joined = "; ".join(h.strip() for h in hooks if str(h).strip())
        if joined:
            parts.append(joined)
    ch = compact_heading(heading_path)
    if ch:
        parts.append(ch)
    return " | ".join(p for p in parts if p)


def projection_key(*, map_hash: str, map_contract: str, embedding_contract_id: str) -> str:
    """Change the embedding model and only this re-runs; change the map content
    (map_hash) and the point moves. Chunking changes do not move it."""
    return hashlib.sha256(json.dumps(
        {"map_hash": map_hash, "map_contract": map_contract,
         "embedding": embedding_contract_id, "projection": PROJECTION_VERSION},
        sort_keys=True).encode()).hexdigest()


def build_payload(*, doc_id: str, parent_id: str, corpus_id: str | None, alias: str,
                  heading_path: Sequence[str], ordinal: int, map_contract: str, map_hash: str,
                  source_text_hash: str | None, embedding_contract_id: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "parent_id": parent_id,
        "corpus_id": corpus_id,
        "alias": alias,
        "heading_path": list(heading_path),
        "parent_ordinal": ordinal,
        "map_contract": map_contract,
        "map_hash": map_hash,
        "source_text_hash": source_text_hash,
        "embedding_contract": embedding_contract_id,
        "projection_key": projection_key(map_hash=map_hash, map_contract=map_contract,
                                          embedding_contract_id=embedding_contract_id),
    }


def vectors_config(dim: int):
    from qdrant_client.http import models as qm
    return {VECTOR_NAME: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)}


def ensure_collection(client, name: str, dim: int) -> bool:
    """Create the contract-named parent-map collection when absent (§14: additive,
    never mutate the source/summary collections in place). Returns True when created."""
    if client.collection_exists(name):
        return False
    client.create_collection(collection_name=name, vectors_config=vectors_config(dim))
    return True


def texts_to_embed(maps: Sequence[CompiledMap], manifest: SkeletonManifest) -> list[tuple[str, str]]:
    """(alias, vector_text) for each map with a known skeleton, in map order — the
    batch the embedder receives. A map whose alias is not in the manifest is skipped
    (it can never have been produced against this manifest)."""
    by_alias = {s.alias: s for s in manifest.skeletons}
    out: list[tuple[str, str]] = []
    for m in maps:
        sk = by_alias.get(m.alias)
        if sk is None:
            continue
        out.append((m.alias, vector_text(m.routing_signature, m.semantic_hooks, sk.heading_path)))
    return out


def project_parent_maps(
    client, *, embed: Callable[[list[str]], list[list[float]]], embedding_contract_id: str, dim: int,
    doc_id: str, corpus_id: str | None, maps: Sequence[CompiledMap], manifest: SkeletonManifest,
    map_contract: str,
) -> dict[str, Any]:
    """Embed each parent's routing text once and upsert one point per map. Returns the
    projection receipt (no vectors inside — counts, hashes, collection, point ids)."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    created = ensure_collection(client, name, dim)
    by_alias = {s.alias: s for s in manifest.skeletons}
    batch = texts_to_embed(maps, manifest)
    if not batch:
        return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created,
                "points": 0, "point_ids": [], "projection_hash": hashlib.sha256(b"").hexdigest(),
                "embedding_contract": embedding_contract_id, "map_contract": map_contract}
    vectors = embed([t for _a, t in batch])
    if len(vectors) != len(batch):
        raise ValueError(f"embedded {len(vectors)} vectors for {len(batch)} texts")
    maps_by_alias = {m.alias: m for m in maps}
    points = []
    point_ids: list[str] = []
    for (alias, _text), vec in zip(batch, vectors):
        m = maps_by_alias[alias]
        sk = by_alias[alias]
        pid = point_id(doc_id, m.parent_id, map_contract)
        point_ids.append(pid)
        payload = build_payload(doc_id=doc_id, parent_id=m.parent_id, corpus_id=corpus_id, alias=alias,
                                heading_path=sk.heading_path, ordinal=sk.ordinal, map_contract=map_contract,
                                map_hash=m.map_hash, source_text_hash=sk.text_hash,
                                embedding_contract_id=embedding_contract_id)
        points.append(qm.PointStruct(id=pid, vector={VECTOR_NAME: list(vec)}, payload=payload))
    client.upsert(collection_name=name, points=points, wait=True)
    projection_hash = hashlib.sha256(json.dumps(
        {"collection": name, "map_contract": map_contract,
         "points": sorted((point_id(doc_id, maps_by_alias[a].parent_id, map_contract), maps_by_alias[a].map_hash)
                          for a, _t in batch)},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created,
            "points": len(points), "point_ids": point_ids, "projection_hash": projection_hash,
            "embedding_contract": embedding_contract_id, "map_contract": map_contract,
            "texts_embedded": len(batch)}


def reconcile(*, active_map_count: int, projected_point_count: int) -> dict[str, Any]:
    """The §14 projection gate: the authoritative active-map count MUST equal the
    projected point count for the contract. A mismatch (a stale receipt masking a
    missing point, or an orphan point) fails the gate."""
    delta = projected_point_count - active_map_count
    return {"ok": delta == 0, "active_maps": active_map_count,
            "projected_points": projected_point_count, "delta": delta}
