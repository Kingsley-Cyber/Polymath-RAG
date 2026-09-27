"""FACET-RETRIEVAL-V1 F4 — the profile-coverage audit scorer (plan §3.4: "an audit script scores every
profile against its document — coverage of the document's top terms and section titles by the profile's
surfaces — and lists the worst").

Pure policy (no I/O): the script ``scripts/profile_audit.py`` loads a library read-only and calls this.

  * ``document_terms`` — the document's top-N terms by a TF-IDF-ish weight: term frequency over the
    document's parents × ``idf`` over the library's documents (how many documents carry the term), the
    same tokenizer and idf the parent skeleton uses (stop terms and short tokens already out).
  * ``section_titles`` — the document's top-level section titles (the giant-profile heading key).
  * ``coverage`` — the share of those terms and titles that appear in the profile's text (a title counts
    when most of its content words do), combined 60 / 40 into one score in [0, 1].

A blank profile scores 0; a profile that names the document's terms and sections scores near 1.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from polymath_shared.document_profile import giant_profile as _gp
from polymath_shared.document_profile import parent_skeleton as _ps

COVERAGE_VERSION = "profile-coverage-v1"
TOP_TERMS = 50
TERM_WEIGHT = 0.6
TITLE_WEIGHT = 0.4
#: a title is covered when at least this share of its content words appears in the profile text
TITLE_MATCH_SHARE = 0.6


def tokens(text: str) -> list[str]:
    """The parent skeleton's content tokens (lower-cased, stop terms and short tokens dropped)."""
    return _ps._word_tokens(text or "")


def _stem(tok: str) -> str:
    """A light, deterministic stem so 'cameras' covers 'camera' and 'lighting' covers 'light'."""
    t = tok.lower()
    for suf in ("ing", "ies", "es", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def document_term_counts(parent_texts: Iterable[str]) -> Counter:
    tf: Counter = Counter()
    for text in parent_texts:
        tf.update(tokens(text))
    return tf


def document_terms(parent_texts: Sequence[str], *, doc_freq: Counter | None = None, n_docs: int = 1,
                   top: int = TOP_TERMS) -> list[tuple[str, float]]:
    """The document's top `top` terms as (term, weight): tf(term) × idf over the library (`doc_freq` =
    the number of documents carrying the term; None ⇒ idf over this document's parents, the fingerprint's
    own vocabulary rule). Deterministic: weight desc, term asc."""
    tf = document_term_counts(parent_texts)
    if not tf:
        return []
    if doc_freq is None:
        sets = [set(tokens(t)) for t in parent_texts]
        doc_freq = _ps.document_frequency(sets)
        n_docs = max(1, len(sets))
    weights = {t: c * _ps.idf(max(1, n_docs), int(doc_freq.get(t, 0))) for t, c in tf.items()}
    ranked = sorted(weights, key=lambda t: (-weights[t], t))
    return [(t, round(weights[t], 3)) for t in ranked[:top]]


def library_doc_freq(docs_parent_texts: Iterable[Sequence[str]]) -> tuple[Counter, int]:
    """(document frequency of every term, number of documents) over a library's documents."""
    df: Counter = Counter()
    n = 0
    for texts in docs_parent_texts:
        n += 1
        df.update({t for text in texts for t in tokens(text)})
    return df, n


def section_titles(parents: Sequence[dict]) -> list[str]:
    """The distinct top-level section titles in document order (the giant-profile heading key)."""
    seen: set[str] = set()
    out: list[str] = []
    for p in parents:
        path = _gp.heading_key_path(p.get("heading_path"))
        if not path:
            continue
        t = path[0]
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out


def flatten_compiled(compiled: dict | None) -> str:
    """Every string surface of a compiled profile (the artifact's `compiled` dict) as one text."""
    parts: list[str] = []
    for v in (compiled or {}).values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v if x)
    return "\n".join(parts)


def flatten_retrieval_profile(rp: dict | None) -> str:
    """The deterministic `documents.retrieval_profile` (document-summary-v1) as one text."""
    if not rp:
        return ""
    parts: list[str] = []
    for k in ("semantic_summary", "primary_domains", "secondary_domains", "core_concepts", "methods",
              "problems_addressed", "use_for_questions_about", "connects_to_domains"):
        v = rp.get(k)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v if x)
    return "\n".join(parts)


