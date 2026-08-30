"""VOCABULARY-PRODUCTION-CONTRACT-REGRESSION-V1.

The vocabulary layer silently produced ZERO families in production for
days while `tests/determinism/test_vocabulary_mapping.py` stayed green,
because that suite feeds the PRE-REFACTOR row shape
(`{"payload": {"parent_id": ...}}`) while the summaries worker moved to
a direct DB read keyed `summary_id`. Component tests passed; the
feature was dead.

This suite pins the CURRENT PRODUCTION SHAPE and the support-identity
semantics, so a future assembly refactor fails loudly here instead of
silently emptying the layer. It is the concrete instance of the trap
AGENTS.md records: "Entry-point wiring drift between refactors ...
pin call sites."
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.vocabulary_mapping import (  # noqa: E402
    MissingSupportIdentity,
    build_concept_families,
)

CORPUS = "vocab_contract_v1"


def _prod_row(support_id: str, concepts: list[str], summary_id: str = "sum_x"):
    """EXACTLY the dict the summaries worker assembles (see
    workers/workers/summary_worker_impl.py :: run_vocabulary_stage)."""
    return {"summary_id": summary_id, "support_id": support_id,
            "entities": [], "concepts": concepts, "summary": ""}


def _build(parents, docs=None, accepted=None):
    return build_concept_families(
        corpus_id=CORPUS, parent_summaries=parents,
        document_summaries=docs or [],
        accepted_concepts=accepted if accepted is not None else [])


# ---------------------------------------------------------------- A
def test_a_production_shape_two_independent_parents_admits():
    """The regression case: production-shaped rows must yield families."""
    fams = _build([
        _prod_row("chunk_p1", ["attention mechanism", "multi-head attention"], "sum_1"),
        _prod_row("chunk_p2", ["attention mechanism", "self-attention"], "sum_2"),
    ])["families"]
    assert len(fams) == 1, fams
    assert fams[0]["canonical_name"] == "attention mechanism"
    assert fams[0]["independent_support_count"] == 2
    assert set(fams[0]["supporting_summaries"]) == {"chunk_p1", "chunk_p2"}


# ---------------------------------------------------------------- B
def test_b_single_parent_is_rejected():
    """min_support=2 is a PRECISION guard; one neighbourhood is not
    corroboration. Never lower it to make tables populate."""
    fams = _build([_prod_row("chunk_p1", ["attention mechanism",
                                          "multi-head attention"])])["families"]
    assert fams == []


# ---------------------------------------------------------------- C
def test_c_duplicate_summaries_of_one_parent_cannot_fake_support():
    """MEASURED on cysa-study-v1: 3,016 parent_summaries rows cover only
    1,775 distinct parent_ids — 1,241 parents carry TWO summary rows.
    Keying support on summary_id would clear the >=2 guard from a single
    evidence neighbourhood. Support must stay parent-scoped."""
    fams = _build([
        _prod_row("chunk_p1", ["attention mechanism", "multi-head attention"], "sum_1"),
        _prod_row("chunk_p1", ["attention mechanism", "multi-head attention"], "sum_2"),
    ])["families"]
    assert fams == [], "duplicate summaries of ONE parent faked corroboration"


# ---------------------------------------------------------------- D
def test_d_derived_document_summary_cannot_fake_second_support():
    """A document summary derives FROM parent summaries; counting it as
    independent support would let one parent + its own derivative mint a
    concept."""
    fams = _build(
        [_prod_row("chunk_p1", ["attention mechanism", "multi-head attention"])],
        docs=[{"summary_id": "doc_1",
               "major_concepts": ["attention mechanism"], "major_entities": []}],
    )["families"]
    assert fams == []


# ---------------------------------------------------------------- E
def test_e_two_independent_parents_count_two():
    fams = _build([
        _prod_row("chunk_p1", ["siem"], "sum_1"),
        _prod_row("chunk_p2", ["siem"], "sum_2"),
    ])["families"]
    assert len(fams) == 1
    assert fams[0]["independent_support_count"] == 2


# ---------------------------------------------------------------- F
def test_f_missing_support_identity_fails_loudly():
    """The regression itself: a row with no support identity must RAISE,
    never collapse every concept onto a shared sentinel."""
    broken = {"summary_id": "sum_1", "entities": [],
              "concepts": ["siem"], "summary": ""}  # pre-fix production shape
    with pytest.raises(MissingSupportIdentity):
        _build([broken])


def test_f2_summary_id_is_not_accepted_as_support_identity():
    """Guards the tempting one-line 'fix'. summary_id must NOT satisfy
    the support contract — it is not the evidence neighbourhood."""
    rows = [{"summary_id": "sum_1", "entities": [], "concepts": ["siem"],
             "summary": ""},
            {"summary_id": "sum_2", "entities": [], "concepts": ["siem"],
             "summary": ""}]
    with pytest.raises(MissingSupportIdentity):
        _build(rows)


# ---------------------------------------------------------------- G
def test_g_deterministic_replay():
    parents = [
        _prod_row("chunk_p1", ["siem", "security information and event management"], "s1"),
        _prod_row("chunk_p2", ["siem", "log management"], "s2"),
        _prod_row("chunk_p3", ["edr"], "s3"),
    ]
    a = _build(parents)
    b = _build(parents)
    assert a == b


# ------------------------------------------------------- legacy shape
def test_legacy_payload_shape_still_supported():
    """The pre-refactor artifact shape carries the SAME identity
    (parent_id) and must keep working, so historical fixtures and any
    payload-wrapped caller remain valid."""
    fams = _build([
        {"payload": {"parent_id": "chunk_p1", "concepts": ["siem"]}},
        {"payload": {"parent_id": "chunk_p2", "concepts": ["siem"]}},
    ])["families"]
    assert len(fams) == 1
    assert fams[0]["independent_support_count"] == 2


# ------------------------------------------------------- CALLSITE PIN
def test_callsite_pin_worker_selects_and_maps_support_id():
    """CALLSITE PIN. The defect was invisible because nothing tied the
    worker's DB assembly to the builder's contract. This reads the
    worker source and fails if the SELECT stops providing parent_id or
    the zip() stops naming it support_id -- i.e. if the exact refactor
    that caused the regression happens again."""
    src = (ROOT / "workers" / "workers" / "summary_worker_impl.py").read_text()
    # scope to the vocabulary stage: other stages legitimately read
    # parent_summaries with different projections
    start = src.index("def _do_vocabulary")
    end = src.index("\ndef ", start + 1)
    src = src[start:end]
    select = re.search(
        r"SELECT\s+([^\"]*?)\s+FROM parent_summaries", src, re.S)
    assert select, "summaries worker no longer reads parent_summaries"
    assert "parent_id" in select.group(1), (
        "summaries worker no longer SELECTs parent_id from "
        "parent_summaries — the vocabulary layer loses its support "
        "identity and silently produces zero families. Selected: "
        f"{select.group(1)!r}")
    # the row assembly that feeds build_concept_families must NAME it
    assembly = re.search(
        r"dict\(zip\(\((.*?)\),\s*r\)\)", src, re.S)
    assert assembly and "support_id" in assembly.group(1), (
        "worker row assembly no longer names the support identity "
        "'support_id'; build_concept_families will raise "
        "MissingSupportIdentity. Assembly: "
        f"{assembly.group(1) if assembly else None!r}")
