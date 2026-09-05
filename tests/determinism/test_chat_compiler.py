"""CHAT-INTENT-PLAN-V1 compiler laws (plan §3.1–§3.2, P0.b), pure — the LLM
is a stub. Live behaviour is measured by scripts/chat_compiler_canary.py."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import chat_plan as cp  # noqa: E402

GOOD = {
    "resolved_request": "How does cognitive overload affect creativity?",
    "task_type": "GROUNDED_SYNTHESIS", "evidence_policy": "corpus_grounded", "retrieval_required": True,
    "retrieval_goal": "mechanisms linking overload to creative output",
    "queries": [{"id": "q0", "type": "PRIMARY", "query": "cognitive overload effects on creativity", "weight": 1.0},
                {"id": "q1", "type": "MECHANISM", "query": "working memory load divergent thinking", "weight": 0.8}],
    "semantic_queries": ["cognitive overload creativity"], "exact_terms": [], "entities": [], "must_answer": ["mechanism", "evidence"],
    "user_constraints": [], "response_type": "answer", "antecedent": {"turn": -2, "kind": "topic", "summary": "cognitive overload"},
    "graph_useful": False,
}


def _complete_returning(obj):
    def _c(system_prompt, user_prompt, max_tokens):
        assert "QUERY COMPILER" in system_prompt and max_tokens <= cp.COMPILER_MAX_OUTPUT_TOKENS
        return (json.dumps(obj) if not isinstance(obj, str) else obj), None
    return _c


def test_valid_plan_compiles_and_resolves_the_followup():
    hist = [{"role": "user", "content": "What does the corpus say about cognitive overload?"},
            {"role": "assistant", "content": "Cognitive overload occurs when ..."}]
    plan = cp.compile_plan("How does that affect creativity though?", hist, ["ecom-meta-v1"], _complete_returning(GOOD), model="stub")
    assert not plan.fallback and plan.task_type == "GROUNDED_SYNTHESIS" and plan.retrieval_required
    assert plan.original_request == "How does that affect creativity though?"
    assert "overload" in plan.resolved_request and "creativ" in plan.resolved_request
    assert [q.type for q in plan.queries] == ["PRIMARY", "MECHANISM"] and plan.compiler["history_turns"] == 2


def test_fallback_is_todays_behaviour_and_receipted():
    for reason_src, comp in (("transport", lambda s, u, m: ("", "HTTP_429")),
                             ("invalid_json", lambda s, u, m: ("sure! here is the plan: task=qa", None)),
                             ("exception", lambda s, u, m: (_ for _ in ()).throw(RuntimeError("boom")))):
        plan = cp.compile_plan("What is the 180-degree rule?", [], ["cinema"], comp)
        assert plan.fallback and plan.task_type == "GROUNDED_QA" and plan.retrieval_required
        assert plan.queries[0].type == "PRIMARY" and plan.queries[0].query == "What is the 180-degree rule?"
        assert plan.compiler["reason"], reason_src


def test_soft_budget_is_measured_and_hard_budget_falls_back():
    import time as _t
    def slow(s, u, m):
        _t.sleep(0.05); return json.dumps(GOOD), None
    # over the SOFT budget: the plan is kept and flagged (the p50 gate reads the flag)
    kept = cp.compile_plan("How does that affect creativity though?", [], [], slow, budget_s=0.01, hard_budget_s=5.0)
    assert not kept.fallback and kept.compiler["over_budget"] is True
    # over the HARD budget: the plan is discarded for the fallback
    plan = cp.compile_plan("How does that affect creativity though?", [], [], slow, budget_s=0.01, hard_budget_s=0.02)
    assert plan.fallback and plan.compiler["reason"].startswith("budget_exceeded")


def test_law1_the_compiler_never_rewrites_the_task():
    raw = dict(GOOD, resolved_request="Summarize what Christensen says about new markets.")
    plan, reason = cp.validate_plan(raw, "Tell me whether the authors agree or disagree about where new markets come from.")
    assert plan is None and reason.startswith("task_rewritten")
    raw2 = dict(GOOD, resolved_request="Compare Christensen's and Kim & Mauborgne's positions on where new markets come from and state where they agree or disagree.")
    plan2, reason2 = cp.validate_plan(raw2, "Tell me whether the authors agree or disagree about where new markets come from.")
    assert plan2 is not None, reason2
    # an artifact continuation may be restated as a production request
    raw3 = {"resolved_request": "Produce the final video-generation prompt developed earlier in this conversation.",
            "task_type": "CONTINUE_PRIOR_ARTIFACT", "evidence_policy": "conversation", "retrieval_required": False,
            "queries": [], "response_type": "artifact"}
    plan3, r3 = cp.validate_plan(raw3, "so what's the final prompt ?? for video gen")
    assert plan3 is not None and plan3.retrieval_required is False and plan3.queries == [] and plan3.response_type == "artifact"


def test_two_query_representations_and_verbatim_exact_terms():
    msg = 'What does RAPO say about "reward-aware prompt optimization" for text-to-video (TS410 setup, 24fps)?'
    raw = dict(GOOD, resolved_request="What does RAPO say about reward-aware prompt optimization for text-to-video?",
               task_type="GROUNDED_QA",
               queries=[{"id": "q0", "type": "PRIMARY", "query": "automated prompt optimization techniques for video generation", "weight": 1}],
               semantic_queries=["automated prompt optimization for video generation"], exact_terms=[])
    plan, reason = cp.validate_plan(raw, msg)
    assert plan is not None, reason
    assert "RAPO" in plan.exact_terms and "TS410" in plan.exact_terms and "reward-aware prompt optimization" in plan.exact_terms
    assert plan.semantic_queries[0].startswith("automated prompt")           # dense text may be rewritten
    assert "RAPO" not in plan.semantic_queries[0]                              # … while the sparse lane keeps the verbatim term


def test_queries_are_topical_short_and_bounded():
    raw = dict(GOOD, queries=[
        {"id": "a", "type": "PRIMARY", "query": "respond in markdown with bullet lists and a warm tone", "weight": 1},
        {"id": "b", "type": "PRIMARY", "query": " ".join(["attention"] * 60), "weight": 1},
        {"id": "c", "type": "BOGUS", "query": "habit formation cues rewards repetition", "weight": 5},
        {"id": "d", "type": "MECHANISM", "query": "variable reward novelty attention switching", "weight": 0.5},
        {"id": "e", "type": "CAUSAL", "query": "dopamine reward prediction checking", "weight": 0.5},
        {"id": "f", "type": "EXAMPLE", "query": "one more", "weight": 0.5},
    ])
    plan, reason = cp.validate_plan(raw, "Why does short-form media destroy my ability to read and how do I recover it?")
    assert plan is not None, reason
    assert len(plan.queries) == cp.MAX_QUERIES
    assert all(len(q.query.split()) <= cp.MAX_QUERY_WORDS for q in plan.queries)
    assert not any("markdown" in q.query for q in plan.queries)
    assert sum(1 for q in plan.queries if q.type == "PRIMARY") == 1 and all(q.weight <= 1.0 for q in plan.queries)


def test_no_retrieval_tasks_carry_no_queries():
    raw = {"resolved_request": "Rewrite the user's Brainrot Recovery prompt into a stronger production-quality prompt with the same deliverable.",
           "task_type": "TRANSFORM_USER_CONTENT", "evidence_policy": "conversation", "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "habit coaching prompt", "weight": 1}]}
    plan, reason = cp.validate_plan(raw, "Turn this into a stronger, production-quality prompt while keeping the same deliverable.")
    assert plan is not None, reason
    assert plan.retrieval_required is False and plan.queries == [] and plan.response_type == "artifact"


def test_history_window_and_prompt_shape():
    hist = [{"role": "user", "content": f"turn {i} " + "x" * 3000} for i in range(20)]
    prompt, n = cp.user_prompt("and the final one?", hist, ["cinema"])
    assert n == cp.HISTORY_TURNS and "[turn -1]" in prompt and "turn 19" in prompt and "turn 0 " not in prompt
    assert len(prompt) < cp.HISTORY_TURNS * (cp.HISTORY_CHARS_PER_TURN + 40) + 400


def test_fixtures_declare_expectations_the_live_canary_checks():
    D = ROOT / "eval" / "fixtures" / "chat_conversations"
    names = sorted(p.stem for p in D.glob("*.json"))
    assert {"video_prompt_final", "brainrot_transform", "followup_creativity", "cinema_improve_prompt", "authors_agree", "exact_terms_rapo"} <= set(names)
    for p in D.glob("*.json"):
        fx = json.loads(p.read_text())
        assert fx.get("message") and "corpus_id" in fx
        exp = fx.get("expected") or fx.get("expected_after_compiler") or {}
        assert exp.get("task_type") in cp.TASK_TYPES


def test_corrections_fix_the_two_measured_confusions():
    # A. corpus reference forces retrieval even when the lane said CONTINUE
    raw = {"resolved_request": "Improve the final video-generation prompt using the cinema books' guidance on action, cinematography and movement.",
           "task_type": "CONTINUE_PRIOR_ARTIFACT", "evidence_policy": "conversation", "retrieval_required": False, "queries": [], "response_type": "artifact"}
    msg = "Use everything my cinema books know about action, cinematography and movement to make this final video-gen prompt better"
    plan = cp.compile_plan(msg, [{"role": "assistant", "content": "Draft: ..."}], ["cinema"], _complete_returning(raw))
    assert plan.task_type == "CREATE_FROM_KNOWLEDGE" and plan.retrieval_required and plan.queries and plan.response_type == "artifact"
    assert any(c.startswith("corpus_reference:") for c in plan.compiler["corrections"])
    # B. 'the final prompt' after an assistant artifact, no corpus reference → continuation, no retrieval
    raw2 = dict(GOOD, resolved_request="Produce the final video-generation prompt based on the draft developed earlier.",
                task_type="CREATE_FROM_KNOWLEDGE", retrieval_required=True)
    hist = [{"role": "user", "content": "draft me a video prompt"}, {"role": "assistant", "content": "Draft v1: ..."}]
    plan2 = cp.compile_plan("so what's the final prompt ?? for video gen", hist, ["cinema"], _complete_returning(raw2))
    assert plan2.task_type == "CONTINUE_PRIOR_ARTIFACT" and plan2.retrieval_required is False and plan2.queries == []
    assert any(c.startswith("prior_artifact:") for c in plan2.compiler["corrections"])
    # no assistant turn to refer to → the rule does not fire
    plan3 = cp.compile_plan("so what's the final prompt ?? for video gen", [], ["cinema"], _complete_returning(raw2))
    assert plan3.task_type == "CREATE_FROM_KNOWLEDGE" and plan3.compiler["corrections"] == []
    assert cp.references_corpus("what do my books say about habits") and not cp.references_corpus("what is the 180-degree rule")
