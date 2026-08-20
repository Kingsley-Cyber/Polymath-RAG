"""ADR-0016 Phase 5: observability realignment.

Qualification criterion #14 requires that observability explain every
terminal outcome. These tests pin the vocabulary the kimi_v1 lane emits,
the step/terminal split that keeps the first-loss funnel honest, and the
mapping between BindingSource mechanisms and directive Phase 17
discipline tiers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import BindingSource
from polymath_shared.observability import (
    ALL_CODES,
    BINDING_DISCIPLINE,
    ROLE,
    STEP_CODES,
    SUMMARY_EVENT_TYPES,
    TYPE_PRECHECK,
    UD_BINDING,
    TraceCollector,
    binding_discipline,
)
from workers.extract_worker import _EVENT_TYPE_BY_STAGE, _STAGE_BY_CODE

# Every code the kimi_v1 lane can emit, gathered from the emission sites
# in workers/kimi_candidates.py.
KIMI_EMITTED = {
    "UD_SUBJECT_BOUND", "UD_OBJECT_BOUND", "UD_OBLIQUE_BOUND",
    "UD_NO_ARGUMENT_IN_SLOT",
    "TYPE_PRECHECK_PASS", "TYPE_PRECHECK_FAIL",
    "TYPE_PRECHECK_NO_VIABLE_PAIR",
    "ROLE_ARG0_ASSIGNED", "ROLE_ARG1_ASSIGNED", "ROLE_ARG2_ASSIGNED",
    "ROLE_ASSIGNED", "ROLE_NO_ROLESET", "ROLE_ORIENTATION_INCOMPLETE",
    "CANDIDATE_CREATED",
    "SUBJECT_ENDPOINT_UNAVAILABLE", "OBJECT_ENDPOINT_UNAVAILABLE",
}


def test_every_emitted_kimi_code_is_registered():
    unregistered = KIMI_EMITTED - ALL_CODES
    assert not unregistered, f"emitted but not in ALL_CODES: {sorted(unregistered)}"


def test_every_emitted_kimi_code_has_an_owning_stage():
    unmapped = {c for c in KIMI_EMITTED if c not in _STAGE_BY_CODE}
    assert not unmapped, f"no owning stage: {sorted(unmapped)}"


def test_plan_phase5_codes_all_exist():
    """The eight codes the implementation plan names verbatim."""
    for code in ("UD_SUBJECT_BOUND", "UD_OBJECT_BOUND", "UD_OBLIQUE_BOUND",
                 "UD_NO_ARGUMENT_IN_SLOT", "ROLE_ARG0_ASSIGNED",
                 "ROLE_ARG1_ASSIGNED", "TYPE_PRECHECK_PASS",
                 "TYPE_PRECHECK_FAIL"):
        assert code in ALL_CODES, code


def test_step_codes_are_never_terminal_losses():
    """A bound subject or one rejected pair is not a reason a fact died."""
    assert STEP_CODES == (UD_BINDING | ROLE | TYPE_PRECHECK) - {
        "TYPE_PRECHECK_NO_VIABLE_PAIR"}
    # the code that DOES end a trigger's life stays terminal
    assert "TYPE_PRECHECK_NO_VIABLE_PAIR" not in STEP_CODES
    assert "SUBJECT_ENDPOINT_UNAVAILABLE" not in STEP_CODES


def test_step_events_are_excluded_from_summary_mode():
    """Summary mode keeps terminal decisions only; step events are full-only."""
    for stage, event_type in _EVENT_TYPE_BY_STAGE.items():
        assert event_type not in SUMMARY_EVENT_TYPES, (stage, event_type)


def test_binding_discipline_covers_every_binding_source():
    for source in BindingSource:
        assert source.value in BINDING_DISCIPLINE, source
        assert binding_discipline(source) in (
            "UD_PRIMARY", "SAFE_FALLBACK", "BOUNDED_RECALL")


def test_binding_discipline_tiers_are_correct():
    assert binding_discipline(BindingSource.UD_DIRECT) == "UD_PRIMARY"
    assert binding_discipline(BindingSource.UD_PASSIVE) == "UD_PRIMARY"
    assert binding_discipline(BindingSource.SAFE_LOCAL_PATTERN) == "SAFE_FALLBACK"
    assert binding_discipline(
        BindingSource.BOUNDED_LINEAR_RECALL) == "BOUNDED_RECALL"
    # bare strings resolve identically to their enum members
    assert binding_discipline("UD_DIRECT") == "UD_PRIMARY"
    # an unknown source never claims stronger provenance than it can prove
    assert binding_discipline("SOMETHING_NEW") == "BOUNDED_RECALL"


def test_retained_alias_still_validates_historical_traces():
    """TYPE_PRECHECK_IMPOSSIBLE is no longer emitted but stays registered."""
    assert "TYPE_PRECHECK_IMPOSSIBLE" in ALL_CODES


class _Row(dict):
    pass


class _Evidence:
    text = "founded"
    start = 10
    end = 17
    evidence_class = "founding"
    trigger_lemma = "found"
    trigger_predicate_id = "found.01"


def _observer(mode="full"):
    from workers.extract_worker import _SliceObserver
    collector = TraceCollector(mode, "run_test", {"rule_pack_version": "1.3.0"})
    row = _Row(doc_id="doc1", chunk_id="chunk1")
    return _SliceObserver(collector, row, None, "chunk1:0"), collector


def test_step_events_do_not_enter_the_loss_list():
    obs, collector = _observer()
    ev = _Evidence()
    for code in ("UD_SUBJECT_BOUND", "ROLE_ARG0_ASSIGNED", "TYPE_PRECHECK_PASS",
                 "UD_NO_ARGUMENT_IN_SLOT", "TYPE_PRECHECK_FAIL"):
        obs.record_candidate_outcome(None, ev, code, {})
    assert obs.losses == []
    assert collector.funnel()["first_loss"] == {}

    obs.record_candidate_outcome(None, ev, "TYPE_PRECHECK_NO_VIABLE_PAIR", {})
    assert obs.losses == ["TYPE_PRECHECK_NO_VIABLE_PAIR"]
    assert collector.funnel()["first_loss"] == {"type_precheck": 1}


def test_binding_discipline_is_attached_to_every_binding_event():
    obs, collector = _observer()
    obs.record_candidate_outcome(
        None, _Evidence(), "UD_SUBJECT_BOUND",
        {"binding_source": BindingSource.UD_DIRECT})
    detail = collector.events[0]["detail"]
    assert detail["binding_discipline"] == "UD_PRIMARY"


def test_off_mode_records_no_step_events():
    obs, collector = _observer("off")
    obs.record_candidate_outcome(None, _Evidence(), "UD_SUBJECT_BOUND", {})
    assert collector.events == []
    assert obs.losses == []


def _trace_codes(syntax, ents, evs, text, parse):
    """Drive the real kimi_v1 candidate path and collect emitted events."""
    import test_kimi_role_direction as R

    class _Obs:
        def __init__(self): self.outcomes = []
        def record_candidate_outcome(self, sl, ev, code, detail=None):
            self.outcomes.append((code, detail or {}))

    obs = _Obs()
    R.build_candidates_kimi(
        [R._slice(ents, evs, text, syntax=syntax, parse=parse)],
        doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=R.PACK, observer=obs)
    return obs.outcomes


def _role_paths(outcomes):
    return {d["role"]: d["syntactic_path"]
            for c, d in outcomes if c.startswith("ROLE_ARG")}


def test_active_voice_role_paths_name_their_real_dependency():
    import test_kimi_role_direction as R
    outcomes = _trace_codes(
        R._active_syntax(),
        [R._ent("John", 0, 4, "Person"), R._ent("Acme", 13, 17, "Organization")],
        [R._ev("founded", 5, 12)], "John founded Acme.", {"voice": "active"})
    assert _role_paths(outcomes) == {"ARG0": "nsubj", "ARG1": "dobj"}


def test_passive_voice_role_paths_are_not_mislabelled_by_role_order():
    """Regression: under passive, ARG0 comes from the by-agent and ARG1
    from the surface subject. Deriving the path from the role label alone
    silently mislabels every passive."""
    import test_kimi_role_direction as R
    outcomes = _trace_codes(
        R._passive_syntax(),
        [R._ent("Acme", 0, 4, "Organization"), R._ent("John", 21, 25, "Person")],
        [R._ev("founded", 9, 16)], "Acme was founded by John.",
        {"voice": "passive"})
    assert _role_paths(outcomes) == {"ARG0": "agent", "ARG1": "nsubj:pass"}


def test_ud_bound_events_carry_the_spans_they_bound():
    import test_kimi_role_direction as R
    outcomes = _trace_codes(
        R._passive_syntax(),
        [R._ent("Acme", 0, 4, "Organization"), R._ent("John", 21, 25, "Person")],
        [R._ev("founded", 9, 16)], "Acme was founded by John.",
        {"voice": "passive"})
    by_code = {c: d for c, d in outcomes}
    assert by_code["UD_SUBJECT_BOUND"]["spans"] == ["Acme"]
    assert by_code["UD_OBJECT_BOUND"]["spans"] == ["John"]
    assert by_code["UD_OBLIQUE_BOUND"]["spans"] == ["John"]


def test_envelope_distinguishes_extraction_arms():
    """Regression: legacy_v1 and kimi_v1 runs of the same corpus at the same
    rule pack once produced byte-identical envelopes, so the second arm's
    events collided on trace_event_id and were dropped by ON CONFLICT DO
    NOTHING — an A/B read as if one arm emitted nothing."""
    import os
    from polymath_shared.observability import extraction_contracts

    prev = os.environ.get("POLYMATH_RELATION_PIPELINE")
    try:
        os.environ["POLYMATH_RELATION_PIPELINE"] = "legacy_v1"
        legacy = extraction_contracts()
        os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
        kimi = extraction_contracts()
    finally:
        if prev is None:
            os.environ.pop("POLYMATH_RELATION_PIPELINE", None)
        else:
            os.environ["POLYMATH_RELATION_PIPELINE"] = prev

    assert legacy["relation_pipeline"] == "legacy_v1"
    assert kimi["relation_pipeline"] == "kimi_v1"
    assert legacy != kimi

    from polymath_shared.observability import TraceEvent
    base = {"event_type": "fact", "decision": "FACT_ACCEPTED",
            "reason_code": "FACT_ACCEPTED", "surface": "s", "detail": {"f": 1}}
    assert (TraceEvent(**base).envelope(legacy)["trace_event_id"]
            != TraceEvent(**base).envelope(kimi)["trace_event_id"])
