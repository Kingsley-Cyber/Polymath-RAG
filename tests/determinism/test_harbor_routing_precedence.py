"""PHASE 2C.2 — Harbor routing precedence.

Referential-envelope recovery (2C.1) must not demote an already-qualified
identity-bearing mention. Identity is tested on the RAW case-preserving
`proposal_surface`, BEFORE the determiner-bearing envelope is inspected.

The adversarial case matters most: the router must NOT become
"proper token somewhere in the envelope -> IDENTITY". That is why the
predicate is the frozen admission identity rule, not `named_anchor_present`
(REVISION 3b: structural evidence, never authority).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_admission import decide

# Load by explicit file path. Several eval/ directories contain a module named
# `harness.py`, so putting any of them on sys.path shadows the others and breaks
# unrelated suites (this test did exactly that to the Q1 regression).
def _load(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_attr = _load("_harbor_attribution", ROOT / "eval/doc_audit/harbor_attribution.py")
DECISIVE_IDENTITY_REASONS = _attr.DECISIVE_IDENTITY_REASONS
decisive_identity = _attr.decisive_identity

GOLD_V2 = {i["surface"].lower(): i for i in json.loads(
    (ROOT / "eval/admission/admission_gold_v2.json").read_text())["items"]}


def test_identity_bearing_proposals_stay_identity_under_envelope_recovery():
    """The four 2C.1 regressions. Each gains a determiner from the envelope
    and must still route as IDENTITY."""
    for proposal in ("FreightNet routing platform", "Crestline automation team",
                     "Cobalt assembly cell", "West Coast logistics consortium"):
        ok, why = decisive_identity(proposal, "Technology")
        assert ok, f"{proposal!r} lost decisive identity ({why})"
        assert why in DECISIVE_IDENTITY_REASONS


def test_definite_descriptions_still_reach_the_discourse_consumer():
    """Identity-first must not swallow genuine definite descriptions."""
    for proposal in ("vision system", "pump failure", "robotics vendor",
                     "regional dispatchers", "mentor engine"):
        ok, _ = decisive_identity(proposal, "Technology")
        assert not ok, f"{proposal!r} wrongly claims decisive identity"


def test_identity_is_read_from_the_proposal_not_the_envelope():
    """A determiner supplied by the envelope must never itself be identity
    evidence, and must never remove identity either."""
    bare, _ = decisive_identity("FreightNet routing platform", "Technology")
    withdet, _ = decisive_identity("the FreightNet routing platform", "Technology")
    assert bare and withdet          # determiner is irrelevant to the predicate
    # a description does not become identity by acquiring a determiner
    assert not decisive_identity("vision system", "Technology")[0]
    assert not decisive_identity("the vision system", "Technology")[0]


def test_qualified_ruling_outranks_the_identity_predicate():
    """ADVERSARIAL: `Qwen3 embedding model` SATISFIES the frozen identity
    predicate, but REVISION 3b ruled it CONTEXT_REQUIRED because the surface
    cannot say whether it is one deployed model or the Qwen3 family. The
    router must consult the qualified ruling first, or identity-first routing
    would silently overturn a governance decision."""
    ok, why = decisive_identity("Qwen3 embedding model", "Technology")
    assert ok, "precondition: the predicate does fire here"
    assert why == "versioned_identity_structure"
    ruling = GOLD_V2["qwen3 embedding model"]
    assert ruling["anchor_kind"] == "UNKNOWN"
    assert ruling["decision_status"] == "CONTEXT_REQUIRED"
    assert "ruling" in ruling      # routing precedence keys on this


def test_predicate_uses_no_new_or_widened_signals():
    """Only the three reasons the frozen admission policy already emits."""
    assert DECISIVE_IDENTITY_REASONS == {
        "acronym_identity", "versioned_identity_structure", "proper_name_identity"}
    for surface in ("FreightNet routing platform", "vision system", "Model 3"):
        _, why = decisive_identity(surface, "Technology")
        assert why == decide(surface, "Technology", 0.9).reasons[0]


def test_named_anchor_present_is_not_the_predicate():
    """`Qwen3 embedding model` and `Polymath retrieval system` carry identical
    structural evidence; only the qualified ruling separates them."""
    a = GOLD_V2["polymath retrieval system"]
    b = GOLD_V2["qwen3 embedding model"]
    assert a["structural"]["named_anchor_present"]
    assert b["structural"]["named_anchor_present"]
    assert a["anchor_kind"] != b["anchor_kind"]


def test_identity_never_derived_from_normalized_surface():
    for raw in ("FreightNet routing platform", "Crestline automation team",
                "Cobalt assembly cell", "West Coast logistics consortium"):
        assert decisive_identity(raw, "Technology")[0]
        assert not decisive_identity(raw.lower(), "Technology")[0], (
            f"{raw.lower()!r} must not yield identity — case is load-bearing")
