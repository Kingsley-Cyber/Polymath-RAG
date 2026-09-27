"""FACET-RETRIEVAL-V1 F2 — diversity by construction in the one composer every mode uses (register 11.545; plan §3.2, §4 F2).

The measured failure (receipt q_e09925df009649c6be872299): of 15 seats one book took 8 (53 %), four other documents were
retrieved and cut, the aspect seats seated nothing. Proof here, on fixed candidate pools:
  * flags off → `compose_evidence` is byte-identical to HEAD (its outputs on five pools were pinned BEFORE the change);
  * a document holding the top 10 chunks takes ≤ 40 % of the 24 seats when three documents qualify;
  * at most 3 seats per document per lane, lifted only when seats would otherwise stay empty (receipted);
  * two seats per facet whose best candidate clears the floor; a weak facet is named and seated nowhere;
  * MMR seats a second document over a near-duplicate chunk and the receipt says what it changed;
  * `default_budget` applies the profile on every surface (chat, /retrieve, evidence route, deep research) and the flag
    restores the pre-F2 budget; the env knobs still override single values.
"""
from __future__ import annotations

import inspect
import json
import pathlib

from orchestrator.api import chat_retrieval as cr
from polymath_shared import candidate_engine as ce

PINS = json.loads((pathlib.Path(__file__).with_name("facet_diversity_head_pins.json")).read_text())


def cand(cid, doc, score, arrivals=(ce.LANE_B,), qids=("q0",), text=None):
    return ce.CandidateEvidence(chunk_id=cid, doc_id=doc, parent_id=f"{doc}-p", source_name=doc, text=text or cid,
                                arrivals=list(arrivals), query_ids=list(qids), rerank_score=score)


def pools() -> dict[str, list]:
    """The five pools whose HEAD outputs are pinned in facet_diversity_head_pins.json — built exactly as the pin script did."""
    p = {}
    a = [cand(f"d1-{i}", "d1", 6.0 - i * 0.01, text=f"lighting the face with soft key fill {i}") for i in range(10)]
    a += [cand(f"d2-{i}", "d2", 5.95 - i * 0.01, text=f"camera motion control dialect {i}") for i in range(4)]
    a += [cand(f"d3-{i}", "d3", 5.9 - i * 0.01, text=f"emotional arc of an advert story {i}") for i in range(4)]
    a += [cand("d4-sp", "d4", 1.0, arrivals=(ce.LANE_C,), text="exact term match"), cand("d5-q2", "d5", 0.9, qids=("q2",), text="aspect two only")]
    p["A"] = a
    b = [cand(f"x{i}", f"doc{i % 3}", 3.0 - i * 0.2, arrivals=(ce.LANE_A, ce.LANE_B) if i % 2 else (ce.LANE_B,),
              qids=("q0", "q1") if i % 3 == 0 else ("q0",), text=f"token{i} shared words here") for i in range(14)]
    b += [cand("rej1", "doc9", -2.0, text="rejected one"), cand("rej2", "doc9", -3.0, arrivals=(ce.LANE_C,), text="rejected two")]
    p["B"] = b
    p["C"] = [cand(f"c{i}", f"d{i % 4}", None, text=f"c text {i}") for i in range(12)]
    d = [cand(f"n{i}", "n1", 4.0 - i * 0.001, text="the exact same passage repeated word for word") for i in range(9)]
    d += [cand("m0", "m2", 3.5, text="a different passage about montage rhythm and cut"), cand("m1", "m2", 3.4, text="another montage passage")]
    p["D"] = d
    p["E"] = [cand("a", "d1", 3.0), cand("rej", "d2", -2.0), cand("rej-sp", "d3", -1.5, arrivals=(ce.LANE_C,))]
    return p


def _profile(**over) -> ce.CandidateBudget:
    return ce.CandidateBudget(**{**ce.FACET_DIVERSITY_PROFILE, **over})


