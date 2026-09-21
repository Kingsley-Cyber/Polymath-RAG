"""Restoration Slice 2 — hypothesis-specific research fidelity (SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE §9).

hypothesis -> ITS uncertainty -> ITS research program -> ITS query. §9.1 every legitimate gap source, deduplicated, stably
identified · §9.2 an unowned gap is a TYPED refusal on Polymath's side (submit time + at the Trail boundary) · §9.3 queries compiled
from semantic state, governance text never searched · §9.4 Trail's template slots bound per hypothesis, an unbindable slot reported ·
§9.5 `K_questions.need` reaches `K_retrieve` (a domain-compiled need only) · §9.6 field-record mapping · §9.7 acceptance.

No database, no network. The ecommerce binding is executed OUT OF PROCESS through its own protocol (JSON in, JSON out) — the same
door the worker uses — so nothing here imports `workers` (under pytest in a worktree that package resolves to the MAIN checkout)."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "tests" / "determinism"))
from polymath_shared.adapter import evidence_boundary as EB  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter import research_gaps as RG  # noqa: E402
from polymath_shared.adapter import semantic_view as SV  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter.transitions import SubmissionRejected  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

BINDING = ROOT / "adapters" / "ecommerce" / "binding.py"
H1, H2, DEAD = "hyp_a5423927fff69cb4bc52eead", "hyp_2bb7c484b0dbf0327bb99c49", "hyp_" + "d" * 24
GOVERNANCE_PHRASES = ("corroborate", "independent", "observations", "admitted")


def test_the_code_under_test_is_this_checkout():
    for mod in (EB, M, RG, SV, service):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__
    assert BINDING.is_file()


# ─────────────────────────────────────────────────────────── state shaped like run 5, round 2
def _ledger(hid, **over):
    base = {"hypothesis_id": hid, "revision": 1, "status": "revised", "statement": "s" * 12, "population": None, "activity": None, "task": None,
            "context": None, "mechanism": None, "suspected_friction": None, "knowledge_gaps": [], "falsifiers": [], "knowledge_support": []}
    return {**base, **over}


CURRENT = {
    H1: _ledger(H1, statement="Landscape photographers on the trail miss shots because spare batteries are buried in the pack", population="landscape photographers",
                activity="landscape photography", task="reach spare batteries and filters", context="on the trail, in cold or wet weather",
                suspected_friction="buried accessories", falsifiers=["pack access is quick and never costs a shot"],
                knowledge_gaps=[{"gap_id": "gap_a5423927_0", "question": "Do landscape photographers miss shots digging for batteries in the bag?", "evidence_role": "friction", "status": "open"},
                                {"gap_id": "gap_a5423927_1", "question": "an already researched gap", "evidence_role": "behavior", "status": "researched"}]),
    H2: _ledger(H2, statement="Wildlife photographers carry a heavy telephoto lens awkwardly while hiking", population="wildlife photographers",
                activity="wildlife photography", task="carry a telephoto lens while hiking", suspected_friction="lens weight on the neck"),
    DEAD: _ledger(DEAD, status="killed", knowledge_gaps=[{"gap_id": "gap_dead_0", "question": "a dead hypothesis's gap", "evidence_role": "behavior", "status": "open"}]),
}
OUTPUTS = {
    "C_bridge": {"bridges": [{"hypothesis_id": H1, "gaps": ["Do lone outdoor photographers stop work to reach spares?"]},
                             {"hypothesis_id": H2, "gaps": ["do they already use a chest harness?"]}]},
    "G_mechanisms": {"knowledge_gaps": [{"hypothesis_id": H1, "question": "do landscape photographers miss shots digging for batteries in the bag?", "evidence_role": "friction"},
                                        {"hypothesis_id": H2, "question": "How do wildlife photographers carry a heavy telephoto lens while hiking?", "evidence_role": "workaround"}]},
    "K_revise": {"open_gaps": [{"hypothesis_id": H2, "question": "Independent voices: do hikers outside one thread report neck strain?", "evidence_role": "friction", "note": "one thread so far"}]},
    "L_judge": {"operation_kind": "hypotheses.judge", "trail_operation_id": "top_1",
                "open_gaps": [{"gap_id": "gap-bc52eead-independence", "hypothesis_id": H1, "question": "corroborate from a second independent source", "evidence_role": "friction"},
                              {"gap_id": "gap-7bb99c49-volume", "hypothesis_id": H2, "question": "reach 10 independent observations (2 so far)", "evidence_role": "friction"}]},
}
ORDER = ("C_bridge", "G_mechanisms", "K_revise", "L_judge")


# ─────────────────────────────────────────────────────────── §9.1 every legitimate source, once, owned, stably identified
def test_harvest_merges_every_source_without_duplication_and_nothing_shadows_the_agents_open_gaps():
    h = RG.harvest(CURRENT, OUTPUTS, order=ORDER)
    got = [(g["hypothesis_id"][-4:], g["origin"]) for g in h["knowledge_gaps"]]
    assert got == [("eead", "ledger"), ("9c49", "step"), ("9c49", "agent_open"), ("eead", "bridge"), ("9c49", "bridge")]
    # the ledger gap and the step's identically worded gap are ONE gap, and it keeps the LEDGER's id
    assert h["knowledge_gaps"][0]["gap_id"] == "gap_a5423927_0" and sum(1 for g in h["knowledge_gaps"] if "digging for batteries" in g["question"].lower()) == 1
    assert not any("researched" in g["question"] or "dead" in g["question"] for g in h["knowledge_gaps"])
    # Trail's own gate gaps travel beside them, keep Trail's ids, and are marked as governance
    assert [(g["gap_id"], g["origin"]) for g in h["open_gaps"]] == [("gap-bc52eead-independence", "trail_gate"), ("gap-7bb99c49-volume", "trail_gate")]
    assert h["refused"] == [] and RG.harvest(CURRENT, OUTPUTS, order=ORDER) == h


def test_gap_identity_survives_rounds():
    first = {g["question"]: g["gap_id"] for g in RG.harvest(CURRENT, OUTPUTS, order=ORDER)["knowledge_gaps"]}
    later = dict(OUTPUTS, G_mechanisms={"knowledge_gaps": list(reversed(OUTPUTS["G_mechanisms"]["knowledge_gaps"])) + [
        {"hypothesis_id": H1, "question": "a NEW question in round two", "evidence_role": "behavior"}]})
    second = {g["question"]: g["gap_id"] for g in RG.harvest(CURRENT, later, order=ORDER)["knowledge_gaps"]}
    assert all(second[q] == i for q, i in first.items()) and len(set(second.values())) == len(second) == len(first) + 1   # never `gap_0`, `gap_1` per round


# ─────────────────────────────────────────────────────────── §9.2 an unowned gap is refused, never given to the first hypothesis
def test_harvest_refuses_unowned_and_dead_owner_gaps_with_a_typed_code():
    outputs = dict(OUTPUTS, K_revise={"open_gaps": [{"question": "whose gap is this?", "evidence_role": "friction"},
                                                     {"hypothesis_id": DEAD, "question": "a gap of a killed hypothesis", "evidence_role": "friction"}]})
    h = RG.harvest(CURRENT, outputs, order=ORDER)
    assert [(r["code"], r["origin"]) for r in h["refused"]] == [("GAP_OWNER_MISSING", "agent_open"), ("GAP_OWNER_NOT_LIVE", "agent_open")]
    sent = RG.trail_gap_payload({"research_gaps": h})
    assert all(g["hypothesis_id"] in (H1, H2) for g in sent["knowledge_gaps"] + sent["open_gaps"])             # Trail's fallback is unreachable
    assert not any("whose gap" in g["question"] for g in sent["knowledge_gaps"])


def test_what_trail_receives_is_closed_at_its_four_wire_fields_and_a_step_that_did_not_opt_in_is_untouched():
    sent = RG.trail_gap_payload({"research_gaps": RG.harvest(CURRENT, OUTPUTS, order=ORDER)})
    assert all(tuple(g) == RG.TRAIL_GAP_FIELDS for g in sent["knowledge_gaps"] + sent["open_gaps"])            # ResearchKnowledgeGapV1 is extra="forbid"
    assert RG.trail_gap_payload(None) is None and RG.trail_gap_payload({"hypotheses": []}) is None


@pytest.fixture
def runtime(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    service.reset_registry()
    yield store
    service.reset_registry()


def test_submit_refuses_a_top_level_gap_without_a_live_owner(runtime):
    fixtures = ROOT / "tests" / "fixtures" / "adapter_semantic_view"
    rid = service.start(None, adapter_id="fixture.semantic_continuity", input_payload={"seed": "how a camera crew keeps equipment working"}, directory=fixtures)["run_id"]
    rows = [{"id": "chunk_1", "kind": "chunk", "text": "t"}]
    executors = {"POLYMATH_RETRIEVE": lambda step, state, m: {"output": {"rows": rows}, "evidence_refs": [{"kind": "chunk", "id": "chunk_1"}]}}
    service.advance(None, rid, executors, max_steps=1, directory=fixtures)
    service.advance(None, rid, executors, max_steps=1, directory=fixtures)
    step = service.next_step(None, rid, directory=fixtures)["step"]
    payload = {"primitives": {}, "latent_structures": [], "population_leads": []}
    for bad, code in (({"knowledge_gaps": [{"question": "whose?", "evidence_role": "behavior"}]}, "GAP_OWNER_MISSING"),
                      ({"open_gaps": [{"hypothesis_id": "hyp_" + "9" * 24, "question": "whose?", "evidence_role": "behavior"}]}, "GAP_OWNER_NOT_LIVE")):
        with pytest.raises(SubmissionRejected) as exc:
            service.submit(None, rid, {"step_id": step["step_id"], "payload": {**payload, **bad}, "submitted_by": {"agent_identity": "t"}}, directory=fixtures)
        assert exc.value.errors[0].startswith(code)
    assert runtime.current_step(None, rid)["status"] == "issued"                                               # the agent may correct and resubmit
    service.submit(None, rid, {"step_id": step["step_id"], "payload": payload, "submitted_by": {"agent_identity": "t"}}, directory=fixtures)


def test_the_view_scope_carries_the_harvest_for_steps_that_opt_in():
    assert service._wants_semantics({"config": {"gaps_from": "context.semantics.research_gaps"}})
    assert service._wants_semantics({"config": {"inputs": {"a": ["outputs.x", "context.semantics.query"]}}})
    assert not service._wants_semantics({"config": {"stage": "field_evidence", "inputs": {"a": "context.hypotheses"}}})
    m = M.load_manifest(ROOT / "config" / "adapters" / "ecommerce.product_research.json")
    assert m.steps["H_gaps"]["config"]["gaps_from"] == "context.semantics.research_gaps"
    assert {"semantics", "research_gaps"} <= set(m.steps["H_plan"]["config"]["inputs"]) and "semantics" in m.steps["J_cards"]["config"]["inputs"]
    assert m.steps["K_revise"]["output_schema"]["properties"]["open_gaps"]["items"]["required"] == ["hypothesis_id", "question", "evidence_role"]
    assert m.steps["K_retrieve"]["config"]["source"] == "outputs.K_questions.need" and m.steps["K_questions"]["type"] == "DOMAIN_OPERATION"


# ─────────────────────────────────────────────────────────── §9.5 the computed corpus need reaches retrieval — and only a domain-compiled one
def test_a_domain_compiled_need_is_the_retrieval_need_and_an_agent_written_one_never_is():
    import inspect
    seed = {"seed": "how a camera crew keeps equipment working"}
    outputs = {"K_questions": {"need": "What reduces  the time to reach a spare battery with one hand?"}, "K_revise": {"need": "an LLM-written reformulation"}}
    trusted = ["K_questions"]                                                                                    # the manifest's DOMAIN_OPERATION steps
    need = EB.domain_compiled_need({"source": "outputs.K_questions.need"}, outputs, trusted)
    assert need == "What reduces the time to reach a spare battery with one hand?"
    assert EB.original_needs({"source": "outputs.K_questions.need"}, seed, compiled_need=need) == [need]
    # the law that existed stays a law: the need function can not see a step output, and nothing but domain code is ever trusted
    assert "outputs" not in inspect.signature(EB.original_needs).parameters
    assert EB.domain_compiled_need({"source": "outputs.K_revise.need"}, outputs, trusted) is None               # an agent-answered step
    assert EB.domain_compiled_need({"source": "input.seed"}, outputs, trusted) is None
    assert EB.domain_compiled_need({"source": "outputs.K_questions.need"}, {"K_questions": {"need": "  "}}, trusted) is None     # no cluster yet
    assert EB.original_needs({"source": "outputs.K_questions.need"}, seed) == [seed["seed"]]                     # nothing resolved: the seed, as before
    assert EB.original_needs({"query_from": "hypotheses"}, seed, None, [{"statement": "a live hypothesis"}], compiled_need=need) == ["a live hypothesis"]


def test_the_runtime_resolves_the_need_and_hands_it_to_the_boundary_executor_in_memory(runtime):
    fixtures = ROOT / "tests" / "fixtures" / "adapter_research_fidelity"
    seen: dict[str, dict] = {}

    def knowledge(step, state, m):
        seen[step["step_id"]] = step
        return {"output": {"rows": [], "needs": EB.original_needs(m.step(step["step_id"]).get("config"), state.input, None, None, compiled_need=step.get("_compiled_need"))}}

    executors = {"POLYMATH_RETRIEVE": knowledge, "DOMAIN_OPERATION": lambda step, state, m: {"output": {"need": "what holds a spare battery within reach of one hand?"}}}
    rid = service.start(None, adapter_id="fixture.research_fidelity", input_payload={"seed": "how a camera crew keeps equipment working"}, directory=fixtures)["run_id"]
    st = service.advance(None, rid, executors, directory=fixtures)
    assert st.status == "completed"
    rows = {r["step_id"]: r for r in runtime.list_steps(None, rid)}
    assert rows["first_pass"]["output"]["needs"] == ["how a camera crew keeps equipment working"]              # no compiled need yet: the seed
    assert rows["loop_pass"]["output"]["needs"] == ["what holds a spare battery within reach of one hand?"]    # K_questions-style need reached retrieval
    assert "_compiled_need" not in rows["loop_pass"]["step"] and "_compiled_need" in seen["loop_pass"]           # in memory only


# ─────────────────────────────────────────────────────────── the engine binding, out of process (the worker's own door)
def _binding(operation: str, inputs: dict) -> dict:
    req = {"schema_version": "domain_operation_request.v1", "domain": "ecommerce", "operation": operation, "run_id": "adr_" + "2" * 32, "step_id": "op",
           "input": {}, "inputs": inputs, "config": {}}
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, str(BINDING)], input=json.dumps(req), capture_output=True, text=True, timeout=120, cwd=str(BINDING.parent), env=env)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


def _semantics():
    view = SV.build({h: {**s, "run_id": "r", "parent_hypothesis_ids": [], "trail_priors": [], "field_evidence_ids": [], "assumptions": [], "contradictions": []}
                     for h, s in CURRENT.items()}, {"C_primitives": {"primitives": {"workarounds": ["spares taped to the tripod leg"], "evidence_refs": {}}}, **OUTPUTS},
                    order=("C_primitives",) + ORDER)
    return SV.scope(view)["query"]


def _directive(gaps):
    trail = RG.trail_gap_payload({"research_gaps": gaps})
    return {"objective": "find first-person field evidence for the live hypotheses", "geography": None, "language": None, "hypothesis_ids": [H1, H2],
            "evidence_gaps": trail["knowledge_gaps"] + trail["open_gaps"],
            "search_intents": [{"intent_id": "q-complaint", "intent": "Find direct complaint language", "evidence_goal": "complaint", "evidence_roles": ["friction", "behavior"], "template": "{activity} {task} annoying"},
                               {"intent_id": "q-wish", "intent": "Find missing feature language", "evidence_goal": "complaint", "evidence_roles": ["friction", "behavior"], "template": "{activity} wish it had {friction_family}"},
                               {"intent_id": "q-territory", "intent": "Find products", "evidence_goal": "complaint", "evidence_roles": ["friction"], "template": "best {product_territory} for {activity}"},
                               {"intent_id": "q-workaround", "intent": "Find workaround discussions", "evidence_goal": "workaround", "evidence_roles": ["workaround"], "template": None}],
            "preferred_source_roles": ["community_discussion"], "disallowed_source_roles": ["supplier_listing"], "minimum_independent_sources": 2,
            "freshness_requirement": {"max_age_days": 365, "policy_ref": "strictest-routed-source"}, "budget": {"max_queries": 66, "max_sources": 20, "max_observations": 80},
            "success_condition": "10 independent complaints", "falsification_condition": "independent communities do not report the friction"}


@pytest.fixture(scope="module")
def plan():
    gaps = RG.harvest(CURRENT, OUTPUTS, order=ORDER)
    directive = _directive(gaps)
    resp = _binding("research.plan", {"research_directive": directive, "semantics": _semantics(), "research_gaps": gaps,
                                      "hypotheses": [SV.trail_projection(s) for h, s in CURRENT.items() if h != DEAD]})
    assert resp["ok"], resp
    return directive, resp["output"]


def test_acceptance_h1_gap_h1_query_h1_intent_and_h2_likewise(plan):
    _, out = plan
    index = out["intent_index"]
    by_h = {h: [i for i in index if i["hypothesis_id"] == h] for h in (H1, H2)}
    assert by_h[H1] and by_h[H2]
    h1_words, h2_words = {"landscape", "batteries", "spare"}, {"wildlife", "telephoto", "lens"}
    for i in by_h[H1]:
        assert not (set(i["query"].split()) & h2_words), i                                                     # H1's program speaks H1's language
    for i in by_h[H2]:
        assert not (set(i["query"].split()) & h1_words), i
    assert any(set(i["query"].split()) & h1_words for i in by_h[H1]) and any(set(i["query"].split()) & h2_words for i in by_h[H2])
    issued = {i["intent_id"] for i in out["research_directive"]["search_intents"]}
    assert {i["intent_id"] for i in index} <= issued                                                            # every indexed intent is one the harness receives
    assert any(i["gap_id"] == "gap_a5423927_0" and i["intent_id"].endswith(":gap_a5423927_0") for i in by_h[H1])   # the gap's id rides the intent


def test_no_intent_reaches_the_harness_with_an_unbound_slot(plan):
    _, out = plan
    intents = out["research_directive"]["search_intents"]
    assert not [i for i in intents if "{" in (i.get("template") or "") or "{" in i["intent"]]
    bound = [i for i in intents if i["intent_id"].startswith("q-complaint:")][:2]
    assert [i["template"] for i in bound] == ["landscape photography reach spare batteries filters annoying", "wildlife photography carry telephoto lens hiking annoying"]                   # function words never enter a search string
    assert [i["intent_id"] for i in bound] == ["q-complaint:a5423927", "q-complaint:2bb7c484"] and bound[0]["evidence_roles"] == ["friction", "behavior"]
    # a slot nobody can bind yet (the territory NAME is Trail's to return — Slice 4) is REPORTED, per hypothesis, never sent
    assert {(u["intent_id"], u["hypothesis_id"], tuple(u["missing_slots"])) for u in out["planned"]["unresolved_slots"]} == \
        {("q-territory", H1, ("product_territory",)), ("q-territory", H2, ("product_territory",))}
    assert any(i["intent_id"] == "q-workaround" for i in intents)                                              # a template without slots is TrailSignal's, untouched


def test_governance_text_is_never_a_search_string(plan):
    _, out = plan
    gate = [i for i in out["intent_index"] if i["origin"] == "trail_gate"]
    assert {i["gap_id"] for i in gate} == {"gap-bc52eead-independence", "gap-7bb99c49-volume"}
    for i in gate:
        assert not (set(i["query"].split()) & set(GOVERNANCE_PHRASES)), i
    assert next(i for i in gate if i["hypothesis_id"] == H1)["query"] == "landscape photographers reach spare batteries buried accessories"
    for i in out["research_directive"]["search_intents"]:
        assert "corroborate" not in (i.get("template") or "") and "observations" not in (i.get("template") or "")
    # a gap a reasoning step wrote contributes ITS OWN words, after the hypothesis's vocabulary
    own = next(i for i in out["intent_index"] if i["origin"] == "agent_open")
    words = set(own["query"].split())
    assert {"wildlife", "photographers"} <= words and {"hikers", "strain"} <= words and own["hypothesis_id"] == H2      # the gap's OWN words, after the hypothesis's
    assert not (words & {"independent", "voices", "thread"})                                                   # even when a reasoning step echoes governance language
    assert {i["hypothesis_id"] for i in out["intent_index"] if i["origin"] == "falsifier"} == {H1}              # only H1 states a falsifier


def test_trail_governance_is_untouched_and_what_did_not_fit_is_counted(plan):
    directive, out = plan
    d = out["research_directive"]
    for key in ("objective", "hypothesis_ids", "evidence_gaps", "preferred_source_roles", "disallowed_source_roles", "freshness_requirement", "geography",
                "language", "minimum_independent_sources", "success_condition", "falsification_condition", "budget"):
        assert d[key] == directive[key], key
    p = out["planned"]
    assert out["governance_unchanged"] is True and p["compiler"] == "semantic.v1" and len(d["search_intents"]) <= p["intent_cap"] <= 100
    assert p["bound_trail_intents"] == 5 and p["subjects"] == 8 and p["channel_intents"] + p["dropped_over_budget"] > 0 and p["refused_gaps"] == []


def test_without_semantics_the_operation_behaves_exactly_as_before():
    directive = _directive(RG.harvest(CURRENT, OUTPUTS, order=ORDER))
    out = _binding("research.plan", {"research_directive": directive})["output"]
    assert "intent_index" not in out and out["research_directive"]["search_intents"][0]["template"] == "{activity} {task} annoying"


# ─────────────────────────────────────────────────────────── §9.6 the field-record mapping
def test_field_records_read_the_current_ledger_state_and_never_call_a_host_a_community():
    receipt = {"action_id": "hact_1", "observations": [
        {"observation_id": "obs_1", "source_id": "s1", "claim": "I tape a spare battery to the tripod leg", "paraphrase_or_excerpt": "been doing this for years", "context": "lead: lead_1"},
        {"observation_id": "obs_2", "source_id": "s1", "claim": "digging through the pack costs me the light", "paraphrase_or_excerpt": "every dawn", "context": ""}],
        "sources": [{"source_id": "s1", "url": "https://www.photrio.com/forum/threads/1", "source_class": "forum"}]}
    admission = {"admitted": [{"admitted_evidence_id": "fev_1", "observation_id": "obs_1", "evidence_role": "workaround", "polarity": "supporting", "hypothesis_ids": [H1],
                               "independence_group": "g1", "freshness": "fresh", "source_class": "forum"},
                              {"admitted_evidence_id": "fev_2", "observation_id": "obs_2", "evidence_role": "friction", "polarity": "supporting", "hypothesis_ids": [H2],
                               "independence_group": "g2", "freshness": "fresh", "source_class": "forum"}]}
    out = _binding("population.evidence_cards", {"admissions": [admission], "receipts": [receipt], "semantics": _semantics(),
                                                 "hypotheses": [{"statement": "generation-time proposal", "suspected_friction": "STALE friction"}], "hypothesis_ids": [H1],
                                                 "population_leads": [{"id": "lead_1", "name": "landscape photographers who hike"}], "community_leads": []})["output"]
    rec = {r["id"]: r for r in out["field_records"]}
    assert rec["fev_1"]["community"] == "landscape photographers who hike" and rec["fev_2"]["community"] == "wildlife photographers"   # the lead, else the population
    assert "photrio" not in rec["fev_1"]["community"] and rec["fev_1"]["source_identity"]["platform"] == "photrio"                     # the host stays the SOURCE identity
    assert rec["fev_1"]["workaround"] == "I tape a spare battery to the tripod leg" and rec["fev_1"]["quote_ref"] == "been doing this for years"
    assert rec["fev_1"]["friction_family"] == "buried accessories" and rec["fev_2"]["friction_family"] == "lens weight on the neck"   # revised state, SPLIT-safe
    assert rec["fev_2"]["workaround"] == ""
