"""IDENTITY-ALLOCATION-V1 — scope to durable id, for a settled admission.

S4c. Separates the two questions the plan keeps apart:

    interpret_admission()  "what IS this reference?"      -> AdmissionResult
    allocate_identity()    "may it become durable identity?" -> MentionIdentity

Durability is decided by `graph_eligible()` alone (plan line 139: ADMISSION
answers "is this allowed to become durable identity?"; line 1244: every
admission_class consumer moves to graph_eligible()). A reference that is
merely *resolved* does not earn a durable id — successful anaphora must not
manufacture identity.

The id hash uses a whitespace/case-normalized surface. That is the sanctioned
lookup use of normalization; nothing here CLASSIFIES from a normalized
surface, which remains forbidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from polymath_shared.admission_interpreter import AdmissionResult
from polymath_shared.identity import content_hash

IDENTITY_ALLOCATION_CONTRACT = "identity-allocation-v1"
TYPE_ALIGNMENT_CONTRACT = "harbor-type-identity-alignment-v1"


@dataclass(frozen=True)
class MentionIdentity:
    """One span's single interpretation plus the identity it earned."""
    admission: AdmissionResult
    entity_id: str
    durable: bool

    @property
    def admission_class(self) -> str:
        """The scope a consumer may act on. An ineligible decision reports
        MENTION_ONLY however it was scoped, so no consumer can treat an
        abstention as a durable class."""
        return self.admission.scope if self.durable else "MENTION_ONLY"


def canonical_type(result: AdmissionResult) -> str:
    """HARBOR-TYPE-IDENTITY-ALIGNMENT-V1 — which type NAMES the identity.

        provider type helps DESCRIBE an identity;
        it does not by itself DEFINE identity.

    `core_type` is a provisional neural label. Model typing is not stable
    across a diverse corpus — `working memory` came back Concept in one
    sentence and Technology in another, `transformer` alternates between
    Technology/Model/Architecture — and because the type is part of the
    identity key, that instability split one referent into several canonical
    entities.

    The precedence is inverted here:

        qualified semantic authority  ->  canonical identity namespace
        provider type                 ->  retained as evidence

    Applied ONLY where a stronger Harbor authority has actually established
    the semantic kind:

      CONCEPT  the document itself defined the term (DOCUMENT_DEFINED,
               GLOSSARY_DECLARED, ...). That authority outranks a competing
               provider guess, so the concept is named by its concept-hood,
               not by whichever label the extractor produced this time.

      IDENTITY provider type is DELIBERATELY retained. It is what keeps
               genuine homonyms apart — Apple the company from Apple the
               fruit, Java the language from Java the island, Mercury the
               planet from Mercury the element. Collapsing type here would
               overmerge, which is the more damaging error.

    This is not GLiNER type arbitration. Nothing here adjudicates between
    competing neural labels; it decides only whether a provisional label is
    allowed to fragment an identity a qualified authority already settled.
    """
    if result.anchor_kind == "CONCEPT":
        return "CONCEPT"
    return result.core_type


def normalized_for_lookup(surface: str) -> str:
    return re.sub(r"\s+", " ", surface).strip().lower()


def span_identity_key(span, corpus_id: str) -> tuple:
    """Identity of a PROPOSAL, not of a reference: the exact span a provider
    proposed. Two consumers asking about the same span must produce the same
    key or they will silently allocate twice."""
    return (corpus_id, span.doc_id, span.chunk_id, span.start, span.end,
            span.core_type.value)


def allocate_identity(result: AdmissionResult, *, corpus_id: str, doc_id: str,
                      chunk_id: str, span_start: int, span_end: int,
                      inherit_entity_id: str | None = None) -> MentionIdentity:
    """Route a settled admission to its identity.

    GLOBAL          -> ent_   type + surface, corpus-independent
    CORPUS_SCOPED   -> entc_  corpus + type + surface
    DOCUMENT_SCOPED -> entd_  corpus + doc + type + surface
    otherwise       -> mention_  stable evidence id, never durable

    ANTECEDENT-IDENTITY-INHERITANCE-V1 takes precedence over all of it. A
    reference that RESOLVED to an antecedent denotes that antecedent, so it
    must carry the antecedent's identity:

        same referent  ->  same identity

    Minting `entd_<hash("the new concept")>` from the reference's own
    descriptive surface would assert the opposite — same referent, different
    identity — and duplicate the node the resolution just found. If the
    antecedent holds no durable identity of its own (it was a generic
    population, or a bare noun phrase that was never admitted), there is
    nothing to inherit and the reference is not eligible. Resolution never
    manufactures identity.
    """
    if result.reference_basis == "ANTECEDENT_RESOLVED":
        if inherit_entity_id:
            return MentionIdentity(admission=result,
                                   entity_id=inherit_entity_id, durable=True)
        return MentionIdentity(
            admission=result,
            entity_id="mention_" + content_hash({
                "doc": doc_id, "chunk": chunk_id, "type": result.core_type,
                "start": span_start, "end": span_end}),
            durable=False)

    durable = bool(result.graph_eligible)
    # Key identity on the PROPOSAL surface, never on the envelope.
    # The envelope is an INTERPRETATION artifact — it exists so a definite
    # description reaches the discourse consumer with its determiner intact.
    # Keying on it would split one referent in two: `the CareConnect portal`
    # and `CareConnect portal` would hash differently and become separate
    # entities purely because of a determiner. The proposal surface is what
    # the provider actually delimited, so it is the stable identity key.
    surface = normalized_for_lookup(result.proposal_surface)
    core = canonical_type(result)
    scope = result.scope

    if durable and scope == "GLOBAL":
        entity_id = "ent_" + content_hash({"core": core, "surface": surface})
    elif durable and scope == "CORPUS_SCOPED":
        entity_id = "entc_" + content_hash({
            "corpus": corpus_id, "type": core, "surface": surface})
    elif durable and scope == "DOCUMENT_SCOPED":
        entity_id = "entd_" + content_hash({
            "corpus": corpus_id, "doc": doc_id, "type": core,
            "surface": surface})
    else:
        durable = False
        entity_id = "mention_" + content_hash({
            "doc": doc_id, "chunk": chunk_id, "type": core,
            "start": span_start, "end": span_end})

    return MentionIdentity(admission=result, entity_id=entity_id,
                           durable=durable)
