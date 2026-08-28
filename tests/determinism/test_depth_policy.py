"""QUERY-SHAPE-V1 depth policy: multi-intent qualification.

The depth profile lifts per-document caps and turns on neighbour
expansion. It is right for completeness questions and wrong everywhere
else: an ordinary comparison answered with 24 chunks is padding, not
thoroughness.

This matrix already caught one live over-trigger — "what are the pros
and cons of X" pulled the depth sweep via a bare "what are the ..."
branch — so every intent class below is pinned.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.pass1 import PASS1_DEFAULT_PLAN  # noqa: E402
from polymath_shared.query_shape import (  # noqa: E402
    is_document_metadata_query,
    is_enumeration_query,
    plan_for_query,
)

BREADTH = "breadth"
DEPTH = "depth"

MATRIX = [
    # (intent class, query, expected depth class)
    ("simple fact",        "what is a SIEM", BREADTH),
    ("simple fact",        "what port does SSH use", BREADTH),
    ("explanation",        "how does vulnerability scanning work", BREADTH),
    ("comparison",         "what are the tradeoffs between SIEM and SOAR", BREADTH),
    ("pros/cons",          "what are the pros and cons of agentless vulnerability scanning", BREADTH),
    ("difference",         "what are the differences between threat hunting and threat intelligence", BREADTH),
    ("single procedure",   "how do you contain a compromised host", BREADTH),
    ("metadata",           "who wrote this book", BREADTH),
    ("what are all",       "what are all the domains and subdomains of CySA+", DEPTH),
    ("what are all",       "what are all the phases of the incident response life cycle", DEPTH),
    ("list every",         "list every log source useful for detecting lateral movement", DEPTH),
    ("give me all",        "list all the incident response steps", DEPTH),
    ("cross-doc enum",     "name every control in domain 2", DEPTH),
    ("structure nouns",    "what are the domains and subdomains of CySA", DEPTH),
]


@pytest.mark.parametrize("intent,query,expected", MATRIX,
                         ids=[f"{i}:{q[:28]}" for i, q, _ in MATRIX])
def test_depth_class(intent, query, expected):
    got = DEPTH if is_enumeration_query(query) else BREADTH
    assert got == expected, f"{intent}: {query!r} -> {got}, expected {expected}"


def test_depth_only_widens_within_one_document():
    """Depth must not inflate breadth: max_documents is unchanged, so a
    completeness question does not silently fan out across the corpus."""
    base = PASS1_DEFAULT_PLAN
    deep = plan_for_query("what are all the domains and subdomains", base)
    assert deep.max_documents == base.max_documents
    assert deep.max_sections_per_document > base.max_sections_per_document
    assert deep.final_max_children > base.final_max_children


def test_breadth_plan_is_byte_identical_for_ordinary_questions():
    """The frozen plan must be untouched for non-enumeration queries."""
    assert plan_for_query("what is a SIEM", PASS1_DEFAULT_PLAN) == PASS1_DEFAULT_PLAN


# ------------------------------------------------ metadata escape hatch
METADATA_QUERIES = [
    "who wrote this book",
    "what does this book cover and who wrote it",
    "show the bibliography",
    "what chapters are listed in the table of contents",
    "what does the preface say",
]
NOT_METADATA = [
    "what is a SIEM",
    "how do you contain a compromised host",
    "what are all the domains and subdomains of CySA+",
    # region vocabulary inside a technical question must NOT lift demotion
    "what are index structures in databases",
    "explain code signing",
]


@pytest.mark.parametrize("q", METADATA_QUERIES)
def test_metadata_queries_lift_region_demotion(q):
    assert is_document_metadata_query(q)
    assert plan_for_query(q, PASS1_DEFAULT_PLAN).demote_noisy_regions is False


@pytest.mark.parametrize("q", NOT_METADATA)
def test_ordinary_queries_keep_region_demotion(q):
    assert not is_document_metadata_query(q)
    assert plan_for_query(q, PASS1_DEFAULT_PLAN).demote_noisy_regions is True
