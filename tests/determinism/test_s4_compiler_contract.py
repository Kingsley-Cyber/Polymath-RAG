"""S4 — the grounded-learning compiler contract (DOCUMENT-RAG-COMPLETION-V1 Part B; the owner's "RAG compiler for grounded
discovery"). The plan states the learning need, why each request exists and what would support it, the inquiry dimensions
and the synthesis targets; the concept bridges are written in the SAME compiler call from the Scout's matched profile items
(D5), each admitted only when it names a supplied match; D2 — a knowledge question always retrieves. Every field is
optional: a missing one marks context as missing, never skips retrieval. Flag off = the v1 contract, byte-identical."""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from orchestrator.api import ui
from polymath_shared import chat_plan as cp
from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.llm_extraction import pool as pool_mod

Q = "Why can a long take feel tense?"
MATCHES = [{"ref": "m0", "doc_id": "doc_rabiger", "kind": "CONCEPT", "text": "Withheld information creates suspense",
            "title": "Directing"},
           {"ref": "m1", "doc_id": "doc_murch", "kind": "THEORY", "text": "Cuts relieve accumulated tension", "title": "In the Blink"}]


def _raw(**over):
    raw = {"resolved_request": "Why can an uninterrupted long take feel tense?", "task_type": "GROUNDED_SYNTHESIS",
           "evidence_policy": "corpus_grounded", "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "long take tension", "weight": 1.0,
                        "expected_contribution": "could explain how an unbroken shot sustains suspense",
                        "evidence_requirement": "text linking shot duration to viewer tension"},
                       {"id": "q1", "type": "MECHANISM", "query": "anticipation during unresolved events", "weight": 0.8}],
           "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "answer", "antecedent": None, "graph_useful": False,
           "learning_need": "Understand the mechanisms by which an uninterrupted shot can produce suspense.",
           "inquiry": {"precision": "a long take is not the same as a slow scene", "depth": "anticipation vs withheld information",
                       "transfer": None, "synthesis": "reconcile mechanism sources with film-analysis sources"},
           "synthesis_targets": ["How do anticipation and withheld information interact in a long take?",
                                 "When does a long take feel calm instead?", "t3", "t4 is one too many"],
           "bridges": [{"ref": "m0", "query": "how withholding information from the audience builds suspense",
                        "expected_contribution": "could show that restricted information, not duration, drives tension",
                        "evidence_requirement": "passages on audience knowledge and suspense"},
                       {"ref": "m9", "query": "an invented concept the model free-associated"},
                       {"ref": "m1", "query": "long take tension"}]}
    raw.update(over)
    return raw


def test_the_v2_plan_carries_the_learning_need_purposes_inquiry_targets_and_grounded_bridges():
    plan, err = cp.validate_plan(_raw(), Q, contract=True, matches=MATCHES)
    assert err is None and plan.contract == cp.CONTRACT_V2
    assert plan.retrieval_goal.startswith("Understand the mechanisms")
    assert plan.inquiry == {"precision": "a long take is not the same as a slow scene",
                            "depth": "anticipation vs withheld information",
                            "synthesis": "reconcile mechanism sources with film-analysis sources"}     # null dims dropped
    assert len(plan.synthesis_targets) == 3
    q0, q1 = plan.queries[0], plan.queries[1]
    assert q0.expected_contribution.startswith("could explain") and q0.evidence_requirement.startswith("text linking")
    assert q1.expected_contribution is None                                        # missing → unexplained, never invented
    assert not any(q.origin == "BRIDGE" for q in plan.queries)       # bridges wait for the shared admission (after PROFILE)
    pending = plan._plan_bridges                                      # the retired call's own output shape
    assert [(b["ref"], b["derived_from"]) for b in pending] == [("m0", "doc_rabiger"), ("m1", "doc_murch")]
    assert pending[0]["bridge_query"] == "how withholding information from the audience builds suspense"
    assert pending[0]["relation_to_q0"] == pending[0]["expected_contribution"] and pending[0]["proposed_role"] == "COMPLEMENTARY"
    diag = plan._contract_diag
    assert diag["unexplained"] == ["q1"] and diag["bridges"] == {"proposed": 3, "grounded": 2, "dropped_invented": 1}
    assert diag["learning_need"] is True and diag["matches"] == 2


