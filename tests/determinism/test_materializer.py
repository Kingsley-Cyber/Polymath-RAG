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


# ---------------------------------------------------------------------------
# HTML-STRUCTURE-V1 (2026-09-05): lists, tables, pre and headings keep the
# structure the chunker routes on, instead of one paragraph per block tag.
# ---------------------------------------------------------------------------

def _structured():
    return _m("structured.html", "text/html")


def test_html_list_is_one_block_of_item_lines() -> None:
    m = _structured()
    blocks = [m.text[s["text_start"]:s["text_end"]] for s in m.source_map]
    lst = next(b for b in blocks if b.startswith("- lower_com"))
    assert lst.split("\n") == [
        "- lower_com: drop the centre of mass before the launch step",
        "- shorten_penultimate_step so the plant foot lands under the hips",
        "- plant_takeoff_foot flat, toes toward the landing mark",   # <li><p>…</p></li> keeps its bullet
        "- beat: propulsion",
        "  1. wind-up through the arms and torso",                   # nested <ol> indents under its parent item
        "  2. release on the downbeat of the music cue",
    ]
    assert "\n\n" not in lst


def test_html_table_is_one_block_of_pipe_rows() -> None:
    m = _structured()
    blocks = [m.text[s["text_start"]:s["text_end"]] for s in m.source_map]
    tbl = next(b for b in blocks if b.startswith("| Desired control"))
    rows = tbl.split("\n")
    assert rows[0] == "| Desired control | Preferred carrier | Fallback |"
    assert rows[1].startswith("| exact actor identity | character/reference asset |")
    assert len(rows) == 3


def test_html_pre_keeps_lines_and_indentation_in_one_block() -> None:
    m = _structured()
    blocks = [m.text[s["text_start"]:s["text_end"]] for s in m.source_map]
    code = next(b for b in blocks if "cpcs.<domain>.<concept>" in b)
    assert code.split("\n") == [
        "```",
        "id: cpcs.<domain>.<concept>",       # entities unescaped
        "kind: knowledge_card",
        "  nested:",                         # original indentation preserved
        "    depth: 2",
        "epistemic_status: designed_not_executed   # from the controlled vocabulary",
        "sources: [SRC-001, SRC-004, SRC-016]      # primary-source registry ids",
        "```",
    ]


def test_html_headings_br_quote_and_noise() -> None:
    m = _structured()
    blocks = [m.text[s["text_start"]:s["text_end"]] for s in m.source_map]
    assert "# Blocking for Cinematic Storytelling" in blocks
    assert "## Motion primitives" in blocks and "### Carrier table" in blocks
    para = next(b for b in blocks if b.startswith("The process of blocking"))
    assert "&" in para and "&amp;" not in para
    assert para.endswith("\nA line break inside the paragraph stays in the paragraph."), "<br> is a line break, not a paragraph break"
    assert any(b.startswith("> Information also flows backward") for b in blocks)
    assert "must not appear" not in m.text          # <nav>, <script>, <style> dropped
    assert m.parser_version == "1.1.0"
    a = _structured()
    assert a.text == m.text and a.source_map == m.source_map


def test_html_structure_survives_the_tier_chunker_without_stub_children() -> None:
    """End to end: the list and table land in prose-bearing children, not
    one `stub` child per item (the handbook.html failure: 37 % stubs)."""
    import sys
    root = Path(__file__).resolve().parents[2]
    for sub in ("workers", "shared"):
        if str(root / sub) not in sys.path:
            sys.path.insert(0, str(root / sub))
    from workers.tier_chunker import tier_chunk_layout
    from polymath_shared.region_role import classify_region

    m = _structured()
    chunks, _layout = tier_chunk_layout(m.text, "doc_test_structured")
    children = [c for c in chunks if c["tier"] == "child"]
    assert children
    texts = [c["text"] for c in children]
    assert any("- lower_com" in t and "- shorten_penultimate_step" in t and "1. wind-up" in t for t in texts), \
        "list items must share a child, not one child per item"
    assert any(t.startswith("```") and "kind: knowledge_card" in t for t in texts), "pre must be an atomic code child"
    assert any("| exact actor identity |" in t and "| exact start/end pose |" in t for t in texts), \
        "table rows must share a child"
    roles = [classify_region(c["text"], None)[0] for c in children]
    assert roles.count("stub") == 0, f"stub children from structured HTML: {roles}"
