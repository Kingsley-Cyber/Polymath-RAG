"""SUMMARY-LAYER S2: parent summary composition (deterministic)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.parent_summary import build_parent_summary  # noqa: E402


def _sample():
    children = [
        {"id": "child_001",
         "text": "The encoder uses self-attention layers."},
        {"id": "child_002",
         "text": "Each attention head learns different relationships."},
        {"id": "child_003",
         "text": "The architecture allows parallel processing."},
    ]
    facts = [{"predicate": "uses",
              "subject_surface": "Transformer",
              "object_surface": "self-attention"}]
    entities = [{"surface": "Transformer", "core_type": "Framework"},
                {"surface": "dropout noise", "core_type": "Concept",
                 "admission_class": "MENTION_ONLY"}]
    return children, facts, entities


def test_parent_summary_shape_and_provenance():
    children, facts, entities = _sample()
    env = build_parent_summary(parent_id="parent_001",
                               parent_text=" ".join(
                                   c["text"] for c in children),
                               children=children, facts=facts,
                               entities=entities)
    assert not validate(env)
    payload = env["payload"]
    assert payload["summary_type"] == "parent"
    assert payload["parent_id"] == "parent_001"
    assert env["derived_from"] == ["child_001", "child_002", "child_003"]
    assert "Transformer uses self-attention." in payload["summary"]
    assert "Transformer" in payload["entities"]
    assert "dropout noise" not in payload["entities"]


def test_concept_capture_from_children():
    children, facts, entities = _sample()
    env = build_parent_summary(parent_id="p", parent_text="x",
                               children=children, facts=facts,
                               entities=entities)
    concepts = " | ".join(env["payload"]["concepts"]).lower()
    assert "self-attention" in concepts


def test_fallback_when_no_facts():
    children = [{"id": "c1", "text": "Quiet section about storage."}]
    env = build_parent_summary(parent_id="p2", parent_text="Quiet "
                               "section about storage.",
                               children=children, facts=[],
                               entities=[{"surface": "X",
                                          "core_type": "Product"}])
    assert env["payload"]["summary"].startswith("Quiet section")


def validate(env):
    from polymath_shared.summary_layer import validate_envelope
    return validate_envelope(env)
