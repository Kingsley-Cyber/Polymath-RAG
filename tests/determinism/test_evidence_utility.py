"""EVIDENCE-UTILITY-V1 exit gate — every property that makes the
selector safe to trust, each pinned:

  frozen-path identity (flag off = the old cut, byte-identical)
  degeneration (flag on with no pressure = the old cut)
  parent saturation breadth vs genuine depth
  requirement-coverage promotion, bounded by the lookahead window
  redundancy veto
  relevance floor (tail junk can never leapfrog past the window)
  rescue seat floors under the utility cut
  latent competition: relevance bar, novel-parent survival, fail-open
  determinism
"""
from __future__ import annotations

from dataclasses import replace

from polymath_shared.evidence_utility import (
    derive_requirements,
    latent_competition,
    utility_cut,
)
from polymath_shared.hybrid import HYBRID_DEFAULT_PLAN, hybrid_retrieve
from polymath_shared.latent.rescue import (
    ARRIVAL_LATENT_RESCUE,
    latent_rescue_parents,
)
from polymath_shared.pass1 import ARRIVAL_GLOBAL_CHILD_RESCUE

RESCUES = (ARRIVAL_GLOBAL_CHILD_RESCUE, ARRIVAL_LATENT_RESCUE)


def _c(cid, parent, text, arrival=None, score=None):
    out = {"chunk_id": cid, "parent_id": parent, "doc_id": "d1",
           "text": text}
    if arrival:
        out["arrival"] = arrival
    if score is not None:
        out["rerank_score"] = score
    return out


# ---------------------------------------------------------------- unit

def test_no_pressure_degenerates_to_plain_cut():
    cands = [_c(f"c{i}", f"p{i}", f"unique topic {i} alpha beta gamma "
                f"delta{i}") for i in range(8)]
    out, diag = utility_cut(list(cands), 5, reserved=0,
                            rescue_arrivals=RESCUES)
    assert [c["chunk_id"] for c in out] == [f"c{i}" for i in range(5)]
    assert diag["promotions"] == 0


def test_parent_saturation_prefers_breadth():
    # five children of ONE parent lead; fresh parents wait behind
    cands = ([_c(f"same{i}", "p_hog", f"hog text variant {i} energy "
                 f"storage cell{i}") for i in range(5)]
             + [_c("fresh1", "p_a", "replication copies regions quorum"),
                _c("fresh2", "p_b", "encryption keys rotation policy")])
    out, diag = utility_cut(list(cands), 4, reserved=0,
                            rescue_arrivals=RESCUES,
                            parent_saturation=2)
    picked = [c["chunk_id"] for c in out]
    hog = sum(1 for c in out if c["parent_id"] == "p_hog")
    assert hog == 2 and "fresh1" in picked and "fresh2" in picked
    assert diag["promotions"] >= 2


def test_parent_saturation_allows_genuine_depth():
    # ONLY one parent exists — depth must not be blocked by the cap
    cands = [_c(f"c{i}", "p_only", f"deep dive part {i} mechanism "
                f"detail{i}") for i in range(6)]
    out, _ = utility_cut(list(cands), 4, reserved=0,
                         rescue_arrivals=RESCUES, parent_saturation=2)
    assert len(out) == 4                      # cap defers, never starves


def test_requirement_coverage_promotes_within_window():
    reqs = derive_requirements(
        "what is the replication architecture and how does key "
        "rotation work and when should archives expire")
    assert len(reqs) == 3
    cands = [_c("r1", "p1", "replication architecture copies regions"),
             _c("r2", "p2", "replication design zones copies failover"),
             _c("r3", "p3", "replication quorum writes reads"),
             _c("k1", "p4", "key rotation schedule cryptographic"),
             _c("a1", "p5", "archives expire lifecycle retention")]
    out, diag = utility_cut(list(cands), 3, reserved=0,
                            rescue_arrivals=RESCUES, requirements=reqs)
    picked = [c["chunk_id"] for c in out]
    assert "k1" in picked and "a1" in picked      # coverage beat rank
    assert diag["covered"] == 3


def test_relevance_floor_tail_junk_never_leapfrogs():
    cands = [_c(f"c{i}", f"p{i}", f"relevant material {i} topic{i} "
                f"detail{i}") for i in range(30)]
    cands.append(_c("junk", "p_junk", "totally different novel words "
                    "unicorn rainbow"))
    out, _ = utility_cut(list(cands), 6, reserved=0,
                         rescue_arrivals=RESCUES,
                         requirements=[{"unicorn", "rainbow"},
                                       {"relevant", "material"}],
                         lookahead=12)
    assert "junk" not in {c["chunk_id"] for c in out}


def test_redundancy_veto_defers_near_duplicates():
    dup = "bert uses masked language modeling pretraining objective"
    cands = [_c("c1", "p1", dup),
             _c("c2", "p2", dup + " indeed"),
             _c("c3", "p3", "wordpiece tokenizer vocabulary subword")]
    out, diag = utility_cut(list(cands), 2, reserved=0,
                            rescue_arrivals=RESCUES,
                            redundancy_veto=0.6)
    assert [c["chunk_id"] for c in out] == ["c1", "c3"]
    assert diag["redundancy_deferrals"] >= 1


