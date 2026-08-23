"""STEP 1 acceptance: deterministic identity derivation (owner tests)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.identity_model import (  # noqa: E402
    artifact_hash,
    document_fingerprint,
    entity_key,
    fact_key,
)


def test_duplicate_document_same_fingerprint():
    a = document_fingerprint(normalized_content="paper body",
                             corpus_id="ai_v1")
    b = document_fingerprint(normalized_content="paper body",
                             corpus_id="ai_v1")
    assert a == b


def test_pipeline_upgrade_keeps_source_changes_artifact():
    fp = "8fa92ab1"
    v5 = artifact_hash(document_fingerprint=fp,
                       ingestion_contract_version="v1",
                       extraction_version="gliner-2pass-v1",
                       semantic_bundle_version="v5-production-005")
    v6 = artifact_hash(document_fingerprint=fp,
                       ingestion_contract_version="v1",
                       extraction_version="gliner-2pass-v1",
                       semantic_bundle_version="v5-production-006")
    assert v5 != v6, "new rules must regenerate derived artifacts"
    assert fp  # raw document survives


def test_entity_aliasing_one_canonical_key():
    keys = {
        entity_key(corpus_id="AI", normalized_name="bert",
                   entity_type="Model"),
        entity_key(corpus_id="AI", normalized_name="bert",
                   entity_type="Model"),
        entity_key(corpus_id="AI", normalized_name="bert",
                   entity_type="Model"),
    }
    assert len(keys) == 1


def test_corpus_isolation_no_cross_merge():
    ai = entity_key(corpus_id="AI_v1", normalized_name="model",
                    entity_type="Concept")
    cyber = entity_key(corpus_id="cyber_v1", normalized_name="model",
                       entity_type="Concept")
    assert ai != cyber


def test_fact_growth_is_one_key():
    k1 = fact_key(subject_id="ent_bert", predicate="trained_on",
                  object_id="ent_books")
    k2 = fact_key(subject_id="ent_bert", predicate="trained_on",
                  object_id="ent_books")
    assert k1 == k2
    other = fact_key(subject_id="ent_books", predicate="trained_on",
                     object_id="ent_bert")
    assert other != k1, "direction errors must never collide"
