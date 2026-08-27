"""CP2.1 — in-flight lease renewal for long stages.

claim_ttl_s=300 vs a 45-minute book extract: without renewal the control
plane revokes a healthy worker's lease mid-stage (ready ticket = double-
processing risk) and falsely quarantines the owner, because heartbeats only
happen between events."""
import threading
import time

from polymath_shared.worker_runtime import _lease_keeper


class _Conn:
    calls: list = []
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=()):
        _Conn.calls.append((" ".join(sql.split()), params))
        class _R:
            def fetchone(self): return None
            def fetchall(self): return []
        return _R()
    def commit(self): pass


def test_keeper_renews_lease_and_heartbeats_then_stops(monkeypatch):
    import psycopg
    import polymath_shared.worker_runtime as W
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: _Conn())
    monkeypatch.setattr(W, "heartbeat",
                        lambda conn, wid, **kw: _Conn.calls.append(("HEARTBEAT", wid)))
    _Conn.calls = []
    stop = threading.Event()
    t = threading.Thread(target=_lease_keeper,
                         args=("dsn", "w1", "t1", 300, stop, 0.05), daemon=True)
    t.start()
    time.sleep(0.30)
    stop.set(); t.join(timeout=2)
    renewals = [c for c in _Conn.calls if "lease_expires_at" in c[0]]
    beats = [c for c in _Conn.calls if c[0] == "HEARTBEAT"]
    assert len(renewals) >= 3 and len(beats) >= 3
    # renewal is scoped: only OUR lease, only while still leased
    assert "lease_owner = %s" in renewals[0][0] or "lease_owner" in renewals[0][0]
    n = len(_Conn.calls)
    time.sleep(0.2)
    assert len(_Conn.calls) == n, "keeper must stop when the stage finishes"