def _lane_counts(final) -> dict:
    out: dict = {}
    for c in final:
        k = (c.doc_id, c.arrivals[0] if c.arrivals else "")
        out[k] = out.get(k, 0) + 1
    return out


def test_flags_off_composes_byte_identically_to_head():
    """The three F2 fields default OFF: every pinned pool composes to the SAME final list and the SAME trace as HEAD."""
    b0 = ce.CandidateBudget()
    assert (b0.facet_seats, b0.compose_doc_lane_max, b0.mmr_lambda, b0.synthesis_max, b0.compose_dominance_share) == (0, 0, 0.0, 15, 0.6)
    checked = 0
    for name, pool in pools().items():
        for label, b in (("default", ce.CandidateBudget()), ("s15", ce.CandidateBudget(synthesis_max=15, compose_relevance_slots=8)),
                         ("s5", ce.CandidateBudget(synthesis_max=5))):
            final, tr = ce.compose_evidence(pool, b, weak_aspects={"q9"})
            got = json.dumps({"final": [c.chunk_id for c in final], "trace": tr}, sort_keys=True)
            assert got == json.dumps(PINS[f"{name}/{label}"], sort_keys=True), (name, label)
            assert set(tr) <= {"slots", "doc_counts", "doc_share_top", "docs_within_gap", "dominance", "dominance_avoidable", "aspect_seats",
                               "agreement_reordered"}                                     # no new receipt keys with the flags off
            checked += 1
    assert checked == 15
    # facets given but facet_seats 0 → still the old set (the facet path is the budget's, never the caller's)
    final, tr = ce.compose_evidence(pools()["A"], ce.CandidateBudget(), facets=(("f1", ("q0",)), ("f2", ("q2",))))
    assert [c.chunk_id for c in final] == PINS["A/default"]["final"] and "facet_seats" not in tr and "facet" not in tr["slots"]


def test_one_document_holding_the_top_ten_takes_at_most_forty_percent_when_three_documents_qualify():
    # d1 holds the 14 best chunks, spread over lanes A / B / C so the lane quota alone would still allow it 9 seats;
    # d2 and d3 score within the gap with 8 accepted chunks each — enough to fill 24 seats without lifting any cap
    lanes = ((ce.LANE_A, ce.LANE_B), (ce.LANE_B,), (ce.LANE_C,))
    pool = [cand(f"d1-{i}", "d1", 6.0 - i * 0.001, arrivals=lanes[i % 3], text=f"d1 passage number {i} about lighting") for i in range(14)]
    pool += [cand(f"d2-{i}", "d2", 5.98 - i * 0.001, arrivals=lanes[i % 3], text=f"d2 passage number {i} about motion") for i in range(8)]
    pool += [cand(f"d3-{i}", "d3", 5.97 - i * 0.001, arrivals=lanes[i % 3], text=f"d3 passage number {i} about story") for i in range(8)]
    final, tr = ce.compose_evidence(pool, _profile())
    assert len(final) == 24 and tr["docs_within_gap"] >= 3
    assert tr["doc_counts"]["d1"] <= int(0.4 * 24) and tr["doc_share_top"] <= 0.4 + 1e-9 and tr["dominance"] is False
    assert tr["doc_counts"]["d2"] >= 7 and tr["doc_counts"]["d3"] >= 6
    assert max(_lane_counts(final).values()) <= 3 and tr["lane_quota"]["lifted"] == 0
    # the old budget on the same pool: 60 % and no lane quota — the finding's shape
    _, tr_old = ce.compose_evidence(pool, ce.CandidateBudget())
    assert tr_old["doc_counts"]["d1"] == 9 and tr_old["doc_share_top"] == 0.6 and "lane_quota" not in tr_old


