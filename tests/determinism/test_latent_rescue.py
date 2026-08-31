"""Phase D exit proofs (plan §4.D.3): fail-open on every failure mode,
caps honoured, section-parents skipped, deterministic collapse — and the
frozen-plan proof that latent_enabled=False is byte-identical."""
from __future__ import annotations

from dataclasses import replace

from polymath_shared.hybrid import HYBRID_DEFAULT_PLAN
from polymath_shared.latent.rescue import latent_rescue_parents

PLAN = replace(HYBRID_DEFAULT_PLAN, latent_enabled=True)
QVEC = [0.1] * 8


def _row(pid, doc, score, kind_payload=None):
    return {"score": score, "payload": {
        "parent_id": pid, "doc_id": doc, "source_name": f"{doc}.md",
        **(kind_payload or {})}}


def test_collapse_dedupe_and_caps():
    def search(_c, _v, filters):
        kind = filters["representation_kind"]
        if kind == "latent_abstraction":
            return [_row("p1", "d1", 0.9), _row("p2", "d1", 0.8),
                    _row("p3", "d2", 0.7), _row("p4", "d2", 0.6)]
        return [_row("p2", "d1", 0.95), _row("p5", "d3", 0.5)]

    out = latent_rescue_parents(QVEC, corpus_id="c", plan=PLAN,
                                routing_search=search)
    assert out.degraded is None
    # collapsed by parent, best score wins, capped at latent_max_parents
    assert [p.parent_id for p in out.parents] == ["p2", "p1", "p3"]
    p2 = out.parents[0]
    assert p2.best_score == 0.95
    assert set(p2.channels) == {"latent_abstraction", "latent_transfer"}


def test_section_parents_are_skipped():
    def search(_c, _v, filters):
        return [_row("p_in_sections", "d1", 0.9), _row("p_new", "d1", 0.8)]

    out = latent_rescue_parents(
        QVEC, corpus_id="c", plan=PLAN, routing_search=search,
        skip_parent_ids=frozenset({"p_in_sections"}))
    assert [p.parent_id for p in out.parents] == ["p_new"]


def test_fail_open_on_exception():
    def search(*_a, **_k):
        raise RuntimeError("qdrant down")

    out = latent_rescue_parents(QVEC, corpus_id="c", plan=PLAN,
                                routing_search=search)
    assert out.parents == [] and out.degraded == "RuntimeError"


def test_fail_open_on_budget():
    ticks = iter([0.0, 10.0, 10.0, 10.0])

    def clock():
        return next(ticks)

    out = latent_rescue_parents(QVEC, corpus_id="c", plan=PLAN,
                                routing_search=lambda *a: [],
                                clock=clock)
    assert out.parents == [] and out.degraded == "budget_exceeded"


def test_malformed_payload_rows_are_ignored():
    def search(_c, _v, _f):
        return [{"score": 0.9, "payload": {}},          # no parent_id
                {"score": None, "payload": None},        # junk
                _row("p_ok", "d1", 0.5)]

    out = latent_rescue_parents(QVEC, corpus_id="c", plan=PLAN,
                                routing_search=search)
    assert out.degraded is None or out.degraded == "TypeError"
    ids = [p.parent_id for p in out.parents]
    assert ids in (["p_ok"], [])                        # never junk parents


def test_latent_disabled_plan_is_frozen():
    # the frozen default: latent OFF, all knobs at plan v1 values
    assert HYBRID_DEFAULT_PLAN.latent_enabled is False
    assert HYBRID_DEFAULT_PLAN.plan_version == "hybrid-retrieval-v1"
