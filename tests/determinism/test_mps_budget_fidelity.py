"""The MPS cap a sidecar receives must be the cap the budget states.

Two defects are fenced here, both observed in production:

  DENOMINATOR  `PYTORCH_MPS_HIGH_WATERMARK_RATIO` is applied by torch
               against Metal's recommended max working set (~78% of
               RAM), not against physical memory. Dividing the budget by
               physical memory made a 2.0 GB embedder budget into a
               1.56 GiB ceiling, and the release projection died with
               `MPS backend out of memory` at 1.54 GiB allocated -- a
               22% shortfall that read, from outside, like a semantic
               failure.

  OOM RECOVERY the batch planner sizes groups from an approximate token
               count. When that estimate was wrong the allocator raised,
               the sidecar answered 500, and the caller lost a whole
               projection ticket plus one of its retries. A wrong size
               estimate must cost a retry of the batch, not the work.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import runtime_budget as rb  # noqa: E402

EMBEDDER = ROOT / "sidecars" / "embedder" / "server.py"


# ---------------------------------------------------------------------------
# DENOMINATOR
# ---------------------------------------------------------------------------

def test_ratio_resolves_to_the_budgeted_gigabytes(monkeypatch):
    """ratio x torch's own denominator must reproduce the budget figure."""
    monkeypatch.setattr(rb, "mps_denominator_gb", lambda: 24.96)
    env = rb.mps_env("sidecar_embedder")
    ratio = float(env["PYTORCH_MPS_HIGH_WATERMARK_RATIO"])
    budgeted = float(rb.budget()["sidecars"]["sidecar_embedder"]["mps_gb"])
    assert ratio * 24.96 == pytest.approx(budgeted, rel=0.01), (
        f"ratio {ratio} against torch's 24.96 GiB denominator yields "
        f"{ratio * 24.96:.2f} GiB, but the budget promises {budgeted} GB")


def test_denominator_is_not_physical_memory(monkeypatch):
    """The exact regression: physical memory is the wrong divisor."""
    monkeypatch.setattr(rb, "mps_denominator_gb", lambda: 24.96)
    monkeypatch.setattr(rb, "physical_gb", lambda: 32.0)
    ratio = float(rb.mps_env("sidecar_embedder")["PYTORCH_MPS_HIGH_WATERMARK_RATIO"])
    budgeted = float(rb.budget()["sidecars"]["sidecar_embedder"]["mps_gb"])
    assert ratio != pytest.approx(budgeted / 32.0, rel=0.001), (
        "cap was computed against physical memory; torch will apply it to "
        "the recommended working set and the sidecar will OOM below budget")


def test_denominator_falls_back_without_torch(monkeypatch):
    """No Metal, no crash: the fallback must stay a plausible fraction."""
    phys = rb.physical_gb() or 32.0
    real_run = rb.subprocess.run

    def only_torch_fails(cmd, *a, **k):
        if "-c" in cmd:                       # the torch probe, not sysctl
            raise OSError("no torch")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(rb.subprocess, "run", only_torch_fails)
    rb.mps_denominator_gb.cache_clear()
    try:
        value = rb.mps_denominator_gb()
    finally:
        rb.mps_denominator_gb.cache_clear()
    assert 0.5 * phys < value <= phys, (
        f"fallback denominator {value} is not a sane fraction of {phys}")


def test_cpu_only_sidecar_gets_no_metal_budget():
    env = rb.mps_env("sidecar_spacy")
    assert env["POLYMATH_MPS_CAP_GB"] == "0"
    assert "PYTORCH_MPS_HIGH_WATERMARK_RATIO" not in env


# ---------------------------------------------------------------------------
# OOM RECOVERY  (AST-based: a previous text patch to this file silently
# dedented a `return` out of its guard and caused 11 restart storms)
# ---------------------------------------------------------------------------

def _fn(name: str):
    """Locate a def by name. `infer` is `async def`, a distinct AST node."""
    tree = ast.parse(EMBEDDER.read_text())
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return node
    raise AssertionError(f"{name}() missing from {EMBEDDER.name}")


def test_infer_encodes_through_the_adaptive_path():
    """/infer must not call model.encode directly and lose the retry."""
    infer = _fn("infer")
    calls = [n for n in ast.walk(infer) if isinstance(n, ast.Call)]
    direct = [c for c in calls
              if isinstance(c.func, ast.Attribute) and c.func.attr == "encode"]
    assert not direct, "infer() calls model.encode directly; an OOM there 500s"
    assert any(isinstance(c.func, ast.Name) and c.func.id == "_encode_adaptive"
               for c in calls), "infer() does not use _encode_adaptive"


def test_adaptive_encode_splits_on_oom_and_recurses():
    fn = _fn("_encode_adaptive")
    src = ast.dump(fn)
    assert "_is_oom" in src, "_encode_adaptive does not discriminate OOM"
    assert "_release_mps" in src, "_encode_adaptive does not release the pool"
    assert sum(1 for n in ast.walk(fn)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "_encode_adaptive") >= 2, (
        "_encode_adaptive does not recurse into both halves")


def test_single_text_oom_still_raises():
    """One text that cannot fit is a real capacity failure, not a retry."""
    fn = _fn("_encode_adaptive")
    guards = [n for n in ast.walk(fn) if isinstance(n, ast.If)]
    assert any(
        any(isinstance(c, ast.Compare)
            and any(isinstance(x, ast.Constant) and x.value == 1
                    for x in c.comparators)
            for c in ast.walk(g.test))
        and any(isinstance(b, ast.Raise) for b in ast.walk(g))
        for g in guards), (
        "_encode_adaptive must re-raise rather than split a single text; "
        "silently returning would fabricate vectors")


def test_non_oom_errors_are_not_retried():
    """Splitting a batch cannot fix a contract or model error."""
    fn = _fn("_encode_adaptive")
    assert any(
        isinstance(g.test, ast.BoolOp)
        and any(isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)
                for v in ast.walk(g.test))
        and any(isinstance(b, ast.Raise) for b in ast.walk(g))
        for g in ast.walk(fn) if isinstance(g, ast.If)), (
        "_encode_adaptive must re-raise non-OOM exceptions immediately")
