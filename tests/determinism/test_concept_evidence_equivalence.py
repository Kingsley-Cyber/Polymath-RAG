"""ADMISSION-IMPL-MEMO-V1 — find_document_definition optimization proof.

The optimized implementation (cached sentence split, precompiled
templates, same-engine term prefilter, per-(term, text) memo) must be
input/output-identical to the naive reference: same evidence kind, term,
quote, offsets; same first-sentence-then-first-template precedence; same
ABSTAIN. The concept-evidence-v1 contract string is unchanged BECAUSE
behavior is unchanged — this test is what licenses that.
"""
import re

import pytest

from polymath_shared.concept_evidence import (
    _DEFINITIONAL,
    _sentences,
    _strip_det,
    ConceptEvidence,
    ConceptEvidenceKind,
    find_document_definition,
)


def _reference_find_document_definition(term, text, doc_id=None):
    """The pre-optimization implementation, verbatim semantics."""
    bare = _strip_det(term)
    pat = re.escape(bare)
    for sent in [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]:
        for tmpl, why in _DEFINITIONAL:
            if re.search(tmpl.replace("{term}", pat), sent, re.I):
                off = text.find(sent)
                return ConceptEvidence(
                    ConceptEvidenceKind.DOCUMENT_DEFINED, bare, quote=sent[:200],
                    source_document_id=doc_id,
                    source_offsets=(off, off + len(sent)) if off >= 0 else None)
    return None


DOC = """# Notes on systems

Write-ahead logging is a technique for durability. The buffer pool
is often described as the cache of disk pages. Checkpointing refers to
flushing dirty pages.

A deadlock, a cycle of waiting transactions, halts progress, always.
We define fencing as excluding stale leaders. By quorum we mean a
majority. Latency is slow. The system is widely used.

Thrashing occurs when the working set exceeds memory! Paging, also
called swapping, moves frames. STRAßE is a street. The ſilent term
is odd. IP is a protocol identifier.
"""

TERMS = [
    "Write-ahead logging", "the buffer pool", "Checkpointing", "a deadlock",
    "fencing", "quorum", "Latency", "The system", "Thrashing", "Paging",
    "STRAßE", "straße", "ſilent term", "IP", "ip", "nonexistent thing",
    "logging", "pool", "a", "the", "", "  ", "term (with) parens",
    "C++ pointers", "waiting transactions", "cycle of waiting transactions",
    "majority", "working set", "swapping",
]


@pytest.mark.parametrize("term", TERMS)
def test_matches_reference_on_mixed_document(term):
    assert find_document_definition(term, DOC, "d1") == \
        _reference_find_document_definition(term, DOC, "d1")


def test_precedence_first_sentence_wins_over_earlier_template():
    # sentence 1 matches only a LATE template ('refers to'); sentence 2
    # matches the FIRST template. Reference returns sentence 1.
    text = "Foo refers to a thing. Foo is a widget that spins."
    got = find_document_definition("Foo", text)
    ref = _reference_find_document_definition("Foo", text)
    assert got == ref
    assert got is not None and got.quote.startswith("Foo refers to")


def test_template_order_within_a_sentence():
    text = "We define bar as bar is a gadget."
    assert find_document_definition("bar", text) == \
        _reference_find_document_definition("bar", text)


def test_repeated_calls_and_distinct_texts_do_not_cross_contaminate():
    t1 = "Alpha is a metric for load."
    t2 = "Alpha is slow."
    for _ in range(3):
        assert find_document_definition("Alpha", t1) == \
            _reference_find_document_definition("Alpha", t1)
        assert find_document_definition("Alpha", t2) == \
            _reference_find_document_definition("Alpha", t2)
        assert find_document_definition("Beta", t1) == \
            _reference_find_document_definition("Beta", t1)


def test_offsets_and_quote_construction_identical():
    text = "Preamble here.\nGamma rays are a form of radiation."
    got = find_document_definition("Gamma rays", text, "docX")
    ref = _reference_find_document_definition("Gamma rays", text, "docX")
    assert got == ref
    assert got.source_offsets is not None
    assert got.source_document_id == "docX"


def test_sentence_cache_returns_same_split():
    text = "One sentence. Another one!\nA third?"
    assert list(_sentences(text)) == [s.strip() for s in
        re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
