"""SCIENTIFIC-KAG-V1 phase 6b: event candidate generation + admission.

Static relationships never become events; scientific actions with a
temporal anchor (or multiple participant roles) promote.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.event_reification import (  # noqa: E402
    admit_event,
    event_candidate,
)


def _cand(predicate, subj="BERT", obj="GLUE", date=None,
          subject_surface=None, object_surface=None):
    qualifiers = {}
    if date:
        qualifiers["temporal_surface"] = date
        qualifiers["valid_from"] = "2023-03"
    return event_candidate(predicate, "ent_s", "ent_o", qualifiers,
                           subject_surface=subject_surface or subj,
                           object_surface=object_surface or obj)


def test_static_relationships_never_become_events():
    assert event_candidate("uses", "a", "b", {}) is None
    assert event_candidate("is_a", "a", "b", {}) is None
    assert event_candidate("part_of", "a", "b", {}) is None


def test_scientific_actions_generate_candidates():
    for predicate in ("trained_on", "evaluated_on", "released_on",
                      "occurred_at", "proposed"):
        c = _cand(predicate)
        assert c is not None and c["event_type"].endswith("_event")


def test_temporal_anchor_promotes():
    ok, reason = admit_event(_cand("evaluated_on", date="March 2023"))
    assert ok and reason == "R1_temporal_anchor"


def test_agent_and_artifact_promote_release_event():
    c = event_candidate("released_on", "ent_o", "ent_g",
                        {}, subject_surface="GPT-4",
                        object_surface="March 2023",
                        agent_surface="OpenAI")
    ok, reason = admit_event(c)
    assert ok and reason == "R2_multiple_participants"
    assert c["event_type"] == "release_event"


def test_bare_pair_without_time_abstains():
    ok, reason = admit_event(_cand("trained_on"))
    assert not ok and reason == "no_temporal_anchor_and_single_role"
