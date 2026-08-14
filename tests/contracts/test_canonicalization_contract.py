"""C1 contract: canonicalization_output.schema.json validates real
canonicalizer output and rejects malformed memberships/decisions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.canonicalizer import canonicalize  # noqa: E402


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "contracts" / "canonicalization" / "v1"
         / "canonicalization_output.schema.json").read_text()
    )


def _output() -> dict:
    out = canonicalize("corpus_x", [
        {"entity_id": "ent_a", "core_type": "Organization",
         "normalized_surface": "AcmeCorp"},
        {"entity_id": "ent_b", "core_type": "Organization",
         "normalized_surface": "acmecorp"},
        {"entity_id": "ent_c", "core_type": "Person",
         "normalized_surface": "John Smith"},
    ], aliases={"AcmeCorp": ["ACME"]})
    return {
        "corpus_id": out.corpus_id,
        "canonicalizer_version": out.canonicalizer_version,
        "canonical_entities": [
            {
                "canonical_id": c.canonical_id,
                "canonical_type": c.canonical_type,
                "normalized_name": c.normalized_name,
                "canonicalizer_version": c.canonicalizer_version,
            }
            for c in out.canonical_entities
        ],
        "memberships": [
            {
                "canonical_id": m.canonical_id,
                "local_entity_id": m.local_entity_id,
                "decision": m.decision,
                "confidence": m.confidence,
                "basis": m.basis,
                "canonicalizer_version": m.canonicalizer_version,
            }
            for m in out.memberships
        ],
        "decisions": [
            {
                "decision_id": d.decision_id,
                "local_entity_a": d.local_entity_a,
                "local_entity_b": d.local_entity_b,
                "decision": d.decision,
                "confidence": d.confidence,
                "basis": d.basis,
                "canonical_id": d.canonical_id,
                "canonicalizer_version": d.canonicalizer_version,
            }
            for d in out.decisions
        ],
    }


def test_real_output_validates(schema: dict) -> None:
    jsonschema.validate(_output(), schema)


def test_membership_decision_vocabulary_is_closed(schema: dict) -> None:
    out = _output()
    out["memberships"][0]["decision"] = "FUZZY_MERGE"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(out, schema)


def test_missing_basis_is_rejected(schema: dict) -> None:
    out = _output()
    del out["memberships"][0]["basis"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(out, schema)


def test_decision_without_confidence_is_rejected(schema: dict) -> None:
    out = _output()
    del out["decisions"][0]["confidence"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(out, schema)
