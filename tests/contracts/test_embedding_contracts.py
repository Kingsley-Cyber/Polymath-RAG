"""G2 embedding-contract gates (no stores needed).

Gate 4: changing any frozen field — model revision, dimension,
preprocessing, normalization — yields a NEW contract id, never an
in-place mutation of an existing index.
Gate 5: the contract carries no backend location; physical execution
lives outside retrieval semantics.
Gate: hash-embed-v1 is permanent — the zero-model deterministic test
contract is never deleted when the neural embedder lands.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.embedding_contracts import (  # noqa: E402
    CONTRACTS,
    HASH_EMBED_CONTRACT,
    NEURAL_EMBED_CONTRACT,
    EmbeddingContract,
)


def test_revision_change_is_a_new_contract() -> None:
    a = NEURAL_EMBED_CONTRACT
    b = replace(a, model_revision="40ec419335d09393f298636f471328b722c6da9e")
    assert a.contract_id != b.contract_id


def test_dimension_change_is_a_new_contract() -> None:
    a = NEURAL_EMBED_CONTRACT
    b = replace(a, dimension=768)
    assert a.contract_id != b.contract_id


def test_preprocessing_change_is_a_new_contract() -> None:
    a = NEURAL_EMBED_CONTRACT
    b = replace(a, query_prefix="search: ")
    assert a.contract_id != b.contract_id


def test_normalization_change_is_a_new_contract() -> None:
    a = NEURAL_EMBED_CONTRACT
    b = replace(a, normalization="none")
    assert a.contract_id != b.contract_id


def test_contract_has_no_backend_field() -> None:
    """Gate 5: physical execution (MPS/CUDA/API) is not part of the
    contract — backend location cannot change retrieval semantics."""
    fields = EmbeddingContract.__dataclass_fields__
    assert "backend" not in fields
    assert "device" not in fields
    assert "endpoint" not in fields


def test_contract_id_is_stable_for_identical_fields() -> None:
    a = NEURAL_EMBED_CONTRACT
    b = replace(a)
    assert a.contract_id == b.contract_id
    assert a.contract_id in CONTRACTS


def test_hash_embed_contract_is_permanent_and_working() -> None:
    assert HASH_EMBED_CONTRACT.contract_id in CONTRACTS
    v = HASH_EMBED_CONTRACT.embed("deterministic fixture", "child_chunk")
    assert len(v) == HASH_EMBED_CONTRACT.dimension
    w = HASH_EMBED_CONTRACT.embed("deterministic fixture", "child_chunk")
    assert v == w  # byte-stable across calls


def test_neural_contract_pins_the_model_identity() -> None:
    assert NEURAL_EMBED_CONTRACT.model_id
    assert NEURAL_EMBED_CONTRACT.representation_kinds == (
        "document_profile", "parent_summary", "child_chunk", "query",
    )
