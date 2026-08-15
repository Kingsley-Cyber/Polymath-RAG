"""Entity admission policy (EXPERIMENT-ONLY, entity-admission-v1).

Separates two decisions that the current pipeline conflates:

  GLiNER extraction confidence  "does this span look like a Type?"
  Reference/admission class     "is this mention specific enough to
                                 deserve durable graph identity?"

Deterministic categorical classes (no numeric fake confidence):

  GLOBAL        durable cross-document identity
  SCOPED        corpus-local identity (participates in facts, never
                becomes a worldwide entity by surface equality alone)
  MENTION_ONLY  evidence/provenance mention; no durable identity

Feature extraction is pure and reproducible. The decision DAG is a
small explicit table, not scattered conditionals:

  1. proper-name / acronym / version signal          -> GLOBAL
  2. bare generic common noun (single lowercase
     content token, determiner-only modifier)        -> MENTION_ONLY
  3. modified descriptive reference (>=2 content
     tokens, no proper signal)                       -> SCOPED
  4. fallback                                        -> MENTION_ONLY

NOT production. Promoted only after the admission gold + the downstream
G4/G4.2 checkpoint both pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from polymath_shared.identity import content_hash

POLICY_VERSION = "entity-admission-v1"

_DET = {"the", "a", "an"}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.\-/]*")
_ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9]*$")
_VERSION_RE = re.compile(r"[0-9]")

# Deterministic lexical signals only — no model, no external data.
PROPER_NAME_SIGNAL_SUFFIXES = ()


@dataclass(frozen=True)
class EntityAdmissionDecision:
    mention_id: str
    surface: str
    core_type: str
    extraction_score: float
    reference_class: str  # GLOBAL | SCOPED | MENTION_ONLY
    reasons: tuple[str, ...]
    policy_version: str = POLICY_VERSION

    def to_record(self) -> dict:
        return {
            "mention_id": self.mention_id,
            "surface": self.surface,
            "core_type": self.core_type,
            "extraction_score": self.extraction_score,
            "reference_class": self.reference_class,
            "reasons": list(self.reasons),
            "policy_version": self.policy_version,
        }


def _tokens(surface: str) -> list[str]:
    return _WORD_RE.findall(surface)


def content_tokens(surface: str) -> list[str]:
    return [t for t in _tokens(surface) if t.lower() not in _DET]


def _signals(surface: str) -> dict:
    ct = content_tokens(surface)
    tokens = _tokens(surface)
    has_proper = any(
        re.match(r"^[A-Z]", t) and not _ACRONYM_RE.match(t)
        for t in tokens
    )
    has_acronym = any(_ACRONYM_RE.match(t) and len(t) >= 2 for t in tokens)
    has_version = any(_VERSION_RE.search(t) for t in tokens)
    return {
        "content_token_count": len(ct),
        "has_proper_name_signal": has_proper,
        "has_acronym_signal": has_acronym,
        "has_version_signal": has_version,
        "bare_common_noun": (
            len(ct) == 1
            and not has_proper
            and not has_acronym
            and not has_version
        ),
    }


def decide(surface: str, core_type: str, extraction_score: float,
           mention_id: str | None = None) -> EntityAdmissionDecision:
    """Admission decision for one accepted GLiNER span."""
    sig = _signals(surface)
    if mention_id is None:
        mention_id = "mention_" + content_hash({
            "surface": surface, "type": core_type,
        })[:16]
    if sig["has_acronym_signal"] or sig["has_version_signal"]:
        cls, reasons = "GLOBAL", (
            "acronym_identity" if sig["has_acronym_signal"] else "version_identity",
        )
    elif sig["has_proper_name_signal"]:
        cls, reasons = "GLOBAL", ("proper_name_identity",)
    elif sig["bare_common_noun"]:
        cls, reasons = "MENTION_ONLY", ("bare_generic_common_noun",)
    elif sig["content_token_count"] >= 2:
        cls, reasons = "SCOPED", ("modified_descriptive_reference",)
    else:
        cls, reasons = "MENTION_ONLY", ("insufficient_referential_specificity",)
    return EntityAdmissionDecision(
        mention_id=mention_id,
        surface=surface,
        core_type=core_type,
        extraction_score=extraction_score,
        reference_class=cls,
        reasons=reasons,
    )