def test_per_document_per_lane_quota_is_three_and_lifts_only_when_seats_would_stay_empty():
    # d1: 8 chunks all through lane B (the fusion's dominant lane); ten other documents offer 40 chunks over lanes A and C
    # (one arrival each, so the judge order is the score order — the agreement bonus stays out of this proof)
    pool = [cand(f"d1-{i}", "d1", 5.0 - i * 0.01, text=f"d1 lane b passage {i}") for i in range(8)]
    pool += [cand(f"o{i}", f"o{i % 10}", 4.0 - i * 0.01, arrivals=(ce.LANE_A,) if i % 2 else (ce.LANE_C,), text=f"other passage {i} words {i * 7}")
             for i in range(40)]
    final, tr = ce.compose_evidence(pool, _profile())
    counts = _lane_counts(final)
    assert counts[("d1", ce.LANE_B)] == 3 and max(counts.values()) <= 3 and len(final) == 24
    assert tr["lane_quota"] == {"max": 3, "by": "first_arrival", "refused": tr["lane_quota"]["refused"], "lifted": 0} and tr["lane_quota"]["refused"] >= 5
    assert tr["slots"]["relevance"] == 8 and [c.doc_id for c in final[:3]] == ["d1", "d1", "d1"] and final[3].doc_id != "d1"   # the 4th-best d1 chunk yielded
    # a pool smaller than the seats: the last fill lifts the quota so nothing is left empty, and the receipt says so
    small = [cand(f"s{i}", "s1", 3.0 - i * 0.01) for i in range(6)] + [cand("t0", "t1", 2.5)]
    final2, tr2 = ce.compose_evidence(small, _profile())
    assert len(final2) == 7 and tr2["lane_quota"]["lifted"] == 3 and tr2["doc_counts"]["s1"] == 6


def test_two_seats_per_strong_facet_and_none_for_a_weak_one():
    # f1 = q0 (the core: 40 strong chunks over six documents and two lanes — more than the seats); f2 = q2 (four accepted
    # chunks, all outside the relevance slots); f3 = q3 (only judge-rejected evidence) — the aspect types are just how a
    # facet is asked
    pool = [cand(f"c{i}", f"d{i % 6}", 6.0 - i * 0.01, arrivals=(ce.LANE_A,) if i % 2 else (ce.LANE_B,), text=f"core passage {i} about the question") for i in range(40)]
    pool += [cand(f"f2-{i}", "e2", 0.6 - i * 0.05, qids=("q2",), text=f"directing the video model shot {i}") for i in range(4)]
    pool += [cand(f"f3-{i}", "e3", -2.0 - i, qids=("q3",), text=f"weak facet passage {i}") for i in range(2)]
    facets = (("f1", ("q0",)), ("f2", ("q2",)), ("f3", ("q3",)))
    final, tr = ce.compose_evidence(pool, _profile(), facets=facets)
    seats = {s["facet_id"]: s for s in tr["facet_seats"]}
    assert seats["f1"]["represented"] >= 2 and seats["f1"]["seated"] == 0                 # the relevance slots already seat the core
    assert seats["f2"] == {"facet_id": "f2", "seated": 2, "represented": 2, "chunk_ids": ["f2-0", "f2-1"]}
    assert seats["f3"] == {"facet_id": "f3", "seated": 0, "represented": 0, "weak": "below_floor"}
    # the two reserved seats hold (the diversity slot may add a third — a reserve is a floor, never a cap); the weak facet never
    # seats: when the quota runs the core dry, accepted core chunks are lifted in BEFORE any judge-rejected chunk
    assert tr["slots"]["facet"] == 2 and sum(1 for c in final if "q2" in c.query_ids) >= 2 and not any("q3" in c.query_ids for c in final)
    assert final[8].chunk_id == "f2-0" and final[9].chunk_id == "f2-1"                    # the facet seats come right after relevance
    assert len(final) == 24 and tr["mmr"]["seats"] > 0 and tr["lane_quota"]["lifted"] >= 1 and all(c.rerank_score > 0 for c in final)
    # no facets on the turn (/retrieve, deep research): the per-query aspect seat stands, and the receipt has no facet block
    _, tr2 = ce.compose_evidence(pool, _profile())
    assert "facet_seats" not in tr2 and "facet" not in tr2["slots"] and tr2["aspect_seats"][0]["query_id"] == "q2"
    # a facet whose queries found nothing is named `no_candidates`
    _, tr3 = ce.compose_evidence(pool, _profile(), facets=(("f1", ("q0",)), ("f7", ("q7",))))
    assert {s["facet_id"]: s.get("weak") for s in tr3["facet_seats"]}["f7"] == "no_candidates"


