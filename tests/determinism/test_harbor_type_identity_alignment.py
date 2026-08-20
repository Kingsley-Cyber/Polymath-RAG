"""HARBOR-TYPE-IDENTITY-ALIGNMENT-V1.

    provider type helps DESCRIBE an identity;
    it does not by itself DEFINE identity.

`core_type` is a provisional neural label and is part of the identity key, so
model typing instability fragmented one referent into several canonical
entities. The fix inverts the precedence for kinds a qualified Harbor
authority has settled — and deliberately does NOT for the kind where provider
type is what keeps homonyms apart.
"""
import pytest

from polymath_shared.admission_interpreter import AdmissionResult
from polymath_shared.identity_allocation import allocate_identity, canonical_type


def _result(surface, core, anchor, scope, *, basis=None, reason="test"):
    return AdmissionResult(
        proposal_surface=surface, referential_surface=surface, core_type=core,
        anchor_kind=anchor, decision_status="RESOLVED", scope=scope,
        reference_basis=basis, graph_eligible=True, admission_reason=reason,
        semantic_contract="admission-harbor-v2")


def _id(result, **kw):
    kw.setdefault("corpus_id", "c")
    kw.setdefault("doc_id", "d")
    kw.setdefault("chunk_id", "ch")
    kw.setdefault("span_start", 0)
    kw.setdefault("span_end", 1)
    return allocate_identity(result, **kw).entity_id


# ------------------------------------------------------ the motivating case

@pytest.mark.parametrize("provider_type", ["Concept", "Technology", "Method",
                                           "Process"])
def test_a_document_defined_concept_is_one_identity_whatever_the_provider_guessed(
        provider_type):
    """`working memory` came back Concept in one sentence and Technology in
    another. Once the document itself defines the term, that authority
    outranks the provider guess and the referent is ONE concept."""
    baseline = _id(_result("working memory", "Concept", "CONCEPT",
                           "CORPUS_SCOPED", reason="concept: DOCUMENT_DEFINED"))
    other = _id(_result("working memory", provider_type, "CONCEPT",
                        "CORPUS_SCOPED", reason="concept: DOCUMENT_DEFINED"))
    assert baseline == other, (
        f"provider type {provider_type!r} fragmented a document-defined "
        "concept into a second canonical identity")


# ---------------------------------------------------- the overmerge guard

@pytest.mark.parametrize("surface,a,b", [
    ("Java", "Technology", "Location"),        # language vs island
    ("Apple", "Organization", "Product"),      # company vs fruit
    ("Mercury", "Concept", "Location"),        # element vs planet
    ("Amazon", "Organization", "Location"),
])
def test_named_identities_keep_their_type_so_homonyms_stay_apart(surface, a, b):
    """Provider type is DELIBERATELY retained for IDENTITY. Collapsing it
    here would overmerge, which is the more damaging error."""
    assert _id(_result(surface, a, "IDENTITY", "GLOBAL")) != \
           _id(_result(surface, b, "IDENTITY", "GLOBAL")), (
        f"{surface} [{a}] and {surface} [{b}] were merged into one identity")


def test_alignment_does_not_merge_on_string_equality_alone():
    """A concept and a named identity sharing a surface are not the same
    thing. The gate keys off Harbor evidence, not matching strings."""
    concept = _id(_result("Mercury", "Concept", "CONCEPT", "CORPUS_SCOPED",
                          reason="concept: DOCUMENT_DEFINED"))
    named = _id(_result("Mercury", "Concept", "IDENTITY", "GLOBAL"))
    assert concept != named


# --------------------------------------------------------- the precedence

def test_canonical_type_names_the_authority_not_the_provider():
    assert canonical_type(_result("x", "Technology", "CONCEPT", "CORPUS_SCOPED")) == "CONCEPT"
    assert canonical_type(_result("x", "Technology", "IDENTITY", "GLOBAL")) == "Technology"


def test_provider_type_is_retained_as_evidence_not_discarded():
    """The gate changes which type NAMES the identity. The provider's own
    label must survive on the record — it is extraction evidence."""
    r = _result("working memory", "Technology", "CONCEPT", "CORPUS_SCOPED")
    ident = allocate_identity(r, corpus_id="c", doc_id="d", chunk_id="ch",
                              span_start=0, span_end=1)
    assert ident.admission.core_type == "Technology"


def test_local_references_are_unaffected_and_still_inherit():
    """Row 48's rule takes precedence; alignment must not disturb it."""
    r = _result("the new concept", "Concept", "LOCAL_REFERENCE",
                "DOCUMENT_SCOPED", basis="ANTECEDENT_RESOLVED")
    assert allocate_identity(r, corpus_id="c", doc_id="d", chunk_id="ch",
                             span_start=0, span_end=1,
                             inherit_entity_id="ent_anchor").entity_id == "ent_anchor"


def test_the_alignment_contract_is_in_the_semantic_bundle():
    from polymath_shared.execution import semantic_authorities

    assert semantic_authorities()["type_identity_alignment_contract"] == \
        "harbor-type-identity-alignment-v1"
