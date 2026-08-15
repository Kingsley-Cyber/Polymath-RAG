"""Q1 qualification regression locks (no stores).

Freezes the heterogeneous qualification corpus and its measured
results: the corpus hash, the scorer (Phase H harness) hash, and the
baseline (production lexical arm) metrics. Any compiler/rule-pack
change that moves these numbers fails loudly here — extraction changes
require a demonstrated regression or a separately measured
improvement.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval" / "phase_h"))

Q1_CORPUS_SHA256 = "2ce1d237d222e1feaf573747abb53c3a618d557b561667f22d5d336c1dbe380a"
HARNESS_SHA256 = "94fdc6a9a92abb9f9ae0206e4b4d67ac4e42ad93f4fa9e80fefa0f5efc5b656c"
FROZEN_BASELINE = {
    "correct": 50,
    "incorrect": 3,
    "missed": 3,
    "total": 56,
    "precision": 0.9433962264150944,
    "recall": 0.9433962264150944,
}


@pytest.fixture(scope="module")
def q1_paths(repo_root: Path) -> tuple[Path, Path]:
    return (
        repo_root / "eval" / "gold" / "qualification_q1.yaml",
        repo_root / "eval" / "phase_h" / "harness.py",
    )


def test_q1_corpus_is_frozen(q1_paths: tuple[Path, Path]) -> None:
    corpus, _ = q1_paths
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() == Q1_CORPUS_SHA256


def test_q1_scorer_is_frozen(q1_paths: tuple[Path, Path]) -> None:
    _, harness = q1_paths
    assert hashlib.sha256(harness.read_bytes()).hexdigest() == HARNESS_SHA256


def test_q1_baseline_metrics_reproduce(q1_paths: tuple[Path, Path]) -> None:
    """Re-run the production (lexical) arm over the frozen corpus and
    compare against the frozen qualification metrics."""
    corpus, _ = q1_paths
    gold = yaml.safe_load(corpus.read_text())
    assert gold["version"] == "q1.0"

    import harness as _h  # noqa: E402

    run = _h.run_arm(gold["items"], "baseline")
    units = _h.score(run["predictions"], gold["items"])["units"]
    summary = _h.summarize(units)
    for key, value in FROZEN_BASELINE.items():
        assert summary[key] == value, f"baseline {key} drifted: {summary[key]} != {value}"
