"""RESOLUTION-LIFT-V1 — raise the user's request to the corpus's precise vocabulary.

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §10–§12: given the user query + its initial evidence,
DISCOVER the corpus's more precise vocabulary / schema / identifiers for what the user
means, from SOURCE-DERIVED candidates ONLY (never a hardcoded domain rule like
`if "face" in query: search_facs()`), rank them, and hand the top few to bounded precision
probes. The core law (§12): **VOCABULARY DISCOVERS. SOURCE CHUNKS PROVE.** — a lifted term
is a retrieval hint, never a factual claim.

This module is the PURE core: the candidate model + the §11 ranking. It takes candidate
terms already gathered from the corpus surfaces (TERM/TOPIC, MAP semantic_hooks[] /
exact_identifiers[], document exact identifiers, entity cards / canonical aliases, heading
paths, profile-atom terminology) and returns the ≤k highest-value precision terms. The
GATHERING (which store each surface lives in) is wired by the caller; keeping it out here
makes the ranking deterministic and unit-testable, and lets every surface reuse one ranker.

Ranking factors (§11):
  source locality        — the term comes from a document already in the top evidence
  rarity / informativeness — low corpus document-frequency (idf); rarer ⇒ more informative
  canonicality           — a canonical entity / alias
  identifier-like form   — a code / CVE / AU-code / unit (precise by construction, §56)
  semantic support       — vector / source support for the term
  specificity beyond the query — the term is NOT already in the user's words (a lift, not a
                                 restatement); required, else the candidate is dropped
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

RESOLUTION_LIFT_VERSION = "resolution-lift-v1"

#: the source surfaces a candidate may come from (§11); ordered by default precision trust.
SOURCES = ("EXACT_ID", "MAP_ID", "ENTITY", "ALIAS", "TERM", "MAP_HOOK", "TOPIC", "HEADING", "ATOM")

#: default per-source priors (0..1) — an identifier or canonical entity is intrinsically more
#: precise than a topic word; tuned, not hardcoded to any domain.
_SOURCE_PRIOR = {
    "EXACT_ID": 1.00, "MAP_ID": 0.95, "ENTITY": 0.90, "ALIAS": 0.85, "TERM": 0.70,
    "MAP_HOOK": 0.65, "TOPIC": 0.50, "HEADING": 0.45, "ATOM": 0.55,
}

_IDENTIFIER = re.compile(r"\d|(?:\b(?:CVE|RFC|ISO|IEEE)\b)|(?:\b[A-Z]{1,5}\d[A-Z0-9]*\b)|%", re.I)
_WORD = re.compile(r"[a-z0-9]+")


def is_identifier_like(term: str) -> bool:
    """A code / CVE / AU-code / unit — precise by construction (§56 keeps its semantics)."""
    return bool(_IDENTIFIER.search(term or ""))


def _norm_words(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def specificity_beyond(term: str, query: str, query_exact_terms: Iterable[str] = ()) -> bool:
    """True when `term` adds vocabulary the user did NOT already say — the §10/§12 test that
    a lift is a resolution, not a restatement. A term all of whose word-tokens already appear
    in the query (or that equals an existing query exact term) is not a lift."""
    t = (term or "").strip()
    if not t:
        return False
    if any(t.lower() == (e or "").lower() for e in query_exact_terms):
        return False
    tw = _norm_words(t)
    if not tw:
        return False
    return not tw.issubset(_norm_words(query))


@dataclass(frozen=True)
class LiftCandidate:
    term: str
    source: str                          # one of SOURCES
    doc_id: str = ""
    in_top_evidence: bool = False        # source locality
    doc_frequency: int | None = None     # corpus DF (rarity); None = unknown
    canonical: bool = False              # a canonical entity / alias
    semantic_support: float = 0.0        # 0..1 vector/source support
    meta: dict = field(default_factory=dict)


def _idf(df: int | None, corpus_doc_count: int | None) -> float:
    """Rarity as normalized idf in [0,1]; unknown df is treated as mid-rarity (0.5)."""
    if not df or not corpus_doc_count or corpus_doc_count <= 0:
        return 0.5
    df = max(1, min(df, corpus_doc_count))
    return max(0.0, min(1.0, math.log(corpus_doc_count / df) / math.log(corpus_doc_count + 1)))


def score_candidate(c: LiftCandidate, *, corpus_doc_count: int | None = None) -> float:
    """The §11 weighted specificity score (higher = a better precision term)."""
    prior = _SOURCE_PRIOR.get(c.source, 0.5)
    rarity = _idf(c.doc_frequency, corpus_doc_count)
    ident = 1.0 if is_identifier_like(c.term) else 0.0
    canon = 1.0 if c.canonical else 0.0
    local = 1.0 if c.in_top_evidence else 0.0
    support = max(0.0, min(1.0, c.semantic_support))
    # weights (§11 order): locality, rarity, canonicality, identifier form, semantic support,
    # with the per-source prior as the base trust.
    return round(
        0.20 * prior + 0.18 * local + 0.20 * rarity + 0.16 * canon + 0.14 * ident + 0.12 * support,
        6,
    )


def rank_lift_candidates(candidates: Sequence[LiftCandidate], query: str, *,
                         query_exact_terms: Iterable[str] = (), k: int = 3,
                         corpus_doc_count: int | None = None) -> list[LiftCandidate]:
    """Filter to source-derived terms that ADD specificity, dedupe by lowercased term
    (keeping the highest-scored source), and return the top `k` (§14: corpus vocab probes
    ≤ 3). Deterministic: ties break by score, then source prior, then term."""
    qet = tuple(query_exact_terms or ())
    scored: dict[str, tuple[float, LiftCandidate]] = {}
    for c in candidates:
        if not c.term or not specificity_beyond(c.term, query, qet):
            continue
        s = score_candidate(c, corpus_doc_count=corpus_doc_count)
        key = c.term.strip().lower()
        cur = scored.get(key)
        if cur is None or s > cur[0]:
            scored[key] = (s, c)
    ranked = sorted(scored.values(), key=lambda sc: (-sc[0], -_SOURCE_PRIOR.get(sc[1].source, 0.5), sc[1].term.lower()))
    return [c for _s, c in ranked[: max(0, int(k))]]
