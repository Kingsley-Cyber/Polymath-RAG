"""LAYOUT-EVIDENCE-V1 — where a span sits in the document's typography.

Layout is not semantics. A publisher capitalizes headings as a house style,
and that typography must never be read as evidence about what a phrase
refers to:

    layout-induced capitalization  !=  semantic identity evidence

This module answers exactly one question — is this span inside a heading —
and answers it from real line structure, never from the span's own shape.
Deciding "looks like a title" from the phrase itself would reintroduce the
capitalization heuristic this exists to remove.

Recognized heading forms are deliberately narrow and syntactic: ATX
markdown headings (`## Working Memory`) and setext underlines (`====`,
`----`). A prose line that merely happens to be short and capitalized is
NOT treated as a heading; guessing there would suppress real identity in
ordinary text, which is the more costly error.
"""
from __future__ import annotations

import re

LAYOUT_CONTRACT = "layout-evidence-v1"

_ATX = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S", re.M)
_SETEXT_RULE = re.compile(r"^[ \t]{0,3}(=+|-{2,})[ \t]*$")


def project_regions(regions: list[tuple[int, int]],
                    doc_start: int, doc_end: int,
                    chunk_start: int) -> list[tuple[int, int]]:
    """Translate document-offset regions into chunk-relative coordinates for
    ONE contiguous piece of source text.

    Chunk text is assembled by joining sentences with a single space, so a
    chunk is NOT a contiguous slice of the document and offsets drift across
    sentence boundaries. Within one sentence the mapping is exact, which is
    why the caller projects per sentence rather than per chunk.

    Sentence granularity would not be enough on its own: a heading with no
    terminal punctuation is merged with the following prose into a single
    sentence, so a region is clipped to the sentence and projected at
    character level.
    """
    out: list[tuple[int, int]] = []
    for r_start, r_end in regions:
        lo, hi = max(r_start, doc_start), min(r_end, doc_end)
        if lo < hi:
            out.append((chunk_start + (lo - doc_start),
                        chunk_start + (hi - doc_start)))
    return out


def heading_regions(text: str) -> list[tuple[int, int]]:
    """Character regions of `text` that are heading lines, as [start, end).

    MUST be called on text that still has its line structure — the
    materialized source document. Calling it on assembled chunk text is the
    defect this contract exists to prevent: chunk text has no newlines, so a
    leading `###` makes the whole chunk look like one heading.
    """
    regions: list[tuple[int, int]] = []
    offset = 0
    lines = text.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        end = offset + len(stripped)
        if _ATX.match(line):
            regions.append((offset, end))
        elif stripped.strip() and idx + 1 < len(lines) and _SETEXT_RULE.match(
                lines[idx + 1].rstrip("\r\n")):
            regions.append((offset, end))
        offset += len(line)
    return regions


def in_heading(regions: list[tuple[int, int]], start: int, end: int) -> bool:
    """Does [start, end) fall inside any heading region?"""
    return any(s <= start and end <= e for s, e in regions)


def independently_capitalized(token_text: str) -> bool:
    """Is this token's capitalization UNEXPLAINABLE by title-casing?

    Title-casing a word produces `Xxxxx` — one leading capital and nothing
    else. So a capital anywhere after the first character, or an all-caps
    token, is evidence the writer chose that form, not the layout:

        Working     -> False   title-case could have produced this
        Memory      -> False
        PostgreSQL  -> True    internal capitals survive lowercasing a title
        GLiNER      -> True
        NIST        -> True
    """
    core = re.sub(r"[^A-Za-z]", "", token_text)
    if len(core) < 2:
        return False
    return core.isupper() or any(ch.isupper() for ch in core[1:])
