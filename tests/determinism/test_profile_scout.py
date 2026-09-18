"""P5a Profile Scout — pure fusion contract (PROFILE-SCOUT-V1).

Proves the owner's acceptance list: deterministic RRF ordering; a doc in both projections gets
both contributions; repeated atoms for one doc do NOT create multiple RRF votes in that
projection; full provenance retained; empty-in ⇒ empty-out; one projection may be empty;
top_k honored; deterministic doc_id tie-break; raw scores are provenance-only (not
cross-projection calibrated); no planner/mode/answer/gate fields in the result. Pure function
— no stores, no I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from pytest import approx  # noqa: E402
from polymath_shared.document_profile.profile_scout import (  # noqa: E402
    ScoutHit, ProfileNomination, ProfileScoutResult, fuse_profile_scout_hits,
    profile_hits_from_doc_ids, atom_hits_from_search,
)


def P(doc_id, rank):  # a thin DOCUMENT_PROFILE hit (profile_nominate exposes only doc_id + rank)
    return ScoutHit(doc_id=doc_id, source="profile", rank=rank)


def A(doc_id, rank, kind, text="t", score=0.5, group="discovery"):  # a rich PROFILE_ATOM hit
    return ScoutHit(doc_id=doc_id, source="atom", rank=rank, surface=kind,
                    surface_type=group, text=text, score=score)


def test_deterministic_rrf_ordering():
    r = fuse_profile_scout_hits([P("doc_b", 1), P("doc_c", 2)], [A("doc_a", 1, "BRIDGE")])
    # doc_a & doc_b each rank-1 (1/61) → tie → doc_id asc; doc_c rank-2 (1/62) last.
    assert [n.doc_id for n in r.nominations] == ["doc_a", "doc_b", "doc_c"]


def test_doc_in_both_projections_gets_both_contributions():
    nom = fuse_profile_scout_hits([P("doc_a", 1)], [A("doc_a", 1, "BRIDGE")]).nominations[0]
    assert {c.source for c in nom.contributions} == {"profile", "atom"}
    assert nom.fused_score == approx(1 / 61 + 1 / 61)


def test_repeated_atoms_for_one_doc_are_a_single_projection_vote():
    nom = fuse_profile_scout_hits(
        [], [A("doc_a", 1, "BRIDGE"), A("doc_a", 2, "THEORY"), A("doc_a", 3, "CONCEPT")]
    ).nominations[0]
    atom_contribs = [c for c in nom.contributions if c.source == "atom"]
    assert len(atom_contribs) == 1               # one vote, not three
    assert atom_contribs[0].best_rank == 1       # collapsed to the best rank
    assert nom.fused_score == approx(1 / 61)     # row count buys no weight
    assert len(nom.provenance) == 3              # ...but every hit is retained


def test_full_provenance_and_matched_surfaces_retained():
    nom = fuse_profile_scout_hits(
        [P("doc_a", 1)], [A("doc_a", 2, "BRIDGE"), A("doc_a", 5, "THEORY")]
    ).nominations[0]
    assert len(nom.provenance) == 3
    assert {h.source for h in nom.provenance} == {"profile", "atom"}
    assert nom.matched_surfaces == ("BRIDGE", "THEORY")   # profile hit contributes no surface


def test_empty_inputs_yield_empty_result():
    assert fuse_profile_scout_hits([], []) == ProfileScoutResult(nominations=())


def test_one_projection_may_be_empty():
    only_profile = fuse_profile_scout_hits([P("doc_a", 1)], [])
    only_atom = fuse_profile_scout_hits([], [A("doc_a", 1, "BRIDGE")])
    assert only_profile.nominations[0].doc_id == "doc_a"
    assert [c.source for c in only_profile.nominations[0].contributions] == ["profile"]
    assert [c.source for c in only_atom.nominations[0].contributions] == ["atom"]


def test_top_k_is_honored():
    profile = [P(f"doc_{i:02d}", i + 1) for i in range(20)]
    r = fuse_profile_scout_hits(profile, [], max_documents=8)
    assert len(r.nominations) == 8
    assert [n.rank for n in r.nominations] == list(range(1, 9))


def test_deterministic_doc_id_tiebreak_and_repeatable():
    args = ([P("doc_z", 2)], [A("doc_a", 2, "BRIDGE")])   # both rank-2 → equal fused → doc_id asc
    r = fuse_profile_scout_hits(*args)
    assert [n.doc_id for n in r.nominations] == ["doc_a", "doc_z"]
    assert r == fuse_profile_scout_hits(*args)             # identical rerun


def test_raw_scores_are_provenance_only_not_cross_projection_calibrated():
    # A rank-1 profile hit (no score) beats a rank-5 atom hit with a huge raw score — RRF is rank-based.
    r = fuse_profile_scout_hits([P("doc_p", 1)], [A("doc_a", 5, "BRIDGE", score=0.99)])
    assert [n.doc_id for n in r.nominations] == ["doc_p", "doc_a"]
    atom_nom = r.nominations[1]
    assert atom_nom.provenance[0].score == 0.99            # raw score survives only as provenance
    assert atom_nom.fused_score == approx(1 / 65)          # fused is rank-derived, unrelated to 0.99


def test_representative_is_best_text_hit_and_none_for_profile_only():
    r = fuse_profile_scout_hits([P("doc_p", 1)], [A("doc_a", 1, "BRIDGE", text="bridge-text")])
    by_id = {n.doc_id: n for n in r.nominations}
    assert by_id["doc_a"].representative_surface == "BRIDGE"
    assert by_id["doc_a"].representative_text == "bridge-text"
    assert by_id["doc_p"].representative_surface is None    # profile-only doc has nothing verbatim
    assert by_id["doc_p"].representative_text is None


def test_result_carries_no_planner_answer_or_gate_fields():
    forbidden = {"recommended_mode", "required_subquery", "must_use_graph",
                 "intent_override", "answer_strategy", "answer", "mode", "gate"}
    assert set(ProfileNomination.__dataclass_fields__) & forbidden == set()
    assert set(ProfileScoutResult.__dataclass_fields__) == {"nominations"}


# --- P5b normalization (pure) ---

def test_profile_hits_from_doc_ids_are_thin_and_ranked_by_position():
    hits = profile_hits_from_doc_ids(["doc_a", "doc_b", "", None])
    assert [(h.doc_id, h.source, h.rank) for h in hits] == [("doc_a", "profile", 1), ("doc_b", "profile", 2)]
    assert all(h.surface is None and h.surface_type is None and h.text is None and h.score is None for h in hits)


def test_atom_hits_from_search_are_rich_with_injected_group():
    rows = [{"doc_id": "doc_a", "atom_kind": "BRIDGE", "text": "t", "score": 0.7}, {"doc_id": None}]
    hits = atom_hits_from_search(rows, group_of=lambda k: {"BRIDGE": "discovery"}.get(k))
    assert len(hits) == 1  # the doc_id-less row is dropped
    h = hits[0]
    assert (h.doc_id, h.source, h.rank, h.surface, h.surface_type, h.text, h.score) == \
        ("doc_a", "atom", 1, "BRIDGE", "discovery", "t", 0.7)


def test_normalized_hits_fuse_end_to_end():
    p = profile_hits_from_doc_ids(["doc_a"])
    a = atom_hits_from_search([{"doc_id": "doc_a", "atom_kind": "THEORY", "text": "x", "score": 0.5}],
                              group_of=lambda k: "semantic")
    nom = fuse_profile_scout_hits(p, a).nominations[0]
    assert nom.doc_id == "doc_a"
    assert {c.source for c in nom.contributions} == {"profile", "atom"}
    assert nom.representative_text == "x"  # the only text-bearing hit
