"""Pydantic contract validation: malformed spans fail loudly at the boundary.

Structural validation only — the models never infer semantics (docx §16:
any semantic logic in a validator violates the architecture).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.contracts import (  # noqa: E402
    CoreType,
    EntitySpan,
    EvidenceSpan,
    ExtractionManifest,
    RelationCandidate,
    ScopeFlags,
)


def _entity() -> EntitySpan:
    return EntitySpan(
        doc_id="doc_1", chunk_id="chunk_1", start=0, end=4,
        text="John", core_type=CoreType.PERSON, score=0.9, extractor_version="v1",
    )


def test_entity_span_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        EntitySpan(
            doc_id="doc_1", chunk_id="chunk_1", start=0, end=4,
            text="John", core_type=CoreType.PERSON, score=1.5, extractor_version="v1",
        )


def test_negative_offsets_rejected() -> None:
    with pytest.raises(ValidationError):
        EntitySpan(
            doc_id="doc_1", chunk_id="chunk_1", start=-1, end=4,
            text="John", core_type=CoreType.PERSON, score=0.9, extractor_version="v1",
        )


def test_unknown_core_type_rejected() -> None:
    with pytest.raises(ValidationError):
        EntitySpan(
            doc_id="doc_1", chunk_id="chunk_1", start=0, end=4,
            text="John", core_type="Spaceship", score=0.9, extractor_version="v1",
        )


def test_relation_candidate_requires_evidence_and_entities() -> None:
    from polymath_shared.contracts import EntityCandidate

    candidate = RelationCandidate(
        evidence=EvidenceSpan(
            chunk_id="c", start=0, end=7, text="founded",
            evidence_class="creation", score=0.8, extractor_version="v1",
        ),
        subject=EntityCandidate(span=_entity(), resolved_entity_id="ent_1"),
        object=EntityCandidate(span=_entity(), resolved_entity_id="ent_2"),
        scope=ScopeFlags(),
        ontology_profile="core",
    )
    assert candidate.evidence.evidence_class == "creation"


def test_extraction_manifest_requires_versions() -> None:
    with pytest.raises(ValidationError):
        ExtractionManifest(
            run_id="run_1", gliner_model="m", gliner_revision="r",
            parser="spacy", parser_version="3.7",
            ontology_version="v1",  # rule_pack_version missing
        )
