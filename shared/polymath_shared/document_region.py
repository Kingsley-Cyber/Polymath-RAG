"""DOCUMENT-REGION-V1: deterministic document-role classification.

WHY THIS EXISTS
---------------
Semantic similarity cannot separate "text ABOUT a book" from "text OF a
book". MEASURED on cysa-study-v1 for the query "what are all the domains
and subdomains of CySA+":

    author biography chunk   cosine 0.5955   (ranked #1 after rerank)
    correct objectives map   cosine 0.4894   (demoted to #7)

The boilerplate is MORE similar than the answer, because it is dense in
the query's vocabulary ("CySA+", "exam", "domains", "CS0-003") while
carrying none of its content. No global score threshold can fix that —
any floor that removes the biography removes the answer first. The
missing signal is DOCUMENT ROLE, not relevance.

WHY CONTENT, NOT POSITION
-------------------------
v3.3 classified primarily by heading path. That does not transfer: v4's
production chunker (legacy_v1) never writes `heading_path` (0 of 7,085
children), and the recoverable `document_layout` headings are 5,130 page
markers to 2,138 semantic headings, with text recovery lossy where a
heading straddles a chunk boundary.

More decisively, position is the WRONG signal here. The author biography
and the CS0-003 objectives map sit in the SAME front-matter region of the
same book — both resolve to the copyright heading. Classifying by
position would suppress the correct answer. Classifying by content
separates them cleanly: one is a person's credentials, the other is a
numbered objectives list.

PRECISION DOCTRINE (PHASE C)
----------------------------
False suppression of real technical content is worse than leaving some
boilerplate in place. Therefore:

  - every rule demands STRUCTURAL evidence (line shape, ratios,
    anchored position in the chunk), never bare token occurrence;
  - "References to the Windows registry", "Index structures in
    databases", "Appendix exploitation techniques" and friends must
    classify BODY;
  - anything unproven is BODY. UNKNOWN is reserved for empty text.

APPENDIX is deliberately NOT a suppressed role in v4. v3.3 excluded it;
technical appendices in this corpus carry real evidence (objectives
maps, port tables, command references), so inheriting that exclusion
would suppress answers. Measured decision, not an inherited default.

ROLE IS METADATA, NEVER TRUTH. Classification never alters child text,
never deletes a chunk, and never removes anything from the index. It
only lets default retrieval prefer answer-bearing regions, while
explicit metadata questions ("who wrote this book?") can still reach the
suppressed regions.
"""
from __future__ import annotations

import re

CONTRACT = "document-region-v1"

# ---------------------------------------------------------------- roles
ROLE_BODY = "body"
ROLE_FRONT_MATTER = "front_matter"
ROLE_MARKETING = "marketing"
ROLE_TOC = "toc"
ROLE_INDEX = "index"
ROLE_BIBLIOGRAPHY = "bibliography"
ROLE_OCR_NOISE = "ocr_noise"
ROLE_UNKNOWN = "unknown"

#: Roles demoted out of DEFAULT retrieval. Everything here is still
#: stored, still embedded, still indexed, and still reachable by an
#: explicit document-metadata question.
NOISY_ROLES = (ROLE_FRONT_MATTER, ROLE_MARKETING, ROLE_TOC,
               ROLE_INDEX, ROLE_BIBLIOGRAPHY, ROLE_OCR_NOISE)

#: Never demoted. BODY is the default; UNKNOWN means "no text to judge"
#: and is treated as retrievable so an empty classifier can never
#: suppress a corpus.
RETRIEVABLE_ROLES = (ROLE_BODY, ROLE_UNKNOWN)

# ------------------------------------------------------------ detectors

#: A person's credentials block. Requires a credential/role phrase AND a
#: biographical predicate — "about privilege escalation" and "About the
#: publisher's threat model" must not match.
_BIO_CREDENTIALS = re.compile(
    r"\b(MCSE|CISSP|CASP\+|OSCP|CEH|PMP|Ph\.?D|M\.?Sc)\b")
_BIO_PREDICATE = re.compile(
    r"\b(is|was)\s+(a|an|the)\s+[^.]{0,60}\b"
    r"(consultant|trainer|author|instructor|editor|speaker|professor|"
    r"engineer|architect|analyst|researcher|founder)\b", re.I)
_BIO_HEADING = re.compile(
    r"(?im)^\s{0,3}#{0,6}\s*about\s+the\s+"
    r"(author|authors|technical\s+editor|editor|reviewers?|contributors?)\s*$")

#: Publisher promotion. Anchored on transactional phrasing that prose
#: about a subject never uses.
_MARKETING = re.compile(
    r"\b(companion volume to|we highly recommend that you use|"
    r"register your book|why subscribe|share your thoughts|"
    r"leave a review|join our (book'?s |community'?s )?discord|"
    r"download the (example|code|colou?r)|code bundle|"
    r"dramatically increase your chances|online test bank|"
    r"visit (our|the) website to (register|download))\b", re.I)

#: Copyright / imprint block.
_IMPRINT = re.compile(
    r"\b(all rights reserved|no part of this publication may be "
    r"reproduced|published simultaneously in|library of congress "
    r"cataloging|ISBN[-:\s]*[\dXx][-\dXx\s]{8,})\b", re.I)

#: Front-matter section openers. The keyword must be the WHOLE heading
#: line — not a sentence opener. Without the end-anchor, "Preface
#: attacks manipulate the leading bytes..." was suppressed as front
#: matter (caught by the adversarial suite before this ever shipped).
_FRONT_HEADING = re.compile(
    r"(?im)^\s{0,3}#{0,6}\s*"
    r"(acknowledg(e)?ments?|dedication|preface|foreword|colophon)"
    r"\s*:?\s*$")

