"""Embedding contracts (Phase G2): representation, not routing policy.

The contract freezes everything that changes a vector's meaning. Any
difference in any frozen field is a DIFFERENT contract — a model
revision, dimension, or normalization change can never silently mutate
an existing index (G2 gate 4). Backend location (MPS, CUDA, API) is
deliberately absent: physical execution lives outside retrieval
semantics (G2 gate 5).

representation_kind separates the lane semantics so document profiles,
parent summaries, and child evidence can never become "just vectors"
and interchangeable:

    document_profile  corpus-wide conceptual discovery
    parent_summary    topic/section localization
    child_chunk       precise evidence recall
    query             the query side of every lane

`hash-embed-v1` is retained PERMANENTLY as a zero-model deterministic
test contract for projection, reconstruction, fusion, and contract
migration tests without GPU/model variability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from polymath_shared.identity import content_hash

REPRESENTATION_KINDS = ("document_profile", "parent_summary", "child_chunk", "query")

DISTANCE_METRICS = ("cosine", "dot", "euclidean")
NORMALIZATIONS = ("l2", "none")


@dataclass(frozen=True)
class EmbeddingContract:
    """Frozen representation contract. Immutable: a change is a new id."""

    contract_version: str
    model_id: str
    model_revision: str
    dimension: int
    distance_metric: str
    normalization: str
    query_prefix: str = ""
    document_prefix: str = ""
    tokenization: str = "default"
    max_input_tokens: int = 512
    batch_limit: int = 64
    representation_kinds: tuple[str, ...] = field(default_factory=lambda: REPRESENTATION_KINDS)
    embed_fn: Callable[[str], list[float]] | None = None

    @property
    def contract_id(self) -> str:
        """Content-hash identity: any frozen-field change = new contract."""
        return "embed_" + content_hash({
            "version": self.contract_version,
            "model": self.model_id,
            "revision": self.model_revision,
            "dim": self.dimension,
            "distance": self.distance_metric,
            "normalization": self.normalization,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
            "tokenization": self.tokenization,
            "max_tokens": self.max_input_tokens,
            "batch": self.batch_limit,
            "kinds": list(self.representation_kinds),
        })[:16]

    def content_hash(self) -> str:
        return self.contract_id

    def embed(self, text: str, kind: str) -> list[float]:
        if kind not in self.representation_kinds:
            raise ValueError(f"representation kind {kind!r} not in contract {self.contract_id}")
        prefixed = text
        if self.query_prefix and kind == "query":
            prefixed = self.query_prefix + text
        elif self.document_prefix and kind in ("document_profile", "parent_summary", "child_chunk"):
            prefixed = self.document_prefix + text
        if self.embed_fn is None:
            raise ValueError(f"contract {self.contract_id} has no embed implementation")
        return self.embed_fn(prefixed)


def _hash_embed_fn(text: str) -> list[float]:
    from polymath_shared.projection_contracts import hash_embed_v1

    return hash_embed_v1(text)


# The permanent zero-model test contract (G2: never deleted).
HASH_EMBED_CONTRACT = EmbeddingContract(
    contract_version="1",
    model_id="none",
    model_revision="none",
    dimension=512,
    distance_metric="cosine",
    normalization="l2",
    tokenization="char-3gram",
    embed_fn=_hash_embed_fn,
)

# The neural contract: pinned model release. weights pin: the embedder
# sidecar manifest owns revision + sha256 verification; this contract
# records the SAME revision so index naming and sidecar identity cannot
# drift apart.
NEURAL_EMBED_CONTRACT = EmbeddingContract(
    contract_version="1",
    model_id="Qwen/Qwen3-Embedding-0.6B",
    model_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
    dimension=1024,
    distance_metric="cosine",
    normalization="l2",
    query_prefix="Instruct: Given a search query, retrieve relevant passages.\nQuery: ",
    document_prefix="",
    tokenization="sentence-transformers-default",
    max_input_tokens=8192,
    batch_limit=32,
    embed_fn=None,  # served by the embedder sidecar; see clients.EmbedderClient
)

CONTRACTS: dict[str, EmbeddingContract] = {
    HASH_EMBED_CONTRACT.contract_id: HASH_EMBED_CONTRACT,
    NEURAL_EMBED_CONTRACT.contract_id: NEURAL_EMBED_CONTRACT,
}

# Friendly ids -> contracts, for configuration and tests. A friendly id
# resolves to the contract whose derived id keys the index names.
SHORT_NAMES: dict[str, EmbeddingContract] = {
    "hash-embed-v1": HASH_EMBED_CONTRACT,
    "neural-embed-v1": NEURAL_EMBED_CONTRACT,
}

# The active embedding contract for new projections.
ACTIVE_CONTRACT_ID = "hash-embed-v1"


def active_contract() -> EmbeddingContract:
    """Resolve the active contract from settings (default hash-embed-v1).
    Accepts a friendly id or a derived contract id. An unknown id raises
    — a contract is an explicit versioning decision, never a fallback."""
    from polymath_shared.settings import get_settings

    contract_id = get_settings().stores.embedding_contract_id
    contract = SHORT_NAMES.get(contract_id) or CONTRACTS.get(contract_id)
    if contract is None:
        raise ValueError(f"unknown embedding contract: {contract_id}")
    return contract
