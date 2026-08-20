"""PHASE 0: the admission qualification harness must test production code.

Ledger row 37: `qualify_admission.py` imported a frozen local fork and
loaded a superseded gold whose label vocabulary the policy can no longer
emit, reporting 0.773 for a policy that scores 55/55. These tests pin the
repair so the harness cannot silently drift from production again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_admission import POLICY_VERSION, decide

EVAL = ROOT / "eval" / "admission"
POLICY_LABELS = {"GLOBAL", "CORPUS_SCOPED", "DOCUMENT_SCOPED", "MENTION_ONLY"}


def _harness_sources():
    return [(p, p.read_text()) for p in
            (EVAL / "qualify_admission.py", EVAL / "downstream_g4.py")]


def test_harnesses_import_production_admission_not_the_fork():
    for path, src in _harness_sources():
        assert "from polymath_shared.entity_admission import" in src, path.name
        assert "\nfrom entity_admission import" not in src, (
            f"{path.name} imports the historical fork")


def test_historical_fork_is_labelled_do_not_import():
    src = (EVAL / "entity_admission.py").read_text()
    assert "HISTORICAL SNAPSHOT" in src and "DO NOT IMPORT" in src


def test_default_gold_matches_the_policy_label_vocabulary():
    gold = json.loads((EVAL / "admission_gold_v1.1.json").read_text())["items"]
    assert {i["label"] for i in gold} <= POLICY_LABELS


def test_production_policy_scores_55_of_55_on_its_gold():
    gold = json.loads((EVAL / "admission_gold_v1.1.json").read_text())["items"]
    wrong = [(i["surface"], i["label"],
              decide(i["surface"], i["core_type"], 0.5).reference_class)
             for i in gold
             if decide(i["surface"], i["core_type"], 0.5).reference_class != i["label"]]
    assert not wrong, f"{POLICY_VERSION} regressions: {wrong}"
    assert len(gold) == 55


def test_superseded_gold_is_rejected_not_scored():
    """The v1 gold uses the umbrella label SCOPED, which the policy cannot
    emit. Scoring against it silently produces a wrong number."""
    gold = json.loads((EVAL / "admission_gold.json").read_text())["items"]
    assert {i["label"] for i in gold} - POLICY_LABELS == {"SCOPED"}
    assert "Refusing to report a misleading accuracy" in (
        EVAL / "qualify_admission.py").read_text()


def test_harness_does_not_overwrite_committed_artifacts_by_default():
    src = (EVAL / "qualify_admission.py").read_text()
    assert "POLYMATH_WRITE_ARTIFACTS" in src
