"""S1a (DOCUMENT-RAG-COMPLETION-V1 Part F, E5): the retrieval measurements a turn already makes are kept on its receipt,
so a slow or lossy turn can be read back at $0:
- per-probe survival;
- the deadlines hit;
- latent selection;
- the WILDCARD sweep (E4's atom frontier);
- every lane / stage timing.

Every wall-clock number lives under `trace_ms`, so a route-parity comparison drops them in one place."""
from __future__ import annotations

from orchestrator.api import ui

TRACE = {
    "plan": "chat-retrieval-v2",
    "aspects": {"q1": {"lanes": {"B": 3, "C": 1}, "degraded": [], "union": 4}},
    "aspect_final": {"q1": 2}, "aspect_best": {"q1": 0.8123}, "aspect_prefix": {"q1": 3},
    "aspect_seated": {"q1": 1}, "weak_aspects": ["q2"], "weak_reasons": {"q2": "no_candidates"},
    "concurrency": {"timed_out": ["latent_rescue"]},
    "timings_ms": {"union": 12.5, "core_wall": 900.1},
    "latency_ms": {"graph": 40.0, "wildcard": 1200.0},
    "latent": {"candidates": 5, "lane_ms": 310.2},
    "dualread": {"candidates": 2, "lane_ms": 120.0},
    "gnn": {"candidates": 0, "degraded": "off"},
}


def _ms_keys(d, path=""):
    """Every key ending in `_ms` anywhere under `d` (the wall-clock numbers that must live under trace_ms)."""
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            if str(k).endswith("_ms"):
                out.append(f"{path}{k}")
            out += _ms_keys(v, f"{path}{k}.")
    return out


def test_the_retrieval_trace_keeps_per_probe_survival_and_moves_every_timing_to_trace_ms():
    x = ui._turn_receipt_extras(TRACE, None, None)
    rt = x["retrieval_trace"]
    assert rt["aspects"] == TRACE["aspects"] and rt["aspect_final"] == {"q1": 2} and rt["aspect_best"] == {"q1": 0.8123}
    assert rt["aspect_prefix"] == {"q1": 3} and rt["aspect_seated"] == {"q1": 1}
    assert rt["weak_aspects"] == ["q2"] and rt["weak_reasons"] == {"q2": "no_candidates"}
    assert rt["timed_out"] == ["latent_rescue"]
    assert x["trace_ms"]["stages"] == {"union": 12.5, "core_wall": 900.1}
    assert x["trace_ms"]["retrieval"] == {"graph": 40.0, "wildcard": 1200.0}
    assert x["trace_ms"]["lanes"] == {"latent": 310.2, "dualread": 120.0}
    assert not _ms_keys({k: v for k, v in x.items() if k != "trace_ms"})


def test_latent_selection_and_the_wildcard_sweep_are_kept_without_their_timings():
    lat = {"enabled": True, "n_bridges": 3, "counts": {"complementary": 1}, "latency_ms": {"portfolio_seating": 88.0}}
    wc = {"returned": 3, "verified_bridges": 3, "sweep_ms": 412.0, "finish_ms": 95.5, "sweep_done_before_core": True,
          "atom_frontier": {"atoms": 12, "maps": 4, "parents_added": 16, "error": None}}
    x = ui._turn_receipt_extras(None, lat, wc)
    assert x["latent_selection"] == {"enabled": True, "n_bridges": 3, "counts": {"complementary": 1}}
    assert x["wildcard"]["atom_frontier"] == {"atoms": 12, "maps": 4, "parents_added": 16, "error": None}  # E4, receipted
    assert x["wildcard"]["returned"] == 3 and "sweep_ms" not in x["wildcard"] and "finish_ms" not in x["wildcard"]
    assert "sweep_done_before_core" not in x["wildcard"]              # which concurrent task won is a clock reading
    assert x["trace_ms"]["wildcard"] == {"sweep_ms": 412.0, "finish_ms": 95.5, "sweep_done_before_core": True}
    assert x["trace_ms"]["latent"] == {"latency_ms": {"portfolio_seating": 88.0}}
    assert not _ms_keys({k: v for k, v in x.items() if k != "trace_ms"})


def test_nothing_measured_means_nothing_receipted():
    assert ui._turn_receipt_extras(None, None, None) == {
        "retrieval_trace": None, "latent_selection": None, "wildcard": None, "trace_ms": None}


def test_s1d_the_path_aware_judge_and_each_probe_route_are_receipted_without_their_timings():
    trace = {"contextual": {"enabled": True, "judged": 4, "needs": 2, "pairs": 7, "promoted": 1, "vague": 1, "ms": 212.4},
             "probe_routes": {"p0": {"origin": "PROFILE", "own_book": True, "docs": 1, "sections": 3, "candidates": 6,
                                     "lane_ms": 188.0},
                              "br0": {"origin": "BRIDGE", "own_book": False, "docs": 3, "sections": 3, "candidates": 5,
                                      "lane_ms": 240.5}}}
    x = ui._turn_receipt_extras(trace, None, None)
    rt = x["retrieval_trace"]
    assert rt["contextual"] == {"enabled": True, "judged": 4, "needs": 2, "pairs": 7, "promoted": 1, "vague": 1}
    assert rt["probe_routes"]["p0"] == {"origin": "PROFILE", "own_book": True, "docs": 1, "sections": 3, "candidates": 6}
    assert x["trace_ms"]["contextual"] == 212.4
    assert x["trace_ms"]["probe_routes"] == {"p0": {"lane_ms": 188.0}, "br0": {"lane_ms": 240.5}}
    assert not _ms_keys({k: v for k, v in x.items() if k != "trace_ms"})


def test_s1d_a_judge_that_did_not_run_is_not_receipted():
    x = ui._turn_receipt_extras({"contextual": {"enabled": False}, "aspects": {"q1": {}}}, None, None)
    assert "contextual" not in x["retrieval_trace"] and "probe_routes" not in x["retrieval_trace"]
