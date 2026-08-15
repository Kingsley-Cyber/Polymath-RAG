"""I0 materializer invariants (no stores).

Deterministic per-format materialization: identical bytes produce
identical text + source map + hashes. Structural order preserved
(EPUB spine, DOCX paragraph/heading). Failure is LOUD for
unsupported/encrypted/corrupted/empty/low-yield inputs. Source-map
segments resolve normalized character ranges back to native
locations.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.materializer import (  # noqa: E402
    CorruptedDocumentError,
    EmptyExtractionError,
    EncryptedDocumentError,
    LowYieldError,
    UnsupportedFormatError,
    materialize,
)

FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures" / "native_docs"


def _m(name: str, media_type: str):
    return materialize((FIXTURES / name).read_bytes(), media_type, name)


def test_txt_is_byte_stable_and_deterministic() -> None:
    m = _m("psychology.txt", "text/plain")
    assert m.format == "text"
    assert "bundles of habits" in m.text
    assert m.source_map[0]["kind"] == "document"
    a = _m("psychology.txt", "text/plain")
    assert a.normalized_text_sha256 == m.normalized_text_sha256
    assert a.text == m.text


def test_markdown_materializes_stably() -> None:
    m = _m("psychology.md", "text/markdown")
    assert m.format == "markdown"
    # Markdown is TEXT: heading markers are kept byte-stable, not stripped.
    assert "# THE PRINCIPLES OF PSYCHOLOGY" in m.text
    assert "Habit simplifies" in m.text


def test_html_removes_presentation_noise_deterministically() -> None:
    m = _m("psychology.html", "text/html")
    assert m.format == "html"
    assert "navigation noise that must not appear" not in m.text
    assert "var tracking" not in m.text
    assert "bundles of habits" in m.text
    assert m.source_map and all(s["kind"] == "block" for s in m.source_map)
    a = _m("psychology.html", "text/html")
    assert a.normalized_text_sha256 == m.normalized_text_sha256


def test_pdf_extracts_pages_in_order_with_page_map() -> None:
    m = _m("psychology.pdf", "application/pdf")
    assert m.format == "pdf"
    assert len(m.text) > 500
    locations = [s["location"] for s in m.source_map]
    assert locations == sorted(locations, key=lambda l: int(l.split()[1]))
    assert len(m.source_map) >= 2
    for seg in m.source_map:
        assert m.text[seg["text_start"]:seg["text_end"]].strip()


def test_epub_extracts_chapters_in_spine_order() -> None:
    m = _m("psychology.epub", "application/epub+zip")
    assert m.format == "epub"
    chapters = [s["label"] for s in m.source_map if s["kind"] == "chapter"]
    assert chapters == ["c1", "c2", "c3"]
    assert "bundles of habits" in m.text
    assert "Editor's summary" in m.text


def test_docx_preserves_paragraph_heading_order() -> None:
    m = _m("psychology.docx",
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert m.format == "docx"
    assert m.source_map[0]["label"] == "Title"
    assert any(s["kind"] == "heading" and "HABIT" in s["location"] for s in m.source_map)
    # headings set the section context for following paragraphs
    heading_positions = [s for s in m.source_map if s["kind"] == "heading"]
    assert heading_positions
    after_heading = [s for s in m.source_map
                     if s["text_start"] > heading_positions[0]["text_start"]]
    assert after_heading[0]["location"] == heading_positions[0]["location"]


def test_source_map_segments_resolve_offsets() -> None:
    m = _m("psychology.pdf", "application/pdf")
    offset = len(m.text) // 2
    seg = next(s for s in m.source_map
               if s["text_start"] <= offset < s["text_end"])
    assert seg["kind"] == "page"
    assert "page " in seg["location"]


def test_unsupported_format_fails_loudly() -> None:
    with pytest.raises(UnsupportedFormatError):
        materialize(b"binary", "application/octet-stream", "data.bin")


def test_empty_extraction_fails_loudly() -> None:
    with pytest.raises(EmptyExtractionError):
        materialize(b"   \n  ", "text/plain", "empty.txt")


def test_corrupted_zip_fails_loudly() -> None:
    with pytest.raises(CorruptedDocumentError):
        materialize(b"not a zip at all", "application/epub+zip", "broken.epub")


def test_docx_missing_document_xml_fails_loudly() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.txt", "no document.xml here")
    with pytest.raises(CorruptedDocumentError):
        materialize(buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "broken.docx")


def test_low_yield_binary_fails_loudly() -> None:
    # A "pdf" whose text yield is below the threshold: pad with non-text.
    big = b"%PDF-1.7 fake header " + b"\x00" * 50000
    with pytest.raises((CorruptedDocumentError, LowYieldError)):
        materialize(big, "application/pdf", "low.pdf")


def test_repeated_parsing_is_identical_for_all_formats() -> None:
    cases = [
        ("psychology.txt", "text/plain"),
        ("psychology.md", "text/markdown"),
        ("psychology.html", "text/html"),
        ("psychology.pdf", "application/pdf"),
        ("psychology.epub", "application/epub+zip"),
        ("psychology.docx",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
    for name, mt in cases:
        a = materialize((FIXTURES / name).read_bytes(), mt, name)
        b = materialize((FIXTURES / name).read_bytes(), mt, name)
        assert a.text == b.text, name
        assert a.normalized_text_sha256 == b.normalized_text_sha256, name
        assert a.source_map == b.source_map, name
        assert a.original_sha256 == b.original_sha256, name


def test_original_hash_is_traceable() -> None:
    raw = (FIXTURES / "technical.txt").read_bytes()
    m = materialize(raw, "text/plain", "technical.txt")
    import hashlib

    assert m.original_sha256 == hashlib.sha256(raw).hexdigest()
    assert m.original_byte_length == len(raw)


def test_evidence_lemmatizer_v2_maps_realistic_prose_forms() -> None:
    """Q1-R regression lock: the v2 lexical lemmatizer maps past-tense
    and copula forms that realistic prose depends on. The v1 stemmer
    produced zero anchors for these (the Q1-R generalization failure)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers"))
    from workers.evidence_proposer import _match_verb  # noqa: E402

    assert _match_verb("used", ["use", "apply"]) == "use"
    assert _match_verb("based", ["locate", "base", "situate"]) == "base"
    assert _match_verb("reduced", ["reduce", "cut"]) == "reduce"
    assert _match_verb("reported", ["state", "cite", "document", "describe", "report"]) == "report"
    assert _match_verb("is", ["be", "represent", "constitute"]) == "be"
    assert _match_verb("making", ["make", "create"]) == "make"
    assert _match_verb("uses", ["use", "apply"]) == "use"
    assert _match_verb("leads", ["lead", "head"]) == "lead"
