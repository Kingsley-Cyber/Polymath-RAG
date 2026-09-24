"""S8 — the grounded-learning synthesis contract (DOCUMENT-RAG-COMPLETION-V1 Part E). Behind POLYMATH_CHAT_SYNTH_CONTRACT
(default off): every [S#] the main search did not find names the path that discovered it (and, on a v2 plan, what that
search was meant to show), the request carries the planner's learning need and synthesis targets as hypotheses, the
system prompt carries the Part E answer rules, and a derived insight [A#] whose proving child is not an [S#] is dropped
(ELITE §6 rule 3). Off = the prompt is unchanged."""
from __future__ import annotations

from orchestrator.api import ui
from polymath_shared import chat_plan as cp

FLAG = ui._SYNTH_CONTRACT_FLAG


def _item(cid: str, text: str) -> dict:
    return {"kind": "child", "text_kind": "child", "source_chunk_id": cid, "source_document_id": f"doc_{cid}",
            "source_span": {"locator": f"chunk:{cid}", "text": text},
            "presentation": {"human_locator": f"Book {cid} › Section"}}


def _bundle() -> dict:
    return {"evidence_bundle": [_item("c1", "Murch ranks emotion first and three-dimensional continuity last."),
                                _item("c2", "Withholding information from the audience builds suspense."),
                                _item("c3", "A moving camera can carry a sense of effort.")],
            "evidence_roles": {"c1": "DIRECT", "c2": "LATENT", "c3": "RELATIONAL"},
            "evidence_paths": {"c1": ["q0"], "c2": ["br0", "q1", "p0", "rt:latent"], "c3": ["rt:seealso"]},
            "derived_insights": [
                {"principle": "Information asymmetry drives tension", "why_it_may_transfer": "a cut withholds",
                 "source_evidence": {"chunk_id": "c2", "text": "Withholding information…"}, "verified": True},
                {"principle": "Effort qualities map to camera speed", "why_it_may_transfer": "dance → camera",
                 "source_evidence": {"chunk_id": "c9", "text": "an unjudged child"}, "verified": True}]}


def _plan(v2: bool = True):
    raw = {"resolved_request": "How should I prioritise continuity when I cut?", "task_type": "GROUNDED_SYNTHESIS",
           "evidence_policy": "corpus_grounded", "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "continuity priority in editing", "weight": 1.0,
                        "expected_contribution": "could show how editors rank continuity",
                        "evidence_requirement": "a ranking of cutting criteria"},
                       {"id": "q1", "type": "MECHANISM", "query": "why a cut feels invisible", "weight": 0.8}],
           "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "answer", "antecedent": None, "graph_useful": False,
           "learning_need": "Understand what editors trade continuity against when they cut.",
           "synthesis_targets": ["When does emotion override continuity?", "Which continuity errors do audiences notice?"],
           "bridges": []}
    plan, err = cp.validate_plan(raw, "Since Murch says continuity matters most, how should I cut for it?", contract=v2)
    assert err is None
    if v2:
        plan.queries.append(cp.CompiledQuery(id="br0", type="ENTITY", query="how withholding information builds suspense",
                                             weight=0.55, role="bridge", origin="BRIDGE",
                                             expected_contribution="could show tension without continuity"))
    return plan


def _msgs(monkeypatch, on: bool, plan=None, bundle=None):
    monkeypatch.setenv(FLAG, "1" if on else "0")
    monkeypatch.setenv("POLYMATH_CHAT_SYNTH_ROLES", "1")
    b = bundle if bundle is not None else _bundle()
    return ui._grounded_messages("Since Murch says continuity matters most, how should I cut for it?", b, [], [], [],
                                 plan=plan if plan is not None else _plan()), b


def test_off_nothing_changes_in_the_prompt(monkeypatch):
    msgs, b = _msgs(monkeypatch, on=False)
    system, user = msgs[0]["content"], msgs[-1]["content"]
    assert system == ui._llm_system_prompt("neutral")
    for marker in ("found by:", "Grounded-learning contract", "LEARNING NEED", "SYNTHESIS TARGETS"):
        assert marker not in system + user
    assert "GROUNDS IN (attached child, not an [S#])" in user          # today's behaviour for an unproven [A#]
    assert "synth_contract" not in b
    no_paths = dict(_bundle(), evidence_paths={})
    assert _msgs(monkeypatch, on=False, bundle=no_paths)[0] == msgs     # the paths are inert while the flag is off


