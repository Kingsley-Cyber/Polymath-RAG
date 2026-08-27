"""REGION-POLICY-V1 — deterministic source-region classification.

Which part of a book is this span standing in? Body prose asserts
things; an index line, a reference entry, a running heading and a figure
caption do not, even though all four contain real words that retrieval
must keep reachable.

Persisted layout evidence (`document_layout`, LAYOUT-EVIDENCE-V1) is the
first authority, but it is thin in practice — on the 25-book corpus it
covers 13 of 25 documents and records only `heading`. So this module
adds deterministic STRUCTURAL classification derived from the immutable
chunk text: no model, no probability, no corpus-specific phrase lists —
only shape (line geometry, punctuation regularity, numeric density).

Classification is computed ONCE per chunk and reused for every candidate
in it (the 289M-regex episode is not repeated).
"""

from __future__ import annotations

import functools
import re
from typing import Iterable, Optional

REGION_POLICY_VERSION = "region-policy-v1"

BODY_PROSE = "BODY_PROSE"
BIBLIOGRAPHY = "BIBLIOGRAPHY"
INDEX = "INDEX"
TABLE_OF_CONTENTS = "TABLE_OF_CONTENTS"
CAPTION = "CAPTION"
HEADING = "HEADING"
CODE_OR_CONFIG = "CODE_OR_CONFIG"

# --- shape signals ---------------------------------------------------------

# "(1998)" / "(2001)" and the OCR-mangled "~2000!" seen in scanned papers
_YEAR_CITE = re.compile(r"[~(\[]\s*(1[89]\d{2}|20\d{2})[a-z]?\s*[!)\]]")
# "Nakamura, H.," / "Kleppmann, M."
_AUTHOR_INITIAL = re.compile(r"[A-Z][a-zA-Z’'\-]+,\s+(?:[A-Z]\.\s*){1,3}")
# index entry: "process monitor, 484" / "sockets, 122–130, 145"
_INDEX_LINE = re.compile(r"^\s*\S[^,]{0,60},\s*\d+(?:\s*[–—-]\s*\d+)?"
                         r"(?:\s*,\s*\d+(?:\s*[–—-]\s*\d+)?)*\s*$")
# toc line: dot leaders or trailing page number after a title
_TOC_LINE = re.compile(r"^\s*.{3,70}?(?:\.{3,}|\s{3,})\s*\d{1,4}\s*$")
_CHAPTER_LINE = re.compile(r"^\s*(?:chapter|part|appendix)\s+[\dIVXLC]+\b", re.I)
# caption: "Figure 4-7. …" / "Table 13.7 …" / "Listing 2-1:"
_CAPTION_LINE = re.compile(r"^\s*(figure|fig\.|table|listing|example|exhibit|"
                           r"algorithm|equation)\s*[\d]+(?:[.\-–]\d+)*\s*[.:—–]?",
                           re.I)
# code/config: shell prompts, key:value config lines (bare or as list
# items), calls, braces, declaration keywords. Deliberately NOT a plain
# "- " bullet: prose bullet lists are body text, not config.
_CODE_LINE = re.compile(r"^\s*(?:[$#>]\s"
                        r"|(?:-\s+)?[\w.\-]+\s*:\s*(?:\S.*)?$"
                        r"|[\w.]+\("
                        r"|[{}\[\]<]"
                        r"|(?:def|class|import|from|function|var|const|let|SELECT|"
                        r"public|private|return)\b)")


# Line-independent signals. Chunk text is NORMALIZED: newlines are often
# stripped, so an index page arrives as one flowing line
# ("dialog in Process Monitor, 484 exploits, 245 filters ... 588").
# Iteration 1 admitted part_of(process, ida pro) from exactly that. Shape
# must therefore also be detectable without line geometry — the same
# lesson LAYOUT-EVIDENCE-V1 recorded: layout cannot be recovered from
# normalized text, so structure has to be measured, not assumed.
_PAGE_REF = re.compile(r",\s*\d{1,4}(?:\s*[–—-]\s*\d{1,4})?(?=[\s,.;]|$)")
_TABLE_CELL = re.compile(r"\b[A-Z]{1,3}\d{2,5}\s*,")
# Bibliographic furniture: volume/number/pages/doi/isbn/proceedings.
_CITATION_FURNITURE = re.compile(
    r"\b(?:volume|vol\.|number|no\.|pages|pp\.|doi|isbn|issn|"
    r"proceedings|journal|conference|symposium|eds?\.|edition)\b", re.I)


