"""DOCUMENT-GROUNDING-CONTEXT-V1 (RAG-PIPELINE-FINISH Phase 5).

A universal, deterministic, CPU-only document ORIENTATION for the parent-map (pMAP)
request — roughly 50-100 tokens of reliable title / author / type / top-level
structure, derived ONLY from source/metadata evidence. It gives the mapping model
the whole-document framing a single parent skeleton cannot, WITHOUT depending on the
LLM Document Profile (plan frozen decision §1.6 / Phase 5).

Design laws (mirror the surrounding deterministic policy in this package):

* **Source-derived only** — title/author/type from the document's frontmatter +
  filename; the outline from the parents' own heading paths (furniture removed).
  No summary is invented, no model is called, no store is touched.
* **Deterministic** — same (document, parents) => same context and same
  ``context_hash``; the hash enters the pMAP generation/batch identity (Phase 6)
  so an old skeleton-only map cannot satisfy the new grounded generation.
* **Bounded** — a hard token budget (~50-100) that is NEVER exceeded; the outline
  is trimmed first, then the byline, and the title is protected (trimmed last).
* **Degrades gracefully** — missing title falls back to the cleaned filename then
  a short title-like first line; missing author/structure are simply omitted;
  OCR/boilerplate noise is rejected, not surfaced, and can never crowd out a
  high-confidence title.

Reuses the deterministic helpers already proven in ``context.py`` (``clean_title``,
``structure_lines``, ``est_tokens``, ``_trim_tokens``) so grounding and the profile
context share one title/structure derivation — no second, divergent parser.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from polymath_shared.document_profile.context import (
    clean_title,
    est_tokens,
    structure_lines,
    _trim_tokens,
)

GROUNDING_CONTEXT_VERSION = "grounding-context-v1"

DEFAULT_BUDGET_TOKENS = 90          # target band 50-100; hard ceiling enforced at build
_TITLE_MIN_TOKENS = 6               # the title is protected down to this floor
_BYLINE_MAX_TOKENS = 16
_TYPE_MAX_TOKENS = 4
_MAX_ANCHORS = 12                   # never more than this many outline anchors
_MIN_ANCHOR_LETTERS = 3

_WS_RE = re.compile(r"\s+")
# a title-like first line: short, no sentence-terminal punctuation, mostly letters
_TITLE_LINE_MAX_WORDS = 14


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_noise(segment: str) -> bool:
    """Reject an outline anchor that is OCR/boilerplate noise: too few letters, or
    mostly non-alphabetic (page numbers, garbled runs, rule lines)."""
    s = (segment or "").strip()
    letters = sum(ch.isalpha() for ch in s)
    if letters < _MIN_ANCHOR_LETTERS:
        return True
    if letters < max(3, len(s) // 2):
        return True
    return False


def _byline(fm: dict) -> str:
    """Author / organization / publisher from frontmatter, first available, cleaned."""
    for key in ("author", "authors", "organization", "publisher"):
        v = fm.get(key)
        if not v:
            continue
        text = v if isinstance(v, str) else ", ".join(str(x) for x in v if str(x).strip())
        text = _WS_RE.sub(" ", str(text)).strip(" ,·-")
        if text:
            return text
    return ""


def _doc_type(document: dict, fm: dict) -> str:
    mt = str(document.get("media_type") or "")
    if mt:
        return mt.split("/")[-1]
    for key in ("type", "document_type"):
        v = fm.get(key)
        if v:
            return str(v).strip()
    return ""


def _title_like_first_line(parents: Sequence[dict]) -> str:
    """A short, heading-like opening line — the graceful fallback for plain text with
    a title on line 1 and no frontmatter. Deterministic: the first body parent's
    first non-empty line, only if it is short and not a full sentence."""
    ordered = sorted(
        (p for p in parents if str(p.get("text") or "").strip()),
        key=lambda r: (r.get("chunk_index") is None, r.get("chunk_index") or 0, r.get("char_start") or 0),
    )
    if not ordered:
        return ""
    raw = str(ordered[0].get("text") or "")
    # split on the ORIGINAL newline first, THEN collapse whitespace within the line.
    line = _WS_RE.sub(" ", raw.split("\n", 1)[0]).strip()
    # take the leading clause up to a sentence break
    head = re.split(r"(?<=[.!?])\s", line)[0].strip()
    words = head.split()
    if not words or len(words) > _TITLE_LINE_MAX_WORDS:
        return ""
    if head.endswith((".", "!", "?")):        # a full sentence is not a title
        return ""
    letters = sum(ch.isalpha() for ch in head)
    if letters < max(3, len(head) // 2):
        return ""
    return head


def _alpha(s: str) -> str:
    """Lowercased letters-only signature (digits/punctuation → spaces, collapsed) —
    used to detect a running header that merely echoes the document title."""
    return _WS_RE.sub(" ", re.sub(r"[^A-Za-zÀ-ɏ]+", " ", s or "")).strip().lower()


def _outline_anchors(parents: Sequence[dict], title: str = "") -> list[str]:
    """Top-level document sections: distinct FIRST segments of the furniture-filtered
    heading paths, in document order. Rejects OCR/rule-line noise and running headers
    that echo the document title. A flat/transcript document yields none."""
    title_sig = _alpha(title)
    seen: set[str] = set()
    anchors: list[str] = []
    for line in structure_lines(parents):
        # the FIRST meaningful segment of the path: skip OCR/page-noise or a running
        # header that echoes the title, so a real heading behind noise is not lost.
        top = ""
        for seg in (s.strip() for s in line.split(" › ")):
            if not seg or _is_noise(seg):
                continue
            if title_sig and title_sig in _alpha(seg):
                continue
            top = seg
            break
        if not top:
            continue
        key = top.lower()
        if key in seen:
            continue
        seen.add(key)
        anchors.append(top)
        if len(anchors) >= _MAX_ANCHORS:
            break
    return anchors


@dataclass(frozen=True)
class DocumentGroundingContextV1:
    """Bounded, source-derived document orientation for the pMAP prompt."""

    title: str
    byline: str
    doc_type: str
    anchors: tuple[str, ...]
    budget_tokens: int
    version: str = GROUNDING_CONTEXT_VERSION
    context_hash: str = ""

    def render(self) -> str:
        """The compact block injected AHEAD of the ParentSkeleton data in the pMAP
        prompt. Only present surfaces are emitted."""
        lines = [f"DOCUMENT: {self.title}"]
        if self.byline:
            lines.append(f"BY: {self.byline}")
        if self.doc_type:
            lines.append(f"TYPE: {self.doc_type}")
        if self.anchors:
            lines.append("OUTLINE: " + " · ".join(self.anchors))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "title": self.title, "byline": self.byline,
                "doc_type": self.doc_type, "anchors": list(self.anchors),
                "budget_tokens": self.budget_tokens, "context_hash": self.context_hash}


def _hash_fields(title: str, byline: str, doc_type: str, anchors: tuple[str, ...]) -> str:
    payload = "\x1f".join([GROUNDING_CONTEXT_VERSION, title, byline, doc_type, "\x1e".join(anchors)])
    return _sha256(payload)


def build_grounding_context(
    document: dict,
    parents: Sequence[dict],
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> DocumentGroundingContextV1:
    """Build the deterministic grounding context.

    ``document``: {source_name, media_type, frontmatter?}; ``parents``: the
    document's parent rows {heading_path, text, chunk_index, char_start, region_role?}
    in any order. Same inputs => identical context + hash.
    """
    fm = document.get("frontmatter") or {}
    title = str(fm.get("title") or "").strip()
    if not title:
        # no authored frontmatter title: a title-like FIRST LINE (human-authored) beats
        # the filename; fall back to the cleaned filename, then a literal placeholder.
        title = _title_like_first_line(parents) or clean_title(document.get("source_name") or "") or "untitled"
    if _is_noise(title):
        title = clean_title(document.get("source_name") or "") or "untitled"
    title = _WS_RE.sub(" ", title).strip()

    byline = _trim_tokens(_byline(fm), _BYLINE_MAX_TOKENS)
    doc_type = _trim_tokens(_doc_type(document, fm), _TYPE_MAX_TOKENS)
    anchors = _outline_anchors(parents, title)

    # ---- hard budget: title protected, trim outline then byline then type ---------
    def total(t: str, b: str, ty: str, anc: list[str]) -> int:
        g = DocumentGroundingContextV1(title=t, byline=b, doc_type=ty, anchors=tuple(anc),
                                       budget_tokens=budget_tokens)
        return est_tokens(g.render())

    # the title itself is trimmed only if it alone exceeds the budget (rare).
    if est_tokens(f"DOCUMENT: {title}") > budget_tokens:
        title = _trim_tokens(title, max(_TITLE_MIN_TOKENS, budget_tokens - 2))

    while anchors and total(title, byline, doc_type, anchors) > budget_tokens:
        anchors.pop()                                  # drop the least-important trailing anchor
    if total(title, byline, doc_type, anchors) > budget_tokens and byline:
        byline = ""
    if total(title, byline, doc_type, anchors) > budget_tokens and doc_type:
        doc_type = ""

    anchors_t = tuple(anchors)
    return DocumentGroundingContextV1(
        title=title, byline=byline, doc_type=doc_type, anchors=anchors_t,
        budget_tokens=budget_tokens,
        context_hash=_hash_fields(title, byline, doc_type, anchors_t),
    )
