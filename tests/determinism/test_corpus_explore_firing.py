"""CORPUS-EXPLORE-FIRING-V1 — miss attribution (pure). Every non-firing request carries exactly ONE cause
code (the first closed gate, pipeline order); a firing request carries none. Also pins the additive diag
fields the classifier reads (`bridge_compiler.json_status`, `activate_corpus(diag=)`), and that they do not
change any returned value."""
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import corpus_explore_firing as F  # noqa: E402
from polymath_shared.bridge_compiler import (  # noqa: E402
    BridgeCompilerInput, Concept, _loads, _loads_status, compile_bridges)
from polymath_shared.corpus_activation import activate_corpus  # noqa: E402
from polymath_shared.evidence_packet import build_evidence_packet  # noqa: E402

#: a state that FIRES — every gate open. Each case below closes exactly one gate.
FIRES = F.FiringState(capability_on=True, requested=True, n_hits=12, n_candidates=8, intent="SYNTHESIS",
                      eligible=True, eligible_reason="eligible", json_status="ok", generated=4, admitted=4,
                      added=4)

CASES = [
    (dict(capability_on=False), F.CAPABILITY_OFF),
    (dict(requested=False), F.REQUEST_OFF),
    (dict(plan_present=False), F.OTHER),
    (dict(plan_fallback=True, fallback_reason="transport:timeout"), F.PLAN_FALLBACK),
    (dict(has_primary=False), F.OTHER),
    (dict(upstream_error="KeyError"), F.OTHER),
    (dict(no_corpus=True), F.OTHER),
    (dict(stage="embed", atoms_error="ReadTimeout", n_hits=None, n_candidates=None), F.ATOMS_ERROR_OR_TIMEOUT),
    (dict(n_hits=0, n_candidates=0, fetch_errors=1), F.ATOMS_ERROR_OR_TIMEOUT),
    (dict(n_hits=0, n_candidates=0, atom_universe=0), F.NO_ATOM_COVERAGE),
    (dict(n_hits=0, n_candidates=0, atom_universe=5000), F.ATOMS_EMPTY),
    (dict(n_hits=0, n_candidates=0, atom_universe=None), F.ATOMS_EMPTY),
    (dict(n_hits=12, n_candidates=0), F.CANDIDATES_FILTERED),
    (dict(eligible=False, eligible_reason="intent_not_latent", intent="DEFINITION"), F.INTENT_INELIGIBLE),
    (dict(eligible=False, eligible_reason="no_nominated_concepts"), F.CANDIDATES_FILTERED),
    (dict(eligible=False, eligible_reason="no_primary"), F.OTHER),
    (dict(generate_error="ReadTimeout", generated=0, admitted=0, added=0), F.BRIDGE_COMPILE_EMPTY),
    (dict(json_status="invalid_json", generated=0, admitted=0, added=0), F.BRIDGE_JSON_INVALID),
    (dict(json_status="empty_output", generated=0, admitted=0, added=0), F.BRIDGE_COMPILE_EMPTY),
    (dict(json_status="ok", generated=0, admitted=0, added=0), F.BRIDGE_COMPILE_EMPTY),
    (dict(generated=3, admitted=0, added=0), F.SUBQUERY_DROPPED),
    (dict(generated=3, admitted=2, added=0), F.SUBQUERY_DROPPED),
    (dict(retrieval_skipped=True), F.OTHER),
    (dict(n_hits=None, n_candidates=None, explorer_error="ImportError"), F.OTHER),
]


def test_open_gates_fire_with_no_cause():
    assert F.classify(FIRES) == (True, None, None)
    r = F.firing_receipt(FIRES)
    assert r["fired"] is True and r["cause"] is None and r["contract"] == F.CONTRACT
    assert r["stages"]["added"] == 4 and r["stages"]["intent"] == "SYNTHESIS"


def test_every_closed_gate_yields_exactly_one_known_cause():
    for overrides, want in CASES:
        fired, cause, _detail = F.classify(replace(FIRES, **overrides))
        assert fired is False, overrides
        assert cause == want, (overrides, cause)
        assert cause in F.CAUSES


