"""DOCUMENT-PROFILE-V1 step 4 — the profile vector projection (owner spec 2026-09-07).

One point per document in its OWN collection (`polymath_document_profiles_<embedding contract>`), never mixed
with the chunk points: named dense vectors `title`, `identity`, `theme` and named MULTIVECTORS `questions`,
`searches`, `theories`, `concepts`, `seealso` (one vector per atomic unit, MaxSim at query time). TERM is not a
dense vector. The compiler produces semantic units; this module produces vectors — from an injected `embed`
(production wires the embedder sidecar, tests wire a deterministic stub) and an injected Qdrant client.

`projection_key = hash(source_doc_hash, schema, prompt_version, embedding contract)` — change chunking and
nothing here moves; change the embedding model and only this re-runs. The projection receipt closes the chain:
content hash → input hash → raw response hash → compiled hash → PROJECTION HASH.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from typing import Any

PROJECTION_VERSION = "doc-profile-projection-v1"
COLLECTION_PREFIX = "polymath_document_profiles"
DENSE_SURFACES = ("title", "identity", "theme")
MULTI_SURFACES = ("questions", "searches", "theories", "concepts", "seealso")
#: normal answer retrieval prefetches these; `seealso` (and by default theories / concepts) belong to exploration
ANSWER_SURFACES = ("identity", "theme", "questions", "searches", "title")
EXPLORATION_SURFACES = ("seealso", "theories", "concepts")


def collection_name(embedding_contract_id: str) -> str:
    return f"{COLLECTION_PREFIX}_{embedding_contract_id}"


def point_id(doc_id: str) -> str:
    """Stable UUID per document (Qdrant ids are ints or UUIDs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"polymath:doc_profile:{doc_id}"))


def projection_key(*, source_doc_hash: str, schema_version: str, prompt_version: str, embedding_contract_id: str) -> str:
    return hashlib.sha256(json.dumps({"doc": source_doc_hash, "schema": schema_version, "prompt": prompt_version,
                                      "embedding": embedding_contract_id, "projection": PROJECTION_VERSION},
                                     sort_keys=True).encode()).hexdigest()


def vectors_config(dim: int):
    """Named dense + multivector config (qdrant ≥ 1.10; measured 1.13.4)."""
    from qdrant_client.http import models as qm
    cfg: dict[str, Any] = {s: qm.VectorParams(size=dim, distance=qm.Distance.COSINE) for s in DENSE_SURFACES}
    for s in MULTI_SURFACES:
        cfg[s] = qm.VectorParams(size=dim, distance=qm.Distance.COSINE,
                                 multivector_config=qm.MultiVectorConfig(comparator=qm.MultiVectorComparator.MAX_SIM))
    return cfg


def ensure_collection(client, name: str, dim: int) -> bool:
    """Create the profile collection when absent. Returns True when created."""
    if client.collection_exists(name):
        return False
    client.create_collection(collection_name=name, vectors_config=vectors_config(dim))
    return True


def texts_to_embed(title: str, representations: dict[str, Any]) -> list[tuple[str, int | None, str]]:
    """(surface, index-or-None, text) in a fixed order — the batch the embedder receives."""
    out: list[tuple[str, int | None, str]] = []
    if (title or "").strip():
        out.append(("title", None, title.strip()))
    for s in ("identity", "theme"):
        v = str(representations.get(s) or "").strip()
        if v:
            out.append((s, None, v))
    for s in MULTI_SURFACES:
        for i, item in enumerate(representations.get(s) or []):
            it = str(item or "").strip()
            if it:
                out.append((s, i, it))
    return out


def build_point_vectors(batch: list[tuple[str, int | None, str]], vectors: list[list[float]]) -> dict[str, Any]:
    """Named vectors for the point: str surfaces → one vector, list surfaces → a list of vectors (multivector)."""
    if len(batch) != len(vectors):
        raise ValueError(f"embedded {len(vectors)} vectors for {len(batch)} texts")
    named: dict[str, Any] = {}
    for (surface, idx, _text), vec in zip(batch, vectors):
        if idx is None:
            named[surface] = list(vec)
        else:
            named.setdefault(surface, []).append(list(vec))
    return named


def project_profile(client, *, embed: Callable[[list[str]], list[list[float]]], embedding_contract_id: str, dim: int,
                    doc_id: str, corpus_id: str, title: str, representations: dict[str, Any], payload_extra: dict | None = None,
                    source_doc_hash: str, schema_version: str, prompt_version: str, compiled_hash: str) -> dict[str, Any]:
    """Embed every atomic unit once and upsert the document's single multi-representation point. Returns the
    projection receipt (no vectors inside — counts, hashes, collection, point id)."""
    from qdrant_client.http import models as qm
    name = collection_name(embedding_contract_id)
    created = ensure_collection(client, name, dim)
    batch = texts_to_embed(title, representations)
    if not batch:
        raise ValueError("nothing to project: the profile has no embeddable surface")
    vectors = embed([t for _, _, t in batch])
    named = build_point_vectors(batch, vectors)
    pkey = projection_key(source_doc_hash=source_doc_hash, schema_version=schema_version,
                          prompt_version=prompt_version, embedding_contract_id=embedding_contract_id)
    payload = {"doc_id": doc_id, "corpus_id": corpus_id, "title": title, "schema_version": schema_version,
               "prompt_version": prompt_version, "embedding_contract": embedding_contract_id,
               "projection_key": pkey, "compiled_hash": compiled_hash, "source_doc_hash": source_doc_hash,
               "surfaces": {s: (len(v) if isinstance(v, list) and v and isinstance(v[0], list) else 1) for s, v in named.items()},
               **(payload_extra or {})}
    client.upsert(collection_name=name, points=[qm.PointStruct(id=point_id(doc_id), vector=named, payload=payload)], wait=True)
    counts = {s: (len(v) if isinstance(v[0], list) else 1) for s, v in named.items()}
    projection_hash = hashlib.sha256(json.dumps({"key": pkey, "point": point_id(doc_id), "counts": counts,
                                                 "texts": [t for _, _, t in batch]}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"projection": PROJECTION_VERSION, "collection": name, "created_collection": created, "point_id": point_id(doc_id),
            "projection_key": pkey, "projection_hash": projection_hash, "embedding_contract": embedding_contract_id,
            "dim": dim, "vectors": counts, "texts_embedded": len(batch)}


def has_required_vectors(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    """The projector's half of the readiness contract: identity + theme + at least one Q/SEARCH vector."""
    v = receipt.get("vectors") or {}
    missing = []
    if not v.get("identity"):
        missing.append("identity_vector")
    if not v.get("theme"):
        missing.append("theme_vector")
    if not (v.get("questions") or v.get("searches")):
        missing.append("query_hook_vector")
    return (not missing), missing