def test_on_each_discovered_passage_names_the_path_that_found_it(monkeypatch):
    msgs, b = _msgs(monkeypatch, on=True)
    user = msgs[-1]["content"]
    assert "[S1] (DIRECT) Book c1 › Section\nMurch ranks" in user          # the main search found it: direct, no line
    assert ("found by: a bridge from a matched book's idea \"how withholding information builds suspense\" "
            "(meant to show: could show tension without continuity); also a mechanism search") in user
    assert "(+2 more)" in user
    assert "found by: the see-also route (a related-book link)" in user
    assert b["synth_contract"] == {"contract": "synthesis-v3", "paths": 2, "derived_dropped": 1, "targets": 2}


def test_on_the_request_carries_the_learning_need_and_the_targets(monkeypatch):
    user = _msgs(monkeypatch, on=True)[0][-1]["content"]
    assert ("LEARNING NEED (the planner's reading, written before any source was read): Understand what editors trade "
            "continuity") in user
    assert ("SYNTHESIS TARGETS (the planner's questions, written before any source was read — check their premises; "
            "address each the sources support; say which they cannot settle):\n"
            "1. When does emotion override continuity?\n2. Which continuity errors do audiences notice?") in user
    v1_user = _msgs(monkeypatch, on=True, plan=_plan(v2=False))[0][-1]["content"]
    assert "LEARNING NEED" not in v1_user and "SYNTHESIS TARGETS" not in v1_user   # a v1 plan has neither


def test_on_the_system_prompt_carries_the_answer_rules(monkeypatch):
    system = _msgs(monkeypatch, on=True)[0][0]["content"]
    assert system == ui._llm_system_prompt("neutral", learning=True)
    # above the presentation contract, whose "a display rule above loses" clause keeps the answer's shape
    assert system.index("Grounded-learning contract") < system.index("Information-presentation contract")
    for rule in ("open the answer by correcting it", "never answer a target as asked",
                 "say so plainly before offering related material", "state the mapping", "transfer is not established",
                 "only when one passage states the connection", "Never invent a consensus",
                 "Address each SYNTHESIS TARGET the sources can support"):
        assert rule in system


def test_on_a_derived_insight_without_its_proving_source_is_dropped(monkeypatch):
    user = _msgs(monkeypatch, on=True)[0][-1]["content"]
    assert "[A1] PRINCIPLE: Information asymmetry drives tension" in user and "GROUNDS IN: [S2]" in user
    assert "Effort qualities map to camera speed" not in user and "attached child" not in user
    assert "a transferable pattern in [S#] is the principle" in user
    _, n = ui._render_derived(_bundle()["derived_insights"], {"c2": "S2"}, require_proof=True)
    assert n == 1


def test_the_receipt_records_what_the_contract_put_in_front_of_the_model(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    b = _bundle()
    gen = ui._ollama_generate("m", "q", b, [], [], [], plan=_plan())
    first = next(gen)                                              # the prompt frame is yielded before any call
    gen.close()
    assert first["prompt"]["synthesis_contract"] == {"contract": "synthesis-v3", "paths": 2, "derived_dropped": 1,
                                                     "targets": 2}
    assert ui._plan_meta(None)["prompt_contract"] == "synthesis-v3"
    monkeypatch.setenv(FLAG, "0")
    assert ui._plan_meta(None)["prompt_contract"] == ui._SYNTHESIS_CONTRACT
    gen = ui._ollama_generate("m", "q", _bundle(), [], [], [], plan=_plan())
    assert "synthesis_contract" not in next(gen)["prompt"]
    gen.close()


def test_the_rows_handed_to_assembly_keep_the_searches_that_found_them():
    rows = ui._evidence_rows([{"chunk_id": "c1", "doc_id": "d1", "parent_id": "p1", "role": "DIRECT",
                               "query_ids": ["q0", "rt:latent"]}])
    assert rows == [{"chunk_id": "c1", "doc_id": "d1", "parent_id": "p1", "role": "DIRECT", "query_ids": ["q0", "rt:latent"]}]
    assert ui._path_line(["rt:graph", "xq"], None) == "found by: the graph route (a fact hop)"
    assert ui._path_line(["br0", "q0"], _plan()) is None                  # the main search found it too: direct
    assert ui._path_line([], None) is None and ui._path_line(["unknown-id"], None) is None