def test_every_cause_code_is_reachable():
    assert {want for _o, want in CASES} == set(F.CAUSES)


def test_first_closed_gate_wins_in_pipeline_order():
    # capability beats everything; a fallback plan beats an intent problem; atoms beat the bridge model.
    s = replace(FIRES, capability_on=False, requested=False, plan_fallback=True)
    assert F.classify(s)[1] == F.CAPABILITY_OFF
    s = replace(FIRES, plan_fallback=True, eligible=False, eligible_reason="intent_not_latent")
    assert F.classify(s)[1] == F.PLAN_FALLBACK
    s = replace(FIRES, n_hits=0, n_candidates=0, json_status="invalid_json", generated=0, added=0)
    assert F.classify(s)[1] == F.ATOMS_EMPTY


def test_detail_carries_the_evidence():
    assert F.classify(replace(FIRES, plan_fallback=True, fallback_reason="transport:429"))[2] == "transport:429"
    assert F.classify(replace(FIRES, eligible=False, eligible_reason="intent_not_latent",
                              intent="DEFINITION"))[2] == "intent:DEFINITION"
    assert F.classify(replace(FIRES, upstream_error="KeyError"))[2] == "finish_error:KeyError"
    assert F.classify(replace(FIRES, stage="search", atoms_error="ResponseHandlingException", n_hits=None)
                      )[2] == "search:ResponseHandlingException"


def test_turn_receipt_no_plan_and_not_applied_and_skipped():
    no_plan = F.turn_receipt(None, capability_on=True, requested=True, compiler_applied=False,
                             retrieval_skipped=False, compiler_flag="off")
    assert no_plan["fired"] is False and no_plan["cause"] == F.OTHER and "no_plan" in no_plan["detail"]
    off = F.turn_receipt(None, capability_on=True, requested=False, compiler_applied=True,
                         retrieval_skipped=False)
    assert off["cause"] == F.REQUEST_OFF
    fired = F.firing_receipt(FIRES)
    shadow = F.turn_receipt(fired, capability_on=True, requested=True, compiler_applied=False,
                            retrieval_skipped=False, compiler_flag="shadow")
    assert shadow["fired"] is False and shadow["detail"] == "compiler_not_applied:shadow"
    skipped = F.turn_receipt(fired, capability_on=True, requested=True, compiler_applied=True,
                             retrieval_skipped=True)
    assert skipped["fired"] is False and skipped["detail"] == "retrieval_skipped"
    ok = F.turn_receipt(fired, capability_on=True, requested=True, compiler_applied=True,
                        retrieval_skipped=False)
    assert ok["fired"] is True and ok["cause"] is None
    assert fired["fired"] is True                       # input receipt not mutated
    # a plan-level miss keeps its cause at turn level
    miss = F.firing_receipt(replace(FIRES, plan_fallback=True))
    assert F.turn_receipt(miss, capability_on=True, requested=True, compiler_applied=True,
                          retrieval_skipped=True)["cause"] == F.PLAN_FALLBACK


def test_summarize_cause_table():
    rows = [F.firing_receipt(FIRES), F.firing_receipt(FIRES),
            F.firing_receipt(replace(FIRES, plan_fallback=True)),
            F.firing_receipt(replace(FIRES, eligible=False, eligible_reason="intent_not_latent")),
            F.firing_receipt(replace(FIRES, plan_fallback=True)),
            F.firing_receipt(replace(FIRES, requested=False))]          # un-requested: excluded
    s = F.summarize(rows)
    assert s["n"] == 5 and s["fired"] == 2 and s["firing_rate"] == 0.4
    assert s["causes"] == {F.PLAN_FALLBACK: 2, F.INTENT_INELIGIBLE: 1}


