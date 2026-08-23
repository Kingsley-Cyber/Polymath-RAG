"""SUMMARY-VOCABULARY-LAYER S1: stage declarations + artifact envelope.

Summary stages exist in the DAG, run in the background, and must NEVER
block corpus promotion (knowledge=READY while summaries=DEGRADED).
Every summary artifact carries the owner-mandated envelope.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from control.tickets import (  # noqa: E402
    NON_BLOCKING_STAGES,
    STAGE_DAG,
    is_blocking,
)
from polymath_shared.summary_layer import (  # noqa: E402
    build_envelope,
    validate_envelope,
)


def test_summary_stages_declared_after_settlement():
    order = [stage for stage, *_ in STAGE_DAG]
    for stage in ("parent_summary", "document_summary",
                  "corpus_summary", "vocabulary"):
        assert stage in order, stage
        assert order.index(stage) > order.index("verify_projections")


def test_summary_stages_are_never_blocking():
    for stage in ("parent_summary", "document_summary",
                  "corpus_summary", "vocabulary"):
        assert stage in NON_BLOCKING_STAGES
        assert is_blocking(stage) is False
    assert is_blocking("extract") is True
    assert is_blocking("verify_projections") is True


def test_envelope_roundtrip_valid():
    env = build_envelope(derived_from=["child_001", "child_002"],
                         payload={"summary": "attention heads process "
                                             "relationships"})
    problems = validate_envelope(env)
    assert not problems, problems
    assert env["artifact_id"].startswith("sum_")


def test_envelope_rejects_missing_provenance():
    env = build_envelope(derived_from=["child_001"], payload={"s": 1})
    del env["input_hash"]
    problems = validate_envelope(env)
    assert problems


def test_envelope_output_hash_tracks_payload():
    a = build_envelope(derived_from=["x"], payload={"summary": "a"})
    b = build_envelope(derived_from=["x"], payload={"summary": "b"})
    assert a["output_hash"] != b["output_hash"]
    assert a["input_hash"] == b["input_hash"]
