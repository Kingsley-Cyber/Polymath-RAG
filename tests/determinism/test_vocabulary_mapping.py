"""SUMMARY RUNTIME D5: vocabulary mapping — frozen admission rules."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.vocabulary_mapping import (  # noqa: E402
    admit_family,
    build_concept_families,
)


def _parents(concepts_per_parent):
    out = []
    for pid, cpts in concepts_per_parent:
        out.append({"payload": {"parent_id": pid, "concepts": cpts}})
    return out


def test_shared_support_merges_into_one_family():
    families = build_concept_families(
        corpus_id="ai_v1",
        parent_summaries=_parents([
            ("parent_001", ["attention mechanism", "multi-head attention"]),
            ("parent_002", ["self-attention", "attention mechanism"]),
        ]),
        document_summaries=[],
        accepted_concepts=[])
    assert len(families["families"]) == 1
    fam = families["families"][0]
    assert fam["canonical_name"] == "attention mechanism"
    assert set(fam["aliases"]) == {"multi-head attention", "self-attention"}
    assert fam["supporting_summaries"] == ["parent_001", "parent_002"]


def test_disjoint_support_stays_separate():
    families = build_concept_families(
        corpus_id="ai_v1",
        parent_summaries=_parents([
            ("p1", ["attention mechanism"]),
            ("p2", ["retrieval augmented generation"]),
        ]),
        document_summaries=[],
        accepted_concepts=[])
    assert len(families["families"]) == 2


def test_forbidden_embedding_only_merge_has_no_code_path():
    """The module exposes no similarity API: the only family signal is
    shared summary support. Structural proof by inspection of members."""
    import inspect

    from polymath_shared import vocabulary_mapping as vm
    src = inspect.getsource(vm)
    for banned in ("cosine", "similarity", "embed_"):
        assert banned not in src.replace("embedding neighbors", ""), banned
    public = [n for n, _ in inspect.getmembers(vm, inspect.isfunction)]
    assert not [n for n in public
                if "similar" in n or "embed" in n], public


def test_admit_family_enforces_corpus_isolation():
    fam = {"corpus_id": "cyber_v1", "canonical_name": "model",
           "aliases": [], "supporting_summaries": ["s1"]}
    ok, reason = admit_family(fam, corpus_id="ai_v1")
    assert not ok and reason == "R1_corpus_isolation"


def test_entities_never_appear_in_vocabulary_output():
    """Strongest claim about an entity is relates_to; vocabulary output
    carries no entity ids at all."""
    families = build_concept_families(
        corpus_id="ai_v1",
        parent_summaries=_parents([("p1", ["transformer architecture"])]),
        document_summaries=[], accepted_concepts=[])
    blob = repr(families)
    assert "entity" not in blob.lower()
    ok, _ = admit_family(families["families"][0], corpus_id="ai_v1")
    assert ok