def test_record_only_requested_and_never_raises(tmp_path, monkeypatch):
    path = tmp_path / "firing.jsonl"
    monkeypatch.setenv("POLYMATH_CE_FIRING_RECEIPT", str(path))
    F.record(F.firing_receipt(replace(FIRES, requested=False)), q0="x")
    assert not path.exists()
    F.record(F.firing_receipt(replace(FIRES, plan_fallback=True, fallback_reason="t")), q0="hello")
    row = json.loads(path.read_text().strip())
    assert row["cause"] == F.PLAN_FALLBACK and row["fired"] is False and "hello" not in json.dumps(row)
    monkeypatch.setenv("POLYMATH_CE_FIRING_RECEIPT", str(tmp_path / "no" / "such" / "dir" / "f.jsonl"))
    F.record(F.firing_receipt(FIRES), q0="x")            # unwritable path: swallowed


# ---- the additive diag fields the classifier reads -------------------------------------------------

def test_loads_status_distinguishes_declined_empty_and_garbage():
    assert _loads_status("[]") == ([], "ok")                                   # the model declined
    assert _loads_status("") == ([], "empty_output")
    assert _loads_status("   ") == ([], "empty_output")
    assert _loads_status("sorry, I cannot") == ([], "invalid_json")
    assert _loads_status('[{"a": 1') == ([], "invalid_json")
    data, st = _loads_status('```json\n[{"bridge_query": "q"}]\n```')
    assert st == "ok" and data == [{"bridge_query": "q"}]
    for raw in ("[]", "", "garbage", '[{"a":1}]', [{"a": 1}], {"bridges": [{"a": 1}]}):
        assert _loads(raw) == _loads_status(raw)[0]                            # _loads unchanged


def test_compile_bridges_diag_carries_json_status_and_error():
    inp = BridgeCompilerInput(q0="how does a smile read as fake", intent="SYNTHESIS",
                              concepts=[Concept(key="duchenne", label="Duchenne smile", source="d1")],
                              existing_subqueries=[], graph_relations=[])
    _b, d = compile_bridges(inp, generate=lambda _p: "not json at all")
    assert d["json_status"] == "invalid_json" and d["generated"] == 0
    _b, d = compile_bridges(inp, generate=lambda _p: "[]")
    assert d["json_status"] == "ok" and d["generated"] == 0

    def boom(_p):
        raise TimeoutError("x")
    _b, d = compile_bridges(inp, generate=boom)
    assert d["error"] == "TimeoutError" and d["generated"] == 0


def test_activate_corpus_diag_counts_swallowed_fetch_errors_without_changing_output():
    rows = [{"doc_id": "d1", "atom_kind": "CONCEPT", "text": "Duchenne smile", "atom_id": "a1", "score": 0.9}]

    def fetch(cid):
        if cid == "bad":
            raise ConnectionError("qdrant down")
        return rows

    diag: dict = {}
    with_diag = activate_corpus(corpus_ids=["ok", "bad"], fetch_atoms=fetch, diag=diag)
    without = activate_corpus(corpus_ids=["ok", "bad"], fetch_atoms=fetch)
    assert [c.to_dict() for c in with_diag] == [c.to_dict() for c in without]
    assert diag == {"n_hits": 1, "fetch_errors": ["ConnectionError"], "n_candidates": 1}
    diag2: dict = {}
    assert activate_corpus(corpus_ids=["bad"], fetch_atoms=fetch, diag=diag2) == []
    assert diag2 == {"n_hits": 0, "fetch_errors": ["ConnectionError"], "n_candidates": 0}


def test_evidence_packet_carries_the_firing_receipt():
    rec = F.firing_receipt(replace(FIRES, plan_fallback=True, fallback_reason="transport:timeout"))
    pkt = build_evidence_packet(q0="q", retrieval_mode="FAST", plan_queries=[], evidence_rows=[],
                                ca4_grades={}, receipts={"firing": rec, "not_a_known_key": {"x": 1}},
                                corpus_explorer_requested=True, corpus_explorer_used=False).to_dict()
    assert pkt["receipts"]["firing"]["cause"] == F.PLAN_FALLBACK
    assert "not_a_known_key" not in pkt["receipts"]
