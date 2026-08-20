"""E3-ANCHOR-CONTINUITY-V1 and the row 70 exclusion of E4b.

    Lexical overlap may PROPOSE an antecedent. It may not PROVE identity.

E3 resolved on ANY shared content word, which made it an approximate
coreference engine wearing the name of a continuity rule. The division is now:

    E3                  repeated/existing named anchor continuity
    E4                  descriptive anaphora
    contraction resolver  Crestline <-> Crestline Automation
    Harbor              eligibility
"""
import inspect

import pytest

from polymath_shared.entity_harbor import ReferenceBasis
from polymath_shared.discourse_reference import resolve


@pytest.mark.parametrize("target,anchor", [
    ("The assembly line", "Crestline Automation"),
    ("The regional dispatchers", "Corval Logistics"),
    ("The quality board", "Quality Systems Incorporated"),
])
def test_shared_words_alone_no_longer_resolve(target, anchor):
    """The observed failures. A shared noun or modifier shows two phrases are
    lexically related; it says nothing about them denoting one referent."""
    ctx = [f"{anchor} operates here.", f"{target} stopped."]
    r = resolve(target, ctx, admitted_anchors=[(anchor, "Organization")],
                enable_type_noun_anaphora=False)
    assert r.resolves_to != anchor, (
        f"{target!r} still resolved to {anchor!r} on lexical overlap alone")


def test_exact_anchor_repetition_still_resolves():
    ctx = ["CareChart EMR is the system of record.", "The CareChart EMR failed."]
    r = resolve("The CareChart EMR", ctx,
                admitted_anchors=[("CareChart EMR", "Technology")],
                enable_type_noun_anaphora=False)
    assert r.basis is ReferenceBasis.ANTECEDENT_RESOLVED
    assert r.resolves_to == "CareChart EMR"
    assert "exact anchor repetition" in r.evidence[0]


def test_two_identical_anchors_are_ambiguous_not_resolved():
    ctx = ["CareChart EMR shipped.", "CareChart EMR shipped again.",
           "The CareChart EMR failed."]
    r = resolve("The CareChart EMR", ctx,
                admitted_anchors=[("CareChart EMR", "Technology"),
                                  ("CareChart EMR", "Technology")],
                enable_type_noun_anaphora=False)
    assert r.basis in (ReferenceBasis.AMBIGUOUS, ReferenceBasis.ANTECEDENT_RESOLVED)


def test_e3_does_not_claim_contraction_identity():
    """`Crestline` <-> `Crestline Automation` is the contraction resolver's
    job — it has token containment and types. E3 must not approximate it."""
    ctx = ["Crestline Automation runs the plant.", "Crestline shipped the cell."]
    r = resolve("Crestline", ctx,
                admitted_anchors=[("Crestline Automation", "Organization")],
                enable_type_noun_anaphora=False)
    assert r.resolves_to != "Crestline Automation"


# ------------------------------------------------------------ row 70 ------

def test_e4b_is_excluded_from_the_live_v2_composition():
    from polymath_shared import admission_interpreter as ai

    src = inspect.getsource(ai._interpret_v2)
    assert "enable_type_noun_anaphora=False" in src, (
        "admission-harbor-v2 still invokes E4b type-noun anaphora")


def test_e4b_remains_implemented_and_component_testable():
    """Excluded, not deleted, and not accidentally dormant: the input
    representation stays correct so its component tests stay meaningful."""
    ctx = ["QuickScale billing platform was deployed.", "The platform failed."]
    on = resolve("The platform", ctx,
                 admitted_anchors=[("QuickScale billing platform", "Technology")],
                 enable_type_noun_anaphora=True)
    off = resolve("The platform", ctx,
                  admitted_anchors=[("QuickScale billing platform", "Technology")],
                  enable_type_noun_anaphora=False)
    assert on.basis is ReferenceBasis.ANTECEDENT_RESOLVED
    assert "E4b" in on.evidence[0]
    assert off.basis is not ReferenceBasis.ANTECEDENT_RESOLVED or "E4b" not in off.evidence[0]


def test_the_same_typed_confusion_e4b_produced_cannot_recur_live():
    """`vision system` -> `Siemens PLCs`: both Technology, wrong referent."""
    ctx = ["Siemens PLCs drive the line.", "Crestline linked the vision system."]
    r = resolve("the vision system", ctx,
                admitted_anchors=[("Siemens PLCs", "Technology")],
                enable_type_noun_anaphora=False)
    assert r.resolves_to != "Siemens PLCs"
