"""PHASE 1: ENTITY-HARBOR-V1 gold contract (admission_gold_v2).

v2 carries `scope` forward UNCHANGED from v1.1 so the existing policy
regression stays independently checkable, and adds the new Harbor axes
(anchor_kind / referentiality / reference_basis) as SPECIFICATION. The
Harbor contract is not implemented yet — the new items are expected to
fail until PHASE 2. These tests pin the invariants, not a passing score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_admission import decide

EVAL = ROOT / "eval" / "admission"
V2 = json.loads((EVAL / "admission_gold_v2.json").read_text())
V11 = json.loads((EVAL / "admission_gold_v1.1.json").read_text())
KEY = lambda i: (i["surface"], i["core_type"])

# REVISION 3b: GENERIC_GROUP renamed GENERIC; CONTEXT_REQUIRED added for
# surfaces the span cannot settle (the invariant: never guess from morphology).
ANCHOR = {"IDENTITY", "CONCEPT", "LOCAL_REFERENCE", "GENERIC", "UNKNOWN"}
STATUS = {"RESOLVED", "CONTEXT_REQUIRED", "ABSTAINED"}
REFTY = {"SPECIFIC", "GENERIC", "UNRESOLVED"}
BASIS = {"ANTECEDENT_RESOLVED", "DOCUMENT_CONSTITUTED",
         "EXTERNAL_UNRESOLVED", "AMBIGUOUS"}
SCOPE = {"GLOBAL", "CORPUS_SCOPED", "DOCUMENT_SCOPED", "MENTION_ONLY"}


def test_every_item_uses_the_declared_vocabularies():
    for i in V2["items"]:
        assert i["anchor_kind"] in ANCHOR, i
        assert i["referentiality"] in REFTY, i
        assert i["scope"] in SCOPE, i
        assert i["decision_status"] in STATUS, i
        if "reference_basis" in i:
            assert i["reference_basis"] in BASIS, i
        if i["anchor_kind"] == "UNKNOWN":
            assert i["decision_status"] != "RESOLVED", i


def test_reference_basis_only_asserted_with_document_context():
    """A surface string cannot determine reference_basis. Items without
    document context must not claim one."""
    for i in V2["items"]:
        rb = i.get("reference_basis")
        if rb and rb != "CONTEXT_REQUIRED":
            assert i.get("context_document"), (
                f"{i['surface']!r} asserts {rb} with no context_document")


def test_only_local_reference_carries_a_reference_basis():
    for i in V2["items"]:
        if "reference_basis" in i:
            assert i["anchor_kind"] == "LOCAL_REFERENCE", i


def test_revision_3b_rulings_are_recorded():
    by = {i["surface"]: i for i in V2["items"]}
    for surface, kind, status in (
            ("component D6L11", "IDENTITY", "RESOLVED"),
            ("Model 3", "IDENTITY", "RESOLVED"),
            ("Polymath retrieval system", "IDENTITY", "RESOLVED"),
            ("the ingestion system", "UNKNOWN", "CONTEXT_REQUIRED"),
            ("Qwen3 embedding model", "UNKNOWN", "CONTEXT_REQUIRED"),
            ("this service", "LOCAL_REFERENCE", "CONTEXT_REQUIRED"),
            ("our recommendation engine", "LOCAL_REFERENCE", "CONTEXT_REQUIRED")):
        assert by[surface]["anchor_kind"] == kind, surface
        assert by[surface]["decision_status"] == status, surface
        assert "ruling" in by[surface], surface


def test_named_anchor_does_not_determine_anchor_kind():
    """ctx-08 / ctx-09: identical structural evidence, opposite answers."""
    by = {i["surface"]: i for i in V2["items"]}
    a, b = by["Polymath retrieval system"], by["Qwen3 embedding model"]
    assert a["structural"]["named_anchor_present"]
    assert b["structural"]["named_anchor_present"]
    assert a["anchor_kind"] != b["anchor_kind"]


def test_v2_carries_v1_1_scope_forward_unchanged():
    prior = {KEY(i): i["label"] for i in V11["items"]}
    carried = [i for i in V2["items"] if KEY(i) in prior]
    assert len(carried) == len(V11["items"]) == 55
    for i in carried:
        assert i["scope"] == prior[KEY(i)], i["surface"]


def test_production_policy_still_scores_55_of_55_on_carried_scope():
    """v2 must not invalidate the existing admission regression."""
    prior = {KEY(i) for i in V11["items"]}
    carried = [i for i in V2["items"] if KEY(i) in prior]
    wrong = [i["surface"] for i in carried
             if decide(i["surface"], i["core_type"], 0.5).reference_class != i["scope"]]
    assert not wrong, wrong


def test_new_harbor_items_are_the_phase_2_target():
    """Documents the gap rather than asserting it away: the current policy
    collapses every new item to CORPUS_SCOPED via the token-count rule."""
    prior = {KEY(i) for i in V11["items"]}
    new = [i for i in V2["items"] if KEY(i) not in prior]
    assert len(new) == 10
    got = {decide(i["surface"], i["core_type"], 0.5).reference_class for i in new}
    assert got == {"CORPUS_SCOPED"}, (
        f"expected the token-count rule to collapse all new items; got {got}")


def test_bounded_collectives_and_generic_pluralities_are_distinguished():
    """REVISION 3a: the axis is bounded discourse individual vs plurality."""
    by = {i["surface"]: i for i in V2["items"]}
    for s in ("the engineering group", "the analytics team",
              "the radiology review board", "the pump failure",
              "the production stoppage", "the vision system"):
        assert by[s]["reference_basis"] == "DOCUMENT_CONSTITUTED", s
        assert by[s]["scope"] == "DOCUMENT_SCOPED", s
    assert by["the robotics vendor"]["reference_basis"] == "EXTERNAL_UNRESOLVED"
    for s in ("regional dispatchers", "two new surgeons", "three new instructors"):
        assert by[s]["anchor_kind"] == "GENERIC", s
        assert by[s]["scope"] == "MENTION_ONLY", s


def test_prior_golds_are_never_modified():
    assert V11["version"] == "admission-gold-1.1" and len(V11["items"]) == 55
    v1 = json.loads((EVAL / "admission_gold.json").read_text())
    assert v1["version"] == "admission-gold-1" and len(v1["items"]) == 44