def test_mmr_seats_a_second_document_over_a_near_duplicate_and_says_so():
    # two documents within the gap (the dominance guard needs three, so it stays off): n1 holds six copies of one passage,
    # m2 a different passage a hair lower, m3 a different passage well below the gap but above the floor
    dup = "the exact same passage repeated word for word about soft key light on the face"
    pool = [cand(f"n{i}", "n1", 4.0 - i * 0.001, text=dup) for i in range(6)]
    pool += [cand("m0", "m2", 3.7, text="a different passage about montage rhythm and the cut"),
             cand("m1", "m3", 0.5, text="another passage on camera movement dialects per model")]
    b = ce.CandidateBudget(synthesis_max=4, compose_relevance_slots=2, compose_diversity_slots=0, compose_sparse_slots=0, mmr_lambda=0.7)
    final, tr = ce.compose_evidence(pool, b)
    ids = [c.chunk_id for c in final]
    assert tr["docs_within_gap"] == 2 and ids == ["n0", "n1", "m0", "m1"]                    # MMR: two other documents over two more duplicates
    assert tr["slots"]["mmr"] == 2 and tr["mmr"] == {"lambda": 0.7, "similarity": "lexical_cosine", "seats": 2, "changed": 2, "added_docs": ["m2", "m3"]}
    # the plain fill (λ off) takes the duplicates, in judge order
    final0, tr0 = ce.compose_evidence(pool, ce.CandidateBudget(synthesis_max=4, compose_relevance_slots=2, compose_diversity_slots=0, compose_sparse_slots=0))
    assert [c.chunk_id for c in final0] == ["n0", "n1", "n2", "n3"] and "mmr" not in tr0
    # an unjudged turn (fusion order stands) skips MMR and says so
    unjudged = [cand(f"u{i}", "u1", None, text=dup) for i in range(3)] + [cand("v0", "v2", None, text="different")]
    _, tru = ce.compose_evidence(unjudged, b)
    assert tru["mmr"]["skipped"] == "unjudged" and tru["mmr"]["seats"] == 0
    assert ce._mmr_cosine(ce._mmr_vector(dup), ce._mmr_vector(dup)) > 0.999 and ce._mmr_cosine(ce._mmr_vector("alpha beta"), ce._mmr_vector("gamma delta")) == 0.0


