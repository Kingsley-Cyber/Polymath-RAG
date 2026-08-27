"""EMBEDDING-CONTRACT-REGISTRY-V1 regressions (G1 owner decision).

The production semantic-retrieval default is NEURAL (neural-embed-v1).
hash-embed-v1 remains a deterministic TEST/FALLBACK provider — it must
stay registered and resolvable, but must never be the default a new
corpus silently inherits. Per-corpus authority is corpus state:
corpora.embedding_contract_id.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.embedding_contracts import (
    CONTRACTS,
    SHORT_NAMES,
    active_contract,
)


def test_production_default_is_neural():
    """The G1 flip, pinned: settings default resolves to the neural
    contract, not hash."""
    assert active_contract().model_id == "Qwen/Qwen3-Embedding-0.6B"


def test_hash_contract_survives_as_test_fallback():
    """Deterministic fixtures/fallbacks depend on hash-embed-v1 staying
    registered and resolvable — removing it would break replay gates."""
    assert "hash-embed-v1" in SHORT_NAMES
    assert SHORT_NAMES["hash-embed-v1"].embed_fn is not None


def test_neural_contract_frozen_fields_unchanged():
    """Do NOT change model/dimension/serializer/instructions as part of
    G1 — the benchmark that qualified this contract ran exactly these."""
    c = SHORT_NAMES["neural-embed-v1"]
    assert c.model_id == "Qwen/Qwen3-Embedding-0.6B"
    assert c.model_revision == "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    assert c.dimension == 1024
    assert c.distance_metric == "cosine"
    assert c.normalization == "l2"
    assert c.query_prefix.startswith("Instruct:")


def test_worker_resolves_corpus_pin_over_settings_default(monkeypatch):
    """A corpus pinned to hash MUST keep projecting/searching under hash
    even after the default flipped — existing vectors are never
    reinterpreted in place."""
    import workers.project_qdrant_worker as W

    class Conn:
        def execute(self, sql, params=None):
            assert "embedding_contract_id" in sql
            return self

        def fetchone(self):
            return ("hash-embed-v1",)

    resolved = W._corpus_contract(Conn(), "some-legacy-corpus")
    assert resolved.model_id == "none"          # hash contract honored
    # unknown pin fails loudly rather than silently re-embedding
    class BadConn(Conn):
        def fetchone(self):
            return ("embed_does_not_exist",)

    try:
        W._corpus_contract(BadConn(), "broken-corpus")
        raise SystemExit("expected ValueError")
    except ValueError:
        pass
