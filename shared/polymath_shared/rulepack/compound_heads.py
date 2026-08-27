"""PREDICATE-COMPILER-V2: compound scientific head resolution.

"The BERT model was introduced." must bind BERT to 'introduced', never
the generic head noun "model".

Rule (deterministic): when an entity candidate is immediately followed
by a generic scientific head noun joined as a compound (adjacency, or
compound/flat dependency in UD), the ENTITY carries the relation slot
and the generic head inherits nothing. A bare generic head with no
entity modifier ("large model") resolves to NOTHING — it does not
become an entity.

The head-noun allowlist lives in the ontology YAML so scientists, not
code edits, own the vocabulary of generic heads.
"""
from __future__ import annotations

import re

from polymath_shared.rulepack.semantic_frames import compound_head_nouns

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*")


def is_generic_head(surface: str) -> bool:
    """True when the surface is exactly a generic scientific head noun."""
    return surface.strip().lower() in compound_head_nouns()


def resolve_compound_heads(spans: list[dict]) -> list[dict]:
    """Filter entity spans for relation-slot binding.

    spans: [{text, start, end, core_type?, score?}, ...] in document
    order. Returns the spans that may carry a relation slot:

    - a span that IS a generic head noun and whose immediate-left token
      sequence ends with another span's text (compound modifier) is
      DROPPED — the modifier entity inherits the slot;
    - a bare generic head with NO entity modifier is dropped entirely;
    - everything else passes unchanged.
    """
    keep: list[dict] = []
    for i, span in enumerate(spans):
        text = span.get("text", "").strip()
        if not is_generic_head(text):
            keep.append(span)
            continue
        # generic head: inherit ONLY if a preceding span directly abuts
        # (optionally one space) and reads as its compound modifier
        prev = keep[-1] if keep else None
        if prev is not None:
            gap = span.get("start", 0) - prev.get("end", 0)
            if 0 <= gap <= 1:
                continue  # modifier entity absorbs the slot; drop head
        # bare generic head with no entity modifier: drop silently but
        # deterministically (it must never anchor a relation)
    return keep


def strip_head_from_subject(subject_surface: str,
                            subject_entity_surface: str) -> bool:
    """Binding-time check: True when subject_entity_surface is the
    entity head of a compound whose tail is the generic noun in
    subject_surface (e.g. subject 'BERT model', entity 'BERT')."""
    s = subject_surface.strip()
    e = subject_entity_surface.strip()
    if not s or not e or not s.lower().startswith(e.lower()):
        return False
    tail = s[len(e):].strip()
    return is_generic_head(tail)
