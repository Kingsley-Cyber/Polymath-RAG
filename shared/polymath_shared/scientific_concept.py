"""SCIENTIFIC-KAG-V1 phase 2: deterministic named-concept identity gate.

The owner mission names the failure: research concepts ("Tree of
Thoughts", "thought generator", "state evaluator", "tree search") die
as non-durable because nothing in the admission chain can vouch for a
multi-token technical compound. This module is the auditable concept
source Harbor REVISION 3b asked for — surface-pattern evidence only,
no model, no I/O.

Accept (durable concept evidence):
  - multi-token surface with an internal capitalized token or a
    recognizable acronym token  ("Tree of Thoughts", "GPT-4", "ToT")
  - multi-token compound whose HEAD noun is a scientific head lemma
    ("thought generator", "state evaluator", "tree search",
     "search algorithm")
Reject:
  - single-token generic nouns  ("thought", "state", "node",
    "algorithm", "method") — the owner's explicit reject list
  - bare plurals with no naming evidence        ("thoughts", "states")

Placement: in _interpret_v2 AFTER document-definition concept evidence
and BEFORE generic classification, so a document-defined term keeps its
stronger authority and plurals still reach the generic gate.
"""
from __future__ import annotations

import re

# Scientific head lemmas whose compounds name a concept rather than a
# class term. Authored list; extend through policy, never silently.
SCIENTIFIC_HEAD_LEMMAS = frozenset({
    "generator", "evaluator", "search", "framework", "architecture",
    "model", "method", "algorithm", "network", "prompt", "benchmark",
    "dataset", "corpus", "task", "metric", "technique", "component",
    "library", "tool", "pipeline", "paradigm", "reasoning", "training",
    "evaluation", "inference", "decoder", "encoder", "transformer",
})

_ACRONYM_RE = None

_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")


def _is_date_expression(words: list[str]) -> bool:
    """Month-name temporal compounds: 'March 2023', 'March 15, 2023'."""
    if not words:
        return False
    if words[0].lower() in _MONTHS:
        tail = [w for w in words[1:] if w != ","]
        return bool(tail) and tail[-1].isdigit() and len(tail[-1]) == 4
    return False


def _is_version_identity(words: list[str]) -> bool:
    """'Version 3.8', 'version 1.0.2' — an explicit version naming."""
    return (len(words) >= 2
            and words[0].lower() in ("version", "ver")
            and re.fullmatch(r"v?\d+(\.\d+)*", words[1]) is not None)


def _is_acronym(token: str) -> bool:
    return len(token) >= 2 and token.isupper() and token.isalpha()


def _has_digit(token: str) -> bool:
    return any(ch.isdigit() for ch in token)


def named_concept_evidence(surface: str, tokens: list[dict] | None = None):
    """Return auditable evidence dict when `surface` names a scientific
    concept; None when this gate declines (never a refusal — decline
    lets later authorities speak).

    `tokens` are the syntax-evidence tokens inside the span when
    available; lemmas refine the head check. Absent tokens fall back to
    whitespace surface tokens.
    """
    text = (surface or "").strip()
    if not text:
        return None

    words = text.split()

    # Single-token named models/acronyms: "GPT-4", "BERT", "ToT".
    if len(words) == 1:
        w = words[0]
        if _is_acronym(w):
            return {"contract": "scientific-concept-evidence-v1",
                    "pattern": "acronym", "surface": text}
        if (_has_digit(w) and any(ch.isalpha() for ch in w)
                and w[0].isupper()):
            return {"contract": "scientific-concept-evidence-v1",
                    "pattern": "versioned_compound", "surface": text}
        if (w.isalpha() and w[0].isupper() and len(w) <= 6
                and sum(ch.isupper() for ch in w) >= 2
                and not w.istitle()):
            # An uppercase run followed by a lowercase tail is an
            # inflected form ("LMs"), not an acronym.
            if w[-1].islower() and w[-2].isupper():
                return None
            return {"contract": "scientific-concept-evidence-v1",
                    "pattern": "short_acronym", "surface": text}
        return None

    if len(words) < 2:
        return None

    if _is_date_expression(words):
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "date_expression", "surface": text}
    if _is_version_identity(words):
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "version_identity", "surface": text}

    if any(_is_acronym(w) for w in words):
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "acronym_token", "surface": text}
    if any(_has_digit(w) and any(ch.isalpha() for ch in w) for w in words):
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "versioned_compound", "surface": text}
    if any(w[0].isupper() and not w.isupper() for w in words[1:]):
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "capitalized_compound", "surface": text}

    head = words[-1].lower().strip(".,;:!?'\"")
    head_lemma = head
    if tokens:
        for t in tokens:
            if (t.get("text") or "").lower() == head and t.get("lemma"):
                head_lemma = t["lemma"].lower()
                break
    if head_lemma in SCIENTIFIC_HEAD_LEMMAS:
        return {"contract": "scientific-concept-evidence-v1",
                "pattern": "technical_head_compound",
                "head": head_lemma, "surface": text}
    return None
