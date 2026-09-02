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


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    """Answers _open_work by stage family; query/ui signals absent."""

    def __init__(self, open_by_stage):
        self.open_by_stage = open_by_stage

    def execute(self, sql, params=None):
        if "FROM stage_tickets" in sql:
            stages = params[0]
            n = sum(self.open_by_stage.get(st, 0) for st in stages)
            return _FakeCursor((n,))
        if "runtime_signals" in sql and "SELECT" in sql:
            return _FakeCursor(None)
        return _FakeCursor(None)


def test_extract_scales_out_one_worker_per_open_ticket_capped_at_3():
    from control.fleet_autopilot import desired_slots
    known = {"extract", "extract2", "extract3", "profile", "sidecar_gliner",
             "sidecar_spacy", "sidecar_embedder", "qdrant"}
    # a lone document holds profile_document AND extract open: still ONE worker
    one, _ = desired_slots(_FakeConn({"extract": 1, "profile_document": 1}), known)
    two, _ = desired_slots(_FakeConn({"extract": 2, "profile_document": 2}), known)
    five, _ = desired_slots(_FakeConn({"extract": 5, "profile_document": 5}), known)
    assert "extract" in one and "extract2" not in one
    assert {"extract", "extract2"} <= two and "extract3" not in two
    assert {"extract", "extract2", "extract3"} <= five
    assert "extract4" not in five


def test_reranker_stays_warm_during_ingest_when_queries_are_recent():
    """RERANKER-DURING-INGEST-V1: extract demand must not park the
    reranker (GLiNER-era rule); only a resident GLiNER excludes it."""
    from control.fleet_autopilot import desired_slots

    class _Conn(_FakeConn):
        def execute(self, sql, params=None):
            if "runtime_signals" in sql and "last_query" in sql:
                return _FakeCursor((30.0,))          # queried 30 s ago
            return super().execute(sql, params)

    known = {"extract", "profile", "sidecar_embedder", "sidecar_reranker",
             "sidecar_gliner", "sidecar_spacy", "qdrant"}
    got, reasons = desired_slots(_Conn({"extract": 1, "profile_document": 1}), known)
    assert "extract" in got
    assert "sidecar_reranker" in got, reasons
