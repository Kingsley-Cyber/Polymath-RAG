"""GENERIC-CLASSIFICATION-V1 — a narrow ATTRIBUTION gate.

The composed V2 stack could refuse a mention but not say WHY: `Researchers`
came out UNKNOWN and `regional dispatchers` LOCAL_REFERENCE, when the Harbor
contract calls both GENERIC. Graph eligibility was already correct — all
three are refused — so this gate corrects the system's EXPLANATION, not its
behaviour.

    before   Researchers -> UNKNOWN            -> not eligible
    after    Researchers -> GENERIC            -> not eligible

If it ever changes what enters the graph, its scope has exceeded the
demonstrated defect.

STRUCTURAL, never another noun blacklist. `researchers`, `dispatchers`,
`studies`, `findings` cannot all be anticipated by hand, and the next book
brings fifty more. spaCy supplies head POS, lemma, number, determiners and
named anchors, so the rule works the same on a psychology text and a
cybersecurity manual.

PRECEDENCE — GENERIC must never override an established interpretation:

    IDENTITY  >  LOCAL_REFERENCE(resolved/constituted)  >  CONCEPT  >  GENERIC  >  UNKNOWN
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

GENERIC_CONTRACT = "generic-classification-v1"

# Quantifiers that make a phrase denote a plurality rather than one referent.
_QUANTIFIER = frozenset({"one", "two", "three", "several", "many", "few",
                         "every", "each", "all", "some", "both", "various",
                         "multiple", "numerous", "any"})
# Determiners that introduce a CLASS-level reading rather than a specific one.
_GENERIC_DET = frozenset({"a", "an", "any", "every", "each"})
_NOMINAL = frozenset({"NOUN", "PROPN"})


class GenericEvidence(str, Enum):
    PLURAL_COMMON_NOUN = "PLURAL_COMMON_NOUN"
    QUANTIFIED_PHRASE = "QUANTIFIED_PHRASE"
    BARE_KIND_TERM = "BARE_KIND_TERM"
    GENERIC_DETERMINER = "GENERIC_DETERMINER"


@dataclass(frozen=True)
class GenericDecision:
    is_generic: bool
    evidence: GenericEvidence | None = None
    reasons: tuple[str, ...] = ()
    contract: str = GENERIC_CONTRACT


def _content(tokens: list[dict]) -> list[dict]:
    return [t for t in tokens if t.get("pos") not in {"PUNCT", "SPACE"}]


def _is_plural(tok: dict) -> bool:
    """Deterministic from the pinned tagger: a NOUN whose surface differs
    from its lemma is inflected. No morphology field is required, and no
    hand list of plural forms is possible."""
    if tok.get("pos") != "NOUN":
        return False
    lemma = (tok.get("lemma") or "").lower()
    return bool(lemma) and tok["text"].lower() != lemma


def classify_generic(surface: str, *, tokens: list[dict] | None = None,
                     has_identity_anchor: bool = False) -> GenericDecision:
    """Deterministic generic evidence, or nothing.

    `has_identity_anchor` is supplied by the caller from the ALREADY
    qualified identity predicate — this gate never re-derives identity.
    A span carrying an anchor (`PostgreSQL databases`, `Researcher
    Technologies`) is never blindly generic.
    """
    if not tokens:
        return GenericDecision(False, reasons=("no syntax evidence",))
    toks = _content(tokens)
    if not toks:
        return GenericDecision(False, reasons=("no content tokens",))
    if has_identity_anchor or any(t.get("pos") == "PROPN" for t in toks):
        return GenericDecision(
            False, reasons=("carries a proper-noun / identity anchor — "
                            "an anchored span is never blindly generic",))

    head = toks[-1]
    if head.get("pos") not in _NOMINAL:
        return GenericDecision(False, reasons=(f"head is {head.get('pos')}, not nominal",))

    first = toks[0]
    first_lemma = (first.get("lemma") or first["text"]).lower()

    # 2. quantified common-noun phrase — "Two documents", "Several studies"
    if first.get("pos") == "NUM" or first_lemma in _QUANTIFIER:
        return GenericDecision(True, GenericEvidence.QUANTIFIED_PHRASE,
                               (f"quantifier {first['text']!r} over a common-noun "
                                f"head {head['text']!r}",))

    # 1. plural common noun with no anchor — "Researchers", "regional dispatchers"
    if _is_plural(head):
        return GenericDecision(True, GenericEvidence.PLURAL_COMMON_NOUN,
                               (f"plural common noun {head['text']!r} "
                                f"(lemma {head.get('lemma')!r}) with no identity anchor",))

    # 4. class-level determiner — "any server", "every database"
    if first.get("pos") == "DET" and first_lemma in _GENERIC_DET and len(toks) > 1:
        return GenericDecision(True, GenericEvidence.GENERIC_DETERMINER,
                               (f"class-level determiner {first['text']!r}",))

    # 3. bare singular kind term — "system", "platform", "model"
    if len(toks) == 1 and head.get("pos") == "NOUN":
        return GenericDecision(True, GenericEvidence.BARE_KIND_TERM,
                               (f"bare common-noun kind term {head['text']!r} with no "
                                f"identity or concept evidence",))

    return GenericDecision(False, reasons=("no deterministic generic evidence",))
