"""R3a contract: evidence_bundle.schema.json validates real assembler
output and rejects malformed bundles (missing provenance is a
violation, not a data-shape accident)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.evidence_assembly import assemble_evidence_bundle  # noqa: E402


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "contracts" / "answer" / "v1" / "evidence_bundle.schema.json").read_text()
    )


def _sample_bundle() -> dict:
    return assemble_evidence_bundle(
        "who founded Acme",
        [{"fact_id": "fact_f1", "predicate": "founded",
          "subject": "Alice", "object": "Acme"}],
        [{"chunk_id": "chunk_c1", "doc_id": "doc_b", "parent_id": "p",
          "text": "context chunk", "contract_ids": ["lexical-v1"]}],
        resolve_fact=lambda fid: {
            "fact_id": fid, "predicate": "founded",
            "subject_id": "ent_a", "object_id": "ent_b",
            "qualifiers": {}, "decision": "ACCEPT",
            "rule_id": "r1", "rule_version": "1.0.1",
            "provenance": {"roleset": "establish.01",
                           "resource_contract_id": "03a513ec",
                           "compiled_lexical_sha256": "5c58adbd"},
        },
        resolve_evidence=lambda fid: [{
            "evidence_id": "ev_1", "fact_id": fid, "doc_id": "doc_a",
            "chunk_id": "chunk_a1", "span_offsets": {},
            "rule_id": "r1", "extractor_version": "1.0", "rule_version": "1.0.1",
        }],
        resolve_entity=lambda eid: {
            "ent_a": {"entity_id": eid, "core_type": "PERSON",
                      "normalized_surface": "Alice"},
            "ent_b": {"entity_id": eid, "core_type": "ORGANIZATION",
                      "normalized_surface": "Acme"},
        }[eid],
        resolve_document=lambda did: {"doc_a": {"doc_id": "doc_a",
                                                "corpus_id": "c1",
                                                "source_name": "a.txt"},
                                      "doc_b": {"doc_id": "doc_b",
                                                "corpus_id": "c1",
                                                "source_name": "b.txt"}}[did],
        resolve_chunk=lambda cid: {
            "chunk_a1": {"chunk_id": "chunk_a1", "doc_id": "doc_a",
                         "text": "Alice founded Acme.", "char_start": 0,
                         "char_end": 18},
            "chunk_c1": {"chunk_id": "chunk_c1", "doc_id": "doc_b",
                         "text": "context chunk", "char_start": 19,
                         "char_end": 32},
        }[cid],
    )


def test_real_bundle_validates_against_contract(schema: dict) -> None:
    jsonschema.validate(_sample_bundle(), schema)


def test_evidence_item_with_null_claim_is_valid(schema: dict) -> None:
    bundle = _sample_bundle()
    evidence_items = [i for i in bundle["evidence_bundle"] if i["kind"] == "evidence"]
    assert evidence_items
    assert evidence_items[0]["claim_candidate"] is None
    jsonschema.validate(bundle, schema)


def test_missing_required_span_field_is_rejected(schema: dict) -> None:
    bundle = _sample_bundle()
    del bundle["evidence_bundle"][0]["source_span"]["locator"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bundle, schema)
