"""P1.d draft — concurrency + deadlines inside the candidate engine.
Splices a `_gather` helper and executor-aware lane execution into retrieve_candidates.
Anchors target the post-P1.c engine; verify each assert before applying."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
p = ROOT / "shared/polymath_shared/candidate_engine.py"; s = p.read_text(encoding="utf-8")

# 1. budget: wall-clock budgets
old = "    compose_agreement_boost: float = 0.02\n    compose_agreement_cap: float = 0.05\n"
new = old + '''    #: P1.d LATENCY ARCHITECTURE (§3.16): wall-clock budgets, not only K.
    #: A lane that misses `lane_timeout_s` is dropped with a `degraded`
    #: receipt (`<lane>_timeout`) and the turn proceeds; the judge gets
    #: `rerank_budget_s`, after which fusion order is used (`rerank_timeout`).
    lane_timeout_s: float = 6.0
    rerank_budget_s: float = 20.0
    max_workers: int = 8
'''
assert s.count(old) == 1; s = s.replace(old, new)

# 2. gather helper before retrieve_candidates
old = "def _call_dense(dense_search, kind, top_k, extra, qvec):"
new = '''class _LaneOutcome:
    __slots__ = ("rows", "ms", "error")

    def __init__(self, rows, ms, error=None):
        self.rows, self.ms, self.error = rows, ms, error


def _gather(tasks: dict, executor, timeout_s: float) -> dict:
    """Run {name: callable} concurrently on `executor` (inline when None);
    every task gets `timeout_s` from submission. Returns {name: _LaneOutcome}
    — a timeout or exception becomes `error`, never an exception here."""
    out: dict = {}
    if executor is None:
        for name, fn in tasks.items():
            t0 = time.perf_counter()
            try:
                out[name] = _LaneOutcome(fn(), round((time.perf_counter() - t0) * 1000, 1))
            except Exception as exc:  # noqa: BLE001
                out[name] = _LaneOutcome([], round((time.perf_counter() - t0) * 1000, 1), f"{type(exc).__name__}: {str(exc)[:120]}")
        return out
    import concurrent.futures as cf
    t_all = time.perf_counter()
    futs = {name: executor.submit(fn) for name, fn in tasks.items()}
    for name, fut in futs.items():
        remaining = max(0.0, timeout_s - (time.perf_counter() - t_all))
        t0 = time.perf_counter()
        try:
            rows = fut.result(timeout=remaining)
            out[name] = _LaneOutcome(rows, round((time.perf_counter() - t_all) * 1000, 1))
        except cf.TimeoutError:
            out[name] = _LaneOutcome([], round((time.perf_counter() - t_all) * 1000, 1), "timeout")
        except Exception as exc:  # noqa: BLE001
            out[name] = _LaneOutcome([], round((time.perf_counter() - t_all) * 1000, 1), f"{type(exc).__name__}: {str(exc)[:120]}")
    return out


def _call_dense(dense_search, kind, top_k, extra, qvec):'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("draft part 1 applied (budgets + _gather); lane rewiring to follow after P1.c lands")
