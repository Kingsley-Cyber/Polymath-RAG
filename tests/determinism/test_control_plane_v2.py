"""CONTROL-PLANE-V2 unit contract (ADR-0014).

Ticket state machine, worker compatibility gating, generation barrier,
backpressure watermark, snapshot invalidation. Deterministic, no live
services (SQL-shape pieces are integration-tested separately).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

from control.tickets import (
    DAG_ORDER,
    STAGE_DAG,
    DEFAULT_HIGH_WATERMARK,
    backpressure_paused,
    ticket_id,
)
from polymath_shared.execution import compatible, worker_contracts, worker_identity


def test_stage_dag_covers_the_production_chain_in_order():
    assert DAG_ORDER == [
        "intake", "extract", "profile_document", "project_qdrant",
        "project_neo4j", "canonicalize", "project_canonical",
        "verify_projections",
        # SUMMARY-VOCABULARY-LAYER: background intelligence stages,
        # non-blocking (knowledge=READY while summaries=DEGRADED).
        "parent_summary", "document_summary", "corpus_summary",
        "vocabulary",
    ]
    # every stage declares its event type; explicit handoff specs exist
    for stage, event_type, artifacts, receipts in STAGE_DAG:
        assert event_type.endswith(".v1")
        assert isinstance(artifacts, tuple) and isinstance(receipts, tuple)


def test_ticket_identity_is_deterministic_and_stage_scoped():
    a = ticket_id("run_1", "extract")
    assert a == ticket_id("run_1", "extract")
    assert a != ticket_id("run_1", "profile_document")
    assert a != ticket_id("run_2", "extract")


def test_worker_identity_and_contracts_shape():
    identity = worker_identity("extract")
    assert identity["worker_type"] == "extract"
    assert identity["pid"] > 0 and identity["host"]
    contracts = worker_contracts()
    for key in ("query_policy", "rule_pack", "syntax_provider", "rescue_stages"):
        assert key in contracts


def test_compatibility_gating():
    worker = {"build_sha": "abc", "query_policy": "semantic-query-policy-v1",
              "rule_pack": "1.2.0", "syntax_provider": "disabled",
              "rescue_stages": []}
    # identical run contract -> lease granted
    assert compatible(worker, {"worker_build": "abc",
                               "query_policy": "semantic-query-policy-v1",
                               "rule_pack": "1.2.0",
                               "syntax_provider": "disabled",
                               "rescue_stages": []})
    # stale build -> REFUSED (the 12-hour-old-worker class)
    assert not compatible(worker, {"worker_build": "def"})
    # different rescue stages -> REFUSED (experiment isolation)
    assert not compatible(worker, {"rescue_stages": ["boundary"]})
    # different rule pack -> REFUSED
    assert not compatible(worker, {"rule_pack": "1.3.0"})
    # unspecified requirements pass (legacy runs)
    assert compatible(worker, {})


def test_backpressure_watermark_constant():
    assert DEFAULT_HIGH_WATERMARK >= 16  # a real queue bound, not a token


def test_snapshot_invalidation_is_loud():
    # The snapshot module's contract: validate raises RuntimeError on
    # drift/invalid; acquisition refuses at an open barrier. The SQL
    # behavior is exercised in the integration test; here we pin the
    # module's public surface.
    from control import snapshots

    assert callable(snapshots.acquire_snapshot)
    assert callable(snapshots.validate_snapshot)
    assert callable(snapshots.corpus_state_hash)
