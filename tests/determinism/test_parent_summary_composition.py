"""SUMMARY-RUNTIME-FIX fixtures: D1/D2/D3 regression proof.

D1 parent_id leak, D2 summary literal leak — both were replay-harness
input-contract violations (dict-key unpacking); runtime verified here
against its DECLARED contract shapes.
D3 concept derivation: v2 predicates compose fact sentences; concept
scan rejects sentence-length over-matches."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))


def _build(children=None, facts=None):
    from polymath_shared.parent_summary import build_parent_summary
    return build_parent_summary(
        parent_id="par_123", parent_text="Real parent text.",
        children=children if children is not None else
        [{"id": "kid_1", "text": "BERT was introduced by Google Research."}],
        facts=facts if facts is not None else
        [{"predicate": "introduced_by",
          "subject_surface": "BERT",
          "object_surface": "Google Research"}],
        entities=[{"surface": "BERT"}, {"surface": "Google Research"}])


def test_d2_fact_sentence_composes_summary_body():
    p = _build()["payload"]
    assert p["summary"] == "BERT was introduced by Google Research.", (
        "admitted facts must compose the summary body")


def test_d3_v2_predicates_have_phrase_mappings():
    from polymath_shared.parent_summary import _REL_PHRASE
    for pred in ("introduced_by", "trained_on", "evaluated_on",
                 "depends_on"):
        assert pred in _REL_PHRASE, f"v2 predicate {pred} unmapped"


def test_d3_concept_scan_rejects_sentence_over_match():
    from polymath_shared.parent_summary import re_finditer_candidates
    got = re_finditer_candidates(
        "Subsequent studies evaluated BERT on GLUE. "
        "Tree of Thoughts is a framework.")
    assert "Subsequent studies evaluated BERT on GLUE" not in got
    assert "BERT" in got and "Tree of Thoughts" in got


def test_d3_concept_scan_punctuation_boundary():
    from polymath_shared.parent_summary import re_finditer_candidates
    got = re_finditer_candidates("Evaluated on GLUE and SQuAD.")
    joined = [g for g in got if "and" in g]
    assert joined == [], "chains must not cross coordination into junk"


def test_lineage_children_ids_flow_to_derived_from():
    env = _build()
    assert env["derived_from"] == ["kid_1"]


def test_empty_facts_falls_back_to_parent_text_head():
    p = _build(facts=[])["payload"]
    assert p["summary"].startswith("Real parent text.")
