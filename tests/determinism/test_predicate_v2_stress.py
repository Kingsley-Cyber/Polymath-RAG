"""PREDICATE-COMPILER-V2 frozen stress suite (owner decision record).

Seven categories. Fixtures are frozen bytes; the sha256 lock below
makes mutation loud. Expectations are the owner's, verbatim:
  1 similarity contamination -> similar_to = 0
  2 acquisition -> PASS Microsoft acquired Activision
  3 modality    -> T1 candidate, never T2
  4 negation    -> REJECT
  5 passive     -> Microsoft acquired Activision (direction verified)
  6 pronoun     -> REJECT SUBJECT_NOT_DURABLE at F3
  7 cross sentence -> no binding across slices
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "eval" / "v5" / "stress" / "predicate_v2"))

FIXTURES = ROOT / "eval/v5/stress/predicate_v2/fixtures.json"
FROZEN_SHA256 = "e1cc95aa9f7f22d2412c085bfae08e1d683008bf0292d8f3bdf6a02fce550811"

from run_stress import _load, run_case  # noqa: E402


def _frozen_fixtures():
    data = _load()
    digest = hashlib.sha256(FIXTURES.read_bytes()).hexdigest()
    if FROZEN_SHA256 != "REPLACED_AT_FREEZE":
        assert digest == FROZEN_SHA256, (
            f"frozen stress fixtures mutated: {digest} != {FROZEN_SHA256}")
    return {case["id"]: case for case in data["cases"]}


def _surfaces(cand):
    return (cand.subject.span.text, cand.object.span.text)


def test_cat1_similarity_contamination():
    r = run_case(_frozen_fixtures()["cat1_similarity_contamination"])
    similar = [c for c in r["candidates"]
               if c.evidence.trigger_predicate_id == "similar_to"]
    assert similar == []
    assert all(d.fact is None for _, d in r["decisions"])
    assert r["admission_rows"] == []


def test_cat2_acquisition_passes_and_asserts():
    r = run_case(_frozen_fixtures()["cat2_acquisition_pass"])
    accepted = [(c, d) for c, d in r["decisions"]
                if d.decision == "ACCEPT"]
    assert len(accepted) == 1
    c, d = accepted[0]
    assert d.fact.predicate == "acquired"
    assert _surfaces(c) == ("Microsoft", "Activision")
    assert d.fact.subject_id == c.subject.resolved_entity_id
    outcomes = [row[4] for row in r["admission_rows"]]
    assert outcomes == ["PASS"]


def test_cat3_modality_is_t1_never_t2():
    r = run_case(_frozen_fixtures()["cat3_modality_t1_not_t2"])
    facts = [d.fact for _, d in r["decisions"] if d.fact is not None]
    assert len(facts) == 1
    assert facts[0].decision == "QUALIFY"
    assert not any(d.decision == "ACCEPT" for _, d in r["decisions"])
    outcomes = [row[4] for row in r["admission_rows"]]
    assert "PASS" not in outcomes


def test_cat4_negation_rejects():
    r = run_case(_frozen_fixtures()["cat4_negation_reject"])
    assert all(d.fact is None for _, d in r["decisions"])
    assert any(d.decision == "REJECT" and "negated" in str(d.reason)
               for _, d in r["decisions"])


def test_cat5_passive_orients_agent_first():
    r = run_case(_frozen_fixtures()["cat5_passive_direction"])
    accepted = [(c, d) for c, d in r["decisions"]
                if d.decision == "ACCEPT"]
    assert len(accepted) == 1
    c, d = accepted[0]
    assert d.fact.predicate == "acquired"
    id_to_surface = {
        c.subject.resolved_entity_id: c.subject.span.text,
        c.object.resolved_entity_id: c.object.span.text,
    }
    assert (id_to_surface[d.fact.subject_id],
            id_to_surface[d.fact.object_id]) == ("Microsoft", "Activision")
    assert d.fact.provenance.get("orientation") in (
        "role_canonical_passive", "passive_inverted", "role_canonical")


def test_cat6_pronoun_endpoint_refused_at_f3():
    r = run_case(_frozen_fixtures()["cat6_pronoun_endpoint"])
    assert r["admission_rows"], "F-chain must run on the compiled fact"
    rows = [row for row in r["admission_rows"] if row[4] == "REJECT"]
    assert rows, "pronoun endpoint fact must be refused under enforcement"
    gates = {row[5] for row in rows}
    reasons = {row[6] for row in rows}
    assert gates == {"F3_ENDPOINTS"}
    assert any("SUBJ_NOT_DURABLE" in reason for reason in reasons)
    assert r["withheld"] >= 1


def test_cat7_no_cross_sentence_binding():
    r = run_case(_frozen_fixtures()["cat7_cross_sentence_isolation"])
    pairs = {_surfaces(c) for c, d in r["decisions"]}
    cross = {pair for pair in pairs
             if set(pair) & {"Google", "innovation"}
             and set(pair) & {"Microsoft", "Activision"}}
    assert not cross
    similar = [c for c in r["candidates"]
               if c.evidence.trigger_predicate_id == "similar_to"]
    assert similar == []


def test_fixture_hash_lock_is_recorded():
    """Freeze audit: fixtures are frozen bytes; any mutation fails here
    before a single expectation runs."""
    digest = hashlib.sha256(FIXTURES.read_bytes()).hexdigest()
    assert digest == FROZEN_SHA256
