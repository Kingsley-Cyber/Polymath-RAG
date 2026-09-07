"""COMPILER-CORPUS-CONTEXT-V1 (backlog B16, owner design 2026-09-07).

The query compiler used to be told one thing about the corpus — its id. It
had never seen a title, so its ADJACENT query was a domain-neutral guess.
This module ranks the corpus's DOCUMENTS for the current message and
returns their TITLES (never summaries — the owner's rule) for the compiler
prompt: the model sees which books exist, most relevant first, and can write
its queries in the library's own vocabulary.

Ranking is by CONTENT, not title words (owner refinement): the top section
summaries for the message, backward-mapped to documents through the same
RRF vote lane A uses (`aggregate_documents_n`), plus a document-summary
vote when the caller supplies one. Ranked documents come first; the rest
of the library fills up to `top_n` in a stable alphabetical order, so a
small corpus is shown whole and a large one is shown by relevance. A pure
module: the caller runs the searches (dense by default — one message
embedding, ranks by meaning; or the 80 ms lexical BM25 route) and hands the
rows in.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from polymath_shared.pass1 import (
    REPRESENTATION_KIND_DOCUMENT_SUMMARY,
    REPRESENTATION_KIND_SECTION_SUMMARY,
    LaneHit,
    aggregate_documents_n,
)

CONTRACT = "compiler-corpus-context-v1"
DEFAULT_TOP_N = 40
RRF_K = 60                        # the same reciprocal-rank constant lane A fuses with (pass1 `_rrf_score`)
RANK_SPARSE = "sparse"
RANK_DENSE = "dense"
RANK_OVERLAP = "overlap"          # the fallback: question words against titles (no index needed)
RANK_MODES = (RANK_SPARSE, RANK_DENSE)
MAX_TITLE_CHARS = 90

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_SUFFIX_RE = re.compile(r"(?:\s*\d+)?(?:_[0-9a-f]{6,}|\s*\(\d+\))+$", re.IGNORECASE)   # " 1_9e6b68fb", " (1)"
_EXT_RE = re.compile(r"\.(md|html?|pdf|epub|txt|docx?)$", re.IGNORECASE)
_BRACKET_NOISE_RE = re.compile(r"\[[^\]]{0,80}\]|\{[^}]{0,40}\}")            # "[10.1080_…]", "{45131196}"
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}")
_STOP = frozenset({"the", "and", "for", "with", "what", "does", "book", "books", "say", "about", "how", "from",
                   "into", "that", "this", "are", "was", "were", "you", "your", "not", "but", "have", "has"})


@dataclass(frozen=True)
class TitlesKnobs:
    top_n: int = DEFAULT_TOP_N
    rank: str = RANK_DENSE
    section_hits: int = 0            # 0 → max(200, 12 × top_n)
    document_hits: int = 0           # 0 → top_n

    @property
    def enabled(self) -> bool:
        return self.top_n > 0

    @property
    def section_limit(self) -> int:
        return self.section_hits or max(200, 12 * self.top_n)

    @property
    def document_limit(self) -> int:
        return self.document_hits or max(1, self.top_n)

    def to_dict(self) -> dict[str, Any]:
        return {"top_n": self.top_n, "rank": self.rank, "section_hits": self.section_limit,
                "document_hits": self.document_limit}


def titles_knobs(env: dict | None = None) -> TitlesKnobs:
    """POLYMATH_CHAT_COMPILER_TITLES_TOP_N (0 = off) and _RANK (dense | sparse). Default dense (measured 2026-09-07:
    the only ranker that put the Laban Workbook in front of the compiler for a camera question — it ranks by meaning,
    at the cost of one message embedding on the compile path); sparse is the 80 ms lexical route."""
    e = os.environ if env is None else env
    raw_n = str(e.get("POLYMATH_CHAT_COMPILER_TITLES_TOP_N", "") or "").strip()
    try:
        top_n = int(raw_n) if raw_n else DEFAULT_TOP_N
    except ValueError:
        top_n = DEFAULT_TOP_N
    rank = str(e.get("POLYMATH_CHAT_COMPILER_TITLES_RANK", RANK_DENSE) or RANK_DENSE).strip().lower()
    if rank not in RANK_MODES:
        rank = RANK_DENSE

    def _i(name: str) -> int:
        try:
            return max(0, int(str(e.get(name, "") or "0").strip() or 0))
        except ValueError:
            return 0

    return TitlesKnobs(top_n=max(0, top_n), rank=rank,
                       section_hits=_i("POLYMATH_CHAT_COMPILER_TITLES_SECTION_HITS"),
                       document_hits=_i("POLYMATH_CHAT_COMPILER_TITLES_DOCUMENT_HITS"))


def clean_title(source_name: str) -> str:
    """A document's title for the prompt: extension, content-hash / '(1)' suffixes, Markdown link syntax and
    bracketed catalogue noise removed, whitespace collapsed, capped."""
    name = str(source_name or "").strip()
    name = _EXT_RE.sub("", name)
    name = _SUFFIX_RE.sub("", name)
    name = _MD_LINK_RE.sub(r"\1", name)
    name = _BRACKET_NOISE_RE.sub(" ", name)
    name = re.sub(r"[_]{2,}", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" #›-–—:|,.")
    return name[:MAX_TITLE_CHARS].rstrip()


def _hits(kind: str, rows: Iterable[dict], corpus_id: str, limit: int) -> list[LaneHit]:
    out: list[LaneHit] = []
    for i, row in enumerate(list(rows)[:limit]):
        payload = row.get("payload") or {}
        doc_id = str(payload.get("doc_id") or "")
        if not doc_id:
            continue
        out.append(LaneHit(representation_kind=kind, rank=len(out) + 1, raw_similarity=float(row.get("score") or 0.0),
                           corpus_id=str(payload.get("corpus_id") or corpus_id), doc_id=doc_id,
                           parent_id=str(payload.get("parent_id") or ""), chunk_id=str(payload.get("chunk_id") or ""),
                           summary_id=str(payload.get("summary_id") or ""), source_name=str(payload.get("source_name") or ""),
                           text=""))
    return out


def rank_documents(section_rows: Iterable[dict], document_rows: Iterable[dict], *, corpus_id: str,
                   k: int, section_limit: int = 200, document_limit: int = 40) -> list[str]:
    """Section-summary hits (and optional document-summary hits) → the top-k documents in relevance order — the same
    RRF vote lane A casts (`aggregate_documents_n`: one vote per document per lane, from its BEST-ranked hit), so
    'top sections per document, backward-mapped' is exactly this. A document seen by two lanes outranks one seen
    by one lane at a similar rank."""
    lanes = [(REPRESENTATION_KIND_SECTION_SUMMARY, _hits(REPRESENTATION_KIND_SECTION_SUMMARY, section_rows, corpus_id, section_limit))]
    doc_hits = _hits(REPRESENTATION_KIND_DOCUMENT_SUMMARY, document_rows, corpus_id, document_limit)
    if doc_hits:
        lanes.append((REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_hits))
    return [c.doc_id for c in aggregate_documents_n(lanes, k=RRF_K)][: max(k, 1)]


def overlap_rank(question: str, catalog: Iterable[tuple[str, str]]) -> list[str]:
    """Fallback ranking when no index is reachable: question words found in the title (count, then title)."""
    qtoks = {t for t in _TOKEN_RE.findall((question or "").lower()) if t not in _STOP}
    scored = []
    for doc_id, source_name in catalog:
        title = clean_title(source_name)
        ttoks = set(_TOKEN_RE.findall(title.lower()))
        n = len(qtoks & ttoks)
        if n:
            scored.append((-n, title.lower(), doc_id))
    return [d for _, _, d in sorted(scored)]


def select_titles(ranked_doc_ids: Iterable[str], catalog: Iterable[tuple[str, str]], *, top_n: int) -> tuple[list[str], dict[str, Any]]:
    """Ranked documents first (in order, deduplicated), then the rest of the library alphabetically, up to top_n.
    Returns (titles, receipt)."""
    cat = [(str(d), str(n)) for d, n in catalog if d]
    by_id = {d: clean_title(n) for d, n in cat}
    seen: set[str] = set()
    ranked: list[str] = []
    for d in ranked_doc_ids:
        d = str(d)
        if d in by_id and d not in seen:
            seen.add(d)
            ranked.append(d)
        if len(ranked) >= top_n:
            break
    rest = sorted((d for d in by_id if d not in seen), key=lambda d: (by_id[d].lower(), d))
    fill = rest[: max(0, top_n - len(ranked))]
    titles: list[str] = []
    seen_titles: set[str] = set()
    for d in ranked + fill:
        t = by_id[d]
        if t and t.lower() not in seen_titles:
            seen_titles.add(t.lower())
            titles.append(t)
    return titles, {"contract": CONTRACT, "n_corpus": len(by_id), "n_ranked": len(ranked), "n_filled": len(fill),
                    "n_injected": len(titles), "top_n": top_n}


def titles_block(titles: Iterable[str]) -> str:
    """The prompt block: titles only, most relevant first."""
    rows = [f"- {t}" for t in titles if t]
    if not rows:
        return ""
    return ("BOOKS IN THE LIBRARY MOST RELEVANT TO THIS MESSAGE (titles only, most relevant first; use their own "
            "terminology in the queries when it fits — never a title itself):\n" + "\n".join(rows))
