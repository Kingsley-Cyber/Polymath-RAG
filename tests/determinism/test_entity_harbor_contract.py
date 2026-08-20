"""ENTITY-HARBOR-V1 contract (PHASE 2 scaffolding, REVISION 3b).

Pins the vocabulary, the single eligibility authority, and the refusal to
ship a classifier that would have to guess.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_harbor import (
    HARBOR_CONTRACT, AnchorKind, DecisionStatus, HarborDecision,
    ReferenceBasis, Referentiality, StructuralEvidence, classify,
    graph_eligible,
)

EVAL = ROOT / "eval" / "admission"
CTX = json.loads((EVAL / "admission_context_fixtures_v1.json").read_text())["fixtures"]
GOLD = json.loads((EVAL / "admission_gold_v2.json").read_text())


def _d(kind, scope, basis=None, refty=Referentiality.SPECIFIC, surface="x",
       status=DecisionStatus.RESOLVED, **kw):
    return HarborDecision(surface, kind, refty, scope, decision_status=status,
                          reference_basis=basis, **kw)


def test_generic_group_was_renamed_generic():
    assert not hasattr(AnchorKind, "GENERIC_GROUP")
    assert AnchorKind.GENERIC.value == "GENERIC"
    # no ITEM or AXIS may carry the old label; prose describing the rename may
    assert "GENERIC_GROUP" not in json.dumps(GOLD["items"])
    assert "GENERIC_GROUP" not in json.dumps(GOLD["axes"])


def test_decision_state_is_separate_from_referent_type():
    """PHASE 2A: 'what kind of referent' and 'do I know yet' are different
    questions and must not share an enum."""
    assert not hasattr(AnchorKind, "CONTEXT_REQUIRED")
    assert not hasattr(ReferenceBasis, "CONTEXT_REQUIRED")
    assert AnchorKind.UNKNOWN.value == "UNKNOWN"
    assert DecisionStatus.CONTEXT_REQUIRED.value == "CONTEXT_REQUIRED"


def test_unknown_kind_cannot_be_resolved():
    with pytest.raises(ValueError, match="UNKNOWN"):
        _d(AnchorKind.UNKNOWN, "GLOBAL", status=DecisionStatus.RESOLVED)


def test_unsettled_decisions_are_never_graph_eligible():
    """Abstention is the safe direction for a precision gate."""
    assert not graph_eligible(_d(AnchorKind.UNKNOWN, "CORPUS_SCOPED",
                                 status=DecisionStatus.CONTEXT_REQUIRED))
    assert not graph_eligible(_d(AnchorKind.LOCAL_REFERENCE, "DOCUMENT_SCOPED",
                                 status=DecisionStatus.CONTEXT_REQUIRED))
    assert not graph_eligible(_d(AnchorKind.LOCAL_REFERENCE, "DOCUMENT_SCOPED",
                                 ReferenceBasis.AMBIGUOUS,
                                 status=DecisionStatus.ABSTAINED))


def test_eligibility_by_anchor_kind():
    assert graph_eligible(_d(AnchorKind.IDENTITY, "GLOBAL"))
    assert graph_eligible(_d(AnchorKind.CONCEPT, "CORPUS_SCOPED",
                             refty=Referentiality.GENERIC))
    assert not graph_eligible(_d(AnchorKind.GENERIC, "MENTION_ONLY",
                                 refty=Referentiality.GENERIC))
    # GENERIC is refused even if something granted it a wider scope
    assert not graph_eligible(_d(AnchorKind.GENERIC, "CORPUS_SCOPED",
                                 refty=Referentiality.GENERIC))


def test_local_reference_eligibility_depends_on_basis_not_scope():
    """REVISION 3: scope alone can no longer decide eligibility."""
    for basis, want in ((ReferenceBasis.DOCUMENT_CONSTITUTED, True),
                        (ReferenceBasis.ANTECEDENT_RESOLVED, True),
                        (ReferenceBasis.EXTERNAL_UNRESOLVED, False)):
        d = _d(AnchorKind.LOCAL_REFERENCE, "DOCUMENT_SCOPED", basis)
        assert graph_eligible(d) is want, basis


def test_reference_basis_rejected_on_non_local_reference():
    with pytest.raises(ValueError):
        _d(AnchorKind.IDENTITY, "GLOBAL", ReferenceBasis.DOCUMENT_CONSTITUTED)


def test_resolves_to_requires_antecedent_resolved():
    with pytest.raises(ValueError):
        _d(AnchorKind.LOCAL_REFERENCE, "DOCUMENT_SCOPED",
           ReferenceBasis.DOCUMENT_CONSTITUTED, resolves_to="something")


def test_classifier_refuses_to_ship_a_guess():
    """REVISION 3b withholds authorization; morphological inference is
    forbidden, so the interface must raise rather than guess."""
    with pytest.raises(NotImplementedError, match="not authorized"):
        classify("the ingestion system", core_type="Technology")


def test_structural_evidence_is_recorded_but_not_decisive():
    """named_anchor_present must not imply IDENTITY — ctx-08 vs ctx-09."""
    ev = StructuralEvidence(named_anchor_present=True, multiword=True)
    ident = HarborDecision("Polymath retrieval system", AnchorKind.IDENTITY,
                           Referentiality.SPECIFIC, "GLOBAL", structural=ev)
    family = HarborDecision("Qwen3 embedding model", AnchorKind.CONCEPT,
                            Referentiality.GENERIC, "CORPUS_SCOPED", structural=ev)
    assert ident.structural == family.structural      # identical evidence
    assert ident.anchor_kind is not family.anchor_kind  # different answers


def test_context_fixtures_cover_every_reference_basis():
    seen = {f.get("reference_basis") for f in CTX}
    for b in ("ANTECEDENT_RESOLVED", "DOCUMENT_CONSTITUTED", "EXTERNAL_UNRESOLVED"):
        assert b in seen, b


def test_context_fixtures_contain_same_surface_opposite_outcome_pairs():
    """Proves basis is discourse-determined, not surface-determined."""
    by_target = {}
    for f in CTX:
        by_target.setdefault(f["target"].lower(), []).append(f)
    pairs = [v for v in by_target.values() if len(v) > 1]
    assert pairs, "no adversarial same-surface pair present"
    for group in pairs:
        assert len({f["graph_eligible"] for f in group}) > 1, group[0]["target"]


def test_context_fixture_expectations_agree_with_the_eligibility_authority():
    for f in CTX:
        kind = AnchorKind(f["anchor_kind"])
        basis = ReferenceBasis(f["reference_basis"]) if f.get("reference_basis") else None
        scope = "MENTION_ONLY" if kind is AnchorKind.GENERIC else "DOCUMENT_SCOPED"
        d = HarborDecision(f["target"], kind,
                           Referentiality.UNRESOLVED if basis else Referentiality.SPECIFIC,
                           scope, reference_basis=basis,
                           resolves_to=f.get("resolves_to"))
        assert graph_eligible(d) is f["graph_eligible"], f["id"]


def test_contract_version_pinned():
    assert HARBOR_CONTRACT == "entity-harbor-v1"
