"""Deterministic no-LLM ingestion: chunker + summarizer invariants.

The chunker never splits a sentence, the parent layer summarizes its
children, chunk identities are content hashes (re-chunking unchanged
text is a no-op), and summaries are pure functions of the input text.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers"))

from polymath_shared.identity import document_id, normalize_document_bytes  # noqa: E402
from workers.chunker import materialize_chunks, plan_document  # noqa: E402
from workers.summarizer import split_sentences, summarize  # noqa: E402

TEXT = (
    "Polymath v4 is a local-first GraphRAG workbench. "
    "The extraction layer is a two-pass GLiNER pipeline. "
    "A deterministic compiler maps evidence onto canonical predicates. "
    "Postgres is the workflow authority. "
    "Receipts commit in one transaction with the stage artifact. "
    "The control plane is a separate process with a lease. "
    "Models propose spans. The compiler decides. Silence is valid. "
    "Qdrant and Neo4j are rebuildable projections."
) * 3


def test_chunks_are_sentence_aligned() -> None:
    doc_id = document_id(normalize_document_bytes(TEXT.encode()))
    plan = plan_document(TEXT, doc_id, child_target_chars=200)
    assert plan.children, "long text must produce children"
    sentences = split_sentences(TEXT)
    for spec in plan.children:
        for sentence in split_sentences(spec.text):
            assert sentence in sentences, "chunks must contain whole sentences only"


def test_parents_summarize_their_children() -> None:
    doc_id = document_id(normalize_document_bytes(TEXT.encode()))
    rows = materialize_chunks(plan_document(TEXT, doc_id, child_target_chars=250))
    parents = [r for r in rows if r["tier"] == "parent"]
    children = [r for r in rows if r["tier"] == "child"]
    assert parents, "multi-child documents must produce a parent layer"
    assert len(parents) < len(children)
    for child in children:
        assert child["parent_id"] is not None
        assert child["parent_id"] in {p["chunk_id"] for p in parents}


def test_rechunking_identical_text_is_a_noop() -> None:
    doc_id = document_id(normalize_document_bytes(TEXT.encode()))
    first = materialize_chunks(plan_document(TEXT, doc_id))
    second = materialize_chunks(plan_document(TEXT, doc_id))
    assert [r["chunk_id"] for r in first] == [r["chunk_id"] for r in second]
    assert [r["chunk_index"] for r in first] == [r["chunk_index"] for r in second]


def test_summarizer_is_pure_and_bounded() -> None:
    a = summarize(TEXT, max_sentences=3, max_chars=500)
    b = summarize(TEXT, max_sentences=3, max_chars=500)
    assert a == b
    assert len(a) <= 500
    assert a  # non-empty for non-empty input
    assert summarize("") == ""


def test_summarizer_prefers_lead_sentences() -> None:
    text = (
        "Alpha is the most important sentence in this document. "
        "Beta is filler content that repeats filler content again and again. "
        "Gamma repeats filler content too. Delta also repeats filler content. "
        "Epsilon repeats filler content once more."
    )
    summary = summarize(text, max_sentences=2, max_chars=300)
    assert "Alpha" in summary


def test_document_normalization_maps_encodings_to_one_id() -> None:
    raw = b"Hello world.\nThis is a test document.\n"
    crlf = b"Hello world.\r\nThis is a test document.\r\n"
    bom = b"\xef\xbb\xbfHello world.\nThis is a test document.\n"
    a = document_id(normalize_document_bytes(raw))
    b = document_id(normalize_document_bytes(crlf))
    c = document_id(normalize_document_bytes(bom))
    assert a == b == c
