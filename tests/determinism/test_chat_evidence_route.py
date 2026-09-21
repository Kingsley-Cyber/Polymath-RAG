"""Regression for the first real ecommerce run's ZERO-ROW evidence boundary (restoration delta D-a).

DIAGNOSIS (read from `query_receipts.meta.chat_plan`, run `adr_c994b32a…`, 13 of 13 `/chat/evidence` calls): the adapter submits a
NEED that is a STATEMENT (the seed, a hypothesis statement); the chat intent compiler classified it `GENERAL_CONVERSATION`,
`retrieval_required: false`, `queries: []`; `api/ui.py` then skipped retrieval (`retrieval_skipped: true`) and the evidence-only
route answered with an EMPTY packet, `retrieval_completed: true`. `/retrieve/plan`, which has no intent gate, returned 121 rows for
the same need and corpus. The fix is one pure function: on the evidence-only route a plan that would not retrieve is made
retrievable deterministically (grounded QA on the need verbatim, a q0 PRIMARY). The chat route is untouched.

Pure: `shared/` only — no orchestrator import (under pytest in a worktree that package resolves to the MAIN checkout)."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared import chat_plan as CP  # noqa: E402

#: run 5, B_retrieve — the seed, exactly as the evidence boundary submitted it
NEED = "Nature and outdoor photographers and filmmakers struggle to reach, steady and protect their camera gear with cold, wet hands while moving between shots on the trail"


def _conversation_plan() -> CP.ChatPlan:
    """The plan the compiler really produced for that need (fields from the stored receipt)."""
    return CP.ChatPlan(contract=CP.CONTRACT, original_request=NEED, resolved_request=NEED + ".", task_type="GENERAL_CONVERSATION", evidence_policy="conversation",
                       retrieval_required=False, retrieval_goal=None, queries=[], semantic_queries=[], exact_terms=[], entities=[], must_answer=[], user_constraints=[],
                       response_type="answer", antecedent=None, graph_useful=False, intent="EXPLORATORY",
                       compiler={"lane": "compiler_ollama_gemma", "attempt": 3, "fallback": False, "first_failure": "compiler_alt:transport:HTTP_429"})


def test_the_code_under_test_is_this_checkout():
    assert pathlib.Path(CP.__file__).resolve().is_relative_to(ROOT), CP.__file__


def test_the_defect_a_statement_need_compiles_to_a_plan_that_would_never_retrieve():
    plan = _conversation_plan()
    assert plan.task_type in CP.NO_RETRIEVAL_TASKS and not plan.retrieval_required and plan.queries == []           # what run 5 stored, 13 of 13 times


def test_on_the_evidence_route_that_plan_retrieves_the_need_verbatim():
    before = _conversation_plan()
    plan = CP.plan_for_evidence_route(before)
    assert plan.retrieval_required is True and plan.task_type == "GROUNDED_QA" and plan.evidence_policy == "corpus_grounded"
    assert [(q.id, q.type) for q in plan.queries] == [("q0", "PRIMARY")] and plan.queries[0].query == CP._clean_query(NEED)      # a PRIMARY, so Corpus Explore can fire
    assert CP.retrieval_text_for(plan) and "photographers" in CP.retrieval_text_for(plan) and plan.semantic_queries == [CP._clean_query(NEED)]
    assert plan.original_request == NEED and plan.intent == before.intent                                                         # nothing else the compiler said is lost
    # the override is SAID on the plan receipt — never a silent rewrite
    receipt = CP.plan_receipt(plan)
    assert receipt["compiler"]["evidence_route_override"] == {"rule": CP.EVIDENCE_ROUTE_OVERRIDE, "from_task_type": "GENERAL_CONVERSATION", "from_evidence_policy": "conversation",
                                                             "from_retrieval_required": False, "compiled_queries": 0}
    assert receipt["compiler"]["lane"] == "compiler_ollama_gemma" and before.retrieval_required is False and before.queries == []    # the input plan is not mutated


def test_a_plan_that_already_retrieves_is_returned_unchanged():
    plan = CP.fallback_plan("how does a camera crew keep equipment working through a shooting day?", reason="compiler_unreachable")
    assert CP.plan_for_evidence_route(plan) is plan
    compiled = _conversation_plan()
    compiled.retrieval_required, compiled.task_type = True, "GROUNDED_QA"
    compiled.queries = [CP.CompiledQuery(id="q1", type="PRIMARY", query="camera crew equipment hand-offs", weight=1.0)]
    assert CP.plan_for_evidence_route(compiled) is compiled


def test_a_required_retrieval_without_any_compiled_query_still_gets_its_q0():
    plan = _conversation_plan()
    plan.retrieval_required = True
    fixed = CP.plan_for_evidence_route(plan)
    assert [q.type for q in fixed.queries] == ["PRIMARY"] and fixed.compiler["evidence_route_override"]["from_retrieval_required"] is True


def test_the_orchestrator_calls_it_only_for_the_evidence_only_route():
    ui = (ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py").read_text(encoding="utf-8")
    call = ui.index("_plan = plan_for_evidence_route(_plan)")
    guard = ui.rfind('if getattr(req, "evidence_only", False):', 0, call)
    assert 0 < call - guard < 300 and ui.index("_skip_retrieval = (not _plan.retrieval_required)") > call          # applied BEFORE the skip decision; chat turns never reach it
