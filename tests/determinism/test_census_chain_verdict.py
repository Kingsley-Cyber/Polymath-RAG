"""CENSUS-FIRST-GAP-V1 — the legacy census walks the chain and stops at
the first stage that is not ok (measured 2026-08-30: emitting a gap for
every missing stage enqueued profile/canonicalize/neo4j/verify one tick
after intake; SC-200 ran them before extract)."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "control"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "shared"))

from control.census import STAGE_CHAIN, chain_verdict  # noqa: E402


def _hist(**outcomes):
    return {stage: (out, None) for stage, out in outcomes.items()}


def test_only_the_first_missing_stage_is_a_gap() -> None:
    gaps, complete, failed = chain_verdict(_hist(intake="ok"), {"intake": 1})
    assert gaps == [("extract", "stage extract missing")]
    assert not complete and not failed


def test_failed_stage_within_budget_is_the_single_gap() -> None:
    gaps, complete, failed = chain_verdict(_hist(intake="ok", extract="failed"),
                                           {"intake": 1, "extract": 1}, max_attempts=3)
    assert gaps == [("extract", "stage extract failed; retry 1/3")]
    assert not complete and not failed


def test_failed_stage_beyond_budget_fails_the_run_without_gaps() -> None:
    gaps, complete, failed = chain_verdict(_hist(intake="ok", extract="failed"),
                                           {"intake": 1, "extract": 3}, max_attempts=3)
    assert gaps == [] and failed and not complete


def test_full_chain_ok_is_complete() -> None:
    hist = {s: ("ok", None) for s in STAGE_CHAIN}
    gaps, complete, failed = chain_verdict(hist, {s: 1 for s in STAGE_CHAIN})
    assert gaps == [] and complete and not failed
