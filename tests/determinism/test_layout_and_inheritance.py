"""HEADING-IDENTITY-PRECISION-V1 and ANTECEDENT-IDENTITY-INHERITANCE-V1.

Both close defects where one referent became two objects: the first through
typography, the second through resolution minting its own id.
"""
import pytest

from polymath_shared.admission_interpreter import AdmissionResult
from polymath_shared.identity_allocation import allocate_identity
from polymath_shared.identity_evidence import identity_evidence
from polymath_shared.layout_evidence import (
    heading_regions, in_heading, independently_capitalized,
)


def _toks(*pairs):
    return [{"text": t, "pos": p, "lemma": t.lower()} for t, p in pairs]


# --------------------------------------------------------------- row 47 ---

def test_title_capitalization_in_a_heading_is_not_identity_evidence():
    d = identity_evidence("Working Memory",
                          tokens=_toks(("Working", "PROPN"), ("Memory", "PROPN")),
                          heading_context=True)
    assert d.is_identity is False
    assert "layout" in " ".join(d.exclusions)


def test_the_same_phrase_in_prose_is_unaffected():
    """The rule is scoped to heading CONTEXT, not to the phrase. Body prose
    keeps whatever evidence it had."""
    d = identity_evidence("Working Memory",
                          tokens=_toks(("Working", "PROPN"), ("Memory", "PROPN")),
                          heading_context=False)
    assert d.is_identity is True


@pytest.mark.parametrize("surface,tokens", [
    ("PostgreSQL", _toks(("PostgreSQL", "PROPN"))),
    ("GLiNER", _toks(("GLiNER", "PROPN"))),
    ("NIST Cybersecurity Framework",
     _toks(("NIST", "PROPN"), ("Cybersecurity", "PROPN"), ("Framework", "PROPN"))),
    ("TLS 1.3", _toks(("TLS", "PROPN"), ("1.3", "NUM"))),
])
def test_independent_identity_evidence_survives_in_headings(surface, tokens):
    """Only title-case-explicable evidence is withdrawn. Internal capitals,
    acronyms and version identifiers are choices the writer made, not the
    layout, so they still admit."""
    assert identity_evidence(surface, tokens=tokens,
                             heading_context=True).is_identity is True


def test_headings_are_recognized_from_line_structure_not_phrase_shape():
    """Deciding 'looks like a title' from the phrase would reintroduce the
    capitalization heuristic this rule removes."""
    text = "# Working Memory\n\nA Short Capitalized Prose Line is not a heading.\n"
    regions = heading_regions(text)
    assert in_heading(regions, 2, 16)          # inside the ATX heading
    assert not in_heading(regions, 18, 40)     # title-ish prose is NOT


def test_capitalization_discriminator():
    assert independently_capitalized("PostgreSQL")
    assert independently_capitalized("NIST")
    assert not independently_capitalized("Working")
    assert not independently_capitalized("Attention")


# --------------------------------------------------------------- row 48 ---

def _resolved(surface, resolves_to):
    return AdmissionResult(
        proposal_surface=surface, referential_surface=surface,
        core_type="CONCEPT", anchor_kind="LOCAL_REFERENCE",
        decision_status="RESOLVED", scope="DOCUMENT_SCOPED",
        reference_basis="ANTECEDENT_RESOLVED", graph_eligible=True,
        admission_reason="E4 exactly one compatible local antecedent",
        semantic_contract="admission-harbor-v2", resolves_to=resolves_to)


def test_resolved_reference_inherits_the_antecedents_identity():
    """same referent -> same identity. The reference must NOT mint an id
    from its own descriptive surface."""
    antecedent_id = "ent_recommendation_engine"
    ident = allocate_identity(_resolved("the new concept", "recommendation engine"),
                              corpus_id="c", doc_id="d", chunk_id="ch",
                              span_start=0, span_end=15,
                              inherit_entity_id=antecedent_id)
    assert ident.entity_id == antecedent_id
    assert ident.durable is True
    assert not ident.entity_id.startswith("entd_")


def test_resolution_without_a_durable_antecedent_earns_nothing():
    """`the second group` resolves to a generic population. There is no
    identity to inherit, so none is manufactured."""
    ident = allocate_identity(_resolved("the second group", "others"),
                              corpus_id="c", doc_id="d", chunk_id="ch",
                              span_start=0, span_end=16,
                              inherit_entity_id=None)
    assert ident.entity_id.startswith("mention_")
    assert ident.durable is False


def test_a_resolved_reference_never_allocates_a_document_scoped_id():
    """The specific bug: entd_<hash(local-reference surface)>."""
    for inherit in ("ent_x", None):
        ident = allocate_identity(_resolved("these notes", "Research Notes"),
                                  corpus_id="c", doc_id="d", chunk_id="ch",
                                  span_start=0, span_end=11,
                                  inherit_entity_id=inherit)
        assert not ident.entity_id.startswith("entd_"), (
            "a local reference minted a document-scoped identity from its "
            "own surface instead of inheriting the antecedent's")