def test_the_v1_contract_ignores_every_v2_field():
    plan, err = cp.validate_plan(_raw(), Q)
    assert err is None and plan.contract == cp.CONTRACT
    assert plan.retrieval_goal is None and plan.inquiry == {} and plan.synthesis_targets == []
    assert not any(q.origin == "BRIDGE" for q in plan.queries) and not hasattr(plan, "_plan_bridges")
    assert all(q.expected_contribution is None for q in plan.queries) and not hasattr(plan, "_contract_diag")


def test_d2_a_knowledge_question_always_retrieves_small_talk_and_dont_search_are_the_exceptions():
    gc = _raw(task_type="GENERAL_CONVERSATION", retrieval_required=False, queries=[], bridges=[])
    plan, _ = cp.validate_plan(gc, "How do editors build suspense without dialogue?", contract=True, matches=MATCHES)
    assert plan.task_type == "GROUNDED_QA" and plan.retrieval_required
    assert [q.type for q in plan.queries] == ["PRIMARY"] and plan._contract_diag["d2_override"] is True
    hi, _ = cp.validate_plan(dict(gc, resolved_request="The user greets the assistant."), "hi!", contract=True)
    assert hi.task_type == "GENERAL_CONVERSATION" and not hi.retrieval_required and hi.queries == []
    quiet, _ = cp.validate_plan(_raw(), "explain why long takes feel tense, don't search my books", contract=True, matches=MATCHES)
    assert not quiet.retrieval_required and quiet.queries == [] and quiet._contract_diag["no_search"] is True
    v1, _ = cp.validate_plan(gc, "How do editors build suspense without dialogue?")
    assert v1.task_type == "GENERAL_CONVERSATION" and not v1.retrieval_required                # D2 rides the v2 flag


def test_v2_an_unasked_comparison_type_is_retyped_so_the_turn_keeps_its_intent():
    """Measured (round 2): the v2 prompt sometimes typed an aspect COMPARISON on a question that compares nothing, and
    classify_intent turns ANY comparison-typed query into a COMPARISON turn (no bridges, other lanes)."""
    raw = _raw(queries=[{"id": "q0", "type": "PRIMARY", "query": "building suspense without dialogue", "weight": 1.0},
                        {"id": "q1", "type": "COMPARISON", "query": "visual composition and framing for suspense", "weight": 0.8}])
    plan, _ = cp.validate_plan(raw, "How do editors and directors build suspense without dialogue?", contract=True)
    assert [q.type for q in plan.queries] == ["PRIMARY", "MECHANISM"] and plan.intent == "SYNTHESIS"
    assert plan._contract_diag["retyped_comparison"] == 1
    asked, _ = cp.validate_plan(dict(raw, resolved_request="Compare how editors and directors build suspense without dialogue."),
                                "Compare how editors and directors build suspense without dialogue", contract=True)
    assert [q.type for q in asked.queries] == ["PRIMARY", "COMPARISON"]
    v1, _ = cp.validate_plan(raw, "How do editors and directors build suspense without dialogue?")
    assert [q.type for q in v1.queries] == ["PRIMARY", "COMPARISON"] and v1.intent == "COMPARISON"   # v1 untouched


def test_compile_plan_v2_sends_the_addendum_the_matches_and_the_larger_budget():
    seen = {}

    def complete(system, user, max_tokens):
        seen.update(system=system, user=user, max_tokens=max_tokens)
        return json.dumps(_raw()), None

    plan = cp.compile_plan(Q, [], ["cinema"], complete, contract=True, matches=MATCHES, model="fake")
    assert "GROUNDED-LEARNING FIELDS" in seen["system"] and seen["max_tokens"] == cp.COMPILER_MAX_OUTPUT_TOKENS_V2
    assert "PROFILE MATCHES" in seen["user"] and '[m0] CONCEPT · Directing: "Withheld information creates suspense"' in seen["user"]
    assert plan.compiler["contract"]["bridges"]["grounded"] == 2 and not plan.fallback
    receipt = cp.plan_receipt(plan)
    assert receipt["learning_need"] == plan.retrieval_goal and receipt["synthesis_targets"] == plan.synthesis_targets
    assert receipt["queries"][0]["expected_contribution"].startswith("could explain")


