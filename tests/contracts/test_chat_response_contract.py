"""R3b contract: chat_response.schema.json validates real pipeline
output; citations must reference bundle items, not merely documents."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.answer_synthesis import grounded_answer  # noqa: E402
from polymath_shared.evidence_assembly import assemble_evidence_bundle  # noqa: E402


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "contracts" / "answer" / "v2" / "chat_response.schema.json").read_text()
    )


def _bundle() -> dict:
    return assemble_evidence_bundle(
        "who founded AcmeCorp",
        [{"fact_id": "fact_f1", "predicate": "founded",
          "subject": "AliceSmith", "object": "AcmeCorp"}],
        [],
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
                      "normalized_surface": "AliceSmith"},
            "ent_b": {"entity_id": eid, "core_type": "ORGANIZATION",
                      "normalized_surface": "AcmeCorp"},
        }[eid],
        resolve_document=lambda did: {
            "doc_a": {"doc_id": "doc_a", "corpus_id": "c1", "source_name": "a.txt"},
        }.get(did),
        resolve_chunk=lambda cid: {
            "chunk_a1": {"chunk_id": "chunk_a1", "doc_id": "doc_a",
                         "text": "AliceSmith founded AcmeCorp.",
                         "char_start": 0, "char_end": 27},
        }.get(cid),
    )


def test_real_chat_response_validates(schema: dict) -> None:
    resp = grounded_answer(_bundle(), "who founded AcmeCorp")
    jsonschema.validate(resp, schema)
    assert resp["citations"][0]["bundle_item_ids"]
    assert resp["citations"][0]["locators"] == ["chunk:chunk_a1@0:27"]


def test_abstention_response_validates(schema: dict) -> None:
    resp = grounded_answer(_bundle(), "who uses pineapple")
    jsonschema.validate(resp, schema)


def test_response_without_citations_is_rejected(schema: dict) -> None:
    resp = grounded_answer(_bundle(), "who founded AcmeCorp")
    del resp["citations"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(resp, schema)


def test_citation_without_bundle_items_is_rejected(schema: dict) -> None:
    resp = grounded_answer(_bundle(), "who founded AcmeCorp")
    resp["citations"][0]["bundle_item_ids"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(resp, schema)
