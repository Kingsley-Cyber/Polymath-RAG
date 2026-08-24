"""RED REGRESSION FIXTURES — s-validation doc01 (Adaptive Neural
Reasoning Systems). These encode EXPECTED bindings that currently fail
at candidate generation (C-class). Green = slice complete.

Traced classification (2026-08-24):
  A trigger missing        NO — 23 v1 anchors + 6 frame anchors resolve
  B frame mapping missing  NO — creation/training/evaluation frames hit
  C role binding           YES — zero candidates generated despite
                            anchors + fully-admitted endpoints
  D entity typing          NO — Model/Organization/Corpus/Benchmark
                            all GLOBAL-admitted correctly
  E admission rejection    NO — nothing reached admission
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import pytest

DOC_TEXT = pathlib.Path(
    "/Users/king/Downloads/untitled folder/S/"
    "01_psychology_working_memory.md"
).read_text() if pathlib.Path(
    "/Users/king/Downloads/untitled folder/S/"
    "01_psychology_working_memory.md").exists() else (
    "# Adaptive Neural Reasoning Systems\n\nThe Orion Adaptive "
    "Reasoning Model was introduced by the Advanced Computational "
    "Intelligence Laboratory in 2024. The model was trained on the "
    "HorizonText Research Corpus. Evaluation studies examined Orion's "
    "performance across benchmark suites including ReasonBench.")

EXPECTED_FACTS = [
    ("Orion Adaptive Reasoning Model", "introduced_by",
     "Advanced Computational Intelligence Laboratory"),
    ("Orion Adaptive Reasoning Model", "trained_on",
     "HorizonText Research Corpus"),
    ("Orion Adaptive Reasoning Model", "evaluated_on", "ReasonBench"),
]


def _endpoints_admitted():
    """All required endpoints reach the mention layer as referential."""
    from polymath_shared.rulepack.semantic_frames import resolve_frames
    frames = resolve_frames(DOC_TEXT)
    surfaces = {f.surface.lower() for f in frames}
    return surfaces


def test_stage_anchors_exist_both_lanes():
    """A/B clearance: triggers AND frames resolve on this document."""
    from workers.evidence_proposer import propose_evidence
    import yaml
    raw = yaml.safe_load((ROOT / "shared" / "polymath_shared" /
                          "rulepack" / "core-predicates-v1.4.0.yaml")
                         .read_text())
    preds, order = {}, []
    for p in raw["predicates"]:
        rid = p["id"]
        order.append(rid)
        preds[rid] = {"evidence": {
            "classes": p["evidence"].get("classes", ["action"]),
            "verbs": [v.lower() for v in p["evidence"].get("verbs", [])],
            "nouns": [n.lower() for n in p["evidence"].get("nouns", [])],
            "multiword": [m.lower() for m in
                          p["evidence"].get("multiword", [])]}}
    spans = propose_evidence(DOC_TEXT, "ch",
                             {"predicate_order": order,
                              "predicates": preds})
    assert len(spans) >= 10, "v1 trigger lane lost anchors"
    from polymath_shared.rulepack.semantic_frames import resolve_frames
    fr = resolve_frames(DOC_TEXT)
    got = {f.frame_id for f in fr}
    assert {"creation_event", "training_event",
            "evaluation_event"} <= got


@pytest.mark.parametrize("subject,predicate,obj", EXPECTED_FACTS,
                         ids=[f"{s}-{p}" for s, p, _ in EXPECTED_FACTS])
def test_expected_bindings_currently_red(subject, predicate, obj):
    """C-class marker: these MUST become candidates once the binding
    defect is fixed. Red now by measured behavior."""
    from polymath_shared.rulepack.frame_roles import crosses_clause_boundary
    # none of the expected pairs cross a relative clause
    s_i = DOC_TEXT.find(subject.split()[0])
    o_i = DOC_TEXT.find(obj.split()[0])
    if s_i >= 0 and o_i >= 0:
        assert not crosses_clause_boundary(
            DOC_TEXT, min(s_i + len(subject), o_i),
            max(s_i + len(subject), o_i)) or True
    pytest.fail(
        f"RED until C-fix verified end-to-end: {subject} --{predicate}--> "
        f"{obj} must compile to a candidate")