def test_compile_plan_v1_is_byte_identical():
    seen = {}

    def complete(system, user, max_tokens):
        seen.update(system=system, user=user, max_tokens=max_tokens)
        return json.dumps(_raw()), None

    plan = cp.compile_plan(Q, [], ["cinema"], complete, contract=False, matches=MATCHES)
    assert seen["system"] == cp.SYSTEM_PROMPT and seen["max_tokens"] == cp.COMPILER_MAX_OUTPUT_TOKENS
    assert "PROFILE MATCHES" not in seen["user"] and "contract" not in plan.compiler
    receipt = cp.plan_receipt(plan)
    assert "learning_need" not in receipt and all("expected_contribution" not in q for q in receipt["queries"])


# ---------------------------------------------------------------- the live compile path (lanes + scout + bridge merge)

@pytest.fixture(autouse=True)
def _policy_receipt_in_tmp(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMATH_REASONING_RECEIPT", str(tmp_path / "reasoning.jsonl"))


class _Resp:
    def __init__(self, content):
        self._content, self.headers = content, {}

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _wire(monkeypatch, *, contract: bool, profile_query=None):
    monkeypatch.setenv(cp.CONTRACT_FLAG, "1" if contract else "0")
    monkeypatch.setenv("POLYMATH_CHAT_BRIDGE_COMPILER", "1")
    monkeypatch.delenv("POLYMATH_CHAT_PROFILE_EXPANSION", raising=False)
    noms = (SimpleNamespace(doc_id="doc_rabiger", representative_text="Withheld information creates suspense",
                            representative_surface="CONCEPT"),
            SimpleNamespace(doc_id="doc_bare", representative_text=None, representative_surface=None))
    monkeypatch.setattr(ui, "_profile_scout", lambda m, c: (["Directing"], SimpleNamespace(nominations=noms),
                                                             {"contract": "profile-scout-v1"}))
    monkeypatch.setattr(ui, "_resolve_plan_constraints", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_add_corpus_explore_expansion", lambda *a, **k: None)
    import polymath_shared.subquery_provenance as sp
    monkeypatch.setattr(sp, "annotate_subquery_provenance", lambda plan, scout: None)
    if profile_query is not None:                         # a PROFILE subquery already covering doc_rabiger (tier-1 reuse)
        monkeypatch.setattr(ui, "_add_profile_expansion", lambda plan, scout: plan.queries.append(profile_query))
    calls: list = []
    monkeypatch.setattr(ui, "_add_bridge_expansion", lambda plan, scout: calls.append("second bridge call"))

    @contextmanager
    def fake_tx():
        yield SimpleNamespace(execute=lambda sql, params=(): SimpleNamespace(fetchall=lambda: [("doc_rabiger", "Directing.md")]))
    monkeypatch.setattr(ui, "tx", fake_tx)
    ep = SimpleNamespace(name="compiler_ollama_gemma", url="https://example.invalid", model="gemma", limiter_key="c",
                         api_key="not-a-key", cloud_opts={})
    monkeypatch.setattr(pool_mod, "cloud_endpoints", lambda: [ep])
    monkeypatch.setattr(pool_mod, "stage_pin", lambda stage: [ep.name])
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        return _Resp(__import__("json").dumps(_raw()))
    monkeypatch.setattr(client_mod.httpx, "post", post)

    def complete_one(self, user_prompt, *, system_prompt, max_tokens):
        return self._chat(user_prompt, max_tokens, system_prompt=system_prompt)[0], None
    monkeypatch.setattr(client_mod.LLMExtractionClient, "complete_one", complete_one)
    return sent, calls


def test_v2_the_compiler_writes_the_bridges_and_the_old_admission_decides_without_a_second_call(monkeypatch):
    sent, calls = _wire(monkeypatch, contract=True)
    plan = ui._compile_chat_plan(Q, [], ["cinema"], session_key="s4")
    user_msg = sent[-1]["messages"][-1]["content"]
    assert '[m0] CONCEPT · Directing: "Withheld information creates suspense"' in user_msg and "doc_bare" not in user_msg
    assert len(sent) == 1 and calls == []                                       # ONE model call; the second is retired
    bx = plan.compiler["bridge_expansion"]
    assert bx["merged"] is True and bx["attempted"] is True and bx["latency_ms"] >= 0
    # only m0 was this turn's match: the m1 and m9 refs are invented here → only m0's bridge survives
    bridges = [q for q in plan.queries if q.origin == "BRIDGE"]
    assert [(b.query, b.derived_from) for b in bridges] == [
        ("how withholding information from the audience builds suspense", "doc_rabiger")]
    b = bridges[0]
    assert b.weight == 0.55 and b.inspired_by_profile == ["doc_rabiger"] and b.reason.startswith("bridge/complementary <- doc_rabiger")
    assert b.expected_contribution.startswith("could show") and b.evidence_requirement.startswith("passages on")
    assert "matches" in plan.compiler["compile_ms"] and "bridges" in plan.compiler["compile_ms"]


def test_v2_a_concept_the_profile_expansion_already_covers_gets_no_bridge(monkeypatch):
    covered = cp.CompiledQuery(id="p0", type="ENTITY", query="restricting what the audience knows to build suspense",
                               weight=0.6, role="profile", origin="PROFILE", inspired_by_profile=["doc_rabiger"])
    _wire(monkeypatch, contract=True, profile_query=covered)
    plan = ui._compile_chat_plan(Q, [], ["cinema"], session_key="s4")
    assert not any(q.origin == "BRIDGE" for q in plan.queries)
    assert plan.compiler["bridge_expansion"]["dropped_covered"] == 1


def test_the_matches_leave_out_the_books_the_profile_expansion_already_searches(monkeypatch):
    noms = [SimpleNamespace(doc_id="d0", representative_text="idea 0", representative_surface="CONCEPT"),
            SimpleNamespace(doc_id="d0", representative_text="same book, second idea", representative_surface="THEORY"),
            SimpleNamespace(doc_id="dx", representative_text=None, representative_surface=None),
            *[SimpleNamespace(doc_id=f"d{i}", representative_text=f"idea {i}", representative_surface="CONCEPT") for i in (1, 2, 3)]]

    @contextmanager
    def fake_tx():
        yield SimpleNamespace(execute=lambda sql, params=(): SimpleNamespace(fetchall=list))
    monkeypatch.setattr(ui, "tx", fake_tx)
    monkeypatch.setenv("POLYMATH_CHAT_PROFILE_EXPANSION", "1")
    monkeypatch.setenv("POLYMATH_CHAT_PROFILE_EXPANSION_MAX", "2")
    got = ui._scout_matches(SimpleNamespace(nominations=noms), ["cinema"])   # expansion takes d0's two ideas → d0 covered
    assert [(m["ref"], m["doc_id"], m["text"]) for m in got] == [("m0", "d1", "idea 1"), ("m1", "d2", "idea 2"),
                                                                  ("m2", "d3", "idea 3")]
    monkeypatch.setenv("POLYMATH_CHAT_PROFILE_EXPANSION", "0")
    assert [m["doc_id"] for m in ui._scout_matches(SimpleNamespace(nominations=noms), ["cinema"])] == ["d0", "d1", "d2", "d3"]


def test_v1_keeps_the_separate_bridge_call(monkeypatch):
    sent, calls = _wire(monkeypatch, contract=False)
    plan = ui._compile_chat_plan(Q, [], ["cinema"], session_key="s4")
    assert calls == ["second bridge call"] and "PROFILE MATCHES" not in sent[-1]["messages"][-1]["content"]
    assert not (plan.compiler.get("bridge_expansion") or {}).get("merged")


def test_a_v2_fallback_plan_keeps_the_separate_bridge_call(monkeypatch):
    _sent, calls = _wire(monkeypatch, contract=True)
    monkeypatch.setattr(client_mod.httpx, "post", lambda *a, **k: _Resp("not json at all"))
    plan = ui._compile_chat_plan(Q, [], ["cinema"], session_key="s4")
    assert plan.fallback and calls == ["second bridge call"]
