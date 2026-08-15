"""R1A retrieval-summary substrate determinism (pure; no stores).

Canonical DOCUMENT_RETRIEVAL_SUMMARY and SECTION_RETRIEVAL_SUMMARY:
deterministic, source-derived, coverage-preserving, bounded,
versioned content identity, no fabrication.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.retrieval_summaries import (  # noqa: E402
    CONTRACT,
    DOC_SUMMARY_KIND,
    SECTION_SUMMARY_KIND,
    document_retrieval_summary,
    section_retrieval_summary,
    summary_id,
)


def _parents(*texts):
    return [{"chunk_id": f"parent_{i}", "summary": t, "text": t}
            for i, t in enumerate(texts)]


def test_document_summary_is_deterministic_and_bounded():
    parents = _parents(
        "Opening section. Dominant topic A repeated many times. Topic A again.",
        "Middle section. Distinct concept B with unique vocabulary.",
        "Late section. Late-document concept C appears only here at the end.",
    )
    a = document_retrieval_summary(parents, doc_id="d1")
    b = document_retrieval_summary(parents, doc_id="d1")
    assert a == b, "identical inputs must produce identical summaries"
    text, prov = a
    assert len(text) <= 1600
    assert len(prov) <= 12
    assert all("parent_id" in p and "reason" in p for p in prov)


def test_late_document_material_survives():
    """Coverage: the late section's unique concept must appear even though
    the opening section dominates vocabulary."""
    parents = _parents(
        "Opening section. Dominant topic alpha repeated again and again. Alpha alpha.",
        "Opening section two. Alpha continues here as well.",
        "Late section. Unique late concept zephyr appears only here.",
    )
    text, _ = document_retrieval_summary(parents, doc_id="d1")
    assert "zephyr" in text.lower(), f"late material starved: {text}"


def test_section_summary_covers_each_distinct_child():
    children = [
        {"chunk_id": "c1", "text": "First child about vector indexes and dense search."},
        {"chunk_id": "c2", "text": "Second child about a completely different topic: kitchen sinks."},
        {"chunk_id": "c3", "text": "Third child again about vector indexes and dense search."},
    ]
    text, prov = section_retrieval_summary(children, parent_id="p1")
    assert "vector indexes" in text.lower()
    assert "kitchen sinks" in text.lower(), f"child starved: {text}"
    assert len(text) <= 600


def test_single_child_overlap_is_recorded_not_hidden():
    children = [{"chunk_id": "c1", "text": "Only child content discussing retrieval systems in depth."}]
    text, prov = section_retrieval_summary(children, parent_id="p1")
    assert prov and prov[0].get("single_child_overlap") is True


def test_dedupe_removes_redundant_content():
    children = [
        {"chunk_id": "c1", "text": "Repeated sentence about the system."},
        {"chunk_id": "c2", "text": "Repeated sentence about the system."},
    ]
    text, prov = section_retrieval_summary(children, parent_id="p1")
    assert text.count("Repeated sentence") == 1, f"redundancy kept: {text}"


def test_summary_identity_is_versioned_and_content_derived():
    text_a, _ = document_retrieval_summary(_parents("Content alpha here."), doc_id="d1")
    sid_a = summary_id(DOC_SUMMARY_KIND, "d1", text_a)
    sid_b = summary_id(DOC_SUMMARY_KIND, "d1", text_a + " changed")
    sid_c = summary_id(SECTION_SUMMARY_KIND, "d1", text_a)
    assert sid_a.startswith("summ_")
    assert sid_a != sid_b and sid_a != sid_c
    assert sid_a == summary_id(DOC_SUMMARY_KIND, "d1", text_a), "identity must be stable"


def test_no_fabrication_sentences_are_source_derived():
    parents = _parents(
        "Section one contains alpha material.",
        "Section two contains beta material.",
    )
    text, prov = document_retrieval_summary(parents, doc_id="d1")
    for sentence in text.split(". "):
        if sentence.strip():
            assert any(sentence.strip()[:30] in p["text"] for p in parents), \
                f"fabricated sentence: {sentence}"