#: Dot-leader tables of contents, or numbered front-of-book entries.
#: A BARE trailing number is not enough — index entries ("encryption,
#: 15, 60") end that way too, and were being mislabelled TOC.
_TOC_LINE = re.compile(
    r"(\.{3,}\s*\d+\s*$)"
    r"|(?i:^\s*(chapter|part|section|appendix)\s+[\dIVXLC]+\b.*\s\d+\s*$)")
_TOC_HEADING = re.compile(
    r"(?is)\A\s*#{0,6}\s*(table\s+of\s+contents|contents)\s*$", re.M)

#: Index entries: "term, 12, 45-47" — comma then page runs.
_INDEX_LINE = re.compile(
    r"^\s*[A-Za-z][A-Za-z\s,'&/\-]{1,44},\s*\d+(?:[\s,\-–]+\d+)*\s*$")

#: Bibliography entries: author-initial or numbered-citation shapes.
_REF_AUTHOR = re.compile(r"[A-Z][a-zA-Z'’\-]+,\s+(?:[A-Z]\.\s*){1,3}")
_REF_NUMBERED = re.compile(r"(?m)^\s*\[\d+\]\s+[A-Z]")
_REF_STRONG = re.compile(
    r"\b(In:\s|Proceedings of\b|arXiv:\s?\d|doi:\s*10\.\d{4})", re.I)

#: v4-specific: the materializer's OCR failure placeholder.
_OCR_FALLBACK = re.compile(r"OCR_FALLBACK|OCR could not extract", re.I)


#: POSITIVE-CONTENT OVERRIDE. A chunk that carries structured
#: answer-bearing content is BODY no matter what boilerplate shares the
#: page with it. MEASURED: the CS0-003 objectives-map chunk OPENS with
#: "...dramatically increase your chances of passing" and only then
#: reaches "1.1 Explain the importance of...". The marketing rule fired
#: on it in the live corpus, which would have suppressed the exact
#: answer this whole mission exists to protect. Boilerplate phrases
#: describe a chunk's packaging; enumerated structure proves it carries
#: content.
_STRUCTURED_CONTENT = re.compile(r"\b\d+\.\d+\s+[A-Z][a-z]")
_MIN_STRUCTURED_HITS = 2


def _has_answer_bearing_structure(text: str) -> bool:
    return len(_STRUCTURED_CONTENT.findall(text)) >= _MIN_STRUCTURED_HITS


def _lines(text: str) -> list[str]:
    return [ln for ln in (l.strip() for l in text.splitlines()) if ln]


def classify_region(text: str) -> tuple[str, str]:
    """Classify one chunk's document role from its TEXT ALONE.

    Returns (role, reason). Defaults to BODY: a rule fires only on
    structural evidence, so unproven content stays retrievable.
    """
    raw = text or ""
    if not raw.strip():
        return ROLE_UNKNOWN, "empty"

    # OCR placeholders carry no recoverable evidence at all.
    if _OCR_FALLBACK.search(raw):
        return ROLE_OCR_NOISE, "ocr_fallback_placeholder"

    # Precision gate: structured content outranks every boilerplate
    # rule below. Runs before them, never after.
    if _has_answer_bearing_structure(raw):
        return ROLE_BODY, "answer_bearing_structure_override"

    lines = _lines(raw)
    n = len(lines)

    # --- author biography: credentials AND a biographical predicate,
    #     or an explicit "About the Author" heading line.
    if _BIO_HEADING.search(raw):
        return ROLE_FRONT_MATTER, "about_the_author_heading"
    if _BIO_CREDENTIALS.search(raw) and _BIO_PREDICATE.search(raw):
        return ROLE_FRONT_MATTER, "credentials_plus_biographical_predicate"

    if _IMPRINT.search(raw):
        return ROLE_FRONT_MATTER, "imprint_or_copyright_block"
    if _FRONT_HEADING.search(raw):
        return ROLE_FRONT_MATTER, "front_matter_section_opener"

    if _MARKETING.search(raw):
        return ROLE_MARKETING, "publisher_promotion_phrase"

    # --- structural block detectors need enough lines to have a shape
    if n >= 5:
        # INDEX before TOC: index entries are the more specific shape
        # (term + comma + page runs) and were shadowed by the looser
        # TOC rule.
        idx_hits = sum(1 for ln in lines if _INDEX_LINE.match(ln))
        if idx_hits / n >= 0.45:
            return ROLE_INDEX, f"index_page_list_lines {idx_hits}/{n}"
        toc_hits = sum(1 for ln in lines if _TOC_LINE.search(ln))
        if toc_hits / n >= 0.45:
            return ROLE_TOC, f"dot_leader_or_chapter_page_lines {toc_hits}/{n}"
        ref_signals = (len(_REF_AUTHOR.findall(raw))
                       + len(_REF_NUMBERED.findall(raw))
                       + len(_REF_STRONG.findall(raw)))
        if ref_signals >= 4:
            return ROLE_BIBLIOGRAPHY, f"reference_entry_signals {ref_signals}"

    if _TOC_HEADING.search(raw) and n >= 5:
        return ROLE_TOC, "contents_heading_with_list_shape"

    return ROLE_BODY, "default_body"


def is_noisy(role: str | None) -> bool:
    """True when a role is demoted from DEFAULT retrieval.

    Unknown/absent roles are NEVER noisy: a chunk ingested before this
    contract existed must keep competing normally (the legacy-safety
    rule v3.3 also enforced by filtering with must_not rather than
    must-equal-body)."""
    return role in NOISY_ROLES
