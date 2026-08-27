"""PREDICATE-COMPILER-V2: semantic frame resolution (owner mission).

Sits between trigger localization and predicate compilation:

    surface verb
        |  realizations (VerbNet/PropBank/FrameNet provenance,
        |               authored scientific extensions marked)
    semantic frame          <- THIS MODULE
        |
    typed argument roles
        |
    signature validation    <- mapping table, fail-closed
        |
    scientific predicate

Deterministic only. No embedding similarity, no LLM extraction, no
unrestricted verb lists. A candidate whose argument types match no
mapping is UNSUPPORTED — precision over recall.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ONTOLOGY_PATH = Path(__file__).parent / "scientific-predicate-ontology-v2.yaml"

#: Word-boundary matcher cache per realization surface.
_SURFACE_RE_CACHE: dict[str, re.Pattern[str]] = {}


@lru_cache(maxsize=1)
def load_ontology() -> dict[str, Any]:
    """The authored scientific predicate ontology (deterministic)."""
    with _ONTOLOGY_PATH.open() as fh:
        onto = yaml.safe_load(fh)
    if not onto.get("frames"):
        raise ValueError("predicate ontology v2 missing frames")
    return onto


def _surface_regex(surface: str) -> re.Pattern[str]:
    pat = _SURFACE_RE_CACHE.get(surface)
    if pat is None:
        escaped = re.escape(surface).replace(r"\ ", r"\s+")
        pat = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        _SURFACE_RE_CACHE[surface] = pat
    return pat


class FrameCandidate:
    """A semantic frame instantiated by a surface realization at a
    character offset. No fact exists yet — roles bind later."""

    __slots__ = ("frame_id", "surface", "lemma", "start", "end",
                 "provenance")

    def __init__(self, frame_id: str, surface: str, lemma: str,
                 start: int, end: int, provenance: str):
        self.frame_id = frame_id
        self.surface = surface
        self.lemma = lemma
        self.start = start
        self.end = end
        self.provenance = provenance

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"FrameCandidate({self.frame_id!r}, {self.surface!r}, "
                f"{self.start}:{self.end})")


def resolve_frames(text: str) -> list[FrameCandidate]:
    """Scan text for ontology frame realizations (word-boundary exact).

    Multi-word surfaces match across whitespace runs. Returns frames in
    ascending offset order; overlapping matches keep the LONGEST surface
    (e.g. 'relies on' beats 'rely on' family variants deterministically
    by (start, -length))."""
    onto = load_ontology()
    hits: list[FrameCandidate] = []
    for frame_id, frame in onto["frames"].items():
        for rz in frame.get("realizations", []):
            for m in _surface_regex(rz["surface"]).finditer(text):
                hits.append(FrameCandidate(
                    frame_id=frame_id,
                    surface=rz["surface"],
                    lemma=rz["lemma"],
                    start=m.start(),
                    end=m.end(),
                    provenance=rz["provenance"],
                ))
    # longest-surface-wins per overlap, then document order
    hits.sort(key=lambda h: (h.start, -(h.end - h.start)))
    kept: list[FrameCandidate] = []
    for h in hits:
        if kept and h.start < kept[-1].end:
            continue
        kept.append(h)
    return kept


def mappings_for_frame(frame_id: str) -> list[dict[str, Any]]:
    return load_ontology()["frames"][frame_id].get("mappings", [])


def resolve_predicate(frame_id: str,
                      subject_type: str | None,
                      object_type: str | None,
                      lemma_hint: str | None = None) -> dict[str, Any] | None:
    """Signature validation: the ONLY path from a typed frame to a
    predicate. Returns the mapping dict (with predicate id) or None.

    None means UNSUPPORTED - the compiler must not emit a candidate.
    lemma_hint: when the anchor's trigger lemma aligns with exactly one
    viable mapping's predicate root ('created' -> created_by), it wins;
    otherwise first typed match (deterministic).
    """
    if subject_type is None or object_type is None:
        return None
    s = subject_type.lower()
    o = object_type.lower()
    viable = []
    for m in mappings_for_frame(frame_id):
        subs = {t.lower() for t in m.get("subject_types", [])}
        objs = {t.lower() for t in m.get("object_types", [])}
        if s in subs and o in objs:
            viable.append(m)
    if not viable:
        return None
    if lemma_hint:
        root = lemma_hint.lower().removesuffix("d").removesuffix("e")
        aligned = [m for m in viable
                   if m["predicate"].lower().startswith(root)]
        if len(aligned) == 1:
            return aligned[0]
    return viable[0]


def compound_head_nouns() -> frozenset[str]:
    onto = load_ontology()
    return frozenset(onto.get("compound_head_nouns", []))
