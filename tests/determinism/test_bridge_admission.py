"""WLK2C C1 — STRUCTURAL bridge admissibility. Pins that C1 is structure-only: it accepts a well-formed,
grounded, distinct-from-q0 bridge candidate and rejects garbage (primary path / empty / duplicate-q0 /
no-distinct-content / boilerplate / ungrounded) — and makes NO relevance judgment. The load-bearing
test is `test_misdirected_bridge_passes_structural_gate`: a grounded-but-off-topic bridge is
structurally admissible here; only C4 (semantic) may reject it.
"""
from __future__ import annotations

from polymath_shared.bridge_admission import (
    admissible_bridge_paths,
    annotate_admissibility,
    structural_bridge_admissibility,
)
from polymath_shared.retrieval_lineage import DiscoveryPath, Lineage

Q0 = "make the fake smile readable to the audience"


def _p(text, *, origin="PROFILE", qid="b1", primary=False, inspired=None):
    return DiscoveryPath(origin_query=text, origin=origin,
                         query_id=(None if primary else qid), bridge_id=(None if primary else qid),
                         inspired_by_profile=inspired or [])


def _verdict(path):
    return structural_bridge_admissibility(path, Q0)


def test_primary_q0_path_is_not_a_bridge():
    v = _verdict(_p(Q0, primary=True))
    assert not v.admissible and "not_a_bridge_path" in v.reasons


def test_good_existing_subquery_is_admissible():
    v = _verdict(_p("facial mechanics distinguishing genuine and performed smiling", origin="USER"))
    assert v.admissible and v.reasons == []


def test_q0_paraphrase_is_rejected_as_duplicate():
    v = _verdict(_p("make the fake smile readable for the audience"))   # ~ q0 reworded
    assert not v.admissible and "duplicate_of_q0" in v.reasons


def test_no_distinct_content_rejected():
    v = _verdict(_p("readable smile"))                                  # strict subset of q0 content
    assert not v.admissible and "no_distinct_content" in v.reasons


def test_misdirected_bridge_passes_structural_gate():
    # THE contract: grounded + well-formed + distinct-from-q0 but OFF-TOPIC -> structurally admissible.
    # C1 makes NO relevance judgment; C4 (semantic bridge<->q0) is what rejects this.
    v = _verdict(_p("Augmenting prompts for better text-to-video generation", inspired=["docX"]))
    assert v.admissible and v.reasons == []


def test_empty_and_boilerplate_rejected():
    assert "empty_origin_query" in _verdict(_p("   ")).reasons
    short = _verdict(_p("the methods"))       # <2 content tokens after stopword/short-token drop
    assert not short.admissible and "boilerplate_or_too_short" in short.reasons


def test_ungrounded_path_rejected():
    # malformed: a non-primary path with no query id is ungrounded
    bad = DiscoveryPath(origin_query="distinct grounded phrase here", origin="PROFILE",
                        query_id=None, bridge_id="b9")
    assert "ungrounded_origin" in structural_bridge_admissibility(bad, Q0).reasons


def test_admissibility_is_independent_of_relevance():
    # an off-topic-but-distinct bridge is admissible; an on-topic paraphrase is NOT -> the gate keys on
    # STRUCTURE (distinct/well-formed), never on relevance to q0.
    offtopic = _verdict(_p("compositing atmospheric depth for giant creature scale"))
    paraphrase = _verdict(_p("make the audience find the fake smile readable"))   # ≥0.8 overlap w/ q0
    assert offtopic.admissible and not paraphrase.admissible
    assert "duplicate_of_q0" in paraphrase.reasons


def test_admissible_bridge_paths_filters_lineage():
    lin = Lineage(root_query=Q0, paths=[
        _p(Q0, primary=True),                                          # DIRECT (not a bridge)
        _p("expression coding action units around the eyes", origin="PROFILE", qid="p1"),  # admissible
        _p("make the fake smile readable audience", qid="p2"),        # duplicate -> rejected
        _p("x", qid="p3")], discovered_by=["DENSE"])                  # boilerplate -> rejected
    kept = admissible_bridge_paths(lin)
    assert [p.bridge_id for p in kept] == ["p1"]


def test_annotate_admissibility_receipt_shape():
    lin = Lineage(root_query=Q0, paths=[
        _p(Q0, primary=True),
        _p("kinesphere and effort qualities of movement", origin="GRAPH", qid="g1")],
        discovered_by=["GRAPH"])
    rpt = annotate_admissibility(lin)
    assert rpt["is_direct"] is True and len(rpt["bridge_candidates"]) == 1
    assert rpt["bridge_candidates"][0]["structural"]["admissible"] is True
    assert rpt["bridge_candidates"][0]["bridge_id"] == "g1"


def test_deterministic():
    p = _p("effort weight time space movement qualities")
    assert structural_bridge_admissibility(p, Q0).to_dict() == structural_bridge_admissibility(p, Q0).to_dict()