@dataclass
class CoverageReport:
    term_share: float
    title_share: float | None
    score: float
    terms_total: int
    titles_total: int
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    matched_titles: list[str] = field(default_factory=list)
    missing_titles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"version": COVERAGE_VERSION, "score": self.score, "term_share": self.term_share,
                "title_share": self.title_share, "terms_total": self.terms_total, "titles_total": self.titles_total,
                "matched_terms": self.matched_terms, "missing_terms": self.missing_terms,
                "matched_titles": self.matched_titles, "missing_titles": self.missing_titles}


def coverage(top_terms: Sequence[tuple[str, float]] | Sequence[str], titles: Sequence[str],
             profile_text: str) -> CoverageReport:
    """How well `profile_text` covers the document: the share of `top_terms` present (stem match) and the
    share of `titles` whose content words are mostly present; score = 0.6 × terms + 0.4 × titles (terms only
    when the document has no titles). Deterministic; an empty profile scores 0."""
    ptoks = tokens(profile_text)
    pset = set(ptoks) | {_stem(t) for t in ptoks}
    terms = [t[0] if isinstance(t, (tuple, list)) else str(t) for t in top_terms]

    def present(term: str) -> bool:
        return term in pset or _stem(term) in pset

    matched_terms = [t for t in terms if present(t)]
    missing_terms = [t for t in terms if not present(t)]
    term_share = (len(matched_terms) / len(terms)) if terms else 0.0

    matched_titles: list[str] = []
    missing_titles: list[str] = []
    for title in titles:
        words = tokens(title)
        if not words:
            continue
        hit = sum(1 for w in words if present(w))
        (matched_titles if hit / len(words) >= TITLE_MATCH_SHARE else missing_titles).append(title)
    n_titles = len(matched_titles) + len(missing_titles)
    title_share = (len(matched_titles) / n_titles) if n_titles else None
    if title_share is None:
        score = term_share
    else:
        score = TERM_WEIGHT * term_share + TITLE_WEIGHT * title_share
    return CoverageReport(term_share=round(term_share, 4), title_share=(round(title_share, 4) if title_share is not None else None),
                          score=round(score, 4), terms_total=len(terms), titles_total=n_titles,
                          matched_terms=matched_terms, missing_terms=missing_terms,
                          matched_titles=matched_titles, missing_titles=missing_titles)


def audit_document(parents: Sequence[dict], *, profile_texts: dict[str, str], doc_freq: Counter | None = None,
                   n_docs: int = 1, top: int = TOP_TERMS, threshold: int = _gp.GIANT_PARENT_THRESHOLD,
                   section_profiles: int = 0) -> dict[str, Any]:
    """One document's audit row: the top terms and titles, one CoverageReport per named profile text
    (e.g. {"llm": …, "det": …}), the giant flag and whether a giant lacks section profiles."""
    texts = [str(p.get("text") or "") for p in parents]
    terms = document_terms(texts, doc_freq=doc_freq, n_docs=n_docs, top=top)
    titles = section_titles(parents)
    reports = {name: coverage(terms, titles, text or "") for name, text in profile_texts.items()}
    giant = _gp.is_giant(len(parents), threshold=threshold)
    return {
        "parents": len(parents), "giant": giant, "section_profiles": int(section_profiles),
        "giant_without_sections": bool(giant and section_profiles <= 0),
        "top_terms": terms, "titles": titles,
        "reports": {k: v.to_dict() for k, v in reports.items()},
        "score": (max(v.score for v in reports.values()) if reports else 0.0),
    }


def worst(rows: Sequence[dict[str, Any]], *, n: int = 10, key: str = "score") -> list[dict[str, Any]]:
    """The `n` lowest-scoring rows (score asc, then more parents first, then name)."""
    return sorted(rows, key=lambda r: (float(r.get(key) or 0.0), -int(r.get("parents") or 0),
                                       str(r.get("source_name") or "")))[:n]
