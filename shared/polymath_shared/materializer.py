"""I0: deterministic native document materialization (ADR 0010).

Turns native source files (PDF / EPUB / DOCX / TXT / Markdown / HTML)
into a deterministic normalized-text representation plus a structural
source map, for the EXISTING frozen ingestion/extraction pipeline.

Guarantees:
  - pure function of (bytes, media_type): identical input yields
    byte-identical text, source map, and hashes;
  - source-map segments map normalized character ranges to native
    locations (page for PDF, chapter for EPUB, heading context for
    DOCX, block for HTML);
  - failure is LOUD: unsupported format, encrypted/corrupted document,
    empty extraction, or suspiciously low text yield raise a typed
    MaterializationError — an empty document is never ingested
    silently;
  - TXT/Markdown use the SAME byte normalization as the pre-I0 intake
    path (byte-stable; the Q1-qualified behavior is unchanged).

This module owns document materialization ONLY. It never touches
entities, facts, the compiler, GLiNER, ontology, or thresholds.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import io
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional
from xml.etree import ElementTree

MATERIALIZER_NAME = "polymath-materializer"
MATERIALIZER_VERSION = "1.1.0"   # HTML-STRUCTURE-V1 (2026-09-05): lists, tables, pre, headings keep their structure

TEXT_MEDIA_TYPES = {
    "text/plain": "text",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/html": "html",
}

EXTENSION_FALLBACK = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
    ".epub": "epub",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
}

# Binary formats must yield at least this many characters per byte of
# source size; below that the extraction is suspicious and fails loud.
MIN_TEXT_YIELD = 0.001
MIN_BINARY_CHARS = 20

_BLOCK_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br",
    "section", "article", "header", "footer", "blockquote", "pre", "td",
    "th", "table", "ul", "ol", "dl", "dt", "dd",
}
_SKIP_TAGS = {"script", "style", "head", "noscript", "template", "svg", "nav"}   # nav: HTML-STRUCTURE-V1
_WS_RE = re.compile(r"\s+")


class MaterializationError(RuntimeError):
    """Base for loud materialization failures."""


class UnsupportedFormatError(MaterializationError):
    pass


class EncryptedDocumentError(MaterializationError):
    pass


class CorruptedDocumentError(MaterializationError):
    pass


class EmptyExtractionError(MaterializationError):
    pass


class LowYieldError(MaterializationError):
    pass


@dataclass
class Materialization:
    text: str
    source_map: list[dict] = field(default_factory=list)
    parser: str = MATERIALIZER_NAME
    parser_version: str = MATERIALIZER_VERSION
    format: str = ""
    media_type: str = ""
    original_sha256: str = ""
    normalized_text_sha256: str = ""
    original_byte_length: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_record(self) -> dict:
        return {
            "text": self.text,
            "source_map": self.source_map,
            "parser": self.parser,
            "parser_version": self.parser_version,
            "format": self.format,
            "media_type": self.media_type,
            "original_sha256": self.original_sha256,
            "normalized_text_sha256": self.normalized_text_sha256,
            "original_byte_length": self.original_byte_length,
            "warnings": self.warnings,
        }


def _normalize_bytes(raw: bytes) -> bytes:
    """The SAME normalization as the pre-I0 intake path (identity.py
    normalize_document_bytes): BOM strip + CRLF normalize + NFC."""
    from polymath_shared.identity import normalize_document_bytes

    return normalize_document_bytes(raw)


def detect_format(media_type: str, source_name: str) -> Optional[str]:
    if media_type in TEXT_MEDIA_TYPES:
        return TEXT_MEDIA_TYPES[media_type]
    name = (source_name or "").lower()
    for ext, fmt in sorted(EXTENSION_FALLBACK.items(), key=lambda kv: -len(kv[0])):
        if name.endswith(ext):
            return fmt
    return None


def materialize(original_bytes: bytes, media_type: str, source_name: str = "") -> Materialization:
    """Deterministic materialization. Raises typed MaterializationError."""
    fmt = detect_format(media_type, source_name)
    if fmt is None:
        raise UnsupportedFormatError(
            f"unsupported document format: media_type={media_type!r} source={source_name!r}"
        )
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()

    if fmt == "text" or fmt == "markdown":
        text, source_map = _materialize_text(original_bytes, fmt)
        parser = f"{fmt}-codec"
    elif fmt == "html":
        text, source_map = _materialize_html(original_bytes)
        parser = "stdlib-html"
    elif fmt == "pdf":
        text, source_map = _materialize_pdf(original_bytes)
        parser = "pypdf"
    elif fmt == "epub":
        text, source_map = _materialize_epub(original_bytes)
        parser = "stdlib-zip-epub"
    elif fmt == "docx":
        text, source_map = _materialize_docx(original_bytes)
        parser = "stdlib-zip-docx"
    else:  # pragma: no cover — detect_format closes this
        raise UnsupportedFormatError(f"unsupported format {fmt!r}")

    if not text.strip():
        raise EmptyExtractionError(f"{fmt} extraction produced no text ({source_name})")
    if fmt in ("pdf", "epub", "docx"):
        yield_ratio = len(text) / max(len(original_bytes), 1)
        if len(text) < MIN_BINARY_CHARS or yield_ratio < MIN_TEXT_YIELD:
            raise LowYieldError(
                f"suspiciously low extracted text for {fmt}: {len(text)} chars "
                f"from {len(original_bytes)} bytes (yield {yield_ratio:.4f})"
            )

    return Materialization(
        text=text,
        source_map=source_map,
        format=fmt,
        media_type=media_type,
        original_sha256=original_sha256,
        normalized_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        original_byte_length=len(original_bytes),
        warnings=[],
    )


# ---------------------------------------------------------------------------
# TXT / Markdown
# ---------------------------------------------------------------------------

def _materialize_text(raw: bytes, fmt: str) -> tuple[str, list[dict]]:
    normalized = _normalize_bytes(raw)
    try:
        text = normalized.decode("utf-8")
    except UnicodeDecodeError:
        raise CorruptedDocumentError(f"{fmt} bytes are not valid UTF-8")
    text = text.replace("\u0000", "")
    source_map = [{
        "text_start": 0,
        "text_end": len(text),
        "kind": "document",
        "location": "whole-document",
        "label": "",
    }]
    return text, source_map


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_LIST_TAGS = {"ul", "ol", "dl"}
_ITEM_TAGS = {"li", "dt", "dd"}
_CELL_TAGS = {"td", "th"}
_PARA_TAGS = {"p", "div", "section", "article", "header", "footer", "main",
              "aside", "figure", "figcaption", "address", "hr"}


class _TextExtractor(HTMLParser):
    """Deterministic HTML -> markdown-shaped text.

    HTML-STRUCTURE-V1 (owner 2026-09-05, measured on handbook.html — 6,926
    <li>, 2,825 <tr>, 1,819 <pre>): the 1.0.0 extractor turned EVERY block
    tag (li, tr, td, br, pre lines) into its own paragraph, so the chunker
    — which splits on blank lines — emitted one child per list item /
    table cell / code line: 29 % of the children were under 60 chars and
    37 % were classed `stub` (a noise role that extraction and enrichment
    skip) against 1.6 % / 2 % for the same book as Markdown.

    The extractor now emits the structure the chunker already routes on
    (`chunker._WRAP_HARD_LINE`: "- ", "1. ", "#", "|", ">", 4-space code):
      * a list (nested or not) is ONE block of "- item" / "n. item" lines,
        nested levels indented two spaces per depth; <p> inside <li> is a
        line break, never a paragraph break;
      * a table is ONE block of "| c1 | c2 |" rows;
      * <pre> is ONE fenced code block (```), internal newlines and
        indentation preserved;
      * headings become "## Heading" lines in their own block;
      * <br> is a line break inside the current block;
      * <blockquote> lines are prefixed "> ";
      * script/style/head/noscript/template/svg are dropped; entities are
        unescaped; presentation whitespace collapses inside a line.
    Paragraph = blank-line separated block, exactly as Markdown input."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._lines: list[str] = []
        self._cur: list[str] = []
        self._prefix = ""
        self._item_open = False
        self.skip_depth = 0
        self.pre_depth = 0
        self.quote_depth = 0
        self.heading: int | None = None
        self._lists: list[dict] = []
        self._cells: list[str] | None = None      # open <tr>
        self._cell: list[str] | None = None       # open <td>/<th>

    # -- helpers -----------------------------------------------------
    def _line_prefix(self) -> str:
        pre = ""
        if self.heading:
            pre = "#" * self.heading + " "
        if self.quote_depth:
            pre = "> " * self.quote_depth + pre
        return pre + self._prefix

    def _end_line(self) -> None:
        raw = "".join(self._cur)
        self._cur = []
        if self.pre_depth:
            # <pre> becomes a fenced code block: the tier chunker's walker
            # recognises fences (not indentation) as an atomic code region.
            lines = raw.split("\n")
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            if lines:
                self._lines.append("```")
                for ln in lines:
                    self._lines.append(ln.rstrip())
                self._lines.append("```")
        else:
            text = _WS_RE.sub(" ", raw).strip()
            if text:
                self._lines.append(self._line_prefix() + text)
                if self._item_open:
                    # <li><p>a</p><p>b</p></li>: later lines hang under the item
                    self._prefix = " " * len(self._prefix)
                else:
                    self._prefix = ""
            # an empty flush (e.g. <li><p>) keeps the pending item prefix

    def _end_block(self) -> None:
        self._end_line()
        if self._lines:
            while self._lines and not self._lines[-1].strip():
                self._lines.pop()
            if self._lines:
                self.blocks.append("\n".join(self._lines))
            self._lines = []

    def _in_structure(self) -> bool:
        return bool(self._lists) or self._cells is not None or self.pre_depth > 0

    # -- parser events -----------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "br":
            if self._cell is not None:
                self._cell.append(" ")
            else:
                self._end_line()
        elif tag == "pre":
            self._end_block()
            self.pre_depth += 1
        elif tag in _HEADING_TAGS:
            self._end_block()
            self.heading = _HEADING_TAGS[tag]
        elif tag in _LIST_TAGS:
            if self._lists:
                self._end_line()               # nested: close the parent item line
                self._item_open = False
                self._prefix = ""
            else:
                self._end_block()
            self._lists.append({"kind": tag, "n": 0})
        elif tag in _ITEM_TAGS:
            self._item_open = False
            self._end_line()
            self._item_open = True
            depth = max(0, len(self._lists) - 1)
            top = self._lists[-1] if self._lists else {"kind": "ul", "n": 0}
            if tag == "dd":
                self._prefix = "  " * depth + "  "
            elif top["kind"] == "ol":
                top["n"] += 1
                self._prefix = "  " * depth + f"{top['n']}. "
            else:
                self._prefix = "  " * depth + "- "
        elif tag == "table":
            self._end_block()
        elif tag == "tr":
            self._end_line()
            self._cells = []
        elif tag in _CELL_TAGS:
            if self._cells is None:
                self._cells = []
            self._cell = []
        elif tag == "blockquote":
            self._end_block()
            self.quote_depth += 1
        elif tag in _PARA_TAGS:
            if self._in_structure():
                self._end_line()
            else:
                self._end_block()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "pre":
            self._end_block()
            self.pre_depth = max(0, self.pre_depth - 1)
        elif tag in _HEADING_TAGS:
            self._end_block()
            self.heading = None
        elif tag in _ITEM_TAGS:
            self._end_line()
            self._item_open = False
            self._prefix = ""
        elif tag in _LIST_TAGS:
            self._end_line()
            self._item_open = False
            self._prefix = ""
            if self._lists:
                self._lists.pop()
            if not self._lists:
                self._end_block()
        elif tag in _CELL_TAGS:
            if self._cell is not None:
                if self._cells is None:
                    self._cells = []
                self._cells.append(_WS_RE.sub(" ", "".join(self._cell)).strip())
                self._cell = None
        elif tag == "tr":
            if self._cell is not None:          # unterminated cell
                self.handle_endtag("td")
            if self._cells is not None:
                cells = self._cells
                self._cells = None
                if any(c for c in cells):
                    self._lines.append("| " + " | ".join(cells) + " |")
        elif tag == "table":
            if self._cells is not None:
                self.handle_endtag("tr")
            self._end_block()
        elif tag == "blockquote":
            self._end_block()
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag in _PARA_TAGS:
            if self._in_structure():
                self._end_line()
            else:
                self._end_block()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self._cell is not None:
            self._cell.append(data)
        else:
            self._cur.append(data)

    def close(self) -> None:  # type: ignore[override]
        super().close()
        if self._cell is not None:
            self.handle_endtag("td")
        if self._cells is not None:
            self.handle_endtag("tr")
        self._end_block()

    def text(self) -> str:
        return "\n\n".join(self.blocks)


def _materialize_html(raw: bytes) -> tuple[str, list[dict]]:
    try:
        decoded = raw.decode("utf-8", errors="replace")
    except Exception:
        raise CorruptedDocumentError("html bytes are not decodable")
    parser = _TextExtractor()
    try:
        parser.feed(decoded)
        parser.close()
    except Exception as exc:
        raise CorruptedDocumentError(f"html parse failed: {exc}")
    blocks = [b for b in parser.blocks if b.strip()]
    text = "\n\n".join(blocks)
    source_map: list[dict] = []
    pos = 0
    for i, block in enumerate(blocks):
        start = text.find(block, pos)
        if start < 0:
            start = pos
        end = start + len(block)
        source_map.append({"text_start": start, "text_end": end, "kind": "block",
                           "location": "html-block", "label": f"html-block#{i}"})
        pos = end
    return text, source_map


def _collapse_blocks(raw_text: str, kind: str, location: str) -> tuple[str, list[dict]]:
    """Collapse whitespace runs and produce per-paragraph segments with
    deterministic char ranges over the final normalized text."""
    paragraphs: list[str] = []
    for line in raw_text.split("\n"):
        line = _WS_RE.sub(" ", line).strip()
        if line:
            paragraphs.append(line)
    text = "\n\n".join(paragraphs)
    source_map: list[dict] = []
    pos = 0
    for i, para in enumerate(paragraphs):
        start = text.find(para, pos)
        if start < 0:
            start = pos
        end = start + len(para)
        source_map.append({
            "text_start": start,
            "text_end": end,
            "kind": kind,
            "location": location,
            "label": f"{location}#{i}",
        })
        pos = end
    return text, source_map


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _materialize_pdf(raw: bytes) -> tuple[str, list[dict]]:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        raise MaterializationError("pypdf is not installed (pinned dependency)")
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise CorruptedDocumentError(f"pdf open failed: {exc}")
    if reader.is_encrypted:
        raise EncryptedDocumentError("pdf is encrypted and cannot be materialized")
    pages: list[str] = []
    source_map: list[dict] = []
    cursor = 0
    for page_index, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            raise CorruptedDocumentError(f"pdf page {page_index} extraction failed: {exc}")
        page_text = _WS_RE.sub(" ", page_text).strip()
        if page_text:
            pages.append(page_text)
            source_map.append({
                "text_start": cursor,
                "text_end": cursor + len(page_text),
                "kind": "page",
                "location": f"page {page_index + 1}",
                "label": f"page {page_index + 1}",
            })
            cursor += len(page_text) + 2
    text = "\n\n".join(pages)
    return text, source_map


# ---------------------------------------------------------------------------
# EPUB
# ---------------------------------------------------------------------------

_NS_OPF = "{http://www.idpf.org/2007/opf}"
_NS_CNT = "{urn:oasis:names:tc:opendocument:xmlns:container}"


def _materialize_epub(raw: bytes) -> tuple[str, list[dict]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = set(zf.namelist())
            container_path = "META-INF/container.xml"
            if container_path not in names:
                raise CorruptedDocumentError("epub missing META-INF/container.xml")
            container = ElementTree.fromstring(zf.read(container_path))
            opf_href = None
            for rootfile in container.iter(f"{_NS_CNT}rootfile"):
                opf_href = rootfile.get("full-path")
            if not opf_href or opf_href not in names:
                raise CorruptedDocumentError("epub container does not name a readable OPF")
            opf_dir = opf_href.rsplit("/", 1)[0] if "/" in opf_href else ""
            opf = ElementTree.fromstring(zf.read(opf_href))

            manifest: dict[str, str] = {}
            for item in opf.iter(f"{_NS_OPF}item"):
                item_id = item.get("id")
                href = item.get("href")
                if item_id and href:
                    manifest[item_id] = href

            spine_ids: list[str] = []
            for itemref in opf.iter(f"{_NS_OPF}itemref"):
                spine_ids.append(itemref.get("idref") or "")

            chapters: list[str] = []
            source_map: list[dict] = []
            pos = 0
            for spine_id in spine_ids:
                href = manifest.get(spine_id)
                if not href:
                    continue
                full = f"{opf_dir}/{href}".strip("/") if opf_dir else href
                if full not in names:
                    raise CorruptedDocumentError(f"epub spine target missing: {full}")
                chapter_bytes = zf.read(full)
                chapter_text, _ = _materialize_html(chapter_bytes)
                chapter_text = chapter_text.strip()
                if chapter_text:
                    start = pos
                    chapters.append(chapter_text)
                    source_map.append({
                        "text_start": start,
                        "text_end": start + len(chapter_text),
                        "kind": "chapter",
                        "location": f"chapter {spine_id}",
                        "label": spine_id,
                    })
                    pos = start + len(chapter_text) + 2
    except zipfile.BadZipFile as exc:
        raise CorruptedDocumentError(f"epub is not a valid zip: {exc}")
    text = "\n\n".join(chapters)
    return text, source_map


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph_text(paragraph) -> tuple[str, Optional[str]]:
    runs: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_NS_W}t":
            runs.append(node.text or "")
        elif node.tag == f"{_NS_W}tab":
            runs.append(" ")
        elif node.tag == f"{_NS_W}br":
            runs.append("\n")
    style = None
    ppr = paragraph.find(f"{_NS_W}pPr")
    if ppr is not None:
        pstyle = ppr.find(f"{_NS_W}pStyle")
        if pstyle is not None:
            style = pstyle.get(f"{_NS_W}val")
    return "".join(runs), style


def _materialize_docx(raw: bytes) -> tuple[str, list[dict]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            if "word/document.xml" not in zf.namelist():
                raise CorruptedDocumentError("docx missing word/document.xml")
            root = ElementTree.fromstring(zf.read("word/document.xml"))
    except zipfile.BadZipFile as exc:
        raise CorruptedDocumentError(f"docx is not a valid zip: {exc}")

    body = root.find(f"{_NS_W}body")
    if body is None:
        raise CorruptedDocumentError("docx has no document body")

    sections: list[dict] = []
    current_section: Optional[str] = None
    for child in body:
        if child.tag != f"{_NS_W}p":
            continue
        text, style = _docx_paragraph_text(child)
        text = _WS_RE.sub(" ", text).strip()
        if not text:
            continue
        is_heading = bool(style and style.lower().startswith("heading"))
        label = style or "paragraph"
        if is_heading:
            current_section = text
        sections.append({
            "text": text,
            "kind": "heading" if is_heading else "paragraph",
            "section": current_section or "",
            "label": label,
        })

    paragraphs = [s["text"] for s in sections]
    text = "\n\n".join(paragraphs)
    source_map: list[dict] = []
    pos = 0
    for i, para in enumerate(paragraphs):
        start = text.find(para, pos)
        if start < 0:
            start = pos
        end = start + len(para)
        source_map.append({
            "text_start": start,
            "text_end": end,
            "kind": sections[i]["kind"],
            "location": sections[i]["section"] or "paragraph",
            "label": sections[i]["label"],
        })
        pos = end
    return text, source_map
