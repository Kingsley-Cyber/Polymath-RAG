"""Projection contracts (Phase F).

The invariant (PLAN Phase F):

    Postgres state survives projection loss;
    projection state never alters Postgres semantic truth.

Consequences, encoded here:

  - Projection identity is derived: projection_id = sha256(projection |
    entity_kind | source entity id | contract version). A projector
    never invents a semantic id; Neo4j receives fact_id, Qdrant
    receives chunk_id.
  - Projections are versioned by contract: a new embedding contract
    writes a NEW Qdrant collection, leaving the old one intact — the
    source facts never change.
  - Receipts are the commit point: a projector writes the external
    store first, then commits the projection receipt to Postgres in
    the stage transaction. A crash between the two leaves an orphan in
    the projection, which VERIFY_PROJECTIONS detects (acceptance test
    7) — never silent acceptance.

Embedding contracts: v1 is a deterministic hashed n-gram vector
(hash-embed-v1) — zero model, byte-stable, dimension fixed per
contract. The neural embedder sidecar replaces it in Phase G by
adding a contract id, not by changing this module's shape.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from polymath_shared.identity import content_hash

PROJECTION_QDRANT = "qdrant"
PROJECTION_NEO4J = "neo4j"

KIND_CHUNK = "chunk"
KIND_ENTITY = "entity"
KIND_FACT = "fact"
KIND_EVIDENCE = "evidence"

EMBEDDING_CONTRACTS: dict[str, dict[str, Any]] = {
    "hash-embed-v1": {"dim": 512, "description": "deterministic hashed 3-gram bag, zero model"},
}

# The active embedding contract. One id, versioned; changing it creates a
# new Qdrant collection version without touching source facts (gate 5).
EMBEDDING_CONTRACT = "hash-embed-v1"

QDRANT_COLLECTION_PREFIX = "polymath"
NEO4J_CONSTRAINT_FILE = "stores/neo4j/constraints/0001_uniqueness.cypher"


def projection_id(projection: str, entity_kind: str, source_id: str, contract_version: str) -> str:
    """The deterministic identity of one projected artifact."""
    return content_hash({
        "projection": projection,
        "kind": entity_kind,
        "source": source_id,
        "contract": contract_version,
    })


def receipt_hash(projection: str, entity_kind: str, source_id: str, contract_version: str) -> str:
    """Receipt identity = projection identity (same inputs, same key)."""
    return projection_id(projection, entity_kind, source_id, contract_version)


def qdrant_collection_name(corpus_id: str, contract_id: str) -> str:
    """Deterministic collection name. Corpus ids are namespaced by hash
    so exotic corpus names cannot collide; the contract id pins the
    embedding release."""
    corpus_hash = hashlib.sha256(corpus_id.encode("utf-8")).hexdigest()[:12]
    return f"{QDRANT_COLLECTION_PREFIX}_{corpus_hash}_{contract_id}"


_POINT_UUID_NAMESPACE = "polymath-qdrant-point-v1"


def qdrant_point_uuid(source_id: str) -> str:
    """Deterministic point id: uuid5 from the source chunk id. Qdrant 1.13
    accepts only unsigned-int or UUID point ids; the SOURCE identity
    (chunk_id) stays in the payload, and this uuid is re-derivable from
    it — the projection never invents identity, it encodes it."""
    import uuid

    return str(uuid.uuid5(uuid.UUID(int=0), f"{_POINT_UUID_NAMESPACE}:{source_id}"))


def hash_embed_v1(text: str) -> list[float]:
    """Deterministic embedding for the hash-embed-v1 contract.

    Hashed character 3-grams (case-folded, punctuation-stripped) into a
    fixed 512-dim vector, L2-normalized. Pure function: same text, same
    vector, byte for byte, on any machine. Not a semantic embedder —
    it exists so the projection layer has a real, versioned vector
    contract to exercise before the neural embedder lands in Phase G.
    """
    dim = EMBEDDING_CONTRACTS["hash-embed-v1"]["dim"]
    buckets = [0.0] * dim
    cleaned = re.sub(r"[^a-z0-9 ]", "", text.lower())
    grams = re.findall(r"(?=(\w{3}))", cleaned)
    for gram in grams:
        idx = int.from_bytes(hashlib.sha256(gram.encode("utf-8")).digest()[:4], "big") % dim
        buckets[idx] += 1.0
    norm = sum(v * v for v in buckets) ** 0.5
    if norm == 0.0:
        return buckets
    return [v / norm for v in buckets]


def embed(text: str, contract_id: str) -> list[float]:
    """Embed under the named contract. Unknown contracts raise — a new
    contract is an explicit versioning decision, not a fallback. A
    contract may register an `fn` callable for implementations defined
    outside this module (test contracts included)."""
    if contract_id not in EMBEDDING_CONTRACTS:
        raise ValueError(f"unknown embedding contract: {contract_id}")
    impl = EMBEDDING_CONTRACTS[contract_id].get("fn")
    if impl is not None:
        return impl(text)
    if contract_id == "hash-embed-v1":
        return hash_embed_v1(text)
    raise ValueError(f"contract {contract_id} registered but has no implementation")
