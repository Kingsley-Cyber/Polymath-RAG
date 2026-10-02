"""FILES-STATUS-TRUTH-V1 (the owner, 2026-10-02: "THE UI MAY NEED TO BE UPDATED ESPECIALLY FILES COLOR AND STATUSES"): the
per-file summary carries each file's own run status and its open / failed stage tickets, so the Files list can say
Processing or Needs retry instead of "Ready" (measured before: cinema's five embedder-failed files and commerce's two books
whose extraction failed on a provider 503 all read "Ready"). In process: the database is faked; no network."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import document_status as DS  # noqa: E402


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, runs, tickets):
        self.runs, self.tickets, self.sql = runs, tickets, []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.sql.append(s)
        if "FROM runs r JOIN outbox_events e" in s:
            assert "superseded_by_run_id IS NULL" in s and "chunked.v1" in s    # the document_status run rule
            return _Cur(self.runs)
        if "FROM stage_tickets" in s:
            assert "archived_at IS NULL" in s
            return _Cur(self.tickets)
        raise AssertionError(f"unscripted SQL: {s[:80]}")


def _out(*docs):
    return {d: {} for d in docs}


def test_open_and_failed_work_per_file():
    out = _out("d_ready", "d_running", "d_failed", "d_no_run")
    conn = _Conn(runs=[("d_ready", "r1", "query_ready"), ("d_running", "r2", "reconciling"), ("d_failed", "r3", "reconciling")],
                 tickets=[("r1", "vocabulary", "pending", None),                  # background work of a promoted file
                          ("r2", "project_canonical", "leased", None), ("r2", "verify_projections", "pending", None),
                          ("r3", "extract", "failed", "cloud transport failed: HTTP 503 " + "x" * 300),
                          ("r3", "project_qdrant", "pending", None)])            # waits on the failure: not open work
    DS._attach_run_work(conn, out)
    assert out["d_ready"] == {"run_status": "query_ready", "work_open": ["vocabulary"], "work_failed": []}
    assert out["d_running"]["work_open"] == ["project_canonical", "verify_projections"]
    assert out["d_failed"]["work_open"] == []
    assert out["d_failed"]["work_failed"][0]["stage"] == "extract"
    assert out["d_failed"]["work_failed"][0]["note"].startswith("cloud transport failed: HTTP 503")
    assert len(out["d_failed"]["work_failed"][0]["note"]) == 200                 # bounded
    assert out["d_no_run"] == {"run_status": None, "work_open": [], "work_failed": []}


def test_no_run_means_no_ticket_read():
    out = _out("d1")
    conn = _Conn(runs=[], tickets=[])
    DS._attach_run_work(conn, out)
    assert out["d1"]["run_status"] is None and len(conn.sql) == 1               # one read, nothing more
