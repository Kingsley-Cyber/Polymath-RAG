"""E4-ANTECEDENT-TYPE-COMPATIBILITY-V1.

An antecedent must be semantically compatible with the referring noun phrase
BEFORE E4 counts candidates. Filtering after the exactly-one test lets an
incompatible candidate satisfy "exactly one" and resolve anyway — which is
how `the company` came to inherit `Raleigh`'s identity.

    Positive compatibility can support resolution.
    Type incompatibility BLOCKS resolution.
    Unknown compatibility does NOT become positive compatibility.
"""
import pytest

from polymath_shared.entity_harbor import ReferenceBasis
from polymath_shared.discourse_reference import resolve, type_compatible


# ------------------------------------------------------- the ruling ------

@pytest.mark.parametrize("target,anchor,atype", [
    ("The company", "Raleigh", "Location"),            # the observed failure
    ("The hospital", "Acme Corporation", "Person"),
    ("The company", "Seattle", "Location"),
    ("The database", "John Smith", "Person"),
    ("The service", "September outage", "Event"),
])
def test_type_incompatible_antecedents_are_refused(target, anchor, atype):
    head = target.split()[-1].lower()
    ctx = [f"{anchor} appeared alongside the {head} in the review.",
           f"{target} was mentioned again."]
    r = resolve(target, ctx, admitted_anchors=[(anchor, atype)])
    assert r.basis is not ReferenceBasis.ANTECEDENT_RESOLVED, (
        f"{target!r} resolved to {anchor!r} [{atype}] despite type incompatibility")
    assert r.resolves_to != anchor


@pytest.mark.parametrize("target,anchor,atype", [
    ("The company", "Acme Corporation", "Organization"),
    ("The hospital", "Lakeshore General Hospital", "Organization"),
])
def test_type_compatible_antecedents_still_resolve(target, anchor, atype):
    head = target.split()[-1].lower()
    ctx = [f"{anchor} filed the report about the {head}.",
           f"{target} responded."]
    r = resolve(target, ctx, admitted_anchors=[(anchor, atype)])
    assert r.basis is ReferenceBasis.ANTECEDENT_RESOLVED
    assert r.resolves_to == anchor


# ------------------------------------- head identity needs no type ------

@pytest.mark.parametrize("target,antecedent", [
    ("the outage", "the September outage"),
    ("the patient portal", "the CareConnect portal"),
    ("the mentor engine", "the Mentor assessment engine"),
    ("the invoicing system", "the QuickScale invoicing system"),
])
def test_head_sharing_resolution_is_not_type_filtered(target, antecedent):
    """The four inheritances that were already correct. Head identity IS the
    evidence; requiring type corroboration too would discard it."""
    ctx = [f"{antecedent} was introduced first.", f"{target} then failed."]
    r = resolve(target, ctx, admitted_anchors=[])
    assert r.basis is ReferenceBasis.ANTECEDENT_RESOLVED, (
        f"{target!r} lost its head-sharing antecedent {antecedent!r}")


# ------------------------------------------------ the predicate ---------

def test_compatibility_is_three_valued():
    assert type_compatible("company", "Organization") is True
    assert type_compatible("company", "Location") is False
    assert type_compatible("line", "Organization") is None      # head unknown
    assert type_compatible("company", None) is None             # anchor unknown


def test_unknown_compatibility_does_not_support_resolution():
    """`assembly line` -> `Crestline Automation`: head `line` carries no type,
    so co-occurrence alone cannot establish an antecedent."""
    ctx = ["Crestline Automation runs the assembly line in Toledo.",
           "The assembly line stopped."]
    r = resolve("The assembly line", ctx,
                admitted_anchors=[("Crestline Automation", "Organization")])
    assert r.resolves_to != "Crestline Automation"


def test_filtering_precedes_the_exactly_one_count():
    """Structural: an incompatible candidate must never reach the count. With
    one incompatible and one compatible anchor, the compatible one resolves —
    it does not become AMBIGUOUS because the other was counted first."""
    ctx = ["Acme Corporation and Seattle both appear near the company here.",
           "The company replied."]
    r = resolve("The company", ctx,
                admitted_anchors=[("Seattle", "Location"),
                                  ("Acme Corporation", "Organization")])
    assert r.resolves_to == "Acme Corporation"
