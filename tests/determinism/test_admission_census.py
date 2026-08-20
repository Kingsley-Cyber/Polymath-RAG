"""ADMISSION CENSUS REGRESSION.

    A fact-level P/R metric cannot certify the entity-admission layer.

Row 53 is the proof: a defect that parked 42 of 55 graph-eligible identities
left the I4 fact score unmoved at P=.750, because that score compares
endpoint surfaces and never asks how many identities exist or of what kind.
Every admission unit test stayed green as well — each rule was individually
correct and the composition was wrong.
"""
import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify_census", pathlib.Path("eval/census/verify_census.py"))
VC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VC)


def _census(eligible, anchors, facts=11):
    return {"corpus": "c",
            "totals": {"mentions": 82, "graph_eligible": eligible,
                       "distinct_entities": 40, "canonical_entities": 23,
                       "canonical_facts": facts},
            "per_document": {"doc.md": {"mentions": 82, "graph_eligible": eligible,
                                        "anchor_kinds": anchors}}}


HEALTHY = _census(53, {"IDENTITY": 46, "LOCAL_REFERENCE": 21, "GENERIC": 5,
                       "UNKNOWN": 10})
ROW_53 = _census(13, {"IDENTITY": 10, "LOCAL_REFERENCE": 34, "GENERIC": 6,
                      "UNKNOWN": 31}, facts=1)


def test_the_census_catches_the_row_53_collapse():
    """The exact regression that shipped: eligible 53 -> 13, IDENTITY 46 -> 10."""
    diffs = VC.compare(HEALTHY, ROW_53)
    assert diffs, "the census failed to notice a 40-identity collapse"
    joined = " ".join(diffs)
    assert "graph_eligible" in joined and "anchor_kinds" in joined


def test_an_unchanged_census_is_silent():
    assert VC.compare(HEALTHY, HEALTHY) == []


def test_no_tolerance_band():
    """A census that drifts quietly certifies nothing, so even one identity
    moving is reported."""
    off_by_one = _census(52, HEALTHY["per_document"]["doc.md"]["anchor_kinds"])
    assert VC.compare(HEALTHY, off_by_one)


def test_a_missing_document_is_a_divergence():
    gone = {"corpus": "c", "totals": HEALTHY["totals"], "per_document": {}}
    assert any("missing" in d for d in VC.compare(HEALTHY, gone))


def test_an_unexpected_document_is_a_divergence():
    extra = _census(53, HEALTHY["per_document"]["doc.md"]["anchor_kinds"])
    extra["per_document"]["new.md"] = extra["per_document"]["doc.md"]
    assert any("unexpected" in d for d in VC.compare(HEALTHY, extra))


def test_the_frozen_i4_census_exists_and_records_admission_shape():
    import json

    path = pathlib.Path("eval/census/census_i4-fresh-acceptance-v1.json")
    assert path.exists(), "the i4 census must be frozen for the tripwire to fire"
    frozen = json.loads(path.read_text())
    for key in ("mentions", "graph_eligible", "distinct_entities",
                "canonical_entities", "canonical_facts"):
        assert key in frozen["totals"], f"census omits {key}"
    assert frozen["per_document"], "census records no per-document shape"
    assert all("anchor_kinds" in d for d in frozen["per_document"].values())
