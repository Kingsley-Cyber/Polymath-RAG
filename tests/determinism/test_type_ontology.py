"""SCIENTIFIC-KAG-V1 phase 4 groundwork: the knowledge-object hierarchy.

Closure, hybrid-node expansion (Method is both a type and a family),
loud failure on unknown tokens, and rule-pack signature expansion.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.type_ontology import (  # noqa: E402
    expand_signature,
    expand_type,
    validate_closure,
)


def test_closure_holds():
    validate_closure()


def test_research_artifact_family_matches_owner_specification():
    fam = expand_type("ResearchArtifact")
    for expected in ("Method", "Model", "Framework", "Dataset", "Benchmark",
                     "Experiment", "Paper", "Software", "Concept",
                     "Algorithm", "Technique", "Architecture", "Corpus",
                     "Library", "Tool"):
        assert expected in fam, expected


def test_hybrid_nodes_expand_to_themselves_plus_children():
    assert expand_type("Method") == frozenset(
        {"Method", "Algorithm", "Technique"})
    assert expand_type("Dataset") == frozenset({"Dataset", "Corpus"})
    assert expand_type("Person") == frozenset({"Person"})


def test_unknown_token_fails_loudly():
    import pytest
    from polymath_shared.type_ontology import concrete_leaves
    with pytest.raises(ValueError):
        concrete_leaves("NotAKnownFamily")


def test_signature_expansion_resolves_families():
    sig = {"subject_core": ["Agent"], "object_core": ["ResearchArtifact"]}
    out = expand_signature(sig)
    assert "Person" in out["subject_core"]
    assert "ResearchGroup" in out["subject_core"]
    assert "Paper" in out["object_core"]
    assert "Model" in out["object_core"]
    assert "Framework" in out["object_core"]
