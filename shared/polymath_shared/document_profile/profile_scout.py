"""P5a Profile Scout — the pure dual-projection fusion primitive (PROFILE-SCOUT-V1).

Contains the normalized ``ScoutHit`` / ``ProfileScoutResult`` types and the pure deterministic
RRF fusion. There is **no retrieval backend, no I/O, and no injected search callable** here
(a callable that hits Qdrant is still I/O). The caller — P5b — runs the two real searches
(``projection.profile_nominate`` → ordered doc_ids; ``profile_atom_projection.search_atoms`` →
atom hits), normalizes their outputs into ``ScoutHit`` lists, and calls
``fuse_profile_scout_hits``.

RRF fuses already-produced ranked candidates at the projection-level document ranking; it never
interprets ``q0``, never gates retrieval, and never labels a semantic capability. An empty
result subtracts nothing — the caller fails open to normal retrieval. See
docs/wiki/plans/PROFILE-SCOUT-V1.md.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

PROFILE = "profile"
ATOM = "atom"
RRF_K = 60
MAX_DOCUMENTS = 8


@dataclass(frozen=True)
class ScoutHit:
    """One normalized hit from one projection. The atom-only fields stay ``None`` for profile
    hits, because ``profile_nominate`` returns bare ordered doc_ids (no surface/text/score)."""
    doc_id: str
    source: str                     # "profile" | "atom"
    rank: int                       # 1-based rank within its projection's own ranked list
    surface: str | None = None      # atom_kind for atom hits; None for profile
    surface_type: str | None = None  # SurfaceRegistry group (set during P5b normalization)
    text: str | None = None         # verbatim stored snippet for atom hits; None for profile
    score: float | None = None      # raw projection score for atom hits; None for profile


@dataclass(frozen=True)
class ProjectionContribution:
    """One projection's single RRF vote for a document (best-rank collapse)."""
    source: str
    best_rank: int
    rrf_contribution: float


@dataclass(frozen=True)
class ProfileNomination:
    """A nominated document: verbatim pointers + full provenance only.

    Deliberately carries no ``recommended_mode`` / ``required_subquery`` / ``must_use_graph`` /
    ``intent_override`` / ``answer_strategy`` and no answer text — those would make the scout a
    hidden planner. The adaptive planner decides what the matches *mean*.
    """
    doc_id: str
    fused_score: float
    rank: int
    matched_surfaces: tuple[str, ...]
    surface_types: tuple[str, ...]
    representative_surface: str | None
    representative_text: str | None
    contributions: tuple[ProjectionContribution, ...]
    provenance: tuple[ScoutHit, ...]


@dataclass(frozen=True)
class ProfileScoutResult:
    nominations: tuple[ProfileNomination, ...]


def fuse_profile_scout_hits(
    profile_hits: Sequence[ScoutHit],
    atom_hits: Sequence[ScoutHit],
    *,
    rrf_k: int = RRF_K,
    max_documents: int = MAX_DOCUMENTS,
) -> ProfileScoutResult:
    """Pure RRF fusion of two already-normalized ranked ``ScoutHit`` lists → ``ProfileScoutResult``.

    Each projection contributes **at most one** RRF vote per document: its hits are collapsed to
    the doc's best (lowest) rank, so a document with many atom rows cannot gain fusion weight
    from row count. ``fused_score = Σ 1/(rrf_k + best_rank)`` over the projections the doc
    appears in — rank-based, so the two projections' raw score scales are never compared (raw
    ``score`` survives only as provenance). Deterministic: ``fused_score`` desc, tie-break
    ``doc_id`` asc. Every contributing hit is kept in ``provenance``; the best text-bearing hit
    is the verbatim representative. No I/O, no LLM; empty inputs yield an empty result.
    """
    per_doc: dict[str, dict[str, list[ScoutHit]]] = {}
    for hit in list(profile_hits) + list(atom_hits):
        if not hit.doc_id:
            continue
        per_doc.setdefault(hit.doc_id, {}).setdefault(hit.source, []).append(hit)

    scored = []
    for doc_id, by_source in per_doc.items():
        contributions = tuple(
            ProjectionContribution(src, best, 1.0 / (rrf_k + best))
            for src in sorted(by_source)
            for best in (min(h.rank for h in by_source[src]),)
        )
        fused = sum(c.rrf_contribution for c in contributions)
        provenance = tuple(sorted(
            (h for hits in by_source.values() for h in hits),
            key=lambda h: (0 if h.source == PROFILE else 1, h.rank, h.surface or ""),
        ))
        surfaces = tuple(sorted({h.surface for h in provenance if h.surface}))
        groups = tuple(sorted({h.surface_type for h in provenance if h.surface_type}))
        with_text = [h for h in provenance if h.text]
        rep = min(with_text, key=lambda h: h.rank) if with_text else None
        scored.append((doc_id, fused, contributions, surfaces, groups,
                       rep.surface if rep else None, rep.text if rep else None, provenance))

    scored.sort(key=lambda r: (-r[1], r[0]))  # fused_score desc, doc_id asc
    nominations = tuple(
        ProfileNomination(doc_id, fused, rank, surfaces, groups, rep_surface, rep_text,
                          contributions, provenance)
        for rank, (doc_id, fused, contributions, surfaces, groups, rep_surface, rep_text, provenance)
        in enumerate(scored[:max_documents], start=1)
    )
    return ProfileScoutResult(nominations=nominations)
