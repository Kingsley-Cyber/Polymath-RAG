"""Entity admission policy (EXPERIMENT-ONLY, entity-admission-v1.1).

Four classes:
  GLOBAL           strong identity across corpora
  CORPUS_SCOPED    identity meaningful within a corpus
  DOCUMENT_SCOPED  identity established within one document (deictic/
                   possessive modification)
  MENTION_ONLY     linguistic mention; evidence/provenance only, NEVER
                   projected as a KG node

v1.1 fixes the four measured v1.0 error mechanisms:
  1. capitalization alone does NOT establish proper-name identity for
     generic common nouns (sentence-initial or not);
  2. digit/version signal alone does NOT establish GLOBAL identity —
     it requires a co-occurring identity signal (proper/acronym/
     multiword product structure);
  3. weak modifiers ("real", "new", "main", ...) do not lift a generic
     head out of MENTION_ONLY;
  4. genuinely discriminative compounds still qualify (retrieval
     pipeline, vector index, worker pool, transactional outbox).

The genericity signal is a BOUNDED, documented common-noun list
(reproducible lexical structure, not a banned-word dump) — exactly the
"deterministic genericity policy" the G4.2 brief sanctioned.
Deterministic, no model, no numeric fake confidence, every decision
explains itself. NOT production.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from polymath_shared.identity import content_hash

POLICY_VERSION = "entity-admission-v1.1"

_DET = {"the", "a", "an"}

# Bounded, documented generic-head inventory (lexical structure, not a
# banned-word dump): bare or weakly modified forms of these never earn
# durable identity by surface alone.
GENERIC_HEAD = frozenset({
    "system", "model", "platform", "component", "service", "data",
    "process", "application", "tool", "framework", "layer", "engine",
    "node", "record", "store", "index", "pool", "pipeline", "loop",
    "task", "job", "file", "database", "server", "network", "device",
    "interface", "module", "function", "object", "event", "request",
})

WEAK_MODIFIERS = frozenset({
    "real", "new", "main", "other", "same", "some", "any", "all",
    "many", "several", "general", "basic", "simple", "various",
    "different", "certain", "current", "entire", "whole", "particular",
    "additional", "actual", "so-called", "own",
})

DEICTIC_MODIFIERS = frozenset({
    "our", "my", "your", "their", "its", "this", "that", "these", "those",
})

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.\-/]*")
_DIGIT_RE = re.compile(r"\d+")
_ACRONYM_RE = re.compile(r"^[A-Z][A-Z]*$")


@dataclass(frozen=True)
class EntityAdmissionDecision:
    mention_id: str
    surface: str
    core_type: str
    extraction_score: float
    reference_class: str
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
    toks = [t for t in _tokens(surface) if t.lower() not in _DET]
    digits = _DIGIT_RE.findall(surface)
    if digits and len(toks) >= 1:
        toks = toks + digits
    return toks


def _classify(surface: str, sentence_initial: bool) -> tuple[str, tuple[str, ...]]:
    toks = _tokens(surface)
    ct = content_tokens(surface)
    head_tokens = [t for t in ct if not t.isdigit()]
    head = (head_tokens[-1].lower() if head_tokens else "")

    acronym = any(_ACRONYM_RE.match(t) and len(t) >= 2 and t.lower() not in GENERIC_HEAD
                  for t in toks)
    has_digit = bool(_DIGIT_RE.search(surface))
    # identifiers: digit-containing tokens are never identity evidence
    # by themselves ("D6L11", "3").
    identifier = any(_DIGIT_RE.search(t) for t in toks)

    # v1.1 rule 1: capitalization alone never promotes a generic common
    # noun (sentence-initial or not); digit-containing tokens never
    # count as proper names.
    proper = any(
        re.match(r"^[A-Z]", t)
        and (re.match(r"^[A-Za-z]{3,}", t) or not _DIGIT_RE.search(t))
        and t.lower() not in GENERIC_HEAD
        for t in toks
    )
    if sentence_initial:
        first = toks[0] if toks else ""
        if (first and first.lower() in GENERIC_HEAD
                and not acronym and not proper):
            proper = False

    # v1.1 rule 2: version/digit requires a co-occurring identity
    # signal. A digit alone never promotes; multi-token digit surfaces
    # ("Model 3", "component D6L11") are numbered generics, not
    # products — only a single-token versioned name qualifies.
    version_identity = has_digit and (
        acronym or proper
        or (len(toks) == 1 and any(_DIGIT_RE.search(t) for t in toks))
    )

    # v1.1 rule 3: weak modifiers do not count toward specificity.
    discriminative = [t for t in ct
                      if t.lower() not in WEAK_MODIFIERS
                      and t.lower() not in DEICTIC_MODIFIERS
                      and t.lower() not in _DET
                      and not _DIGIT_RE.search(t)]
    deictic = any(t.lower() in DEICTIC_MODIFIERS for t in ct)

    if acronym:
        return "GLOBAL", ("acronym_identity",)
    if version_identity:
        return "GLOBAL", ("versioned_identity_structure",)
    if proper:
        return "GLOBAL", ("proper_name_identity",)

    generic_head = head in GENERIC_HEAD

    # deictic/possessive reference -> document-scoped identity (the
    # reference is anchored to this document's context).
    if deictic and len(ct) >= 2:
        return "DOCUMENT_SCOPED", ("deictic_descriptive_reference",)

    # numbered reference on a capitalized head ("Model 3") is corpus
    # scoped; identifier on a lowercase generic head ("component D6L11")
    # stays mention-only.
    identifier = has_digit and not version_identity and not proper and not acronym
    if identifier and len(ct) >= 2:
        head_token = head_tokens[-1] if head_tokens else ""
        if generic_head and head_token[:1].isupper():
            return "CORPUS_SCOPED", ("numbered_reference",)
        if generic_head:
            return "MENTION_ONLY", ("bare_generic_common_noun",)

    if generic_head and len(discriminative) <= 1:
        return "MENTION_ONLY", ("bare_generic_common_noun",)

    if len(discriminative) >= 2:
        return "CORPUS_SCOPED", ("discriminative_descriptive_reference",)

    return "MENTION_ONLY", ("insufficient_referential_specificity",)


def decide(surface: str, core_type: str, extraction_score: float,
           mention_id: str | None = None,
           sentence_initial: bool = False) -> EntityAdmissionDecision:
    cls, reasons = _classify(surface, sentence_initial)
    if mention_id is None:
        mention_id = "mention_" + content_hash({
            "surface": surface, "type": core_type,
        })[:16]
    return EntityAdmissionDecision(
        mention_id=mention_id,
        surface=surface,
        core_type=core_type,
        extraction_score=extraction_score,
        reference_class=cls,
        reasons=reasons,
    )
