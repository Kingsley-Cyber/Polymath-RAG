"""RECEIPT-LOOKUP-BATCH-V1: the projector's already-current lookup never sends
more than libpq's 65,535 bind parameters in one query. Measured 2026-09-03:
four ecom runs failed project_qdrant on the re-chunked corpus."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

from workers import project_qdrant_worker as W


class _Conn:
    def __init__(self):
        self.param_counts = []

    def execute(self, sql, params):
        self.param_counts.append(len(params))
        class R:
            def fetchall(self_inner):
                # every second row is "current"
                return [(params[j], params[j + 1]) for j in range(0, len(params) - 1, 6)]
        return R()


def test_lookup_is_batched_under_the_parameter_ceiling():
    wanted = [("chunk", f"chunk_{i}", f"h{i}") for i in range(25_000)]
    conn = _Conn()
    got = W._already_current(conn, wanted)
    assert conn.param_counts and max(conn.param_counts) <= 65_535
    assert len(conn.param_counts) == 3            # 10k + 10k + 5k rows
    assert all(c % 3 == 1 for c in conn.param_counts)   # 3 per row + the projection
    assert got and all(k == "chunk" for k, _ in got)
    assert W._already_current(conn, []) == set()
