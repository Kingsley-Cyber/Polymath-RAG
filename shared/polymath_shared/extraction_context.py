"""extraction-context-v1: bounded context envelope for GLiNER inference.

STORAGE UNIT != MODEL CONTEXT WINDOW. The focal semantic_v2 child chunk
remains the authoritative storage/provenance unit; the envelope is
inference-only. A pure deterministic function of (focal chunk, document
structure, sibling ordering, selected policy). Hard boundaries: context
never crosses document or hard-section boundaries. Offset ownership:
only predictions fully inside the focal span become focal mentions.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

CONTEXT_CONTRACT_V1 = "extraction-context-v1"

POLICIES = ("C0_FOCAL_ONLY", "C1_HEADING_FOCAL", "C2_PREVIOUS_FOCAL",
            "C3_HEADING_PREVIOUS_FOCAL", "C4_FOCAL_NEXT",
            "C5_PREVIOUS_FOCAL_NEXT", "C6_HEADING_PREVIOUS_FOCAL_NEXT")


@dataclass(frozen=True)
class ContextComponent:
    role: str          # heading | previous | focal | next
    text: str
    source_start: int  # document-relative
    source_end: int
    chunk_id: str | None = None


@dataclass(frozen=True)
class Envelope:
    policy: str
    focal_chunk_id: str
    focal_source_start: int
    focal_source_end: int
    components: tuple[ContextComponent, ...]
    envelope_text: str
    focal_envelope_start: int  # envelope-relative offset of focal text
    focal_envelope_end: int

    @property
    def context_policy_version(self) -> str:
        return CONTEXT_CONTRACT_V1

    def identity(self) -> dict:
        return {
            "contract": CONTEXT_CONTRACT_V1,
            "policy": self.policy,
            "focal_chunk_id": self.focal_chunk_id,
            "focal_source": [self.focal_source_start, self.focal_source_end],
            "components": [
                {"role": c.role, "source": [c.source_start, c.source_end],
                 "chunk_id": c.chunk_id} for c in self.components
            ],
        }


def active_policy() -> str:
    return os.environ.get("POLYMATH_EXTRACTION_CONTEXT", "C0_FOCAL_ONLY")


def _same_section(a: dict, b: dict) -> bool:
    """Two child chunks are same-section when their heading_path tails
    match (semantic_v2); legacy chunks (heading_path NULL) use parent_id
    equality as the fallback section proxy."""
    ha = a.get("heading_path") or []
    hb = b.get("heading_path") or []
    if ha and hb:
        return list(ha) == list(hb)
    return a.get("parent_id") == b.get("parent_id")


def build_envelope(focal: dict, siblings: list[dict], doc_text: str,
                   policy: str | None = None) -> Envelope:
    """Construct the inference envelope. `focal` is the child chunk row;
    `siblings` are all child chunk rows of the document ordered by
    char_start (focal included). Deterministic: same inputs → same
    envelope byte-for-byte."""
    pol = policy or active_policy()
    focal_start, focal_end = focal["char_start"], focal["char_end"]
    focal_text = doc_text[focal_start:focal_end]
    components: list[ContextComponent] = []

    idx = next(i for i, s in enumerate(siblings) if s["chunk_id"] == focal["chunk_id"])

    # -- heading component (metadata, not focal-owned) --
    if pol in ("C1_HEADING_FOCAL", "C3_HEADING_PREVIOUS_FOCAL",
               "C6_HEADING_PREVIOUS_FOCAL_NEXT"):
        hp = focal.get("heading_path") or []
        heading_text = " — ".join(hp) if hp else ""
        if heading_text:
            # heading lives before the focal chunk in the source
            components.append(ContextComponent(
                role="heading", text=heading_text + "\n\n",
                source_start=max(0, focal_start - len(heading_text) - 2),
                source_end=focal_start))

    # -- previous component --
    if pol in ("C2_PREVIOUS_FOCAL", "C3_HEADING_PREVIOUS_FOCAL",
               "C5_PREVIOUS_FOCAL_NEXT", "C6_HEADING_PREVIOUS_FOCAL_NEXT"):
        prev = siblings[idx - 1] if idx > 0 else None
        if prev is not None and _same_section(prev, focal):
            prev_text = doc_text[prev["char_start"]:prev["char_end"]]
            components.append(ContextComponent(
                role="previous", text=prev_text + "\n",
                source_start=prev["char_start"], source_end=prev["char_end"],
                chunk_id=prev["chunk_id"]))
        # else: hard boundary → NO previous context (deliberately omitted)

    # -- focal component (always present) --
    focal_component = ContextComponent(
        role="focal", text=focal_text,
        source_start=focal_start, source_end=focal_end,
        chunk_id=focal["chunk_id"])
    components.append(focal_component)

    # -- next component --
    if pol in ("C4_FOCAL_NEXT", "C5_PREVIOUS_FOCAL_NEXT",
               "C6_HEADING_PREVIOUS_FOCAL_NEXT"):
        nxt = siblings[idx + 1] if idx + 1 < len(siblings) else None
        if nxt is not None and _same_section(nxt, focal):
            next_text = doc_text[nxt["char_start"]:nxt["char_end"]]
            components.append(ContextComponent(
                role="next", text="\n" + next_text,
                source_start=nxt["char_start"], source_end=nxt["char_end"],
                chunk_id=nxt["chunk_id"]))

    envelope_text = "".join(c.text for c in components)
    focal_envelope_start = sum(len(c.text) for c in components
                               if c.role != "focal") if components[-1].role == "focal" or True else 0
    # precise: focal offset = sum of all preceding component lengths
    offset = 0
    for c in components:
        if c.role == "focal":
            focal_envelope_start = offset
            focal_envelope_end = offset + len(c.text)
            break
        offset += len(c.text)

    return Envelope(
        policy=pol, focal_chunk_id=focal["chunk_id"],
        focal_source_start=focal_start, focal_source_end=focal_end,
        components=tuple(components), envelope_text=envelope_text,
        focal_envelope_start=focal_envelope_start,
        focal_envelope_end=focal_envelope_end,
    )


def classify_prediction(env: Envelope, envelope_start: int, envelope_end: int) -> tuple[str, int, int]:
    """Map an envelope-relative prediction to source coordinates and
    classify ownership. Returns (classification, source_start,
    source_end)."""
    src_start = env.focal_source_start + (envelope_start - env.focal_envelope_start)
    src_end = env.focal_source_start + (envelope_end - env.focal_envelope_start)
    if envelope_start >= env.focal_envelope_start and envelope_end <= env.focal_envelope_end:
        return "CONTEXT_PREDICTION_FOCAL", src_start, src_end
    if envelope_end <= env.focal_envelope_start or envelope_start >= env.focal_envelope_end:
        return "CONTEXT_PREDICTION_OUTSIDE_FOCAL", src_start, src_end
    return "CONTEXT_PREDICTION_CROSSES_FOCAL_BOUNDARY", src_start, src_end