def _page_ref_density(text: str) -> float:
    """Comma-then-page-number references per 100 words."""
    words = max(len(text.split()), 1)
    return 100.0 * len(_PAGE_REF.findall(text)) / words


def _lines(text: str) -> list[str]:
    return text.split("\n")


def _ratio(pred, items: Iterable[str]) -> float:
    items = [i for i in items if i.strip()]
    if not items:
        return 0.0
    return sum(1 for i in items if pred(i)) / len(items)


@functools.lru_cache(maxsize=4096)
def classify_chunk(text: str) -> str:
    """Whole-chunk region. Cached by text (chunks are immutable)."""
    if not text or not text.strip():
        return BODY_PROSE
    lines = _lines(text)
    non_empty = [ln for ln in lines if ln.strip()]

    # Bibliography: dense citation shapes anywhere in the chunk.
    if (len(_YEAR_CITE.findall(text)) >= 4
            or len(_AUTHOR_INITIAL.findall(text)) >= 5
            # A single dense reference line ("Nancy Lynch and Alex
            # Shvartsman: 'Robust Emulation ...' Journal of the ACM,
            # volume 42, number 1, pages 124-142") carries the same
            # citation furniture without repeating it four times.
            or len(_CITATION_FURNITURE.findall(text)) >= 3):
        return BIBLIOGRAPHY

    # newline-independent: dense page references are an index/TOC page
    # whichever way the chunker normalized the whitespace.
    # Both a COUNT and a DENSITY floor: prose quotes figures too
    # ("In 2019, 45 percent ... by 2021, 60 percent"), but rarely four
    # times in one chunk at index density.
    if (len(_PAGE_REF.findall(text)) >= 4
            and _page_ref_density(text) >= 6.0
            and len(text.split()) >= 15):
        return INDEX
    if len(_TABLE_CELL.findall(text)) >= 3:
        return CODE_OR_CONFIG

    if len(non_empty) >= 4:
        if _ratio(lambda l: bool(_INDEX_LINE.match(l)), non_empty) >= 0.4:
            return INDEX
        if (_ratio(lambda l: bool(_TOC_LINE.match(l)), non_empty) >= 0.4
                or _ratio(lambda l: bool(_CHAPTER_LINE.match(l)), non_empty) >= 0.5):
            return TABLE_OF_CONTENTS
        if _ratio(lambda l: bool(_CODE_LINE.match(l)), non_empty) >= 0.5:
            return CODE_OR_CONFIG

    # A single-line chunk that is short and unpunctuated reads as a heading.
    if len(non_empty) == 1 and len(non_empty[0]) <= 80 and not non_empty[0].rstrip().endswith("."):
        return HEADING
    return BODY_PROSE


def _line_bounds(text: str, offset: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return start, (len(text) if end == -1 else end)


def region_at(chunk_text: str, span_start: int, span_end: int,
              layout_spans: Optional[list[tuple[str, int, int]]] = None,
              chunk_char_start: int = 0) -> str:
    """Region governing one span.

    Order of authority:
      1. persisted layout evidence covering the span (LAYOUT-EVIDENCE-V1);
      2. whole-chunk structure (bibliography / index / toc / code);
      3. the span's own line (caption).
    """
    if layout_spans:
        abs_s = chunk_char_start + span_start
        abs_e = chunk_char_start + span_end
        for kind, lo, hi in layout_spans:
            if lo <= abs_s and abs_e <= hi:
                if kind == "heading":
                    return HEADING
                if kind in ("caption", "figure"):
                    return CAPTION

    chunk_region = classify_chunk(chunk_text)
    if chunk_region != BODY_PROSE:
        return chunk_region

    lo, hi = _line_bounds(chunk_text, span_start)
    line = chunk_text[lo:hi]
    if _CAPTION_LINE.match(line):
        return CAPTION
    if _INDEX_LINE.match(line):
        return INDEX
    return BODY_PROSE
