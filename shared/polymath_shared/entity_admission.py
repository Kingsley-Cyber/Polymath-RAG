"""Entity admission: reference identity classes (production, v1.1).

The boundary between "GLiNER recognized a Type" and "this mention
deserves durable graph identity" (E2/C1.1, promoted 2026-08-14).

Classes:
  GLOBAL          strong identity across corpora
  CORPUS_SCOPED   identity meaningful within one corpus
  DOCUMENT_SCOPED identity established within one document
  MENTION_ONLY    linguistic mention; evidence/provenance only, never
                  projected as a Neo4j Entity

Identity allocation (contract version entity-identity-v2 — the old
global-only ids are NOT interchangeable with scoped ids):
  GLOBAL          entity_id(type, normalized surface)        (unchanged)
  CORPUS_SCOPED   entc_ + hash(corpus, type, normalized)
  DOCUMENT_SCOPED entd_ + hash(corpus, doc, type, normalized)
  MENTION_ONLY    mention_ + hash(doc, chunk, offsets, type)

Deterministic; no model; no numeric fake confidence; every decision
carries reasons. See eval/admission/ for the frozen qualification
(55/55 gold + downstream G4 checkpoint).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from polymath_shared.identity import content_hash

POLICY_VERSION = "entity-admission-v1.1"
IDENTITY_CONTRACT = "entity-identity-v2"

_DET = {"the", "a", "an"}

#: FACT-ENDPOINT-ELIGIBILITY-V2 (2026-08-28).
#:
#: An UNRESOLVED closed-class pronoun is never a durable knowledge
#: identity. It remains fully valid as raw source, as a mention, and as
#: syntax/discourse evidence — it simply may not BE the thing a fact is
#: about.
#:
#: MEASURED before this gate: 557 of 3,184 accepted facts (17.5%) carried
#: a pronoun endpoint, producing `you --instance_of--> microsoft`,
#: `you --founded--> organization`, `they --uses--> ssh`. Three `they`
#: entities had additionally been admitted CORPUS_SCOPED, which let those
#: edges reach Neo4j.
#:
#: Closed class only — this list can never grow to cover a domain.
CLOSED_CLASS_PRONOUNS = frozenset({
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "this", "that", "these", "those", "who", "whom",
    "which", "what", "myself", "yourself", "himself", "herself",
    "itself", "ourselves", "themselves", "one", "ones",
})


def is_unresolved_pronoun(surface: str) -> bool:
    """True when `surface` is a bare closed-class pronoun.

    PRECISION FIRST. A naive lowercase membership test would destroy
    real named entities, so every one of these must survive:

        You.com   — contains punctuation, not a bare token
        WeWork    — internal capital, longer than the pronoun
        US / IT / WHO — ALL-CAPS acronym identity
        "They Might Be Giants" — multi-token

    The rule therefore fires ONLY on a single token, with no digits or
    punctuation, that is not all-caps, whose lowercase form is in the
    closed class. Sentence-initial "They" is still a pronoun, so
    capitalisation of a single token is not evidence of a name.
    """
    s = (surface or "").strip()
    if not s or " " in s:
        return False
    if not s.isalpha():                 # You.com, C3, don't
        return False
    if s.isupper() and len(s) > 1:      # US, IT, WHO, WE (org acronyms)
        return False
    if s != s.lower() and s != s.capitalize():
        return False                    # WeWork, iPhone-style casing
    return s.lower() in CLOSED_CLASS_PRONOUNS


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
    # FACT-ENDPOINT-ELIGIBILITY-V2: a bare closed-class pronoun is
    # evidence, never identity. Decided FIRST so no later branch
    # (acronym, proper, discriminative) can promote it — three `they`
    # entities had reached CORPUS_SCOPED that way and carried pronoun
    # edges into the graph.
    if is_unresolved_pronoun(surface):
        return "MENTION_ONLY", ("unresolved_closed_class_pronoun",)
    toks = _tokens(surface)
    ct = content_tokens(surface)
    head_tokens = [t for t in ct if not t.isdigit()]
    head = head_tokens[-1].lower() if head_tokens else ""

    acronym = any(_ACRONYM_RE.match(t) and len(t) >= 2 and t.lower() not in GENERIC_HEAD
                  for t in toks)
    has_digit = bool(_DIGIT_RE.search(surface))

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

    version_identity = has_digit and (
        acronym or proper
        or (len(toks) == 1 and any(_DIGIT_RE.search(t) for t in toks))
    )
    identifier = has_digit and not version_identity and not proper and not acronym

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

    if deictic and len(ct) >= 2:
        return "DOCUMENT_SCOPED", ("deictic_descriptive_reference",)

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


def decide_v1_1_historical(surface: str, core_type: str, extraction_score: float,
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


# S4: `decide` kept as an explicit HISTORICAL alias. Production must never
# call it — the single live authority is
# `admission_interpreter.interpret_admission(contract_version=...)`. A test
# asserts no production module imports this name.
decide = decide_v1_1_historical


def allocate_entity_id(
    surface: str,
    core_type: str,
    *,
    corpus_id: str,
    doc_id: str,
    chunk_id: str,
    span_start: int,
    span_end: int,
    extraction_score: float = 0.0,
    sentence_initial: bool = False,
) -> EntityAdmissionDecision:
    """One function for identity allocation at the admission boundary.

    Returns the decision with mention_id carrying the ALLOCATED
    identity for the class (GLOBAL/CORPUS_SCOPED/DOCUMENT_SCOPED use
    their durable ids as the mention identity; MENTION_ONLY uses the
    stable evidence mention id)."""
    decision = decide(surface, core_type, extraction_score,
                      sentence_initial=sentence_initial)
    cls = decision.reference_class
    norm_surface = re.sub(r"\s+", " ", surface).strip().lower()
    if cls == "GLOBAL":
        allocated = "ent_" + content_hash(
            {"core": core_type, "surface": norm_surface}
        )
    elif cls == "CORPUS_SCOPED":
        allocated = "entc_" + content_hash({
            "corpus": corpus_id, "type": core_type,
            "surface": norm_surface,
        })
    elif cls == "DOCUMENT_SCOPED":
        allocated = "entd_" + content_hash({
            "corpus": corpus_id, "doc": doc_id, "type": core_type,
            "surface": norm_surface,
        })
    else:
        allocated = "mention_" + content_hash({
            "doc": doc_id, "chunk": chunk_id, "type": core_type,
            "start": span_start, "end": span_end,
        })
    return EntityAdmissionDecision(
        mention_id=allocated,
        surface=surface,
        core_type=core_type,
        extraction_score=extraction_score,
        reference_class=cls,
        reasons=decision.reasons,
    )
