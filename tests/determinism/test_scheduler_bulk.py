"""SCHEDULER-BULK-V1 regressions (measured live 2026-08-25).

The per-gap loop made 1-2 queries per census gap (~50-55s of every live
tick across tens of thousands of replayed gaps). The bulk scheduler must
produce BYTE-IDENTICAL idempotency keys with O(types) reads and chunked
inserts.
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "shared"))

from control.census import Census, Gap
from control.scheduler import schedule_gaps
from polymath_shared.identity import content_hash


class RecordingConn:
    """Records statements; serves canned DISTINCT ON rows."""

    def __init__(self, first_payloads):
        self._first = first_payloads
        self.sqls: list[str] = []
        self.insert_params = None

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sqls.append(flat)
        if "FROM stage_tickets" in flat and "superseded" in flat:
            self._result = []          # nothing archived
            return self
        if "DISTINCT ON" in flat:
            self._result = [(rid, {"doc_id": f"d_{rid}"})
                            for rid in self._first]
            return self
        if "INSERT INTO outbox_events" in flat:
            self.insert_params = params
        return self

    def fetchone(self):
        rows = getattr(self, "_result", None)
        return rows[0] if rows else None

    @property
    def rowcount(self):
        p = self.insert_params or ([], [], [], [])
        return len(p[0])

    def fetchall(self):
        return getattr(self, "_result", [])


def _census() -> Census:
    c = Census()
    c.gaps.extend([
        Gap("run_a", "corp", "project_qdrant", "project_qdrant.v1", "missing"),
        Gap("run_b", "corp", "verify_projections", "verify.v1", "missing"),
        Gap("run_c", "corp", "chunked", "chunked.v1", "missing"),
        Gap("run_d", "corp", "chunked", "chunked.v1", "missing"),
    ])
    return c


def test_identity_gaps_need_zero_reads_and_keys_match():
    conn = RecordingConn(first_payloads=["run_c"])   # run_d unresolved
    n = schedule_gaps(conn, _census())
    # exactly one payload read (chunked DISTINCT ON) + one bulk insert;
    # identity-only types issue NO reads at all.
    assert sum(1 for s in conn.sqls if "DISTINCT ON" in s) == 1
    assert len(conn.sqls) == 3  # archived-probe + DISTINCT ON + insert
    assert sum(1 for s in conn.sqls if "INSERT INTO outbox_events" in s) == 1
    assert n == 3   # run_d had no recorded payload -> skipped, as before


def test_idempotency_keys_are_byte_identical_to_legacy_derivation():
    """The outbox re-arm contract depends on key stability across the
    rewrite; derive expected keys independently here."""
    conn = RecordingConn(first_payloads=["run_c"])
    schedule_gaps(conn, _census())
    run_ids, event_types, payloads, keys = conn.insert_params
    by_run = dict(zip(run_ids, zip(event_types, payloads, keys)))

    assert by_run["run_c"][0] == "chunked.v1"
    assert by_run["run_c"][2] == content_hash({
        "run": "run_c", "type": "chunked.v1",
        "payload": {"doc_id": "d_run_c"}})

    assert by_run["run_a"][0] == "project_qdrant.v1"
    assert by_run["run_a"][1] == '{"run_id": "run_a"}'
    assert by_run["run_a"][2] == content_hash({
        "run": "run_a", "type": "project_qdrant.v1",
        "payload": {"run_id": "run_a"}})


def test_intake_falls_back_to_runs_metadata():
    class IntakeConn(RecordingConn):
        def execute(self, sql, params=None):
            flat = " ".join(sql.split())
            self.sqls.append(flat)
            if "FROM stage_tickets" in flat and "superseded" in flat:
                self._result = []
                return self
            if "DISTINCT ON" in flat and "intake.v1" in str(params):
                self._result = []          # no recorded intake event
                return self
            if "FROM runs" in flat:
                self._result = [("run_i", {"intake_payload":
                                           {"corpus_id": "c1"}})]
                return self
            if "INSERT INTO outbox_events" in flat:
                self.insert_params = params
            return self

    c = Census()
    c.gaps.append(Gap("run_i", "c1", "intake", "intake.v1", "missing"))
    conn = IntakeConn(first_payloads=[])
    n = schedule_gaps(conn, c)
    assert n == 1
    run_ids, event_types, payloads, _ = conn.insert_params
    assert run_ids == ["run_i"] and event_types == ["intake.v1"]
    assert '"corpus_id": "c1"' in payloads[0]
