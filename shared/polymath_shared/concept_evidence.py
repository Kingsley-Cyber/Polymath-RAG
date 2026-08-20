"""CONCEPT-EVIDENCE-V1 (PHASE 2D) — cross-domain concept admission.

CROSS-DOMAIN INVARIANT
  1. ingestion never requires a domain-specific admission algorithm
  2. the same deterministic Harbor contract executes on any document
  3. unsupported semantic knowledge causes ABSTENTION, never guessed truth
  4. domain vocabularies are versioned EVIDENCE PROVIDERS, not rule changes
  5. absence of concept recognition never prevents text retrieval
  6. every promoted concept carries an auditable evidence chain
  7. same document + same contracts/resources -> same result

Nothing in this module names a domain. A database textbook
("write-ahead log"), a medical text ("acute respiratory distress
syndrome") and a fantasy novel ("the Ember Rite") are handled by the SAME
machinery; only the evidence sources differ.

Two layers, deliberately separated (evidence world vs truth world):

  2D.1 concept_candidate()  "could this denote a reusable concept?"
                            -> no graph authority whatsoever
  2D.2 admit_concept()      "is there AUDITABLE evidence it is a stable
                            concept?" -> CONCEPT, else abstain

AUTHORITIES (any one suffices):
  DOCUMENT_DEFINED     the document explicitly establishes the term
  GLOSSARY_DECLARED    glossary / terminology / definition-list entry
  EXISTING_CANONICAL   previously admitted under a valid evidence chain
  CURATED_LEXICON      exact entry in a versioned auditable vocabulary

SUPPORTING EVIDENCE ONLY — never sufficient alone:
  multiword form · frequency · corpus uniqueness · capitalization ·
  provider confidence · technical-looking morphology

FORBIDDEN and asserted against by tests: phrase whitelists for the
current corpus, domain-specific code paths, "two words -> concept",
"appears N times -> concept", similarity/embeddings as truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

CONCEPT_CONTRACT = "concept-evidence-v1"


class ConceptEvidenceKind(str, Enum):
    DOCUMENT_DEFINED = "DOCUMENT_DEFINED"
    GLOSSARY_DECLARED = "GLOSSARY_DECLARED"
    EXISTING_CANONICAL = "EXISTING_CANONICAL"
    CURATED_LEXICON = "CURATED_LEXICON"


@dataclass(frozen=True)
class ConceptEvidence:
    kind: ConceptEvidenceKind
    term: str
    quote: str = ""
    source_document_id: str | None = None
    source_offsets: tuple[int, int] | None = None
    external_source_id: str | None = None
    external_source_version: str | None = None
    contract: str = CONCEPT_CONTRACT


@dataclass(frozen=True)
class ConceptRecord:
    concept_id: str
    canonical_term: str
    normalized_term: str
    evidence_kind: ConceptEvidenceKind
    source_document_id: str | None = None
    source_offsets: tuple[int, int] | None = None
    external_source_id: str | None = None
    external_source_version: str | None = None
    concept_contract: str = CONCEPT_CONTRACT


# --- definitional patterns -------------------------------------------------
# Genus-differentia and explicit-definition shapes. These are properties of
# ENGLISH EXPOSITION, not of any subject matter, which is why the same
# patterns fire on a pattern catalogue, a physiology text and a novel.
# Determiners that can introduce a GENUS noun in a definition. "another" is
# classificatory ("X is another condition that...") and is a grammatical
# variant, not a semantic widening. Deliberately excludes "some"/"any", which
# hedge existence rather than assign a genus.
_ART = r"(?:a|an|the|another)"
# CONCEPT-DEFINITION-COVERAGE-V1: copulas may be hedged or modal. Academic
# prose rarely writes "X is a Y"; it writes "X is often described as the Y".
_COP = r"(?:is|are|was|were|can\s+be|may\s+be|could\s+be|has\s+been|have\s+been)"
# up to three hedging adverbs ("often", "generally", "commonly", "widely"...)
_HEDGE = r"(?:\w+\s+){0,3}?"
# participles that mark an EXPLICIT definition rather than a description of state
_DEFV = (r"(?:described|defined|understood|known|characteri[sz]ed|conceived|"
         r"regarded|viewed|treated|conceptuali[sz]ed|referred\s+to)")

_DEFINITIONAL = (
    # "X is a/an/the <noun> ..." — requires an article, so "X is slow" is not a
    # definition while "X is the process by which..." is.
    (rf"^{{term}}\s+{_COP}\s+{_ART}\s+\w+", "copular genus-differentia"),
    (rf"^{_ART}\s+{{term}}\s+{_COP}\s+{_ART}\s+\w+", "copular genus-differentia (article-initial)"),
    # HEDGED: "X is often described as the Y", "X can be defined as a Y",
    # "X is generally understood as the Y". The article after "as" is still
    # required, so "X is widely used" and "X is known to fail" do not match.
    (rf"^{{term}}\s+{_COP}\s+{_HEDGE}{_DEFV}\s+as\s+{_ART}\s+\w+", "hedged definitional copula"),
    (rf"^{_ART}\s+{{term}}\s+{_COP}\s+{_HEDGE}{_DEFV}\s+as\s+{_ART}\s+\w+", "hedged definitional copula (article-initial)"),
    (r"^{term}\s+refers?\s+to\b", "explicit 'refers to'"),
    (r"^{term}\s+(?:is|are)\s+defined\s+as\b", "explicit 'defined as'"),
    (r"^{term}\s+(?:means|denotes|describes|signifies)\b", "explicit 'means/denotes'"),
    # "We define X as ...", "By X we mean ..."
    (r"\bwe\s+define\s+{term}\s+as\b", "author-declared definition"),
    (r"\bby\s+{term}\s+we\s+mean\b", "author-declared definition"),
    # "X, also called/known as Y"
    (r"^{term},\s+also\s+(?:called|known\s+as|termed)\b", "explicit alias declaration"),
    # "X occurs when ...", "X happens when ..." — eventive definition
    (r"^{term}\s+(?:occurs|happens|arises|takes\s+place)\s+when\b", "eventive definition"),
    (rf"^{{term}},\s+{_ART}\s+\w+.*?,", "appositive definition"),
    (rf"^{_ART}\s+{{term}},\s+{_ART}\s+\w+.*?,", "appositive definition (article-initial)"),
)

_GLOSSARY_HEADING = re.compile(
    r"^\s*#{1,6}\s*(glossary|terminology|definitions|key terms|nomenclature)\b",
    re.I | re.M)
# "Term — definition" / "Term: definition" / "Term - definition"
_DEF_LIST = r"^\s*(?:[-*]\s*)?{term}\s*(?:[—–:-])\s+\S"


def _norm(t: str) -> str:
    return " ".join(re.sub(r"[^\w\s\-]", " ", t.lower()).split())


def _strip_det(t: str) -> str:
    return re.sub(r"^(?:the|a|an|this|that|our|its|their)\s+", "", t.strip(), flags=re.I)


def concept_candidate(surface: str, *, is_identity: bool = False,
                      is_generic: bool = False) -> bool:
    """2D.1 — could this denote a reusable concept? NO graph authority.

    Permissive by design: candidacy costs nothing, admission is what is
    gated. Excludes only what another Harbor branch already owns.
    """
    if is_identity or is_generic:
        return False
    return bool(_norm(_strip_det(surface)))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def find_document_definition(term: str, text: str,
                             doc_id: str | None = None) -> ConceptEvidence | None:
    """DOCUMENT_DEFINED — the document itself establishes the term."""
    bare = _strip_det(term)
    pat = re.escape(bare)
    for sent in _sentences(text):
        for tmpl, why in _DEFINITIONAL:
            if re.search(tmpl.replace("{term}", pat), sent, re.I):
                off = text.find(sent)
                return ConceptEvidence(
                    ConceptEvidenceKind.DOCUMENT_DEFINED, bare, quote=sent[:200],
                    source_document_id=doc_id,
                    source_offsets=(off, off + len(sent)) if off >= 0 else None)
    return None


def find_glossary_declaration(term: str, text: str,
                              doc_id: str | None = None) -> ConceptEvidence | None:
    """GLOSSARY_DECLARED — the document declares its own vocabulary."""
    m = _GLOSSARY_HEADING.search(text)
    if not m:
        return None
    section = text[m.end():]
    nxt = re.search(r"^\s*#{1,6}\s+\S", section, re.M)
    if nxt:
        section = section[:nxt.start()]
    bare = _strip_det(term)
    if re.search(_DEF_LIST.replace("{term}", re.escape(bare)), section, re.I | re.M):
        off = text.find(bare, m.end())
        return ConceptEvidence(
            ConceptEvidenceKind.GLOSSARY_DECLARED, bare,
            quote=m.group(0).strip(), source_document_id=doc_id,
            source_offsets=(off, off + len(bare)) if off >= 0 else None)
    return None


def find_registry_entry(term: str,
                        registry: dict[str, ConceptRecord] | None) -> ConceptEvidence | None:
    """EXISTING_CANONICAL — admitted earlier under a valid evidence chain."""
    if not registry:
        return None
    rec = registry.get(_norm(_strip_det(term)))
    if rec is None:
        return None
    return ConceptEvidence(ConceptEvidenceKind.EXISTING_CANONICAL, rec.canonical_term,
                           quote=f"concept_id={rec.concept_id}",
                           external_source_id=rec.external_source_id,
                           external_source_version=rec.external_source_version)


def find_lexicon_entry(term: str, lexicon: dict | None) -> ConceptEvidence | None:
    """CURATED_LEXICON — EXACT entry in a versioned auditable vocabulary.

    Exact match only: fuzzy or similarity matching would make an unversioned
    judgement call and is forbidden as truth evidence.
    """
    if not lexicon:
        return None
    entries = lexicon.get("entries", {})
    rec = entries.get(_norm(_strip_det(term)))
    if rec is None:
        return None
    return ConceptEvidence(
        ConceptEvidenceKind.CURATED_LEXICON, _strip_det(term),
        quote=rec.get("gloss", "")[:200],
        external_source_id=lexicon.get("source_id"),
        external_source_version=lexicon.get("source_version"))


def admit_concept(term: str, *, document_text: str = "", doc_id: str | None = None,
                  registry: dict[str, ConceptRecord] | None = None,
                  lexicon: dict | None = None) -> ConceptEvidence | None:
    """2D.2 — return auditable evidence, or None meaning ABSTAIN.

    Order is by directness of authority. None is a legitimate, expected
    outcome: an unfamiliar concept reduces graph coverage, never graph
    correctness, and the mention plus text retrieval survive regardless.
    """
    for finder in (
        lambda: find_document_definition(term, document_text, doc_id) if document_text else None,
        lambda: find_glossary_declaration(term, document_text, doc_id) if document_text else None,
        lambda: find_registry_entry(term, registry),
        lambda: find_lexicon_entry(term, lexicon),
    ):
        ev = finder()
        if ev is not None:
            return ev
    return None
