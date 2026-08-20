"""CONTRACTION-RESOLUTION-V1 (PHASE 3).

The demonstrated defect: a document introduces a full name, later uses a
contracted form, and the two become separate graph nodes. Both forms are
already ADMITTED in the same document, so resolution reuses an existing
identity and invents nothing.

This must not become fuzzy dedup. `Crestline` vs `Crestview Automation`
has high string similarity and must ABSTAIN; token containment refuses it
where character similarity would not.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.contraction_resolution import (
    CONTRACTION_CONTRACT, MergeDecision, resolve_contraction,
)

DOC3 = [("Crestline Automation", "Organization"), ("Crestline", "Organization"),
        ("robotics vendor", "Organization"), ("analytics team", "Organization"),
        ("Cobalt assembly cell", "Technology"), ("Cobalt cell", "Technology"),
        ("Siemens PLCs", "Technology"), ("vision system", "Technology")]
DOC4 = [("Mentor assessment engine", "Technology"), ("Mentor engine", "Technology"),
        ("QBank item database", "Technology"), ("Coachlight review app", "Technology"),
        ("Coachlight app", "Technology"), ("Brightpath Learning", "Organization")]


def test_anchor_prefix_contraction_resolves():
    r = resolve_contraction("Crestline", "Organization", DOC3)
    assert r.decision is MergeDecision.SAME_ENTITY
    assert r.resolved_to == "Crestline Automation"
    assert r.shape == "anchor-prefix"


def test_head_preserving_elision_resolves():
    for short, ctype, cands, want in (
            ("Mentor engine", "Technology", DOC4, "Mentor assessment engine"),
            ("Cobalt cell", "Technology", DOC3, "Cobalt assembly cell"),
            ("Coachlight app", "Technology", DOC4, "Coachlight review app")):
        r = resolve_contraction(short, ctype, cands)
        assert r.decision is MergeDecision.SAME_ENTITY, short
        assert r.resolved_to == want
        assert r.shape == "head-preserving elision"


def test_string_similarity_is_not_containment():
    """The defining negative: `Crestline` / `Crestview Automation` are very
    similar as strings and share no token."""
    r = resolve_contraction("Crestline", "Organization",
                            [("Crestview Automation", "Organization")])
    assert r.decision is MergeDecision.ABSTAIN
    assert r.resolved_to is None


def test_ambiguity_abstains():
    r = resolve_contraction("Crestline", "Organization",
                            [("Crestline Automation", "Organization"),
                             ("Crestline Automation Team", "Organization")])
    assert r.decision is MergeDecision.ABSTAIN
    assert len(r.candidates) == 2


def test_incompatible_type_abstains():
    assert resolve_contraction("Crestline", "Technology", DOC3).decision \
        is MergeDecision.ABSTAIN


def test_bare_head_does_not_contract():
    """`engine` alone must not absorb `Mentor assessment engine` — a shared
    head is not a contraction."""
    assert resolve_contraction("engine", "Technology", DOC4).decision \
        is MergeDecision.ABSTAIN


def test_never_synthesises_text():
    """Every resolution target must be one of the supplied candidates."""
    for short, ctype, cands in (("Crestline", "Organization", DOC3),
                                ("Mentor engine", "Technology", DOC4)):
        r = resolve_contraction(short, ctype, cands)
        assert r.resolved_to in {s for s, _ in cands}


def test_original_mention_is_preserved_and_evidence_recorded():
    r = resolve_contraction("Crestline", "Organization", DOC3)
    assert r.short_surface == "Crestline"      # untouched
    assert r.evidence and "exact token identity" in r.evidence[0]
    assert r.contract == CONTRACTION_CONTRACT


def test_deterministic():
    seen = {repr(resolve_contraction("Mentor engine", "Technology", DOC4))
            for _ in range(20)}
    assert len(seen) == 1


def test_no_candidates_abstains():
    assert resolve_contraction("Crestline", "Organization", []).decision \
        is MergeDecision.ABSTAIN


# --- PHASE 3 SETTLEMENT: policy B -----------------------------------------

def test_membership_merges_identity_without_rewriting_surfaces():
    from polymath_shared.contraction_resolution import build_memberships
    m = build_memberships(DOC3)
    # both forms survive as their own immutable surfaces...
    assert set(m) >= {"Crestline", "Crestline Automation"}
    for surface, rec in m.items():
        assert rec.surface == surface, "mention surface must be immutable provenance"
    # ...and share one canonical id
    assert m["Crestline"].canonical_id == m["Crestline Automation"].canonical_id
    assert m["Crestline"].is_anchor is False
    assert m["Crestline Automation"].is_anchor is True


def test_every_membership_records_its_basis():
    from polymath_shared.contraction_resolution import build_memberships
    for rec in build_memberships(DOC4).values():
        assert rec.basis and rec.contract == CONTRACTION_CONTRACT


def test_unresolvable_surfaces_are_their_own_anchor_not_dropped():
    from polymath_shared.contraction_resolution import build_memberships
    m = build_memberships(DOC3)
    assert m["robotics vendor"].is_anchor
    assert m["robotics vendor"].canonical_id == "ent_robotics_vendor"
    assert len(m) == len(DOC3), "no admitted surface may be dropped"


def test_label_selection_is_not_part_of_identity_resolution():
    """The frozen gold canonicalizes `CareChart EMR` (short) but
    `FreightNet routing platform` (long) for identical grammatical shapes,
    so no deterministic in-document signal picks a label. Resolution must
    therefore assign identity WITHOUT claiming a preferred surface."""
    from polymath_shared.contraction_resolution import build_memberships
    care = [("CareChart EMR", "Technology"), ("CareChart EMR platform", "Technology")]
    m = build_memberships(care)
    assert m["CareChart EMR"].canonical_id == m["CareChart EMR platform"].canonical_id
    # both surfaces remain available; neither is rewritten into the other
    assert {r.surface for r in m.values()} == {s for s, _ in care}
