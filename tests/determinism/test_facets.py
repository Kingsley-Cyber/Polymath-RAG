"""FACET-RETRIEVAL-V1 F1 — facets in the chat query compiler (register 11.545; plan §3.1, §4 F1).

The measured failure (receipt q_e09925df009649c6be872299): the compiler's USER queries never asked about "direction for an
AI video ad", so the section that answered it was never searched. Proof here, with the model scripted:
  * the facet step names ≥ 4 facets of that exact question, one about directing the AI video model, and its prompt
    carries no corpus id, no library title and no profile match (the prompt builder has no parameter for them);
  * a lookup ("What is AU21?") is one facet = q0; without the step the facets DERIVE from the compiled queries;
  * the wording call gives every query a `facet_id`, a facet it left without a query gets the facet's own query, and
    PROFILE / BRIDGE probes attach to the facet they serve (or None);
  * the receipt: `facets` on the plan receipt, `facet_id` on the provenance rows, `facets_covered` / `facets_uncovered`
    from the final evidence; the flag off is the pre-facet compiler and receipt, byte for byte.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from orchestrator.api import ui
from polymath_shared import chat_plan as cp
from polymath_shared import facets as fx
from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.llm_extraction import pool as pool_mod

#: the receipt's question, verbatim (FACET-RETRIEVAL-V1 §1)
Q_ECOM = ("can you create a prompt eccomerce story prompt and direction for a eccomerce ai video ad. "
          "I want it to be capturing and playing of emotions")
FACETS_ECOM = {
    "resolved_request": "Create an ecommerce story prompt and direction for an AI video ad that captures and plays on emotions",
    "facets": [
        {"id": "f1", "name": "ecommerce ad story prompt", "query": "ecommerce video ad story structure prompt", "type": "PRIMARY"},
        {"id": "f2", "name": "emotional storytelling in ads", "query": "advertising storytelling that evokes emotion", "type": "MECHANISM"},
        {"id": "f3", "name": "directing the AI video model", "query": "directing an AI video generation model camera motion shot prompts",
         "type": "PROCEDURE"},
        {"id": "f4", "name": "emotions that drive purchases", "query": "consumer emotions persuasion buying behaviour", "type": "CAUSAL"},
    ],
}
#: names a real library would tempt the model with — none may reach the facet step
LIBRARY_WORDS = ("Adweek", "Ogilvy", "handbook", "Bruce Block", "cinema", "BOOKS IN THE LIBRARY", "PROFILE MATCHES", "CORPUS IN SCOPE")


def _complete_returning(obj, seen: dict | None = None):
    def _c(system_prompt, user_prompt, max_tokens):
        if seen is not None:
            seen.update({"system": system_prompt, "user": user_prompt, "max_tokens": max_tokens})
        return (json.dumps(obj) if not isinstance(obj, str) else obj), None
    return _c


def _wording_reply(**over):
    raw = {"resolved_request": FACETS_ECOM["resolved_request"], "task_type": "CREATE_FROM_KNOWLEDGE",
           "evidence_policy": "corpus_grounded", "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "ecommerce video ad story prompt", "weight": 1.0, "facet_id": "f1"},
                       {"id": "q1", "type": "MECHANISM", "query": "storytelling that evokes emotion in advertising", "weight": 0.9, "facet_id": "f2"},
                       {"id": "q2", "type": "PROCEDURE", "query": "camera motion and shot prompts for an AI video model", "weight": 0.9, "facet_id": "f3"},
                       {"id": "q3", "type": "ADJACENT", "query": "how a sequence of images moves an observer", "weight": 0.6, "facet_id": "f2"}],
           "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "artifact", "antecedent": None, "graph_useful": False}
    raw.update(over)
    return raw


def test_the_facet_step_names_the_receipts_facets_from_the_question_alone(monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "1")
    seen: dict = {}
    rec = fx.compile_facets(Q_ECOM, [{"role": "user", "content": "earlier turn about Adweek copy"}], _complete_returning(FACETS_ECOM, seen), model="stub")
    assert rec["contract"] == fx.FACET_CONTRACT and rec["fallback"] is False and rec["n"] >= 4 and rec["wall_ms"] >= 0
    names = " ".join(f"{f['name']} {f['query']}" for f in rec["facets"]).lower()
    assert "directing" in names and "video" in names and "model" in names           # the facet the live turn never searched
    assert [f["id"] for f in rec["facets"]] == ["f1", "f2", "f3", "f4"] and rec["facets"][0]["type"] == "PRIMARY"
    # corpus-agnostic by construction: the prompt names the conversation and the message, nothing about the library
    prompt = seen["system"] + "\n" + seen["user"]
    assert "FACET NAMER" in seen["system"] and Q_ECOM in seen["user"] and seen["max_tokens"] == fx.FACET_MAX_OUTPUT_TOKENS
    for w in LIBRARY_WORDS:
        assert w not in seen["system"] and w not in seen["user"].replace("earlier turn about Adweek copy", ""), (w, prompt[:200])
    import inspect
    sig = inspect.signature(fx.facet_user_prompt)
    assert list(sig.parameters) == ["message", "history"]                              # no corpus, no titles, no matches parameter


def test_a_lookup_is_one_facet_and_a_missing_step_derives_the_facets(monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "1")
    one = {"resolved_request": "What is AU21?", "facets": [{"id": "f1", "name": "AU21", "query": "AU21", "type": "PRIMARY"}]}
    rec = fx.compile_facets("What is AU21?", [], _complete_returning(one))
    assert rec["n"] == 1 and rec["facets"] == [{"id": "f1", "name": "AU21", "query": "AU21", "type": "PRIMARY"}]
    lookup = {"resolved_request": "What is AU21?", "task_type": "GROUNDED_QA", "evidence_policy": "corpus_grounded", "retrieval_required": True,
              "queries": [{"id": "q0", "type": "PRIMARY", "query": "AU21", "weight": 1.0, "facet_id": "f1"}], "exact_terms": ["AU21"],
              "response_type": "answer", "graph_useful": False}
    plan = cp.compile_plan("What is AU21?", [], ["cinema"], _complete_returning(lookup), facets=rec["facets"])
    assert not plan.fallback and [q.id for q in plan.queries] == ["q0"] and plan.queries[0].facet_id == "f1"
    assert plan.facets == [{"id": "f1", "name": "AU21", "query_ids": ["q0"]}] and plan.compiler["facets"]["source"] == "facet_step"
    # the step failed (or was late): the facets derive from the compiled queries — a lookup is still one facet = q0
    fb = cp.fallback_plan("What is AU21?", reason="transport:HTTP_429")
    assert fb.facets == [{"id": "f1", "name": "What is AU21?", "query_ids": ["q0"]}] and fb.queries[0].facet_id == "f1"
    assert fb.compiler["facets"]["source"] == "derived"
    late = fx.compile_facets("What is AU21?", [], lambda s, u, m: ("not json at all", None))
    assert late["facets"] is None and late["fallback"] is True and late["reason"] == "invalid_json"
    for bad, why in (({"facets": []}, "facets_missing"), ({"facets": [{"name": "", "query": ""}]}, "no_usable_facets"), ("x", "not_an_object")):
        assert fx.parse_facets(bad, "m") == (None, why)


def test_the_wording_call_carries_facet_ids_and_fills_an_unqueried_facet(monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "1")
    seen: dict = {}
    plan = cp.compile_plan(Q_ECOM, [], ["cinema"], _complete_returning(_wording_reply(), seen), facets=FACETS_ECOM["facets"],
                           titles=["Adweek Copywriting Handbook", "Ogilvy on Advertising"])
    assert not plan.fallback and plan.task_type == "CREATE_FROM_KNOWLEDGE"
    # the prompt: the facets come first, then the library (which may only sharpen wording), and the addendum rules
    assert "FACETS OF THE REQUEST" in seen["user"] and "[f3] directing the AI video model" in seen["user"]
    assert seen["user"].index("FACETS OF THE REQUEST") < seen["user"].index("BOOKS IN THE LIBRARY") < seen["user"].index("RECENT CONVERSATION")
    assert cp.FACETS_ADDENDUM in seen["system"] and "Never drop a facet" in seen["system"]
    assert seen["max_tokens"] == cp.COMPILER_MAX_OUTPUT_TOKENS + cp.FACET_EXTRA_OUTPUT_TOKENS
    # every query claims a facet; f4 (never queried by the model) gets the facet step's own query, USER origin, its type
    assert [(q.id, q.type, q.facet_id, q.origin) for q in plan.queries] == [
        ("q0", "PRIMARY", "f1", "USER"), ("q1", "MECHANISM", "f2", "USER"), ("q2", "PROCEDURE", "f3", "USER"),
        ("q3", "ADJACENT", "f2", "USER"), ("q4", "CAUSAL", "f4", "USER")]
    assert plan.queries[4].query == "consumer emotions persuasion buying behaviour"
    assert plan.facets == [{"id": "f1", "name": "ecommerce ad story prompt", "query_ids": ["q0"]},
                           {"id": "f2", "name": "emotional storytelling in ads", "query_ids": ["q1", "q3"]},
                           {"id": "f3", "name": "directing the AI video model", "query_ids": ["q2"]},
                           {"id": "f4", "name": "emotions that drive purchases", "query_ids": ["q4"]}]
    fr = plan.compiler["facets"]
    assert fr["n"] == 4 and fr["inserted"] == ["f4"] and fr["unqueried"] == [] and fr["dropped"] == 0 and fr["source"] == "facet_step"
    assert len(plan.queries) <= cp.MAX_QUERIES_FACETS and cp.MAX_FACETS == 5 and cp.MAX_QUERIES_FACETS == 6
    # a mis-claimed or missing facet id is assigned by overlap; a second query on the same facet is dropped
    dup = _wording_reply(queries=[{"id": "q0", "type": "PRIMARY", "query": "ecommerce video ad story prompt", "weight": 1.0, "facet_id": "f9"},
                                  {"id": "q1", "type": "PROCEDURE", "query": "directing the AI video model shot list", "weight": 0.9},
                                  {"id": "q2", "type": "MECHANISM", "query": "camera direction for the AI video model", "weight": 0.9, "facet_id": "f3"}])
    plan2 = cp.compile_plan(Q_ECOM, [], ["cinema"], _complete_returning(dup), facets=FACETS_ECOM["facets"])
    ids2 = [(q.id, q.facet_id) for q in plan2.queries]
    assert ids2[:2] == [("q0", "f1"), ("q1", "f3")] and plan2.compiler["facets"]["dropped"] == 1        # q2 repeated f3 → dropped
    assert sorted(plan2.compiler["facets"]["inserted"]) == ["f2", "f4"] and len(plan2.queries) == 4


def test_probes_attach_to_the_facet_they_serve_and_the_receipts_carry_the_facet_fields(monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "1")
    plan = cp.compile_plan(Q_ECOM, [], ["cinema"], _complete_returning(_wording_reply()), facets=FACETS_ECOM["facets"])
    plan.queries.append(cp.CompiledQuery(id="p0", type="ENTITY", query="how a camera move directs the eye in an ai video model", weight=0.6,
                                         role="bridge", origin="PROFILE", inspired_by_profile=["doc_x"]))
    plan.queries.append(cp.CompiledQuery(id="br0", type="ENTITY", query="tension and release in music", weight=0.6, role="bridge", origin="BRIDGE"))
    rec = cp.sync_facets(plan)
    by_id = {q.id: q.facet_id for q in plan.queries}
    assert by_id["p0"] == "f3" and by_id["br0"] is None                      # overlap attaches; no overlap = no single facet
    assert rec == {"n": 4, "source": "facet_step", "attached": 1, "unattached": ["br0"]}
    assert next(f for f in plan.facets if f["id"] == "f3")["query_ids"] == ["q2", "p0"]
    assert cp.sync_facets(plan)["attached"] == 0                              # idempotent
    from polymath_shared.subquery_provenance import annotate_subquery_provenance
    block = annotate_subquery_provenance(plan, None)
    rows = {r["id"]: r for r in block["subqueries"]}
    assert rows["q2"]["facet_id"] == "f3" and rows["p0"]["facet_id"] == "f3" and rows["br0"]["facet_id"] is None
    receipt = cp.plan_receipt(plan)
    assert receipt["facets"] == plan.facets and all("facet_id" in q for q in receipt["queries"])
    assert receipt["queries"][0]["facet_id"] == "f1" and receipt["subquery_provenance"]["subqueries"][0]["facet_id"] == "f1"
    assert receipt["queries"][-1]["facet_id"] is None                            # the bridge that serves no single facet says so
    # the coverage verdict from the final evidence (a chunk per query id, judged): covered = above the floor
    final_detail = [{"chunk_id": "c1", "doc_id": "d1", "rerank_score": 2.0, "query_ids": ["q0"]},
                    {"chunk_id": "c2", "doc_id": "d2", "rerank_score": -3.0, "query_ids": ["q1", "q3"]},     # f2: only below-floor evidence
                    {"chunk_id": "c3", "doc_id": "d3", "rerank_score": 0.4, "query_ids": ["p0"]}]         # f3 covered through its probe
    cov = fx.facet_coverage(plan.facets, final_detail, floor=0.5)
    assert cov == {"covered": ["f1", "f3"], "uncovered": ["f2", "f4"], "judge": "live"}
    unjudged = fx.facet_coverage(plan.facets, [{"chunk_id": "c9", "doc_id": "d1", "rerank_score": None, "query_ids": ["q4"]}], floor=0.5)
    assert unjudged == {"covered": ["f4"], "uncovered": ["f1", "f2", "f3"], "judge": "unjudged"}


def test_the_flag_off_is_the_pre_facet_compiler_and_receipt(monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "0")
    assert not cp.facets_enabled() and cp.facets_enabled({cp.FACETS_FLAG: "1"}) and cp.facets_enabled({})
    seen: dict = {}
    plan = cp.compile_plan(Q_ECOM, [], ["cinema"], _complete_returning(_wording_reply(), seen))
    assert plan.facets == [] and "facets" not in plan.compiler and all(q.facet_id is None for q in plan.queries)
    assert "FACETS OF THE REQUEST" not in seen["user"] and "FACETS OF THE REQUEST" not in seen["system"]
    assert seen["max_tokens"] == cp.COMPILER_MAX_OUTPUT_TOKENS and len(plan.queries) == cp.MAX_QUERIES
    receipt = cp.plan_receipt(plan)
    assert "facets" not in receipt and all("facet_id" not in q for q in receipt["queries"])
    from polymath_shared.subquery_provenance import annotate_subquery_provenance
    assert all("facet_id" not in r for r in annotate_subquery_provenance(plan, None)["subqueries"])
    fb = cp.fallback_plan("What is AU21?", reason="transport:x")
    assert fb.facets == [] and "facets" not in fb.compiler
    assert cp.system_prompt() == cp.SYSTEM_PROMPT and cp.user_prompt("q", [], ["cinema"])[0] == cp.user_prompt("q", [], ["cinema"], facets=None)[0]


# ---------------------------------------------------------------------------------------------------------
# the orchestrator wiring: the blind step runs beside the scout, its facets reach the wording call, the receipt
# ---------------------------------------------------------------------------------------------------------
class _Resp:
    def __init__(self, content):
        self._content, self.headers = content, {}

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _wire(monkeypatch, *, facets_reply, plan_reply, facets_flag="1"):
    monkeypatch.setenv(cp.FACETS_FLAG, facets_flag)
    monkeypatch.setenv(cp.CONTRACT_FLAG, "0")
    for k in ("POLYMATH_CHAT_BRIDGE_COMPILER", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_PROFILE_SCOUT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(ui, "_profile_scout", lambda m, c, scope=None: (["Adweek Copywriting Handbook"], None, {"contract": "profile-scout-v1"}))
    monkeypatch.setattr(ui, "_resolve_plan_constraints", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_add_corpus_explore_expansion", lambda *a, **k: None)
    ep = SimpleNamespace(name="compiler_lane", url="https://example.invalid", model="stub", limiter_key="c", api_key="not-a-key", cloud_opts={})
    monkeypatch.setattr(pool_mod, "cloud_endpoints", lambda: [ep])
    monkeypatch.setattr(pool_mod, "stage_pin", lambda stage: [ep.name])
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        system = json["messages"][0]["content"]
        return _Resp(__import__("json").dumps(facets_reply if "FACET NAMER" in system else plan_reply))
    monkeypatch.setattr(client_mod.httpx, "post", post)

    def complete_one(self, user_prompt, *, system_prompt, max_tokens):
        return self._chat(user_prompt, max_tokens, system_prompt=system_prompt)[0], None
    monkeypatch.setattr(client_mod.LLMExtractionClient, "complete_one", complete_one)

    @contextmanager
    def fake_tx():
        yield SimpleNamespace(execute=lambda sql, params=(): SimpleNamespace(fetchall=list))
    monkeypatch.setattr(ui, "tx", fake_tx)
    return sent


def test_the_orchestrator_runs_the_blind_step_first_and_the_wording_call_reads_its_facets(monkeypatch):
    sent = _wire(monkeypatch, facets_reply=FACETS_ECOM, plan_reply=_wording_reply())
    plan = ui._compile_chat_plan(Q_ECOM, [], ["cinema"], session_key="facets")
    assert not plan.fallback and len(sent) == 2
    facet_call, wording_call = sent[0], sent[1]
    assert "FACET NAMER" in facet_call["messages"][0]["content"] and facet_call["max_tokens"] == fx.FACET_MAX_OUTPUT_TOKENS
    for w in LIBRARY_WORDS:                                              # the scout's titles never reach the facet step
        assert w not in facet_call["messages"][0]["content"] and w not in facet_call["messages"][-1]["content"]
    assert "Adweek Copywriting Handbook" in wording_call["messages"][-1]["content"]      # …but do reach the wording call
    assert "[f3] directing the AI video model" in wording_call["messages"][-1]["content"]
    assert [q.facet_id for q in plan.queries] == ["f1", "f2", "f3", "f2", "f4"] and [f["id"] for f in plan.facets] == ["f1", "f2", "f3", "f4"]
    fr = plan.compiler["facets"]
    assert fr["step"]["contract"] == fx.FACET_CONTRACT and fr["step"]["n"] == 4 and fr["step"]["fallback"] is False and "facets" not in fr["step"]
    assert fr["inserted"] == ["f4"] and fr["attach"] == {"attached": 0, "unattached": []} and "facets" in plan.compiler["compile_ms"]
    # the step fails → the plan still compiles on the wording call and derives its facets (one per USER query)
    sent2 = _wire(monkeypatch, facets_reply={"nothing": True}, plan_reply=_wording_reply())
    plan2 = ui._compile_chat_plan(Q_ECOM, [], ["cinema"], session_key="facets")
    assert not plan2.fallback and len(sent2) == 2 and plan2.compiler["facets"]["step"]["reason"] == "invalid_facets:facets_missing"
    assert plan2.compiler["facets"]["source"] == "derived" and [f["query_ids"] for f in plan2.facets] == [["q0"], ["q1"], ["q2"], ["q3"]]
    # the flag off: one call, no facet fields anywhere
    sent3 = _wire(monkeypatch, facets_reply=FACETS_ECOM, plan_reply=_wording_reply(), facets_flag="0")
    plan3 = ui._compile_chat_plan(Q_ECOM, [], ["cinema"], session_key="facets")
    assert len(sent3) == 1 and plan3.facets == [] and "facets" not in plan3.compiler


@pytest.mark.parametrize("bad", [None, SimpleNamespace(result=lambda timeout=None: (_ for _ in ()).throw(TimeoutError()))])
def test_a_missing_or_late_step_is_a_receipted_none(bad):
    rec = ui._join_facet_step(bad)
    assert rec is None if bad is None else (rec["facets"] is None and rec["reason"] == "join:TimeoutError")