def test_the_profile_reaches_every_surface_through_default_budget_and_the_flag_restores_the_old_budget(monkeypatch):
    for k in ("SYNTHESIS_MAX", "FACET_SEATS", "COMPOSE_DOC_LANE_MAX", "MMR_LAMBDA", "COMPOSE_DOMINANCE_SHARE"):
        monkeypatch.delenv(f"POLYMATH_CHAT_{k}", raising=False)
    monkeypatch.delenv(ce.FACET_DIVERSITY_FLAG, raising=False)
    b = cr.default_budget()
    assert (b.synthesis_max, b.facet_seats, b.compose_doc_lane_max, b.compose_dominance_share, b.mmr_lambda) == (24, 2, 3, 0.4, 0.7)
    assert b.max_subqueries == 10 and b.rerank_max == 24 and b.rerank_max_fair == 32 and b.aspect_weak_floor == 0.5
    assert ce.facet_diversity_budget(ce.CandidateBudget()) == b
    fast = cr._fast_budget(cr.default_budget(), keep_latent=False)
    gnn_src = inspect.getsource(cr._retrieve_gnn)
    assert fast.facet_seats == 2 and fast.compose_doc_lane_max == 3 and "facet" not in gnn_src   # FAST keeps the profile; GNN never strips it
    monkeypatch.setenv("POLYMATH_CHAT_SYNTHESIS_MAX", "30")                                     # a single knob still wins
    monkeypatch.setenv("POLYMATH_CHAT_MMR_LAMBDA", "0.5")
    b2 = cr.default_budget()
    assert b2.synthesis_max == 30 and b2.mmr_lambda == 0.5 and b2.facet_seats == 2
    monkeypatch.setenv(ce.FACET_DIVERSITY_FLAG, "0")
    monkeypatch.delenv("POLYMATH_CHAT_SYNTHESIS_MAX", raising=False)
    monkeypatch.delenv("POLYMATH_CHAT_MMR_LAMBDA", raising=False)
    assert cr.default_budget() == ce.CandidateBudget()                                         # the pre-F2 budget, byte for byte
    assert not ce.facet_diversity_enabled() and ce.facet_diversity_enabled({}) and not ce.facet_diversity_enabled({ce.FACET_DIVERSITY_FLAG: "off"})
    # every mode, /retrieve, the evidence route and deep research's searches build on default_budget → chat_retrieve_v2 → the ONE
    # select_evidence / compose_evidence call
    src = inspect.getsource(cr)
    assert src.count("select_evidence(result, budget") == 1 and "facets=tuple(facets or ()) or None" in src
    assert set(cr.MODE_LANES) >= {"FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"}
    from orchestrator.api import deep_research, evidence, retrieve
    assert "chat_retrieve_mode(" in inspect.getsource(retrieve) and "chat_retrieve_mode(" in inspect.getsource(evidence)
    assert "_retrieve_impl" in inspect.getsource(deep_research)                               # deep research searches through /retrieve


def test_select_evidence_threads_the_facets_into_the_composer_receipt():
    ctx = ce.SearchContext(query="q", corpus_id="c", collection="coll", qvec=(1.0, 0.0), query_id="q0")
    union = [cand(f"c{i}", f"d{i % 3}", None, arrivals=((ce.LANE_A, ce.LANE_B), (ce.LANE_B,), (ce.LANE_C,))[i % 3], text=f"core passage {i} on topic {i % 7}")
             for i in range(30)]
    union += [cand(f"f2-{i}", "e2", None, qids=("q2",), text=f"video model direction {i}") for i in range(3)]
    res = ce.CandidateResult(context=ctx, budget=_profile(), documents=[], selected_documents=[], selected_sections=[], lane_a=[], lane_b=[], lane_c=[],
                             union=union, union_ids_uncapped=[c.chunk_id for c in union], degraded=[], timings_ms={},
                             trace={"aspects": {"q2": {"type": "PROCEDURE", "query": "video model direction", "weight": 0.9, "lanes": {}, "degraded": []}}})
    scores = {c.chunk_id: (3.0 - 0.01 * i if not c.chunk_id.startswith("f2") else 0.5) for i, c in enumerate(union)}

    def judge(q, rows):
        return sorted([dict(r, rerank_score=scores[r["chunk_id"]]) for r in rows], key=lambda r: -r["rerank_score"])
    final, tr = ce.select_evidence(res, _profile(), rerank_children=judge, facets=(("f1", ("q0",)), ("f2", ("q2",))))
    comp = tr["composition"]
    assert {s["facet_id"]: s["represented"] for s in comp["facet_seats"]} == {"f1": comp["slots"]["relevance"], "f2": 2}
    assert comp["mmr"]["lambda"] == 0.7 and comp["lane_quota"]["max"] == 3 and len(final) == 24 and len(tr["pre_g3_order"]) == 32
    assert tr["aspect_final"]["q2"] >= 2 and "q2" not in tr["weak_aspects"] and tr["aspect_best"]["q2"] == round(1 / (1 + 2.718281828459045 ** -0.5), 4)
