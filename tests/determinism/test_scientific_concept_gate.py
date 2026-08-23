"""SCIENTIFIC-KAG-V1 phase 2: the named-concept identity gate.

Accept/reject matrix comes verbatim from the owner mission: named
research concepts are durable; bare generic nouns and plurals are not.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.scientific_concept import (  # noqa: E402
    named_concept_evidence,
)


def _accepts(surface):
    return named_concept_evidence(surface) is not None


def test_named_research_concepts_accept():
    for surface in ("Tree of Thoughts", "Chain of Thought",
                    "Retrieval Augmented Generation", "Transformer Architecture",
                    "thought generator", "state evaluator", "tree search",
                    "search algorithm"):
        assert _accepts(surface), surface


def test_generic_nouns_and_plurals_reject():
    for surface in ("thought", "state", "node", "algorithm", "method",
                    "thoughts", "states", "the"):
        assert not _accepts(surface), surface


def test_model_names_and_acronyms_accept():
    assert _accepts("GPT-4")
    assert _accepts("BERT")
    assert _accepts("ToT")
    assert not _accepts("LMs")  # mixed-case plural noise is not a concept
