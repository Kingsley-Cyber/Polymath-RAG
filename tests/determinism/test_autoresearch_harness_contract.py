"""AUTORESEARCH-SOURCES-AND-HARNESS-V1 (register 11.489), the runtime half — what ANY MCP agent harness is given:
  * H-01: both MCP servers publish ONE operating guide (prompt `run_governed_research` + four resources), byte-identical, and it
    names no source and no harness (the runtime's neutrality law, ADR-0019 §6);
  * H-02 / H-04: a HARNESS_ACTION step carries the receipt contract as its `output_schema` plus the neutral receipt rules, and the
    contract's own example receipt validates against it;
  * A-04: the requester's limits reach the research action (geography / language fill what TrailSignal left open; freshness only
    tightens; constraints / exclusions / category travel in the objective);
  * H-07: the tool descriptions say what a harness must send (corpus_ids for a non-admin key; the full receipt field list).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import re
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("shared", "orchestrator", "workers"):
    sys.path.insert(0, str(ROOT / _sub))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import harness_guide as HG  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import transitions as T  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402

#: the runtime neutrality law's vocabulary (tests/determinism/test_adapter_runtime_neutrality.py)
SOURCE_NAMES = ("reddit", "youtube", "tiktok", "instagram", "facebook", "amazon", "walmart", "etsy", "ebay", "homedepot", "home_depot", "lowes",
                "alibaba", "cj_dropshipping", "cjdropshipping", "1688", "searxng", "google", "exa", "camofox", "playwright", "crawl4ai")
HARNESS_IDS = ("hermes", "claude-code", "claude_code", "codex", "opencode", "openclaw", "gemini")


def _names_nothing(text: str, where: str) -> None:
    low = text.lower()
    for w in SOURCE_NAMES + HARNESS_IDS:
        assert re.search(rf"(?<![a-z0-9_]){re.escape(w)}(?![a-z0-9_])", low) is None, f"{where} names {w!r}"


def _servers():
    from orchestrator import mcp_server as A
    spec = importlib.util.spec_from_file_location("polymath_mcp_under_test", ROOT / "mcp_server" / "polymath_mcp.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    return {"A": A.mcp, "B": B.server}


async def _published(server) -> dict:
    prompts = {p.name for p in await server.list_prompts()}
    uris = sorted(str(r.uri) for r in await server.list_resources())
    texts = {u: [getattr(c, "content", c) for c in await server.read_resource(u)] for u in uris}
    prompt = await server.get_prompt(HG.PROMPT_NAME, {"adapter_id": "some.adapter", "seed": "a seed"})
    return {"prompts": prompts, "uris": uris, "texts": texts, "prompt": json.dumps(prompt.model_dump(mode="json"), sort_keys=True)}


# ─────────────────────────────────────────────────────────── H-01: one guide, both servers, neutral
def test_both_servers_publish_the_same_guide_prompt_and_resources():
    got = {label: asyncio.run(_published(server)) for label, server in _servers().items()}
    assert got["A"] == got["B"]
    a = got["A"]
    assert a["prompts"] == {HG.PROMPT_NAME} and a["uris"] == sorted(HG.RESOURCE_URIS)
    assert a["texts"][HG.GUIDE_URI] == [HG.GUIDE]
    for uri, rel in HG.FILES.items():                                   # the files as they are: the pinned Trail table moves with a re-pin
        assert a["texts"][uri] == [(ROOT / rel).read_text(encoding="utf-8")]
    assert "adapter_list" in a["prompt"] and "some.adapter" in a["prompt"] and "a seed" in a["prompt"]


def test_the_guide_and_the_receipt_rules_name_no_source_and_no_harness():
    _names_nothing(HG.GUIDE, "the operating guide")
    _names_nothing(HG.PROMPT_DESCRIPTION, "the prompt description")
    for rule in T.HARNESS_RECEIPT_RULES:
        _names_nothing(rule, "a receipt rule")
    for needle in ("adapter_next", 'kind="receipt"', "canonical permalink", "never bypass", HG.SOURCES_URI, HG.RECEIPT_SCHEMA_URI,
                   "STALE_BEYOND_POLICY", "independence_group"):
        assert needle in HG.GUIDE, needle


# ─────────────────────────────────────────────────────────── H-02 / H-04: the receipt contract travels in the step
def _harness_state() -> RunState:
    directive = {"objective": "find first-person field evidence", "geography": None, "language": None,
                 "evidence_gaps": [{"gap_id": "gap_0", "hypothesis_id": "hyp_" + "a" * 12, "question": "is the friction recurring?", "evidence_role": "friction"}],
                 "search_intents": [{"intent_id": "q1", "intent": "complaints", "evidence_goal": "complaint", "evidence_roles": ["friction"], "template": "keys bounce running"}],
                 "freshness_requirement": {"max_age_days": 60, "policy_ref": "strictest-routed-source"}, "budget": {"max_queries": 8},
                 "success_condition": "independent complaints", "falsification_condition": "no complaints", "minimum_independent_sources": 2}
    return RunState(run_id="adr_" + "9" * 32, adapter_id="fixture.harness", status="running",
                    input={"seed": "runners lose small items", "geography": "US", "language": "en", "freshness_days": 30,
                           "constraints": ["under 20 dollars"], "exclusions": ["no batteries"], "category": "outdoor"},
                    outputs={"G_directive": {"research_directive": directive, "registry_snapshot": {"snapshot_id": "trs-x", "content_hash": "sha256:" + "0" * 64}}},
                    output_order=("G_directive",))


SPEC = {"step_id": "I_research", "type": "HARNESS_ACTION", "title": "research", "objective": "research", "next": "end",
        "harness": {"action_kind": "AGENT_RESEARCH", "minimum_independent_sources": 3}}


def _action(state: RunState, spec=SPEC) -> dict:
    return service._compile_harness_action(state, spec, "I_research", 1, {"hyp_" + "a" * 12: {"status": "proposed"}},
                                           {"snapshot_id": "trs-x", "content_hash": "sha256:" + "0" * 64}, "2026-09-25T00:00:00Z")


def test_the_requesters_limits_reach_the_research_action():
    action = _action(_harness_state())
    C.assert_valid("harness_action", action)
    assert (action["geography"], action["language"]) == ("US", "en")                                   # TrailSignal left them open
    assert action["freshness_requirement"]["max_age_days"] == 30                                        # the requester tightened 60 -> 30
    assert "The requester's limits" in action["objective"] and all(s in action["objective"] for s in ("under 20 dollars", "no batteries", "outdoor"))
    looser = _harness_state()
    looser.input["freshness_days"] = 365
    assert _action(looser)["freshness_requirement"]["max_age_days"] == 60                              # ... but never loosens it
    plain = _harness_state()
    plain.input.clear(); plain.input["seed"] = "runners lose small items"
    a = _action(plain)
    assert (a["geography"], a["language"], a["freshness_requirement"]["max_age_days"]) == (None, None, 60) and "requester" not in a["objective"]


def test_a_research_step_carries_the_receipt_contract_and_the_example_receipt_validates():
    class _M:                                                               # the one-step manifest surface issue_step reads
        steps = {"I_research": SPEC}
        entry_step_id, terminal_step_id = "I_research", "end"
        budgets = {"max_steps": 10, "max_agent_reason": 5, "max_branch_loops": 2}

        def step(self, sid):
            return self.steps[sid]
    state = _harness_state()
    action = _action(state)
    _, step = T.issue_step(_M(), state, issued_at="2026-09-25T00:00:00Z", harness_action=action)
    assert step["output_schema"] == C.schema("harness_receipt")
    assert list(step["acceptance_rules"])[-len(T.HARNESS_RECEIPT_RULES):] == list(T.HARNESS_RECEIPT_RULES)
    example = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
    jsonschema.Draft202012Validator(step["output_schema"]).validate(example)
    assert all(len(r) <= 500 for r in T.HARNESS_RECEIPT_RULES)                                       # the step contract's item bound


# ─────────────────────────────────────────────────────────── H-07: what the tool descriptions tell a harness
def test_the_tool_descriptions_say_what_a_harness_must_send():
    for label, server in _servers().items():
        tools = {t.name: t.description or "" for t in asyncio.run(server.list_tools())}
        assert "REQUIRED for a non-admin key" in tools["adapter_start"] and "freshness_days" in tools["adapter_start"], label
        assert all(f in tools["adapter_submit"] for f in ("run_id", "started_at", "completed_at", "published_at_if_known", "evidence_role_claimed")), label
        assert HG.PROMPT_NAME in tools["adapter_list"] and "PREFERRED" in tools["adapter_list"], label


# ─────────────────────────────────────────────────────────── A-06: reference fields name records the run produced
def _reason_step() -> dict:
    return {"run_id": "adr_" + "9" * 32, "step_id": "W_interpret", "step_type": "AGENT_REASON", "output_schema": {"type": "object"},
            "context": {"evidence_refs": [{"kind": "field_evidence", "id": "fev_1"}], "hypotheses": [{"hypothesis_id": "hyp_a"}]}}


def test_reference_fields_must_name_records_the_run_produced():
    state = RunState(run_id="adr_" + "9" * 32, adapter_id="fixture.harness", status="awaiting_agent", input={},
                     outputs={"V_score": {"trail_scores": [{"record_id": "score-1"}]}, "R_qualify": {"qualifications": [{"record_id": "qual-market-1"}]}},
                     output_order=("V_score", "R_qualify"))
    step = _reason_step()
    known = T.run_record_ids(state, step)
    assert {"score-1", "qual-market-1", "fev_1", "hyp_a", "V_score"} <= known
    ok = {"product_opportunity": {"trail_score_refs": ["score-1"],
                                  "evidence_chain": [{"hypothesis_id": "hyp_a", "evidence_ids": ["fev_1"], "record_refs": ["qual-market-1"]}]}}
    assert T.validate_submission(step, ok, known_refs=known) == []
    bad = {"product_opportunity": {"trail_score_refs": ["score-999"], "evidence_chain": [{"hypothesis_id": "hyp_a", "record_refs": ["qual-invented"]}]}}
    errs = T.validate_submission(step, bad, known_refs=known)
    assert any("score-999" in e and "qual-invented" in e for e in errs)
    assert T.validate_submission(step, bad) == []                                                   # a caller that passes no run: unchanged
    causes = {"transitions": [{"cause_refs": [{"kind": "chunk", "id": "anything"}]}]}                    # object causes are the ledger's to check
    assert T.validate_submission(step, causes, known_refs=known) == []


def test_the_live_manifest_constrains_evidence_chain_links():
    m = json.loads((ROOT / "config/adapters/ecommerce.product_research.json").read_text())
    schema = next(s for s in m["steps"] if s["step_id"] == "W_interpret")["output_schema"]
    base = {"product_concept": {"title": "t", "mechanism_explanation": "m", "population": "p", "activity": "a", "context": "c", "problem": "x"},
            "remaining_uncertainty": [], "cheapest_falsification_experiment": "interviews"}
    v = jsonschema.Draft202012Validator(schema)
    assert v.is_valid({"product_opportunity": {**base, "evidence_chain": [{"hypothesis_id": "h", "claim": "c", "evidence_ids": ["fev_1"], "record_refs": ["score-1"]}]}})
    assert not v.is_valid({"product_opportunity": {**base, "evidence_chain": ["a free-text link nobody can check"]}})
    assert not v.is_valid({"product_opportunity": {**base, "evidence_chain": [{"hypothesis_id": "h", "source": "trust me"}]}})


# ─────────────────────────────────────────────────────────── A-05: a question the ledger closed stays closed
def test_a_question_the_ledger_closed_never_re_enters_through_another_origin():
    from polymath_shared.adapter import research_gaps as RG
    hid = "hyp_" + "a" * 12
    current = {hid: {"status": "proposed", "knowledge_gaps": [
        {"gap_id": "g_closed", "question": "Do runners lose keys mid-stride?", "evidence_role": "friction", "status": "closed"},
        {"gap_id": "g_done", "question": "Is the bounce worse on trails?", "evidence_role": "behavior", "status": "researched"},
        {"gap_id": "g_open", "question": "Which pocket fails first?", "evidence_role": "behavior", "status": "open"}]}}
    outputs = {"K_revise": {"open_gaps": [{"hypothesis_id": hid, "question": "do runners lose keys   MID-STRIDE?", "evidence_role": "friction"},
                                          {"hypothesis_id": hid, "question": "Does a vest fix it?", "evidence_role": "contradiction"}]},
               "C_bridge": {"bridges": [{"hypothesis_id": hid, "gaps": ["Do runners lose keys mid-stride?", "Is the bounce worse on trails?"]}]}}
    out = RG.harvest(current, outputs, order=("K_revise", "C_bridge"))
    assert [g["question"] for g in out["knowledge_gaps"]] == ["Which pocket fails first?", "Does a vest fix it?", "Is the bounce worse on trails?"]
    assert out["closed_not_reoffered"] == 2                                                         # the closed question, offered twice, re-entered neither time


# ─────────────────────────────────────────────────────────── A-07: a harness can tell which adapter to use
def test_the_catalogue_says_which_product_research_adapter_is_preferred():
    from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests
    desc = {m.adapter_id: str(m.raw.get("description") or "") for m in list_manifests(ADAPTER_DIR)}
    assert desc["ecommerce.product_research"].startswith("PREFERRED")
    assert desc["trail.product_discovery"].startswith("LEGACY") and "prefer ecommerce.product_research" in desc["trail.product_discovery"]
    assert sum(d.startswith("PREFERRED") for d in desc.values()) == 1


def test_the_reference_check_is_opt_in_per_step_and_the_final_interpretations_opt_in():
    """A step's `*_refs` are checked only when its manifest spec says so (`config.refs_must_resolve`) — other adapters' reference
    fields keep their own meaning; the governed product-research final interpretations opt in."""
    run_id = "adr_" + "9" * 32
    state = RunState(run_id=run_id, adapter_id="fixture.harness", status="awaiting_agent", current_step_id="W_interpret", input={},
                     outputs={"V_score": {"trail_scores": [{"record_id": "score-1"}]}}, output_order=("V_score",))
    step = _reason_step()
    invented = {"step_id": "W_interpret", "run_id": run_id, "payload": {"product_opportunity": {"trail_score_refs": ["score-invented"]}},
                "submitted_by": {"agent_identity": "test/agent"}}

    class _M:
        def __init__(self, cfg):
            self.cfg = cfg

        def step(self, sid):
            return {"step_id": sid, "type": "AGENT_REASON", "config": self.cfg}
    T.accept_submission(_M({}), state, step, invented)                                                     # not opted in: unchanged behaviour
    try:
        T.accept_submission(_M({"refs_must_resolve": True}), state, step, invented)
        raise AssertionError("an invented record reference was accepted")
    except T.SubmissionRejected as exc:
        assert "score-invented" in str(exc)
    lawful = dict(invented, payload={"product_opportunity": {"trail_score_refs": ["score-1"]}})
    T.accept_submission(_M({"refs_must_resolve": True}), state, step, lawful)
    from polymath_shared.adapter.manifest import ADAPTER_DIR, list_manifests
    for m in list_manifests(ADAPTER_DIR):
        if m.adapter_id in ("ecommerce.product_research", "trail.product_discovery"):
            assert (m.step("W_interpret").get("config") or {}).get("refs_must_resolve") is True, m.adapter_id
