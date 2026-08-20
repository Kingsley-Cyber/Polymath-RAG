"""CONTRACTION-RESOLUTION-V1 (PHASE 3) — in-document contraction, not dedup.

The demonstrated defect is narrow: a document introduces a full name and
then uses a contracted form, and the two become separate graph nodes.

    "Crestline Automation uses Siemens PLCs..."   then   "Crestline developed..."

Both forms are already admitted in the SAME document, so resolution reuses
an existing identity and invents nothing.

    short/contracted mention
    + existing LONGER identity in the SAME document
    + compatible type
    -> reuse the existing identity

This is explicitly NOT similarity matching:

    Crestline  ~=  Crestview Automation      -> ABSTAIN

String similarity would accept that pair; token containment refuses it.
RapidFuzz / GLinker / embeddings are NOT used and are not needed for the
demonstrated failures — they remain optional candidate generators for
later, if real identity errors ever justify them.

Two contraction SHAPES, both requiring exact token identity, never
character similarity:

  A. anchor prefix        Crestline          -> Crestline Automation
                          short tokens are a strict PREFIX of long
  B. head-preserving      Mentor engine      -> Mentor assessment engine
     elision              Cobalt cell        -> Cobalt assembly cell
                          ordered subsequence, same first token, same head

Ambiguity is abstention: if two longer forms both admit the contraction,
no merge occurs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

CONTRACTION_CONTRACT = "contraction-resolution-v1"


class MergeDecision(str, Enum):
    SAME_ENTITY = "SAME_ENTITY"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ContractionResult:
    decision: MergeDecision
    short_surface: str
    resolved_to: str | None = None
    shape: str | None = None
    evidence: tuple[str, ...] = ()
    candidates: tuple[str, ...] = ()
    contract: str = CONTRACTION_CONTRACT


def _tokens(surface: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", surface.lower()) if t]


def _is_prefix(short: list[str], long: list[str]) -> bool:
    return len(short) < len(long) and long[:len(short)] == short


def _is_head_preserving_subsequence(short: list[str], long: list[str]) -> bool:
    """Ordered token subsequence sharing BOTH the first token and the head.

    Requiring both endpoints is what stops `engine` alone, or an unrelated
    middle-token overlap, from counting as a contraction.
    """
    if len(short) < 2 or len(short) >= len(long):
        return False
    if short[0] != long[0] or short[-1] != long[-1]:
        return False
    it = iter(long)
    return all(t in it for t in short)


def resolve_contraction(short_surface: str, short_type: str,
                        candidates: list[tuple[str, str]]) -> ContractionResult:
    """Resolve a contracted mention against longer identities in the SAME
    document.

    `candidates` are `(surface, core_type)` pairs already ADMITTED in that
    document. Returns SAME_ENTITY with the exact existing surface to reuse,
    or ABSTAIN. Never synthesises text.
    """
    st = _tokens(short_surface)
    if not st:
        return ContractionResult(MergeDecision.ABSTAIN, short_surface,
                                 evidence=("empty surface",))

    matches: list[tuple[str, str]] = []
    for surface, ctype in candidates:
        if ctype != short_type:
            continue
        lt = _tokens(surface)
        if lt == st:
            continue                      # same surface, nothing to resolve
        if _is_prefix(st, lt):
            matches.append((surface, "anchor-prefix"))
        elif _is_head_preserving_subsequence(st, lt):
            matches.append((surface, "head-preserving elision"))

    if not matches:
        return ContractionResult(
            MergeDecision.ABSTAIN, short_surface,
            evidence=("no longer in-document identity contains this form "
                      "by exact token containment",))
    if len(matches) > 1:
        return ContractionResult(
            MergeDecision.ABSTAIN, short_surface,
            evidence=("ambiguous: multiple longer identities admit this "
                      "contraction",),
            candidates=tuple(sorted(m[0] for m in matches)))

    surface, shape = matches[0]
    return ContractionResult(
        MergeDecision.SAME_ENTITY, short_surface, resolved_to=surface,
        shape=shape,
        evidence=(f"{shape}: {_tokens(short_surface)} contained in "
                  f"{_tokens(surface)} by exact token identity; both admitted "
                  f"in this document with core_type {short_type}",),
        candidates=(surface,))


# --- PHASE 3 SETTLEMENT (policy B) ----------------------------------------
# Resolution merges CANONICAL IDENTITY only. It never rewrites a mention or
# fact surface to select a preferred label: the frozen gold canonicalizes
# `CareChart EMR` (short) but `FreightNet routing platform` (long) for
# identical grammatical shapes, so no deterministic in-document signal picks
# a label. Display-label selection is a separate concern with NO authority
# over fact truth.


@dataclass(frozen=True)
class CanonicalMembership:
    """One local surface's membership in a canonical entity.

    `surface` is immutable provenance — the text as it actually occurred.
    `canonical_id` is what the graph joins on.
    """

    surface: str
    core_type: str
    canonical_id: str
    is_anchor: bool
    basis: str
    contract: str = CONTRACTION_CONTRACT


def canonical_id_for(surface: str) -> str:
    return "ent_" + "_".join(_tokens(surface))


def build_memberships(admitted: list[tuple[str, str]]) -> dict[str, CanonicalMembership]:
    """Map every admitted in-document surface to its canonical entity.

    Contracted forms join the anchor's canonical id; every surface is
    retained. Nothing is rewritten and nothing is dropped.
    """
    out: dict[str, CanonicalMembership] = {}
    for surface, ctype in admitted:
        r = resolve_contraction(surface, ctype, admitted)
        if r.decision is MergeDecision.SAME_ENTITY:
            out[surface] = CanonicalMembership(
                surface, ctype, canonical_id_for(r.resolved_to), False,
                f"{r.shape}: joins {r.resolved_to!r}")
        else:
            out[surface] = CanonicalMembership(
                surface, ctype, canonical_id_for(surface), True,
                "anchor (no longer in-document form contains it)")
    return out