def test_rescue_seat_floors_survive_utility_cut():
    cands = [_c(f"c{i}", f"p{i}", f"body text {i} filler{i} words{i}")
             for i in range(10)]
    cands.append(_c("resc", "p_r", "rescued recall item",
                    arrival=ARRIVAL_GLOBAL_CHILD_RESCUE))
    cands.append(_c("lat", "p_l", "latent discovery item",
                    arrival=ARRIVAL_LATENT_RESCUE))
    out, _ = utility_cut(list(cands), 6, reserved=2,
                         rescue_arrivals=RESCUES)
    ids = {c["chunk_id"] for c in out}
    assert "resc" in ids and "lat" in ids and len(out) == 6


def test_latent_competition_drops_only_beaten_and_redundant():
    cands = [_c("b1", "p1", "x", score=0.9),
             _c("b2", "p2", "x", score=0.7),
             _c("lat_clears", "p9", "x", ARRIVAL_LATENT_RESCUE, 0.69),
             _c("lat_novel", "p_new", "x", ARRIVAL_LATENT_RESCUE, 0.2),
             _c("lat_beaten", "p1", "x", ARRIVAL_LATENT_RESCUE, 0.3)]
    out, diag = latent_competition(list(cands),
                                   latent_arrival=ARRIVAL_LATENT_RESCUE,
                                   margin=0.05)
    ids = {c["chunk_id"] for c in out}
    assert "lat_clears" in ids            # within margin of weakest (0.7)
    assert "lat_novel" in ids             # novel parent coverage
    assert "lat_beaten" not in ids        # loses on BOTH counts
    assert diag["latent_dropped"] == 1


def test_latent_competition_fails_open_without_scores():
    cands = [_c("b1", "p1", "x"),
             _c("lat", "p1", "x", ARRIVAL_LATENT_RESCUE)]
    out, diag = latent_competition(list(cands),
                                   latent_arrival=ARRIVAL_LATENT_RESCUE)
    assert {c["chunk_id"] for c in out} == {"b1", "lat"}
    assert diag["latent_dropped"] == 0


def test_single_clause_query_yields_no_requirements():
    assert derive_requirements("what is s3 lifecycle management") == []


def test_deterministic():
    cands = [_c(f"c{i}", f"p{i % 3}", f"text {i} about topic {i % 4} "
                f"alpha{i}") for i in range(20)]
    a = utility_cut(list(cands), 8, reserved=0, rescue_arrivals=RESCUES,
                    requirements=[{"topic", "alpha3"}])
    b = utility_cut(list(cands), 8, reserved=0, rescue_arrivals=RESCUES,
                    requirements=[{"topic", "alpha3"}])
    assert a == b


# -------------------------------------------------------------- engine

def _engine_run(plan, with_latent=True):
    """Fake-search engine harness (test_hybrid_latent pattern)."""
    latent_rows = {"latent_abstraction": [{"score": 0.95, "payload": {
        "parent_id": "p_latent", "doc_id": "d1", "source_name": "one.md"}}]}
    children = {
        "p_latent": [{"score": 0.5, "payload": {
            "chunk_id": "c_lat", "doc_id": "d1", "parent_id": "p_latent",
            "corpus_id": "t", "text": "latent child body",
            "source_name": "one.md"}}],
        "p_s1": [{"score": 0.7, "payload": {
            "chunk_id": f"c_s1_{i}", "doc_id": "d1", "parent_id": "p_s1",
            "corpus_id": "t", "text": f"section child {i} words{i}",
            "source_name": "one.md"}} for i in range(3)],
    }

    def search(_collection, _qvec, filters):
        kind = filters.get("representation_kind")
        if kind in ("latent_abstraction", "latent_transfer"):
            return latent_rows.get(kind, [])
        if kind == "routing_child" and filters.get("parent_id"):
            return children.get(filters["parent_id"], [])
        if kind == "routing_document_summary":
            return [{"score": 0.9, "payload": {
                "summary_id": "sum_d1", "doc_id": "d1", "corpus_id": "t",
                "text": "doc one summary", "source_name": "one.md"}}]
        if kind == "routing_section_summary":
            return [{"score": 0.8, "payload": {
                "summary_id": "sum_s1", "doc_id": "d1", "parent_id": "p_s1",
                "corpus_id": "t", "text": "section one",
                "source_name": "one.md"}}]
        return []

    def latent_rescue(qvec, skip):
        return latent_rescue_parents(
            qvec, corpus_id="t", plan=plan, routing_search=search,
            skip_parent_ids=skip)

    return hybrid_retrieve(
        "test query", plan=replace(plan, corpus_ids=("t",)),
        embed_query=lambda q: [0.1] * 4,
        routing_search=search, lexical_search=lambda q, k: [],
        rerank_children=None,
        latent_rescue=latent_rescue if with_latent else None)


def test_engine_flag_off_is_byte_identical():
    base = replace(HYBRID_DEFAULT_PLAN, latent_enabled=True,
                   rerank_enabled=False)
    a = _engine_run(base)
    b = _engine_run(replace(base, evidence_utility_enabled=False))
    assert a.final_evidence == b.final_evidence
    assert b.trace["evidence_utility"] == {"enabled": False}


def test_engine_flag_on_emits_diagnostics_and_keeps_latent_failopen():
    plan = replace(HYBRID_DEFAULT_PLAN, latent_enabled=True,
                   rerank_enabled=False, evidence_utility_enabled=True)
    r = _engine_run(plan)
    eu = r.trace["evidence_utility"]
    assert eu["enabled"] is True
    # rerank disabled => latent competition fails open, nothing dropped
    assert eu.get("latent_dropped", 0) == 0
    assert any(c.get("arrival") == ARRIVAL_LATENT_RESCUE
               for c in r.final_evidence)
