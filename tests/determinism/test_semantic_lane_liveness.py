"""SEMANTIC-LANE-LIVENESS-V1: ingestion-side dead-feature gates.

Retrieval lanes are judged per query from a trace. Ingestion lanes must
be judged from DURABLE state, because their opportunity happens once at
ingest and has to stay answerable months later.

The measurement this encodes: `procedure_artifacts = 12` is meaningless
alone. It is simultaneously 12 of 12 documents (100%) and 12 of 965
opportunities (1.24%), because compile_procedure emits at most ONE
artifact per document. Only opportunity-vs-capture makes that visible.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.knowledge_objects import concept as C  # noqa: E402
from polymath_shared.knowledge_objects import procedure as P  # noqa: E402
from polymath_shared.lane_liveness import (  # noqa: E402
    STATUS_CAPPED,
    STATUS_LIVE,
    STATUS_NO_OPPORTUNITY,
    STATUS_SUSPECT,
    STATUS_UNOBSERVABLE,
    semantic_lane_status,
)


# ================================================= LIVENESS SEMANTICS
def test_measured_production_state_is_classified_correctly():
    """The real cysa-study-v1 numbers, pinned so a future change that
    silently alters lane behaviour has to confront them."""
    # 965 procedure opportunities -> 12 artifacts, cap never binds
    assert semantic_lane_status(opportunities=965, accepted=12,
                                capped_documents=0, documents=12) == STATUS_LIVE
    # 2,210 concept opportunities -> 120 artifacts, cap binds in 12/12
    assert semantic_lane_status(opportunities=2210, accepted=120,
                                capped_documents=12,
                                documents=12) == STATUS_CAPPED


def test_no_opportunity_is_not_a_defect():
    """A corpus with no procedural evidence SHOULD yield none."""
    assert semantic_lane_status(opportunities=0, accepted=0) \
        == STATUS_NO_OPPORTUNITY


def test_evidence_but_no_output_is_the_dead_lane_signal():
    assert semantic_lane_status(opportunities=400, accepted=0) == STATUS_SUSPECT


def test_missing_instrumentation_is_not_zero():
    """UNOBSERVABLE must never be reported as a correct zero — that
    conflation is how dead lanes hid."""
    assert semantic_lane_status(opportunities=None, accepted=0) \
        == STATUS_UNOBSERVABLE


# ===================================================== CHAOS MATRIX
# Each case is a way an ingestion lane could silently die.

def test_chaos_procedure_compiler_never_invoked():
    """Compiler not called -> artifacts stay 0 while evidence exists."""
    assert semantic_lane_status(opportunities=965, accepted=0) == STATUS_SUSPECT


def test_chaos_concept_compiler_never_invoked():
    assert semantic_lane_status(opportunities=2210, accepted=0) == STATUS_SUSPECT


def test_chaos_accepted_output_not_persisted():
    """Compiler accepts but persistence is disabled: identical
    observable shape to 'never invoked', and both must alert."""
    assert semantic_lane_status(opportunities=100, accepted=0) == STATUS_SUSPECT


def test_chaos_fact_admission_writes_no_decisions():
    """Relation candidates exist, no facts survive -> SUSPECT."""
    assert semantic_lane_status(opportunities=13085, accepted=0) == STATUS_SUSPECT


# ============================================ OPPORTUNITY COUNTERS
# The counters must share the compilers' own helpers, or they will drift
# from what production actually evaluates and the ratio becomes fiction.

def test_procedure_counter_sees_what_the_compiler_sees():
    text = ("Open the console. Click Save to persist the change. "
            "Review the resulting log entry.")
    opportunities = P.count_opportunities(text)
    artifact = P.compile_procedure(document_id="d", corpus_id="c", text=text)
    assert opportunities >= P.MIN_STEPS
    assert artifact is not None
    # the compiler collapses ALL of them into ONE artifact — this is the
    # documented granularity ceiling, pinned so a change is deliberate
    assert len(artifact["steps"]) == opportunities


def test_procedure_counter_reports_zero_on_non_procedural_prose():
    text = ("A SIEM aggregates logs from many sources. It correlates "
            "events so an analyst can reconstruct an attack.")
    assert P.count_opportunities(text) < P.MIN_STEPS
    assert P.compile_procedure(document_id="d", corpus_id="c", text=text) is None


def test_concept_counter_exceeds_the_cap_when_recall_is_truncated():
    """Proves the cap is observable: more definitional sentences than
    the compiler will emit."""
    sentences = [f"Term{i} is a mechanism that controls access."
                 for i in range(25)]
    opportunities = C.count_opportunities(sentences)
    artifacts = C.compile_concepts(document_id="d", corpus_id="c",
                                   sentences=sentences)
    assert opportunities > len(artifacts), (
        "counter must see more than the capped output, otherwise "
        "truncation is invisible")
    assert len(artifacts) <= 10


def test_concept_counter_reports_zero_without_definitional_evidence():
    assert C.count_opportunities(["Click Save.", "Then restart."]) == 0


# ================================================== CALLSITE PIN
def test_callsite_pin_extract_worker_records_lane_attempts():
    """PIN. The vocabulary layer died because nothing tied the producer's
    row shape to its consumer. Here the risk is that a refactor stops
    RECORDING opportunities, which would silently return the lanes to
    output-only counting and re-hide truncation."""
    src = (ROOT / "workers" / "workers" / "extract_worker.py").read_text()
    start = src.index("def _persist_knowledge_artifacts")
    body = src[start:src.index("\ndef ", start + 1)]
    # BOTH lanes must be measured. A weaker "count_opportunities in body"
    # check passed while one call was mutated away, because the other
    # lane still matched — caught by mutation-testing this pin.
    # P3: the procedure lane compiles under PROCEDURE_ARTIFACT_V2, so
    # its counter must be the v2 twin. The counter and the compiler have
    # to share a contract or "accepted" can exceed "opportunities".
    assert "_procedure_mod.count_opportunities_v2(" in body, (
        "extract worker no longer measures PROCEDURE opportunities; "
        "artifact counts alone cannot distinguish a healthy lane from "
        "one discarding 99% of its evidence")
    assert "_concept_mod.count_opportunities(" in body, (
        "extract worker no longer measures CONCEPT opportunities")
    assert "_record_lane_attempt" in body, (
        "extract worker no longer records durable lane dispositions")
    for lane in ('lane="procedure"', 'lane="concept"'):
        assert lane in body, f"{lane} disposition no longer recorded"


@pytest.mark.parametrize("status", [STATUS_LIVE, STATUS_CAPPED,
                                    STATUS_SUSPECT, STATUS_NO_OPPORTUNITY,
                                    STATUS_UNOBSERVABLE])
def test_status_vocabulary_is_stable(status):
    """Operators and dashboards key on these strings."""
    assert isinstance(status, str) and status.isupper()
