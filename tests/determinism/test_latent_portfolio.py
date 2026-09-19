"""WLK2C C5 — bounded evidence-role portfolio. Pins the librarian pair of rules:
  (A) COMPLEMENTARY/DIVERGENT never displaces REQUIRED DIRECT;
  (B) redundant/nonessential DIRECT must not consume a slot a DISTINCT COMPLEMENTARY could occupy.
Plus: DIRECT doesn't monopolize (per-rep cap), DIVERGENT only atop adequate DIRECT and ≤2, and the
seating order = required DIRECT → distinct COMPLEMENTARY → DIVERGENT → fill.
"""
from __future__ import annotations

from polymath_shared.latent_eligibility import (
    COMPLEMENTARY_ELIGIBLE,
    DIRECT_ELIGIBLE,
    DIVERGENT_ELIGIBLE,
    INELIGIBLE,
)
from polymath_shared.latent_portfolio import seat_portfolio


def _c(cid, rep, role):
    return {"chunk_id": cid, "parent_id": rep, "role": role}


def _ids(seated, role=None):
    return [s["chunk_id"] for s in seated if role is None or s["seat_role"] == role]


def test_INVARIANT_B_redundant_direct_yields_to_distinct_complementary():
    # capacity 2; two DIRECT from the SAME representation (one required, one redundant) + one DISTINCT
    # COMPLEMENTARY. The complementary must take the slot the redundant DIRECT would have.
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("D2", "p1", DIRECT_ELIGIBLE),
             _c("C1", "p9", COMPLEMENTARY_ELIGIBLE)]
    seated, tr = seat_portfolio(cands, capacity=2, direct_per_rep_cap=1)
    assert set(_ids(seated)) == {"D1", "C1"}                  # D2 (redundant DIRECT) yielded
    assert tr["redundant_direct_yielded"] == 1 and tr["complementary"] == 1


def test_INVARIANT_A_complementary_never_displaces_required_direct():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("C1", "p9", COMPLEMENTARY_ELIGIBLE)]
    seated, _ = seat_portfolio(cands, capacity=1, direct_per_rep_cap=3)
    assert _ids(seated) == ["D1"]                             # required DIRECT kept; complementary excluded


def test_direct_does_not_monopolize_via_per_rep_cap():
    # 10 DIRECT chunks all from ONE representation + a distinct COMPLEMENTARY, capacity 5.
    cands = [_c(f"D{i}", "p1", DIRECT_ELIGIBLE) for i in range(10)] + [_c("C1", "p9", COMPLEMENTARY_ELIGIBLE)]
    seated, tr = seat_portfolio(cands, capacity=5, direct_per_rep_cap=3)
    assert "C1" in _ids(seated)                               # the one doc did NOT eat all 5 seats
    assert tr["complementary"] == 1 and tr["direct"] == 3     # 3 required (cap) + fill; complementary seated


def test_divergent_requires_direct_grounding():
    only_div = [_c("V1", "pv", DIVERGENT_ELIGIBLE)]
    seated, tr = seat_portfolio(only_div, capacity=4, min_adequate_direct=1)
    assert seated == [] and tr["divergent_allowed"] is False  # no DIRECT grounding ⇒ 0 divergent
    with_direct = [_c("D1", "p1", DIRECT_ELIGIBLE)] + only_div
    seated2, tr2 = seat_portfolio(with_direct, capacity=4)
    assert tr2["divergent_allowed"] and "V1" in _ids(seated2, "DIVERGENT")


def test_DIVERGENT_never_compensates_for_absent_direct_grounding():
    # the owner invariant: even with a C4-DIRECT-looking candidate present, if CA4 says there is no true
    # DIRECT grounding (PARTIAL-only, has_direct_grounding=False), DIVERGENT capacity is 0.
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("V1", "pv", DIVERGENT_ELIGIBLE)]
    seated, tr = seat_portfolio(cands, capacity=5, establishes_need=True, has_direct_grounding=False)
    assert tr["divergent_allowed"] is False and "V1" not in _ids(seated, "DIVERGENT")


def test_complementary_blocked_without_establishes_need():
    # an ungrounded answer (establishes_need False) gets NO complementary latent evidence.
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("C1", "p9", COMPLEMENTARY_ELIGIBLE)]
    _, tr = seat_portfolio(cands, capacity=5, establishes_need=False)
    assert tr["complementary"] == 0                            # C1 may be RELATED fill, never COMPLEMENTARY


def test_partial_only_allows_complementary_but_not_divergent():
    cands = [_c("C1", "p9", COMPLEMENTARY_ELIGIBLE), _c("V1", "pv", DIVERGENT_ELIGIBLE)]
    _, tr = seat_portfolio(cands, capacity=5, establishes_need=True, has_direct_grounding=False)
    assert tr["complementary"] == 1 and tr["divergent"] == 0   # PARTIAL grounding: complementary yes, divergent no


def test_divergent_capped_at_two():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE)] + [_c(f"V{i}", f"pv{i}", DIVERGENT_ELIGIBLE) for i in range(4)]
    seated, tr = seat_portfolio(cands, capacity=10, max_divergent=2)
    assert tr["divergent"] == 2


def test_distinct_complementary_only_redundant_goes_to_fill():
    # a COMPLEMENTARY whose representation a DIRECT already seated is NOT distinct -> not a priority seat.
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("C_same", "p1", COMPLEMENTARY_ELIGIBLE),
             _c("C_new", "p9", COMPLEMENTARY_ELIGIBLE)]
    seated, tr = seat_portfolio(cands, capacity=2, direct_per_rep_cap=1)
    assert set(_ids(seated)) == {"D1", "C_new"}               # the distinct complementary wins the slot
    assert tr["complementary"] == 1


def test_ordinary_fill_and_capacity_zero():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("R1", "p2", INELIGIBLE)]
    seated, _ = seat_portfolio(cands, capacity=5)
    assert _ids(seated) == ["D1", "R1"] and seated[1]["seat_role"] == "RELATED"
    assert seat_portfolio(cands, capacity=0)[0] == []


def test_complementary_cap_bounds():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE)] + [_c(f"C{i}", f"pc{i}", COMPLEMENTARY_ELIGIBLE) for i in range(5)]
    _, tr = seat_portfolio(cands, capacity=10, complementary_cap=2)
    assert tr["complementary"] == 2


def test_seating_order_direct_then_complementary_then_divergent():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("C1", "p2", COMPLEMENTARY_ELIGIBLE),
             _c("V1", "p3", DIVERGENT_ELIGIBLE)]
    seated, _ = seat_portfolio(cands, capacity=3)
    assert [s["seat_role"] for s in seated] == ["DIRECT", "COMPLEMENTARY", "DIVERGENT"]


def test_deterministic():
    cands = [_c("D1", "p1", DIRECT_ELIGIBLE), _c("C1", "p9", COMPLEMENTARY_ELIGIBLE),
             _c("D2", "p1", DIRECT_ELIGIBLE)]
    assert seat_portfolio(cands, capacity=3, direct_per_rep_cap=1) == seat_portfolio(cands, capacity=3, direct_per_rep_cap=1)
