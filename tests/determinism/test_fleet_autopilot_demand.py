"""AUTOPILOT-TAIL-DEMAND-V1: the demand map must cover the whole
ticket taxonomy, and tail work on a query_ready run is still work.

Live failure pinned here (2026-09-01): the moment a run flipped
query_ready its open tail tickets stopped counting as demand —
summaries was parked with parent_enrichment=ready and the tail froze
45+ minutes with zero workers. Separately, parent_enrichment and
compile_objects mapped to no lane at all.
"""
import inspect

from control.fleet_autopilot import LANES, _open_work


def _demand_stages():
    out = set()
    for _name, stages, _slots in LANES:
        out |= set(stages)
    return out


def test_every_tail_stage_signals_some_lane():
    stages = _demand_stages()
    assert "parent_enrichment" in stages, (
        "enrichment tickets must wake the summaries worker")
    assert "compile_objects" in stages, (
        "compile_objects tickets must wake their worker")


def test_compile_objects_maps_to_its_own_slot():
    lane = next((slots for _n, stages, slots in LANES
                 if "compile_objects" in stages), None)
    assert lane and "compile_objects" in lane


def test_enrichment_wakes_the_summaries_slot():
    lane = next((slots for _n, stages, slots in LANES
                 if "parent_enrichment" in stages), None)
    assert lane and "summaries" in lane


def test_query_ready_runs_still_count_as_demand():
    """query_ready is the CHAIN terminal, not the RUN terminal — the
    non-blocking tail keeps open tickets after the flip and must keep
    attracting workers."""
    sql = inspect.getsource(_open_work)
    assert "'query_ready'" in sql, (
        "_open_work's run-status filter dropped query_ready; tail "
        "tickets on promoted runs freeze without it")
    # the historical statuses stay — this is an addition, not a swap
    for s in ("'intake'", "'reconciling'", "'degraded'"):
        assert s in sql
