"""The verifier's gates must not PASS on nothing (2026-09-12).

A gate that reports "no violations found" cannot, by itself, be distinguished from a scan
that found nothing because it looked nowhere. Three gates had that shape:

  * `retrieval_truthful_mode` tested "requested and executed do not CONFLICT" — which a
    response carrying no mode metadata at all satisfied;
  * `outbox_corpus_scoped` tested "no Seq Scan on outbox_events" — trivially true of a
    plan that never touched the table, e.g. for a corpus with zero documents;
  * `hot_path_no_toast_detoast` tested "the plan mentions no payload/TOAST" — trivially
    true of an empty plan.

Each now requires positive evidence that the thing was actually observed. These tests
feed each gate the vacuous input and require FAIL.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def vfs():
    spec = importlib.util.spec_from_file_location(
        "vfs_vacuity", ROOT / "scripts" / "verify_final_state.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["vfs_vacuity"] = m
    spec.loader.exec_module(m)
    m.results.clear()
    return m


def _gate(vfs, name):
    return next(r for r in vfs.results if r["gate"] == name)


def test_a_response_with_no_executed_mode_is_not_truthful(vfs, monkeypatch):
    """The engine answering without saying WHICH mode it ran is exactly the condition
    this gate exists to catch; 'no conflict' let it through."""
    monkeypatch.setattr(vfs, "_post", lambda *a, **k: {
        "meta": {"engine": "candidate-retrieval-v1"}})     # engine present, mode absent
    vfs.check_retrieval_core()
    assert _gate(vfs, "retrieval_truthful_mode")["status"] == vfs.FAIL


def test_a_truthful_response_still_passes(vfs, monkeypatch):
    """The strictness must not cost the real case."""
    def _post(path, body, **k):
        m = body["mode"]
        return {"meta": {"engine": "candidate-retrieval-v1",
                         "requested_mode": m, "executed_mode": m}}
    monkeypatch.setattr(vfs, "_post", _post)
    vfs.check_retrieval_core()
    assert _gate(vfs, "retrieval_truthful_mode")["status"] == vfs.PASS
    assert _gate(vfs, "retrieval_core_one_engine")["status"] == vfs.PASS


class _Conn:
    """EXPLAIN rows per query, plus the doc_id list for the corpus."""

    def __init__(self, graph_plan, outbox_plan, doc_ids):
        self._g, self._o, self._ids = graph_plan, outbox_plan, doc_ids

    def execute(self, sql, *a, **k):
        if "doc_id FROM documents" in sql:
            rows = [(i,) for i in self._ids]
        elif "EXPLAIN" in sql and "outbox" in sql.lower():
            rows = [(l,) for l in self._o.splitlines()]
        else:
            rows = [(l,) for l in self._g.splitlines()]
        class _R:
            def fetchall(_s): return rows
            def fetchone(_s): return rows[0] if rows else None
        return _R()


_GOOD_GRAPH = "Index Scan using documents_pkey\nExecution Time: 0.2 ms"
_GOOD_OUTBOX = "Index Scan using outbox_events_doc_idx on outbox_events\nExecution Time: 0.3 ms"


def test_an_empty_corpus_cannot_certify_the_outbox_index_path(vfs, monkeypatch):
    """Zero documents means the plan scanned nothing, and 'no Seq Scan' is then a
    statement about a query that never ran."""
    monkeypatch.setattr(vfs, "OUTBOX_SQL", "SELECT 1 FROM outbox_events WHERE doc_id = ANY(%s)")
    vfs.check_hot_paths(_Conn(_GOOD_GRAPH, "Result\nExecution Time: 0.01 ms", []))
    assert _gate(vfs, "outbox_corpus_scoped")["status"] == vfs.FAIL


def test_an_empty_plan_is_not_a_toast_free_plan(vfs):
    """sha of nothing is still a sha; a plan with no Execution Time never executed."""
    vfs.check_hot_paths(_Conn("", _GOOD_OUTBOX, ["d1"]))
    assert _gate(vfs, "hot_path_no_toast_detoast")["status"] == vfs.FAIL


def test_real_plans_over_a_real_corpus_still_pass(vfs):
    vfs.check_hot_paths(_Conn(_GOOD_GRAPH, _GOOD_OUTBOX, ["d1", "d2"]))
    assert _gate(vfs, "hot_path_no_toast_detoast")["status"] == vfs.PASS
    assert _gate(vfs, "outbox_corpus_scoped")["status"] == vfs.PASS


def test_no_gate_reports_PASS_from_inside_an_exception_handler():
    """The worst shape of all: the command that certifies everything, certifying an
    error. Every error path must report NOT_TESTED or FAIL, never PASS."""
    import ast
    tree = ast.parse((ROOT / "scripts" / "verify_final_state.py").read_text())
    spans = [(h.lineno, max(getattr(n, "lineno", h.lineno) for n in ast.walk(h)))
             for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)]
    offenders = [c.lineno for c in ast.walk(tree)
                 if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "gate"
                 and len(c.args) > 1 and getattr(c.args[1], "id", "") == "PASS"
                 and any(lo <= c.lineno <= hi for lo, hi in spans)]
    assert not offenders, f"gate(..., PASS) inside an except handler at lines {offenders}"
