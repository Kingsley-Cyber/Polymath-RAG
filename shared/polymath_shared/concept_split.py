"""DECISION A2 — entity vs concept surface classification.

Generic scientific category phrases ("neural models", "extensive
datasets") are CONCEPTS, never entities. Named objects (BERT, GPT-4,
GLUE) are ENTITIES. Classification is deterministic: a surface whose
HEAD token is a generic scientific head noun (compound-head allowlist)
and which carries no proper-noun modifier is a generic category.

Used BEFORE entity admission when POLYMATH_CONCEPT_SPLIT=1; surfaces
classified as concepts route to the concept layer and are excluded
from durable entity identity.
"""
from __future__ import annotations

import re

from polymath_shared.rulepack.compound_heads import (
    compound_head_nouns, is_generic_head)

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")


def _tokens(surface: str) -> list[str]:
    return [t for t in _TOKEN.findall(surface or "") if t]


def classify_surface(surface: str) -> str:
    """Return 'concept' | 'entity'.

    Rules (deterministic, ordered):
    1. contains a digit or is an acronym (all-caps >=2) -> entity
       ("GPT-4", "BERT") — registry/NER authority still applies.
    2. any ProperNoun-style token beyond the first word (capitalized
       mid-phrase) -> entity ("Google Research").
    3. head token (last word, plural-stripped) is a generic scientific
       head noun AND every other word is lowercase -> concept
       ("neural models", "extensive datasets", "language model").
    4. otherwise -> entity (conservative default; admission gates still
       decide).
    """
    toks = _tokens(surface)
    if not toks:
        return "entity"
    if any(t.isdigit() for t in toks):
        return "entity"
    for t in toks:
        if t.isupper() and len(t) >= 2:
            return "entity"
    heads = {h for h in compound_head_nouns()}
    head = toks[-1].lower().removesuffix("s")
    if len(toks) >= 2 and all(t[:1].islower() for t in toks[:-1]) \
            and head in heads:
        return "concept"
    if len(toks) == 1 and toks[0].islower():
        return "concept" if toks[0].lower() in heads else "entity"
    return "entity"
